"""Live-verify the two Stripe email composers (#39) with malicious inputs.

Exercises the actual production rendering functions:
  - app.services.stripe_service._render_payment_success_email
  - app.services.stripe_service._render_payment_failed_email

Parses the resulting HTML with BeautifulSoup and asserts:
  - No live <script> tags
  - No element with on* event-handler attributes
  - No href starts with javascript:
  - Malicious payload appears as escaped text, not as live HTML

Run:
    python outputs/verify_stripe_email_xss_live.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure we can import app.* from this script (same trick scripts/ uses).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env so the StripeService constructor doesn't blow up.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:
    print("ERROR: BeautifulSoup not installed. Run: pip install beautifulsoup4")
    sys.exit(2)

from app.services.stripe_service import StripeService  # noqa: E402

MALICIOUS_NAME = "<script>alert('xss')</script>"
MALICIOUS_PLAN = "<img src=x onerror=alert(1)>"
MALICIOUS_URL = "javascript:alert(1)"

PASS, FAIL = 0, 0


def assert_no_xss(label: str, html: str) -> None:
    global PASS, FAIL
    soup = BeautifulSoup(html, "html.parser")

    # 1. No live <script> tags
    scripts = soup.find_all("script")
    cond1 = len(scripts) == 0
    print(
        f"  [{'PASS' if cond1 else 'FAIL'}] {label}: no <script> tags ({len(scripts)} found)"
    )
    PASS, FAIL = (PASS + 1, FAIL) if cond1 else (PASS, FAIL + 1)

    # 2. No element with on* event-handler attribute
    on_attrs = [
        (tag.name, attr)
        for tag in soup.find_all()
        for attr in tag.attrs
        if attr.startswith("on")
    ]
    cond2 = len(on_attrs) == 0
    print(
        f"  [{'PASS' if cond2 else 'FAIL'}] {label}: no on* event-handler attrs"
        f" ({on_attrs[:5] if on_attrs else 'none'})"
    )
    PASS, FAIL = (PASS + 1, FAIL) if cond2 else (PASS, FAIL + 1)

    # 3. No href starts with javascript:
    js_hrefs = [
        a.get("href")
        for a in soup.find_all("a")
        if (a.get("href") or "").lower().startswith("javascript:")
    ]
    cond3 = len(js_hrefs) == 0
    print(
        f"  [{'PASS' if cond3 else 'FAIL'}] {label}: no javascript: hrefs ({js_hrefs or 'none'})"
    )
    PASS, FAIL = (PASS + 1, FAIL) if cond3 else (PASS, FAIL + 1)

    # 4. Malicious payload appears as escaped text via get_text()
    body_text = soup.get_text()
    cond4a = MALICIOUS_NAME in body_text
    print(
        f"  [{'PASS' if cond4a else 'FAIL'}] {label}:"
        f" malicious name appears as escaped text"
    )
    PASS, FAIL = (PASS + 1, FAIL) if cond4a else (PASS, FAIL + 1)

    cond4b = "&lt;script" in html or "&amp;lt;script" in html
    print(
        f"  [{'PASS' if cond4b else 'FAIL'}] {label}:"
        f" raw HTML contains escaped &lt;script entity"
    )
    PASS, FAIL = (PASS + 1, FAIL) if cond4b else (PASS, FAIL + 1)


def main() -> int:
    svc = StripeService.__new__(StripeService)  # bypass __init__ side effects

    success_inputs = {
        "user_name": MALICIOUS_NAME,
        "plan_name": MALICIOUS_PLAN,
        "amount": 99.99,
        "currency": "usd",
        "invoice_date": "2026-04-29",
        "invoice_pdf": MALICIOUS_URL,
    }
    print("== _render_payment_success_email ==")
    success_html = svc._render_payment_success_email(**success_inputs)
    assert_no_xss("success", success_html)
    print()

    failed_inputs = {
        "user_name": MALICIOUS_NAME,
        "plan_name": MALICIOUS_PLAN,
        "amount": 99.99,
        "currency": "usd",
    }
    print("== _render_payment_failed_email ==")
    failed_html = svc._render_payment_failed_email(**failed_inputs)
    assert_no_xss("failed", failed_html)
    print()

    print("=" * 60)
    print(f"TOTAL: {PASS + FAIL}  PASS: {PASS}  FAIL: {FAIL}")
    print("=" * 60)

    if FAIL:
        # Dump the rendered HTML for inspection on failure
        print("\n--- success_html (head 800 chars) ---")
        print(success_html[:800])
        print("\n--- failed_html (head 800 chars) ---")
        print(failed_html[:800])

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

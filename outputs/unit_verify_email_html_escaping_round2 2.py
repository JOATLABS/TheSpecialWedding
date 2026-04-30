#!/usr/bin/env python3
"""In-process unit verification for stripe_service email HTML escaping (round 2).

Drives the two payment-result composers in `app/services/stripe_service.py`:

  - `StripeService._render_payment_success_email`
  - `StripeService._render_payment_failed_email`

with a malicious-input fixture and confirms the rendered HTML body is XSS-safe:

  - no <script> elements
  - no element with any on* attribute
  - no href starting with "javascript:"
  - the literal "<script>alert('xss')</script>" appears as escaped text

Usage:
    python3 outputs/unit_verify_email_html_escaping_round2.py

Exit code: 0 on full PASS, 1 on any FAIL.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Pin the repo path so this script works inside the cowork workspace mount
# as well as when run from a developer laptop.
REPO_ROOT_CANDIDATES = [
    Path("/sessions/clever-cool-allen/mnt/WeddingWebApp"),
    Path("/Users/emmanuelakinwale/Desktop/WeddingWebApp"),
    Path(__file__).resolve().parents[1],
]
for candidate in REPO_ROOT_CANDIDATES:
    if (candidate / "app" / "services" / "stripe_service.py").exists():
        sys.path.insert(0, str(candidate))
        break

# Minimal env so importing app.* doesn't blow up on missing settings.
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/_unit_test")
os.environ.setdefault("MONGO_DB", "_unit_test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_unit")
os.environ.setdefault("S3_BUCKET_NAME", "_unit_test_bucket")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RESEND_API_KEY", "re_unit")
os.environ.setdefault("FRONTEND_URL", "https://thespecialwedding.io")
os.environ.setdefault(
    "SECRET_KEY", "unit-test-secret-key-with-at-least-32-characters-aaa"
)

from bs4 import BeautifulSoup  # noqa: E402

import app.services.stripe_service as stripe_svc_mod  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))
    print(f"[{PASS if ok else FAIL}] {name}{(' — ' + detail) if detail else ''}")


# Malicious fixtures.
MALICIOUS_NAME = "<script>alert('xss')</script>"
MALICIOUS_PLAN = "<img src=x onerror=alert('plan')>"
MALICIOUS_CURRENCY = "\"><script>alert('cur')</script>"
MALICIOUS_DATE = '<svg onload=alert("date")>'
# Realistic invoice URL — Stripe-provided, not user-supplied. Includes special
# chars (& and ") to prove the escape covers legitimate URLs the way the rest
# of the codebase does (e.g., vendor_service.send_payment_link).
MALICIOUS_INVOICE_PDF = 'https://stripe.example/inv?id="><script>alert(1)</script>&t=1'


def assert_xss_safe(label: str, html_body: str) -> bool:
    """Run the four assertions against html_body."""
    if not html_body or not isinstance(html_body, str):
        record(f"{label}: html body captured", False, repr(html_body)[:120])
        return False

    soup = BeautifulSoup(html_body, "html.parser")

    # 1. No <script> elements at all.
    scripts = soup.find_all("script")
    if scripts:
        record(
            f"{label}: no <script> elements",
            False,
            f"found {len(scripts)}: {[str(s)[:80] for s in scripts]}",
        )
        return False
    record(f"{label}: no <script> elements", True)

    # 2. No element has any on* attribute.
    on_attr_tags = [
        tag for tag in soup.find_all() if any(k.startswith("on") for k in tag.attrs)
    ]
    if on_attr_tags:
        record(
            f"{label}: no on* event-handler attributes",
            False,
            f"found tags: {[str(t)[:80] for t in on_attr_tags]}",
        )
        return False
    record(f"{label}: no on* event-handler attributes", True)

    # 3. No href starts with "javascript:".
    js_hrefs = [
        a
        for a in soup.find_all(href=True)
        if a["href"].lower().lstrip().startswith("javascript:")
    ]
    if js_hrefs:
        record(
            f"{label}: no javascript: hrefs",
            False,
            f"found: {[a['href'] for a in js_hrefs]}",
        )
        return False
    record(f"{label}: no javascript: hrefs", True)

    # 4. The literal malicious script string must appear as escaped text.
    if MALICIOUS_NAME not in soup.get_text():
        record(
            f"{label}: malicious payload appears as escaped text",
            False,
            "literal not found in get_text()",
        )
        return False
    if "&lt;script" not in html_body:
        record(
            f"{label}: malicious payload appears as escaped text",
            False,
            "raw HTML missing &lt;script entity",
        )
        return False
    record(f"{label}: malicious payload appears as escaped text", True)

    return True


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------


def verify_render_payment_success_email() -> None:
    label = "stripe_service._render_payment_success_email"
    svc = stripe_svc_mod.StripeService.__new__(stripe_svc_mod.StripeService)

    html_body = svc._render_payment_success_email(
        user_name=MALICIOUS_NAME,
        plan_name=MALICIOUS_PLAN,
        amount=99.99,
        currency=MALICIOUS_CURRENCY,
        invoice_date=MALICIOUS_DATE,
        invoice_pdf=MALICIOUS_INVOICE_PDF,
    )
    assert_xss_safe(label, html_body)


def verify_render_payment_failed_email() -> None:
    label = "stripe_service._render_payment_failed_email"
    svc = stripe_svc_mod.StripeService.__new__(stripe_svc_mod.StripeService)

    html_body = svc._render_payment_failed_email(
        user_name=MALICIOUS_NAME,
        plan_name=MALICIOUS_PLAN,
        amount=42.00,
        currency=MALICIOUS_CURRENCY,
    )
    assert_xss_safe(label, html_body)


def main() -> int:
    verify_render_payment_success_email()
    print()
    verify_render_payment_failed_email()
    print()

    failures = [r for r in results if r[0] == FAIL]
    print("=" * 60)
    print(
        f"TOTAL: {len(results)}  PASS: {len(results) - len(failures)}  FAIL: {len(failures)}"
    )
    if failures:
        for status, name, detail in failures:
            print(f"  {status} {name} — {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

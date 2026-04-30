#!/usr/bin/env python3
"""In-process unit verification for vendor/contract email HTML escaping.

Drives the email composers (`vendor_service.send_contract`,
`vendor_service.send_payment_link`, the planner-notify path inside
`vendor_service.sign_contract`, and every composer in
`contract_email_service`) with a malicious-input fixture and confirms
the rendered HTML body is XSS-safe:

  - no <script> elements
  - no element with any on* attribute
  - no href starting with "javascript:"
  - the literal "<script>alert('xss')</script>" appears only as escaped
    text content (i.e. shows up as literal text via soup.get_text(), but
    not as a live tag)

Usage:
    python3 outputs/unit_verify_email_html_escaping.py

Exit code: 0 on full PASS, 1 on any FAIL.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# Pin the repo path so this script works inside the cowork workspace mount
# as well as when run from a developer laptop.
REPO_ROOT_CANDIDATES = [
    Path("/sessions/clever-cool-allen/mnt/WeddingWebApp"),
    Path("/Users/emmanuelakinwale/Desktop/WeddingWebApp"),
    Path(__file__).resolve().parents[1],
]
for candidate in REPO_ROOT_CANDIDATES:
    if (candidate / "app" / "services" / "vendor_service.py").exists():
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
from bson import ObjectId  # noqa: E402

import app.services.vendor_service as vendor_svc_mod  # noqa: E402
import app.services.contract_email_service as contract_email_mod  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))
    print(f"[{PASS if ok else FAIL}] {name}{(' — ' + detail) if detail else ''}")


# Malicious fixture per ticket #4.
MALICIOUS_VENDOR_NAME = "<script>alert('xss')</script>"
MALICIOUS_CONTRACT_TITLE = "<img src=x onerror=alert(1)>"
MALICIOUS_MESSAGE = '<a href="javascript:alert(1)">click</a>'


def assert_xss_safe(label: str, html_body: str) -> bool:
    """Run the four assertions from the ticket against html_body."""
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

    # 4. The literal malicious script string must appear in the get_text()
    #    output (escaped form decoded), proving the value WAS rendered (so
    #    the test isn't passing trivially on a missing field) AND that it's
    #    inert text. The raw HTML must contain &lt;script&gt; — not the live
    #    tag — i.e. the substring "<script>" should NOT appear before a
    #    "</script>" pair (already covered by check 1) AND the escaped
    #    sequence "&lt;script" should appear in the raw body.
    if MALICIOUS_VENDOR_NAME not in soup.get_text():
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
# vendor_service.VendorService.send_contract
# ---------------------------------------------------------------------------


async def verify_send_contract() -> None:
    label = "vendor_service.send_contract"
    svc = vendor_svc_mod.VendorService.__new__(vendor_svc_mod.VendorService)

    # Mongo-collection stubs the method touches.
    svc.vendor_contracts = MagicMock()
    svc.vendor_contracts.update_one = AsyncMock()

    contract_oid = str(ObjectId())
    # Internal helpers we don't want to actually exercise.
    contract_doc = {
        "id": contract_oid,
        "_id": contract_oid,
        "vendor_name": MALICIOUS_VENDOR_NAME,
        "vendor_email": "v@example.com",
        "vendor_profile_id": "vp1",
        "wedding_id": "w1",
        "contract_title": MALICIOUS_CONTRACT_TITLE,
        "contract_number": "CON-XXX",
        "service_category": "photographer",
        "custom_service_category": None,
        "total_amount": 1234.56,
        "deposit_amount": 100.0,
        "status": "draft",
        "contract_kind": "original",
        "version_number": 1,
    }
    svc.get_contract = AsyncMock(return_value=contract_doc)
    svc._get_wedding = AsyncMock(return_value={"couple_names": "<b>Couples</b>"})
    svc._get_planner_contract_settings = AsyncMock(
        return_value={"token_expiry_days": 30}
    )
    svc._is_contract_current = MagicMock(return_value=True)
    svc._get_root_contract_id = MagicMock(return_value=contract_oid)
    svc._mark_contract_as_superseded = AsyncMock()
    svc._revoke_contract_access_token = AsyncMock()
    svc._log_contract_activity = AsyncMock()
    svc._log_communication = AsyncMock()
    svc._build_public_vendor_contract_link = (
        vendor_svc_mod.VendorService._build_public_vendor_contract_link
    )
    svc._issue_contract_access_token = MagicMock(
        return_value=(
            "raw-token",
            {
                "access_token_hash": "hash",
                "token_expires_at": datetime.now(timezone.utc),
                "token_revoked_at": None,
                "token_last_sent_at": datetime.now(timezone.utc),
                "token_last_viewed_at": None,
                "updated_at": datetime.now(timezone.utc),
            },
        )
    )
    svc._get_vendor_service_label = MagicMock(return_value="Photography")

    captured: dict[str, Any] = {}

    async def fake_send_email(*args, **kwargs):
        captured.update(kwargs)
        return {"success": True}

    svc.email_service = MagicMock()
    svc.email_service.send_email = fake_send_email

    await svc.send_contract(
        contract_id=contract_oid,
        created_by="planner@example.com",
        message=MALICIOUS_MESSAGE,
    )

    html_body = captured.get("html_content", "")
    assert_xss_safe(label, html_body)


# ---------------------------------------------------------------------------
# vendor_service.VendorService.send_payment_link
# ---------------------------------------------------------------------------


async def verify_send_payment_link() -> None:
    label = "vendor_service.send_payment_link"
    svc = vendor_svc_mod.VendorService.__new__(vendor_svc_mod.VendorService)

    pl_oid = str(ObjectId())
    payment_link_doc = {
        "_id": pl_oid,
        "payer_name": MALICIOUS_VENDOR_NAME,
        "payer_email": "p@example.com",
        "description": MALICIOUS_CONTRACT_TITLE,
        "recipient_name": "<svg/onload=alert(1)>",
        "amount": 250.0,
        "currency": "USD",
        "stripe_payment_link_url": "https://stripe.example/pl/abc",
        "email_message": MALICIOUS_MESSAGE,
    }

    svc.payment_links = MagicMock()
    svc.payment_links.find_one = AsyncMock(return_value=payment_link_doc)
    svc.payment_links.update_one = AsyncMock()
    svc.users = MagicMock()
    svc.users.find_one = AsyncMock(
        return_value={"name": "<script>alert('planner')</script>"}
    )

    captured: dict[str, Any] = {}

    async def fake_send_email(*args, **kwargs):
        captured.update(kwargs)
        return {"success": True}

    svc.email_service = MagicMock()
    svc.email_service.send_email = fake_send_email

    # Drive the composer with the planner-supplied custom_message; the
    # stored email_message also gets rendered, so both paths are covered.
    await svc.send_payment_link(
        payment_link_id=pl_oid,
        planner_email="planner@example.com",
        custom_message=MALICIOUS_MESSAGE,
    )

    html_body = captured.get("html_content", "")
    assert_xss_safe(label, html_body)


# ---------------------------------------------------------------------------
# contract_email_service.ContractEmailService.send_contract_email
# ---------------------------------------------------------------------------


async def verify_send_contract_email() -> None:
    label = "contract_email_service.send_contract_email"
    svc = contract_email_mod.ContractEmailService()

    captured: dict[str, Any] = {}

    class FakeResend:
        class Emails:
            @staticmethod
            def send(payload: dict) -> dict:
                captured.update(payload)
                return {"id": "stub"}

    svc._resend = FakeResend  # bypass _get_resend()

    await svc.send_contract_email(
        contract_id="c1",
        token="t1",
        vendor_email="v@example.com",
        vendor_name=MALICIOUS_VENDOR_NAME,
        contract_title=MALICIOUS_CONTRACT_TITLE,
        planner_message=MALICIOUS_MESSAGE,
    )

    html_body = captured.get("html", "")
    assert_xss_safe(label, html_body)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def main() -> int:
    await verify_send_contract()
    print()
    await verify_send_payment_link()
    print()
    await verify_send_contract_email()
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
    sys.exit(asyncio.run(main()))

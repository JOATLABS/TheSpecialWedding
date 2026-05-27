#!/usr/bin/env python3
"""
Public Vendor Contract Signing - Live Verification
==================================================

Verifies the public vendor-contract lifecycle that failed for the MC:

  1. Planner is seeded on a paid plan.
  2. Planner creates a wedding, vendor profile, assignment, and vendor contract
     through the real admin endpoints.
  3. The driver issues a deterministic public access token directly in Mongo
     so the email provider is not part of this signing-route check.
  4. Public invalid-token view/sign attempts are rejected.
  5. Public valid-token view marks the contract viewed without leaking token
     metadata.
  6. Public valid-token sign marks the contract signed.
  7. Planner-side contract readback, assignment projection, and activity log
     all reflect the signed state.

Cleanup pair: cleanup_public_vendor_contract_signing_state.py

Usage:
    TESTBED_NON_INTERACTIVE=1 python3 testbed/verify_public_vendor_contract_signing.py
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.settings import settings  # noqa: E402
from testbed.harness import Harness, PM_TOKEN_GOOD  # noqa: E402


PLANNER_EMAIL = "test_planner+publicvendorsign@thespecialwedding.io"
PLANNER_PASSWORD = "PublicVendorSign2026!"  # pragma: allowlist secret
PLANNER_FIRST = "PublicVendor"
PLANNER_LAST = "Signer"
PLANNER_COMPANY = "Public Vendor Signing QA Co"

COUPLE_DISPLAY = "Avery & Morgan (PublicVendorSign)"
VENDOR_BUSINESS_NAME = "Elton MC QA - PublicVendorSign"
VENDOR_EMAIL = "vendor+publicvendorsign@thespecialwedding.io"
VENDOR_CATEGORY = "mc"
VENDOR_PHONE = "555-0199"

PUBLIC_TOKEN = "public-vendor-signing-token-2026"  # pragma: allowlist secret
SIGNER_NAME = "Elton QA"
SIGNER_EMAIL = VENDOR_EMAIL

CONTRACT_TOTAL_AMOUNT = 1200.00
WEDDING_DATE_OFFSET_DAYS = 180
PLAN_ID = os.getenv("PUBLIC_VENDOR_SIGN_PLAN_ID", "plan_signature")


def _hash_contract_access_token(raw_token: str) -> str:
    secret_key = settings.secret_key
    if not secret_key:
        raise RuntimeError("SECRET_KEY is required for contract token hashing")
    return hmac.new(
        secret_key.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _public_path(contract_id: str, token: str) -> str:
    return f"/vendor-contract/public/contracts/{contract_id}/{token}"


def _issue_public_contract_token(h: Harness, contract_id: str) -> None:
    now = datetime.now(timezone.utc)
    update = {
        "status": "sent",
        "sent_at": now,
        "updated_at": now,
        "access_token_hash": _hash_contract_access_token(PUBLIC_TOKEN),
        "token_expires_at": now + timedelta(days=7),
        "token_revoked_at": None,
        "token_last_sent_at": now,
        "token_last_viewed_at": None,
    }
    result = h.mongo["vendor_contracts"].update_one(
        {"_id": ObjectId(contract_id), "created_by": PLANNER_EMAIL},
        {"$set": update},
    )
    if result.matched_count != 1:
        raise AssertionError(f"could not issue public token for contract {contract_id}")
    h.log.info("  OK Issued deterministic public token for contract signing")


def _assert_public_rejects_bad_token(h: Harness, contract_id: str) -> None:
    bad_view = h.api_get(_public_path(contract_id, "wrong-token"))
    if bad_view.status_code != 404:
        raise AssertionError(
            f"bad-token public view should be 404, got {bad_view.status_code}: "
            f"{bad_view.text}"
        )

    bad_sign = requests.post(
        f"{h.config.backend_url}{_public_path(contract_id, 'wrong-token')}/sign",
        json={"signer_name": SIGNER_NAME, "signer_email": SIGNER_EMAIL},
        timeout=30,
    )
    if bad_sign.status_code != 404:
        raise AssertionError(
            f"bad-token public sign should be 404, got {bad_sign.status_code}: "
            f"{bad_sign.text}"
        )

    stored = h.mongo["vendor_contracts"].find_one({"_id": ObjectId(contract_id)})
    if stored.get("status") != "sent":
        raise AssertionError(
            f"bad-token attempts changed contract status to {stored.get('status')}"
        )
    h.log.info("  OK Bad public tokens cannot view or sign the contract")


def _assert_public_view(h: Harness, contract_id: str) -> dict:
    resp = h.api_get(_public_path(contract_id, PUBLIC_TOKEN))
    if resp.status_code != 200:
        raise AssertionError(
            f"public contract view failed: {resp.status_code} {resp.text}"
        )
    body = resp.json()
    if body.get("access_token_hash") or body.get("access_token"):
        raise AssertionError("public contract response leaked token metadata")
    if body.get("status") != "viewed":
        raise AssertionError(f"public view should return viewed, got {body!r}")

    stored = h.mongo["vendor_contracts"].find_one({"_id": ObjectId(contract_id)})
    if stored.get("status") != "viewed" or not stored.get("viewed_at"):
        raise AssertionError("public view did not mark contract viewed")
    h.log.info("  OK Public view loads and marks contract viewed")
    return body


def _assert_public_sign(h: Harness, contract_id: str) -> None:
    resp = requests.post(
        f"{h.config.backend_url}{_public_path(contract_id, PUBLIC_TOKEN)}/sign",
        json={"signer_name": SIGNER_NAME, "signer_email": SIGNER_EMAIL},
        timeout=30,
    )
    if resp.status_code != 200:
        raise AssertionError(f"public sign failed: {resp.status_code} {resp.text}")
    body = resp.json()
    if body.get("message") != "Contract signed successfully":
        raise AssertionError(f"unexpected sign response: {body!r}")
    h.log.info("  OK Public sign endpoint returned success")


def _assert_signed_readback(
    h: Harness, planner_token: str, contract_id: str, assignment_id: str
) -> None:
    contract = h.get_vendor_contract(
        planner_token=planner_token, contract_id=contract_id
    )
    if contract.get("status") != "signed":
        raise AssertionError(f"planner readback status is not signed: {contract!r}")
    if contract.get("signed_by_name") != SIGNER_NAME:
        raise AssertionError(f"planner readback signer mismatch: {contract!r}")
    if not contract.get("contract_status_locked_at"):
        raise AssertionError("signed contract was not hard-locked")

    assignment = h.mongo["vendor_assignments"].find_one(
        {"_id": ObjectId(assignment_id)}
    )
    if assignment.get("status") != "contracted":
        raise AssertionError(f"assignment was not marked contracted: {assignment!r}")
    if assignment.get("contract_id") != contract_id:
        raise AssertionError(f"assignment contract link mismatch: {assignment!r}")

    activity = h.mongo["vendor_contract_activities"].find_one(
        {"contract_id": contract_id, "activity_type": "contract_signed"}
    )
    if not activity:
        raise AssertionError("contract_signed activity row was not recorded")
    h.log.info(
        "  OK Planner readback, assignment projection, and activity log are signed"
    )


def main() -> int:
    h = Harness(driver_name="verify_public_vendor_contract_signing")
    h.preflight()
    admin_token = h.get_admin_token()

    h.phase(
        "SEED",
        "subscribe planner; build wedding + vendor + assignment + vendor contract",
    )
    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
        first_name=PLANNER_FIRST,
        last_name=PLANNER_LAST,
        company_name=PLANNER_COMPANY,
        pm_token=PM_TOKEN_GOOD,
    )
    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)

    wedding_date = (
        (datetime.now(timezone.utc) + timedelta(days=WEDDING_DATE_OFFSET_DAYS))
        .date()
        .isoformat()
    )
    wedding_id = h.create_wedding(
        planner_token=planner_token,
        couple_names=COUPLE_DISPLAY,
        date_iso=wedding_date,
        guest_count=50,
        venue="Test Venue (PublicVendorSign)",
    )
    vendor_profile_id = h.create_vendor_profile(
        planner_token=planner_token,
        business_name=VENDOR_BUSINESS_NAME,
        email=VENDOR_EMAIL,
        service_category=VENDOR_CATEGORY,
        phone=VENDOR_PHONE,
    )
    assignment_id = h.assign_vendor_to_wedding(
        planner_token=planner_token,
        vendor_profile_id=vendor_profile_id,
        wedding_id=wedding_id,
        service_notes="PublicVendorSign verifier assignment.",
    )
    contract_id = h.create_vendor_contract(
        planner_token=planner_token,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        total_amount=CONTRACT_TOTAL_AMOUNT,
        service_date=wedding_date,
        service_location="Test Venue (PublicVendorSign)",
    )
    _issue_public_contract_token(h, contract_id)

    h.phase("PUBLIC_ROUTE", "reject bad token, view valid link, then sign")
    _assert_public_rejects_bad_token(h, contract_id)
    public_contract = _assert_public_view(h, contract_id)
    if public_contract.get("vendor_email") != VENDOR_EMAIL:
        raise AssertionError(f"public contract vendor mismatch: {public_contract!r}")
    _assert_public_sign(h, contract_id)

    h.phase("READBACK", "assert planner/admin projections match the signed state")
    _assert_signed_readback(h, planner_token, contract_id, assignment_id)

    h.checkpoint(
        "UI (public vendor contract link)",
        [
            f"Open {h.config.frontend_url}/vendor-contract/{contract_id}/{PUBLIC_TOKEN}",
            "Expected: the public contract page shows the signed confirmation, not an error.",
            f"Open {h.config.frontend_url}/admin/vendors/contracts/{contract_id} as {PLANNER_EMAIL}.",
            "Expected: planner contract status is Signed and activity includes Contract signed.",
        ],
    )

    h.log.info("")
    h.log.info("Public vendor contract signing verification passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger("verify_public_vendor_contract_signing").error(
            f"Verification failed: {exc}", exc_info=True
        )
        raise SystemExit(1)

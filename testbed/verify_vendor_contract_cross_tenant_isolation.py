#!/usr/bin/env python3
"""
Vendor Contract Cross-Tenant Isolation — Live Verification
==========================================================

Verifies the fix at app/services/vendor_service.py for VENDOR_CONTRACT_PREPROD
ticket #1: cross-tenant write on vendor mutation paths.

Pre-fix behavior
----------------
A logged-in planner could mutate another planner's vendor / contract /
assignment data because each lookup was keyed by ``_id`` only, with no
``created_by`` (or ``assigned_planner_*``) filter. Five mutation paths
were vulnerable:

  1. POST /admin/contracts                        (vendor_profile_id, wedding_id)
  2. POST /admin/contracts/upload-pdf             (vendor_profile_id, wedding_id)
  3. POST /admin/contracts/{id}/upload            (contract_id)
  4. POST /admin/assign                           (vendor_profile_id)
  5. PATCH /admin/assignments/{id}/status         (assignment_id)

We additionally exercise a same-tenant positive path on
``PATCH /admin/assignments/{id}/status`` so an over-aggressive
ownership filter (e.g., email-normalization mismatch) cannot land
silently — a planner's own writes must still succeed.

Post-fix behavior
-----------------
Each mutation flows through ``_get_owned_vendor_profile`` /
``_get_owned_wedding`` / ``_get_owned_assignment`` /
``_get_owned_contract``, all of which inject the ownership predicate at
the Mongo query layer. Foreign IDs return 404 (not 403) so the planner
UI cannot probe the existence of another tenant's records.

Strategy
--------
SEED: planner A and planner B each get a vendor, a wedding, and a
contract. Both planners log in.

VERIFY: planner A — authenticated — fires the five mutation requests
against planner B's IDs. Each must return 404 and no Mongo write must
land. We assert both the wire-level status code and the Mongo
post-condition (no new document, no status change).

CHECKPOINT: four live UX checkpoints for the user to verify in Chrome
with planner A logged in (DevTools intercept, console clean, no
cross-tenant string flashes).

Cleanup pair: cleanup_vendor_contract_cross_tenant_isolation_state.py

Usage
-----
    # In another terminal:
    python testbed/testbed.py up
    # Then:
    python testbed/verify_vendor_contract_cross_tenant_isolation.py
    # When done:
    python testbed/cleanup_vendor_contract_cross_tenant_isolation_state.py
    python testbed/testbed.py down
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bson import ObjectId

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from testbed.harness import Harness, PM_TOKEN_GOOD  # noqa: E402

# ---------------------------------------------------------------------------
# Driver constants — grep-visible so reruns are deterministic
# ---------------------------------------------------------------------------

PLANNER_A_EMAIL = "test_planner+xtenant_a@thespecialwedding.io"
PLANNER_A_PASSWORD = "XTenantA2026!"  # pragma: allowlist secret
PLANNER_A_FIRST = "XTenant"
PLANNER_A_LAST = "PlannerA"
PLANNER_A_COMPANY = "X-Tenant QA Co A"

PLANNER_B_EMAIL = "test_planner+xtenant_b@thespecialwedding.io"
PLANNER_B_PASSWORD = "XTenantB2026!"  # pragma: allowlist secret
PLANNER_B_FIRST = "XTenant"
PLANNER_B_LAST = "PlannerB"
PLANNER_B_COMPANY = "X-Tenant QA Co B"

VENDOR_A_BUSINESS_NAME = "Vendor A Co — XTenant Verifier"
VENDOR_A_EMAIL = "vendor+xtenant_a@thespecialwedding.io"
VENDOR_B_BUSINESS_NAME = "Vendor B Co — XTenant Verifier"
VENDOR_B_EMAIL = "vendor+xtenant_b@thespecialwedding.io"
VENDOR_CATEGORY = "florist"

WEDDING_A_COUPLE = "Alex & Jordan (XTenant A)"
WEDDING_B_COUPLE = "Riley & Sky (XTenant B)"

CONTRACT_TOTAL = 2000.00
WEDDING_DATE_OFFSET_DAYS = 180
PLAN_ID = os.getenv("XTENANT_PLAN_ID", "plan_signature")


def _api_patch(
    h: Harness, path: str, *, token: str, params: dict | None = None
) -> requests.Response:
    """PATCH helper — harness intentionally omits PATCH because every other
    driver only needs GET/POST. The cross-tenant fix exercises
    ``PATCH /admin/assignments/{id}/status``, so we add it locally rather
    than expanding the harness for one caller.
    """
    return requests.patch(
        f"{h.config.backend_url}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )


async def main() -> int:
    h = Harness(driver_name="verify_vendor_contract_cross_tenant_isolation")
    h.preflight()
    admin_token = h.get_admin_token()

    # ---- SEED -----------------------------------------------------------
    h.phase("SEED", "subscribe planner A + B; build vendor/wedding/contract on each")

    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_A_EMAIL,
        password=PLANNER_A_PASSWORD,
        plan_id=PLAN_ID,
        first_name=PLANNER_A_FIRST,
        last_name=PLANNER_A_LAST,
        company_name=PLANNER_A_COMPANY,
        pm_token=PM_TOKEN_GOOD,
    )
    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_B_EMAIL,
        password=PLANNER_B_PASSWORD,
        plan_id=PLAN_ID,
        first_name=PLANNER_B_FIRST,
        last_name=PLANNER_B_LAST,
        company_name=PLANNER_B_COMPANY,
        pm_token=PM_TOKEN_GOOD,
    )

    token_a = h.login(PLANNER_A_EMAIL, PLANNER_A_PASSWORD)
    token_b = h.login(PLANNER_B_EMAIL, PLANNER_B_PASSWORD)

    wedding_date = (
        (datetime.now(timezone.utc) + timedelta(days=WEDDING_DATE_OFFSET_DAYS))
        .date()
        .isoformat()
    )

    wedding_a_id = h.create_wedding(
        planner_token=token_a,
        couple_names=WEDDING_A_COUPLE,
        date_iso=wedding_date,
        guest_count=80,
        venue="Test Venue (XTenant A)",
    )
    wedding_b_id = h.create_wedding(
        planner_token=token_b,
        couple_names=WEDDING_B_COUPLE,
        date_iso=wedding_date,
        guest_count=80,
        venue="Test Venue (XTenant B)",
    )

    vendor_a_id = h.create_vendor_profile(
        planner_token=token_a,
        business_name=VENDOR_A_BUSINESS_NAME,
        email=VENDOR_A_EMAIL,
        service_category=VENDOR_CATEGORY,
    )
    vendor_b_id = h.create_vendor_profile(
        planner_token=token_b,
        business_name=VENDOR_B_BUSINESS_NAME,
        email=VENDOR_B_EMAIL,
        service_category=VENDOR_CATEGORY,
    )

    assignment_a_id = h.assign_vendor_to_wedding(
        planner_token=token_a,
        vendor_profile_id=vendor_a_id,
        wedding_id=wedding_a_id,
        service_notes="XTenant verifier — A's own vendor on A's own wedding.",
    )
    assignment_b_id = h.assign_vendor_to_wedding(
        planner_token=token_b,
        vendor_profile_id=vendor_b_id,
        wedding_id=wedding_b_id,
        service_notes="XTenant verifier — B's own vendor on B's own wedding.",
    )

    contract_a_id = h.create_vendor_contract(
        planner_token=token_a,
        wedding_id=wedding_a_id,
        vendor_profile_id=vendor_a_id,
        total_amount=CONTRACT_TOTAL,
        service_date=wedding_date,
        service_location="Test Venue (XTenant A)",
    )
    contract_b_id = h.create_vendor_contract(
        planner_token=token_b,
        wedding_id=wedding_b_id,
        vendor_profile_id=vendor_b_id,
        total_amount=CONTRACT_TOTAL,
        service_date=wedding_date,
        service_location="Test Venue (XTenant B)",
    )

    h.log.info("")
    h.log.info("Seed summary:")
    h.log.info(f"  planner A: {PLANNER_A_EMAIL}")
    h.log.info(f"    wedding_a:    {wedding_a_id}")
    h.log.info(f"    vendor_a:     {vendor_a_id}")
    h.log.info(f"    assignment_a: {assignment_a_id}")
    h.log.info(f"    contract_a:   {contract_a_id}")
    h.log.info(f"  planner B: {PLANNER_B_EMAIL}")
    h.log.info(f"    wedding_b:    {wedding_b_id}")
    h.log.info(f"    vendor_b:     {vendor_b_id}")
    h.log.info(f"    assignment_b: {assignment_b_id}")
    h.log.info(f"    contract_b:   {contract_b_id}")
    h.log.info("")

    # Pre-state Mongo snapshot for tamper detection.
    contracts_before = h.mongo["vendor_contracts"].count_documents({})
    assignment_b_doc_before = h.mongo["vendor_assignments"].find_one(
        {"_id": ObjectId(assignment_b_id)}
    )
    assignment_b_status_before = (
        assignment_b_doc_before.get("status") if assignment_b_doc_before else None
    )

    # ---- VERIFY ---------------------------------------------------------
    h.phase("VERIFY", "planner-A authed → planner-B IDs → expect 404 on every path")

    failures: list[str] = []

    def _expect_404(label: str, resp: requests.Response) -> None:
        if resp.status_code == 404:
            h.log.info(f"  ✅ {label}: got 404 as expected")
        else:
            failures.append(
                f"{label}: expected 404, got {resp.status_code} body={resp.text[:200]}"
            )
            h.log.error(f"  ❌ {label}: expected 404, got {resp.status_code}")

    # Case 1: POST /admin/contracts with vendor_profile_id=V_B (foreign vendor)
    resp = h.api_post(
        "/admin/contracts",
        token=token_a,
        json={
            "wedding_id": wedding_a_id,  # A's own wedding
            "vendor_profile_id": vendor_b_id,  # foreign vendor
            "total_amount": CONTRACT_TOTAL,
        },
    )
    _expect_404("create_contract foreign-vendor", resp)

    # Case 2: POST /admin/contracts with wedding_id=W_B (foreign wedding)
    resp = h.api_post(
        "/admin/contracts",
        token=token_a,
        json={
            "wedding_id": wedding_b_id,  # foreign wedding
            "vendor_profile_id": vendor_a_id,  # A's own vendor
            "total_amount": CONTRACT_TOTAL,
        },
    )
    _expect_404("create_contract foreign-wedding", resp)

    # Case 3: POST /admin/assign against vendor B (foreign vendor)
    resp = h.api_post(
        "/admin/assign",
        token=token_a,
        json={
            "vendor_profile_id": vendor_b_id,  # foreign vendor
            "wedding_id": wedding_a_id,  # A's own wedding
        },
    )
    _expect_404("assign foreign-vendor", resp)

    # Case 3b: POST /admin/assign against own vendor but foreign wedding —
    # the new wedding ownership check must reject this too.
    resp = h.api_post(
        "/admin/assign",
        token=token_a,
        json={
            "vendor_profile_id": vendor_a_id,  # A's own vendor
            "wedding_id": wedding_b_id,  # foreign wedding
        },
    )
    _expect_404("assign foreign-wedding", resp)

    # Case 4: PATCH /admin/assignments/{A_B}/status (foreign assignment)
    resp = _api_patch(
        h,
        f"/admin/assignments/{assignment_b_id}/status",
        token=token_a,
        params={"status": "contracted"},
    )
    _expect_404("update_assignment_status foreign", resp)

    # Case 5: POST /admin/contracts/{C_B}/upload (foreign contract)
    files = {"file": ("signed.pdf", b"%PDF-1.4 fake content", "application/pdf")}
    resp = requests.post(
        f"{h.config.backend_url}/admin/contracts/{contract_b_id}/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files=files,
        params={"document_type": "signed"},
        timeout=30,
    )
    _expect_404("upload_contract_document foreign", resp)

    # Case 6: POST /admin/contracts/upload-pdf (foreign vendor + foreign wedding).
    # Multipart: the route takes file as form-data and the rest as query params.
    # We craft this as a direct httpx-style request because the harness does
    # not (yet) expose a multipart helper. The goal is to exercise the
    # upload_contract_pdf service method's ownership check.
    pdf_blob = b"%PDF-1.4\n%fake content for cross-tenant test\n%%EOF"
    files = {"file": ("foreign.pdf", pdf_blob, "application/pdf")}
    resp = requests.post(
        f"{h.config.backend_url}/admin/contracts/upload-pdf",
        headers={"Authorization": f"Bearer {token_a}"},
        files=files,
        params={
            "wedding_id": wedding_b_id,  # foreign wedding
            "vendor_profile_id": vendor_b_id,  # foreign vendor
            "contract_title": "XTenant Forged PDF",
            "total_amount": CONTRACT_TOTAL,
        },
        timeout=30,
    )
    _expect_404("upload_contract_pdf foreign", resp)

    # Mongo post-condition for Case 6: no new vendor_contracts row landed
    # against wedding_b_id. Even if a future ownership-bypass leak landed,
    # the document would carry wedding_id == wedding_b_id, so a count by
    # that key catches it without coupling to any specific status field.
    foreign_pdf_rows = h.mongo["vendor_contracts"].count_documents(
        {"wedding_id": wedding_b_id, "contract_type": "uploaded_pdf"}
    )
    if foreign_pdf_rows != 0:
        failures.append(
            f"upload_contract_pdf foreign leaked: "
            f"{foreign_pdf_rows} uploaded_pdf row(s) on wedding_b_id"
        )
        h.log.error(
            f"  ❌ upload_contract_pdf foreign: "
            f"{foreign_pdf_rows} pdf row(s) appeared on wedding_b_id"
        )
    else:
        h.log.info("  ✅ no foreign uploaded_pdf row written against wedding_b_id")

    # Case 7 (positive same-tenant): planner A → PATCH on A's own assignment.
    # Catches an over-aggressive ownership filter (e.g., email-normalization
    # mismatch) that would silently 404 a legitimate same-tenant write.
    resp = _api_patch(
        h,
        f"/admin/assignments/{assignment_a_id}/status",
        token=token_a,
        params={"status": "confirmed"},
    )
    if resp.status_code == 200:
        h.log.info("  ✅ same-tenant update_assignment_status: 200 as expected")
    else:
        failures.append(
            f"same-tenant update_assignment_status: expected 200, got "
            f"{resp.status_code} body={resp.text[:200]}"
        )
        h.log.error(
            f"  ❌ same-tenant update_assignment_status: expected 200, got "
            f"{resp.status_code}"
        )

    assignment_a_doc = h.mongo["vendor_assignments"].find_one(
        {"_id": ObjectId(assignment_a_id)}
    )
    assignment_a_status = assignment_a_doc.get("status") if assignment_a_doc else None
    if assignment_a_status == "confirmed":
        h.log.info(
            f"  ✅ same-tenant assignment A status updated: {assignment_a_status!r}"
        )
    else:
        failures.append(
            f"same-tenant assignment A status: expected 'confirmed', "
            f"got {assignment_a_status!r}"
        )
        h.log.error(
            f"  ❌ same-tenant assignment A status: expected 'confirmed', "
            f"got {assignment_a_status!r}"
        )

    # Mongo post-conditions: no new contract, B's assignment status untouched.
    contracts_after = h.mongo["vendor_contracts"].count_documents({})
    if contracts_after != contracts_before:
        failures.append(
            f"vendor_contracts count drifted: before={contracts_before}, "
            f"after={contracts_after}"
        )
        h.log.error(
            f"  ❌ contract count drifted: {contracts_before} → {contracts_after}"
        )
    else:
        h.log.info(f"  ✅ no new contract written (still {contracts_after})")

    assignment_b_doc_after = h.mongo["vendor_assignments"].find_one(
        {"_id": ObjectId(assignment_b_id)}
    )
    assignment_b_status_after = (
        assignment_b_doc_after.get("status") if assignment_b_doc_after else None
    )
    if assignment_b_status_after != assignment_b_status_before:
        failures.append(
            f"assignment B status drifted: before={assignment_b_status_before}, "
            f"after={assignment_b_status_after}"
        )
        h.log.error(
            f"  ❌ assignment B drifted: {assignment_b_status_before} → "
            f"{assignment_b_status_after}"
        )
    else:
        h.log.info(f"  ✅ assignment B status preserved: {assignment_b_status_after!r}")

    contract_b_doc = h.mongo["vendor_contracts"].find_one(
        {"_id": ObjectId(contract_b_id)}
    )
    if contract_b_doc and contract_b_doc.get("signed_document_url"):
        failures.append(
            f"contract B signed_document_url got written: "
            f"{contract_b_doc.get('signed_document_url')}"
        )
        h.log.error("  ❌ contract B signed_document_url was overwritten")
    else:
        h.log.info("  ✅ contract B signed_document_url not written")

    # ---- CHECKPOINTS ----------------------------------------------------
    h.checkpoint(
        "1 — Direct URL escape (planner A logged in)",
        [
            f"In Chrome, navigate to /admin/vendors/contracts/{contract_b_id}",
            "Observe: 'Contract Not Found' (or empty state) renders",
            f"Network panel: GET /admin/contracts/{contract_b_id} returns 404",
            "No B-tenant string ('Vendor B Co', 'Riley & Sky') anywhere on the page",
            "Console: no errors, no warnings",
        ],
    )

    h.checkpoint(
        "2 — Forged create (planner A logged in)",
        [
            "In Chrome, /admin/vendors/contracts/new — start the wizard with own data",
            f"In DevTools, intercept the outgoing POST /admin/contracts and substitute "
            f"vendor_profile_id={vendor_b_id} (or wedding_id={wedding_b_id})",
            "Submit: a 404-derived toast appears (NOT 500)",
            "Reload /admin/vendors/contracts: no new contract row appears",
            "Console: clean",
        ],
    )

    h.checkpoint(
        "3 — Forged PDF upload (planner A logged in)",
        [
            f"In Chrome, intercept POST /admin/contracts/{contract_b_id}/upload via DevTools",
            "Network: 404, no progress-bar success",
            "Reload contract list: contract B's signed_document_url unchanged",
            "Console: clean",
        ],
    )

    h.checkpoint(
        "4 — Forged assignment status (planner A logged in)",
        [
            f"In Chrome DevTools, fire PATCH /admin/assignments/{assignment_b_id}/status?status=contracted",
            "Network: 404",
            "Reload /admin/vendors: no status flip on planner A's view",
            f"Switch to planner B's session (logout → login as {PLANNER_B_EMAIL})",
            "Confirm assignment B still shows 'inquiry' (not 'contracted')",
        ],
    )

    h.checkpoint(
        "5 — Same-tenant positive assignment status (planner A logged in)",
        [
            f"Login as {PLANNER_A_EMAIL}",
            "Navigate to wedding A's vendor list",
            f"Confirm assignment {assignment_a_id} now displays 'confirmed' status",
            "No console errors, no toast warnings",
            "(this catches an over-aggressive ownership filter that would "
            "silently 404 a legitimate same-tenant write)",
        ],
    )

    h.log.info("")
    if failures:
        h.log.error(f"verify FAILED with {len(failures)} issue(s):")
        for f in failures:
            h.log.error(f"  ✗ {f}")
        h.log.info(
            "Run testbed/cleanup_vendor_contract_cross_tenant_isolation_state.py "
            "to reset."
        )
        return 1

    h.log.info(
        "✅ verify_vendor_contract_cross_tenant_isolation: all 6 mutation paths "
        "rejected planner-A → planner-B writes (404 + no Mongo drift), "
        "and same-tenant positive write succeeded"
    )
    h.log.info(
        "Run testbed/cleanup_vendor_contract_cross_tenant_isolation_state.py to reset."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        import logging

        logging.getLogger("verify_vendor_contract_cross_tenant_isolation").error(
            f"Verification aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)

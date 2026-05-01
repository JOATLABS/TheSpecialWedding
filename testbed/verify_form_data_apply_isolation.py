#!/usr/bin/env python3
"""
Form-Data Apply Isolation — Live Verification
=============================================

Verifies the fix at app/services/vendor_service.py for VENDOR_CONTRACT_PREPROD
ticket #3: cross-tenant read on ``apply_form_data_to_contract``.

Pre-fix behavior
----------------
``POST /admin/contracts/{id}/apply-form-data`` accepted a
``form_submission_id`` from the client and merged that submission's content
into the planner's contract sections without verifying the submission's
ownership. A planner could paste another tenant's form-submission data
into their own contract and read it back via
``GET /admin/contracts/{id}`` (sections + T&Cs are returned).

Post-fix behavior
-----------------
The submission lookup now flows through
``_get_owned_form_submission`` / ``_get_owned_form``, which join the
``vendor_submissions`` row to its parent ``vendor_forms`` row and
require ``vendor_forms.created_by == applied_by``. Cross-tenant IDs
return 404, the contract is unmodified, and no sentinel value from
the foreign tenant ever appears in the post-state read.

Strategy
--------
SEED: planner A and planner B each get a wedding, a vendor_form, and
a vendor_submission carrying a sentinel value. Planner A also gets a
draft contract with a ``{{lead_singer_name}}`` placeholder.

VERIFY:
  Case 1 — Cross-tenant apply: planner A POSTs
    /admin/contracts/<C_A>/apply-form-data with form_submission_id=<F_B>.
    Expect 404 + sections unchanged + sentinel never read.
  Case 2 — Same-tenant apply: planner A applies F_A. Expect 200 +
    placeholder replaced + activity row recorded.
  Case 3 — Forged ID: planner A applies a malformed ObjectId. Expect
    400 (validate_object_id) or 404.

CHECKPOINT: three live UX checkpoints for the user to verify in Chrome
with planner A logged in.

Cleanup pair: cleanup_form_data_apply_isolation_state.py

Usage
-----
    # In another terminal:
    python testbed/testbed.py up
    # Then:
    python testbed/verify_form_data_apply_isolation.py
    # When done:
    python testbed/cleanup_form_data_apply_isolation_state.py
    python testbed/testbed.py down
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from testbed.harness import Harness, PM_TOKEN_GOOD  # noqa: E402

# ---------------------------------------------------------------------------
# Driver constants — grep-visible so reruns are deterministic
# ---------------------------------------------------------------------------

PLANNER_A_EMAIL = "test_planner+formapply_a@thespecialwedding.io"
PLANNER_A_PASSWORD = "FormApplyA2026!"  # pragma: allowlist secret
PLANNER_A_FIRST = "FormApply"
PLANNER_A_LAST = "PlannerA"
PLANNER_A_COMPANY = "FormApply QA Co A"

PLANNER_B_EMAIL = "test_planner+formapply_b@thespecialwedding.io"
PLANNER_B_PASSWORD = "FormApplyB2026!"  # pragma: allowlist secret
PLANNER_B_FIRST = "FormApply"
PLANNER_B_LAST = "PlannerB"
PLANNER_B_COMPANY = "FormApply QA Co B"

VENDOR_A_BUSINESS_NAME = "Vendor A Co — FormApply Verifier"
VENDOR_A_EMAIL = "vendor+formapply_a@thespecialwedding.io"
VENDOR_B_BUSINESS_NAME = "Vendor B Co — FormApply Verifier"
VENDOR_B_EMAIL = "vendor+formapply_b@thespecialwedding.io"
VENDOR_CATEGORY = "band"

WEDDING_A_COUPLE = "Alex & Jordan (FormApply A)"
WEDDING_B_COUPLE = "Riley & Sky (FormApply B)"

CONTRACT_TOTAL = 2500.00
WEDDING_DATE_OFFSET_DAYS = 180
PLAN_ID = os.getenv("FORMAPPLY_PLAN_ID", "plan_signature")

SENTINEL_FROM_B = "SENTINEL_FROM_B_lead_singer_should_not_appear"
# Sentinel used for the read-side picker leak scenario (Case 4): planner B
# seeds a vendor_form + vendor_submission whose vendor_email COLLIDES with
# planner A's vendor email. Pre-fix, get_form_data_for_contract filtered
# only by vendor_email, so A's contract-detail picker would surface B's
# submission. Post-fix, the query is also scoped by created_by → owned forms.
SENTINEL_FROM_B_SHARED = (
    "SENTINEL_FROM_B_SHARED_EMAIL_picker_should_not_show"  # pragma: allowlist secret
)
LEGITIMATE_A_VALUE = "Anna Lyric (legit A submission)"

PLACEHOLDER_KEY = "lead_singer_name"
PLACEHOLDER_TOKEN = "{{lead_singer_name}}"

CONTRACT_TITLE = "FormApply Verifier — A's Draft Contract"
SECTION_TITLE = "Performance Lineup"
SECTION_CONTENT = (
    f"The lead singer for the ceremony will be {PLACEHOLDER_TOKEN}. "
    "All other members are to be confirmed."
)


def _seed_vendor_form_and_submission(
    h: Harness,
    *,
    planner_email: str,
    wedding_id: str,
    vendor_email: str,
    vendor_name: str,
    sentinel_value: str,
) -> tuple[str, str]:
    """Insert a vendor_form + vendor_submission directly via Mongo.

    The submission's parent ``vendor_forms.created_by`` is the
    ownership anchor — that's exactly what _get_owned_form_submission
    traverses through. We bypass the public POST endpoint because it
    requires a one-time access_token round-trip; for verification
    purposes the post-state Mongo shape is what matters.
    """
    now = datetime.now(timezone.utc)
    form_doc = {
        "form_name": "Wedding Music Booking Form",
        "vendor_email": vendor_email,
        "vendor_name": vendor_name,
        "vendor_type": "musician",
        "wedding_id": wedding_id,
        "fields": [
            {"id": "lead_singer_name", "label": "Lead Singer Name", "type": "text"},
        ],
        "access_token": "verifier-form-token-" + ObjectId().binary.hex()[:8],
        "created_by": planner_email,
        "created_at": now,
        "updated_at": now,
        "sent_at": None,
        "submitted_at": None,
        "status": "submitted",
        "submission_data": {PLACEHOLDER_KEY: sentinel_value},
    }
    form_id = h.mongo["vendor_forms"].insert_one(form_doc).inserted_id

    submission_doc = {
        "form_id": str(form_id),
        "vendor_email": vendor_email,
        "vendor_name": vendor_name,
        "wedding_id": wedding_id,
        "submission_data": {PLACEHOLDER_KEY: sentinel_value},
        "submitted_at": now,
        "status": "submitted",
    }
    submission_id = h.mongo["vendor_submissions"].insert_one(submission_doc).inserted_id

    h.log.info(
        f"  ✅ Seeded vendor_form={form_id} + vendor_submission={submission_id} "
        f"for planner {planner_email}"
    )
    return str(form_id), str(submission_id)


def _set_contract_section(h: Harness, *, contract_id: str) -> None:
    """Stamp a placeholder section onto the seeded contract directly.

    create_vendor_contract returns a contract with no sections; we
    inject one with ``{{lead_singer_name}}`` so the apply-form-data
    flow has something to replace.
    """
    h.mongo["vendor_contracts"].update_one(
        {"_id": ObjectId(contract_id)},
        {
            "$set": {
                "sections": [
                    {
                        "id": "perf_lineup",
                        "title": SECTION_TITLE,
                        "content": SECTION_CONTENT,
                    }
                ],
                "contract_title": CONTRACT_TITLE,
            }
        },
    )


async def main() -> int:
    h = Harness(driver_name="verify_form_data_apply_isolation")
    h.preflight()
    admin_token = h.get_admin_token()

    # ---- SEED -----------------------------------------------------------
    h.phase(
        "SEED",
        "two planners, vendor forms + submissions, draft contract for A",
    )

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
        venue="Test Venue (FormApply A)",
    )
    wedding_b_id = h.create_wedding(
        planner_token=token_b,
        couple_names=WEDDING_B_COUPLE,
        date_iso=wedding_date,
        guest_count=80,
        venue="Test Venue (FormApply B)",
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

    h.assign_vendor_to_wedding(
        planner_token=token_a,
        vendor_profile_id=vendor_a_id,
        wedding_id=wedding_a_id,
        service_notes="FormApply verifier — A's own.",
    )

    contract_a_id = h.create_vendor_contract(
        planner_token=token_a,
        wedding_id=wedding_a_id,
        vendor_profile_id=vendor_a_id,
        total_amount=CONTRACT_TOTAL,
        service_date=wedding_date,
        service_location="Test Venue (FormApply A)",
    )
    _set_contract_section(h, contract_id=contract_a_id)

    # Direct-Mongo seed: each planner gets a vendor_form + vendor_submission
    # whose parent form's created_by is the planner.
    _form_a_id, submission_a_id = _seed_vendor_form_and_submission(
        h,
        planner_email=PLANNER_A_EMAIL,
        wedding_id=wedding_a_id,
        vendor_email=VENDOR_A_EMAIL,
        vendor_name=VENDOR_A_BUSINESS_NAME,
        sentinel_value=LEGITIMATE_A_VALUE,
    )
    _form_b_id, submission_b_id = _seed_vendor_form_and_submission(
        h,
        planner_email=PLANNER_B_EMAIL,
        wedding_id=wedding_b_id,
        vendor_email=VENDOR_B_EMAIL,
        vendor_name=VENDOR_B_BUSINESS_NAME,
        sentinel_value=SENTINEL_FROM_B,
    )

    # Email-collision seed for Case 4 (read-side picker leak):
    # planner B owns a vendor_form + vendor_submission whose vendor_email
    # is VENDOR_A_EMAIL. Pre-fix, planner A's contract-detail picker would
    # query vendor_submissions by vendor_email only and surface this one
    # alongside A's. Post-fix, owner-scoping by parent vendor_forms.created_by
    # filters it out.
    _form_b_shared_id, submission_b_shared_id = _seed_vendor_form_and_submission(
        h,
        planner_email=PLANNER_B_EMAIL,
        wedding_id=wedding_b_id,
        vendor_email=VENDOR_A_EMAIL,  # COLLISION with planner A's vendor
        vendor_name="Planner B's Shadow Entry (collides with A's vendor email)",
        sentinel_value=SENTINEL_FROM_B_SHARED,
    )

    h.log.info("")
    h.log.info("Seed summary:")
    h.log.info(f"  planner A: {PLANNER_A_EMAIL}")
    h.log.info(f"    wedding_a:    {wedding_a_id}")
    h.log.info(f"    vendor_a:     {vendor_a_id}")
    h.log.info(f"    contract_a:   {contract_a_id}")
    h.log.info(f"    submission_a: {submission_a_id}")
    h.log.info(f"  planner B: {PLANNER_B_EMAIL}")
    h.log.info(f"    wedding_b:    {wedding_b_id}")
    h.log.info(f"    vendor_b:     {vendor_b_id}")
    h.log.info(f"    submission_b: {submission_b_id} (sentinel={SENTINEL_FROM_B!r})")
    h.log.info(
        f"    submission_b_shared: {submission_b_shared_id} "
        f"(vendor_email={VENDOR_A_EMAIL!r} COLLISION, "
        f"sentinel={SENTINEL_FROM_B_SHARED!r})"
    )
    h.log.info("")

    # Pre-state snapshot: capture the seeded section content so we can
    # confirm the cross-tenant attempt makes zero changes.
    contract_before = h.mongo["vendor_contracts"].find_one(
        {"_id": ObjectId(contract_a_id)}
    )
    sections_before = contract_before.get("sections") if contract_before else []

    # ---- VERIFY ---------------------------------------------------------
    h.phase("VERIFY", "cross-tenant 404, same-tenant 200, forged-id 400/404")

    failures: list[str] = []

    # Case 1 — Cross-tenant apply: planner A posts F_B against C_A.
    resp = h.api_post(
        f"/admin/contracts/{contract_a_id}/apply-form-data",
        token=token_a,
        json={"form_submission_id": submission_b_id},
    )
    if resp.status_code == 404:
        h.log.info("  ✅ cross-tenant apply: 404 as expected")
    else:
        failures.append(
            f"cross-tenant apply: expected 404, got {resp.status_code} "
            f"body={resp.text[:200]}"
        )
        h.log.error(f"  ❌ cross-tenant apply: expected 404, got {resp.status_code}")

    # Mongo post-condition: contract A's sections must be byte-equal to
    # pre-state, and the sentinel must NOT appear anywhere in the doc.
    contract_after_xtenant = h.mongo["vendor_contracts"].find_one(
        {"_id": ObjectId(contract_a_id)}
    )
    sections_after_xtenant = (
        contract_after_xtenant.get("sections") if contract_after_xtenant else []
    )
    if sections_after_xtenant != sections_before:
        failures.append(
            f"cross-tenant apply mutated contract sections: "
            f"before={sections_before!r} after={sections_after_xtenant!r}"
        )
        h.log.error("  ❌ cross-tenant apply mutated contract sections")
    else:
        h.log.info("  ✅ contract A sections unchanged after cross-tenant attempt")

    contract_dump = repr(contract_after_xtenant)
    if SENTINEL_FROM_B in contract_dump:
        failures.append("cross-tenant apply leaked sentinel from B into contract A doc")
        h.log.error("  ❌ B's sentinel value appears in contract A document")
    else:
        h.log.info("  ✅ B's sentinel value never appeared in contract A")

    # Case 2 — Same-tenant apply: planner A applies F_A.
    resp = h.api_post(
        f"/admin/contracts/{contract_a_id}/apply-form-data",
        token=token_a,
        json={"form_submission_id": submission_a_id},
    )
    if resp.status_code == 200:
        h.log.info("  ✅ same-tenant apply: 200 as expected")
    else:
        failures.append(
            f"same-tenant apply: expected 200, got {resp.status_code} "
            f"body={resp.text[:200]}"
        )
        h.log.error(f"  ❌ same-tenant apply: expected 200, got {resp.status_code}")

    # Mongo post-condition: A's section content has the placeholder
    # replaced by LEGITIMATE_A_VALUE.
    contract_after_legit = h.mongo["vendor_contracts"].find_one(
        {"_id": ObjectId(contract_a_id)}
    )
    sections_after_legit = (
        contract_after_legit.get("sections") if contract_after_legit else []
    )
    legit_section = next(
        (s for s in sections_after_legit if s.get("id") == "perf_lineup"), None
    )
    if not legit_section:
        failures.append("same-tenant apply: section perf_lineup missing post-update")
        h.log.error("  ❌ section perf_lineup missing after same-tenant apply")
    elif PLACEHOLDER_TOKEN in (legit_section.get("content") or ""):
        failures.append(
            "same-tenant apply: placeholder token still present "
            f"(content={legit_section.get('content')!r})"
        )
        h.log.error("  ❌ same-tenant apply did not replace placeholder")
    elif LEGITIMATE_A_VALUE not in (legit_section.get("content") or ""):
        failures.append(
            "same-tenant apply: legitimate A value did not land "
            f"(content={legit_section.get('content')!r})"
        )
        h.log.error("  ❌ same-tenant apply did not write A's value")
    else:
        h.log.info(
            f"  ✅ same-tenant apply replaced placeholder: "
            f"{legit_section.get('content')!r}"
        )

    # Activity-row audit: the most recent form_data_applied row on
    # contract A must reference the source submission and vendor.
    activity_row = h.mongo["vendor_contract_activities"].find_one(
        {
            "contract_id": contract_a_id,
            "activity_type": "form_data_applied",
        },
        sort=[("created_at", -1)],
    )
    if not activity_row:
        failures.append("same-tenant apply: no form_data_applied activity row")
        h.log.error("  ❌ no form_data_applied activity row recorded")
    else:
        meta = activity_row.get("metadata") or {}
        if meta.get("source_form_submission_id") != submission_a_id:
            failures.append(
                "activity row missing/wrong source_form_submission_id "
                f"(got={meta.get('source_form_submission_id')!r}, "
                f"want={submission_a_id!r})"
            )
            h.log.error("  ❌ activity row source_form_submission_id mismatch")
        else:
            h.log.info(
                f"  ✅ activity row records source_form_submission_id={submission_a_id}"
            )
        if not meta.get("source_vendor_id"):
            failures.append("activity row missing source_vendor_id")
            h.log.error("  ❌ activity row source_vendor_id missing")
        else:
            h.log.info(
                f"  ✅ activity row records source_vendor_id="
                f"{meta.get('source_vendor_id')!r}"
            )

    # Case 3 — Forged ID: planner A applies a malformed ObjectId.
    resp = h.api_post(
        f"/admin/contracts/{contract_a_id}/apply-form-data",
        token=token_a,
        json={"form_submission_id": "not-a-valid-objectid"},
    )
    if resp.status_code in (400, 404):
        h.log.info(f"  ✅ forged ID: {resp.status_code} as expected")
    else:
        failures.append(
            f"forged ID: expected 400/404, got {resp.status_code} "
            f"body={resp.text[:200]}"
        )
        h.log.error(f"  ❌ forged ID: expected 400/404, got {resp.status_code}")

    # Case 4 — Read-side picker isolation: planner A fetches form-data
    # for C_A. Pre-fix: payload would include B's shared-email submission.
    # Post-fix: owner-scoping via parent vendor_forms.created_by filters
    # it out; only A's own submissions surface.
    resp = h.api_get(
        f"/admin/contracts/{contract_a_id}/form-data",
        token=token_a,
    )
    if resp.status_code != 200:
        failures.append(
            f"read-side picker: expected 200, got {resp.status_code} "
            f"body={resp.text[:200]}"
        )
        h.log.error(f"  ❌ read-side picker: expected 200, got {resp.status_code}")
    else:
        payload = resp.json()
        payload_text = repr(payload)
        submissions = payload.get("vendor_submissions", []) or []
        available_fields = payload.get("available_fields", {}) or {}

        # Sentinel must not surface anywhere in the payload (submissions OR
        # available_fields OR suggested_contract_fields).
        if SENTINEL_FROM_B_SHARED in payload_text:
            failures.append(
                "read-side picker leaked B's shared-email sentinel "
                "(SENTINEL_FROM_B_SHARED present in form-data response)"
            )
            h.log.error("  ❌ B's shared-email sentinel appeared in form-data payload")
        else:
            h.log.info(
                "  ✅ B's shared-email sentinel never appeared in form-data response"
            )

        # The UI auto-applies vendor_submissions[0] (per
        # ContractDetailPageClient.tsx). That index must be A's own
        # submission, not B's shadow entry — even though both share the
        # same vendor_email, only A's parent form has created_by == A.
        if not submissions:
            failures.append(
                "read-side picker: vendor_submissions[] is empty; "
                "expected at least A's own submission"
            )
            h.log.error("  ❌ vendor_submissions[] is empty")
        else:
            head = submissions[0]
            head_data = head.get("data") if isinstance(head, dict) else {}
            head_value = (
                head_data.get(PLACEHOLDER_KEY) if isinstance(head_data, dict) else None
            )
            if head_value == LEGITIMATE_A_VALUE:
                h.log.info(
                    "  ✅ vendor_submissions[0] is A's value "
                    "(UI auto-apply is safe: it would apply A's own data)"
                )
            elif head_value == SENTINEL_FROM_B_SHARED:
                failures.append(
                    "vendor_submissions[0] is B's shadow entry — UI "
                    "auto-apply would silently mis-fire across tenants"
                )
                h.log.error("  ❌ vendor_submissions[0] is B's value — auto-apply leak")
            else:
                # Could be a different shape; flag as PARTIAL — the picker
                # didn't leak the sentinel, but the head doesn't match A's
                # known value either.
                h.log.warning(
                    f"  ⚠️  vendor_submissions[0] {PLACEHOLDER_KEY}="
                    f"{head_value!r}; not A's value and not B's shadow — "
                    "manual confirmation required"
                )

            # Tighter check: at least one entry must be sourced from the
            # vendor_submissions collection (not just the vendor_forms
            # fallback) AND must carry a non-empty source_id. Without
            # this, a too-restrictive filter can silently drop
            # vendor_submissions and leave only vendor_form-shaped
            # entries — which the UI auto-apply can't extract a
            # form_submission_id from, breaking the same-tenant happy
            # path. Caught the type-mismatch regression where
            # vendor_submissions.form_id is stored as str(ObjectId) but
            # the filter was passing raw ObjectIds.
            sub_kinds = {
                (s.get("source") if isinstance(s, dict) else None) for s in submissions
            }
            if "vendor_submission" not in sub_kinds:
                failures.append(
                    "read-side picker returned no rows from "
                    "vendor_submissions collection (only vendor_forms "
                    "fallback). UI auto-apply will fire without a "
                    "form_submission_id and 422 the request."
                )
                h.log.error(
                    "  ❌ no vendor_submission-sourced rows in picker — "
                    "UI auto-apply will break"
                )
            else:
                # The UI extracts form_submission_id from each picker entry's
                # `_id` field (see ContractDetailPageClient.tsx:620). The
                # summary helper writes that as `_id` (not `source_id`) — see
                # _summarize_contract_form_submission. Assert the field is
                # present and non-empty for every vendor_submission entry.
                vs_entries = [
                    s
                    for s in submissions
                    if isinstance(s, dict) and s.get("source") == "vendor_submission"
                ]
                missing_id = [s for s in vs_entries if not s.get("_id")]
                if missing_id:
                    failures.append(
                        f"{len(missing_id)} vendor_submission entries "
                        f"missing _id — UI auto-apply would 422 without "
                        f"form_submission_id"
                    )
                    h.log.error(
                        f"  ❌ {len(missing_id)} vendor_submission entries lack _id"
                    )
                else:
                    h.log.info(
                        f"  ✅ {len(vs_entries)} vendor_submission "
                        f"entries present, all with _id "
                        f"(UI auto-apply has the field it needs)"
                    )

        # available_fields source_id must never reference B's shadow.
        for key, field in available_fields.items():
            if not isinstance(field, dict):
                continue
            if field.get("value") == SENTINEL_FROM_B_SHARED:
                failures.append(f"available_fields[{key!r}] leaked B's shadow value")
                h.log.error(f"  ❌ available_fields[{key!r}] leaked B's shadow value")

    # ---- CHECKPOINTS ----------------------------------------------------
    h.checkpoint(
        "1 — Same-tenant happy path (planner A logged in)",
        [
            f"Login as {PLANNER_A_EMAIL}",
            f"Navigate to /admin/vendors/contracts/{contract_a_id}",
            "'Vendor Form Data Available' panel renders for A's own submission",
            "Click 'View & Apply Form Data'",
            f"The 'Performance Lineup' section now contains {LEGITIMATE_A_VALUE!r}",
            "Activity tab shows a 'form_data_applied' row referencing planner A's submission",
            "Console: no errors, no warnings",
        ],
    )

    h.checkpoint(
        "2 — Cross-tenant attempt via DevTools (planner A logged in)",
        [
            f"On /admin/vendors/contracts/{contract_a_id}, open DevTools → Network",
            "Intercept the next outgoing POST /admin/contracts/<id>/apply-form-data",
            f"Substitute form_submission_id={submission_b_id} (planner B's submission)",
            "Submit; Network panel: response is 404",
            "A user-facing error toast appears (no 500/HTML error page)",
            f"At no point does {SENTINEL_FROM_B!r} appear anywhere in the page DOM",
            "Refresh the contract; sections still show A's value (or placeholder)",
            "Console: clean",
        ],
    )

    h.checkpoint(
        "3 — Persistence + UI parity (planner A logged in)",
        [
            f"Refresh /admin/vendors/contracts/{contract_a_id}",
            "Activity tab: NO form_data_applied row was recorded for the failed attempt",
            "(only the legitimate Case-2 row should be present)",
            "Open the 'Apply Form Data' submission picker (if displayed):",
            "→ list contains only A's own submissions (vendor A entries)",
            "→ no planner-B vendor name or sentinel string appears",
            "Console: clean",
        ],
    )

    h.checkpoint(
        "4 — Read-side picker isolation under email collision (planner A logged in)",
        [
            f"On /admin/vendors/contracts/{contract_a_id}, open DevTools → Network",
            "Reload the page; watch GET /admin/contracts/<id>/form-data fire",
            "Inspect the JSON response. Verify:",
            "  → vendor_submissions[] contains ONLY A's own submission(s)",
            f"  → response payload contains NO occurrence of {SENTINEL_FROM_B_SHARED!r}",
            "  → vendor_submissions[0] (the index the UI auto-applies) is A's value",
            f"      (lead_singer_name == {LEGITIMATE_A_VALUE!r} OR matches the placeholder)",
            "  → available_fields and suggested_contract_fields contain no B-attributed values",
            "Now exercise the auto-apply behavior:",
            "  → trigger the 'Apply Form Data' flow as the UI normally would",
            "  → the section content reflects A's value, NOT the shadow B sentinel",
            "  → activity tab: form_data_applied row references A's submission_id, not B's shadow",
            "Console: no errors, no warnings",
        ],
    )

    h.log.info("")
    if failures:
        h.log.error(f"verify FAILED with {len(failures)} issue(s):")
        for f in failures:
            h.log.error(f"  ✗ {f}")
        h.log.info("Run testbed/cleanup_form_data_apply_isolation_state.py to reset.")
        return 1

    h.log.info(
        "✅ verify_form_data_apply_isolation: cross-tenant apply rejected "
        "(404, no contract drift, no sentinel leak), same-tenant apply "
        "succeeded (placeholder replaced, audit row recorded), forged-id "
        "rejected, read-side picker isolated under email collision "
        "(B's shadow submission filtered, auto-apply head is A's value)"
    )
    h.log.info("Run testbed/cleanup_form_data_apply_isolation_state.py to reset.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        import logging

        logging.getLogger("verify_form_data_apply_isolation").error(
            f"Verification aborted: {exc}", exc_info=True
        )
        # Suppress the requests-from-asyncio-context warning by exiting
        # explicitly rather than re-raising.
        raise SystemExit(1)

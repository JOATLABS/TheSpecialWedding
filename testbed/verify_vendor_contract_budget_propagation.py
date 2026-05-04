#!/usr/bin/env python3
"""
Vendor Contract → Budget Rollup Verifier — P2.2 Architecture (pm-substrate)
===========================================================================

Verifies the P2.2 refactor of app/services/vendor_service.py which routes
contract creation and payment recording through the pm-substrate service,
eliminating `vendor_contracts.budget_category_id` entirely.

## Architecture change (P2.2)

Before P2.2:
  - `vendor_contracts.budget_category_id` was hardcoded `None` at contract
    creation. The conditional `$inc` at `vendor_service.record_payment:3129`
    was unreachable in practice — manual milestone payments silently never
    updated `budget_categories.actual_spent`.

After P2.2:
  - `budget_category_id` is removed from `vendor_contracts` entirely.
  - Contract creation calls `pm_substrate.create_contract()` which registers a
    Contract node and wires a `wedding/contract_vendor` edge in the substrate graph.
  - Vendor assignment with a budget_category calls
    `pm_substrate.assign_vendor_to_budget_category()` which wires a
    `wedding/vendor_budget_category` edge in the substrate graph.
  - Payment recording calls `pm_substrate.record_payment()` which emits
    `wedding.contract.payment_recorded` to the substrate event bus.
  - `@pm/capability-wedding-budget` subscribes, walks the graph
    (contract → vendor → budgetCategory), and increments `actualSpentMinor`
    transactionally in Postgres.

## What this verifier tests

1. **Stub substrate flow**: runs the full Python service stack against the
   in-process stub (no live substrate or Postgres required). Verifies:
   - The stub receives `wedding.contract.payment_recorded`.
   - The payload contains `contractId`, `amount`, `paymentId`, `recordedAt`.
   - `budget_category_id` is absent from the payload (architectural assertion).

2. **Negative test**: injects `budget_category_id` directly onto the local
   MongoDB milestone document (simulating a legacy or manually-injected field).
   Verifies:
   - The system ignores it: no `budget_categories.$inc` runs.
   - The substrate event is still emitted.
   - `budget_category_id` is absent from the event payload.
   This confirms the old code path is definitively gone.

3. **Schema assertion**: verifies that new contract documents do NOT contain
   `budget_category_id`. The `pm_contract_id` field is present instead.

## Live end-to-end (deferred to P2.3)
The full flow (Python ↔ live substrate ↔ Postgres) is P2.3 work. When
PM_SUBSTRATE_URL is set and the substrate is running, the actual budget rollup
in Postgres will be testable. The live verifier will extend this file.

## Usage (P2.2 stub mode, no live substrate required)

    python testbed/verify_vendor_contract_budget_propagation.py

Or run via pytest for CI integration:

    pytest testbed/verify_vendor_contract_budget_propagation.py -v

## Prerequisites (P2.3 live mode)
When PM_SUBSTRATE_URL is configured:
  - Backend on localhost:8000, substrate on $PM_SUBSTRATE_URL
  - STRIPE_SECRET_KEY, MONGO_URI, ROOT_ADMIN_PASSWORD in .env
  - `stripe listen --forward-to localhost:8000/stripe/webhook`
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("verify_vendor_contract_budget_propagation")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TENANT_ID = "test_planner+budgetprop@thespecialwedding.io"
VENDOR_PROFILE_ID = "507f1f77bcf86cd799439011"
BUDGET_CATEGORY_ID = "507f1f77bcf86cd799439022"
WEDDING_ID = "wedding_budgetprop_verifier"
PM_CONTRACT_ID = str(uuid.uuid4())
PAYMENT_AMOUNT = 1500.0  # dollars
PAYMENT_AMOUNT_MINOR = int(PAYMENT_AMOUNT * 100)  # cents

# ---------------------------------------------------------------------------
# Helpers: build test fixtures
# ---------------------------------------------------------------------------


def _make_vendor() -> dict:
    return {
        "_id": VENDOR_PROFILE_ID,
        "business_name": "Snap Studios — BudgetProp Verifier",
        "email": "vendor+budgetprop@thespecialwedding.io",
        "phone": None,
        "service_category": "photographer",
        "custom_service_category": None,
        "address": None,
        "created_by": TENANT_ID,
    }


def _make_wedding() -> dict:
    return {
        "_id": WEDDING_ID,
        "couple_names": "Avery & Morgan (BudgetProp)",
        "date": "2026-09-15",
        "venue": "Test Venue",
        "assigned_planner_email": TENANT_ID,
    }


def _make_contract(pm_contract_id: str | None = PM_CONTRACT_ID) -> dict:
    return {
        "_id": "507f1f77bcf86cd799439099",
        "id": "507f1f77bcf86cd799439099",
        "root_contract_id": "507f1f77bcf86cd799439099",
        "wedding_id": WEDDING_ID,
        "vendor_profile_id": VENDOR_PROFILE_ID,
        "pm_contract_id": pm_contract_id,
        # budget_category_id intentionally absent — removed in P2.2
        "vendor_name": "Snap Studios — BudgetProp Verifier",
        "vendor_email": "vendor+budgetprop@thespecialwedding.io",
        "service_category": "photographer",
        "total_amount": 3000.0,
        "currency": "USD",
        "status": "draft",
        "is_current_version": True,
        "is_soft_deleted": None,
        "created_by": TENANT_ID,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "version_number": 1,
    }


def _make_milestone(contract_id: str = "507f1f77bcf86cd799439099") -> dict:
    from bson import ObjectId
    return {
        "_id": ObjectId("507f1f77bcf86cd799439088"),
        "contract_id": contract_id,
        "wedding_id": WEDDING_ID,
        "vendor_profile_id": VENDOR_PROFILE_ID,
        "pm_contract_id": PM_CONTRACT_ID,
        # budget_category_id intentionally absent — removed in P2.2
        "description": "Deposit (BudgetProp Verifier)",
        "amount": PAYMENT_AMOUNT,
        "paid_amount": 0.0,
        "currency": "USD",
        "status": "pending",
        "created_by": TENANT_ID,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# Test 1: stub flow — payment → substrate event → no budget_category_id
# ---------------------------------------------------------------------------


async def test_payment_recorded_event_reaches_substrate_without_budget_category_id() -> None:
    """
    ARCHITECTURAL ASSERTION:
    The payment_recorded event emitted by record_payment() must:
      1. Reach the substrate (stub records the call).
      2. Contain contractId, amount, paymentId, recordedAt in the payload.
      3. NOT contain budget_category_id anywhere in the event (not top-level,
         not inside payload). This is the field that caused the production bug
         and its absence is the architectural invariant of P2.2.
    """
    log.info("TEST 1: payment_recorded event reaches substrate, no budget_category_id")

    from app.integrations.pm_substrate._test_stub import SubstrateStub

    stub = SubstrateStub()
    substrate_client = stub.build_client()

    with patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService

        svc = VendorService.__new__(VendorService)
        milestone = _make_milestone()
        milestone_id = str(milestone["_id"])
        contract = _make_contract(pm_contract_id=PM_CONTRACT_ID)
        updated_milestone = {**milestone, "_id": str(milestone["_id"]), "paid_amount": PAYMENT_AMOUNT, "status": "paid"}

        budget_categories_mock = AsyncMock()
        svc.payment_milestones = AsyncMock()
        svc.payment_milestones.find_one = AsyncMock(side_effect=[milestone, updated_milestone])
        svc.payment_milestones.update_one = AsyncMock()
        svc.vendor_assignments = AsyncMock()
        svc.vendor_assignments.update_one = AsyncMock()
        svc.vendor_profiles = AsyncMock()
        svc.vendor_profiles.update_one = AsyncMock()
        svc.budget_categories = budget_categories_mock
        svc.vendor_contract_activities = AsyncMock()
        svc._get_owned_payment_milestone = AsyncMock(return_value=milestone)
        svc._ensure_contract_current_for_payments = MagicMock()
        svc.get_contract = AsyncMock(return_value=contract)
        svc._get_root_contract_id = VendorService._get_root_contract_id.__func__
        svc._log_contract_activity = AsyncMock()

        async def _fake_transaction(name, op):
            await op(None)

        svc._run_required_transaction = _fake_transaction

        await svc.record_payment(
            milestone_id=milestone_id,
            amount=PAYMENT_AMOUNT,
            payment_method="bank_transfer",
            created_by=TENANT_ID,
        )

    # Assert the substrate received the event.
    payment_events = stub.get_payment_events()
    assert payment_events, "FAIL: substrate did not receive wedding.contract.payment_recorded"
    event = payment_events[0]
    payload = event["payload"]

    assert payload.get("contractId") == PM_CONTRACT_ID, (
        f"FAIL: contractId mismatch: {payload.get('contractId')!r} != {PM_CONTRACT_ID!r}"
    )
    assert payload.get("amount") == PAYMENT_AMOUNT_MINOR, (
        f"FAIL: amount must be {PAYMENT_AMOUNT_MINOR} cents (not {payload.get('amount')!r} dollars)"
    )
    assert "paymentId" in payload, "FAIL: paymentId missing from event payload"
    assert "recordedAt" in payload, "FAIL: recordedAt missing from event payload"

    # THE KEY ARCHITECTURAL ASSERTION.
    stub.assert_no_field_in_events("budget_category_id")
    stub.assert_no_field_in_events("budget_category")

    # The old local rollup must be gone.
    budget_categories_mock.update_one.assert_not_called()

    log.info("  ✅ substrate received payment_recorded event")
    log.info("  ✅ budget_category_id absent from payload (architectural assertion)")
    log.info("  ✅ budget_categories.$inc not called (dead code path removed)")


# ---------------------------------------------------------------------------
# Test 2: negative test — injected budget_category_id is ignored
# ---------------------------------------------------------------------------


async def test_injected_budget_category_id_is_ignored() -> None:
    """
    NEGATIVE TEST:
    Inject budget_category_id manually onto the milestone doc (simulating
    a legacy or externally-modified document). Verify:
      1. No budget_categories.$inc runs (old code path is gone).
      2. Substrate event is still emitted.
      3. budget_category_id does NOT appear in the event payload.

    This test proves the architectural guarantee holds even against legacy data:
    the substrate path is the ONLY path for budget rollup.
    """
    log.info("TEST 2: injected budget_category_id is ignored by the system")

    from app.integrations.pm_substrate._test_stub import SubstrateStub

    stub = SubstrateStub()
    substrate_client = stub.build_client()

    with patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService

        svc = VendorService.__new__(VendorService)
        milestone = _make_milestone()
        # Inject the field manually.
        milestone["budget_category_id"] = BUDGET_CATEGORY_ID
        milestone_id = str(milestone["_id"])
        contract = _make_contract(pm_contract_id=PM_CONTRACT_ID)
        updated_milestone = {**milestone, "_id": str(milestone["_id"]), "paid_amount": PAYMENT_AMOUNT, "status": "paid"}

        budget_categories_mock = AsyncMock()
        svc.payment_milestones = AsyncMock()
        svc.payment_milestones.find_one = AsyncMock(side_effect=[milestone, updated_milestone])
        svc.payment_milestones.update_one = AsyncMock()
        svc.vendor_assignments = AsyncMock()
        svc.vendor_assignments.update_one = AsyncMock()
        svc.vendor_profiles = AsyncMock()
        svc.vendor_profiles.update_one = AsyncMock()
        svc.budget_categories = budget_categories_mock
        svc.vendor_contract_activities = AsyncMock()
        svc._get_owned_payment_milestone = AsyncMock(return_value=milestone)
        svc._ensure_contract_current_for_payments = MagicMock()
        svc.get_contract = AsyncMock(return_value=contract)
        svc._get_root_contract_id = VendorService._get_root_contract_id.__func__
        svc._log_contract_activity = AsyncMock()

        async def _fake_transaction(name, op):
            await op(None)

        svc._run_required_transaction = _fake_transaction

        await svc.record_payment(
            milestone_id=milestone_id,
            amount=PAYMENT_AMOUNT,
            payment_method="bank_transfer",
            created_by=TENANT_ID,
        )

    # Old rollup: must not run.
    budget_categories_mock.update_one.assert_not_called()

    # Substrate path: must still fire.
    payment_events = stub.get_payment_events()
    assert payment_events, "FAIL: substrate must still receive event even with injected budget_category_id"

    # Payload must not leak the injected field.
    stub.assert_no_field_in_events("budget_category_id")
    stub.assert_no_field_in_events("budget_category")

    log.info("  ✅ budget_categories.$inc not called despite injected budget_category_id")
    log.info("  ✅ substrate event still emitted (substrate path is the only path)")
    log.info("  ✅ budget_category_id absent from event payload")


# ---------------------------------------------------------------------------
# Test 3: schema assertion — new contracts have no budget_category_id
# ---------------------------------------------------------------------------


async def test_new_contract_has_no_budget_category_id_field() -> None:
    """
    Schema assertion: vendor_service.create_contract() must NOT write
    budget_category_id to the vendor_contracts document. The pm_contract_id
    field must be present instead.
    """
    log.info("TEST 3: new contract docs have no budget_category_id, have pm_contract_id")

    from app.integrations.pm_substrate._test_stub import SubstrateStub

    stub = SubstrateStub()
    substrate_client = stub.build_client()

    captured_docs: list[dict] = []

    async def _capture_insert(doc, **kwargs):
        captured_docs.append(dict(doc))
        result = MagicMock()
        result.inserted_id = "507f1f77bcf86cd799439099"
        return result

    async def _capture_update(query, update, **kwargs):
        pass

    with patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService

        svc = VendorService.__new__(VendorService)
        svc.vendor_contracts = AsyncMock()
        svc.vendor_contracts.insert_one = AsyncMock(side_effect=_capture_insert)
        svc.vendor_contracts.update_one = AsyncMock(side_effect=_capture_update)
        svc.vendor_profiles = AsyncMock()
        svc.contract_templates = AsyncMock()
        svc.vendor_assignments = AsyncMock()
        svc.vendor_assignments.find_one = AsyncMock(return_value=None)
        svc.vendor_quotes = AsyncMock()
        svc.vendor_contract_activities = AsyncMock()
        svc.users = AsyncMock()
        svc.users.find_one = AsyncMock(return_value=None)
        svc.weddings = AsyncMock()
        svc.email_service = AsyncMock()
        svc.storage = MagicMock()
        svc.payment_links = AsyncMock()
        svc.vendor_forms = AsyncMock()
        svc.form_responses = AsyncMock()

        svc._generate_contract_number = lambda: "CON-20260101-0001"
        svc._get_vendor_service_label = VendorService._get_vendor_service_label.__func__
        svc._get_planner_contract_settings = AsyncMock(
            return_value={
                "token_expiry_days": 30, "deposit_due_days": 7,
                "payment_reminder_days": [], "auto_followup_days": 3, "default_currency": "USD",
            }
        )
        svc._get_owned_vendor_profile = AsyncMock(return_value=_make_vendor())
        svc._get_owned_wedding = AsyncMock(return_value=_make_wedding())
        svc._serialize_doc = VendorService._serialize_doc.__func__
        svc._attach_contract_version_metadata = VendorService._attach_contract_version_metadata.__func__
        svc._stringify_id = VendorService._stringify_id.__func__
        svc._get_root_contract_id = VendorService._get_root_contract_id.__func__
        svc._log_contract_activity = AsyncMock()
        svc._build_inactive_contract_token_fields = (
            VendorService._build_inactive_contract_token_fields.__func__
        )

        await svc.create_contract(
            wedding_id=WEDDING_ID,
            vendor_profile_id=VENDOR_PROFILE_ID,
            created_by=TENANT_ID,
            total_amount=3000.0,
        )

    assert captured_docs, "Expected insert_one to be called"
    doc = captured_docs[0]

    # The field must be gone.
    assert "budget_category_id" not in doc, (
        f"FAIL: budget_category_id must not appear in new contract docs. Got: {doc.get('budget_category_id')!r}"
    )

    # pm_contract_id must be present (even if None initially, before substrate call fills it).
    assert "pm_contract_id" in doc, (
        "FAIL: pm_contract_id must be present in new contract docs"
    )

    # Substrate must have received Contract + Vendor node creation calls.
    contract_nodes = [n for n in stub.nodes if n.get("profile", {}).get("concrete") == "Contract"]
    assert contract_nodes, "FAIL: substrate must receive Contract node creation"

    log.info("  ✅ budget_category_id absent from new contract document")
    log.info("  ✅ pm_contract_id present in new contract document")
    log.info("  ✅ substrate received Contract node creation")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def main() -> int:
    log.info("")
    log.info("=" * 60)
    log.info("verify_vendor_contract_budget_propagation — P2.2")
    log.info("Verifying pm-substrate budget rollup architecture")
    log.info("=" * 60)
    log.info("")

    failures: list[str] = []

    for test_fn in [
        test_payment_recorded_event_reaches_substrate_without_budget_category_id,
        test_injected_budget_category_id_is_ignored,
        test_new_contract_has_no_budget_category_id_field,
    ]:
        test_name = test_fn.__name__
        try:
            await test_fn()
            log.info("PASS: %s", test_name)
        except AssertionError as exc:
            log.error("FAIL: %s — %s", test_name, exc)
            failures.append(test_name)
        except Exception as exc:
            log.exception("ERROR: %s — %s", test_name, exc)
            failures.append(test_name)
        log.info("")

    log.info("=" * 60)
    if failures:
        log.error("FAILED: %d test(s)", len(failures))
        for name in failures:
            log.error("  - %s", name)
        return 1

    log.info("✅ All P2.2 assertions pass.")
    log.info("")
    log.info("P2.3 TODO:")
    log.info("  - Real end-to-end test: Python ↔ live substrate ↔ Postgres.")
    log.info("  - Set PM_SUBSTRATE_URL and run with the substrate online.")
    log.info("  - Verify BudgetCategory.actualSpentMinor increments in Postgres.")
    log.info("=" * 60)
    return 0


# ---------------------------------------------------------------------------
# Pytest integration
# ---------------------------------------------------------------------------


def test_payment_recorded_no_budget_category_id():
    """pytest entry point for test 1."""
    asyncio.run(test_payment_recorded_event_reaches_substrate_without_budget_category_id())


def test_injected_field_is_ignored():
    """pytest entry point for test 2."""
    asyncio.run(test_injected_budget_category_id_is_ignored())


def test_new_contract_schema():
    """pytest entry point for test 3."""
    asyncio.run(test_new_contract_has_no_budget_category_id_field())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        log.exception("Verification aborted: %s", exc)
        raise SystemExit(1)

"""
PM Substrate service integration tests (P2.2).

Tests the vendor_service.py refactor against the in-process stub:
  - contract creation flow: Python service → stub substrate received correct calls.
  - payment recording flow: Python service → stub substrate received
    wedding.contract.payment_recorded with correct payload, no budget_category_id.
  - vendor → BudgetCategory edge sync: assign_vendor_to_wedding calls the
    substrate when a budget_category_id is provided.

These tests mock MongoDB (mongomock) and the substrate (SubstrateStub).
No live backend, Postgres, or Stripe required.

P2.3 will add real end-to-end tests (Python ↔ live substrate ↔ Postgres).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.integrations.pm_substrate._test_stub import SubstrateStub
from app.integrations.pm_substrate.client import (
    PMSubstrateClient,
    _budget_category_node_id,
    _vendor_node_id,
)

# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

TENANT_ID = "planner@example.com"
VENDOR_PROFILE_ID = "507f1f77bcf86cd799439011"
WEDDING_ID = "wedding_abc123"
BUDGET_CATEGORY_ID = "507f1f77bcf86cd799439022"
PM_CONTRACT_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers: build realistic-looking Mongo document stubs
# ---------------------------------------------------------------------------


def _make_vendor(vendor_profile_id: str = VENDOR_PROFILE_ID) -> dict:
    return {
        "_id": vendor_profile_id,
        "business_name": "Snap Studios",
        "email": "snap@vendor.io",
        "phone": "555-0100",
        "service_category": "photographer",
        "custom_service_category": None,
        "address": "123 Main St",
        "created_by": TENANT_ID,
    }


def _make_wedding() -> dict:
    return {
        "_id": WEDDING_ID,
        "couple_names": "Avery & Morgan",
        "date": "2026-09-15",
        "venue": "Garden Hall",
        "assigned_planner_email": TENANT_ID,
    }


def _make_contract(pm_contract_id: str | None = PM_CONTRACT_ID) -> dict:
    return {
        "_id": "507f1f77bcf86cd799439099",
        "id": "507f1f77bcf86cd799439099",
        "wedding_id": WEDDING_ID,
        "vendor_profile_id": VENDOR_PROFILE_ID,
        "pm_contract_id": pm_contract_id,
        "vendor_name": "Snap Studios",
        "vendor_email": "snap@vendor.io",
        "service_category": "photographer",
        "total_amount": 3000.0,
        "currency": "USD",
        "status": "draft",
        "is_current_version": True,
        "is_soft_deleted": None,
        "created_by": TENANT_ID,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "root_contract_id": "507f1f77bcf86cd799439099",
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
        "description": "Deposit",
        "amount": 1500.0,
        "paid_amount": 0.0,
        "currency": "USD",
        "status": "pending",
        "created_by": TENANT_ID,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# contract creation flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_contract_calls_substrate_create_contract():
    """
    vendor_service.create_contract() calls pm_substrate.create_contract()
    with the correct arguments after writing the local Mongo doc.
    """
    stub = SubstrateStub()
    substrate_client = stub.build_client()

    with patch(
        "app.integrations.pm_substrate.client._default_client", substrate_client
    ), patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService

        svc = VendorService.__new__(VendorService)

        # Wire mock collections.
        inserted_id = "507f1f77bcf86cd799439099"
        insert_result = MagicMock()
        insert_result.inserted_id = inserted_id

        vendor_contracts_coll = AsyncMock()
        vendor_contracts_coll.insert_one = AsyncMock(return_value=insert_result)
        vendor_contracts_coll.update_one = AsyncMock()

        svc.vendor_contracts = vendor_contracts_coll
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

        # Internal helpers that need real implementations.
        svc._generate_contract_number = lambda: "CON-20260101-0001"
        svc._get_vendor_service_label = VendorService._get_vendor_service_label.__func__
        svc._get_planner_contract_settings = AsyncMock(
            return_value={
                "token_expiry_days": 30,
                "deposit_due_days": 7,
                "payment_reminder_days": [7, 3, 1],
                "auto_followup_days": 3,
                "default_currency": "USD",
            }
        )
        svc._get_owned_vendor_profile = AsyncMock(return_value=_make_vendor())
        svc._get_owned_wedding = AsyncMock(return_value=_make_wedding())
        svc._get_owned_contract = AsyncMock()
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

    # Verify substrate received correct calls.
    assert len(stub.nodes) >= 2, f"Expected ≥2 nodes (Vendor + Contract), got {len(stub.nodes)}"

    # Vendor node.
    vendor_nodes = [n for n in stub.nodes if n.get("profile", {}).get("concrete") == "Vendor"]
    assert vendor_nodes, "Expected Vendor node creation"
    assert vendor_nodes[0]["identity"]["name"] == "Snap Studios"

    # Contract node.
    contract_nodes = [n for n in stub.nodes if n.get("profile", {}).get("concrete") == "Contract"]
    assert contract_nodes, "Expected Contract node creation"
    assert contract_nodes[0]["identity"]["state"] == "draft"
    assert contract_nodes[0]["identity"]["amountMinor"] == 300000  # 3000.00 * 100

    # Edge contract → vendor.
    contract_vendor_edges = [e for e in stub.edges if e.get("type") == "wedding/contract_vendor"]
    assert contract_vendor_edges, "Expected wedding/contract_vendor edge"

    # Architectural invariant: no budget_category_id anywhere.
    for node in stub.nodes:
        assert "budget_category_id" not in node
        assert "budget_category_id" not in node.get("identity", {})


@pytest.mark.asyncio
async def test_create_contract_stores_pm_contract_id():
    """
    create_contract() writes pm_contract_id back to the MongoDB doc.
    budget_category_id must NOT be written.
    """
    stub = SubstrateStub()
    substrate_client = stub.build_client()

    with patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService

        svc = VendorService.__new__(VendorService)

        inserted_id = "507f1f77bcf86cd799439099"
        insert_result = MagicMock()
        insert_result.inserted_id = inserted_id

        captured_updates: list[dict] = []

        async def _capture_update(query, update, **kwargs):
            captured_updates.append({"query": query, "update": update})

        vendor_contracts_coll = AsyncMock()
        vendor_contracts_coll.insert_one = AsyncMock(return_value=insert_result)
        vendor_contracts_coll.update_one = AsyncMock(side_effect=_capture_update)
        svc.vendor_contracts = vendor_contracts_coll
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
            return_value={"token_expiry_days": 30, "deposit_due_days": 7,
                          "payment_reminder_days": [], "auto_followup_days": 3, "default_currency": "USD"}
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

    # At least one update should have set pm_contract_id.
    pm_updates = [
        u for u in captured_updates
        if "pm_contract_id" in u["update"].get("$set", {})
    ]
    assert pm_updates, "Expected update_one to set pm_contract_id on the contract doc"

    # Architectural assertion: no update should set budget_category_id.
    for u in captured_updates:
        assert "budget_category_id" not in u["update"].get("$set", {}), (
            f"budget_category_id must never be written to vendor_contracts: {u}"
        )


# ---------------------------------------------------------------------------
# payment recording flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_payment_emits_substrate_event_no_budget_category_id():
    """
    ARCHITECTURAL ASSERTION:
    record_payment() emits wedding.contract.payment_recorded to the substrate
    and the payload does NOT contain budget_category_id — anywhere.
    """
    stub = SubstrateStub()
    substrate_client = stub.build_client()

    with patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService
        from bson import ObjectId

        svc = VendorService.__new__(VendorService)

        milestone = _make_milestone()
        milestone_id = str(milestone["_id"])
        contract = _make_contract(pm_contract_id=PM_CONTRACT_ID)

        updated_milestone = {**milestone, "_id": str(milestone["_id"]), "paid_amount": 1500.0, "status": "paid"}

        svc.payment_milestones = AsyncMock()
        svc.payment_milestones.find_one = AsyncMock(side_effect=[milestone, updated_milestone])
        svc.payment_milestones.update_one = AsyncMock()
        svc.vendor_assignments = AsyncMock()
        svc.vendor_assignments.update_one = AsyncMock()
        svc.vendor_profiles = AsyncMock()
        svc.vendor_profiles.update_one = AsyncMock()
        svc.budget_categories = AsyncMock()
        svc.vendor_contract_activities = AsyncMock()

        svc._get_owned_payment_milestone = AsyncMock(return_value=milestone)
        svc._ensure_contract_current_for_payments = MagicMock()
        svc.get_contract = AsyncMock(return_value=contract)
        svc._get_root_contract_id = VendorService._get_root_contract_id.__func__
        svc._log_contract_activity = AsyncMock()

        # Make the Mongo transaction work without a real connection.
        async def _fake_transaction(name, op):
            await op(None)

        svc._run_required_transaction = _fake_transaction

        await svc.record_payment(
            milestone_id=milestone_id,
            amount=1500.0,
            payment_method="bank_transfer",
            created_by=TENANT_ID,
        )

    # The substrate must have received the payment event.
    payment_events = stub.get_payment_events()
    assert payment_events, "Expected at least one wedding.contract.payment_recorded event"

    event = payment_events[0]
    payload = event["payload"]
    assert payload["contractId"] == PM_CONTRACT_ID
    assert payload["amount"] == 150000  # $1500.00 in cents
    assert "paymentId" in payload
    assert "recordedAt" in payload

    # THE KEY ARCHITECTURAL ASSERTION.
    stub.assert_no_field_in_events("budget_category_id")
    stub.assert_no_field_in_events("budget_category")

    # budget_categories.update_one must NOT have been called.
    svc.budget_categories.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_record_payment_skips_substrate_when_no_pm_contract_id():
    """
    record_payment() gracefully skips the substrate event when the contract
    predates P2.2 (no pm_contract_id set). No error is raised.
    """
    stub = SubstrateStub()
    substrate_client = stub.build_client()

    with patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService

        svc = VendorService.__new__(VendorService)

        milestone = _make_milestone()
        milestone["pm_contract_id"] = None
        milestone_id = str(milestone["_id"])
        contract = _make_contract(pm_contract_id=None)  # Pre-P2.2 contract

        updated_milestone = {**milestone, "_id": str(milestone["_id"]), "paid_amount": 1500.0, "status": "paid"}

        svc.payment_milestones = AsyncMock()
        svc.payment_milestones.find_one = AsyncMock(side_effect=[milestone, updated_milestone])
        svc.payment_milestones.update_one = AsyncMock()
        svc.vendor_assignments = AsyncMock()
        svc.vendor_assignments.update_one = AsyncMock()
        svc.vendor_profiles = AsyncMock()
        svc.vendor_profiles.update_one = AsyncMock()
        svc.budget_categories = AsyncMock()
        svc.vendor_contract_activities = AsyncMock()

        svc._get_owned_payment_milestone = AsyncMock(return_value=milestone)
        svc._ensure_contract_current_for_payments = MagicMock()
        svc.get_contract = AsyncMock(return_value=contract)
        svc._get_root_contract_id = VendorService._get_root_contract_id.__func__
        svc._log_contract_activity = AsyncMock()

        async def _fake_transaction(name, op):
            await op(None)

        svc._run_required_transaction = _fake_transaction

        # Should not raise.
        await svc.record_payment(
            milestone_id=milestone_id,
            amount=1500.0,
            payment_method="bank_transfer",
            created_by=TENANT_ID,
        )

    # No substrate events should have been emitted.
    assert not stub.events, "No substrate events expected for pre-P2.2 contracts"
    # Also: budget_categories must not be touched (the old dead code path is gone).
    svc.budget_categories.update_one.assert_not_called()


# ---------------------------------------------------------------------------
# vendor → BudgetCategory edge sync
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assign_vendor_to_wedding_creates_substrate_edge():
    """
    assign_vendor_to_wedding() calls pm_substrate.assign_vendor_to_budget_category()
    when a budget_category_id is provided, creating the vendor_budget_category edge.
    """
    stub = SubstrateStub()
    substrate_client = stub.build_client()

    with patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService

        svc = VendorService.__new__(VendorService)

        insert_result = MagicMock()
        insert_result.inserted_id = "assignment_001"

        svc.vendor_profiles = AsyncMock()
        svc.vendor_profiles.update_one = AsyncMock()
        svc.vendor_assignments = AsyncMock()
        svc.vendor_assignments.find_one = AsyncMock(return_value=None)
        svc.vendor_assignments.insert_one = AsyncMock(return_value=insert_result)
        svc.weddings = AsyncMock()
        svc.users = AsyncMock()
        svc.email_service = AsyncMock()
        svc.storage = MagicMock()
        svc.payment_links = AsyncMock()

        svc._get_owned_vendor_profile = AsyncMock(return_value=_make_vendor())
        svc._get_owned_wedding = AsyncMock(return_value=_make_wedding())

        await svc.assign_vendor_to_wedding(
            vendor_profile_id=VENDOR_PROFILE_ID,
            wedding_id=WEDDING_ID,
            created_by=TENANT_ID,
            budget_category_id=BUDGET_CATEGORY_ID,
            service_notes="Test assignment",
        )

    # The edge must have been created.
    edge = stub.assert_edge_created("wedding/vendor_budget_category")
    assert edge["fromId"] == _vendor_node_id(TENANT_ID, VENDOR_PROFILE_ID)
    assert edge["toId"] == _budget_category_node_id(TENANT_ID, BUDGET_CATEGORY_ID)

    # Vendor and BudgetCategory nodes must have been created.
    vendor_nodes = [n for n in stub.nodes if n.get("profile", {}).get("concrete") == "Vendor"]
    assert vendor_nodes, "Expected Vendor node"
    category_nodes = [n for n in stub.nodes if n.get("profile", {}).get("concrete") == "BudgetCategory"]
    assert category_nodes, "Expected BudgetCategory node"


@pytest.mark.asyncio
async def test_assign_vendor_to_wedding_no_substrate_call_without_budget_category():
    """
    assign_vendor_to_wedding() does NOT call the substrate when no budget_category_id
    is provided — the edge has no target.
    """
    stub = SubstrateStub()
    substrate_client = stub.build_client()

    with patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService

        svc = VendorService.__new__(VendorService)

        insert_result = MagicMock()
        insert_result.inserted_id = "assignment_002"

        svc.vendor_profiles = AsyncMock()
        svc.vendor_profiles.update_one = AsyncMock()
        svc.vendor_assignments = AsyncMock()
        svc.vendor_assignments.find_one = AsyncMock(return_value=None)
        svc.vendor_assignments.insert_one = AsyncMock(return_value=insert_result)
        svc.weddings = AsyncMock()
        svc.users = AsyncMock()
        svc.email_service = AsyncMock()
        svc.storage = MagicMock()
        svc.payment_links = AsyncMock()

        svc._get_owned_vendor_profile = AsyncMock(return_value=_make_vendor())
        svc._get_owned_wedding = AsyncMock(return_value=_make_wedding())

        await svc.assign_vendor_to_wedding(
            vendor_profile_id=VENDOR_PROFILE_ID,
            wedding_id=WEDDING_ID,
            created_by=TENANT_ID,
            budget_category_id=None,  # No category
        )

    assert not stub.nodes, "No substrate nodes expected when no budget_category_id"
    assert not stub.edges, "No substrate edges expected when no budget_category_id"


# ---------------------------------------------------------------------------
# Negative test: old code path is gone
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_categories_collection_not_touched_in_record_payment():
    """
    REGRESSION TEST: The old budget_categories.actual_spent $inc is gone.
    record_payment must NEVER touch budget_categories directly, regardless of
    what fields are on the milestone.
    """
    stub = SubstrateStub()
    substrate_client = stub.build_client()

    with patch("app.services.vendor_service._get_substrate_client", return_value=substrate_client):
        from app.services.vendor_service import VendorService

        svc = VendorService.__new__(VendorService)

        milestone = _make_milestone()
        # Inject a budget_category_id manually — simulates an injected or
        # legacy doc. The system must ignore it.
        milestone["budget_category_id"] = BUDGET_CATEGORY_ID
        milestone_id = str(milestone["_id"])
        contract = _make_contract(pm_contract_id=PM_CONTRACT_ID)

        updated_milestone = {**milestone, "_id": str(milestone["_id"]), "paid_amount": 1500.0, "status": "paid"}

        budget_categories_mock = AsyncMock()

        svc.payment_milestones = AsyncMock()
        svc.payment_milestones.find_one = AsyncMock(side_effect=[milestone, updated_milestone])
        svc.payment_milestones.update_one = AsyncMock()
        svc.vendor_assignments = AsyncMock()
        svc.vendor_assignments.update_one = AsyncMock()
        svc.vendor_profiles = AsyncMock()
        svc.vendor_profiles.update_one = AsyncMock()
        svc.budget_categories = budget_categories_mock  # Will assert never called
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
            amount=1500.0,
            payment_method="bank_transfer",
            created_by=TENANT_ID,
        )

    # The key negative assertion: budget_categories must not be touched.
    budget_categories_mock.update_one.assert_not_called()

    # The substrate event must still have been emitted.
    payment_events = stub.get_payment_events()
    assert payment_events, "Substrate event must still fire"

    # And budget_category_id must be absent from all events.
    stub.assert_no_field_in_events("budget_category_id")

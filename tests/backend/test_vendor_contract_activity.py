from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi import HTTPException

import app.services.vendor_service as vendor_service_module
from app.models.vendor import ContractKind, ContractStatus
from app.models.vendor_contracts import VendorContractActivityType
from app.services.vendor_service import vendor_service


def _matches_query(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == "$or":
            return any(_matches_query(document, branch) for branch in expected)

        actual = document.get(key)
        if isinstance(expected, dict):
            if "$exists" in expected:
                exists = key in document
                if exists != expected["$exists"]:
                    return False
                continue
            if "$in" in expected:
                if actual not in expected["$in"]:
                    return False
                continue
            if "$ne" in expected:
                # ``{"$ne": True}`` filters used by the soft-delete retrofit
                # accept missing fields (Mongo treats absent as not-equal).
                if actual == expected["$ne"]:
                    return False
                continue
            return False

        if actual != expected:
            return False

    return True


class FakeCursor:
    def __init__(self, documents: list[dict]):
        self._documents = documents

    def sort(self, field: str, direction: int) -> "FakeCursor":
        reverse = direction == -1
        self._documents = sorted(
            self._documents,
            key=lambda item: item.get(field),
            reverse=reverse,
        )
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        docs = deepcopy(self._documents)
        if length is None:
            return docs
        return docs[:length]


class FakeCollection:
    def __init__(self, documents: list[dict] | None = None):
        self.documents = documents or []

    async def insert_one(self, document: dict, session=None) -> SimpleNamespace:
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def find_one(self, query: dict, session=None) -> dict | None:
        for document in self.documents:
            if _matches_query(document, query):
                return deepcopy(document)
        return None

    async def update_one(
        self, query: dict, update: dict, session=None
    ) -> SimpleNamespace:
        for document in self.documents:
            if _matches_query(document, query):
                for key, value in update.get("$set", {}).items():
                    document[key] = deepcopy(value)
                for key, value in update.get("$inc", {}).items():
                    document[key] = document.get(key, 0) + value
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    async def update_many(
        self, query: dict, update: dict, session=None
    ) -> SimpleNamespace:
        modified_count = 0
        for document in self.documents:
            if _matches_query(document, query):
                for key, value in update.get("$set", {}).items():
                    document[key] = deepcopy(value)
                modified_count += 1
        return SimpleNamespace(
            matched_count=modified_count, modified_count=modified_count
        )

    def find(self, query: dict) -> FakeCursor:
        return FakeCursor(
            [
                deepcopy(document)
                for document in self.documents
                if _matches_query(document, query)
            ]
        )


class DummyEmailService:
    async def send_email(self, **kwargs) -> dict:
        return {"success": True, "id": "email_123"}


def make_contract_doc(
    *,
    contract_id: ObjectId | None = None,
    status: str = ContractStatus.DRAFT.value,
    is_current_version: bool = True,
    contract_kind: str = ContractKind.ORIGINAL.value,
    root_contract_id: str | None = None,
    parent_contract_id: str | None = None,
    supersedes_contract_id: str | None = None,
    access_token: str = "token-1",
    created_at: datetime | None = None,
) -> dict:
    object_id = contract_id or ObjectId()
    now = created_at or datetime.now(timezone.utc)
    return {
        "_id": object_id,
        "wedding_id": "wedding-1",
        "vendor_profile_id": "vendor-1",
        "vendor_name": "Vendor Co",
        "vendor_email": "vendor@example.com",
        "service_category": "photographer",
        "contract_title": "Photo Contract",
        "contract_number": "CON-TEST-001",
        "sections": [
            {"id": "scope", "title": "Scope", "content": "Coverage", "order": 0}
        ],
        "terms_and_conditions": "Terms",
        "cancellation_policy": "Cancel",
        "custom_clauses": "Custom",
        "total_amount": 5000,
        "currency": "USD",
        "deposit_amount": 2500,
        "status": status,
        "access_token_hash": vendor_service._hash_contract_access_token(access_token),
        "token_expires_at": datetime.now(timezone.utc) + timedelta(days=30),
        "token_revoked_at": None,
        "token_last_sent_at": None,
        "token_last_viewed_at": None,
        "created_by": "planner@example.com",
        "created_at": now,
        "updated_at": now,
        "version_number": 1,
        "root_contract_id": root_contract_id or str(object_id),
        "parent_contract_id": parent_contract_id,
        "supersedes_contract_id": supersedes_contract_id,
        "superseded_by_contract_id": None,
        "is_current_version": is_current_version,
        "contract_kind": contract_kind,
        "amendment_reason": None,
        "superseded_at": None,
        "sent_at": None,
        "viewed_at": None,
        "signed_at": None,
        "signed_by_name": None,
        "signed_by_email": None,
        "signature_ip": None,
        "internal_notes": "Internal",
        "attachments": [],
    }


@pytest.fixture
def configured_vendor_service(monkeypatch: pytest.MonkeyPatch):
    vendor_id = ObjectId()
    contracts = FakeCollection([])
    activities = FakeCollection([])
    milestones = FakeCollection([])
    assignments = FakeCollection([])
    budget_categories = FakeCollection([])
    vendor_profiles = FakeCollection(
        [
            {
                "_id": vendor_id,
                "business_name": "Vendor Co",
                "email": "vendor@example.com",
                "phone": "555-1234",
                "address": "123 Main St",
                "service_category": "photographer",
                "total_revenue": 0,
                "created_by": "planner@example.com",
            }
        ]
    )

    monkeypatch.setattr(vendor_service, "vendor_contracts", contracts)
    monkeypatch.setattr(vendor_service, "vendor_contract_activities", activities)
    monkeypatch.setattr(vendor_service, "payment_milestones", milestones)
    monkeypatch.setattr(vendor_service, "vendor_assignments", assignments)
    monkeypatch.setattr(vendor_service, "budget_categories", budget_categories)
    monkeypatch.setattr(vendor_service, "vendor_profiles", vendor_profiles)
    monkeypatch.setattr(
        vendor_service,
        "_get_owned_wedding",
        AsyncMock(
            return_value={
                "_id": "wedding-1",
                "couple_names": "Alex & Jamie",
                "date": "2026-06-12",
                "venue": "Garden Venue",
                "assigned_planner_email": "planner@example.com",
            }
        ),
    )
    monkeypatch.setattr(vendor_service, "_log_communication", AsyncMock())

    async def run_required_transaction(_operation_name, operation):
        return await operation(None)

    monkeypatch.setattr(
        vendor_service, "_run_required_transaction", run_required_transaction
    )
    monkeypatch.setattr(
        vendor_service,
        "_get_planner_contract_settings",
        AsyncMock(return_value={"token_expiry_days": 30, "deposit_due_days": 7}),
    )
    monkeypatch.setattr(
        vendor_service,
        "_get_wedding",
        AsyncMock(
            return_value={
                "_id": "wedding-1",
                "couple_names": "Alex & Jamie",
                "date": "2026-06-12",
                "venue": "Garden Venue",
            }
        ),
    )
    monkeypatch.setattr(
        vendor_service,
        "users",
        SimpleNamespace(
            find_one=AsyncMock(
                return_value={
                    "email": "planner@example.com",
                    "first_name": "Pat",
                    "last_name": "Planner",
                    "company_name": "Best Weddings",
                }
            )
        ),
    )
    vendor_service.email_service = DummyEmailService()

    monkeypatch.setattr(
        vendor_service_module,
        "mongo",
        SimpleNamespace(
            db={
                "vendor_submissions": FakeCollection([]),
                "vendor_forms": FakeCollection([]),
            }
        ),
    )

    return (
        vendor_service,
        contracts,
        activities,
        milestones,
        assignments,
        budget_categories,
        str(vendor_id),
    )


@pytest.mark.asyncio
async def test_create_contract_logs_contract_created(configured_vendor_service) -> None:
    service, _, activities, _, _, _, vendor_profile_id = configured_vendor_service

    created = await service.create_contract(
        wedding_id="wedding-1",
        vendor_profile_id=vendor_profile_id,
        created_by="planner@example.com",
        total_amount=5000,
        deposit_percentage=50,
    )

    assert (
        activities.documents[-1]["activity_type"]
        == VendorContractActivityType.CONTRACT_CREATED.value
    )
    assert activities.documents[-1]["contract_id"] == created["_id"]


@pytest.mark.asyncio
async def test_update_contract_logs_contract_updated(configured_vendor_service) -> None:
    service, contracts, activities, _, _, _, _ = configured_vendor_service
    contract = make_contract_doc(status=ContractStatus.DRAFT.value)
    contracts.documents.append(deepcopy(contract))

    await service.update_contract(
        contract_id=str(contract["_id"]),
        data={"service_location": "Austin, TX"},
        updated_by="planner@example.com",
    )

    assert (
        activities.documents[-1]["activity_type"]
        == VendorContractActivityType.CONTRACT_UPDATED.value
    )
    assert activities.documents[-1]["metadata"]["changed_fields"] == [
        "service_location"
    ]


@pytest.mark.asyncio
async def test_apply_form_data_logs_activity(
    configured_vendor_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, contracts, activities, _, _, _, _ = configured_vendor_service
    contract = make_contract_doc(status=ContractStatus.DRAFT.value)
    contracts.documents.append(deepcopy(contract))

    # Stub the tenant-scoped form-lookup helpers introduced in the
    # cross-tenant form-data apply fix. Their underlying Motor reads on
    # ``vendor_submissions`` / ``vendor_forms`` (and ``self.vendor_forms``)
    # would otherwise try to hit real Mongo.
    monkeypatch.setattr(
        vendor_service,
        "_get_owned_form_submission",
        AsyncMock(
            return_value={
                "_id": ObjectId("507f1f77bcf86cd799439012"),
                "form_id": ObjectId("507f1f77bcf86cd799439013"),
                "vendor_email": "vendor@example.com",
                "submission_data": {
                    "portfolio_link": "https://example.com/work",
                },
            }
        ),
    )
    monkeypatch.setattr(
        vendor_service,
        "_get_owned_form",
        AsyncMock(
            return_value={
                "_id": ObjectId("507f1f77bcf86cd799439013"),
                "created_by": "planner@example.com",
                "vendor_email": "vendor@example.com",
                "fields": [],
            }
        ),
    )

    await service.apply_form_data_to_contract(
        contract_id=str(contract["_id"]),
        form_submission_id="507f1f77bcf86cd799439012",
        field_mappings={"portfolio_link": "{{vendor_portfolio}}"},
        applied_by="planner@example.com",
    )

    assert (
        activities.documents[-1]["activity_type"]
        == VendorContractActivityType.FORM_DATA_APPLIED.value
    )
    assert (
        activities.documents[-1]["metadata"]["form_submission_id"]
        == "507f1f77bcf86cd799439012"
    )


@pytest.mark.asyncio
async def test_contract_view_is_logged_once_on_first_public_view(
    configured_vendor_service,
) -> None:
    service, contracts, activities, _, _, _, _ = configured_vendor_service
    contract = make_contract_doc(status=ContractStatus.SENT.value)
    contracts.documents.append(deepcopy(contract))

    await service.get_contract_by_token(str(contract["_id"]), "token-1")
    await service.get_contract_by_token(str(contract["_id"]), "token-1")

    viewed_events = [
        item
        for item in activities.documents
        if item["activity_type"] == VendorContractActivityType.CONTRACT_VIEWED.value
    ]
    assert len(viewed_events) == 1


@pytest.mark.asyncio
async def test_send_contract_logs_sent_and_superseded_activity(
    configured_vendor_service,
) -> None:
    service, contracts, activities, _, _, _, _ = configured_vendor_service
    original = make_contract_doc(
        status=ContractStatus.SIGNED.value,
        is_current_version=True,
        access_token="original-token",
    )
    child = make_contract_doc(
        contract_id=ObjectId(),
        status=ContractStatus.DRAFT.value,
        is_current_version=False,
        contract_kind=ContractKind.REVISION.value,
        root_contract_id=str(original["_id"]),
        parent_contract_id=str(original["_id"]),
        supersedes_contract_id=str(original["_id"]),
        access_token="child-token",
    )
    child["version_number"] = 2
    contracts.documents.extend([deepcopy(original), deepcopy(child)])

    await service.send_contract(
        contract_id=str(child["_id"]),
        created_by="planner@example.com",
        message="Please review changes",
    )

    activity_types = [item["activity_type"] for item in activities.documents]
    assert VendorContractActivityType.CONTRACT_SENT.value in activity_types
    assert VendorContractActivityType.CONTRACT_SUPERSEDED.value in activity_types


@pytest.mark.asyncio
async def test_sign_contract_logs_signed_activity(configured_vendor_service) -> None:
    service, contracts, activities, _, assignments, _, _ = configured_vendor_service
    contract = make_contract_doc(status=ContractStatus.SENT.value)
    contracts.documents.append(deepcopy(contract))
    assignments.documents.append(
        {
            "_id": ObjectId(),
            "vendor_profile_id": "vendor-1",
            "wedding_id": "wedding-1",
            "paid_amount": 0,
            "status": "quoted",
        }
    )

    await service.sign_contract(
        contract_id=str(contract["_id"]),
        token="token-1",
        signer_name="Vendor Owner",
        signer_email="vendor@example.com",
        signature_ip="127.0.0.1",
    )

    assert (
        activities.documents[-1]["activity_type"]
        == VendorContractActivityType.CONTRACT_SIGNED.value
    )
    assert activities.documents[-1]["actor"]["display_name"] == "Vendor Owner"


@pytest.mark.asyncio
async def test_create_payment_milestones_and_record_payment_log_activity(
    configured_vendor_service,
) -> None:
    (
        service,
        contracts,
        activities,
        milestones,
        assignments,
        budget_categories,
        vendor_profile_id,
    ) = configured_vendor_service
    contract = make_contract_doc(status=ContractStatus.DRAFT.value)
    contract["vendor_profile_id"] = vendor_profile_id
    contract["budget_category_id"] = str(ObjectId())
    contracts.documents.append(deepcopy(contract))
    assignments.documents.append(
        {
            "_id": ObjectId(),
            "vendor_profile_id": "vendor-1",
            "wedding_id": "wedding-1",
            "paid_amount": 0,
        }
    )
    budget_categories.documents.append(
        {
            "_id": ObjectId(contract["budget_category_id"]),
            "actual_spent": 0,
        }
    )

    created = await service.create_payment_milestones(
        contract_id=str(contract["_id"]),
        milestones=[
            {
                "description": "Deposit",
                "amount": 2500,
                "due_date": datetime(2026, 4, 20, tzinfo=timezone.utc),
            }
        ],
        created_by="planner@example.com",
    )

    assert (
        activities.documents[-1]["activity_type"]
        == VendorContractActivityType.MILESTONES_CREATED.value
    )

    await service.record_payment(
        milestone_id=created[0]["_id"],
        amount=1200,
        payment_method="bank_transfer",
        created_by="planner@example.com",
        notes="Wire received",
    )

    assert (
        activities.documents[-1]["activity_type"]
        == VendorContractActivityType.PAYMENT_RECORDED.value
    )
    assert activities.documents[-1]["metadata"]["amount"] == 1200
    assert milestones.documents[0]["paid_amount"] == 1200


@pytest.mark.asyncio
async def test_create_payment_milestones_rejects_historical_contract_versions(
    configured_vendor_service,
) -> None:
    (
        service,
        contracts,
        activities,
        milestones,
        _,
        _,
        vendor_profile_id,
    ) = configured_vendor_service
    contract = make_contract_doc(
        status=ContractStatus.SIGNED.value,
        is_current_version=False,
    )
    contract["vendor_profile_id"] = vendor_profile_id
    contracts.documents.append(deepcopy(contract))

    with pytest.raises(HTTPException) as exc_info:
        await service.create_payment_milestones(
            contract_id=str(contract["_id"]),
            milestones=[
                {
                    "description": "Final payment",
                    "amount": 2500,
                    "due_date": datetime(2026, 4, 25, tzinfo=timezone.utc),
                }
            ],
            created_by="planner@example.com",
        )

    assert exc_info.value.status_code == 409
    assert "historical contract version" in exc_info.value.detail
    assert milestones.documents == []
    assert activities.documents == []


@pytest.mark.asyncio
async def test_record_payment_rejects_historical_contract_versions(
    configured_vendor_service,
) -> None:
    (
        service,
        contracts,
        activities,
        milestones,
        assignments,
        budget_categories,
        vendor_profile_id,
    ) = configured_vendor_service
    contract = make_contract_doc(
        status=ContractStatus.SIGNED.value,
        is_current_version=False,
    )
    contract["vendor_profile_id"] = vendor_profile_id
    contract["budget_category_id"] = str(ObjectId())
    contracts.documents.append(deepcopy(contract))
    assignments.documents.append(
        {
            "_id": ObjectId(),
            "vendor_profile_id": "vendor-1",
            "wedding_id": "wedding-1",
            "paid_amount": 0,
        }
    )
    budget_categories.documents.append(
        {
            "_id": ObjectId(contract["budget_category_id"]),
            "actual_spent": 0,
        }
    )
    milestones.documents.append(
        {
            "_id": ObjectId(),
            "contract_id": str(contract["_id"]),
            "wedding_id": contract["wedding_id"],
            "vendor_profile_id": contract["vendor_profile_id"],
            "budget_category_id": contract["budget_category_id"],
            "description": "Final payment",
            "amount": 2500,
            "currency": "USD",
            "status": "pending",
            "paid_amount": 0,
            "vendor_name": contract["vendor_name"],
            "vendor_email": contract["vendor_email"],
            "created_by": "planner@example.com",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.record_payment(
            milestone_id=str(milestones.documents[0]["_id"]),
            amount=1200,
            payment_method="bank_transfer",
            created_by="planner@example.com",
        )

    assert exc_info.value.status_code == 409
    assert "historical contract version" in exc_info.value.detail
    assert milestones.documents[0]["paid_amount"] == 0
    assert assignments.documents[0]["paid_amount"] == 0
    assert budget_categories.documents[0]["actual_spent"] == 0
    assert activities.documents == []


@pytest.mark.asyncio
async def test_create_revision_logs_revision_created(configured_vendor_service) -> None:
    service, contracts, activities, _, _, _, _ = configured_vendor_service
    contract = make_contract_doc(status=ContractStatus.SENT.value)
    contracts.documents.append(deepcopy(contract))

    created = await service.create_contract_revision(
        contract_id=str(contract["_id"]),
        created_by="planner@example.com",
        revision_kind=ContractKind.REVISION.value,
        reason="Adjusted coverage",
    )

    assert (
        activities.documents[-1]["activity_type"]
        == VendorContractActivityType.REVISION_CREATED.value
    )
    assert activities.documents[-1]["contract_id"] == created["_id"]


@pytest.mark.asyncio
async def test_get_contract_activity_returns_descending_items_and_synthesizes_legacy_entries(
    configured_vendor_service,
) -> None:
    service, contracts, activities, _, _, _, _ = configured_vendor_service
    contract = make_contract_doc(
        status=ContractStatus.SIGNED.value,
        created_at=datetime(2026, 4, 8, 10, tzinfo=timezone.utc),
    )
    contract["updated_at"] = datetime(2026, 4, 8, 11, tzinfo=timezone.utc)
    contract["sent_at"] = datetime(2026, 4, 8, 12, tzinfo=timezone.utc)
    contract["viewed_at"] = datetime(2026, 4, 8, 14, tzinfo=timezone.utc)
    contract["signed_at"] = datetime(2026, 4, 8, 16, tzinfo=timezone.utc)
    contracts.documents.append(deepcopy(contract))

    response = await service.get_contract_activity(
        contract_id=str(contract["_id"]),
        created_by="planner@example.com",
    )

    assert (
        response["items"][0]["activity_type"]
        == VendorContractActivityType.CONTRACT_SIGNED.value
    )
    assert any(
        item["activity_type"] == VendorContractActivityType.CONTRACT_CREATED.value
        for item in response["items"]
    )

    await service._log_contract_activity(
        contract_id=str(contract["_id"]),
        root_contract_id=str(contract["_id"]),
        activity_type=VendorContractActivityType.CONTRACT_UPDATED,
        title="Contract updated",
        description=None,
        actor_type="planner",
        actor_identifier="planner@example.com",
        actor_display_name="planner@example.com",
        created_at=datetime(2026, 4, 9, 10, tzinfo=timezone.utc),
    )

    explicit_response = await service.get_contract_activity(
        contract_id=str(contract["_id"]),
        created_by="planner@example.com",
    )

    assert (
        explicit_response["items"][0]["activity_type"]
        == VendorContractActivityType.CONTRACT_UPDATED.value
    )
    assert any(
        item["activity_type"] == VendorContractActivityType.CONTRACT_SIGNED.value
        for item in explicit_response["items"]
    )


@pytest.mark.asyncio
async def test_get_contract_activity_is_contract_scoped_not_lineage_scoped(
    configured_vendor_service,
) -> None:
    service, contracts, activities, _, _, _, _ = configured_vendor_service
    root_id = ObjectId()
    contract_a = make_contract_doc(
        contract_id=root_id,
        root_contract_id=str(root_id),
        status=ContractStatus.SIGNED.value,
    )
    contract_b = make_contract_doc(
        contract_id=ObjectId(),
        root_contract_id=str(root_id),
        parent_contract_id=str(root_id),
        supersedes_contract_id=str(root_id),
        contract_kind=ContractKind.REVISION.value,
        status=ContractStatus.SENT.value,
        is_current_version=True,
    )
    contract_b["version_number"] = 2
    contracts.documents.extend([deepcopy(contract_a), deepcopy(contract_b)])

    await service._log_contract_activity(
        contract_id=str(contract_a["_id"]),
        root_contract_id=str(root_id),
        activity_type=VendorContractActivityType.CONTRACT_UPDATED,
        title="Original updated",
        description=None,
        actor_type="planner",
        actor_identifier="planner@example.com",
        actor_display_name="planner@example.com",
        created_at=datetime(2026, 4, 9, 10, tzinfo=timezone.utc),
    )
    await service._log_contract_activity(
        contract_id=str(contract_b["_id"]),
        root_contract_id=str(root_id),
        activity_type=VendorContractActivityType.CONTRACT_SENT,
        title="Revision sent",
        description=None,
        actor_type="planner",
        actor_identifier="planner@example.com",
        actor_display_name="planner@example.com",
        created_at=datetime(2026, 4, 10, 10, tzinfo=timezone.utc),
    )

    response = await service.get_contract_activity(
        contract_id=str(contract_a["_id"]),
        created_by="planner@example.com",
    )

    assert all(
        item["contract_id"] == str(contract_a["_id"]) for item in response["items"]
    )
    assert not any(item["title"] == "Revision sent" for item in response["items"])


@pytest.mark.asyncio
async def test_explicit_activity_dedupes_matching_synthesized_event_types(
    configured_vendor_service,
) -> None:
    service, contracts, _, _, _, _, _ = configured_vendor_service
    contract = make_contract_doc(
        status=ContractStatus.SIGNED.value,
        created_at=datetime(2026, 4, 8, 10, tzinfo=timezone.utc),
    )
    contract["sent_at"] = datetime(2026, 4, 8, 12, tzinfo=timezone.utc)
    contract["signed_at"] = datetime(2026, 4, 8, 16, tzinfo=timezone.utc)
    contracts.documents.append(deepcopy(contract))

    await service._log_contract_activity(
        contract_id=str(contract["_id"]),
        root_contract_id=str(contract["_id"]),
        activity_type=VendorContractActivityType.CONTRACT_SIGNED,
        title="Contract signed",
        description="Explicit audit event",
        actor_type="vendor",
        actor_identifier="vendor@example.com",
        actor_display_name="Vendor",
        created_at=datetime(2026, 4, 8, 16, tzinfo=timezone.utc),
    )

    response = await service.get_contract_activity(
        contract_id=str(contract["_id"]),
        created_by="planner@example.com",
    )

    signed_items = [
        item
        for item in response["items"]
        if item["activity_type"] == VendorContractActivityType.CONTRACT_SIGNED.value
    ]
    assert len(signed_items) == 1


@pytest.mark.asyncio
async def test_get_payment_milestones_scopes_generic_queries_to_created_by(
    configured_vendor_service,
) -> None:
    service, _, _, milestones, _, _, _ = configured_vendor_service
    milestones.documents.extend(
        [
            {
                "_id": ObjectId(),
                "contract_id": "contract-1",
                "created_by": "planner@example.com",
                "status": "pending",
                "due_date": datetime(2026, 4, 20, tzinfo=timezone.utc),
                "amount": 100,
                "paid_amount": 0,
            },
            {
                "_id": ObjectId(),
                "contract_id": "contract-2",
                "created_by": "other@example.com",
                "status": "pending",
                "due_date": datetime(2026, 4, 22, tzinfo=timezone.utc),
                "amount": 100,
                "paid_amount": 0,
            },
        ]
    )

    result = await service.get_payment_milestones(created_by="planner@example.com")

    assert len(result) == 1
    assert result[0]["contract_id"] == "contract-1"

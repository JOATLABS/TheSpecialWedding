from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.models.vendor import ContractKind, ContractStatus
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
            return False

        if actual != expected:
            return False

    return True


class FakeCursor:
    def __init__(self, documents: list[dict]):
        self._documents = documents

    async def to_list(self, length: int | None = None) -> list[dict]:
        if length is None:
            return deepcopy(self._documents)
        return deepcopy(self._documents[:length])


class FakeCollection:
    def __init__(self, documents: list[dict] | None = None):
        self.documents = documents or []

    async def insert_one(self, document: dict) -> SimpleNamespace:
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def find_one(self, query: dict) -> dict | None:
        for document in self.documents:
            if _matches_query(document, query):
                return deepcopy(document)
        return None

    async def update_one(self, query: dict, update: dict) -> SimpleNamespace:
        for document in self.documents:
            if _matches_query(document, query):
                for key, value in update.get("$set", {}).items():
                    document[key] = deepcopy(value)
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    def find(self, query: dict) -> FakeCursor:
        return FakeCursor(
            [deepcopy(document) for document in self.documents if _matches_query(document, query)]
        )


class DummyEmailService:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_email(self, **kwargs) -> dict:
        self.sent.append(kwargs)
        return {"success": True, "id": "email_123"}


def make_contract_doc(
    *,
    contract_id: ObjectId | None = None,
    root_contract_id: str | None = None,
    parent_contract_id: str | None = None,
    supersedes_contract_id: str | None = None,
    superseded_by_contract_id: str | None = None,
    version_number: int = 1,
    contract_kind: str = ContractKind.ORIGINAL.value,
    status: str = ContractStatus.SENT.value,
    is_current_version: bool = True,
    access_token: str = "token-1",
    created_at: datetime | None = None,
    sent_at: datetime | None = None,
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
        "access_token": access_token,
        "token_expires_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "created_by": "planner@example.com",
        "created_at": now,
        "updated_at": now,
        "version_number": version_number,
        "root_contract_id": root_contract_id or str(object_id),
        "parent_contract_id": parent_contract_id,
        "supersedes_contract_id": supersedes_contract_id,
        "superseded_by_contract_id": superseded_by_contract_id,
        "is_current_version": is_current_version,
        "contract_kind": contract_kind,
        "amendment_reason": None,
        "superseded_at": None,
        "sent_at": sent_at,
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
    assignments = FakeCollection([])
    templates = FakeCollection([])
    quotes = FakeCollection([])

    monkeypatch.setattr(vendor_service, "vendor_contracts", contracts)
    monkeypatch.setattr(vendor_service, "vendor_contract_activities", activities)
    monkeypatch.setattr(vendor_service, "vendor_assignments", assignments)
    monkeypatch.setattr(vendor_service, "contract_templates", templates)
    monkeypatch.setattr(vendor_service, "vendor_quotes", quotes)
    monkeypatch.setattr(
        vendor_service,
        "vendor_profiles",
        FakeCollection(
            [
                {
                    "_id": vendor_id,
                    "business_name": "Vendor Co",
                    "email": "vendor@example.com",
                    "phone": "555-1234",
                    "address": "123 Main St",
                    "service_category": "photographer",
                }
            ]
        ),
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
    monkeypatch.setattr(vendor_service, "_log_communication", AsyncMock())
    vendor_service.email_service = DummyEmailService()

    return vendor_service, contracts, assignments, str(vendor_id)


@pytest.mark.asyncio
async def test_create_contract_initializes_version_metadata(configured_vendor_service) -> None:
    service, contracts, _, vendor_profile_id = configured_vendor_service

    created = await service.create_contract(
        wedding_id="wedding-1",
        vendor_profile_id=vendor_profile_id,
        created_by="planner@example.com",
        total_amount=5000,
        deposit_percentage=50,
    )

    stored = contracts.documents[0]
    assert created["version_number"] == 1
    assert created["is_current_version"] is True
    assert created["contract_kind"] == ContractKind.ORIGINAL.value
    assert created["root_contract_id"] == created["_id"]
    assert stored["root_contract_id"] == str(stored["_id"])
    assert stored["parent_contract_id"] is None
    assert stored["supersedes_contract_id"] is None


@pytest.mark.asyncio
async def test_create_revision_from_sent_contract_creates_new_draft_child_version(
    configured_vendor_service,
) -> None:
    service, contracts, _, _ = configured_vendor_service
    original = make_contract_doc(status=ContractStatus.SENT.value)
    contracts.documents.append(deepcopy(original))

    created = await service.create_contract_revision(
        contract_id=str(original["_id"]),
        created_by="planner@example.com",
        revision_kind=ContractKind.REVISION.value,
        reason="Updated scope",
    )

    assert created["status"] == ContractStatus.DRAFT.value
    assert created["contract_kind"] == ContractKind.REVISION.value
    assert created["version_number"] == 2
    assert created["root_contract_id"] == str(original["_id"])
    assert created["parent_contract_id"] == str(original["_id"])
    assert created["supersedes_contract_id"] == str(original["_id"])
    assert created["is_current_version"] is False

    stored_original = contracts.documents[0]
    assert stored_original["is_current_version"] is True
    assert stored_original["superseded_by_contract_id"] is None


@pytest.mark.asyncio
async def test_create_amendment_from_signed_contract_creates_new_draft_child_version(
    configured_vendor_service,
) -> None:
    service, contracts, _, _ = configured_vendor_service
    original = make_contract_doc(status=ContractStatus.SIGNED.value)
    contracts.documents.append(deepcopy(original))

    created = await service.create_contract_revision(
        contract_id=str(original["_id"]),
        created_by="planner@example.com",
        revision_kind=ContractKind.AMENDMENT.value,
        reason="Signed change order",
    )

    assert created["status"] == ContractStatus.DRAFT.value
    assert created["contract_kind"] == ContractKind.AMENDMENT.value
    assert created["amendment_reason"] == "Signed change order"
    assert created["version_number"] == 2


@pytest.mark.asyncio
async def test_create_revision_rejects_non_current_source_contract(
    configured_vendor_service,
) -> None:
    service, contracts, _, _ = configured_vendor_service
    historical = make_contract_doc(
        status=ContractStatus.SIGNED.value,
        is_current_version=False,
        superseded_by_contract_id=str(ObjectId()),
    )
    contracts.documents.append(deepcopy(historical))

    with pytest.raises(HTTPException) as exc_info:
        await service.create_contract_revision(
            contract_id=str(historical["_id"]),
            created_by="planner@example.com",
            revision_kind=ContractKind.REVISION.value,
        )

    assert exc_info.value.status_code == 400
    assert "historical contract version" in exc_info.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("revision_kind", "source_status"),
    [
        (ContractKind.REVISION.value, ContractStatus.SENT.value),
        (ContractKind.AMENDMENT.value, ContractStatus.SIGNED.value),
    ],
)
async def test_sending_child_version_supersedes_previous_current_and_keeps_single_current(
    configured_vendor_service,
    revision_kind: str,
    source_status: str,
) -> None:
    service, contracts, _, _ = configured_vendor_service
    original = make_contract_doc(status=source_status, access_token="old-token")
    child = make_contract_doc(
        status=ContractStatus.DRAFT.value,
        contract_id=ObjectId(),
        root_contract_id=str(original["_id"]),
        parent_contract_id=str(original["_id"]),
        supersedes_contract_id=str(original["_id"]),
        version_number=2,
        contract_kind=revision_kind,
        is_current_version=False,
        access_token="new-token",
    )
    contracts.documents.extend([deepcopy(original), deepcopy(child)])

    result = await service.send_contract(
        contract_id=str(child["_id"]),
        created_by="planner@example.com",
        message="Please review",
    )

    assert result["sent_to"] == "vendor@example.com"

    stored_original = next(doc for doc in contracts.documents if doc["_id"] == original["_id"])
    stored_child = next(doc for doc in contracts.documents if doc["_id"] == child["_id"])

    assert stored_original["is_current_version"] is False
    assert stored_original["superseded_by_contract_id"] == str(child["_id"])
    assert stored_child["is_current_version"] is True
    assert stored_child["status"] == ContractStatus.SENT.value
    assert sum(1 for doc in contracts.documents if doc.get("is_current_version")) == 1


@pytest.mark.asyncio
async def test_send_contract_rejects_stale_revision_supersede_target(
    configured_vendor_service,
) -> None:
    service, contracts, _, _ = configured_vendor_service
    original = make_contract_doc(
        status=ContractStatus.SIGNED.value,
        is_current_version=False,
        superseded_by_contract_id=str(ObjectId()),
    )
    stale_revision = make_contract_doc(
        status=ContractStatus.DRAFT.value,
        contract_id=ObjectId(),
        root_contract_id=str(original["_id"]),
        parent_contract_id=str(original["_id"]),
        supersedes_contract_id=str(original["_id"]),
        version_number=2,
        contract_kind=ContractKind.REVISION.value,
        is_current_version=False,
        access_token="revision-token",
    )
    contracts.documents.extend([deepcopy(original), deepcopy(stale_revision)])

    with pytest.raises(HTTPException) as exc_info:
        await service.send_contract(
            contract_id=str(stale_revision["_id"]),
            created_by="planner@example.com",
            message="Please review",
        )

    assert exc_info.value.status_code == 409
    assert "outdated contract version" in exc_info.value.detail


@pytest.mark.asyncio
async def test_superseded_contract_token_cannot_be_viewed_or_signed(
    configured_vendor_service,
) -> None:
    service, contracts, _, _ = configured_vendor_service
    superseded = make_contract_doc(
        status=ContractStatus.SIGNED.value,
        is_current_version=False,
        access_token="old-token",
        superseded_by_contract_id=str(ObjectId()),
    )
    contracts.documents.append(deepcopy(superseded))

    with pytest.raises(HTTPException) as view_error:
        await service.get_contract_by_token(str(superseded["_id"]), "old-token")
    assert view_error.value.status_code == 410

    with pytest.raises(HTTPException) as sign_error:
        await service.sign_contract(
            contract_id=str(superseded["_id"]),
            token="old-token",
            signer_name="Vendor Co",
            signer_email="vendor@example.com",
        )
    assert sign_error.value.status_code == 410


@pytest.mark.asyncio
async def test_current_contract_token_can_still_be_viewed_and_signed(
    configured_vendor_service,
) -> None:
    service, contracts, assignments, _ = configured_vendor_service
    current = make_contract_doc(
        status=ContractStatus.SENT.value,
        is_current_version=True,
        access_token="current-token",
    )
    assignments.documents.append(
        {
            "_id": ObjectId(),
            "vendor_profile_id": "vendor-1",
            "wedding_id": "wedding-1",
            "status": "quoted",
        }
    )
    contracts.documents.append(deepcopy(current))

    viewed = await service.get_contract_by_token(str(current["_id"]), "current-token")
    assert viewed["status"] == ContractStatus.VIEWED.value

    signed = await service.sign_contract(
        contract_id=str(current["_id"]),
        token="current-token",
        signer_name="Vendor Co",
        signer_email="vendor@example.com",
    )
    assert signed["message"] == "Contract signed successfully"

    stored_current = next(doc for doc in contracts.documents if doc["_id"] == current["_id"])
    assert stored_current["status"] == ContractStatus.SIGNED.value


@pytest.mark.asyncio
async def test_revision_history_returns_ordered_lineage(configured_vendor_service) -> None:
    service, contracts, _, _ = configured_vendor_service
    root_id = ObjectId()
    contracts.documents.extend(
        [
            make_contract_doc(
                contract_id=root_id,
                root_contract_id=str(root_id),
                version_number=1,
                contract_kind=ContractKind.ORIGINAL.value,
                status=ContractStatus.SIGNED.value,
                is_current_version=False,
                superseded_by_contract_id="contract-v2",
                created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            ),
            make_contract_doc(
                contract_id=ObjectId(),
                root_contract_id=str(root_id),
                parent_contract_id=str(root_id),
                supersedes_contract_id=str(root_id),
                version_number=2,
                contract_kind=ContractKind.REVISION.value,
                status=ContractStatus.SIGNED.value,
                is_current_version=False,
                superseded_by_contract_id="contract-v3",
                created_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
            ),
            make_contract_doc(
                contract_id=ObjectId(),
                root_contract_id=str(root_id),
                parent_contract_id=str(root_id),
                supersedes_contract_id=str(root_id),
                version_number=3,
                contract_kind=ContractKind.AMENDMENT.value,
                status=ContractStatus.SENT.value,
                is_current_version=True,
                created_at=datetime(2026, 4, 3, tzinfo=timezone.utc),
            ),
        ]
    )

    history = await service.get_contract_revision_history(
        contract_id=str(root_id),
        created_by="planner@example.com",
    )

    assert history["root_contract_id"] == str(root_id)
    assert [version["version_number"] for version in history["versions"]] == [1, 2, 3]
    assert history["current_contract_id"] == history["versions"][2]["id"]

from __future__ import annotations

import importlib.util
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.models.vendor import ContractKind, ContractStatus
from app.services.vendor_service import vendor_service


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


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

    async def update_one(self, query: dict, update: dict, session=None) -> SimpleNamespace:
        for document in self.documents:
            if _matches_query(document, query):
                for key, value in update.get("$set", {}).items():
                    document[key] = deepcopy(value)
                for key, value in update.get("$inc", {}).items():
                    document[key] = document.get(key, 0) + value
                for key in update.get("$unset", {}):
                    document.pop(key, None)
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
    status: str = ContractStatus.SENT.value,
    access_token: str = "token-1",
    is_current_version: bool = True,
    token_expires_at: datetime | None = None,
    token_revoked_at: datetime | None = None,
) -> dict:
    object_id = contract_id or ObjectId()
    now = datetime.now(timezone.utc)
    return {
        "_id": object_id,
        "wedding_id": "wedding-1",
        "vendor_profile_id": "vendor-1",
        "budget_category_id": str(ObjectId()),
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
        "token_expires_at": token_expires_at or datetime(2026, 5, 1, tzinfo=timezone.utc),
        "token_revoked_at": token_revoked_at,
        "token_last_sent_at": None,
        "token_last_viewed_at": None,
        "created_by": "planner@example.com",
        "created_at": now,
        "updated_at": now,
        "version_number": 1,
        "root_contract_id": str(object_id),
        "parent_contract_id": None,
        "supersedes_contract_id": None,
        "superseded_by_contract_id": None,
        "is_current_version": is_current_version,
        "contract_kind": ContractKind.ORIGINAL.value,
        "amendment_reason": None,
        "superseded_at": None,
        "sent_at": now if status == ContractStatus.SENT.value else None,
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
            }
        ]
    )

    monkeypatch.setattr(vendor_service, "vendor_contracts", contracts)
    monkeypatch.setattr(vendor_service, "vendor_contract_activities", activities)
    monkeypatch.setattr(vendor_service, "payment_milestones", milestones)
    monkeypatch.setattr(vendor_service, "vendor_assignments", assignments)
    monkeypatch.setattr(vendor_service, "budget_categories", budget_categories)
    monkeypatch.setattr(vendor_service, "vendor_profiles", vendor_profiles)
    monkeypatch.setattr(vendor_service, "_log_communication", AsyncMock())
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

    async def run_required_transaction(_operation_name, operation):
        return await operation(None)

    monkeypatch.setattr(vendor_service, "_run_required_transaction", run_required_transaction)
    vendor_service.email_service = DummyEmailService()

    return {
        "service": vendor_service,
        "contracts": contracts,
        "activities": activities,
        "milestones": milestones,
        "assignments": assignments,
        "budget_categories": budget_categories,
        "vendor_profiles": vendor_profiles,
        "vendor_profile_id": str(vendor_id),
        "email_service": vendor_service.email_service,
    }


def _load_backfill_module():
    script_path = ROOT / "scripts" / "backfill_vendor_contract_security_fields.py"
    spec = importlib.util.spec_from_file_location("vendor_contract_security_backfill", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_create_contract_initializes_inactive_token_fields(configured_vendor_service) -> None:
    context = configured_vendor_service
    service = context["service"]

    created = await service.create_contract(
        wedding_id="wedding-1",
        vendor_profile_id=context["vendor_profile_id"],
        created_by="planner@example.com",
        total_amount=5000,
        deposit_percentage=50,
    )

    stored = context["contracts"].documents[0]
    assert created["access_token_hash"] is None
    assert created["token_expires_at"] is None
    assert created["token_revoked_at"] is None
    assert created["token_last_sent_at"] is None
    assert created["token_last_viewed_at"] is None
    assert "access_token" not in stored


@pytest.mark.asyncio
async def test_send_contract_persists_only_hash_and_public_validation_uses_raw_email_token(
    configured_vendor_service,
) -> None:
    context = configured_vendor_service
    service = context["service"]
    contract = make_contract_doc(status=ContractStatus.DRAFT.value, access_token="legacy-token")
    contract["access_token_hash"] = None
    contract["token_expires_at"] = None
    context["contracts"].documents.append(deepcopy(contract))

    await service.send_contract(
        contract_id=str(contract["_id"]),
        created_by="planner@example.com",
    )

    stored = context["contracts"].documents[0]
    email = context["email_service"].sent[0]
    match = re.search(
        rf"/vendor-contract/{stored['_id']}/([^\"<]+)",
        email["html_content"],
    )
    assert match, "expected sent email to contain canonical vendor contract link"
    raw_token = match.group(1)

    assert stored["access_token_hash"] == service._hash_contract_access_token(raw_token)
    assert stored["token_last_sent_at"] is not None
    assert stored["token_revoked_at"] is None
    assert "access_token" not in stored

    viewed = await service.get_contract_by_token(str(stored["_id"]), raw_token)
    assert viewed["status"] == ContractStatus.VIEWED.value
    assert "access_token_hash" not in viewed
    assert context["contracts"].documents[0]["token_last_viewed_at"] is not None


@pytest.mark.asyncio
async def test_invalid_revoked_and_expired_tokens_are_rejected(
    configured_vendor_service,
) -> None:
    context = configured_vendor_service
    service = context["service"]

    valid = make_contract_doc(access_token="valid-token")
    revoked = make_contract_doc(
        contract_id=ObjectId(),
        access_token="revoked-token",
        token_revoked_at=datetime.now(timezone.utc),
    )
    expired = make_contract_doc(
        contract_id=ObjectId(),
        access_token="expired-token",
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    context["contracts"].documents.extend([deepcopy(valid), deepcopy(revoked), deepcopy(expired)])

    with pytest.raises(HTTPException) as invalid_error:
        await service.get_contract_by_token(str(valid["_id"]), "wrong-token")
    assert invalid_error.value.status_code == 404

    with pytest.raises(HTTPException) as revoked_error:
        await service.get_contract_by_token(str(revoked["_id"]), "revoked-token")
    assert revoked_error.value.status_code == 403

    with pytest.raises(HTTPException) as expired_error:
        await service.get_contract_by_token(str(expired["_id"]), "expired-token")
    assert expired_error.value.status_code == 403


@pytest.mark.asyncio
async def test_public_view_does_not_downgrade_signed_contract_status(
    configured_vendor_service,
) -> None:
    context = configured_vendor_service
    service = context["service"]
    contract = make_contract_doc(access_token="signed-token")
    context["contracts"].documents.append(deepcopy(contract))
    context["assignments"].documents.append(
        {
            "_id": ObjectId(),
            "vendor_profile_id": "vendor-1",
            "wedding_id": "wedding-1",
            "status": "quoted",
        }
    )

    await service.sign_contract(
        contract_id=str(contract["_id"]),
        token="signed-token",
        signer_name="Vendor Owner",
        signer_email="vendor@example.com",
    )
    viewed = await service.get_contract_by_token(str(contract["_id"]), "signed-token")

    assert viewed["status"] == ContractStatus.SIGNED.value
    assert context["contracts"].documents[0]["status"] == ContractStatus.SIGNED.value


@pytest.mark.asyncio
async def test_sign_contract_rolls_back_on_transaction_failure(configured_vendor_service, monkeypatch) -> None:
    context = configured_vendor_service
    service = context["service"]
    contract = make_contract_doc(access_token="sign-token")
    context["contracts"].documents.append(deepcopy(contract))
    context["assignments"].documents.append(
        {
            "_id": ObjectId(),
            "vendor_profile_id": "vendor-1",
            "wedding_id": "wedding-1",
            "status": "quoted",
        }
    )

    async def transactional_runner(_operation_name, operation):
        contracts_snapshot = deepcopy(context["contracts"].documents)
        assignments_snapshot = deepcopy(context["assignments"].documents)
        try:
            return await operation(None)
        except Exception:
            context["contracts"].documents = contracts_snapshot
            context["assignments"].documents = assignments_snapshot
            raise

    monkeypatch.setattr(vendor_service, "_run_required_transaction", transactional_runner)

    original_update_one = context["assignments"].update_one

    async def failing_assignment_update(query, update, session=None):
        raise RuntimeError("assignment failure")

    monkeypatch.setattr(context["assignments"], "update_one", failing_assignment_update)

    with pytest.raises(HTTPException) as exc_info:
        await service.sign_contract(
            contract_id=str(contract["_id"]),
            token="sign-token",
            signer_name="Vendor Signer",
            signer_email="vendor@example.com",
        )

    assert exc_info.value.status_code == 500
    assert context["contracts"].documents[0]["status"] == ContractStatus.SENT.value
    assert context["assignments"].documents[0]["status"] == "quoted"
    monkeypatch.setattr(context["assignments"], "update_one", original_update_one)


@pytest.mark.asyncio
async def test_record_payment_rolls_back_on_transaction_failure(configured_vendor_service, monkeypatch) -> None:
    context = configured_vendor_service
    service = context["service"]
    contract = make_contract_doc(access_token="pay-token")
    context["contracts"].documents.append(deepcopy(contract))
    context["assignments"].documents.append(
        {
            "_id": ObjectId(),
            "vendor_profile_id": "vendor-1",
            "wedding_id": "wedding-1",
            "paid_amount": 0,
        }
    )
    context["budget_categories"].documents.append(
        {"_id": ObjectId(contract["budget_category_id"]), "actual_spent": 0}
    )
    context["milestones"].documents.append(
        {
            "_id": ObjectId(),
            "contract_id": str(contract["_id"]),
            "wedding_id": contract["wedding_id"],
            "vendor_profile_id": contract["vendor_profile_id"],
            "budget_category_id": contract["budget_category_id"],
            "description": "Deposit",
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

    async def transactional_runner(_operation_name, operation):
        milestone_snapshot = deepcopy(context["milestones"].documents)
        assignment_snapshot = deepcopy(context["assignments"].documents)
        vendor_snapshot = deepcopy(context["vendor_profiles"].documents)
        budget_snapshot = deepcopy(context["budget_categories"].documents)
        try:
            return await operation(None)
        except Exception:
            context["milestones"].documents = milestone_snapshot
            context["assignments"].documents = assignment_snapshot
            context["vendor_profiles"].documents = vendor_snapshot
            context["budget_categories"].documents = budget_snapshot
            raise

    monkeypatch.setattr(vendor_service, "_run_required_transaction", transactional_runner)

    async def failing_vendor_update(query, update, session=None):
        raise RuntimeError("vendor revenue failure")

    monkeypatch.setattr(context["vendor_profiles"], "update_one", failing_vendor_update)

    with pytest.raises(HTTPException) as exc_info:
        await service.record_payment(
            milestone_id=str(context["milestones"].documents[0]["_id"]),
            amount=1200,
            payment_method="bank_transfer",
            created_by="planner@example.com",
        )

    assert exc_info.value.status_code == 500
    assert context["milestones"].documents[0]["paid_amount"] == 0
    assert context["assignments"].documents[0]["paid_amount"] == 0
    assert context["budget_categories"].documents[0]["actual_spent"] == 0


def test_query_token_public_routes_are_removed_and_canonical_routes_remain() -> None:
    source = _read("app/api/vendor_contract_public.py")
    assert '/public/contracts/{contract_id}/{token}' in source
    assert '/public/contracts/{contract_id}/{token}/sign' in source
    assert '/public/contracts/{contract_id}",' not in source
    assert '/public/contracts/{contract_id}/sign' not in source
    assert "Query(" not in source


def test_vendor_contract_security_indexes_are_declared() -> None:
    source = _read("app/core/database_indexes.py")
    assert "idx_vendor_contract_access_token_hash" in source
    assert "idx_vendor_contract_root_version_unique" in source
    assert "idx_vendor_contract_single_current_version" in source
    assert 'partialFilterExpression={"is_current_version": True}' in source
    assert "idx_vendor_payment_milestones_contract_status_due" in source


def test_backfill_helper_hashes_plaintext_vendor_contract_tokens() -> None:
    backfill_module = _load_backfill_module()
    document = {
        "_id": ObjectId(),
        "access_token": "legacy-token",
        "sent_at": datetime(2026, 4, 8, 12, tzinfo=timezone.utc),
        "viewed_at": datetime(2026, 4, 8, 14, tzinfo=timezone.utc),
    }

    set_updates, unset_updates = backfill_module.build_vendor_contract_security_backfill_ops(
        document,
        drop_plaintext_token=True,
    )

    assert set_updates["access_token_hash"] == vendor_service._hash_contract_access_token(
        "legacy-token"
    )
    assert set_updates["token_last_sent_at"] == document["sent_at"]
    assert set_updates["token_last_viewed_at"] == document["viewed_at"]
    assert unset_updates == {"access_token": ""}

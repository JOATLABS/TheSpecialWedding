from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.vendor import (
    ContractStatus,
    ContractType,
    VendorCategory,
    VendorContract,
)
from app.services.vendor_service import VendorService


class _DummyInsertResult:
    inserted_id = "vendor_123"


class _DummyVendorCollection:
    def __init__(self):
        self.inserted_docs = []

    async def insert_one(self, doc):
        self.inserted_docs.append(doc.copy())
        return _DummyInsertResult()


class _DummyFindOneCollection:
    def __init__(self, result):
        self.result = result

    async def find_one(self, query):
        return self.result


class _DummyCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *_args):
        return self

    def limit(self, value):
        self.docs = self.docs[:value]
        return self

    async def to_list(self, length=None):
        return list(self.docs if length is None else self.docs[:length])


class _DummyFindCollection:
    def __init__(self, docs):
        self.docs = docs
        self.last_query = None

    def find(self, query):
        self.last_query = query
        matched = []
        for doc in self.docs:
            if self._matches(doc, query):
                matched.append(doc.copy())
        return _DummyCursor(matched)

    @staticmethod
    def _matches(doc, query):
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                continue
            if actual != expected:
                return False
        return True


@pytest.mark.asyncio
async def test_create_vendor_profile_omits_empty_google_place_id():
    service = VendorService.__new__(VendorService)
    service.vendor_profiles = _DummyVendorCollection()

    payload = {
        "business_name": "Lens & Light",
        "email": "vendor@example.com",
        "service_category": "photographer",
        "google_place_id": None,
    }

    result = await service.create_vendor_profile(payload, "planner@example.com")

    inserted_doc = service.vendor_profiles.inserted_docs[0]
    assert "google_place_id" not in inserted_doc
    assert result["_id"] == "vendor_123"


@pytest.mark.asyncio
async def test_create_vendor_profile_trims_non_empty_google_place_id():
    service = VendorService.__new__(VendorService)
    service.vendor_profiles = _DummyVendorCollection()

    payload = {
        "business_name": "Lens & Light",
        "email": "vendor@example.com",
        "service_category": "photographer",
        "google_place_id": "  place_123  ",
    }

    result = await service.create_vendor_profile(payload, "planner@example.com")

    inserted_doc = service.vendor_profiles.inserted_docs[0]
    assert inserted_doc["google_place_id"] == "place_123"
    assert result["_id"] == "vendor_123"


@pytest.mark.asyncio
async def test_assign_vendor_to_wedding_returns_conflict_for_duplicates():
    vendor_id = "507f1f77bcf86cd799439011"
    service = VendorService.__new__(VendorService)
    service.vendor_profiles = _DummyFindOneCollection(
        {
            "_id": vendor_id,
            "business_name": "Lens & Light",
            "email": "vendor@example.com",
            "service_category": "photographer",
        }
    )
    service.weddings = _DummyFindOneCollection(
        {
            "_id": "wedding_123",
            "assigned_planner_email": "planner@example.com",
        }
    )
    service.vendor_assignments = _DummyFindOneCollection({"_id": "assignment_123"})

    with pytest.raises(HTTPException) as exc_info:
        await service.assign_vendor_to_wedding(
            vendor_profile_id=vendor_id,
            wedding_id="wedding_123",
            created_by="planner@example.com",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Vendor already assigned to this wedding"


@pytest.mark.asyncio
async def test_get_wedding_vendors_scopes_assignments_by_owner():
    service = VendorService.__new__(VendorService)
    service.vendor_assignments = _DummyFindCollection(
        [
            {
                "_id": "assignment-1",
                "wedding_id": "wedding_123",
                "created_by": "planner@example.com",
                "is_deleted": False,
            },
            {
                "_id": "assignment-2",
                "wedding_id": "wedding_123",
                "created_by": "other@example.com",
                "is_deleted": False,
            },
        ]
    )

    results = await service.get_wedding_vendors(
        "wedding_123",
        created_by="planner@example.com",
    )

    assert [item["_id"] for item in results] == ["assignment-1"]
    assert service.vendor_assignments.last_query["created_by"] == "planner@example.com"


def _build_contract_payload(**overrides) -> dict:
    """Minimal valid VendorContract payload for model-construction tests."""
    payload = {
        "wedding_id": "wedding_123",
        "vendor_name": "Lens & Light",
        "vendor_email": "vendor@example.com",
        "service_category": VendorCategory.PHOTOGRAPHER,
        "contract_title": "Photography Services Contract",
        "contract_type": ContractType.TEMPLATE,
        "total_amount": 1000.0,
        "status": ContractStatus.DRAFT,
        "created_by": "planner@example.com",
    }
    payload.update(overrides)
    return payload


def test_vendor_contract_validator_rejects_deposit_exceeding_total():
    """Deposit cannot exceed total — Pydantic must reject before persisting."""
    payload = _build_contract_payload(total_amount=500.0, deposit_amount=600.0)
    with pytest.raises(ValidationError) as exc_info:
        VendorContract(**payload)
    assert "deposit_amount cannot exceed total_amount" in str(exc_info.value)


def test_vendor_contract_validator_accepts_deposit_equal_to_total():
    """Deposit equal to total is legal (full pre-payment)."""
    payload = _build_contract_payload(total_amount=500.0, deposit_amount=500.0)
    contract = VendorContract(**payload)
    assert contract.deposit_amount == 500.0


def test_vendor_contract_validator_accepts_none_deposit():
    """Existing data with no deposit must continue to validate."""
    payload = _build_contract_payload(total_amount=500.0, deposit_amount=None)
    contract = VendorContract(**payload)
    assert contract.deposit_amount is None


def test_vendor_contract_validator_accepts_zero_deposit():
    """Zero-deposit contracts (the existing default for many flows) must pass."""
    payload = _build_contract_payload(total_amount=500.0, deposit_amount=0.0)
    contract = VendorContract(**payload)
    assert contract.deposit_amount == 0.0


@pytest.mark.asyncio
async def test_ensure_contract_editable_rejects_locked_contract():
    """Once contract_status_locked_at is set, edits must 409 even on DRAFT status."""
    service = VendorService.__new__(VendorService)
    locked_contract = {
        "_id": "contract_locked",
        "status": ContractStatus.DRAFT.value,
        "is_current_version": True,
        "contract_status_locked_at": datetime.now(timezone.utc),
        "created_by": "planner@example.com",
    }

    with pytest.raises(HTTPException) as exc_info:
        await service._ensure_contract_editable(locked_contract)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Contract is locked after signing"


@pytest.mark.asyncio
async def test_ensure_contract_editable_allows_unlocked_draft():
    """Without contract_status_locked_at, DRAFT contracts remain editable."""
    service = VendorService.__new__(VendorService)
    unlocked_contract = {
        "_id": "contract_unlocked",
        "status": ContractStatus.DRAFT.value,
        "is_current_version": True,
        "created_by": "planner@example.com",
    }

    # Should not raise.
    await service._ensure_contract_editable(unlocked_contract)


@pytest.mark.asyncio
async def test_get_vendor_communications_scopes_by_owner():
    service = VendorService.__new__(VendorService)
    service.vendor_communications = _DummyFindCollection(
        [
            {
                "_id": "comm-1",
                "vendor_profile_id": "vendor-1",
                "created_by": "planner@example.com",
            },
            {
                "_id": "comm-2",
                "vendor_profile_id": "vendor-1",
                "created_by": "other@example.com",
            },
        ]
    )

    results = await service.get_vendor_communications(
        "vendor-1",
        created_by="planner@example.com",
    )

    assert [item["_id"] for item in results] == ["comm-1"]
    assert (
        service.vendor_communications.last_query["created_by"] == "planner@example.com"
    )

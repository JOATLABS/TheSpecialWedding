import pytest
from fastapi import HTTPException

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
    service.vendor_assignments = _DummyFindOneCollection({"_id": "assignment_123"})

    with pytest.raises(HTTPException) as exc_info:
        await service.assign_vendor_to_wedding(
            vendor_profile_id=vendor_id,
            wedding_id="wedding_123",
            created_by="planner@example.com",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Vendor already assigned to this wedding"

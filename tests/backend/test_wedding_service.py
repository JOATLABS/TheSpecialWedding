import re

import pytest

from app.services.wedding_service import WeddingService


class FakeWeddingCollection:
    def __init__(self):
        self.inserted = None
        self.slug_queries: list[str] = []

    async def find_one(self, query):
        if "_id" in query:
            return None
        if "slug" in query:
            self.slug_queries.append(query["slug"])
            return None
        return None

    async def insert_one(self, document):
        self.inserted = document
        return None


@pytest.mark.asyncio
async def test_create_wedding_generates_missing_id_and_slug():
    service = WeddingService()
    fake_collection = FakeWeddingCollection()
    service.collection = fake_collection

    result = await service.create_wedding(
        {
            "couple_names": "Integration & Test",
            "date": "2026-09-15T14:00:00Z",
            "location": "CI/CD Chapel",
            "guest_count_estimate": 100,
        }
    )

    assert result["message"] == "Wedding created successfully"
    assert re.fullmatch(r"wedding_[0-9a-f]{12}", result["id"])
    assert result["slug"] == "integration-test"
    assert fake_collection.inserted is not None
    assert fake_collection.inserted["_id"] == result["id"]
    assert fake_collection.inserted["slug"] == "integration-test"
    assert fake_collection.slug_queries == ["integration-test"]

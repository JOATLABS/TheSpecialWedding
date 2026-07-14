from __future__ import annotations

import importlib
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

testimonials_module = importlib.import_module("app.api.testimonials")

LEGACY_VENDOR_ACCESS_QUOTE = (
    "Coordinating twelve vendors across two venues was a nightmare of group "
    "texts and missed emails. Now every florist, caterer, and photographer has "
    "role-based access to the timeline, uploads deliverables to the gallery, "
    "and signs off on contracts inside the platform. The automated reminders "
    "alone saved me from three near-disasters last season."
)


class FakeTestimonialsCollection:
    def __init__(self, documents: list[dict]):
        self.documents = deepcopy(documents)

    async def count_documents(self, _query: dict) -> int:
        return len(self.documents)

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        for document in self.documents:
            if all(document.get(field) == value for field, value in query.items()):
                document.update(deepcopy(update.get("$set", {})))
                return SimpleNamespace(modified_count=1)
        if upsert:
            self.documents.append(deepcopy(update["$setOnInsert"]))
            return SimpleNamespace(modified_count=0)
        return SimpleNamespace(modified_count=0)


def install_collection(monkeypatch: pytest.MonkeyPatch, documents: list[dict]):
    collection = FakeTestimonialsCollection(documents)
    monkeypatch.setattr(
        testimonials_module,
        "mongo",
        SimpleNamespace(db={testimonials_module.COLLECTION: collection}),
    )
    return collection


@pytest.mark.asyncio
async def test_refreshes_the_exact_legacy_vendor_access_testimonial(monkeypatch):
    seeded_priya = next(
        testimonial
        for testimonial in testimonials_module.DEFAULT_TESTIMONIALS
        if testimonial["name"] == "Priya Chandran"
    )
    assert seeded_priya["quote"] == testimonials_module.PRIYA_PLANNER_QUOTE

    collection = install_collection(
        monkeypatch,
        [
            {
                "name": "Priya Chandran",
                "company": "Verdant Celebrations",
                "quote": LEGACY_VENDOR_ACCESS_QUOTE,
            }
        ],
    )

    await testimonials_module._ensure_seeded()

    assert collection.documents[0]["quote"] == testimonials_module.PRIYA_PLANNER_QUOTE
    assert "role-based access" not in collection.documents[0]["quote"]


@pytest.mark.asyncio
async def test_preserves_operator_edited_testimonial_copy(monkeypatch):
    operator_quote = "Our team uses the private planner workspace every weekend."
    collection = install_collection(
        monkeypatch,
        [
            {
                "name": "Priya Chandran",
                "company": "Verdant Celebrations",
                "quote": operator_quote,
            }
        ],
    )

    await testimonials_module._ensure_seeded()

    assert collection.documents[0]["quote"] == operator_quote

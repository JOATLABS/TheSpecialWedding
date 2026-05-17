"""Tests for contract template universal-fallback behavior.

When a planner creates a contract for a vendor whose service_category is
"other" (or any category that has no dedicated templates), they should
still see "universal" templates — those created without a service_category
constraint. This file exercises that query behavior end-to-end through
``vendor_service.get_contract_templates`` and ``create_contract_template``.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.services.vendor_service import vendor_service


def _matches(document: Dict[str, Any], query: Dict[str, Any]) -> bool:
    """Minimal MongoDB query matcher supporting equality, $or, $in, $exists."""
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(document, branch) for branch in expected):
                return False
            continue

        actual = document.get(key)
        if isinstance(expected, dict):
            if "$exists" in expected:
                if (key in document) != expected["$exists"]:
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
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    def sort(self, key: str, direction: int = 1) -> "FakeCursor":
        self._docs = sorted(
            self._docs,
            key=lambda d: d.get(key) or "",
            reverse=direction < 0,
        )
        return self

    async def to_list(self, length: Optional[int] = None) -> List[Dict[str, Any]]:
        if length is None:
            return deepcopy(self._docs)
        return deepcopy(self._docs[:length])


class FakeTemplatesCollection:
    def __init__(self, documents: Optional[List[Dict[str, Any]]] = None):
        self.documents: List[Dict[str, Any]] = documents or []

    async def insert_one(self, document: Dict[str, Any]) -> SimpleNamespace:
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def find(self, query: Dict[str, Any]) -> FakeCursor:
        matched = [deepcopy(d) for d in self.documents if _matches(d, query)]
        return FakeCursor(matched)

    async def find_one(self, query: Dict[str, Any]) -> Dict[str, Any] | None:
        for document in self.documents:
            if _matches(document, query):
                return deepcopy(document)
        return None


def _make_template(
    *,
    name: str,
    service_category: Optional[str],
    created_by: str = "planner@example.com",
    is_system_template: bool = False,
    is_active: bool = True,
) -> Dict[str, Any]:
    return {
        "_id": ObjectId(),
        "name": name,
        "description": f"{name} description",
        "service_category": service_category,
        "sections": [],
        "terms_and_conditions": "Terms",
        "cancellation_policy": "Cancel",
        "default_deposit_percentage": 50.0,
        "default_payment_schedule": [],
        "created_by": created_by,
        "is_system_template": is_system_template,
        "is_public": False,
        "is_active": is_active,
        "usage_count": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def configured_template_service(monkeypatch: pytest.MonkeyPatch):
    fake = FakeTemplatesCollection()
    monkeypatch.setattr(vendor_service, "contract_templates", fake)
    return vendor_service, fake


@pytest.mark.asyncio
async def test_create_template_without_category_persists_as_universal(
    configured_template_service,
) -> None:
    service, fake = configured_template_service

    template = await service.create_contract_template(
        data={
            "name": "Universal NDA",
            "description": "Applies to any vendor",
            "sections": [],
        },
        created_by="planner@example.com",
    )

    assert template["service_category"] is None
    assert template["name"] == "Universal NDA"
    stored = fake.documents[0]
    assert stored["service_category"] is None


@pytest.mark.asyncio
async def test_create_template_with_category_persists_category(
    configured_template_service,
) -> None:
    service, _ = configured_template_service

    template = await service.create_contract_template(
        data={
            "name": "Photographer Contract",
            "service_category": "photographer",
            "sections": [],
        },
        created_by="planner@example.com",
    )

    assert template["service_category"] == "photographer"


@pytest.mark.asyncio
async def test_get_templates_by_category_returns_category_specific_and_universal(
    configured_template_service,
) -> None:
    service, fake = configured_template_service
    fake.documents.extend(
        [
            _make_template(name="Photographer A", service_category="photographer"),
            _make_template(name="Florist Only", service_category="florist"),
            _make_template(name="Universal NDA", service_category=None),
        ]
    )

    results = await service.get_contract_templates(
        created_by="planner@example.com",
        category="photographer",
    )

    names = sorted(t["name"] for t in results)
    assert names == ["Photographer A", "Universal NDA"]


@pytest.mark.asyncio
async def test_get_templates_for_other_category_still_returns_universal(
    configured_template_service,
) -> None:
    """Planners using custom 'other' vendor types must still see universal templates."""
    service, fake = configured_template_service
    fake.documents.extend(
        [
            _make_template(name="Photographer A", service_category="photographer"),
            _make_template(name="Universal NDA", service_category=None),
        ]
    )

    results = await service.get_contract_templates(
        created_by="planner@example.com",
        category="other",
    )

    names = [t["name"] for t in results]
    # Only the universal template surfaces for an 'other' vendor.
    assert names == ["Universal NDA"]


@pytest.mark.asyncio
async def test_get_templates_without_category_returns_all_owned_and_system(
    configured_template_service,
) -> None:
    service, fake = configured_template_service
    fake.documents.extend(
        [
            _make_template(name="Photographer A", service_category="photographer"),
            _make_template(name="Universal NDA", service_category=None),
            _make_template(
                name="System Florist",
                service_category="florist",
                created_by="someone-else@example.com",
                is_system_template=True,
            ),
            _make_template(
                name="Other Planner Private",
                service_category="caterer",
                created_by="someone-else@example.com",
            ),
        ]
    )

    results = await service.get_contract_templates(
        created_by="planner@example.com",
    )

    names = sorted(t["name"] for t in results)
    # Owned + system templates surface; another planner's private template does not.
    assert names == ["Photographer A", "System Florist", "Universal NDA"]


@pytest.mark.asyncio
async def test_get_templates_excludes_inactive(
    configured_template_service,
) -> None:
    service, fake = configured_template_service
    fake.documents.extend(
        [
            _make_template(name="Active Universal", service_category=None),
            _make_template(
                name="Soft-deleted Universal",
                service_category=None,
                is_active=False,
            ),
        ]
    )

    results = await service.get_contract_templates(
        created_by="planner@example.com",
        category="mc",
    )

    assert [t["name"] for t in results] == ["Active Universal"]


@pytest.mark.asyncio
async def test_get_template_rejects_other_planner_private_template(
    configured_template_service,
) -> None:
    service, fake = configured_template_service
    template_id = ObjectId()
    fake.documents.append(
        {
            **_make_template(
                name="Other Planner Private",
                service_category=None,
                created_by="other@example.com",
            ),
            "_id": template_id,
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.get_contract_template(
            str(template_id),
            created_by="planner@example.com",
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_template_allows_system_template_across_planners(
    configured_template_service,
) -> None:
    service, fake = configured_template_service
    template_id = ObjectId()
    fake.documents.append(
        {
            **_make_template(
                name="System Starter",
                service_category=None,
                created_by="system@example.com",
                is_system_template=True,
            ),
            "_id": template_id,
        }
    )

    result = await service.get_contract_template(
        str(template_id),
        created_by="planner@example.com",
    )

    assert result["name"] == "System Starter"

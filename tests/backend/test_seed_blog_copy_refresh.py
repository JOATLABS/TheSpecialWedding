from __future__ import annotations

import importlib
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

seed_blog_module = importlib.import_module("app.scripts.seed_blog")


class FakeBlogCollection:
    def __init__(self, documents: list[dict] | None = None):
        self.documents = deepcopy(documents or [])
        self.update_calls: list[tuple[dict, dict]] = []

    async def count_documents(self, _query: dict) -> int:
        return len(self.documents)

    async def update_one(self, query: dict, update: dict):
        self.update_calls.append((deepcopy(query), deepcopy(update)))
        for document in self.documents:
            if self._matches(document, query):
                document.update(deepcopy(update["$set"]))
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    async def insert_one(self, document: dict):
        self.documents.append(deepcopy(document))
        return SimpleNamespace(inserted_id=document["_id"])

    @staticmethod
    def _matches(document: dict, query: dict) -> bool:
        for field, expected in query.items():
            if field == "$or":
                if not any(
                    FakeBlogCollection._matches(document, branch) for branch in expected
                ):
                    return False
                continue
            if field == "$expr":
                left, right = expected["$eq"]
                left_field = left.removeprefix("$")
                right_field = right.removeprefix("$")
                if left_field not in document or right_field not in document:
                    return False
                if document[left_field] != document[right_field]:
                    return False
                continue
            if isinstance(expected, dict) and "$exists" in expected:
                if (field in document) is not expected["$exists"]:
                    return False
            elif isinstance(expected, dict) and "$lt" in expected:
                if field not in document or document[field] >= expected["$lt"]:
                    return False
            elif document.get(field) != expected:
                return False
        return True


def install_collection(monkeypatch: pytest.MonkeyPatch, documents: list[dict]):
    collection = FakeBlogCollection(documents)
    monkeypatch.setattr(
        seed_blog_module,
        "mongo",
        SimpleNamespace(db={"blog_articles": collection}),
    )
    return collection


@pytest.mark.asyncio
async def test_refreshes_only_the_legacy_system_seeded_public_intro(monkeypatch):
    seeded_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    collection = install_collection(
        monkeypatch,
        [
            {
                "_id": "intro-1",
                "slug": "introducing-the-special-wedding",
                "created_by": "hello@thespecialwedding.io",
                "title": "Legacy intro",
                "content": "Invite vendors into dedicated workspaces.",
                "created_at": seeded_at,
                "updated_at": seeded_at,
                "operator_note": "preserve me",
            }
        ],
    )

    result = await seed_blog_module.seed_blog()

    assert result["inserted"] == 0
    assert result["updated"] == 1
    refreshed = collection.documents[0]
    canonical = seed_blog_module.BLOG_ARTICLES[0]
    assert refreshed["title"] == canonical["title"]
    assert refreshed["content"] == canonical["content"]
    assert refreshed["seed_revision"] == seed_blog_module.PUBLIC_COPY_SEED_REVISION
    assert refreshed["operator_note"] == "preserve me"


@pytest.mark.asyncio
async def test_refreshes_the_untouched_legacy_guest_management_article(monkeypatch):
    seeded_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    collection = install_collection(
        monkeypatch,
        [
            {
                "_id": "guest-management-1",
                "slug": "managing-200-guests",
                "created_by": "hello@thespecialwedding.io",
                "title": "Managing 200+ Guests Without Losing Your Mind",
                "content": "Real-time updates visible across your team and to the couple.",
                "created_at": seeded_at,
                "updated_at": seeded_at,
            }
        ],
    )

    result = await seed_blog_module.seed_blog()

    assert result["inserted"] == 0
    assert result["updated"] == 1
    refreshed = collection.documents[0]
    canonical = next(
        article
        for article in seed_blog_module.BLOG_ARTICLES
        if article["slug"] == "managing-200-guests"
    )
    assert refreshed["content"] == canonical["content"]
    assert "real-time updates visible" not in refreshed["content"]
    assert (
        refreshed["seed_revision"]
        == seed_blog_module.PUBLIC_COPY_SEED_REVISIONS["managing-200-guests"]
    )


@pytest.mark.asyncio
async def test_automatic_refreshes_remain_eligible_for_the_next_seed_revision(
    monkeypatch,
):
    seeded_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    slug = "introducing-the-special-wedding"
    collection = install_collection(
        monkeypatch,
        [
            {
                "_id": "sequential-intro",
                "slug": slug,
                "created_by": "hello@thespecialwedding.io",
                "title": "Revision one",
                "content": "Legacy copy",
                "seed_revision": 1,
                "created_at": seeded_at,
                "updated_at": seeded_at,
            }
        ],
    )

    revision_two = await seed_blog_module.seed_blog()
    assert revision_two["updated"] == 1
    assert collection.documents[0]["seed_revision"] == 2
    assert collection.documents[0]["updated_at"] == seeded_at
    assert collection.documents[0]["seed_refreshed_at"] > seeded_at

    monkeypatch.setitem(seed_blog_module.PUBLIC_COPY_SEED_REVISIONS, slug, 3)
    revision_three = await seed_blog_module.seed_blog()

    assert revision_three["updated"] == 1
    assert collection.documents[0]["seed_revision"] == 3
    assert collection.documents[0]["updated_at"] == seeded_at

    collection.documents[0]["content"] = "Operator edit after revision three"
    collection.documents[0]["updated_at"] = seeded_at + timedelta(days=1)
    monkeypatch.setitem(seed_blog_module.PUBLIC_COPY_SEED_REVISIONS, slug, 4)

    blocked_revision = await seed_blog_module.seed_blog()
    assert blocked_revision["updated"] == 0
    assert collection.documents[0]["seed_revision"] == 3
    assert collection.documents[0]["content"] == "Operator edit after revision three"


@pytest.mark.asyncio
async def test_never_overwrites_an_operator_authored_article_with_the_same_slug(
    monkeypatch,
):
    original = {
        "_id": "operator-intro",
        "slug": "introducing-the-special-wedding",
        "created_by": "planner@example.com",
        "title": "Operator-authored intro",
        "content": "Keep this editorial copy.",
    }
    collection = install_collection(monkeypatch, [original])

    result = await seed_blog_module.seed_blog()

    assert result["inserted"] == 0
    assert result["updated"] == 0
    assert collection.documents == [original]


@pytest.mark.asyncio
async def test_never_overwrites_an_admin_edited_legacy_system_article(monkeypatch):
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    edited = {
        "_id": "edited-system-intro",
        "slug": "introducing-the-special-wedding",
        "created_by": "hello@thespecialwedding.io",
        "title": "Admin-edited intro",
        "content": "Preserve this editorial revision.",
        "created_at": created_at,
        "updated_at": created_at + timedelta(days=1),
    }
    collection = install_collection(monkeypatch, [edited])

    result = await seed_blog_module.seed_blog()

    assert result["updated"] == 0
    assert collection.documents == [edited]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "slug", ["introducing-the-special-wedding", "managing-200-guests"]
)
@pytest.mark.parametrize("revision_offset", [0, 1])
async def test_public_copy_refresh_never_downgrades_current_or_future_revisions(
    monkeypatch, slug, revision_offset
):
    seeded_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    seed_revision = seed_blog_module.PUBLIC_COPY_SEED_REVISIONS[slug] + revision_offset
    collection = install_collection(
        monkeypatch,
        [
            {
                "_id": "intro-2",
                "slug": slug,
                "created_by": "hello@thespecialwedding.io",
                "seed_revision": seed_revision,
                "title": "Already refreshed",
                "created_at": seeded_at,
                "updated_at": seeded_at,
            }
        ],
    )

    first_result = await seed_blog_module.seed_blog()
    second_result = await seed_blog_module.seed_blog()

    assert first_result["updated"] == 0
    assert second_result["updated"] == 0
    assert collection.documents[0]["title"] == "Already refreshed"


@pytest.mark.asyncio
async def test_new_seed_records_the_public_copy_revision(monkeypatch):
    collection = install_collection(monkeypatch, [])

    result = await seed_blog_module.seed_blog()

    assert result["inserted"] == len(seed_blog_module.BLOG_ARTICLES)
    assert result["updated"] == 0
    intro = next(
        article
        for article in collection.documents
        if article["slug"] == "introducing-the-special-wedding"
    )
    guest_management = next(
        article
        for article in collection.documents
        if article["slug"] == "managing-200-guests"
    )
    assert intro["seed_revision"] == seed_blog_module.PUBLIC_COPY_SEED_REVISION
    assert (
        guest_management["seed_revision"]
        == seed_blog_module.PUBLIC_COPY_SEED_REVISIONS["managing-200-guests"]
    )

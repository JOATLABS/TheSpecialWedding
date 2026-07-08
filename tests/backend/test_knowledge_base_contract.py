"""
Knowledge base contract tests.

These tests cover the status contract alignment, the removal of the dead
feedback-summary route, and the projection/query behavior of article listing.
"""

from types import SimpleNamespace

import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.api.knowledge_base import ArticleCreateRequest, ArticleUpdateRequest, router
from app.api.public_knowledge_base import router as public_router
from app.models.knowledge_base import (
    KB_STATUSES,
    KnowledgeBaseArticleCreateModel,
    KnowledgeBaseArticleUpdateModel,
)
from app.services.knowledge_base_service import KnowledgeBaseService

VALID_ARTICLE_PAYLOAD = {
    "title": "How to use the knowledge base",
    "content": "This is long enough content for validation. " * 4,
    "excerpt": "This excerpt is long enough to satisfy validation.",
    "category": "general",
    "tags": ["docs"],
}


class FakeCursor:
    def sort(self, *_args, **_kwargs):
        return self

    def skip(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class FakeArticlesCollection:
    def __init__(self):
        self.count_query = None
        self.find_query = None
        self.find_projection = None

    async def count_documents(self, query):
        self.count_query = query
        return 0

    def find(self, query, projection=None):
        self.find_query = query
        self.find_projection = projection
        return FakeCursor()


class FakePublicArticlesCollection:
    def __init__(self, article):
        self.article = article
        self.find_query = None
        self.update_query = None
        self.update_payload = None

    async def find_one(self, query):
        self.find_query = query
        return self.article

    async def update_one(self, query, payload):
        self.update_query = query
        self.update_payload = payload


class FakeKnowledgeBaseService(KnowledgeBaseService):
    def __init__(self, articles_collection):
        self.articles_collection = articles_collection


def test_pending_review_rejected_across_kb_models_and_requests():
    with pytest.raises(ValidationError):
        KnowledgeBaseArticleCreateModel(
            **VALID_ARTICLE_PAYLOAD, status="pending_review"
        )

    with pytest.raises(ValidationError):
        KnowledgeBaseArticleUpdateModel(status="pending_review")

    with pytest.raises(ValidationError):
        ArticleCreateRequest(**VALID_ARTICLE_PAYLOAD, status="pending_review")

    with pytest.raises(ValidationError):
        ArticleUpdateRequest(status="pending_review")


def test_archived_is_supported_status():
    assert "archived" in KB_STATUSES
    KnowledgeBaseArticleCreateModel(**VALID_ARTICLE_PAYLOAD, status="archived")
    ArticleCreateRequest(**VALID_ARTICLE_PAYLOAD, status="archived")


def test_feedback_summary_route_removed_from_router():
    paths = {route.path for route in router.routes}
    assert "/admin/kb/feedback-summary" not in paths


def test_public_kb_router_is_get_only_and_outside_admin_prefix():
    paths = {route.path for route in public_router.routes}
    methods = {
        method
        for route in public_router.routes
        for method in getattr(route, "methods", set())
    }

    assert "/public/kb/articles" in paths
    assert "/public/kb/categories" in paths
    assert "/public/kb/search" in paths
    assert all(not path.startswith("/admin") for path in paths)
    assert methods <= {"GET", "HEAD"}


@pytest.mark.asyncio
async def test_get_articles_uses_projection_for_large_fields():
    fake_collection = FakeArticlesCollection()
    service = SimpleNamespace(articles_collection=fake_collection)

    result = await KnowledgeBaseService.get_articles(
        service,
        page=1,
        limit=20,
        search="guide",
        status="published",
    )

    assert result["articles"] == []
    assert fake_collection.find_projection == {"content": 0, "feedback": 0}
    assert fake_collection.find_query["status"] == "published"


@pytest.mark.asyncio
async def test_get_articles_allows_admin_route_to_fetch_all_statuses():
    fake_collection = FakeArticlesCollection()
    service = SimpleNamespace(articles_collection=fake_collection)

    await KnowledgeBaseService.get_articles(
        service,
        page=1,
        limit=20,
        status=None,
    )

    assert fake_collection.count_query == {}
    assert fake_collection.find_query == {}


@pytest.mark.asyncio
async def test_public_articles_force_published_status():
    fake_collection = FakeArticlesCollection()
    service = FakeKnowledgeBaseService(fake_collection)

    await service.get_public_articles(page=1, limit=20, category="general")

    assert fake_collection.count_query == {
        "status": "published",
        "category": "general",
    }
    assert fake_collection.find_query == {
        "status": "published",
        "category": "general",
    }


@pytest.mark.asyncio
async def test_public_article_by_slug_sanitizes_private_fields():
    article_id = ObjectId()
    article = {
        "_id": article_id,
        "title": "Public calendar guide",
        "slug": "public-calendar-guide",
        "content": "# Public calendar guide\n\nConnect Google Calendar safely.",
        "excerpt": "Connect Google Calendar safely.",
        "category": "calendar-tasks",
        "tags": ["calendar"],
        "status": "published",
        "is_official": True,
        "featured": False,
        "author_name": "The Special Wedding",
        "author_email": "root@example.com",
        "author_id": "private-user-id",
        "created_by": "root@example.com",
        "updated_by": "root@example.com",
        "feedback": [{"user_email": "planner@example.com", "helpful": True}],
        "view_count": 3,
        "helpful_count": 2,
        "not_helpful_count": 1,
        "estimated_read_minutes": 4,
    }
    fake_collection = FakePublicArticlesCollection(article)
    service = FakeKnowledgeBaseService(fake_collection)

    result = await service.get_public_article_by_slug("public-calendar-guide")

    assert fake_collection.find_query == {
        "slug": "public-calendar-guide",
        "status": "published",
    }
    assert fake_collection.update_query == {"_id": article_id}
    assert fake_collection.update_payload == {"$inc": {"view_count": 1}}
    assert result["content"].startswith("# Public calendar guide")
    assert result["view_count"] == 4
    assert "_id" not in result
    assert "author_email" not in result
    assert "author_id" not in result
    assert "created_by" not in result
    assert "updated_by" not in result
    assert "feedback" not in result
    assert "not_helpful_count" not in result

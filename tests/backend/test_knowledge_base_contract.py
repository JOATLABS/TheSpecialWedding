"""
Knowledge base contract tests.

These tests cover the status contract alignment, the removal of the dead
feedback-summary route, and the projection/query behavior of article listing.
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.knowledge_base import ArticleCreateRequest, ArticleUpdateRequest, router
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

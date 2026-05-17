"""
Tests for app/services/babylovegrowth_sync_service.py.

Three test surfaces:

  1. BabyLoveGrowthClient — HTTP error taxonomy + retry policy. The
     mockup commits to specific handler behaviour for 401 (kill),
     404 (skip), 429 (backoff×3 then raise), 5xx (same), network
     errors (same). One test per row in the taxonomy table.

  2. _map_blg_article — pure mapping function. Mapping rules for
     title truncation, meta truncation, excerpt fallback chain,
     slug regeneration, keyword→tag mapping, LAND_AS_DRAFT default.

  3. BabyLoveGrowthSyncService — orchestration with mocked Mongo +
     mocked client + mocked image upload. Lock acquire/release,
     final-status threshold logic, language filter, idempotency
     by babylovegrowth_id.

All tests stub external systems — no real Mongo, no real httpx, no
real R2. Reserved for the testbed driver.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from app.services.babylovegrowth_sync_service import (
    MAX_RETRY_ATTEMPTS,
    SYNC_STATE_COLLECTION,
    SYNC_STATE_DOC_ID,
    BabyLoveGrowthAuthError,
    BabyLoveGrowthClient,
    BabyLoveGrowthClientError,
    BabyLoveGrowthNotFoundError,
    BabyLoveGrowthSyncService,
    _map_blg_article,
)


# Helper to skip real retry backoff during tests — patches asyncio.sleep
# to a no-op so retry tests run instantly.
@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.asyncio.sleep", _instant_sleep
    )


def _fixture_summary(blg_id: int, *, language: str = "en") -> dict:
    return {
        "id": blg_id,
        "title": f"Article {blg_id}",
        "slug": f"article-{blg_id}",
        "hero_image_url": "https://cdn.example.com/hero.jpg",
        "languageCode": language,
        "meta_description": "Short meta description for the card view.",
        "excerpt": "A useful excerpt for the listing layout, definitely long enough.",
        "orgWebsite": "https://thespecialwedding.io",
        "created_at": "2026-05-14T00:00:00.000Z",
        "seedKeyword": "weddings",
        "keywords": ["weddings", "planning"],
    }


def _fixture_full(blg_id: int) -> dict:
    return {
        "id": blg_id,
        "title": f"Article {blg_id}",
        "slug": f"article-{blg_id}",
        "content_markdown": "# Title\n\nBody content paragraph.",
        "content_html": (
            "<h2>Section</h2>"
            "<p>Body paragraph with enough text to satisfy the 50-char min.</p>"
        ),
        "jsonLd": {"@context": "https://schema.org"},
        "faqJsonLd": {"@context": "https://schema.org"},
        "meta_description": "Full meta description.",
        "hero_image_url": "https://cdn.example.com/hero.jpg",
        "orgWebsite": "https://thespecialwedding.io",
        "created_at": "2026-05-14T00:00:00.000Z",
        "seedKeyword": "weddings",
        "keywords": ["weddings", "planning"],
    }


# ──────────────────────────────── BabyLoveGrowthClient ───────────────────────


@respx.mock
def test_client_list_happy_path():
    client = BabyLoveGrowthClient(
        "test-key", "https://api.example.com/api/integrations"
    )
    respx.get("https://api.example.com/api/integrations/v1/articles").mock(
        return_value=httpx.Response(200, json=[_fixture_summary(1)])
    )
    result = asyncio.run(client.list_articles(limit=50, offset=0))
    assert len(result) == 1
    assert result[0]["id"] == 1


@respx.mock
def test_client_fetch_happy_path():
    client = BabyLoveGrowthClient(
        "test-key", "https://api.example.com/api/integrations"
    )
    respx.get("https://api.example.com/api/integrations/v1/articles/42").mock(
        return_value=httpx.Response(200, json=_fixture_full(42))
    )
    result = asyncio.run(client.fetch_article(42))
    assert result["id"] == 42
    assert "content_html" in result


@respx.mock
def test_client_401_raises_auth_error_no_retry():
    """Per the mockup: 401 fails loud, no retry."""
    client = BabyLoveGrowthClient("bad-key", "https://api.example.com/api/integrations")
    route = respx.get("https://api.example.com/api/integrations/v1/articles").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )

    with pytest.raises(BabyLoveGrowthAuthError, match="401"):
        asyncio.run(client.list_articles(limit=50, offset=0))
    # Exactly one request — no retry on 401.
    assert route.call_count == 1


@respx.mock
def test_client_404_raises_not_found_no_retry():
    client = BabyLoveGrowthClient(
        "test-key", "https://api.example.com/api/integrations"
    )
    route = respx.get("https://api.example.com/api/integrations/v1/articles/99").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )

    with pytest.raises(BabyLoveGrowthNotFoundError, match="404"):
        asyncio.run(client.fetch_article(99))
    assert route.call_count == 1


@respx.mock
def test_client_429_retries_then_raises_client_error():
    client = BabyLoveGrowthClient(
        "test-key", "https://api.example.com/api/integrations"
    )
    route = respx.get("https://api.example.com/api/integrations/v1/articles").mock(
        return_value=httpx.Response(429)
    )

    with pytest.raises(BabyLoveGrowthClientError, match="429"):
        asyncio.run(client.list_articles(limit=50, offset=0))
    # All three retry attempts consumed before raising.
    assert route.call_count == MAX_RETRY_ATTEMPTS


@respx.mock
def test_client_429_then_200_succeeds():
    """If retry attempt succeeds, the result is returned normally."""
    client = BabyLoveGrowthClient(
        "test-key", "https://api.example.com/api/integrations"
    )
    route = respx.get("https://api.example.com/api/integrations/v1/articles").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json=[_fixture_summary(1)]),
        ]
    )
    result = asyncio.run(client.list_articles(limit=50, offset=0))
    assert len(result) == 1
    assert route.call_count == 2


@respx.mock
def test_client_503_retries_then_raises():
    client = BabyLoveGrowthClient(
        "test-key", "https://api.example.com/api/integrations"
    )
    route = respx.get("https://api.example.com/api/integrations/v1/articles").mock(
        return_value=httpx.Response(503)
    )

    with pytest.raises(BabyLoveGrowthClientError, match="503"):
        asyncio.run(client.list_articles(limit=50, offset=0))
    assert route.call_count == MAX_RETRY_ATTEMPTS


@respx.mock
def test_client_network_error_retries_then_raises():
    client = BabyLoveGrowthClient(
        "test-key", "https://api.example.com/api/integrations"
    )
    route = respx.get("https://api.example.com/api/integrations/v1/articles").mock(
        side_effect=httpx.ConnectError("conn refused")
    )

    with pytest.raises(BabyLoveGrowthClientError, match="Network error"):
        asyncio.run(client.list_articles(limit=50, offset=0))
    assert route.call_count == MAX_RETRY_ATTEMPTS


@respx.mock
def test_client_malformed_json_raises_client_error():
    client = BabyLoveGrowthClient(
        "test-key", "https://api.example.com/api/integrations"
    )
    respx.get("https://api.example.com/api/integrations/v1/articles").mock(
        return_value=httpx.Response(
            200, content=b"<html>not json</html>", headers={"content-type": "text/html"}
        )
    )

    with pytest.raises(BabyLoveGrowthClientError, match="non-JSON"):
        asyncio.run(client.list_articles(limit=50, offset=0))


# ─────────────────────────────── _map_blg_article ────────────────────────────


def test_map_happy_path():
    full = _fixture_full(1)
    summary = _fixture_summary(1)
    result = _map_blg_article(full, summary)
    assert result is not None
    assert result["title"] == "Article 1"
    assert result["slug"] == "article-1"
    assert "<h2>Section</h2>" in result["content"]
    assert result["tags"] == ["weddings", "planning"]
    assert result["category"] == "general"


def test_map_title_truncated_at_200_chars(caplog):
    full = _fixture_full(1)
    full["title"] = "x" * 300
    summary = _fixture_summary(1)
    summary["title"] = "x" * 300

    result = _map_blg_article(full, summary)
    assert len(result["title"]) == 200


def test_map_meta_description_truncated_at_160_chars():
    full = _fixture_full(1)
    full["meta_description"] = "y" * 500
    summary = _fixture_summary(1)
    summary["meta_description"] = "y" * 500

    result = _map_blg_article(full, summary)
    assert len(result["meta_description"]) == 160


def test_map_excerpt_falls_back_to_meta_when_missing():
    """Single-fetch payload has no excerpt; summary excerpt is removed
    to force the meta_description fallback path. Meta is sourced from
    full first, then summary — set on both so the mapper uses it
    deterministically."""
    full = _fixture_full(1)
    full["meta_description"] = "Meta fallback content for excerpt — long enough."
    summary = _fixture_summary(1)
    summary.pop("excerpt", None)
    summary["meta_description"] = full["meta_description"]

    result = _map_blg_article(full, summary)
    assert "Meta fallback" in result["excerpt"]


def test_map_excerpt_falls_back_to_content_when_meta_also_missing():
    full = _fixture_full(1)
    full["meta_description"] = ""
    summary = _fixture_summary(1)
    summary.pop("excerpt", None)
    summary["meta_description"] = ""

    result = _map_blg_article(full, summary)
    assert result["excerpt"]
    # Should have stripped HTML and used a chunk of body text.
    assert "<" not in result["excerpt"]


def test_map_invalid_slug_regenerated_from_title():
    full = _fixture_full(1)
    full["slug"] = "Bad Slug With Spaces!!"
    full["title"] = "Wedding Planning Tips"
    summary = _fixture_summary(1)
    summary["slug"] = full["slug"]
    summary["title"] = full["title"]

    result = _map_blg_article(full, summary)
    assert result["slug"] == "wedding-planning-tips"


def test_map_empty_title_returns_none():
    full = _fixture_full(1)
    full["title"] = ""
    summary = _fixture_summary(1)
    summary["title"] = ""
    assert _map_blg_article(full, summary) is None


def test_map_empty_content_returns_none():
    full = _fixture_full(1)
    full["content_html"] = ""
    full["content_markdown"] = ""
    summary = _fixture_summary(1)
    assert _map_blg_article(full, summary) is None


def test_map_keywords_capped_at_15_tags():
    full = _fixture_full(1)
    full["keywords"] = [f"kw-{i}" for i in range(30)]
    summary = _fixture_summary(1)
    summary["keywords"] = full["keywords"]

    result = _map_blg_article(full, summary)
    assert len(result["tags"]) == 15


def test_map_keywords_lowercased_and_stripped():
    full = _fixture_full(1)
    full["keywords"] = ["WEDDINGS", "  Planning  ", "DIY"]
    summary = _fixture_summary(1)
    summary["keywords"] = full["keywords"]

    result = _map_blg_article(full, summary)
    assert "weddings" in result["tags"]
    assert "planning" in result["tags"]
    assert "diy" in result["tags"]


def test_map_land_as_draft_true_produces_draft_status(monkeypatch):
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_land_as_draft",
        True,
    )
    full = _fixture_full(1)
    summary = _fixture_summary(1)

    result = _map_blg_article(full, summary)
    assert result["status"] == "draft"
    assert result["published_at"] is None


def test_map_land_as_draft_false_produces_published_status(monkeypatch):
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_land_as_draft",
        False,
    )
    full = _fixture_full(1)
    summary = _fixture_summary(1)

    result = _map_blg_article(full, summary)
    assert result["status"] == "published"
    assert result["published_at"] is not None


def test_map_img_in_content_survives_sanitization():
    """The CP1 img allowlist must work end-to-end through the mapper."""
    full = _fixture_full(1)
    full["content_html"] = (
        "<h2>Heading</h2>"
        "<p>Body intro that is long enough to clear sanitization.</p>"
        '<img src="https://cdn.example.com/inline.jpg" alt="Inline">'
    )
    summary = _fixture_summary(1)

    result = _map_blg_article(full, summary)
    assert "<img" in result["content"]
    assert 'src="https://cdn.example.com/inline.jpg"' in result["content"]


def test_map_json_ld_and_faq_json_ld_preserved():
    """Per BLG docs Best Practice, jsonLd and faqJsonLd should be
    stored as dedicated fields so rich-result eligibility is kept.
    Citation: https://www.babylovegrowth.ai/docs/integrations/api"""
    full = _fixture_full(1)
    full["jsonLd"] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Test",
    }
    full["faqJsonLd"] = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [],
    }
    summary = _fixture_summary(1)

    result = _map_blg_article(full, summary)
    assert result["json_ld"] == full["jsonLd"]
    assert result["faq_json_ld"] == full["faqJsonLd"]


def test_map_missing_json_ld_yields_none_not_keyerror():
    """If BLG omits jsonLd/faqJsonLd (e.g. an older article in their
    pipeline), we must store None — never raise KeyError."""
    full = _fixture_full(1)
    full.pop("jsonLd", None)
    full.pop("faqJsonLd", None)
    summary = _fixture_summary(1)

    result = _map_blg_article(full, summary)
    assert result["json_ld"] is None
    assert result["faq_json_ld"] is None


def test_map_jsonld_unexpected_type_dropped(caplog):
    """Defensive: if BLG ships back a string instead of an object,
    drop the field rather than corrupt the Mongo doc."""
    full = _fixture_full(1)
    full["jsonLd"] = "not-an-object"  # Schema change scenario
    full["faqJsonLd"] = 12345
    summary = _fixture_summary(1)

    result = _map_blg_article(full, summary)
    assert result["json_ld"] is None
    assert result["faq_json_ld"] is None


def test_map_http_img_in_content_dropped():
    """Defense in depth: even if a synced article has an http: image,
    the sanitizer drops it. Tests CP1 + CP4 together."""
    full = _fixture_full(1)
    full["content_html"] = (
        "<h2>Heading</h2>"
        "<p>Body intro that is long enough to clear sanitization.</p>"
        '<img src="http://insecure.example.com/x.jpg" alt="Bad">'
    )
    summary = _fixture_summary(1)

    result = _map_blg_article(full, summary)
    assert "http://insecure" not in result["content"]


# ─────────────────────── BabyLoveGrowthSyncService ───────────────────────────


@pytest.fixture
def mock_mongo_for_sync(monkeypatch):
    """Inject an in-memory dict-backed Mongo replacement for the sync collections."""
    state = {"blog_articles": [], "babylovegrowth_sync_runs_doc": None}

    blog_articles = MagicMock()

    class _BlogArticlesCursor:
        def __init__(self, docs):
            self._docs = list(docs)

        def __aiter__(self):
            self._iter = iter(self._docs)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    def _blog_find(query, projection=None):
        # Only used for fetching known babylovegrowth_ids.
        docs = [
            {"babylovegrowth_id": d.get("babylovegrowth_id")}
            for d in state["blog_articles"]
            if d.get("babylovegrowth_id") is not None
        ]
        return _BlogArticlesCursor(docs)

    async def _blog_update_one(filter_doc, update, upsert=False):
        # Apply $set + $setOnInsert. Mirrors Mongo semantics enough for
        # the success-path tests; doesn't simulate DuplicateKeyError.
        match_id = filter_doc.get("babylovegrowth_id")
        existing = next(
            (
                d
                for d in state["blog_articles"]
                if d.get("babylovegrowth_id") == match_id
            ),
            None,
        )
        if existing is None and upsert:
            new_doc = {}
            new_doc.update(update.get("$setOnInsert", {}))
            new_doc.update(update.get("$set", {}))
            state["blog_articles"].append(new_doc)
        elif existing is not None:
            existing.update(update.get("$set", {}))

    blog_articles.find.side_effect = _blog_find
    blog_articles.update_one = AsyncMock(side_effect=_blog_update_one)

    # ────── sync runs collection ──────
    sync_runs = MagicMock()

    async def _runs_find_one_and_update(
        filter_doc, update, upsert=False, return_document=None
    ):
        doc = state["babylovegrowth_sync_runs_doc"]
        # Accept the lock if doc doesn't exist OR matches the filter conditions.
        matches = False
        if doc is None and upsert:
            matches = True
        else:
            # Simplified: accept whenever status != "running".
            matches = doc is not None and doc.get("status") != "running"
        if matches:
            new_doc = dict(doc) if doc else {"_id": SYNC_STATE_DOC_ID}
            new_doc.update(update.get("$set", {}))
            state["babylovegrowth_sync_runs_doc"] = new_doc
            return new_doc
        return None

    async def _runs_update_one(filter_doc, update):
        doc = state["babylovegrowth_sync_runs_doc"]
        if doc is None:
            return
        # Apply $set if filter matches lock_token.
        token_filter = filter_doc.get("lock_token")
        if token_filter is not None and doc.get("lock_token") != token_filter:
            return
        doc.update(update.get("$set", {}))

    async def _runs_find_one(filter_doc):
        return state["babylovegrowth_sync_runs_doc"]

    sync_runs.find_one_and_update = AsyncMock(side_effect=_runs_find_one_and_update)
    sync_runs.update_one = AsyncMock(side_effect=_runs_update_one)
    sync_runs.find_one = AsyncMock(side_effect=_runs_find_one)

    # Build a fake mongo.db proxy.
    fake_db = {"blog_articles": blog_articles, SYNC_STATE_COLLECTION: sync_runs}
    fake_mongo = MagicMock()
    fake_mongo.db = fake_db

    monkeypatch.setattr("app.services.babylovegrowth_sync_service.mongo", fake_mongo)
    return state


@pytest.fixture
def configured_settings(monkeypatch):
    """Stub Settings so the sync service believes it's enabled."""
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_sync_enabled",
        True,
    )
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_api_base_url",
        "https://api.example.com/api/integrations",
    )
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_land_as_draft",
        True,
    )


def test_service_skipped_when_disabled(monkeypatch, mock_mongo_for_sync):
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_sync_enabled",
        False,
    )
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_api_key",
        "test-key",
    )

    service = BabyLoveGrowthSyncService()
    result = asyncio.run(service.run_full_sync())
    assert result == {"status": "skipped", "reason": "sync_disabled"}


def test_service_skipped_when_no_api_key(monkeypatch, mock_mongo_for_sync):
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_sync_enabled",
        True,
    )
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.settings.babylovegrowth_api_key", None
    )

    service = BabyLoveGrowthSyncService()
    result = asyncio.run(service.run_full_sync())
    assert result == {"status": "skipped", "reason": "no_api_key"}


@respx.mock
def test_service_happy_path(monkeypatch, mock_mongo_for_sync, configured_settings):
    """End-to-end through the orchestration with stubbed BLG + R2."""
    # Stub BLG list (one page, then empty page).
    respx.get(
        "https://api.example.com/api/integrations/v1/articles",
        params={"limit": 50, "offset": 0},
    ).mock(
        return_value=httpx.Response(
            200, json=[_fixture_summary(101), _fixture_summary(102)]
        )
    )

    respx.get("https://api.example.com/api/integrations/v1/articles/101").mock(
        return_value=httpx.Response(200, json=_fixture_full(101))
    )
    respx.get("https://api.example.com/api/integrations/v1/articles/102").mock(
        return_value=httpx.Response(200, json=_fixture_full(102))
    )

    # Stub upload_service.upload_from_url so hero image proxy succeeds.
    mock_upload = AsyncMock(
        return_value={"key": "blog/synced/k", "cdn_url": "https://cdn.test/k"}
    )

    service = BabyLoveGrowthSyncService()
    monkeypatch.setattr(
        service, "_upload_service", MagicMock(upload_from_url=mock_upload)
    )

    result = asyncio.run(service.run_full_sync())
    assert result["status"] == "succeeded"
    assert result["new_count"] == 2
    assert result["error_count"] == 0
    assert len(mock_mongo_for_sync["blog_articles"]) == 2
    # All upserts carry babylovegrowth_id.
    assert {d["babylovegrowth_id"] for d in mock_mongo_for_sync["blog_articles"]} == {
        101,
        102,
    }
    # Hero proxied to our CDN.
    assert all(
        d["og_image"] == "https://cdn.test/k"
        for d in mock_mongo_for_sync["blog_articles"]
    )
    # Brand-safe default: draft status.
    assert all(d["status"] == "draft" for d in mock_mongo_for_sync["blog_articles"])


@respx.mock
def test_service_skips_non_english(
    monkeypatch, mock_mongo_for_sync, configured_settings
):
    es_summary = _fixture_summary(201, language="es")
    en_summary = _fixture_summary(202, language="en")
    respx.get(
        "https://api.example.com/api/integrations/v1/articles",
        params={"limit": 50, "offset": 0},
    ).mock(return_value=httpx.Response(200, json=[es_summary, en_summary]))
    respx.get("https://api.example.com/api/integrations/v1/articles/202").mock(
        return_value=httpx.Response(200, json=_fixture_full(202))
    )

    mock_upload = AsyncMock(return_value={"key": "k", "cdn_url": "https://cdn.test/k"})
    service = BabyLoveGrowthSyncService()
    monkeypatch.setattr(
        service, "_upload_service", MagicMock(upload_from_url=mock_upload)
    )

    result = asyncio.run(service.run_full_sync())
    assert result["status"] == "succeeded"
    assert result["new_count"] == 1
    assert result["skipped_count"] == 1
    assert {d["babylovegrowth_id"] for d in mock_mongo_for_sync["blog_articles"]} == {
        202
    }


@respx.mock
def test_service_image_failure_persists_article_without_hero(
    monkeypatch, mock_mongo_for_sync, configured_settings
):
    respx.get(
        "https://api.example.com/api/integrations/v1/articles",
        params={"limit": 50, "offset": 0},
    ).mock(return_value=httpx.Response(200, json=[_fixture_summary(301)]))
    respx.get("https://api.example.com/api/integrations/v1/articles/301").mock(
        return_value=httpx.Response(200, json=_fixture_full(301))
    )

    # Image fetch raises — should be caught by _proxy_hero_image.
    from app.services.blog_upload_service import BlogUploadFromUrlError

    mock_upload = AsyncMock(side_effect=BlogUploadFromUrlError("image gone"))
    service = BabyLoveGrowthSyncService()
    monkeypatch.setattr(
        service, "_upload_service", MagicMock(upload_from_url=mock_upload)
    )

    result = asyncio.run(service.run_full_sync())
    assert result["status"] == "succeeded"
    assert result["new_count"] == 1
    assert result["image_failed_count"] == 1
    article = mock_mongo_for_sync["blog_articles"][0]
    assert article["og_image"] is None
    assert article["card_image"] is None


@respx.mock
def test_service_already_synced_skipped(
    monkeypatch, mock_mongo_for_sync, configured_settings
):
    # Pre-seed the in-memory mongo with an already-synced article.
    mock_mongo_for_sync["blog_articles"].append(
        {"babylovegrowth_id": 401, "slug": "old"}
    )

    respx.get(
        "https://api.example.com/api/integrations/v1/articles",
        params={"limit": 50, "offset": 0},
    ).mock(return_value=httpx.Response(200, json=[_fixture_summary(401)]))

    mock_upload = AsyncMock(return_value={"key": "k", "cdn_url": "https://cdn.test/k"})
    service = BabyLoveGrowthSyncService()
    monkeypatch.setattr(
        service, "_upload_service", MagicMock(upload_from_url=mock_upload)
    )

    result = asyncio.run(service.run_full_sync())
    assert result["new_count"] == 0
    assert result["skipped_count"] == 1


@respx.mock
def test_service_404_on_single_fetch_skipped_not_fatal(
    monkeypatch, mock_mongo_for_sync, configured_settings
):
    respx.get(
        "https://api.example.com/api/integrations/v1/articles",
        params={"limit": 50, "offset": 0},
    ).mock(return_value=httpx.Response(200, json=[_fixture_summary(501)]))
    respx.get("https://api.example.com/api/integrations/v1/articles/501").mock(
        return_value=httpx.Response(404, json={"error": "gone"})
    )

    mock_upload = AsyncMock(return_value={"key": "k", "cdn_url": "https://cdn.test/k"})
    service = BabyLoveGrowthSyncService()
    monkeypatch.setattr(
        service, "_upload_service", MagicMock(upload_from_url=mock_upload)
    )

    result = asyncio.run(service.run_full_sync())
    # Sole article was 404 → 100% error rate → status="failed" per threshold rule.
    assert result["new_count"] == 0
    assert result["error_count"] == 1


@respx.mock
def test_service_401_flips_kill_switch(
    monkeypatch, mock_mongo_for_sync, configured_settings
):
    respx.get(
        "https://api.example.com/api/integrations/v1/articles",
        params={"limit": 50, "offset": 0},
    ).mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))

    service = BabyLoveGrowthSyncService()
    monkeypatch.setattr(service, "_upload_service", MagicMock())

    result = asyncio.run(service.run_full_sync())
    assert result["status"] == "failed"
    # Settings flag flipped to False so cron won't keep retrying a bad key.
    from app.services.babylovegrowth_sync_service import settings as _settings

    assert _settings.babylovegrowth_sync_enabled is False

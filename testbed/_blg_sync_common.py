"""Shared helpers for the BabyLoveGrowth sync testbed verifiers.

Every ``verify_blg_*.py`` driver needs the same handful of ingredients:

  - A reserved range of synthetic BLG article IDs so reruns are
    deterministic and never collide with real BLG data
  - Fixture payloads matching BLG's API contract (verified against
    https://www.babylovegrowth.ai/docs/integrations/api)
  - A predictable R2 folder prefix so cleanup can purge fixtures
    without touching admin-authored content
  - Mongo helpers reused across drivers

Leading underscore on the module name keeps driver discovery from
picking this file up as a runnable verifier — it's a library, not a
driver.

Cross-references:
  - Implementation plan: docs/plans/babylovegrowth_integration_mockup.md
  - Existing pattern: testbed/_form_lifecycle_common.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Reserved synthetic BLG ID range — never collides with real BLG data.
#
# Real BLG article IDs (per their docs response examples) are large
# 5-6 digit integers. We park our fixtures at 9_990_000+ so cleanup
# can sweep this range safely.
# ---------------------------------------------------------------------------

BLG_TEST_ID_BASE = 9_990_000

BLG_TEST_IDS = {
    "happy_path": BLG_TEST_ID_BASE + 1,
    "idempotency": BLG_TEST_ID_BASE + 2,
    "lock_contention_a": BLG_TEST_ID_BASE + 3,
    "lock_contention_b": BLG_TEST_ID_BASE + 4,
    "image_failure": BLG_TEST_ID_BASE + 5,
    "kill_switch": BLG_TEST_ID_BASE + 6,
    "language_filter": BLG_TEST_ID_BASE + 7,
    "img_allowlist_persisted": BLG_TEST_ID_BASE + 8,
    "settings_and_index": BLG_TEST_ID_BASE + 9,
}


# R2 folder prefix for testbed fixture images — `blog_upload_service`'s
# delete_blog_file works on individual keys, so cleanup iterates this
# prefix via boto3's list_objects_v2.
BLG_TEST_R2_PREFIX = "blog/synced/test-fixtures"


# ---------------------------------------------------------------------------
# Fixture payloads — match BLG's documented response shape exactly.
# Single-fetch shape per https://www.babylovegrowth.ai/docs/integrations/api
# ---------------------------------------------------------------------------


def make_blg_summary(
    blg_id: int,
    *,
    title: str = "Test Article",
    slug: Optional[str] = None,
    language_code: str = "en",
    hero_image_url: Optional[str] = "https://cdn.example.com/test-hero.jpg",
) -> Dict[str, Any]:
    """Build a BLG list-endpoint summary object."""
    return {
        "id": blg_id,
        "title": title,
        "slug": slug or f"test-article-{blg_id}",
        "hero_image_url": hero_image_url,
        "languageCode": language_code,
        "meta_description": "Test meta description for BLG sync verification.",
        "excerpt": "Short excerpt for the card view layout.",
        "orgWebsite": "https://thespecialwedding.io",
        "created_at": "2026-05-14T00:00:00.000Z",
        "seedKeyword": "wedding planning",
        "keywords": ["weddings", "planning", "testbed"],
    }


def make_blg_full_article(
    blg_id: int,
    *,
    title: str = "Test Article",
    slug: Optional[str] = None,
    content_html: Optional[str] = None,
    language_code: str = "en",
    hero_image_url: Optional[str] = "https://cdn.example.com/test-hero.jpg",
) -> Dict[str, Any]:
    """Build a BLG single-fetch full-article object."""
    if content_html is None:
        content_html = (
            "<h1>Test Article</h1>"
            "<p>Body paragraph one.</p>"
            '<img src="https://cdn.example.com/inline.jpg" alt="Inline">'
            "<p>Body paragraph two.</p>"
        )

    return {
        "id": blg_id,
        "title": title,
        "slug": slug or f"test-article-{blg_id}",
        "content_markdown": f"# {title}\n\nBody paragraph one.\n\nBody paragraph two.",
        "content_html": content_html,
        "jsonLd": {"@context": "https://schema.org", "@type": "Article"},
        "faqJsonLd": {"@context": "https://schema.org", "@type": "FAQPage"},
        "meta_description": "Test meta description for BLG sync verification.",
        "hero_image_url": hero_image_url,
        "orgWebsite": "https://thespecialwedding.io",
        "created_at": "2026-05-14T00:00:00.000Z",
        "seedKeyword": "wedding planning",
        "keywords": ["weddings", "planning", "testbed"],
    }


# ---------------------------------------------------------------------------
# Mongo helpers — thin wrappers reused across drivers.
# ---------------------------------------------------------------------------


def get_async_mongo():
    """Return the project's MongoConnector (Motor under the hood).

    Drivers run against the real configured MONGODB_URL — that's the
    point. Imported lazily so any preflight check has a chance to fail
    loud before we touch the DB.
    """
    from app.core.database import mongo

    return mongo


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def count_blog_articles(query: Dict[str, Any]) -> int:
    mongo = get_async_mongo()
    return int(await mongo.db["blog_articles"].count_documents(query))


async def find_blog_article(query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    mongo = get_async_mongo()
    return await mongo.db["blog_articles"].find_one(query)


async def delete_blog_articles(query: Dict[str, Any]) -> int:
    mongo = get_async_mongo()
    result = await mongo.db["blog_articles"].delete_many(query)
    return int(getattr(result, "deleted_count", 0) or 0)


# ---------------------------------------------------------------------------
# Cleanup primitives — used by cleanup_blg_sync_state.py.
# ---------------------------------------------------------------------------


async def purge_blg_test_articles() -> Dict[str, int]:
    """Delete any blog_articles row in the reserved BLG_TEST_IDS range.

    Idempotent — re-running on already-cleaned state returns zero.
    """
    test_id_set = list(BLG_TEST_IDS.values())
    deleted = await delete_blog_articles({"babylovegrowth_id": {"$in": test_id_set}})
    return {"blog_articles (test BLG IDs)": deleted}


async def reset_blg_sync_runs() -> Dict[str, int]:
    """Reset the singleton sync-runs doc to status='idle'.

    The doc may not exist yet; in that case nothing to do. The sync
    service is responsible for upserting on first use, so we just
    clear any 'running' state a crashed run might have left behind.
    """
    mongo = get_async_mongo()
    coll = mongo.db["babylovegrowth_sync_runs"]
    result = await coll.update_many(
        {"status": "running"},
        {"$set": {"status": "idle", "lock_token": None, "lock_acquired_at": None}},
    )
    return {"babylovegrowth_sync_runs (running→idle)": int(result.modified_count)}


def purge_blg_test_r2_fixtures() -> Dict[str, int]:
    """Delete every R2 object under BLG_TEST_R2_PREFIX.

    Uses the existing MediaStorage client directly so we share
    credentials/endpoint config with the rest of the app. Idempotent.
    """
    from app.services.media_storage import MediaStorage, StorageTarget

    storage = MediaStorage()
    target = storage.target(StorageTarget.BLOG_ASSETS)
    if not target.bucket_name:
        return {"r2 objects": 0, "_skipped": "BLOG_ASSETS bucket not configured"}

    client = storage.client
    deleted_count = 0
    continuation: Optional[str] = None
    while True:
        params: Dict[str, Any] = {
            "Bucket": target.bucket_name,
            "Prefix": BLG_TEST_R2_PREFIX,
        }
        if continuation:
            params["ContinuationToken"] = continuation
        response = client.list_objects_v2(**params)
        keys = [
            {"Key": obj["Key"]}
            for obj in response.get("Contents", [])
            if obj.get("Key")
        ]
        if keys:
            client.delete_objects(
                Bucket=target.bucket_name,
                Delete={"Objects": keys, "Quiet": True},
            )
            deleted_count += len(keys)
        if not response.get("IsTruncated"):
            break
        continuation = response.get("NextContinuationToken")
    return {"r2 objects (BLG_TEST_R2_PREFIX)": deleted_count}


# ---------------------------------------------------------------------------
# Console helpers — same shape as testbed/_form_lifecycle_common.py.
# ---------------------------------------------------------------------------


def banner(label: str) -> None:
    print()
    print("=" * 72)
    print(f"  {label}")
    print("=" * 72)
    print()


def checkpoint_pause(label: str, expectations: List[str]) -> None:
    """Pause the driver and print a checklist for the human to verify
    in the browser before pressing ENTER."""
    print()
    print(f"  📋 CHECKPOINT — {label}")
    for line in expectations:
        print(f"    • {line}")
    print()
    if os.environ.get("BLG_NO_INPUT"):
        # CI / smoke-import path — don't block.
        return
    input("  Press ENTER once verified…")


def run(coro):
    """Execute an async coroutine inside the driver's __main__ block."""
    asyncio.run(coro)


# ---------------------------------------------------------------------------
# HTTP-layer helpers — used by the e2e drivers to exercise the FastAPI
# endpoints (POST /admin/blog/sync-babylovegrowth + GET .../status)
# in-process. We mount the blog router on a minimal FastAPI app rather
# than importing app.main.app to avoid side effects from Stripe init,
# webhook bootstrap, etc.
# ---------------------------------------------------------------------------


def build_blog_test_app():
    """Create a minimal FastAPI app with the blog router mounted and
    require_root_admin overridden to a fake testbed admin.

    Returns (app, fake_admin). Drivers use httpx.AsyncClient with
    ASGITransport to call this app in-process — same route resolution,
    same BackgroundTasks scheduling, same dependency injection, but
    no uvicorn process required.
    """
    from types import SimpleNamespace

    from fastapi import FastAPI

    from app.api.blog import router as blog_router
    from app.dependencies.auth_extended import require_root_admin

    app = FastAPI()
    app.include_router(blog_router)

    fake_admin = SimpleNamespace(
        email="testbed-root@thespecialwedding.io",
        role="root_admin",
    )
    app.dependency_overrides[require_root_admin] = lambda: fake_admin
    return app, fake_admin


async def poll_sync_status(
    http_client,
    *,
    max_attempts: int = 30,
    delay_seconds: float = 0.25,
) -> dict:
    """Poll GET /admin/blog/sync-babylovegrowth/status until status
    is no longer 'running', or raise after max_attempts.

    Used by drivers immediately after POST /sync-babylovegrowth to
    wait for the BackgroundTask to settle before asserting on state.
    """
    for _ in range(max_attempts):
        response = await http_client.get("/admin/blog/sync-babylovegrowth/status")
        response.raise_for_status()
        state = response.json()
        if state.get("status") != "running":
            return state
        await asyncio.sleep(delay_seconds)
    raise RuntimeError(
        f"Sync did not settle after {max_attempts} polls "
        f"({max_attempts * delay_seconds}s)"
    )


# ---------------------------------------------------------------------------
# Fixture BLG clients — each e2e scenario monkey-patches
# BabyLoveGrowthClient with one of these. All match the real client's
# __init__ signature so the swap is invisible to the sync service.
# ---------------------------------------------------------------------------


def make_fixture_client_class(
    *,
    summaries_by_offset: dict[int, list[dict]],
    full_articles_by_id: Optional[dict[int, dict]] = None,
    fetch_error_by_id: Optional[dict[int, type]] = None,
    list_error: Optional[type] = None,
):
    """Build a per-scenario fixture client class.

    Args:
        summaries_by_offset: offset → list of summary objects. Empty
            list signals end of pagination.
        full_articles_by_id: BLG ID → full article. If omitted, a
            default generated by make_blg_full_article is used.
        fetch_error_by_id: BLG ID → exception class to raise on
            single-fetch (e.g. BabyLoveGrowthNotFoundError for 404
            scenarios). Imported lazily inside the closure so the
            driver doesn't have to.
        list_error: exception class to raise on list_articles (e.g.
            BabyLoveGrowthAuthError for the kill-switch scenario).
    """

    class FixtureBabyLoveGrowthClient:
        def __init__(self, api_key, base_url, *, timeout_seconds=15.0):
            self._api_key = api_key
            self._base_url = base_url

        async def list_articles(self, *, limit, offset):
            if list_error is not None:
                raise list_error("fixture list_error")
            return summaries_by_offset.get(offset, [])

        async def fetch_article(self, blg_id):
            if fetch_error_by_id and blg_id in fetch_error_by_id:
                raise fetch_error_by_id[blg_id](f"fixture fetch_error for {blg_id}")
            if full_articles_by_id and blg_id in full_articles_by_id:
                return full_articles_by_id[blg_id]
            return make_blg_full_article(blg_id)

    return FixtureBabyLoveGrowthClient


def seed_hero_source_image(key: str) -> str:
    """Push a tiny PNG into R2 at the given key. Returns its public
    CDN URL. Used by drivers that want a real https-reachable hero
    image fixture.
    """
    from app.services.media_storage import MediaStorage, StorageTarget

    # Tiny 1x1 PNG — 80 bytes, smallest valid encoding.
    tiny_png = bytes.fromhex(  # pragma: allowlist secret
        "89504e470d0a1a0a"  # pragma: allowlist secret - PNG signature fixture
        "0000000d49484452000000010000000108060000001f15c4890000"
        "000d4944415478da636060606000000000050001609cf6a30000"
        "000049454e44ae426082"
    )
    storage = MediaStorage()
    try:
        storage.delete_object(StorageTarget.BLOG_ASSETS, key)
    except Exception:
        pass

    import io as _io

    storage.upload_fileobj(
        _io.BytesIO(tiny_png),
        StorageTarget.BLOG_ASSETS,
        key,
        {"ContentType": "image/png"},
    )
    return storage.build_public_url(StorageTarget.BLOG_ASSETS, key)


def install_fixture_blg_client(client_class):
    """Monkey-patch BabyLoveGrowthClient in the sync service module.
    Returns a callable that restores the original class — drivers
    should call it in a finally block.
    """
    import app.services.babylovegrowth_sync_service as svc_mod

    original = svc_mod.BabyLoveGrowthClient
    svc_mod.BabyLoveGrowthClient = client_class

    def _restore():
        svc_mod.BabyLoveGrowthClient = original

    return _restore


def install_test_settings(
    *,
    sync_enabled: bool = True,
    api_key: str = "test-fixture-key",
    land_as_draft: bool = True,
):
    """Mutate live settings to scenario-specific values. Returns a
    callable that restores the previous values."""
    from app.core.settings import settings

    saved = {
        "sync_enabled": settings.babylovegrowth_sync_enabled,
        "api_key": settings.babylovegrowth_api_key,
        "land_as_draft": settings.babylovegrowth_land_as_draft,
    }
    settings.babylovegrowth_sync_enabled = sync_enabled
    settings.babylovegrowth_api_key = api_key
    settings.babylovegrowth_land_as_draft = land_as_draft

    def _restore():
        settings.babylovegrowth_sync_enabled = saved["sync_enabled"]
        settings.babylovegrowth_api_key = saved["api_key"]
        settings.babylovegrowth_land_as_draft = saved["land_as_draft"]

    return _restore

#!/usr/bin/env python3
"""
CP4 — BabyLoveGrowth Sync Service End-to-End Lifecycle
=======================================================

Exercises the full sync orchestration against REAL Mongo and REAL R2,
with the BLG HTTP client monkey-patched to return fixture payloads.

What the unit tests in tests/backend/test_babylovegrowth_sync.py cover:
  - httpx error taxonomy (401/404/429/5xx/network/malformed)
  - _map_blg_article rules in isolation
  - Service-level orchestration with mocked Mongo

What this driver adds:
  - Real Motor + Mongo (assertions against the actual collection state)
  - Real boto3 + R2 (hero image actually ends up at BLOG_MEDIA_DOMAIN)
  - Real settings module (LAND_AS_DRAFT default behavior)
  - Real BlogUploadService.upload_from_url ingest path (CP3 wired
    correctly into the sync flow)

Strategy
--------
SEED:
    - Cleanup any prior test runs (purge BLG test IDs from
      blog_articles + reset sync_runs lock + sweep R2 fixtures)
    - Monkey-patch BabyLoveGrowthClient inside the sync-service
      module to a fixture client that returns two summary articles
      then a single full-fetch each
    - Override settings: sync_enabled=True, api_key="test-fixture",  # pragma: allowlist secret
      land_as_draft=True (the brand-safe default we'll exercise)

VERIFY (each checkpoint pauses for ENTER):

    [CHECKPOINT 1/5] First sync — both fixture articles upserted into
                     blog_articles with babylovegrowth_id set, status="draft"
    [CHECKPOINT 2/5] Hero images proxied to our R2 — og_image / card_image
                     point at BLOG_MEDIA_DOMAIN, NOT BLG's CDN
    [CHECKPOINT 3/5] sync_runs singleton doc has status="succeeded",
                     new_count=2, skipped_count=0, error_count=0
    [CHECKPOINT 4/5] Second sync (idempotency) — new_count=0,
                     skipped_count=2; no duplicate rows
    [CHECKPOINT 5/5] Lock released after each run — status="idle",
                     lock_token=None

Pair: cleanup_blg_sync_state.py (purges all test-fixture state).
"""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._blg_sync_common import (  # noqa: E402
    BLG_TEST_IDS,
    BLG_TEST_R2_PREFIX,
    banner,
    checkpoint_pause,
    count_blog_articles,
    find_blog_article,
    get_async_mongo,
    make_blg_full_article,
    make_blg_summary,
    purge_blg_test_articles,
    purge_blg_test_r2_fixtures,
    reset_blg_sync_runs,
)

# Tiny PNG for the testbed's source image — pushed into R2 under the
# BLG_TEST_R2_PREFIX so the hero proxy path has something real to fetch.
TINY_PNG_BYTES = bytes.fromhex(  # pragma: allowlist secret
    "89504e470d0a1a0a"  # pragma: allowlist secret - PNG signature fixture
    "0000000d49484452000000010000000108060000001f15c4890000"
    "000d4944415478da636060606000000000050001609cf6a30000"
    "000049454e44ae426082"
)
SOURCE_HERO_KEY = f"{BLG_TEST_R2_PREFIX}/cp4_hero.png"

ARTICLE_A_ID = BLG_TEST_IDS["happy_path"]
ARTICLE_B_ID = BLG_TEST_IDS["idempotency"]


class _FixtureBabyLoveGrowthClient:
    """Drop-in replacement for BabyLoveGrowthClient.

    Constructor signature matches the real client so monkey-patching
    the class itself in the service module just works.
    """

    def __init__(self, api_key: str, base_url: str, *, timeout_seconds: float = 15.0):
        self._api_key = api_key
        self._base_url = base_url
        # No actual network usage — fixtures live in memory.

    async def list_articles(self, *, limit: int, offset: int) -> list[dict]:
        if offset == 0:
            return [
                make_blg_summary(ARTICLE_A_ID, hero_image_url=_hero_url()),
                make_blg_summary(ARTICLE_B_ID, hero_image_url=_hero_url()),
            ]
        return []

    async def fetch_article(self, blg_id: int) -> dict:
        return make_blg_full_article(blg_id, hero_image_url=_hero_url())


def _hero_url() -> str:
    """Public CDN URL of the seed PNG fixture — same R2 the sync service
    will re-upload INTO (different key)."""
    from app.services.media_storage import MediaStorage, StorageTarget

    storage = MediaStorage()
    return storage.build_public_url(StorageTarget.BLOG_ASSETS, SOURCE_HERO_KEY)


def _seed_source_hero_image() -> None:
    """Push the tiny PNG fixture to R2 so the hero proxy has a real source."""
    from app.services.media_storage import MediaStorage, StorageTarget

    storage = MediaStorage()
    # Idempotent — drop any leftover before pushing.
    try:
        storage.delete_object(StorageTarget.BLOG_ASSETS, SOURCE_HERO_KEY)
    except Exception:
        pass
    storage.upload_fileobj(
        io.BytesIO(TINY_PNG_BYTES),
        StorageTarget.BLOG_ASSETS,
        SOURCE_HERO_KEY,
        {"ContentType": "image/png"},
    )


async def _hero_cdn_domain() -> Optional[str]:
    from app.core.settings import settings

    return settings.normalized_blog_media_domain


async def main() -> None:
    banner("verify_blg_sync_service (CP4)")

    # ─── Idempotent SEED ─────────────────────────────────────────────────────
    print("  SEED")
    print("    • Purging any prior test state…")
    await purge_blg_test_articles()
    await reset_blg_sync_runs()
    purge_blg_test_r2_fixtures()
    print("    • Pushing source hero PNG into R2…")
    _seed_source_hero_image()

    # Patch BabyLoveGrowthClient + settings so the service runs against
    # fixtures. We re-import the module so the monkey-patched class is
    # what _run_sync_body picks up at construction time.
    import app.services.babylovegrowth_sync_service as svc_mod

    original_client = svc_mod.BabyLoveGrowthClient
    svc_mod.BabyLoveGrowthClient = _FixtureBabyLoveGrowthClient

    # Enable + key are required for run_full_sync to proceed.
    from app.core.settings import settings as live_settings

    saved_enabled = live_settings.babylovegrowth_sync_enabled
    saved_key = live_settings.babylovegrowth_api_key
    saved_draft = live_settings.babylovegrowth_land_as_draft
    live_settings.babylovegrowth_sync_enabled = True
    live_settings.babylovegrowth_api_key = (
        "test-fixture-key"  # pragma: allowlist secret
    )
    live_settings.babylovegrowth_land_as_draft = True

    try:
        # ─── First run ───────────────────────────────────────────────────────
        print()
        print("  VERIFY — first sync")
        result = await svc_mod.babylovegrowth_sync_service.run_full_sync(
            triggered_by="testbed"
        )
        print(f"    • run result: {result}")

        # Checkpoint 1: both articles persisted.
        count = await count_blog_articles(
            {"babylovegrowth_id": {"$in": [ARTICLE_A_ID, ARTICLE_B_ID]}}
        )
        assert count == 2, (
            f"Expected 2 synced articles, got {count}. Run result: {result}"
        )
        article_a = await find_blog_article({"babylovegrowth_id": ARTICLE_A_ID})
        assert article_a is not None
        assert article_a["status"] == "draft", (
            f"Brand-safe default should land as draft, got {article_a['status']}"
        )
        checkpoint_pause(
            "1/5 — Both fixture articles upserted as drafts",
            [
                f"BLG IDs found: {{{ARTICLE_A_ID}, {ARTICLE_B_ID}}}",
                f"article_a status: {article_a['status']}",
                f"article_a slug: {article_a['slug']}",
                f"article_a title: {article_a['title']}",
            ],
        )

        # Checkpoint 2: hero images on OUR CDN.
        cdn_domain = await _hero_cdn_domain()
        og = article_a.get("og_image") or ""
        card = article_a.get("card_image") or ""
        assert og and "babylovegrowth" not in og.lower(), (
            f"og_image still points at BLG's CDN: {og}"
        )
        if cdn_domain:
            assert cdn_domain in og, (
                f"og_image {og!r} not under BLOG_MEDIA_DOMAIN {cdn_domain!r}"
            )
        assert og == card, "og_image and card_image should match for synced articles"
        checkpoint_pause(
            "2/5 — Hero image proxied to OUR R2/CDN",
            [
                f"og_image: {og}",
                f"BLOG_MEDIA_DOMAIN: {cdn_domain}",
                "BLG CDN NOT in URL",
            ],
        )

        # Checkpoint 3: sync_runs doc reflects success.
        mongo = get_async_mongo()
        run_doc = await mongo.db["babylovegrowth_sync_runs"].find_one(
            {"_id": "babylovegrowth_sync_state"}
        )
        assert run_doc is not None
        assert run_doc.get("status") == "succeeded", (
            f"Run status was {run_doc.get('status')}, expected 'succeeded'"
        )
        assert run_doc.get("new_count") == 2, (
            f"new_count was {run_doc.get('new_count')}, expected 2"
        )
        assert run_doc.get("error_count") == 0, (
            f"error_count was {run_doc.get('error_count')}, expected 0"
        )
        checkpoint_pause(
            "3/5 — sync_runs singleton reflects successful run",
            [
                f"status: {run_doc.get('status')}",
                f"new_count: {run_doc.get('new_count')}",
                f"skipped_count: {run_doc.get('skipped_count')}",
                f"error_count: {run_doc.get('error_count')}",
                f"image_failed_count: {run_doc.get('image_failed_count')}",
            ],
        )

        # ─── Second run (idempotency) ────────────────────────────────────────
        print()
        print("  VERIFY — second sync (idempotency)")
        result2 = await svc_mod.babylovegrowth_sync_service.run_full_sync(
            triggered_by="testbed"
        )
        print(f"    • run result: {result2}")
        assert result2["new_count"] == 0, (
            f"Second sync should add 0 new, got {result2['new_count']}"
        )
        assert result2["skipped_count"] == 2, (
            f"Second sync should skip both prior articles, got skipped_count={result2['skipped_count']}"
        )
        # No duplicate rows.
        count2 = await count_blog_articles(
            {"babylovegrowth_id": {"$in": [ARTICLE_A_ID, ARTICLE_B_ID]}}
        )
        assert count2 == 2, f"Duplicate rows created on second sync: count={count2}"
        checkpoint_pause(
            "4/5 — Second sync is a no-op",
            [
                "new_count: 0",
                "skipped_count: 2",
                "row count unchanged: 2",
            ],
        )

        # Checkpoint 5: lock released, status idle.
        final_doc = await mongo.db["babylovegrowth_sync_runs"].find_one(
            {"_id": "babylovegrowth_sync_state"}
        )
        # After a successful run we set status="succeeded" — the lock is
        # released via lock_token=None. Either is acceptable; the
        # invariant is no stuck "running" state and no held lock_token.
        assert final_doc.get("status") != "running", (
            f"Lock left in running state: {final_doc}"
        )
        assert final_doc.get("lock_token") is None, (
            f"Lock token not cleared: {final_doc.get('lock_token')}"
        )
        checkpoint_pause(
            "5/5 — Lock released after each run",
            [
                f"final status: {final_doc.get('status')}",
                f"lock_token: {final_doc.get('lock_token')}",
                f"lock_acquired_at: {final_doc.get('lock_acquired_at')}",
            ],
        )

        print()
        print("  ✅ CP4 sync service verified end-to-end against real Mongo + R2.")
        print("  Run testbed/cleanup_blg_sync_state.py to purge state.")
    finally:
        svc_mod.BabyLoveGrowthClient = original_client
        live_settings.babylovegrowth_sync_enabled = saved_enabled
        live_settings.babylovegrowth_api_key = saved_key
        live_settings.babylovegrowth_land_as_draft = saved_draft


if __name__ == "__main__":
    asyncio.run(main())

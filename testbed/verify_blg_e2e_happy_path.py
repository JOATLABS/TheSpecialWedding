#!/usr/bin/env python3
"""
E2E #1/6 — Happy Path Through The FastAPI Endpoint
==================================================

Exercises the full integration end-to-end via the HTTP layer:

    cron / Etastic
       │
       ▼  POST /admin/blog/sync-babylovegrowth   (require_root_admin)
    FastAPI route
       │
       ▼  BackgroundTasks.add_task(run_full_sync, triggered_by="manual")
    BabyLoveGrowthSyncService.run_full_sync
       │
       ▼  BabyLoveGrowthClient (fixture) → list + fetch
       ▼  BlogUploadService.upload_from_url → real R2 PUT
       ▼  upsert into blog_articles
       ▼  finalize_run → babylovegrowth_sync_runs.status="succeeded"
       │
       ▼  GET /admin/blog/sync-babylovegrowth/status
    Driver asserts everything is in the expected state.

What CP4 testbed already does: calls the sync service directly
against real Mongo + R2. What this driver adds: the HTTP route,
dependency injection, BackgroundTasks scheduling, and JSON
response shape on the way out.

Strategy
--------
SEED:
    - Cleanup prior test state (blog_articles by BLG_TEST_IDS,
      sync_runs lock, R2 fixtures).
    - Push a source hero PNG into R2 — gives the sync's
      upload_from_url call a real https-reachable URL to fetch.
    - Monkey-patch BabyLoveGrowthClient with a fixture that returns
      a single article with that hero URL.
    - Override settings: sync_enabled=True, land_as_draft=True.

VERIFY:

    [CHECKPOINT 1/4] POST returns 202-shaped accepted body
    [CHECKPOINT 2/4] After poll, status endpoint reports
                     status="succeeded", new_count=1, error_count=0
    [CHECKPOINT 3/4] blog_articles row exists with status="draft"
                     (brand-safe default), babylovegrowth_id set,
                     and hero re-hosted on BLOG_MEDIA_DOMAIN
    [CHECKPOINT 4/4] Lock released — status doc has lock_token=None

Pair: cleanup_blg_sync_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import httpx  # noqa: E402

from testbed._blg_sync_common import (  # noqa: E402
    BLG_TEST_IDS,
    BLG_TEST_R2_PREFIX,
    banner,
    build_blog_test_app,
    checkpoint_pause,
    find_blog_article,
    install_fixture_blg_client,
    install_test_settings,
    make_blg_summary,
    make_fixture_client_class,
    poll_sync_status,
    purge_blg_test_articles,
    purge_blg_test_r2_fixtures,
    reset_blg_sync_runs,
    seed_hero_source_image,
)

ARTICLE_ID = BLG_TEST_IDS["happy_path"]
SOURCE_KEY = f"{BLG_TEST_R2_PREFIX}/e2e_happy_hero.png"


async def main() -> None:
    banner("verify_blg_e2e_happy_path (E2E #1/6)")

    # ─── SEED ────────────────────────────────────────────────────────────────
    print("  SEED")
    print("    • Purging prior test state…")
    await purge_blg_test_articles()
    await reset_blg_sync_runs()
    purge_blg_test_r2_fixtures()
    print("    • Pushing source hero PNG to R2…")
    source_hero_url = seed_hero_source_image(SOURCE_KEY)
    print(f"    • Hero source URL: {source_hero_url}")

    FixtureClient = make_fixture_client_class(
        summaries_by_offset={
            0: [make_blg_summary(ARTICLE_ID, hero_image_url=source_hero_url)],
            50: [],
        },
    )
    restore_client = install_fixture_blg_client(FixtureClient)
    restore_settings = install_test_settings()

    try:
        app, _ = build_blog_test_app()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # Checkpoint 1: POST returns 202-shaped accepted body.
            print()
            print("  VERIFY")
            response = await client.post("/admin/blog/sync-babylovegrowth")
            assert response.status_code == 200, (
                f"POST returned {response.status_code} expected 200: {response.text}"
            )
            body = response.json()
            assert body.get("status") == "accepted", body
            checkpoint_pause(
                "1/4 — POST /sync-babylovegrowth accepted",
                [
                    f"HTTP status: {response.status_code}",
                    f"response body: {body}",
                ],
            )

            # Checkpoint 2: background task completed, status reports success.
            state = await poll_sync_status(client)
            assert state.get("status") == "succeeded", (
                f"Expected status=succeeded, got: {state}"
            )
            assert state.get("new_count") == 1, f"Expected new_count=1, got: {state}"
            assert state.get("error_count") == 0, (
                f"Expected error_count=0, got: {state}"
            )
            checkpoint_pause(
                "2/4 — GET /status reports successful sync",
                [
                    f"status: {state.get('status')}",
                    f"new_count: {state.get('new_count')}",
                    f"skipped_count: {state.get('skipped_count')}",
                    f"image_failed_count: {state.get('image_failed_count')}",
                    f"error_count: {state.get('error_count')}",
                ],
            )

            # Checkpoint 3: article persisted with the right defaults.
            article = await find_blog_article({"babylovegrowth_id": ARTICLE_ID})
            assert article is not None, "Article not in blog_articles"
            assert article["status"] == "draft", (
                f"Brand-safe default land_as_draft expected, got {article['status']}"
            )
            assert article.get("og_image"), "og_image missing"
            from app.core.settings import settings as _settings

            cdn_domain = _settings.normalized_blog_media_domain or ""
            if cdn_domain:
                assert cdn_domain in article["og_image"], (
                    f"og_image {article['og_image']!r} not under "
                    f"BLOG_MEDIA_DOMAIN {cdn_domain!r} — hero proxy broken"
                )
            checkpoint_pause(
                "3/4 — Article persisted with brand-safe defaults",
                [
                    f"slug: {article['slug']}",
                    f"status: {article['status']}",
                    f"babylovegrowth_id: {article['babylovegrowth_id']}",
                    f"og_image: {article['og_image']}",
                    f"BLOG_MEDIA_DOMAIN: {cdn_domain}",
                ],
            )

            # Checkpoint 4: lock released, sync_runs doc reflects idle.
            final_state = await client.get("/admin/blog/sync-babylovegrowth/status")
            final_doc = final_state.json()
            assert final_doc.get("lock_token") is None, (
                f"Lock token not cleared: {final_doc.get('lock_token')}"
            )
            assert final_doc.get("status") != "running", final_doc
            checkpoint_pause(
                "4/4 — Lock released after run completes",
                [
                    f"status: {final_doc.get('status')}",
                    f"lock_token: {final_doc.get('lock_token')}",
                ],
            )

        print()
        print("  ✅ E2E happy path verified through FastAPI route.")
        print("  Run testbed/cleanup_blg_sync_state.py to purge fixtures.")
    finally:
        restore_settings()
        restore_client()


if __name__ == "__main__":
    asyncio.run(main())

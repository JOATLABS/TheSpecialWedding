#!/usr/bin/env python3
"""
E2E #4/6 — Hero Image Failure Persists Article Without Image
============================================================

Mockup contract: if the hero image fetch fails (404, oversized, wrong
content-type, network error), the sync logs and continues with
og_image=None / card_image=None — it does NOT fail the article. The
image is non-essential; what matters is the body content reaches our
readers.

This driver exercises the full FastAPI → BackgroundTasks →
BlogUploadService.upload_from_url path with a deliberately-broken
hero URL, and verifies the article still lands (just imageless).

Strategy
--------
SEED:
    - Cleanup state.
    - DO NOT seed a hero image to R2. Instead, fixture client points
      hero_image_url at a known-bad URL (e.g. a URL that will 404).
    - One fixture article with that bad hero URL.

VERIFY:

    [CHECKPOINT 1/4] POST returns 202; sync completes
    [CHECKPOINT 2/4] Status reports new_count=1, image_failed_count=1
                     (NOT error_count — image failure is not an article
                     error)
    [CHECKPOINT 3/4] blog_articles row exists with og_image=None and
                     card_image=None — but title, slug, content all
                     populated normally
    [CHECKPOINT 4/4] Final run status is "succeeded", not "partial" or
                     "failed" (image failure ≠ article failure)

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
)

ARTICLE_ID = BLG_TEST_IDS["image_failure"]
# Deliberately unreachable URL: example.com/<random-nonexistent-path>
# returns a 404-or-similar. The upload_from_url method treats any
# non-200 as a BlogUploadFromUrlError, which the sync catches and
# downgrades to image_failed_count++.
BROKEN_HERO_URL = "https://example.com/this-path-does-not-exist-cp-e2e-4.jpg"


async def main() -> None:
    banner("verify_blg_e2e_image_failure (E2E #4/6)")

    print("  SEED")
    await purge_blg_test_articles()
    await reset_blg_sync_runs()
    purge_blg_test_r2_fixtures()

    FixtureClient = make_fixture_client_class(
        summaries_by_offset={
            0: [make_blg_summary(ARTICLE_ID, hero_image_url=BROKEN_HERO_URL)],
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
            print()
            print("  VERIFY")

            response = await client.post("/admin/blog/sync-babylovegrowth")
            assert response.status_code == 200, response.text
            checkpoint_pause(
                "1/4 — POST accepted; sync running in background",
                [f"response: {response.json()}"],
            )

            state = await poll_sync_status(client)
            assert state["new_count"] == 1, (
                f"Article should still persist despite image failure, "
                f"new_count={state['new_count']}"
            )
            assert state["image_failed_count"] == 1, (
                f"image_failed_count should be 1, got {state['image_failed_count']}"
            )
            assert state["error_count"] == 0, (
                f"Image failure must not count as an article error; "
                f"got error_count={state['error_count']}"
            )
            checkpoint_pause(
                "2/4 — Image failure counted separately from errors",
                [
                    f"new_count: {state['new_count']}",
                    f"image_failed_count: {state['image_failed_count']}",
                    f"error_count: {state['error_count']}",
                ],
            )

            article = await find_blog_article({"babylovegrowth_id": ARTICLE_ID})
            assert article is not None, "Article missing from blog_articles"
            assert article.get("og_image") is None, (
                f"og_image should be None after fetch failure, got {article.get('og_image')}"
            )
            assert article.get("card_image") is None, (
                f"card_image should be None after fetch failure, got {article.get('card_image')}"
            )
            # Body content + metadata should still be present.
            assert article.get("title"), "Title missing"
            assert article.get("content"), "Content missing"
            assert article.get("slug"), "Slug missing"
            checkpoint_pause(
                "3/4 — Article persisted imageless with body intact",
                [
                    f"slug: {article['slug']}",
                    f"title: {article['title']}",
                    f"og_image: {article.get('og_image')}",
                    f"card_image: {article.get('card_image')}",
                    f"content length: {len(article.get('content') or '')}",
                ],
            )

            assert state["status"] == "succeeded", (
                f"Run should be 'succeeded' since image failure is not "
                f"an article error; got status={state['status']}"
            )
            checkpoint_pause(
                "4/4 — Run status is succeeded (image ≠ article failure)",
                [f"status: {state['status']}"],
            )

        print()
        print("  ✅ E2E image-failure path verified.")
    finally:
        restore_settings()
        restore_client()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
E2E #6/6 — Non-English Articles Are Dropped By The Language Filter
==================================================================

Mockup contract: BLG can generate non-English articles, but
blog_articles has no i18n column. v1 filter: drop anything where
`languageCode != "en"` with skipped_count++ and a logger.info, NOT
an error. The article never reaches Mongo, the run still counts as
successful.

This driver exercises a mixed-language fixture batch (one `en`,
one `es`, one `fr`) and verifies the en one syncs while the others
are silently skipped.

Strategy
--------
SEED:
    - Cleanup state.
    - Seed source hero PNG.
    - Fixture client returns three summary articles:
        • English (en) → should be persisted
        • Spanish (es) → should be skipped
        • French  (fr) → should be skipped
      Only the English single-fetch is wired so a code regression
      that incorrectly fetched the non-English ones would 404.

VERIFY:

    [CHECKPOINT 1/4] POST returns accepted; sync completes
    [CHECKPOINT 2/4] Status reports new_count=1, skipped_count=2,
                     error_count=0 (skip is not an error)
    [CHECKPOINT 3/4] Only the English article exists in blog_articles
                     (no rows with babylovegrowth_id == es_id or fr_id)
    [CHECKPOINT 4/4] Run finalized "succeeded" (filtered articles
                     are not failures)

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
    count_blog_articles,
    find_blog_article,
    install_fixture_blg_client,
    install_test_settings,
    make_blg_full_article,
    make_blg_summary,
    make_fixture_client_class,
    poll_sync_status,
    purge_blg_test_articles,
    purge_blg_test_r2_fixtures,
    reset_blg_sync_runs,
    seed_hero_source_image,
)

EN_ID = BLG_TEST_IDS["language_filter"]
ES_ID = BLG_TEST_IDS["lock_contention_a"]  # Reusing slot — we'll purge below.
FR_ID = BLG_TEST_IDS["lock_contention_b"]
SOURCE_KEY = f"{BLG_TEST_R2_PREFIX}/e2e_lang_hero.png"


async def main() -> None:
    banner("verify_blg_e2e_language_filter (E2E #6/6)")

    print("  SEED")
    await purge_blg_test_articles()
    await reset_blg_sync_runs()
    purge_blg_test_r2_fixtures()
    source_hero_url = seed_hero_source_image(SOURCE_KEY)

    FixtureClient = make_fixture_client_class(
        summaries_by_offset={
            0: [
                make_blg_summary(EN_ID, language="en", hero_image_url=source_hero_url),
                make_blg_summary(ES_ID, language="es", hero_image_url=source_hero_url),
                make_blg_summary(FR_ID, language="fr", hero_image_url=source_hero_url),
            ],
            50: [],
        },
        # Only wire the EN full article — if a regression caused the
        # service to try fetching es/fr full content despite the filter,
        # this would surface as a missing-article error rather than
        # silently passing.
        full_articles_by_id={
            EN_ID: make_blg_full_article(EN_ID, hero_image_url=source_hero_url),
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
                "1/4 — POST accepted; mixed-language sync runs",
                [f"response: {response.json()}"],
            )

            state = await poll_sync_status(client)
            assert state["new_count"] == 1, (
                f"Only the EN article should be persisted, got "
                f"new_count={state['new_count']}"
            )
            assert state["skipped_count"] == 2, (
                f"Both non-EN articles should be skipped, got "
                f"skipped_count={state['skipped_count']}"
            )
            assert state["error_count"] == 0, (
                f"Language filter must not generate errors; "
                f"got error_count={state['error_count']}"
            )
            checkpoint_pause(
                "2/4 — Counts: 1 new, 2 skipped, 0 errors",
                [
                    f"new_count: {state['new_count']}",
                    f"skipped_count: {state['skipped_count']}",
                    f"error_count: {state['error_count']}",
                ],
            )

            # Checkpoint 3: only EN landed.
            en_article = await find_blog_article({"babylovegrowth_id": EN_ID})
            assert en_article is not None, "EN article missing from blog_articles"
            es_article = await find_blog_article({"babylovegrowth_id": ES_ID})
            fr_article = await find_blog_article({"babylovegrowth_id": FR_ID})
            assert es_article is None, (
                f"ES article should NOT be in blog_articles, found: {es_article}"
            )
            assert fr_article is None, (
                f"FR article should NOT be in blog_articles, found: {fr_article}"
            )
            row_count = await count_blog_articles(
                {"babylovegrowth_id": {"$in": [EN_ID, ES_ID, FR_ID]}}
            )
            assert row_count == 1, (
                f"Expected exactly 1 BLG row (EN only), got {row_count}"
            )
            checkpoint_pause(
                "3/4 — Only the EN article reached blog_articles",
                [
                    f"EN ({EN_ID}) present: {bool(en_article)}",
                    f"ES ({ES_ID}) present: {bool(es_article)}",
                    f"FR ({FR_ID}) present: {bool(fr_article)}",
                    f"row count: {row_count}",
                ],
            )

            assert state["status"] == "succeeded", (
                f"Filtered articles aren't failures; run should be "
                f"'succeeded', got status={state['status']}"
            )
            checkpoint_pause(
                "4/4 — Run status is succeeded (filters ≠ failures)",
                [f"status: {state['status']}"],
            )

        print()
        print("  ✅ E2E language filter verified.")
    finally:
        restore_settings()
        restore_client()


if __name__ == "__main__":
    asyncio.run(main())

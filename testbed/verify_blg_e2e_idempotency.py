#!/usr/bin/env python3
"""
E2E #2/6 — Idempotency Across Multiple Sync Runs
================================================

Verifies that running the sync twice through the HTTP endpoint
produces zero duplicate rows. The unique sparse index
idx_blog_babylovegrowth_id_unique enforces this at the DB layer; this
driver proves the service correctly skips known IDs *before* attempting
the upsert, so we don't waste BLG quota or R2 PUTs on dupes.

Strategy
--------
SEED:
    - Cleanup state.
    - Seed source hero PNG.
    - Fixture client: returns 2 articles on first list call. To make
      idempotency observable, the SAME 2 articles are returned on the
      second sync run too.

VERIFY:

    [CHECKPOINT 1/4] First sync → status=succeeded, new_count=2,
                     skipped_count=0
    [CHECKPOINT 2/4] blog_articles has exactly 2 rows in the BLG test
                     range
    [CHECKPOINT 3/4] Second sync (same fixtures) → status=succeeded,
                     new_count=0, skipped_count=2; no second upsert
    [CHECKPOINT 4/4] blog_articles row count UNCHANGED at 2

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

ARTICLE_A = BLG_TEST_IDS["happy_path"]
ARTICLE_B = BLG_TEST_IDS["idempotency"]
SOURCE_KEY = f"{BLG_TEST_R2_PREFIX}/e2e_idempo_hero.png"


async def main() -> None:
    banner("verify_blg_e2e_idempotency (E2E #2/6)")

    print("  SEED")
    await purge_blg_test_articles()
    await reset_blg_sync_runs()
    purge_blg_test_r2_fixtures()
    source_hero_url = seed_hero_source_image(SOURCE_KEY)
    print(f"    • hero source: {source_hero_url}")

    # Same two summaries on every list call so reruns expose the
    # idempotency contract.
    summaries = [
        make_blg_summary(ARTICLE_A, hero_image_url=source_hero_url),
        make_blg_summary(ARTICLE_B, hero_image_url=source_hero_url),
    ]
    FixtureClient = make_fixture_client_class(
        summaries_by_offset={0: summaries, 50: []},
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

            # First sync.
            await client.post("/admin/blog/sync-babylovegrowth")
            state1 = await poll_sync_status(client)
            assert state1["new_count"] == 2, state1
            assert state1["skipped_count"] == 0, state1
            checkpoint_pause(
                "1/4 — First sync inserted both fixtures",
                [
                    f"new_count: {state1['new_count']}",
                    f"skipped_count: {state1['skipped_count']}",
                    f"status: {state1['status']}",
                ],
            )

            count1 = await count_blog_articles(
                {"babylovegrowth_id": {"$in": [ARTICLE_A, ARTICLE_B]}}
            )
            assert count1 == 2, f"Expected 2 rows, got {count1}"
            checkpoint_pause(
                "2/4 — blog_articles has exactly 2 BLG rows",
                [f"row count: {count1}"],
            )

            # Second sync — must be a no-op.
            await client.post("/admin/blog/sync-babylovegrowth")
            state2 = await poll_sync_status(client)
            assert state2["new_count"] == 0, (
                f"Idempotency broken: second sync inserted {state2['new_count']}"
            )
            assert state2["skipped_count"] == 2, (
                f"Expected skipped_count=2, got {state2['skipped_count']}"
            )
            checkpoint_pause(
                "3/4 — Second sync is a no-op",
                [
                    f"new_count: {state2['new_count']}",
                    f"skipped_count: {state2['skipped_count']}",
                ],
            )

            count2 = await count_blog_articles(
                {"babylovegrowth_id": {"$in": [ARTICLE_A, ARTICLE_B]}}
            )
            assert count2 == 2, (
                f"Duplicate rows on second sync: count went {count1}→{count2}"
            )
            checkpoint_pause(
                "4/4 — Row count UNCHANGED after second sync",
                [f"row count: {count2} (same as before)"],
            )

        print()
        print("  ✅ E2E idempotency verified through FastAPI route.")
    finally:
        restore_settings()
        restore_client()


if __name__ == "__main__":
    asyncio.run(main())

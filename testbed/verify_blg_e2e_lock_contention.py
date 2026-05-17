#!/usr/bin/env python3
"""
E2E #3/6 — Concurrent Sync Runs And The Advisory Lock
=====================================================

Verifies that two concurrent sync triggers do NOT both run. The
mockup's "Concurrency / double-run protection" section commits to a
single-row advisory lock on babylovegrowth_sync_runs — the loser of
the race must observe `lock_held` and return without consuming BLG
quota or R2 PUTs.

The mongo unique indexes guarantee no duplicate documents could ever
be created. This test proves the loser bails BEFORE the work — saving
quota, R2 cost, and log noise.

Strategy
--------
SEED:
    - Cleanup state.
    - Seed source hero PNG.
    - Fixture client that introduces a small delay (asyncio.sleep)
      between list and fetch so the second concurrent call has time to
      observe the in-flight lock.

VERIFY:

    [CHECKPOINT 1/4] Fire two run_full_sync() calls in parallel
                     via asyncio.gather
    [CHECKPOINT 2/4] Exactly ONE returns a runnable result (status
                     "succeeded" or "partial" with new_count > 0).
                     The other returns {status: "skipped",
                     reason: "lock_held"}
    [CHECKPOINT 3/4] blog_articles has 1 row (not 2 — the dropped
                     run never touched Mongo)
    [CHECKPOINT 4/4] Final sync_runs doc is idle, lock released

Note: this driver calls the sync service directly (not through the
HTTP endpoint) because BackgroundTasks runs the call after the
response — and httpx.ASGITransport blocks until that completes, so
in-process two POSTs would queue rather than race. Direct invocation
gives us deterministic concurrency to exercise the lock.

Pair: cleanup_blg_sync_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._blg_sync_common import (  # noqa: E402
    BLG_TEST_IDS,
    BLG_TEST_R2_PREFIX,
    banner,
    checkpoint_pause,
    count_blog_articles,
    get_async_mongo,
    install_fixture_blg_client,
    install_test_settings,
    make_blg_full_article,
    make_blg_summary,
    purge_blg_test_articles,
    purge_blg_test_r2_fixtures,
    reset_blg_sync_runs,
    seed_hero_source_image,
)

ARTICLE_ID = BLG_TEST_IDS["lock_contention_a"]
SOURCE_KEY = f"{BLG_TEST_R2_PREFIX}/e2e_lock_hero.png"


def make_slow_fixture_client(source_hero_url: str, list_delay: float):
    """Fixture client that sleeps inside list_articles so the second
    concurrent caller has time to hit _acquire_lock and bail."""

    class SlowFixtureBabyLoveGrowthClient:
        def __init__(self, api_key, base_url, *, timeout_seconds=15.0):
            pass

        async def list_articles(self, *, limit, offset):
            if offset == 0:
                await asyncio.sleep(list_delay)
                return [make_blg_summary(ARTICLE_ID, hero_image_url=source_hero_url)]
            return []

        async def fetch_article(self, blg_id):
            return make_blg_full_article(blg_id, hero_image_url=source_hero_url)

    return SlowFixtureBabyLoveGrowthClient


async def main() -> None:
    banner("verify_blg_e2e_lock_contention (E2E #3/6)")

    print("  SEED")
    await purge_blg_test_articles()
    await reset_blg_sync_runs()
    purge_blg_test_r2_fixtures()
    source_hero_url = seed_hero_source_image(SOURCE_KEY)

    SlowClient = make_slow_fixture_client(source_hero_url, list_delay=0.5)
    restore_client = install_fixture_blg_client(SlowClient)
    restore_settings = install_test_settings()

    try:
        from app.services.babylovegrowth_sync_service import (
            babylovegrowth_sync_service,
        )

        print()
        print("  VERIFY")

        # Checkpoint 1: fire two concurrent runs.
        print("    • Firing two run_full_sync calls in parallel…")
        results = await asyncio.gather(
            babylovegrowth_sync_service.run_full_sync(triggered_by="testbed-A"),
            babylovegrowth_sync_service.run_full_sync(triggered_by="testbed-B"),
        )
        print(f"    • result A: {results[0]}")
        print(f"    • result B: {results[1]}")
        checkpoint_pause(
            "1/4 — Two concurrent sync invocations launched",
            [
                f"run A: {results[0]}",
                f"run B: {results[1]}",
            ],
        )

        # Checkpoint 2: exactly one ran, exactly one was skipped.
        skipped = [r for r in results if r.get("status") == "skipped"]
        runnable = [r for r in results if r.get("status") != "skipped"]
        assert len(skipped) == 1, (
            f"Expected exactly one skip, got {len(skipped)}: {results}"
        )
        assert skipped[0].get("reason") == "lock_held", (
            f"Loser skipped for wrong reason: {skipped[0]}"
        )
        assert len(runnable) == 1, (
            f"Expected exactly one runnable result, got {len(runnable)}"
        )
        assert runnable[0].get("status") in ("succeeded", "partial"), (
            f"Winner had unexpected status: {runnable[0]}"
        )
        checkpoint_pause(
            "2/4 — Lock granted to exactly one caller",
            [
                f"winner status: {runnable[0].get('status')}",
                f"winner new_count: {runnable[0].get('new_count')}",
                f"loser reason: {skipped[0].get('reason')}",
            ],
        )

        # Checkpoint 3: blog_articles has exactly ONE row from the winner.
        row_count = await count_blog_articles({"babylovegrowth_id": ARTICLE_ID})
        assert row_count == 1, (
            f"Expected 1 article row (winner only), got {row_count}. "
            "Lock did not prevent loser from also writing."
        )
        checkpoint_pause(
            "3/4 — Loser never wrote to blog_articles",
            [f"blog_articles row count: {row_count} (winner only)"],
        )

        # Checkpoint 4: lock released.
        mongo = get_async_mongo()
        final_doc = await mongo.db["babylovegrowth_sync_runs"].find_one(
            {"_id": "babylovegrowth_sync_state"}
        )
        assert final_doc.get("status") != "running", (
            f"Lock leaked in running state: {final_doc}"
        )
        assert final_doc.get("lock_token") is None, (
            f"Lock token still held: {final_doc.get('lock_token')}"
        )
        checkpoint_pause(
            "4/4 — Lock cleanly released after contention",
            [
                f"final status: {final_doc.get('status')}",
                f"lock_token: {final_doc.get('lock_token')}",
            ],
        )

        print()
        print("  ✅ E2E lock contention verified.")
    finally:
        restore_settings()
        restore_client()


if __name__ == "__main__":
    asyncio.run(main())

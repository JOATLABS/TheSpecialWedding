#!/usr/bin/env python3
"""Cleanup paired with the verify_blg_*.py testbed drivers.

Drops every Mongo row in the reserved BLG_TEST_IDS range, resets the
singleton babylovegrowth_sync_runs doc out of 'running' status, and
sweeps R2 objects under BLG_TEST_R2_PREFIX so the next SEED phase
starts from zero. Idempotent — safe to re-run.

Sweeps:

    blog_articles                  (rows with babylovegrowth_id in
                                    the reserved BLG_TEST_IDS range)
    babylovegrowth_sync_runs       ('running' → 'idle' lock release)
    r2://<BLOG_ASSETS bucket>/
        blog/synced/test-fixtures  (testbed hero/inline images)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._blg_sync_common import (  # noqa: E402
    banner,
    purge_blg_test_articles,
    purge_blg_test_r2_fixtures,
    reset_blg_sync_runs,
)


async def main() -> None:
    banner("cleanup_blg_sync_state")

    articles_deleted = await purge_blg_test_articles()
    runs_reset = await reset_blg_sync_runs()
    r2_deleted = purge_blg_test_r2_fixtures()

    for collection, count in articles_deleted.items():
        print(f"    • {collection}: {count} deleted")
    for collection, count in runs_reset.items():
        print(f"    • {collection}: {count} reset")
    for resource, count in r2_deleted.items():
        if resource.startswith("_"):
            print(f"    • {resource}: {count}")
        else:
            print(f"    • {resource}: {count} deleted")


if __name__ == "__main__":
    asyncio.run(main())

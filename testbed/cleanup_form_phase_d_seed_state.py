#!/usr/bin/env python3
"""Cleanup paired with verify_form_phase_d_seed.py.

Removes the seeded planner's forms + the planner row itself so a
re-run from scratch will exercise the verify_email seeder again.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    PHASE_D_SEED,
    banner,
    delete_many,
    purge_form_rows_for_planner,
)


async def main() -> None:
    banner("cleanup_form_phase_d_seed_state")
    deleted = await purge_form_rows_for_planner(PHASE_D_SEED.email)
    for collection, count in deleted.items():
        print(f"  • {collection}: {count} deleted")
    users_dropped = await delete_many("users", {"email": PHASE_D_SEED.email})
    print(f"  • users: {users_dropped} deleted")


if __name__ == "__main__":
    asyncio.run(main())

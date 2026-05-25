#!/usr/bin/env python3
"""Cleanup paired with verify_communication_reminder_all_events.py."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import banner  # noqa: E402
from testbed.verify_communication_reminder_all_events import cleanup_state  # noqa: E402


async def main() -> None:
    banner("cleanup_communication_reminder_all_events_state")
    print(await cleanup_state())


if __name__ == "__main__":
    asyncio.run(main())

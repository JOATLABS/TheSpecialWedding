#!/usr/bin/env python3
"""Cleanup paired with verify_form_file_upload_lifecycle.py."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    FILE_UPLOAD,
    banner,
    purge_form_rows_for_planner,
)


async def main() -> None:
    banner("cleanup_form_file_upload_state")
    deleted = await purge_form_rows_for_planner(FILE_UPLOAD.email)
    for collection, count in deleted.items():
        print(f"  • {collection}: {count} deleted")


if __name__ == "__main__":
    asyncio.run(main())

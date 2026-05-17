#!/usr/bin/env python3
"""Backfill calendar-only Aurinko scopes for existing connection rows.

Existing planners connected before Tasks/Contacts consent was introduced do
not have ``connection_scopes`` on their ``calendar_connections`` rows. Backfill
calendar-only scope metadata so the frontend can show the incremental-auth
banner instead of assuming expanded access already exists.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.core.database import mongo


async def main() -> None:
    now = datetime.now(UTC)
    result = await mongo.get_calendar_connections_collection().update_many(
        {
            "$or": [
                {"connection_scopes": {"$exists": False}},
                {"connection_scopes": []},
                {"connection_scopes": None},
            ]
        },
        {
            "$set": {
                "connection_scopes": ["Calendar.Read", "Calendar.ReadWrite"],
                "updated_at": now,
            }
        },
    )
    print(f"Backfilled {result.modified_count} calendar connection row(s).")


if __name__ == "__main__":
    asyncio.run(main())

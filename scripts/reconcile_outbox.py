#!/usr/bin/env python3
"""
PM Substrate outbox reconciliation tool.

Allows ops to inspect and manually intervene in the ``pm_substrate_outbox``
collection without touching every tenant's data globally.

Every command requires ``--tenant`` (the planner email that is the substrate
tenant_id) to enforce the tenant boundary rule from AGENTS.md.

Usage
-----
List failed entries for a tenant:

    python scripts/reconcile_outbox.py list --tenant planner@example.com

Retry a specific entry (force back to pending):

    python scripts/reconcile_outbox.py retry \\
        --tenant planner@example.com \\
        --row-id 507f1f77bcf86cd799439011

Mark an entry delivered manually (use when substrate received it but ack was lost):

    python scripts/reconcile_outbox.py mark-delivered \\
        --tenant planner@example.com \\
        --row-id 507f1f77bcf86cd799439011 \\
        --by ops@thespecialwedding.io

Count pending/in_flight/failed rows per status for a tenant:

    python scripts/reconcile_outbox.py stats --tenant planner@example.com

Environment
-----------
Requires the same environment variables as the main app (MONGO_URI, etc.).
The easiest way to run this in production is via the Coolify one-off task
runner with the app container env loaded.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make the project root importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def _init_db() -> None:
    """Boot the minimal DB connection needed for outbox ops."""
    from app.core.database import init_database

    await init_database()


async def cmd_list(tenant: str, limit: int, status: str | None) -> None:
    from app.integrations.pm_substrate.outbox import (
        STATUS_FAILED,
        get_outbox_collection,
    )

    effective_status = status or STATUS_FAILED
    coll = get_outbox_collection()
    query: dict = {"tenant_id": tenant, "status": effective_status}
    cursor = coll.find(query, sort=[("created_at", -1)], limit=limit)
    rows = await cursor.to_list(length=limit)

    if not rows:
        print(f"No {effective_status!r} rows for tenant {tenant!r}.")
        return

    print(f"\n{'='*60}")
    print(f"Tenant: {tenant}")
    print(f"Status: {effective_status} — {len(rows)} row(s) shown (limit {limit})")
    print(f"{'='*60}")
    for row in rows:
        print(f"\n  row_id      : {row['_id']}")
        print(f"  event_type  : {row.get('event_type')}")
        print(f"  idempotency : {row.get('idempotency_key')}")
        print(f"  status      : {row.get('status')}")
        print(f"  attempts    : {row.get('attempts')}")
        print(f"  created_at  : {row.get('created_at')}")
        print(f"  last_attempt: {row.get('last_attempt_at')}")
        err = row.get("last_error") or ""
        print(f"  last_error  : {err[:120]}")
    print()


async def cmd_retry(tenant: str, row_id_str: str) -> None:
    from bson import ObjectId

    from app.integrations.pm_substrate.outbox import (
        STATUS_FAILED,
        STATUS_IN_FLIGHT,
        get_outbox_collection,
        reset_to_pending,
    )

    try:
        row_id = ObjectId(row_id_str)
    except Exception:
        print(f"ERROR: invalid ObjectId: {row_id_str!r}", file=sys.stderr)
        sys.exit(1)

    # Verify row belongs to this tenant before touching it.
    coll = get_outbox_collection()
    row = await coll.find_one({"_id": row_id})
    if not row:
        print(f"ERROR: row {row_id} not found.", file=sys.stderr)
        sys.exit(1)
    if row.get("tenant_id") != tenant:
        print(
            f"ERROR: row {row_id} belongs to tenant {row.get('tenant_id')!r}, "
            f"not {tenant!r}. Use the correct --tenant flag.",
            file=sys.stderr,
        )
        sys.exit(1)

    ok = await reset_to_pending(row_id)
    if ok:
        print(f"OK: row {row_id} reset to pending for tenant {tenant!r}.")
    else:
        print(
            f"WARNING: row {row_id} was not reset — it may already be pending or delivered.",
            file=sys.stderr,
        )


async def cmd_mark_delivered(tenant: str, row_id_str: str, by: str) -> None:
    from bson import ObjectId

    from app.integrations.pm_substrate.outbox import (
        get_outbox_collection,
        mark_delivered_manual,
    )

    try:
        row_id = ObjectId(row_id_str)
    except Exception:
        print(f"ERROR: invalid ObjectId: {row_id_str!r}", file=sys.stderr)
        sys.exit(1)

    coll = get_outbox_collection()
    row = await coll.find_one({"_id": row_id})
    if not row:
        print(f"ERROR: row {row_id} not found.", file=sys.stderr)
        sys.exit(1)
    if row.get("tenant_id") != tenant:
        print(
            f"ERROR: row {row_id} belongs to tenant {row.get('tenant_id')!r}, "
            f"not {tenant!r}.",
            file=sys.stderr,
        )
        sys.exit(1)

    ok = await mark_delivered_manual(row_id, by=by)
    if ok:
        print(f"OK: row {row_id} marked delivered by {by!r} for tenant {tenant!r}.")
    else:
        print(
            f"WARNING: row {row_id} was not updated — it may not exist.",
            file=sys.stderr,
        )


async def cmd_stats(tenant: str) -> None:
    from app.integrations.pm_substrate.outbox import get_outbox_collection

    coll = get_outbox_collection()
    pipeline = [
        {"$match": {"tenant_id": tenant}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    results = await coll.aggregate(pipeline).to_list(length=20)
    if not results:
        print(f"No outbox rows for tenant {tenant!r}.")
        return

    print(f"\nOutbox stats for tenant {tenant!r}:")
    total = 0
    for r in sorted(results, key=lambda x: x["_id"]):
        count = r["count"]
        total += count
        print(f"  {r['_id']:<12} : {count}")
    print(f"  {'TOTAL':<12} : {total}")
    print()


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="PM Substrate outbox reconciliation tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--tenant",
        required=True,
        help="Planner email (substrate tenant_id). Required — never global ops.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list", help="List outbox rows for a tenant")
    p_list.add_argument(
        "--status",
        default=None,
        help="Filter by status (default: failed). One of: pending, in_flight, delivered, failed.",
    )
    p_list.add_argument("--limit", type=int, default=50, help="Max rows to show.")

    # retry
    p_retry = sub.add_parser("retry", help="Reset a failed row back to pending")
    p_retry.add_argument("--row-id", required=True, help="MongoDB ObjectId of the outbox row.")

    # mark-delivered
    p_md = sub.add_parser(
        "mark-delivered",
        help="Manually mark a row as delivered (use when substrate received but ack was lost)",
    )
    p_md.add_argument("--row-id", required=True, help="MongoDB ObjectId of the outbox row.")
    p_md.add_argument("--by", required=True, help="Operator email for audit trail.")

    # stats
    sub.add_parser("stats", help="Show row counts by status for a tenant")

    args = parser.parse_args()

    await _init_db()

    if args.command == "list":
        await cmd_list(args.tenant, args.limit, args.status)
    elif args.command == "retry":
        await cmd_retry(args.tenant, args.row_id)
    elif args.command == "mark-delivered":
        await cmd_mark_delivered(args.tenant, args.row_id, args.by)
    elif args.command == "stats":
        await cmd_stats(args.tenant)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())

#!/usr/bin/env python3
"""Clean up partial state from the Aurinko lifecycle drivers.

Shared cleanup for all three Aurinko verifiers:

    * verify_aurinko_oauth_lifecycle.py
    * verify_aurinko_event_crud.py
    * verify_aurinko_webhook_roundtrip.py

Sweeps the planner chain (users, user_subscriptions, stripe_customers,
team_members), plus calendar-side collections that the chain doesn't
reach:

    * ``calendar_connections``       — rows written by OAuth callback
    * ``calendar_event_syncs``       — sync rows from event create/update
    * ``calendar_idempotency_keys``  — webhook-delivery dedupe rows
    * ``calendar_audit_log``         — audit entries from connect/disconnect
    * ``planner_tasks``              — meetings created by the CRUD driver

It does NOT delete the corresponding Aurinko-side subscriptions on the
aggregator account — the OAuth lifecycle driver's P6 phase already does
that on a successful disconnect, and any leftover subscriptions are
harmless once the encrypted account token is gone (no client can target
them). If you want a guaranteed Aurinko-side reset, run the OAuth driver
to its disconnect phase before running this cleanup.

Safe to re-run.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness

logger = logging.getLogger(__name__)

DRIVER_NAME = "cleanup_aurinko_lifecycle_state"

# Must mirror the verifiers — keep in sync.
PLANNER_EMAIL = "test_planner+aurinko_oauth@thespecialwedding.io"


def drop_calendar_state(h: Harness, planner_email: str) -> None:
    user = h.mongo["users"].find_one({"email": planner_email}, {"_id": 1})
    owner_id = str(user["_id"]) if user else None

    connection_rows = list(
        h.mongo["calendar_connections"].find(
            {"user_email": planner_email}, {"_id": 1, "aurinko_account_id": 1}
        )
    )
    connection_ids = [str(r["_id"]) for r in connection_rows]

    if connection_ids:
        synced = h.mongo["calendar_event_syncs"].delete_many(
            {"calendar_connection_id": {"$in": connection_ids}}
        )
        logger.info("dropped %d calendar_event_syncs rows", synced.deleted_count)

    conn_drop = h.mongo["calendar_connections"].delete_many(
        {"user_email": planner_email}
    )
    logger.info("dropped %d calendar_connections rows", conn_drop.deleted_count)

    # Idempotency keys for the aurinko_webhook scope are not user-scoped, but
    # they have a TTL and are only meaningful for the lifetime of a single
    # delivery. Sweep any rows older than 1 hour to keep the collection lean
    # without disrupting other concurrent runs.
    from datetime import datetime, timedelta, timezone

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    idem = h.mongo["calendar_idempotency_keys"].delete_many(
        {
            "scope_key": "aurinko_webhook",
            "created_at": {"$lt": one_hour_ago},
        }
    )
    logger.info("dropped %d aged calendar_idempotency_keys rows", idem.deleted_count)

    if owner_id:
        tasks_drop = h.mongo["planner_tasks"].delete_many(
            {"owner_planner_id": owner_id}
        )
        logger.info("dropped %d planner_tasks rows", tasks_drop.deleted_count)
        audit_drop = h.mongo["calendar_audit_log"].delete_many(
            {"owner_planner_email": planner_email}
        )
        logger.info("dropped %d calendar_audit_log rows", audit_drop.deleted_count)


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("CLEANUP — Aurinko Lifecycle (plus-variant planner)")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")

    h.log.info("")
    h.log.info(f"Dropping calendar state for {PLANNER_EMAIL}…")
    drop_calendar_state(h, PLANNER_EMAIL)

    h.log.info("")
    h.log.info(f"Dropping Mongo chain for {PLANNER_EMAIL}…")
    affected = h.delete_user_chain(PLANNER_EMAIL)
    if affected == 0:
        h.log.info(f"  (no Mongo user for {PLANNER_EMAIL})")

    h.log.info("")
    h.log.info(f"cleanup complete for planner={PLANNER_EMAIL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

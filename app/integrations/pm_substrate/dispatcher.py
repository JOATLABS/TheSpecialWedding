"""
PM Substrate outbox dispatcher.

Background asyncio task that polls ``pm_substrate_outbox`` for pending rows
and delivers them to the substrate HTTP service.

Wire-up
-------
This module exposes ``outbox_dispatcher_scheduler()``, a long-running coroutine
designed to be launched via ``asyncio.create_task()`` from ``app/main.py``
under the existing scheduler leadership guard.  The app already uses this
pattern for billing, rollup, and guest-media schedulers — we follow the same
convention rather than introducing a new worker runtime.

Delivery semantics
------------------
- **At-least-once**: a row stays ``pending`` (or is reset to ``pending``) until
  the substrate returns 2xx.  Retries use exponential backoff.
- **Exactly-once-effective**: the substrate is idempotent on ``paymentId`` /
  ``idempotency_key``, so replays are safe.

Event type routing
------------------
Each outbox row carries an ``event_type``.  The dispatcher routes to a handler
function based on this type:

``wedding.contract.payment_recorded``
    POST /tenants/{tenant_id}/events — single HTTP call.

``substrate.create_contract``
    Three-step: ensure vendor node, create contract node, wire edge.
    After success, writes ``pm_contract_id`` back to the local ``vendor_contracts``
    document.

``substrate.assign_vendor_to_budget_category``
    Three-step: ensure vendor node, ensure budget_category node, wire edge.

Configuration (environment variables)
--------------------------------------
OUTBOX_POLL_INTERVAL_SECONDS   Seconds between dispatcher poll cycles. Default 10.
OUTBOX_BATCH_SIZE              Max rows claimed per cycle. Default 20.
OUTBOX_MAX_RETRIES             Max delivery attempts before permanent failure. Default 5.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from bson import ObjectId

from app.integrations.pm_substrate.client import PMSubstrateClient, get_client
from app.integrations.pm_substrate.errors import PMSubstrateError
from app.integrations.pm_substrate.outbox import (
    STATUS_DELIVERED,
    claim_pending_rows,
    mark_delivered,
    mark_failed_permanent,
    mark_for_retry,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTBOX_POLL_INTERVAL_SECONDS: float = float(
    os.environ.get("OUTBOX_POLL_INTERVAL_SECONDS", "10")
)
OUTBOX_BATCH_SIZE: int = int(os.environ.get("OUTBOX_BATCH_SIZE", "20"))
OUTBOX_MAX_RETRIES: int = int(os.environ.get("OUTBOX_MAX_RETRIES", "5"))

# ---------------------------------------------------------------------------
# Per-event-type handlers
# ---------------------------------------------------------------------------


async def _handle_payment_recorded(
    row: Dict[str, Any],
    client: PMSubstrateClient,
) -> None:
    """Deliver a ``wedding.contract.payment_recorded`` event to the substrate."""
    p = row["payload"]
    tenant_id = row["tenant_id"]

    await client.record_payment(
        tenant_id=tenant_id,
        pm_contract_id=p["pm_contract_id"],
        amount_minor=int(p["amount_minor"]),
        recorded_at=p["recorded_at"],
        payment_id=p["payment_id"],
    )


async def _handle_create_contract(
    row: Dict[str, Any],
    client: PMSubstrateClient,
) -> None:
    """Deliver a ``substrate.create_contract`` operation.

    Creates vendor node, contract node, and contract→vendor edge in the
    substrate graph.  On success, writes the returned ``pm_contract_id``
    back to the local ``vendor_contracts`` MongoDB document so the payment
    dispatcher can reference it.
    """
    from app.core.database import mongo

    p = row["payload"]
    tenant_id = row["tenant_id"]
    local_contract_id = p.get("local_contract_id")

    pm_contract_id = await client.create_contract(
        tenant_id=tenant_id,
        vendor_profile_id=p["vendor_profile_id"],
        contract_data=p["contract_data"],
        vendor_data=p.get("vendor_data"),
    )

    # Write pm_contract_id back to the local vendor_contracts doc.
    if local_contract_id and pm_contract_id:
        try:
            await mongo.db["vendor_contracts"].update_one(
                {"_id": ObjectId(local_contract_id)},
                {"$set": {"pm_contract_id": pm_contract_id}},
            )
            logger.info(
                "outbox.dispatcher: stored pm_contract_id=%s for local contract %s",
                pm_contract_id,
                local_contract_id,
            )
        except Exception as exc:
            # Non-fatal: the substrate contract was created. The local doc
            # won't have pm_contract_id until the next manual reconciliation.
            # Log as warning rather than raising so we don't un-deliver the row.
            logger.warning(
                "outbox.dispatcher: failed to write pm_contract_id=%s back "
                "to vendor_contracts/%s: %s",
                pm_contract_id,
                local_contract_id,
                exc,
            )


async def _handle_assign_vendor_to_budget_category(
    row: Dict[str, Any],
    client: PMSubstrateClient,
) -> None:
    """Deliver a ``substrate.assign_vendor_to_budget_category`` operation."""
    p = row["payload"]
    tenant_id = row["tenant_id"]

    await client.assign_vendor_to_budget_category(
        tenant_id=tenant_id,
        vendor_profile_id=p["vendor_profile_id"],
        budget_category_id=p["budget_category_id"],
        vendor_data=p.get("vendor_data"),
        category_data=p.get("category_data"),
    )


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

_HANDLERS = {
    "wedding.contract.payment_recorded": _handle_payment_recorded,
    "substrate.create_contract": _handle_create_contract,
    "substrate.assign_vendor_to_budget_category": _handle_assign_vendor_to_budget_category,
}

# ---------------------------------------------------------------------------
# Core dispatch cycle
# ---------------------------------------------------------------------------


async def _dispatch_batch() -> int:
    """Claim and deliver one batch of pending outbox rows.

    Returns the number of rows processed (delivered or failed) this cycle.
    """
    rows = await claim_pending_rows(limit=OUTBOX_BATCH_SIZE)
    if not rows:
        return 0

    client = get_client()
    processed = 0

    for row in rows:
        row_id: ObjectId = row["_id"]
        event_type: str = row.get("event_type", "")
        attempts: int = row.get("attempts", 0)

        handler = _HANDLERS.get(event_type)
        if handler is None:
            # Unknown event type — fail permanently so it doesn't block the queue.
            err = f"Unknown outbox event_type: {event_type!r}"
            logger.error("outbox.dispatcher: %s (row=%s)", err, row_id)
            await mark_failed_permanent(row_id, err)
            processed += 1
            continue

        try:
            await handler(row, client)
            await mark_delivered(row_id)
            logger.info(
                "outbox.dispatcher: delivered event_type=%s row=%s (attempt %d)",
                event_type,
                row_id,
                attempts + 1,
            )
        except PMSubstrateError as exc:
            # 4xx = non-retryable (bad payload / auth). 5xx / network = retryable.
            status_code = exc.status_code
            is_retryable = status_code is None or status_code >= 500
            error_str = str(exc)

            if is_retryable:
                logger.warning(
                    "outbox.dispatcher: retryable error for row=%s event=%s "
                    "(attempt %d/%d): %s",
                    row_id,
                    event_type,
                    attempts + 1,
                    OUTBOX_MAX_RETRIES,
                    error_str,
                )
                await mark_for_retry(row_id, error_str, attempts + 1, OUTBOX_MAX_RETRIES)
            else:
                logger.error(
                    "outbox.dispatcher: non-retryable error (HTTP %s) for row=%s "
                    "event=%s: %s",
                    status_code,
                    row_id,
                    event_type,
                    error_str,
                )
                await mark_failed_permanent(row_id, error_str)
            processed += 1
            continue
        except Exception as exc:
            error_str = str(exc)
            logger.warning(
                "outbox.dispatcher: unexpected error for row=%s event=%s "
                "(attempt %d/%d): %s",
                row_id,
                event_type,
                attempts + 1,
                OUTBOX_MAX_RETRIES,
                error_str,
            )
            await mark_for_retry(row_id, error_str, attempts + 1, OUTBOX_MAX_RETRIES)
            processed += 1
            continue

        processed += 1

    return processed


# ---------------------------------------------------------------------------
# Long-running scheduler (for main.py asyncio.create_task)
# ---------------------------------------------------------------------------


async def outbox_dispatcher_scheduler() -> None:
    """Long-running coroutine that polls and delivers outbox rows.

    Design mirrors the existing ad-rollup and billing schedulers in
    ``app/main.py``.  Should be launched via ``asyncio.create_task()``
    inside the lifespan scheduler-leadership block.

    Sleeps ``OUTBOX_POLL_INTERVAL_SECONDS`` between cycles, or a shorter
    interval when the last cycle had pending work (to drain quickly).
    """
    logger.info(
        "outbox.dispatcher: starting (poll_interval=%.1fs, batch=%d, max_retries=%d)",
        OUTBOX_POLL_INTERVAL_SECONDS,
        OUTBOX_BATCH_SIZE,
        OUTBOX_MAX_RETRIES,
    )
    while True:
        try:
            processed = await _dispatch_batch()
            # If we had a full batch, sleep briefly and re-poll to drain.
            sleep_for = (
                1.0 if processed >= OUTBOX_BATCH_SIZE else OUTBOX_POLL_INTERVAL_SECONDS
            )
        except asyncio.CancelledError:
            logger.info("outbox.dispatcher: shutting down")
            return
        except Exception as exc:
            logger.error(
                "outbox.dispatcher: unhandled error in poll cycle: %s",
                exc,
                exc_info=True,
            )
            sleep_for = OUTBOX_POLL_INTERVAL_SECONDS

        try:
            await asyncio.sleep(sleep_for)
        except asyncio.CancelledError:
            logger.info("outbox.dispatcher: shutting down during sleep")
            return

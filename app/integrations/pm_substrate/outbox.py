"""
PM Substrate outbox — at-least-once delivery for substrate calls.

The outbox pattern closes the atomicity gap between the local Mongo write
and the substrate HTTP call. Without it: if Mongo commits but the substrate
is down, the payment is recorded locally and never propagated.

Architecture
------------
1.  Service writes to ``pm_substrate_outbox`` IN THE SAME Mongo transaction
    as the local domain write (milestone, contract, assignment).
2.  Outbox dispatcher (background poll loop) picks up ``pending`` rows,
    marks them ``in_flight``, attempts the HTTP call, then marks
    ``delivered`` or ``failed``.
3.  Substrate is idempotent on ``idempotency_key`` so retries are safe.

End-to-end semantics: exactly-once-effective.
  - At-least-once delivery (outbox).
  - Idempotent processing (substrate dedupes on idempotency_key / payment_id).

Event types
-----------
``wedding.contract.payment_recorded``
    Emitted when a milestone payment is recorded. Substrate route:
    ``POST /tenants/{tenant_id}/events``.

``substrate.create_contract``
    Drives the three-step substrate contract creation (vendor node, contract
    node, contract→vendor edge). Dispatcher stores the returned
    ``pm_contract_id`` back on the local ``vendor_contracts`` document.

``substrate.assign_vendor_to_budget_category``
    Drives the vendor→budget-category edge creation in the substrate graph.

Index strategy
--------------
Primary poll index: ``{ status: 1, next_attempt_at: 1, created_at: 1 }``
  Used by the dispatcher's ``$or``-based status+timing query.

Idempotency index: ``{ idempotency_key: 1 }`` unique sparse.
  Prevents duplicate outbox rows for the same underlying operation.

Tenant+status: ``{ tenant_id: 1, status: 1 }``
  Used by the reconciliation CLI tool's list/retry queries.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

logger = logging.getLogger(__name__)


def _get_mongo():
    """Lazy import of mongo to allow test-time mocking without Motor startup."""
    from app.core.database import mongo
    return mongo

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_IN_FLIGHT = "in_flight"
STATUS_DELIVERED = "delivered"
STATUS_FAILED = "failed"

# ---------------------------------------------------------------------------
# Configuration (env-overridable via the dispatcher module)
# ---------------------------------------------------------------------------

OUTBOX_COLLECTION_NAME = "pm_substrate_outbox"

# ---------------------------------------------------------------------------
# Collection accessor
# ---------------------------------------------------------------------------


def get_outbox_collection():
    """Return the ``pm_substrate_outbox`` Motor collection."""
    return _get_mongo().db[OUTBOX_COLLECTION_NAME]


# ---------------------------------------------------------------------------
# Index bootstrap
# ---------------------------------------------------------------------------


async def ensure_outbox_indexes() -> None:
    """Create all outbox indexes idempotently.

    Called once during app startup. Safe to call multiple times — MongoDB
    ignores index creation requests for identical existing indexes.
    """
    coll = get_outbox_collection()
    try:
        # Primary dispatcher poll index.
        await coll.create_index(
            [("status", 1), ("next_attempt_at", 1), ("created_at", 1)],
            background=True,
            name="outbox_dispatcher_poll",
        )
        # Idempotency guard — unique per business key.
        # sparse=True: documents that do NOT have idempotency_key are excluded
        # from the uniqueness check (protects against null collisions).
        await coll.create_index(
            [("idempotency_key", 1)],
            unique=True,
            sparse=True,
            background=True,
            name="outbox_idempotency_key",
        )
        # Reconciliation and tenant-scoped ops.
        await coll.create_index(
            [("tenant_id", 1), ("status", 1), ("created_at", -1)],
            background=True,
            name="outbox_tenant_status",
        )
        logger.info("pm_substrate_outbox: indexes ensured")
    except Exception as exc:
        logger.warning("pm_substrate_outbox: index creation warning: %s", exc)


# ---------------------------------------------------------------------------
# Outbox row builder
# ---------------------------------------------------------------------------


def build_outbox_row(
    *,
    tenant_id: str,
    created_by: str,
    event_type: str,
    payload: Dict[str, Any],
    route: str,
    idempotency_key: str,
) -> Dict[str, Any]:
    """Build a new outbox document ready for insertion.

    The caller is responsible for inserting this document, typically inside
    a Mongo transaction alongside the local domain write.

    Args:
        tenant_id:        Planner email — the substrate tenant identifier.
        created_by:       Same as tenant_id in most cases; logged for audit.
        event_type:       One of the substrate event type strings defined in
                          this module (e.g. ``"wedding.contract.payment_recorded"``).
        payload:          The full context needed by the dispatcher to make the
                          substrate call. Schema varies by event_type.
        route:            Human-readable description of the substrate target
                          (e.g. ``"POST /tenants/{tenant_id}/events"``).
        idempotency_key:  Stable business key — substrate uses this to dedupe.
                          For payment events: the payment/milestone ID.
                          For create_contract: the local contract MongoDB ID.
                          For edge creation: ``f"{tenant}:{vendor}:{category}"``.

    Returns:
        Dict suitable for ``collection.insert_one(doc, session=session)``.
    """
    now = datetime.now(timezone.utc)
    return {
        "_id": ObjectId(),
        "tenant_id": tenant_id,
        "created_by": created_by,
        "event_type": event_type,
        "payload": payload,
        "route": route,
        "status": STATUS_PENDING,
        "attempts": 0,
        "last_attempt_at": None,
        "last_error": None,
        "created_at": now,
        "delivered_at": None,
        "next_attempt_at": now,  # eligible for dispatch immediately
        "idempotency_key": idempotency_key,
    }


# ---------------------------------------------------------------------------
# Dispatcher-facing helpers
# ---------------------------------------------------------------------------


async def claim_pending_rows(limit: int = 20) -> List[Dict[str, Any]]:
    """Atomically claim up to ``limit`` pending outbox rows for dispatch.

    Uses ``find_one_and_update`` semantics via a loop to avoid a race where
    two dispatcher instances claim the same row. Each row is individually
    claimed: mark ``in_flight`` only if it is still ``pending``.

    A simpler bulk ``update_many`` would be faster but risks large batches
    blocking the poll loop when the substrate is slow. Per-document claims
    let the dispatcher interleave delivery with claiming.

    Returns a list of row dicts (with ``_id`` as ObjectId).
    """
    coll = get_outbox_collection()
    now = datetime.now(timezone.utc)

    # Find candidate IDs first (read-only scan).
    cursor = coll.find(
        {
            "status": STATUS_PENDING,
            "next_attempt_at": {"$lte": now},
        },
        {"_id": 1},
        sort=[("next_attempt_at", 1), ("created_at", 1)],
        limit=limit,
    )
    candidates = await cursor.to_list(length=limit)

    claimed: List[Dict[str, Any]] = []
    for candidate in candidates:
        row = await coll.find_one_and_update(
            {"_id": candidate["_id"], "status": STATUS_PENDING},
            {
                "$set": {
                    "status": STATUS_IN_FLIGHT,
                    "last_attempt_at": now,
                }
            },
            return_document=True,
        )
        if row is not None:
            claimed.append(row)

    return claimed


async def mark_delivered(row_id: ObjectId) -> None:
    """Mark an outbox row as successfully delivered."""
    coll = get_outbox_collection()
    now = datetime.now(timezone.utc)
    await coll.update_one(
        {"_id": row_id},
        {"$set": {"status": STATUS_DELIVERED, "delivered_at": now}},
    )


async def mark_failed_permanent(row_id: ObjectId, error: str) -> None:
    """Mark an outbox row as permanently failed (max retries exceeded)."""
    coll = get_outbox_collection()
    await coll.update_one(
        {"_id": row_id},
        {
            "$set": {
                "status": STATUS_FAILED,
                "last_error": error[:2000],
            }
        },
    )


async def mark_for_retry(
    row_id: ObjectId,
    error: str,
    attempts: int,
    max_retries: int,
) -> None:
    """On transient failure: increment attempts and schedule next retry.

    Backoff: ``min(2 ** attempts, 3600)`` seconds.
    If ``attempts >= max_retries``, permanently fails the row instead.
    """
    if attempts >= max_retries:
        await mark_failed_permanent(row_id, error)
        return

    backoff_seconds = min(math.pow(2, attempts), 3600)
    next_attempt = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)

    coll = get_outbox_collection()
    await coll.update_one(
        {"_id": row_id},
        {
            "$set": {
                "status": STATUS_PENDING,
                "last_error": error[:2000],
                "next_attempt_at": next_attempt,
            },
            "$inc": {"attempts": 1},
        },
    )


# ---------------------------------------------------------------------------
# Reconciliation helpers (used by CLI script)
# ---------------------------------------------------------------------------


async def list_failed_rows(tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return failed outbox rows for a specific tenant."""
    coll = get_outbox_collection()
    cursor = coll.find(
        {"tenant_id": tenant_id, "status": STATUS_FAILED},
        sort=[("created_at", -1)],
        limit=limit,
    )
    rows = await cursor.to_list(length=limit)
    return rows


async def reset_to_pending(row_id: ObjectId) -> bool:
    """Force a failed (or in_flight) row back to pending for retry.

    Returns True if the row was updated, False if not found.
    """
    coll = get_outbox_collection()
    now = datetime.now(timezone.utc)
    result = await coll.update_one(
        {"_id": row_id, "status": {"$in": [STATUS_FAILED, STATUS_IN_FLIGHT]}},
        {
            "$set": {
                "status": STATUS_PENDING,
                "next_attempt_at": now,
                "last_error": None,
            }
        },
    )
    return result.modified_count > 0


async def mark_delivered_manual(row_id: ObjectId, by: str) -> bool:
    """Manually mark a row as delivered (e.g., substrate received but ack was lost).

    Returns True if the row was updated.
    """
    coll = get_outbox_collection()
    now = datetime.now(timezone.utc)
    result = await coll.update_one(
        {"_id": row_id},
        {
            "$set": {
                "status": STATUS_DELIVERED,
                "delivered_at": now,
                "last_error": f"Manually marked delivered by {by}",
            }
        },
    )
    return result.modified_count > 0

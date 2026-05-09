"""Meter-state Mongo write helpers — defensive against Stripe-vs-Mongo divergence.

When a meter event succeeds at Stripe, the wedding row MUST be updated to
reflect that fact. If the Mongo update fails (network blip, timeout) and
the caller returns without retrying, the daily batch job
(``app/api/billing_jobs.py``) will see ``last_billed_at`` unset and fire
a DUPLICATE meter event — different idempotency-key prefix than the
original, so Stripe won't dedupe → **customer is double-billed**.

This module wraps the post-meter-event Mongo write with:

* one immediate retry on failure (covers transient blips)
* on persistent failure: logs to an explicit ``STRIPE_MONGO_DIVERGENCE``
  error stream so the divergence is grep-able / alertable

See ``docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md`` §SS4.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def update_wedding_meter_state(
    weddings_collection: Any,
    wedding_id: Any,
    set_fields: dict,
    *,
    context: str = "meter_state_update",
) -> bool:
    """Update a wedding's meter-state fields with retry-on-failure.

    The retry exists because the success-path write (after a meter event
    landed at Stripe) is the dangerous failure mode: dropping it leads
    to silent double-billing on the next daily-batch run.

    Args:
        weddings_collection: Motor async collection handle for
            ``mongo.db["weddings"]``. Passed in (rather than imported)
            so callers can inject test doubles.
        wedding_id: The wedding's ``_id``.
        set_fields: Fields to set. Will be wrapped in ``{"$set": ...}``.
        context: Descriptive label that appears in failure logs. Use
            something like ``"wedding_create_success"`` so operators can
            trace which call site diverged.

    Returns:
        ``True`` if Mongo matched at least one document on either
        attempt. ``False`` if both attempts failed.
    """
    for attempt in (1, 2):
        try:
            result = await weddings_collection.update_one(
                {"_id": wedding_id},
                {"$set": set_fields},
            )
            return result.matched_count > 0
        except Exception as exc:  # noqa: BLE001 — Mongo error type varies
            if attempt == 1:
                logger.warning(
                    "update_wedding_meter_state attempt 1 failed for "
                    "wedding_id=%r context=%r: %s. Retrying once.",
                    wedding_id,
                    context,
                    exc,
                )
                await asyncio.sleep(0.1)
            else:
                # Grep-able prefix for ops alerting.
                logger.error(
                    "STRIPE_MONGO_DIVERGENCE wedding_id=%r context=%r "
                    "set_fields=%r — Mongo update failed twice: %s. "
                    "Stripe-side meter state may be ahead of Mongo. "
                    "Operator must reconcile via "
                    "/admin/metering/retry-pending OR by inspecting "
                    "weddings.last_billed_at against the Stripe "
                    "MeterEventSummary for this customer.",
                    wedding_id,
                    context,
                    set_fields,
                    exc,
                )
    return False

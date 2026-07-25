"""Shared period-boundary parsing helpers.

Used by metering hooks (``app/api/wedding.py``, ``app/api/billing_jobs.py``,
``app/api/metering.py``) and any other code that reads
``user_subscriptions.current_period_start`` and needs to compare it to a
billing event timestamp.

Why this is its own module
==========================

Per ``project_subscription_lifecycle_bug_patterns`` (2026-04-25), divergent
period-boundary parsing has historically caused real metering bugs. Two
prior implementations existed in parallel:

* ``app/api/wedding.py`` coerced naive datetimes using
  ``datetime.now(timezone.utc).astimezone().tzinfo`` — which returns the
  **process's local timezone**, not UTC. On a non-UTC server this
  silently tagged Mongo datetimes (which are stored as UTC) with a local
  offset, causing "already billed this period" checks to false-positive
  or -negative around period boundaries.
* ``app/api/billing_jobs.py`` used ``timezone.utc`` directly — correct.

Extracting these into one helper, with the UTC-correct semantics, fixes
the wedding.py bug as a side effect. See
docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md §C5.

Contract
========

* Input: ``str`` (ISO 8601 with optional Z suffix), ``datetime`` (naive
  or aware), or ``None`` / unparseable input.
* Output: an aware ``datetime`` in UTC, or ``None`` if input was missing
  or unparseable.
* Naive datetimes are assumed to be UTC. Mongo stores datetimes as UTC by
  convention; trusting that is safer than guessing local.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def coerce_period_start(value: Any) -> datetime | None:
    """Normalize ``current_period_start`` into a UTC-aware datetime.

    Args:
        value: Raw value as it might appear in
            ``user_subscriptions.current_period_start``. Stripe sends
            ISO 8601 strings; older webhook handlers may have stored
            naive datetimes; some legacy paths leave it ``None``.

    Returns:
        A timezone-aware ``datetime`` in UTC, or ``None`` if the value
        was missing or could not be parsed. Callers should treat ``None``
        as "skip this billing period check" rather than "before all time."

    Behavior:
        * ``None`` / empty → ``None``.
        * ``str`` parseable as ISO 8601 (handling trailing ``Z``) →
          aware UTC datetime.
        * ``str`` unparseable → ``None`` and a logged warning.
        * Naive ``datetime`` → tagged as UTC (matches Mongo convention).
        * Aware ``datetime`` → returned in UTC (converted if needed).
    """
    if value is None:
        return None

    # String input: ISO 8601 with optional Z suffix.
    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            logger.warning(
                "coerce_period_start: failed to parse %r as ISO 8601: %s",
                value,
                exc,
            )
            return None

    if not isinstance(value, datetime):
        logger.warning(
            "coerce_period_start: unexpected type %s for value %r",
            type(value).__name__,
            value,
        )
        return None

    # Naive datetime: assume UTC. Mongo stores datetimes as UTC by
    # convention; this matches what the rest of the codebase does (see
    # app/api/billing_jobs.py for the canonical pattern).
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    # Aware but possibly non-UTC: normalize.
    return value.astimezone(UTC)

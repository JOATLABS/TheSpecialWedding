"""Stripe Billing Meter helpers — shared between runtime and seed.

These functions operate purely on the Stripe SDK and have ZERO dependencies
on ``app.core.database``, ``app.core.settings``, or any async / motor code.

That isolation is intentional: ``scripts/seed_subscription_plans.py`` runs
at container startup before the FastAPI app boots, and historically had its
own stripped-down Stripe-sync code path. To collapse to a single source of
truth for meter configuration without forcing the seed to import the full
service layer, the meter-specific logic lives here.

Two callsites:

* ``app/services/stripe_service.py`` (runtime)
* ``scripts/seed_subscription_plans.py`` (container startup)

When you change anything in this module, both callsites are affected. There
is no third caller — keep it that way.

References:

* docs/analysis/METERING_REVIEW_2026-05-04_PART2.md §5 (CC1, CC2, HH1)
* https://docs.stripe.com/api/billing/meter (canonical Meter config)
* https://docs.stripe.com/billing/subscriptions/usage-based/meters/configure
"""

from __future__ import annotations

import logging
from typing import Optional

import stripe
from stripe import InvalidRequestError, StripeError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical meter configuration
#
# These constants pin the meter shape that the rest of the codebase depends
# on. Changing any of them requires coordinated updates in
# ``app/api/wedding.py`` (where the meter event payload is constructed) and
# in the admin plan editor.
# ---------------------------------------------------------------------------

METER_AGGREGATION_FORMULA = "sum"
"""Required Stripe Meter ``default_aggregation.formula``.

The wedding-delete hook in ``app/api/wedding.py:386`` emits ``value="-1"``
to "reverse" a prior ``+1`` event. The negative-value reversal nets
correctly *only* on a Sum meter — Count and Last would silently break
billing. Stripe does also expose ``MeterEventAdjustment`` for explicit
within-24h cancellations; that's a separate code path discussed in the
review doc, not this helper's concern.
"""

METER_CUSTOMER_MAPPING_KEY = "stripe_customer_id"
"""Required ``customer_mapping.event_payload_key``.

Every ``MeterEvent.create`` call in this codebase sends customer
attribution under the ``stripe_customer_id`` payload key. A meter created
with a different mapping key would cause Stripe to reject every event
silently.
"""

METER_VALUE_KEY = "value"
"""Required ``value_settings.event_payload_key``.

The numeric quantity (typically ``"1"`` or ``"-1"``) is sent under the
``value`` key.
"""

# ---------------------------------------------------------------------------
# Canonical event names
#
# Centralized so the admin form, the seed script, the runtime hooks, and the
# tests all reference the same string. See METERING_REVIEW_2026-05-04 §M1.
# ---------------------------------------------------------------------------

METER_EVENT_NAME_WEDDING_ACTIVE = "wedding_active"
"""The canonical event name for per-active-wedding billing.

Must match (a) what the admin form puts in ``plan.meter_event_name``,
(b) what ``app/api/wedding.py`` passes to ``report_meter_event``, and
(c) the meter's ``event_name`` in Stripe. ``ensure_stripe_meter()`` below
guarantees Stripe-side consistency for any caller using this string.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_stripe_meter(
    event_name: str,
    display_name: Optional[str] = None,
) -> str:
    """Idempotently provision a Stripe Billing Meter.

    Searches active meters by ``event_name``. Returns the existing meter ID
    if found; otherwise creates a new meter with the canonical config:

    * ``default_aggregation.formula = "sum"``
    * ``customer_mapping = {type: "by_id", event_payload_key: "stripe_customer_id"}``
    * ``value_settings = {event_payload_key: "value"}``

    Args:
        event_name: Stripe meter event name. Must match
            ``plan.meter_event_name`` byte-for-byte downstream.
        display_name: Human-readable name shown in the Stripe Dashboard.
            Defaults to ``event_name`` title-cased with underscores
            replaced by spaces (``"wedding_active"`` → ``"Wedding Active"``).

    Returns:
        Stripe Meter ID, e.g. ``"mtr_..."``.

    Raises:
        StripeError: ``Meter.create`` failed and no existing meter was found.
            Callers in HTTP contexts should wrap this in HTTPException.
    """
    # 1. Search for existing meter by event_name.
    #
    # ``auto_paging_iter`` walks past the per-page limit; without it, an
    # account with >100 active meters could miss a match. Failing the list
    # call is non-fatal — we fall through to ``Meter.create`` and rely on
    # the idempotency_key (step 2) to keep concurrent calls from
    # producing duplicates.
    try:
        meters = stripe.billing.Meter.list(status="active", limit=100)
        for meter in meters.auto_paging_iter():
            if getattr(meter, "event_name", None) != event_name:
                continue
            # C2 fix: don't silently bind to a misconfigured existing
            # meter. Validate before returning. If the meter is broken,
            # we raise loudly — replacing it automatically would orphan
            # any prior meter events. See METERING_GAP_SCENARIOS_2026-05-04.md
            # §C2.
            try:
                assert_meter_config(meter.id)
            except ValueError as exc:
                logger.error(
                    "Found existing meter %s for event_name=%r but it has "
                    "invalid config: %s. Refusing to silently bind to a "
                    "broken meter. Operator must fix or deactivate it in "
                    "the Stripe Dashboard.",
                    meter.id,
                    event_name,
                    exc,
                )
                raise
            logger.info(
                "Found valid existing Stripe meter for event_name=%r: %s",
                event_name,
                meter.id,
            )
            return meter.id
    except StripeError as exc:
        # Don't hard-fail on transient list errors — let create attempt below.
        logger.warning(
            "Meter.list failed during ensure_stripe_meter(%r): %s. "
            "Falling through to Meter.create.",
            event_name,
            exc,
        )

    # 2. Create a new meter with the canonical config.
    #
    # SS1 fix: pass an idempotency_key so concurrent seed runs (e.g.,
    # multi-container rolling deploys) share Stripe's 24h idempotency
    # cache. The first call creates the meter; subsequent calls with the
    # same key get the cached response — no duplicates. The 24h cache
    # window is well beyond any realistic deploy duration; reuses past
    # 24h are harmless because the Meter.list step above will find the
    # existing meter and skip Meter.create entirely. See
    # METERING_GAP_SCENARIOS_2026-05-04.md §SS1.
    if not display_name:
        display_name = event_name.replace("_", " ").title()

    new_meter = stripe.billing.Meter.create(
        display_name=display_name,
        event_name=event_name,
        default_aggregation={"formula": METER_AGGREGATION_FORMULA},
        customer_mapping={
            "type": "by_id",
            "event_payload_key": METER_CUSTOMER_MAPPING_KEY,
        },
        value_settings={"event_payload_key": METER_VALUE_KEY},
        idempotency_key=f"ensure_stripe_meter_{event_name}",
    )
    logger.info(
        "Created Stripe meter for event_name=%r: %s",
        event_name,
        new_meter.id,
    )
    return new_meter.id


def assert_meter_config(meter_id: str) -> None:
    """Verify a live Stripe Meter matches the codebase's required shape.

    Raises ``ValueError`` with an explicit message on any mismatch. Callers
    in HTTP contexts should catch and wrap as ``HTTPException(400, ...)``.

    Three things must be true:

    1. ``default_aggregation.formula == "sum"`` — the reversal pattern in
       ``app/api/wedding.py`` (``value="-1"``) only nets correctly on Sum.
    2. ``customer_mapping.event_payload_key == "stripe_customer_id"`` —
       every meter event sends customer attribution under this key.
    3. ``value_settings.event_payload_key == "value"`` — every meter event
       sends the numeric quantity under this key.

    Args:
        meter_id: A ``"mtr_..."`` ID, typically pulled from
            ``plan.meter_id``.

    Raises:
        ValueError: The meter exists but is misconfigured.
        ValueError: The meter ID does not exist on the account.
    """
    try:
        meter = stripe.billing.Meter.retrieve(meter_id)
    except InvalidRequestError as exc:
        raise ValueError(
            f"Stripe meter {meter_id!r} not found: {exc}. "
            f"Provision it via ensure_stripe_meter() before syncing the plan."
        ) from exc

    formula = getattr(
        getattr(meter, "default_aggregation", None),
        "formula",
        None,
    )
    if formula != METER_AGGREGATION_FORMULA:
        raise ValueError(
            f"Stripe meter {meter_id!r} aggregation={formula!r}, must be "
            f"{METER_AGGREGATION_FORMULA!r}. The reversal arithmetic in "
            f"app/api/wedding.py emits value=-1 on delete; only sum nets "
            f"correctly. Recreate the meter with formula=sum."
        )

    customer_mapping_key = getattr(
        getattr(meter, "customer_mapping", None),
        "event_payload_key",
        None,
    )
    if customer_mapping_key != METER_CUSTOMER_MAPPING_KEY:
        raise ValueError(
            f"Stripe meter {meter_id!r} customer_mapping.event_payload_key="
            f"{customer_mapping_key!r}, must be "
            f"{METER_CUSTOMER_MAPPING_KEY!r}. Every wedding meter event "
            f"sends customer attribution under this key."
        )

    value_key = getattr(
        getattr(meter, "value_settings", None),
        "event_payload_key",
        None,
    )
    if value_key != METER_VALUE_KEY:
        raise ValueError(
            f"Stripe meter {meter_id!r} value_settings.event_payload_key="
            f"{value_key!r}, must be {METER_VALUE_KEY!r}. Wedding meter "
            f"events send the numeric quantity under this key."
        )

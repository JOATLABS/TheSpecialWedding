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

* docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md (gap analysis driving
  the SS1 idempotency_key + C2 validate-on-existing-match fixes)
* https://docs.stripe.com/api/billing/meter (canonical Meter config)
* https://docs.stripe.com/billing/subscriptions/usage-based/meters/configure
"""

from __future__ import annotations

import logging

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

The wedding-delete hook in ``app/api/wedding.py`` emits ``value="-1"``
to "reverse" a prior ``+1`` event. The negative-value reversal nets
correctly *only* on a Sum meter — Count and Last would silently break
billing.
"""

METER_CUSTOMER_MAPPING_KEY = "stripe_customer_id"
"""Required ``customer_mapping.event_payload_key``.

Every ``MeterEvent.create`` call in this codebase sends customer
attribution under the ``stripe_customer_id`` payload key.
"""

METER_VALUE_KEY = "value"
"""Required ``value_settings.event_payload_key``."""

# ---------------------------------------------------------------------------
# Canonical event names
# ---------------------------------------------------------------------------

METER_EVENT_NAME_WEDDING_ACTIVE = "wedding_active"
"""The canonical event name for per-active-wedding billing."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_stripe_meter(
    event_name: str,
    display_name: str | None = None,
) -> str:
    """Idempotently provision a Stripe Billing Meter.

    Searches active meters by ``event_name``. Returns the existing meter ID
    if found AND it has the canonical config; otherwise creates a new meter.

    Two SS-tier fixes are wired into this function:

    * **C2 (validate on existing match):** when ``Meter.list`` returns a
      matching meter, we call ``assert_meter_config`` before returning. A
      misconfigured existing meter raises ``ValueError`` rather than
      silently binding to a broken meter. The seed catches this and prints
      an actionable operator message.

    * **SS1 (idempotency_key on Meter.create):** ``Meter.create`` is called
      with a deterministic ``idempotency_key``. Concurrent seed runs (e.g.,
      multi-container rolling deploys) share Stripe's 24h idempotency
      cache and all get the same meter id — no duplicates.

    Args:
        event_name: Stripe meter event name. Must match
            ``plan.meter_event_name`` byte-for-byte downstream.
        display_name: Human-readable name shown in the Stripe Dashboard.
            Defaults to title-cased ``event_name`` (``"wedding_active"``
            → ``"Wedding Active"``).

    Returns:
        Stripe Meter ID (``"mtr_..."``).

    Raises:
        StripeError: ``Meter.create`` failed.
        ValueError: An existing meter matched the event_name but has
            invalid config. Caller must fix in the Stripe Dashboard.
    """
    # 1. Search for existing meter by event_name.
    try:
        meters = stripe.billing.Meter.list(status="active", limit=100)
        for meter in meters.auto_paging_iter():
            if getattr(meter, "event_name", None) != event_name:
                continue
            # C2: don't silently bind to a misconfigured existing meter.
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
        logger.warning(
            "Meter.list failed during ensure_stripe_meter(%r): %s. "
            "Falling through to Meter.create.",
            event_name,
            exc,
        )

    # 2. Create a new meter with the canonical config.
    #
    # SS1: idempotency_key keyed by event_name. Concurrent seeds within
    # Stripe's 24h idempotency cache window share the response → no
    # duplicates. After 24h, Meter.list above finds the existing meter
    # so we never reach create.
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

    Three things must be true:

    1. ``default_aggregation.formula == "sum"`` — the reversal pattern
       in ``app/api/wedding.py`` (``value="-1"``) only nets correctly
       on Sum.
    2. ``customer_mapping.event_payload_key == "stripe_customer_id"``.
    3. ``value_settings.event_payload_key == "value"``.

    Raises:
        ValueError: meter is misconfigured or doesn't exist. Callers
            in HTTP contexts should wrap as ``HTTPException(400, ...)``.
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

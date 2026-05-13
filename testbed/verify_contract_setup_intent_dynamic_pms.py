#!/usr/bin/env python3
"""Live E2E driver: contract-sign SetupIntent uses dynamic payment methods.

Background (2026-05-12 Stripe-guidelines audit):
Stripe's current integration guidance (per the Integration Options doc at
https://docs.stripe.com/payments/payment-methods/integration-options.md)
says integrations should NOT hardcode ``payment_method_types=["card"]`` on
SetupIntent or PaymentIntent. Instead, set ``automatic_payment_methods=
{"enabled": True}`` and let Stripe surface payment methods from the
merchant's Dashboard configuration (wallets, BNPL, ACH, link, etc).

Pre-fix, ``app/api/contracts.py::create_setup_intent`` (the
``/contracts/{token}/setup-intent`` endpoint that opens the
StripePaymentCapture component for a couple signing a vendor contract)
hardcoded ``payment_method_types=["card"]``. The second SetupIntent in
the same file (update-payment-method flow) already used
``automatic_payment_methods``. The fix aligned the first call with the
second.

This driver verifies the fix end-to-end against a live Stripe test
account.

Phases:

* **D1 — Setup.** Create a Stripe test Customer (no need for a Mongo
  contract row — we call ``stripe.SetupIntent.create`` directly with the
  same kwargs the production endpoint uses).

* **D2 — Create SetupIntent.** Use the SAME kwargs the production
  endpoint sends post-fix: ``automatic_payment_methods={"enabled": True}``,
  no ``payment_method_types``. Capture the returned SetupIntent id and
  ``automatic_payment_methods`` config.

* **D3 — Pin contract.** Assert:
    - ``setup_intent.automatic_payment_methods.enabled == True``
    - ``setup_intent.payment_method_types`` is a LIST of multiple methods,
      not just ``["card"]`` — at minimum card is present plus whatever the
      Stripe test account has enabled (link is usually on by default).
      Strict assert: ``"card" in payment_method_types``. Soft probe (warn
      not assert): if list length is 1, the merchant may have only
      enabled card in the Dashboard.
    - ``setup_intent.metadata.action == "contract_sign"`` (proves the
      metadata wiring still works).

* **D4 — Negative control.** Re-run the SAME call with
  ``payment_method_types=["card"]`` instead (the OLD pattern) and assert
  the response has ``automatic_payment_methods`` unset and
  ``payment_method_types == ["card"]`` — confirms the difference is
  observable from the Stripe API response.

* **D5 — Cleanup.** Delete the test Customer; the SetupIntents will
  auto-expire after 24h (Stripe doesn't expose SetupIntent deletion).

Skip discipline: each phase is independent. Set ``CONTRACT_SI_PHASES`` to
a comma-separated subset.

Usage::

    # All phases (interactive — pauses at checkpoints)
    python testbed/verify_contract_setup_intent_dynamic_pms.py

    # Specific phases
    CONTRACT_SI_PHASES=D1,D2,D3 python testbed/verify_contract_setup_intent_dynamic_pms.py

    # Unattended
    TESTBED_NON_INTERACTIVE=1 python testbed/verify_contract_setup_intent_dynamic_pms.py

WARNING: This driver creates a real Stripe test Customer + SetupIntents.
Use a test key. The fixture customer email uses a unique suffix to avoid
collision with prior runs.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe  # noqa: E402

from testbed.harness import Harness  # noqa: E402

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_contract_setup_intent_dynamic_pms"
ALL_PHASES = ("D1", "D2", "D3", "D4", "D5")


def _selected_phases() -> list[str]:
    raw = os.getenv("CONTRACT_SI_PHASES")
    if not raw:
        return list(ALL_PHASES)
    selected = [p.strip().upper() for p in raw.split(",") if p.strip()]
    invalid = [p for p in selected if p not in ALL_PHASES]
    if invalid:
        raise SystemExit(f"Unknown phase(s): {invalid}. Valid: {ALL_PHASES}")
    return selected


def _fixture_email() -> str:
    """Generate a unique fixture email per run to avoid prior-run collision."""
    suffix = int(time.time())
    return f"testbed+contract-si-{suffix}@thespecialwedding.io"


# =============================================================================
# Phases
# =============================================================================


def phase_d1_setup(h: Harness) -> stripe.Customer:
    """D1 — Create a Stripe test Customer for the SetupIntent fixture."""
    h.phase("D1_SETUP", "Create test Stripe Customer for contract-SI fixture")

    email = _fixture_email()
    customer = stripe.Customer.create(
        email=email,
        name="Testbed Contract Signer",
        metadata={
            "source": "testbed_contract_setup_intent",
            "driver": DRIVER_NAME,
        },
    )
    h.log.info(f"  Created Customer {customer.id} for {email}")
    return customer


def phase_d2_create_setup_intent(
    h: Harness, customer: stripe.Customer
) -> stripe.SetupIntent:
    """D2 — Mirror the production ``create_setup_intent`` call (post-fix).

    Uses the exact kwargs from ``app/api/contracts.py::create_setup_intent``
    after the 2026-05-12 fix that removed ``payment_method_types=["card"]``
    and added ``automatic_payment_methods={"enabled": True}``.
    """
    h.phase(
        "D2_CREATE_SETUP_INTENT",
        "Create SetupIntent with automatic_payment_methods enabled",
    )

    setup_intent = stripe.SetupIntent.create(
        customer=customer.id,
        automatic_payment_methods={"enabled": True},
        metadata={
            "contract_id": "fixture_contract_id_for_testbed",
            "contract_token": "fixture_token_for_testbed",
            "action": "contract_sign",
        },
    )
    h.log.info(f"  SetupIntent created: {setup_intent.id}")
    h.log.info(
        f"  automatic_payment_methods: {dict(setup_intent.automatic_payment_methods or {})}"
    )
    h.log.info(f"  payment_method_types: {list(setup_intent.payment_method_types)}")
    return setup_intent


def phase_d3_pin_dynamic_methods_contract(
    h: Harness, setup_intent: stripe.SetupIntent
) -> None:
    """D3 — Pin the dynamic-payment-methods contract.

    Strict assertions:
      - automatic_payment_methods.enabled == True
      - payment_method_types contains 'card' (always Stripe default)
      - metadata.action passes through as 'contract_sign'

    Soft probe (warn, do not fail): if payment_method_types is ONLY
    ['card'], the operator's Stripe Dashboard hasn't enabled any other
    methods. The fix still works correctly; this is just visibility.
    """
    h.phase("D3_PIN_CONTRACT", "Pin: dynamic payment methods enabled")

    apm = setup_intent.automatic_payment_methods or {}
    assert apm.get("enabled") is True, (
        f"D3: automatic_payment_methods.enabled should be True, got "
        f"{apm!r}. The fix at app/api/contracts.py:create_setup_intent "
        "may have regressed."
    )
    h.log.info("  ✅ automatic_payment_methods.enabled == True")

    pm_types = list(setup_intent.payment_method_types)
    assert "card" in pm_types, (
        f"D3: 'card' should be in payment_method_types, got {pm_types!r}"
    )

    if len(pm_types) == 1:
        h.log.warning(
            f"  ⚠️  Only one payment method enabled ({pm_types[0]!r}). The "
            "fix is working, but the Stripe Dashboard hasn't enabled any "
            "additional payment methods. Visit Stripe → Settings → Payment "
            "methods to enable Link / Apple Pay / Google Pay / ACH / etc."
        )
    else:
        h.log.info(
            f"  ✅ payment_method_types surfaces {len(pm_types)} methods: {pm_types!r}"
        )

    metadata = dict(setup_intent.metadata or {})
    assert metadata.get("action") == "contract_sign", (
        f"D3: metadata.action should pass through; got {metadata!r}"
    )
    h.log.info("  ✅ metadata.action == 'contract_sign' (passes through)")


def phase_d4_negative_control(h: Harness, customer: stripe.Customer) -> None:
    """D4 — Negative control: card-only path produces a different shape.

    Creates a SetupIntent the OLD way (``payment_method_types=["card"]``,
    no ``automatic_payment_methods``) and asserts the response differs
    from D2's. This proves the fix in D2 is observable via the Stripe API
    — not just a no-op syntactic difference.
    """
    h.phase("D4_NEGATIVE_CONTROL", "Card-only legacy pattern produces different shape")

    legacy_si = stripe.SetupIntent.create(
        customer=customer.id,
        payment_method_types=["card"],
        metadata={
            "contract_id": "fixture_legacy_card_only",
            "contract_token": "fixture_legacy_token",
            "action": "contract_sign_legacy_card_only",
        },
    )
    h.log.info(f"  Legacy SetupIntent: {legacy_si.id}")
    h.log.info(
        f"  automatic_payment_methods: {dict(legacy_si.automatic_payment_methods or {})}"
    )
    h.log.info(f"  payment_method_types: {list(legacy_si.payment_method_types)}")

    apm = legacy_si.automatic_payment_methods
    # Stripe may return automatic_payment_methods={enabled: False} or None
    # depending on API version. Either way the surface is restricted.
    assert apm is None or apm.get("enabled") is not True, (
        f"D4: legacy pattern should NOT have automatic_payment_methods enabled, "
        f"got {dict(apm or {})!r}"
    )
    h.log.info("  ✅ legacy pattern does NOT enable automatic_payment_methods")

    pm_types = list(legacy_si.payment_method_types)
    assert pm_types == ["card"], (
        f"D4: legacy pattern should restrict payment_method_types to ['card'], "
        f"got {pm_types!r}"
    )
    h.log.info("  ✅ legacy pattern restricts payment_method_types to ['card']")


def phase_d5_cleanup(h: Harness, customer: stripe.Customer) -> None:
    """D5 — Delete the fixture Customer.

    Stripe doesn't expose SetupIntent.delete; they auto-expire after 24h.
    The fixture Customer can be deleted, which also archives any attached
    SetupIntents from a billing-history standpoint.
    """
    h.phase("D5_CLEANUP", f"Delete fixture Customer {customer.id}")
    try:
        stripe.Customer.delete(customer.id)
        h.log.info(f"  ✅ Deleted Customer {customer.id}")
    except stripe.error.StripeError as exc:
        h.log.warning(f"  Could not delete Customer {customer.id}: {exc}")


# =============================================================================
# Entrypoint
# =============================================================================


def main() -> int:
    h = Harness(DRIVER_NAME)
    h.banner(f"{DRIVER_NAME} — contract SetupIntent dynamic-PM verification")

    phases = _selected_phases()
    h.log.info(f"Running phases: {', '.join(phases)}")

    customer: stripe.Customer | None = None
    setup_intent: stripe.SetupIntent | None = None

    try:
        if "D1" in phases:
            customer = phase_d1_setup(h)

        if "D2" in phases:
            if customer is None:
                raise SystemExit("D2 requires the Customer from D1 — include D1.")
            setup_intent = phase_d2_create_setup_intent(h, customer)

        if "D3" in phases:
            if setup_intent is None:
                raise SystemExit("D3 requires the SetupIntent from D2 — include D2.")
            phase_d3_pin_dynamic_methods_contract(h, setup_intent)

        if "D4" in phases:
            if customer is None:
                raise SystemExit("D4 requires the Customer from D1 — include D1.")
            phase_d4_negative_control(h, customer)

        if "D5" in phases:
            if customer is None:
                h.log.info("D5: no Customer in scope (D1 not run); skipping")
            else:
                phase_d5_cleanup(h, customer)

        h.banner("ALL PHASES PASSED")
        return 0

    except AssertionError as exc:
        h.log.error(f"❌ ASSERTION FAILED: {exc}")
        if customer is not None:
            h.log.error(
                f"  Fixture Customer {customer.id} left in place for inspection."
            )
            h.log.error("  Re-run with CONTRACT_SI_PHASES=D5 to clean up.")
        return 1
    except Exception as exc:
        h.log.exception(f"❌ UNEXPECTED ERROR: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

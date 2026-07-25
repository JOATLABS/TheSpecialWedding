"""Predicates for whether a planner is set up to collect couple payments.

Stripe Connect onboarding is the gate that lets a planner take card payments
from couples and have the funds settle to their own connected account
(via `transfer_data.destination` on the PaymentIntent). Without it, the
contract-sign auto-charge path still succeeds — but with no destination —
and the money lands in the platform Stripe account instead of the planner's.

This module is the single source of truth for "can this planner accept a
package payment right now?" so every callsite (the package-send route, the
contract-sign auto-charge fallback, autopilot retry paths, etc.) reads the
same answer.

Mirrors the pattern in `planner_billing_scope.py`: an isolated module
exposing predicates over a user document.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Mongo `users` collection field names — kept here so callers don't sprinkle
# string literals across the codebase.
CONNECT_ID_FIELD = "stripe_connect_id"
CONNECT_CHARGES_ENABLED_FIELD = "stripe_connect_charges_enabled"
CONNECT_DETAILS_SUBMITTED_FIELD = "stripe_connect_details_submitted"
CONNECT_PAYOUTS_ENABLED_FIELD = "stripe_connect_payouts_enabled"

# API error code returned by routes that gate on Connect readiness so the
# frontend can branch (e.g., toast + CTA back to /admin/planner/billing).
CONNECT_NOT_READY_CODE = "CONNECT_NOT_READY"


def planner_can_collect_payments(user_doc: Mapping[str, Any] | None) -> bool:
    """Return True when the planner can accept a couple payment.

    We check both `details_submitted` (planner finished hosted onboarding)
    and `charges_enabled` (Stripe approved them to take card payments).
    `payouts_enabled` is intentionally NOT required — Stripe sometimes
    holds payouts pending verification while still allowing charges, and
    in that case the funds accrue safely on the connected account until
    payouts resume. The planner can still collect.
    """

    if not user_doc:
        return False
    if not user_doc.get(CONNECT_ID_FIELD):
        return False
    if not user_doc.get(CONNECT_CHARGES_ENABLED_FIELD):
        return False
    if not user_doc.get(CONNECT_DETAILS_SUBMITTED_FIELD):
        return False
    return True


def connect_not_ready_detail(setup_url: str = "/admin/planner/billing") -> dict:
    """Standard error body for 4xx responses when the gate trips.

    Frontend code branches on `code == CONNECT_NOT_READY_CODE` to surface
    a "set up payouts" CTA pointing at `setup_url`.
    """

    return {
        "code": CONNECT_NOT_READY_CODE,
        "message": (
            "Set up Stripe payouts before sending packages — without it, any "
            "couple payment would route to the platform instead of you."
        ),
        "setup_url": setup_url,
    }

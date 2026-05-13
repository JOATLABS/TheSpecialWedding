#!/usr/bin/env python3
"""Read-only Stripe inspector for leftovers from prior pricing strategies.

After the 2026-05-12 pricing refresh ($29→$49, $59→$149, $149→$399, plus
the unlimited-weddings rework), the Stripe test account inevitably carries
a tail of artifacts:

* **Archived Prices** — every time the seed's ``_ensure_seed_price`` helper
  detects a unit_amount mismatch, it creates a new Price and archives the
  old one (per Stripe's immutability contract). After multiple refreshes
  there will be several archived Prices per Product.

* **Orphan Products** — Products created by the seed script during failed
  runs or for test fixtures (e.g. ``plan_testbed_price_refresh``) that
  weren't cleaned up.

* **Products from the metered experiment** — the 2026-05-04 metered
  hardening may have left behind metered Prices that we now keep around
  as inactive history.

This script lists everything so an operator can decide what to clean up
in the Stripe Dashboard. It does NOT delete or archive anything — Stripe
doesn't allow Price deletion, and Product archival is a per-Product
decision an operator should make in the UI.

Usage::

    # Default: scan only products with metadata.source = 'seed_script' or
    # a known plan_id metadata key.
    STRIPE_SECRET_KEY=sk_test_xxx python scripts/inspect_stripe_leftovers.py

    # Scan ALL active+archived products on the account
    INSPECT_ALL_PRODUCTS=1 python scripts/inspect_stripe_leftovers.py

    # Only flag prices that don't match the current seed
    SHOW_ONLY_DRIFT=1 python scripts/inspect_stripe_leftovers.py

Output is plain text, grep-friendly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import stripe
    from stripe import StripeError
except ImportError:
    print("[ERROR] stripe package not installed", file=sys.stderr)
    sys.exit(1)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY")
if not STRIPE_KEY:
    print("[ERROR] STRIPE_SECRET_KEY not set", file=sys.stderr)
    sys.exit(1)
stripe.api_key = STRIPE_KEY

if not STRIPE_KEY.startswith("sk_test_"):
    print(
        "[WARN] STRIPE_SECRET_KEY does not start with 'sk_test_' — you may "
        "be inspecting LIVE Stripe data. Continue? [y/N] ",
        end="",
    )
    if input().strip().lower() not in ("y", "yes"):
        sys.exit(0)

INSPECT_ALL_PRODUCTS = os.getenv("INSPECT_ALL_PRODUCTS", "").lower() in {
    "1",
    "true",
    "yes",
}
SHOW_ONLY_DRIFT = os.getenv("SHOW_ONLY_DRIFT", "").lower() in {"1", "true", "yes"}


# Mirror of the current seed's canonical plan amounts. Kept inline rather
# than imported from scripts/seed_subscription_plans.py to avoid that
# module's mongo-connect side effects on import.
CURRENT_SEED_AMOUNTS_CENTS = {
    "plan_solo": {"monthly": 0, "yearly": 0},
    "plan_boutique": {"monthly": 4900, "yearly": 49000},
    "plan_signature": {"monthly": 14900, "yearly": 149000},
    "plan_enterprise": {"monthly": 39900, "yearly": 399000},
}


def _list_products() -> list:
    """Return Products to inspect, filtered or not per env flag."""
    products = []
    if INSPECT_ALL_PRODUCTS:
        # Get every product, active and archived.
        for active_filter in (True, False):
            for prod in stripe.Product.list(
                active=active_filter, limit=100
            ).auto_paging_iter():
                products.append(prod)
    else:
        # Filter to seed-created or plan-tagged products.
        for prod in stripe.Product.list(active=True, limit=100).auto_paging_iter():
            meta = prod.metadata or {}
            if meta.get("source") == "seed_script" or meta.get("plan_id"):
                products.append(prod)
        for prod in stripe.Product.list(active=False, limit=100).auto_paging_iter():
            meta = prod.metadata or {}
            if meta.get("source") == "seed_script" or meta.get("plan_id"):
                products.append(prod)
    return products


def _summarize_price(price) -> str:
    """One-line summary of a Stripe Price."""
    amount = price.unit_amount
    interval = price.recurring.interval if price.recurring else "one-time"
    usage = price.recurring.usage_type if price.recurring else "—"
    active = "active" if price.active else "ARCHIVED"
    return f"{price.id}  ${amount / 100:>7.2f} / {interval:5}  usage={usage:8} {active}"


def _classify_drift(price, plan_id: str | None) -> str:
    """Return drift status: MATCH / DRIFT / UNKNOWN / NO-SEED-ENTRY."""
    if not plan_id or plan_id not in CURRENT_SEED_AMOUNTS_CENTS:
        return "NO-SEED-ENTRY"
    if not price.recurring:
        return "UNKNOWN (not recurring)"
    interval = price.recurring.interval
    expected = CURRENT_SEED_AMOUNTS_CENTS[plan_id].get(
        {"month": "monthly", "year": "yearly"}.get(interval)
    )
    if expected is None:
        return "UNKNOWN (interval)"
    if price.unit_amount == expected:
        return "MATCH"
    return f"DRIFT (expected ${expected / 100:.2f}, got ${price.unit_amount / 100:.2f})"


def main() -> int:
    print("=" * 70)
    print("STRIPE LEFTOVER INSPECTOR")
    print(f"  Mode: {'ALL PRODUCTS' if INSPECT_ALL_PRODUCTS else 'seed-tagged only'}")
    print(f"  Filter: {'drift only' if SHOW_ONLY_DRIFT else 'show everything'}")
    print("=" * 70)

    try:
        products = _list_products()
    except StripeError as exc:
        print(f"[ERROR] Stripe API error: {exc}", file=sys.stderr)
        return 1

    if not products:
        print(
            "\nNo products matched the filter. Set INSPECT_ALL_PRODUCTS=1 "
            "to scan everything."
        )
        return 0

    print(f"\nFound {len(products)} product(s):\n")

    total_prices = 0
    archived_prices = 0
    drift_prices = 0
    orphan_products = 0

    for prod in products:
        meta = prod.metadata or {}
        plan_id = meta.get("plan_id")
        status_tag = "ACTIVE" if prod.active else "ARCHIVED"
        print(f"  [{status_tag}] {prod.id}  ({prod.name})")
        print(f"          plan_id metadata: {plan_id or '—'}")
        print(f"          description: {(prod.description or '')[:80]}")

        try:
            prices = list(
                stripe.Price.list(product=prod.id, limit=100).auto_paging_iter()
            )
        except StripeError as exc:
            print(f"          [WARN] could not list prices: {exc}")
            continue

        if not prices:
            print("          (no prices — orphan product candidate)")
            orphan_products += 1
            print()
            continue

        for price in prices:
            total_prices += 1
            if not price.active:
                archived_prices += 1
            drift = _classify_drift(price, plan_id)
            if drift.startswith("DRIFT"):
                drift_prices += 1
            if SHOW_ONLY_DRIFT and not drift.startswith("DRIFT"):
                continue
            print(f"          {_summarize_price(price)}  [{drift}]")
        print()

    print("=" * 70)
    print("SUMMARY")
    print(f"  Products inspected:  {len(products)}")
    print(f"  Total prices:        {total_prices}")
    print(f"  Archived prices:     {archived_prices}")
    print(f"  Drift vs seed:       {drift_prices}")
    print(f"  Orphan products:     {orphan_products}")
    print("=" * 70)
    print()
    print(
        "Cleanup recipes (run in Stripe Dashboard — Stripe API does not "
        "allow Price deletion):"
    )
    print("  • Archived prices: leave them. Grandfathered subscriptions may")
    print("    still reference them.")
    print("  • Orphan products: archive in Stripe Dashboard if no longer")
    print("    referenced by any active Price or Subscription.")
    print("  • DRIFT prices: investigate. If they're attached to a current")
    print("    subscription, you may need a Subscription Item migration")
    print("    before archiving (see Stripe docs:")
    print("    https://docs.stripe.com/billing/subscriptions/change-price).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

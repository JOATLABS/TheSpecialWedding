# Metering Audit — The Special Wedding SaaS

**Author:** Claude (paired with Etastic)
**Date:** 2026-04-17
**Status:** Updated 2026-05-10 after product correction. Canonical public plans are intentionally metered on `wedding_active`; flat-rate is no longer the accepted default. See `docs/qa/BILLING_STABILIZATION_STATUS.md` for the live stabilization checklist.

---

## 2026-05-10 Billing Model Decision

The accepted production posture is **Path A: metered billing enabled intentionally**.

| Area | Production-ready now | Guarded / follow-up |
| --- | --- | --- |
| Canonical public plans | Boutique, Signature, and Enterprise seed with `billing_model="metered"`, `is_metered=True`, and `meter_event_name="wedding_active"`. | Seed owns billing model/Meter fields; root admin owns mutable pricing, limits, features, highlights, and visibility after creation. |
| Stripe sync | Seed and admin sync create/resolve Stripe Meters and metered Prices with `recurring.usage_type="metered"`. | Existing flat subscription items still require an explicit Stripe subscription-item migration. |
| Wedding usage | Wedding create/delete hooks report `wedding_active` meter events when the subscriber plan is metered. | `/billing/sync-usage` and `/metering/retry-pending` are root-admin/manual endpoints; scheduler wiring is still a deployment follow-up. |
| Grandfathering | New snapshots record `billing_model`, `is_metered`, `meter_event_name`, and `meter_id`. | Historical snapshots may need repair/backfill. Billing-model flips with active subscriptions are blocked unless `TSW_ALLOW_PLAN_BILLING_MODEL_MIGRATION=true`. |
| Admin plan editing | Root admin can edit pricing, feature flags, public feature highlights, limits, active/featured state, and display order for metered plans. | Switching an active plan between flat and metered is blocked without a migration flag because existing Stripe subscriptions stay on old Prices. |

Operator notes:

- Do not flip a live flat plan to metered by editing Mongo alone. Existing Stripe subscriptions keep their current subscription item Price until explicitly migrated.
- Before enabling or reseeding metering in a live environment that may already have active flat subscribers, run the subscription-item migration or keep `TSW_ALLOW_PLAN_BILLING_MODEL_MIGRATION` unset so the guard aborts the seed/update.
- Live verification command, when Stripe and Mongo testbed config are present:

```bash
TESTBED_NON_INTERACTIVE=1 python testbed/verify_metered_seed_e2e.py
```

---

## Executive Summary

The metering infrastructure is built end-to-end and is now the intended production billing model:

- `scripts/seed_subscription_plans.py` and `/system/seed-default-plans` emit canonical public plans as metered on `wedding_active`.
- `app/services/stripe_service.py` resolves or validates Stripe Meters before creating metered Prices.
- `app/api/wedding.py` reports create/delete meter events for metered plans.
- `app/api/billing_jobs.py` can catch up missed usage.
- `app/api/metering.py` can retry pending events.
- Subscription snapshots carry the billing model fields needed for grandfathering.
- Root-admin plan editing preserves seeded feature flags and public feature highlights instead of dropping unknown feature keys.

The remaining production risk is not whether metering is wired. It is migration and operations:

- Existing live Stripe subscription items may still point at old flat Prices.
- `/billing/sync-usage` has no repo-owned scheduler wiring.
- Negative usage reversal semantics still need a product/Stripe policy decision.
- Stripe Product search eventual consistency can still create operational awkwardness during deploys.

---

## Current Route And Service Map

### Plan Model

`app/models/subscription.py`

- Defaults new plan models and create requests to `billing_model="metered"`, `is_metered=True`, and `meter_event_name="wedding_active"`.
- Update requests accept `features_list` and `display_order` so root admin changes survive the API boundary.

### Seed

`scripts/seed_subscription_plans.py`

- Seeds Boutique, Signature, and Enterprise as metered.
- Preserves existing root-admin pricing, limits, feature flags, public feature highlights, and visibility for already-created plans.
- Writes `billing_model`, `is_metered`, `meter_event_name`, and `meter_id` on every deploy; mutable plan fields are only set on insert.
- Provisions or validates the Stripe Meter before creating metered Prices.
- Aborts instead of changing a flat plan to metered while active subscriptions exist, unless `TSW_ALLOW_PLAN_BILLING_MODEL_MIGRATION=true`.

### Stripe Sync

`app/services/stripe_service.py`

- Resolves `meter_id` from `meter_event_name` if needed.
- Requires a valid Stripe Meter before metered Price sync.
- Creates prices with `recurring.usage_type="metered"` and `recurring.meter=<meter_id>`.
- Omits Checkout quantity for metered line items.
- Snapshots billing model fields on subscription creation/sync.

### Wedding Meter Events

`app/api/wedding.py`

- On create, reports `value="1"` using idempotency key `wedding_create_{wedding_id}_{customer_id}_{YYYY-MM}`.
- On delete, reports `value="-1"` once per period using idempotency key `wedding_delete_{wedding_id}_{customer_id}_{YYYY-MM}`.
- Marks `meter_pending=True` when Stripe reporting fails so recovery paths can find it.

### Catch-Up And Retry

`app/api/billing_jobs.py`

- `/billing/sync-usage` walks active subscriptions and reports missing current-period wedding usage for metered plans.
- No repo-managed cron/scheduler was found.

`app/api/metering.py`

- `/metering/retry-pending` retries `meter_pending=True` weddings in batches.

### Admin And Public UI

`app/admin/saas/page.tsx`

- Shows the current billing model on plan cards and inside the edit modal.
- Allows root admin to edit metered pricing and feature configuration.
- Preserves known seeded feature keys and unknown future keys through `planFeatureConfig.ts`.
- Sends `features_list`, yearly pricing, limits, display order, active state, and metered fields to the API.

Public pricing surfaces now receive `billing_model` and `is_metered` from `/public/subscription-plans` and render metered units such as `/active wedding/mo`.

---

## Live Checks Still Needed

These require production/staging Mongo and Stripe access:

1. Mongo plan state:
   `db.subscription_plans.find({}, { _id: 1, name: 1, billing_model: 1, is_metered: 1, meter_event_name: 1, meter_id: 1, stripe_price_id_monthly: 1 })`
2. Stripe Price shape: linked Prices should have `recurring.usage_type == "metered"` and `recurring.meter` set.
3. Stripe Meter resources: confirm a valid active `wedding_active` Meter exists.
4. Existing subscriptions: list active subscription items that still point at flat Prices.
5. Scheduler: confirm `/billing/sync-usage` is called by production cron or add that wiring.
6. Pending backlog: `db.weddings.countDocuments({ meter_pending: true })`.

---

## Current Follow-Ups

1. Write and run a Stripe subscription-item migration for any existing flat subscribers.
2. Add scheduled production wiring for `/billing/sync-usage`.
3. Decide whether delete reversals should move from negative meter events to Stripe MeterEventAdjustment.
4. Backfill old active subscription snapshots if every historical subscription must carry explicit billing model fields.
5. Replace Stripe Product search dependency with a more deterministic product lookup strategy.

# Metering Audit — The Special Wedding SaaS

**Author:** Claude (paired with Etastic)
**Date:** 2026-04-17
**Status:** Investigation complete. No code changes made. Awaiting review before any plan-config or Stripe changes.
**Context:** Surfaced while resuming PR1 live verification of the team-member billing gate. Etastic's expected mental model is "the whole billing is metering." What the repo actually ships today is different, and the gap is worth pinning down before the PR1 test matrix continues.

---

## 1. Executive Summary

The metering **infrastructure** is built end-to-end: wedding create/delete hooks report meter events, a daily batch job catches up usage, a retry endpoint reprocesses failures, the Plan model has metering fields, and the admin UI exposes a toggle for metered plans.

The **default plan config does not turn metering on**. `scripts/seed_subscription_plans.py` sets `is_metered: False` on all three canonical plans (Boutique / Signature / Enterprise), so in practice today's customers are billed at a flat monthly or yearly price. Every metering code path is gated on `plan.is_metered == True AND plan.meter_event_name` — if either is falsy, the meter call is silently skipped.

That means:

- Today's live system bills as flat subscription with hard `max_weddings` caps.
- The metering code is dormant but wired in — flipping `is_metered` on a plan would route subsequent wedding CRUD through `stripe.billing.MeterEvent.create`.
- To go metered end-to-end you additionally need (a) a Stripe Meter resource, (b) Stripe prices created with `recurring.usage_type = "metered"` and `meter = <meter_id>`, and (c) a decision about what to do with `max_weddings` caps when metering is on.

There is no single commit or PR that turned metering "off" recently — the seed file has always specified flat plans. The infrastructure and the seed have drifted from each other over time.

---

## 2. What's Actually Built

All paths below are relative to the repo root (`/Users/emmanuelakinwale/Desktop/WeddingWebApp`).

### 2.1 Plan model

`app/models/subscription.py:115-123`

```python
# Metered Billing Support
is_metered: bool = Field(False, description="Whether this plan uses metered billing")
meter_event_name: Optional[str] = Field(None, description="Stripe Meter Event Name for usage reporting")
meter_id: Optional[str] = Field(None, description="Stripe Meter ID")
```

Default `is_metered=False`. Both `meter_event_name` and `meter_id` are optional.

### 2.2 Stripe service — plan sync honors metering

`app/services/stripe_service.py:171-327` (`sync_plan_to_stripe`)

- Lines 184-204: if `is_metered` is set, the service tries to resolve `meter_id` from `meter_event_name` via `stripe.billing.Meter.list(status="active")`. If it cannot resolve a `meter_id`, it raises 400.
- Lines 240-308 (`ensure_price`): when the plan is metered, it creates the Stripe price with `recurring = {"interval": ..., "usage_type": "metered", "meter": <meter_id>}`. When a plan is flipped between flat and metered, it detects the mismatch (line 266-273) and creates a fresh price, deactivating the old one.

### 2.3 Meter event call

`app/services/stripe_service.py:369-423` (`report_meter_event`)

- Wraps `stripe.billing.MeterEvent.create(event_name, payload, timestamp, identifier)`.
- Truncates the idempotency `identifier` to 100 chars (Stripe's hard limit).
- Treats duplicate-identifier errors as success (true idempotency). This is the right shape for safe retries.

### 2.4 Wedding create hook — real-time meter

`app/api/wedding.py:140-244`

Trigger: any non-root-admin wedding creation.

Logic:
1. Increment local usage counter (`subscription_service.increment_usage`).
2. Load user's active subscription; require `stripe_customer_id` and `plan_id`.
3. Load plan; require `is_metered == True` and `meter_event_name`.
4. Check `wedding.last_billed_at >= current_period_start` — if already billed this period, skip.
5. Otherwise call `report_meter_event` with `value: "1"` and idempotency key `wedding_create_{wedding_id}_{customer_id}_{YYYY-MM}`.
6. On success: set `last_billed_at`, `billed_period`, clear `meter_pending`.
7. On failure: mark `meter_pending=True` with a reason string — this is what the admin weddings page shows as a badge.

### 2.5 Wedding delete hook — meter reversal

`app/api/wedding.py:355-413`

Before cascade delete:
1. Find the planner and their active subscription the same way.
2. If the plan is metered and this wedding has not been reversed this period (`meter_reversed_period != current_period`), call `report_meter_event` with `value: "-1"` and idempotency key `wedding_delete_{wedding_id}_{customer_id}_{YYYY-MM}`.
3. Mark `meter_reversed_period` on success, or set `meter_pending=True` on failure.

Design note: the current implementation reverses once per period. This means a delete + re-create in the same period would net out to zero — which matches "pay per active wedding this month" semantics but is worth confirming as intended.

### 2.6 Daily batch — catches up missed weddings

`app/api/billing_jobs.py:17-141` (`/billing/sync-usage` → `process_daily_usage_check`)

Iterates every active subscription, skips any plan that is not metered, then iterates that user's active weddings. For every wedding whose `last_billed_at` is older than `current_period_start` (or missing), it reports a meter event with idempotency key `billing_job_{wedding_id}_{customer_id}_{YYYY-MM}`.

This is the safety net if the real-time hook ever fails. Must be called by a scheduler — I did not find a cron wired up in the repo.

### 2.7 Retry endpoint — operator recovery

`app/api/metering.py:16-133` (`POST /metering/retry-pending`, ROOT_ADMIN only)

Walks weddings with `meter_pending=True` in batches of 100, resolves the planner → subscription → plan chain, and reports `value: "1"` with idempotency key `meter_retry_{wedding_id}_{customer_id}_{YYYY-MM}` (current-period, so retries land in the current billing month). Returns a `{retried, succeeded, failed[]}` summary.

### 2.8 Admin UI — plan editor exposes toggle

`app/admin/saas/page.tsx`
- Line 39-40: TypeScript Plan type includes `is_metered` and `meter_event_name`.
- Line 1350-1352: plan card renders a "Metered: {event_name}" badge when `is_metered` is true.
- Line 1550-1565: plan edit form shows an `is_metered` checkbox and a `meter_event_name` text input (default `wedding_active`).

`app/admin/weddings/page.tsx:1150-1152` renders a "Meter pending" badge with the failure reason when a wedding doc has `meter_pending=True`.

So an operator can flip a plan to metered through the UI without touching the database — provided the Stripe side has a matching Meter resource.

---

## 3. The Drift

`scripts/seed_subscription_plans.py:215-310` sets `is_metered: False` on every default plan:

| Plan | Price monthly | Trial days | `is_metered` | `max_weddings` |
|------|---------------|------------|--------------|----------------|
| Boutique | $29 | 30 | False | 3 |
| Signature | $59 | 30 | True (featured) — but `is_metered: False` | 10 |
| Enterprise | $149 | 30 | False | -1 (unlimited) |

Combined with the fact that `grep -r "is_metered.*True"` returns zero hits anywhere in the repo, the shipped config is unambiguously flat-rate.

Other drift signals:

- **Plan snapshot omits metering fields.** `app/services/subscription_service.py:239-252` snapshots `max_weddings`, pricing, features, Stripe price IDs — but not `is_metered`, `meter_event_name`, or `meter_id`. Since the live metering logic re-reads the plan (not the snapshot), this is fine *today*. If grandfathering ever needs to pin a user on flat billing after a plan flip, the snapshot would have to be extended.
- **No setup or deploy script flips the flag.** No migration, no init routine, no deploy verification calls it out.
- **Stripe Integration Guide is non-committal.** `docs/guides/STRIPE_INTEGRATION_GUIDE.md:525-527` mentions metering as "if needed" for AI credits — not as the core billing model.

---

## 4. What's Unverified (needs a live check)

These can't be answered from static code. They need Mongo + Stripe reads against the live account.

1. **Live Mongo plan state.** Are all plans in `subscription_plans` still `is_metered: False`, or did someone flip one via the admin UI at some point? Command: `db.subscription_plans.find({}, { _id: 1, name: 1, is_metered: 1, meter_event_name: 1, meter_id: 1, stripe_price_id_monthly: 1 })`.
2. **Stripe-side price shape.** Do the existing Stripe `Price` objects linked from each plan have `recurring.usage_type == "metered"`? If not, even flipping `is_metered` in Mongo without re-running `sync_plan_to_stripe` would leave the Stripe side flat.
3. **Stripe Meter resources.** Does this Stripe account have any `billing.Meter` objects at all? What are their `event_name`s? This is required before a plan can be flipped metered — `sync_plan_to_stripe` raises 400 without one.
4. **Scheduler.** Is `/billing/sync-usage` wired to a cron / Cloudflare Worker / external scheduler? If not, the real-time hook is the only metering path in production — meaning a transient Stripe failure leaves `meter_pending=True` until the retry endpoint is manually called.
5. **Any weddings currently `meter_pending=True`?** A backlog here would suggest metering was briefly on at some point. `db.weddings.countDocuments({ meter_pending: true })`.

---

## 5. Implications for PR1 Verification

Etastic's expanded test matrix:

> test the original 30-days trial then what happens once trial is over, test an active subscription with 1 wedding (the Stripe metering cost) then two weddings then 0 weddings for month to month

Against the current live config, the "1 wedding vs 2 weddings vs 0 weddings" axis does **not** produce different Stripe charges — the customer pays $29/$59/$149 regardless, and `max_weddings` is enforced as a hard cap in code rather than priced per-unit.

Therefore, to actually exercise the metered path end-to-end, one of the following has to happen first:

**Option A — Verify current reality only.** Keep plans flat, and run PR1 verification against the flat billing model. The team-member gate test (past_due blocks team members, active unblocks them) works fine with flat billing — it does not depend on metering.

**Option B — Flip a test plan to metered before verifying.** Create or select one plan (probably Signature), create a matching Stripe Meter (e.g. `wedding_active`), flip `is_metered: True` and set `meter_event_name`, re-sync via `stripe_service.sync_plan_to_stripe` so the Stripe price is re-created with `usage_type="metered"`. Then run the full test matrix including the wedding-count dimension. This is a product decision, not a test-script decision.

**Option C — Product conversation first.** If the intent has always been metering and this is a real gap rather than a deliberate simplification, the conversation is bigger than PR1: pricing page copy, max_weddings semantics under metering, grandfathering, snapshot fields, cron wiring, and customer comms all need alignment before flipping production.

My read: the right path depends on what "metering" is supposed to mean in the product story. If it's "pay per active wedding per month," Option C is where this lands; PR1 verification can proceed in parallel under Option A and be re-run under Option B once a metered plan exists.

---

## 6. Suggested Next Steps

Nothing below is done — this is a proposal for Etastic's review.

1. Confirm product intent on whether monthly billing is supposed to be metered by default. If yes, this becomes a tracked issue separate from PR1.
2. Run the five live checks in §4 against staging and production to establish the actual state.
3. For PR1, proceed with Option A — verify the team-member gate against the current flat plans. This exercises `PLANNER_BLOCKED_SUBSCRIPTION_STATUSES`, which is what PR1 is actually about.
4. File a separate ticket for the metering drift that captures §2-§4 so it doesn't get lost when PR1 closes.
5. If going down the metered path eventually, add metering fields (`is_metered`, `meter_event_name`) to the plan snapshot in `subscription_service.py:239-252` so grandfathering is intact.

---

## 7. Reference — Files Touched in This Audit

Read-only; no edits made.

- `app/models/subscription.py` (Plan model, `PLANNER_BLOCKED_SUBSCRIPTION_STATUSES`)
- `app/api/wedding.py` (create hook 140-244, delete hook 355-413)
- `app/api/metering.py` (retry endpoint, full file)
- `app/api/billing_jobs.py` (daily sync 17-141, cleanup 144+)
- `app/services/stripe_service.py` (plan sync 171-327, meter event 369-423, plan snapshot path 1627+)
- `app/services/subscription_service.py` (plan snapshot 239-252)
- `scripts/seed_subscription_plans.py` (default plan config 215-310)
- `app/admin/saas/page.tsx` (plan editor UI 1350-1565)
- `app/admin/weddings/page.tsx` (meter_pending badge 1150-1152)
- `docs/guides/STRIPE_INTEGRATION_GUIDE.md` (metering mention line 525-527)
- `CHANGELOG.md` (grep: no metering-related entries)

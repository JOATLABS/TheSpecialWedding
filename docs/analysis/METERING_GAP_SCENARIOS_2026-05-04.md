# Stripe Metering — Gap Scenarios That Could Break Our Assumptions

**Date:** 2026-05-04
**Status:** Analysis. The four ship-stopper fixes are implemented (see METERING_IMPLEMENTATION). Other items track as follow-up.

---

## Triage summary

| Tier | Count | Action |
|---|---|---|
| **SHIP-STOPPER** | 5 | Address before flipping any plan metered in prod |
| **CRITICAL** | 8 | High-likelihood × high-impact; mitigate in next PR |
| **EDGE** | 9 | Pin with tests or document |

Five ship-stoppers: SS1 duplicate meters from concurrent seed runs · SS2 flat→metered flip orphans existing customers · SS3 `value=-1` reversal not the documented Stripe API · SS4 Mongo update can fail after Stripe meter event succeeded · SS5 `Product.search` eventual consistency.

---

## SHIP-STOPPERS

### SS1 — Concurrent seed runs create duplicate Stripe Meters ✅ FIXED

**Failure scenario:** Coolify rolling deploy starts 2+ containers in parallel. Each runs the seed. Both `Meter.list` miss before either creates → both call `Meter.create` → two meters with identical `event_name` exist on Stripe.

**Why silent:** Stripe doesn't enforce uniqueness on `event_name`; meters are unique only by `id`.

**Fix shipped:** `ensure_stripe_meter` passes `idempotency_key=f"ensure_stripe_meter_{event_name}"` to `Meter.create`. Stripe's 24h idempotency cache returns the same meter id for any concurrent call within the deploy window. Pinned by `test_ss1_meter_create_passes_idempotency_key`.

### SS2 — Flat→metered flip orphans existing customers on the deactivated flat price ⚠ OPEN

**Failure scenario:** 200 planners are subscribed to the flat monthly price. You flip metered in seed and redeploy. `sync_plan_to_stripe` correctly creates `price_NEW_METERED_MO`, deactivates `price_OLD_FLAT_MO`. **But** `stripe.Subscription.modify` is never called — the 200 existing Subscriptions still reference the old (deactivated) price. They keep billing flat. Their meter events accumulate but never invoice.

**Severity:** High. Silent revenue divergence.

**Recommended fix:** Migrate at flip time (`Subscription.list(price=<old>)` → `Subscription.modify`) OR migrate at next renewal via webhook OR document operator-required manual action.

**Status:** S6 phase in the testbed driver flags this with a checkpoint warning. Not auto-fixed — needs product decision on migration policy.

### SS3 — `value=-1` reversal is not Stripe's documented mechanism ⚠ OPEN

**Failure scenario:** Stripe documents `MeterEventAdjustment.create(cancellation_action="cancel")` as the supported reversal API, with a 24h cancellation window. The codebase emits `value="-1"` instead — works mathematically on Sum aggregation but is not documented.

Cross-period deletes (delete in month B for create in month A) never refund the customer regardless of API: Stripe explicitly does NOT update finalized invoices for cancelled usage.

**Status:** Documented; not auto-fixed. Gates on product decision about cross-period refund semantics.

### SS4 — Mongo update can fail after Stripe meter event succeeded → state divergence ✅ FIXED

**Failure scenario:** Meter event lands at Stripe (customer charged), but the follow-up `update_one({"last_billed_at": ...})` fails. The wedding row has no `last_billed_at`. Daily batch re-fires the meter event with a different idempotency-key prefix (`billing_job_*` vs `wedding_create_*`) → Stripe doesn't dedupe across prefixes → **customer is double-billed**.

**Fix shipped:** New `app/utils/meter_state.py::update_wedding_meter_state(coll, id, fields, *, context=...)` retries once and logs `STRIPE_MONGO_DIVERGENCE` (grep-able for ops alerting). Wired into all 4 call sites.

### SS5 — `stripe.Product.search` is eventually consistent → seed creates duplicate Products ⚠ OPEN

**Failure scenario:** Fresh deploy. Seed runs `Product.search`, returns empty (correct, plan is new). Seed creates the Product. Container restarts. Seed runs again. `Product.search` runs **before Stripe's metadata index has caught up** → returns empty → seed creates a SECOND Product with same `metadata.plan_id`.

**Status:** Documented; not auto-fixed. Recommended: switch to `Product.list` filtered by metadata, or maintain `stripe_product_id` in Mongo as the source of truth.

---

## CRITICAL gaps

### C1 — `assert_meter_config` doesn't verify the Price `recurring.meter` matches our expected `meter_id`
Plan in Mongo has `meter_id=mtr_NEW`. Stripe Product has a Price with `recurring.meter=mtr_OLD`. Preflight passes, but billing fails silently.

### C2 — `ensure_stripe_meter` returns existing meter without validating its config ✅ FIXED
A hand-created meter with `formula=count` would be silently bound. Now `ensure_stripe_meter` calls `assert_meter_config` on existing matches and raises if invalid. Pinned by `test_c2_existing_misconfigured_meter_is_not_silently_returned`.

### C3 — `assert_meter_config` accepts inactive meters
`Meter.retrieve` returns inactive meters too. Pinned as known caveat in `test_known_caveat_assert_meter_config_does_not_check_status`.

### C4 — Plan flipped on/off across deploys leaves Stripe state inconsistent
Inactive Prices accumulate. Operational hygiene issue.

### C5 — `current_period_start` parsing duplicated; latent local-tz bug ✅ FIXED
Two implementations existed in `wedding.py` and `billing_jobs.py`. The `wedding.py` version used `datetime.now(timezone.utc).astimezone().tzinfo` — the **process's local timezone**, not UTC. Extracted to `app/utils/period_parsing.py::coerce_period_start` with UTC-correct semantics. Pinned by `test_c5_naive_datetime_assumed_utc_not_local` (output) and `test_c5_naive_datetime_uses_utc_constant_not_runtime_local` (source-level).

### C6 — Webhook delays leave `current_period_start` stale → silent under-billing
If `customer.subscription.updated` is delayed 30+ minutes, the wedding-create hook reads stale `current_period_start` and incorrectly skips billing.

### C7 — Multiple "active" subscriptions per user breaks customer attribution
`find_one({"user_id": user_id, "status": ACTIVE})` returns whichever Mongo orders first. Per memory `project_subscription_lifecycle_bug_patterns`, this is exactly the bug class that has bitten before.

### C8 — Whitespace in `meter_event_name` from admin form
Admin form has no trim. `" wedding_active"` would be sent to Stripe — meter event silently rejected.

---

## EDGE cases

E1 `value` field type coercion across SDK versions · E2 Test clock vs Meter aggregation interaction · E3 Stripe API version drift relative to SDK upgrade · E4 `Meter.list` Connect-platform scope · E5 Currency hardcoded `"usd"` · E6 Stripe Meter beta/regional restrictions · E7 Plan deletion doesn't deactivate the Stripe Meter · E8 `_provision_meter_if_needed` log line "Existing meter_id is invalid" can be a false alarm under rate limit · E9 Soft-deleted weddings still match the daily batch query.

---

## Cross-cutting recommendation

Several criticals share a root cause: **the codebase trusts Mongo as runtime source of truth but doesn't lock or version-check writes against concurrent / delayed-webhook scenarios.** The optimistic-locking pattern in `UserSubscriptionModel.version` is a good template — extend it to metering writes.

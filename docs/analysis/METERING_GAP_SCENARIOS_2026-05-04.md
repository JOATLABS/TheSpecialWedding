# Stripe Metering — Gap Scenarios That Could Break Our Assumptions

**Date:** 2026-05-04
**Author:** Claude (paired with Etastic)
**Status:** Analysis only. Findings prioritized; recommended fixes documented but NOT implemented.
**Trigger:** "Any gap scenarios that can break what our logics or assumptions break? That's more important."

**Scope:** Beyond the existing 49-test suite — what could go wrong in production that our tests don't catch, our preflight doesn't reject, and our caveats don't surface?

---

## Triage summary

| Tier | Count | Action |
|---|---|---|
| **SHIP-STOPPER** | 5 | Address before flipping any plan metered in prod |
| **CRITICAL** | 8 | High-likelihood × high-impact; mitigate in next PR |
| **EDGE** | 9 | Pin with tests or document as known-limitation |
| **TOTAL** | 22 |  |

The five ship-stoppers are: (S1) duplicate meters from concurrent seed runs, (S2) flat→metered flip leaves existing customers unmigrated, (S3) `value=-1` reversal not officially supported by Stripe, (S4) Mongo update can fail after Stripe meter event succeeded leaving inconsistent state, (S5) Stripe `Product.search` is eventually-consistent → seed can create duplicate Products on fresh deploy.

---

## SHIP-STOPPERS — must address before going live with metering

### SS1 — Concurrent seed runs create duplicate Stripe Meters

**Failure scenario:** Coolify (or any container orchestrator) starts 2+ containers in parallel during a rolling deploy. Each one runs `scripts/seed_subscription_plans.py`. Each container's seed calls `ensure_stripe_meter` for the same `event_name=wedding_active`. Both `Meter.list` calls happen before either's `Meter.create` returns → both see "no match" → both call `Meter.create` → **two meters with identical `event_name` exist on the Stripe account**.

**Why this is silent and bad:**
- Stripe does NOT enforce uniqueness on `event_name`; meters are unique only by `id`.
- Subsequent meter events would land against ONE of the two meters depending on which `meter_id` was persisted to Mongo last (race winner).
- The other meter accumulates events from any old deployment that still references its id.
- Cycle totals are split. Some weddings billed, some not. Operator has no signal anything is wrong.

**Probability:** High. Coolify deploys are multi-container by default. Any zero-downtime deploy hits this.

**Severity:** High. Silent partial billing.

**Current mitigation:** None. The "fall through to create on list error" branch in `ensure_stripe_meter` makes this worse, not better — it widens the race window.

**Recommended fix:**
1. Pass an `idempotency_key` to `Meter.create`:
   ```python
   stripe.billing.Meter.create(
       ...,
       idempotency_key=f"meter_create_{event_name}",  # Stripe header
   )
   ```
   Stripe's idempotency mechanism caches the response for 24h; concurrent calls with the same key all get the same meter.
2. **Better**: do a Mongo-side mutex. Use `find_and_modify` with `upsert: true` on a `meter_provisioning_locks` collection keyed by `event_name`. Only the lock-winner calls `Meter.create`; losers spin until the lock is released and read the resulting `meter_id` from Mongo.

**Test status:** Not covered. The existing tests for `ensure_stripe_meter` are sequential.

**Tests to add:**
- Unit: mock `Meter.create` to verify `idempotency_key` is passed.
- E2E: phase that runs the seed in two subprocesses simultaneously, asserts post-state has exactly one meter for the event_name.

---

### SS2 — Flat→metered flip orphans existing customers on the deactivated flat price

**Failure scenario:** Plan `signature` is currently flat. 200 planners are subscribed to the flat monthly price `price_OLD_FLAT_MO`. You ship the metered seed flip. `sync_plan_to_stripe` correctly:
- Creates a new `price_NEW_METERED_MO` with `recurring.usage_type=metered`.
- Deactivates `price_OLD_FLAT_MO` (sets `active=false`).
- Updates Mongo to point at the new price.

**But** `stripe.Subscription.modify` is never called. The 200 existing Subscriptions still reference `price_OLD_FLAT_MO`. Stripe continues billing them at the flat rate. New checkouts use the new metered price.

**Why this is bad:**
- The product change is silently scoped to NEW customers only.
- The operator thinks they've shipped metered billing globally; revenue model is split.
- Customers who created weddings will fire meter events that **don't drive billing for them** because their Subscription's price is the deactivated flat one.
- Worst case: meter events accumulate against a Stripe meter linked to a Price that no Subscription points at. The events go to /dev/null (well, to the meter's accumulation but never to an invoice).

**Probability:** High. Default behavior on any flat→metered flip with existing customers.

**Severity:** High. Silent revenue divergence; metered-billing rollout isn't actually rolled out.

**Current mitigation:** S6 in the testbed driver flags this with a `checkpoint` warning. That's documentation, not a fix.

**Recommended fix (one of):**
- **Option A — Migrate existing subs at flip time.** After `sync_plan_to_stripe` returns the new price ID, iterate `Subscription.list(price=<old_price>)` and `Subscription.modify(items=[...])` each one to swap. Use `proration_behavior="none"` to avoid mid-cycle credits.
- **Option B — Migrate at next renewal.** Don't auto-modify; wait for Stripe to renew each Subscription, then have a webhook handler swap the price. Slower migration but no mid-cycle surprise.
- **Option C — Document and require manual operator action.** Don't auto-anything; print a warning post-sync with a count of affected subscriptions.

**Test status:** S6 in the E2E driver pins the symptom (old price deactivated) but does NOT verify any subscription migration. There's no test that this is intentional vs forgotten.

**Tests to add:**
- E2E: create a Stripe test Subscription on the flat price, run the metered flip, assert whether the Subscription's price changed (or didn't, depending on chosen fix).

---

### SS3 — `value=-1` reversal is not Stripe's documented reversal mechanism

**Failure scenario:** Stripe's docs explicitly say to use `MeterEventAdjustment.create(cancellation_action="cancel")` to reverse meter events. The 24-hour cancellation window only applies to that API. The codebase emits `value="-1"` — which works mathematically on Sum aggregation but is not a documented Stripe pattern.

**Three real risks:**

1. **Stripe could change Sum aggregation to reject negative values.** Sum has historically accepted negatives (the docs use a credit-balance example), but billing safety could push Stripe to clamp. The codebase has zero defense.

2. **Finalized invoices are not retroactively corrected.** If a wedding was billed in month A's invoice (already finalized, customer paid), then deleted in month B firing `value="-1"`, Stripe's docs are explicit: month B's cycle total will reflect the `-1`, but month A's invoice is unchanged. Customer paid for month A's wedding. Net effect: customer is short-credited, operator has no signal.

3. **In-window deletes (within 24h) MUST use `MeterEventAdjustment` per Stripe.** The codebase uses `value="-1"` for those too. Stripe's invoice tooling treats adjusted events as not-occurring (eliminated from cycle totals); but `-1` events produce a negative-summed total. The semantics are different.

**Probability:** Medium. Stripe-side change in Sum behavior is unlikely short-term but possible. The cross-period refund issue happens **every time** a wedding is deleted in a different period than it was created in.

**Severity:** High. Customer billing accuracy.

**Current mitigation:** None. The Part 2 review flagged this (CC1) but didn't fix it. Open product question #2 in §7.

**Recommended fix:**
1. Branch `app/api/wedding.py:355-413` (delete hook) on `now - last_billed_at`:
   - **<24h:** call `stripe.billing.MeterEventAdjustment.create(event_name=..., cancellation_action="cancel", ...)`.
   - **>=24h:** keep `value="-1"` BUT explicitly log "no automatic refund — operator must issue credit memo if needed."
2. Add a per-deletion record in Mongo showing `reversal_method: "adjustment"` vs `"negative_value"` for audit.

**Test status:** Existing tests pin the current behavior (`value="-1"` always). No test exercises `MeterEventAdjustment`.

---

### SS4 — Mongo update can fail after Stripe meter event succeeded → state divergence

**Failure scenario:** `app/api/wedding.py:205-226`:
```python
meter_result = stripe_service.report_meter_event(...)  # SUCCESS — Stripe charged
if meter_result.get("status") == "success":
    await mongo.db["weddings"].update_one(
        {"_id": wedding_data["_id"]},
        {"$set": {"last_billed_at": ..., "billed_period": ..., ...}}
    )  # FAILS — Mongo write timeout
```

The meter event landed at Stripe (will bill the customer), but Mongo doesn't know it was billed.

**What happens next:**
- The retry endpoint walks `meter_pending=True` rows. This wedding isn't `meter_pending=True` because `meter_pending` was never SET (the failure was on the success-path write). So the retry endpoint never picks it up.
- The daily batch (`/billing/sync-usage`) checks `last_billed_at < current_period_start`. `last_billed_at` is None (never set). The batch fires another `MeterEvent.create` with idempotency key `billing_job_<wedding>_<cust>_<period>`.
- Stripe's identifier window is 24h. If this happens within 24h: dedupe protects us (different idempotency key prefix though — `billing_job_*` vs `wedding_create_*` — so DIFFERENT key, NOT deduped). **Customer is double-billed.**
- If past 24h: also double-billed, no dedupe protection at all.

**Probability:** Low per-call but nonzero (Mongo write timeout, network blip). High over thousands of wedding creates.

**Severity:** High. Silent double-billing.

**Current mitigation:** None. The error-branch sets `meter_pending=True`, but only when the Stripe call itself fails. A Mongo failure on the success path is unhandled.

**Recommended fix:**
1. Wrap the success-path Mongo write in a try/except. On failure, log loudly AND attempt one immediate retry. If that also fails, log to an "operator must reconcile" error stream (the same way `cleanup_orphaned_stripe_customers` handles state divergence).
2. **Better long-term:** transactional outbox pattern. Write the intent to Mongo (`pending_meter_event` row) BEFORE calling Stripe. After Stripe succeeds, mark the row as completed. A separate worker reconciles any pending rows that didn't get marked.

**Test status:** Not covered. The existing tests assume Mongo writes succeed.

**Tests to add:**
- Unit: mock `mongo.update_one` to raise; assert the wedding doesn't end up in a state where the daily batch will rebill.

---

### SS5 — `stripe.Product.search` is eventually consistent → seed creates duplicate Products

**Failure scenario:** Fresh deploy. Plan dict has `_id: "plan_signature"`. The seed runs `stripe.Product.search(query="metadata['plan_id']:'plan_signature'")` — returns empty (correct, plan is new). Seed calls `Product.create`. Mongo upsert succeeds.

Container restarts (deploy in progress, scaling event, whatever). Seed runs again. `Product.search` runs **before Stripe's metadata index has caught up to the new Product** — Stripe's docs warn the search index has eventual consistency. Search returns empty. Seed calls `Product.create` AGAIN. **Now there are two Products with the same `metadata.plan_id`.**

**Why this is silent and bad:**
- Both Products have prices. Subsequent `Price.list(product=...)` only returns prices for ONE of them.
- Mongo's `stripe_product_id` could point to either.
- Operator sees duplicate products in the Stripe Dashboard.
- Subscription creation might pull a price from the "wrong" product.

**Probability:** Medium. Stripe's search index lag is typically 1-10 seconds; rolling deploys can run multiple seeds within that window.

**Severity:** Medium. Operationally messy; cleanup is manual; doesn't bill customers wrong directly but obscures the source of truth.

**Current mitigation:** The `[EXISTS]` log line catches duplicates AFTER the search index converges, but by then the second product is created.

**Recommended fix:**
1. Switch from `Product.search` to `Product.list` filtered by metadata after creation (the LIST endpoint is strongly consistent for the account's own writes per Stripe).
2. **Better:** maintain `stripe_product_id` in Mongo as the source of truth. Only call Stripe APIs when Mongo says we don't have one yet.

**Test status:** Not covered. Existing tests assume the search returns the right thing.

---

## CRITICAL gaps — high-likelihood × high-impact

### C1 — `assert_meter_config` doesn't verify the Price `recurring.meter` matches our expected `meter_id`

**Failure scenario:** Plan in Mongo has `meter_id=mtr_NEW`. The Stripe Product has a Price with `recurring.meter=mtr_OLD` (drift from a prior failed sync). `assert_meter_config(mtr_NEW)` passes (meter is correctly configured). `sync_plan_to_stripe` reuses the existing Price (its monetary fields match) without checking that `recurring.meter` matches `mtr_NEW`. Meter events fire against `mtr_NEW`, but the Subscription bills against a Price linked to `mtr_OLD`. **Meter events accumulate but never invoice.**

**Probability:** Low (requires a prior partial failure). Real if SS1 happened.

**Severity:** High. Silent zero-billing.

**Recommended fix:** Extend `ensure_price` in `sync_plan_to_stripe` to detect `recurring.meter` mismatch the same way it detects `usage_type` mismatch.

---

### C2 — `ensure_stripe_meter` returns existing meter without validating its config

**Failure scenario:** A meter with `event_name=wedding_active` exists from a manual Dashboard creation (the screenshot scenario from earlier). It has `formula=count` (operator picked the wrong dropdown). `ensure_stripe_meter` does `Meter.list` → finds the meter → returns its `id` WITHOUT calling `assert_meter_config`. The seed persists the broken meter id to Mongo. `sync_plan_to_stripe` later catches it via preflight, but only AFTER the seed has reported success.

**Probability:** Medium (operator hand-creation is the screenshot-driven scenario).

**Severity:** Medium. Seed succeeds-then-runtime-fails ordering means the operator thinks deploy succeeded.

**Recommended fix:** In `ensure_stripe_meter`, after finding an existing match, call `assert_meter_config(found.id)`. If it raises, treat as "not found" and fall through to `Meter.create`.

---

### C3 — `assert_meter_config` accepts inactive meters

**Failure scenario:** A meter is correctly configured (formula=sum etc.) but has been deactivated in Stripe (operator did this, or it was deactivated via API). `Meter.retrieve` returns it (Stripe doesn't filter by status on retrieve). `assert_meter_config` passes. `sync_plan_to_stripe` uses the meter id. Subscription bills against a Price linked to a deactivated meter. **Stripe might reject the meter event, or might silently accept and never invoice.**

**Probability:** Low.

**Severity:** Medium-High. Operationally invisible.

**Recommended fix:** Add `if meter.status != "active": raise ValueError(...)` to `assert_meter_config`.

**Test status:** This is pinned in `test_known_caveat_assert_meter_config_does_not_check_status` as a known-caveat. Inverting that test is the work item when this is fixed.

---

### C4 — Plan flipped on/off across deploys leaves Stripe state inconsistent

**Failure scenario:** Sprint 1: someone flips `signature` plan to metered, ships, runs the seed → metered Price created, flat Price deactivated. Sprint 2: it's reverted (flat again), seed re-runs → flat Price recreated, metered Price deactivated. Sprint 3: re-flipped to metered. Now the old metered price is still around but inactive, the new metered price gets created. Stripe Product accumulates 4 inactive Prices over time.

This isn't a billing bug per se but it's operational drift. Plus: if the operator manually swaps a Subscription back to an old Price (some support case, "restore my customer to the original price"), they could swap to a deactivated old Price → Subscription bills nothing? Or fails? Stripe behavior unspecified.

**Probability:** Low (requires multiple flips), but bad inventory hygiene.

**Severity:** Low-Medium. Mostly operational.

**Recommended fix:** Add a periodic cleanup job that hard-deletes Prices with no associated Subscriptions and `active=false` for > 90 days.

---

### C5 — `current_period_start` parsing duplicated across files

**Failure scenario:** `app/api/wedding.py:155-175` and `app/api/billing_jobs.py:78-94` both parse `current_period_start` independently — string→datetime, naive→aware coercion. If one drifts (e.g., a future PR updates the wedding-hook parser to handle a new format), the daily batch silently uses the OLD parser → mismatched billing windows → false-positive "needs billing" when it shouldn't.

**Probability:** Medium (already at risk per memory `project_subscription_lifecycle_bug_patterns`).

**Severity:** High. Could double-bill or under-bill in edge timezones.

**Current mitigation:** None.

**Recommended fix:** Extract to `app/utils/coerce_period_start.py` (already flagged as Part 1 L2 — promote to critical given this concern).

---

### C6 — Webhook delays leave `current_period_start` stale

**Failure scenario:** Stripe sends `customer.subscription.updated` after a renewal. Webhook handler updates `user_subscriptions.current_period_start` in Mongo. If the webhook is delayed (Stripe retries with backoff, our endpoint was down briefly), the handler arrives 30+ minutes after the actual renewal.

In that window, a wedding is created. The hook reads stale `current_period_start` (still the previous period). Calculates `last_billed_at >= stale_period_start` → sees True → skips the meter event. **Wedding is never billed.** When the daily batch runs, same calculation → still doesn't bill.

**Probability:** Medium (Stripe webhook delays are common).

**Severity:** High (silent under-billing).

**Recommended fix:** When firing a meter event, additionally read the live Stripe Subscription's `current_period_start` and use the max of (Mongo, Stripe) — Stripe is source of truth.

---

### C7 — Multiple "active" subscriptions per user breaks customer attribution

**Failure scenario:** `find_one({"user_id": user_id, "status": ACTIVE})` is used in `wedding.py` and `metering.py`. If a planner has TWO active subscriptions in Mongo (legacy from upgrade/downgrade where webhook left the old one ACTIVE), `find_one` returns whichever Mongo orders first. Meter event goes to whichever customer that sub points at — could be the old, irrelevant Stripe customer.

**Probability:** Low (modern code prevents this), but legacy data may have it. Per memory `project_subscription_lifecycle_bug_patterns`, this is exactly the family that's bitten before.

**Severity:** High. Wrong customer billed.

**Recommended fix:** Replace `find_one` with `find().sort([("updated_at", -1)]).limit(1)` everywhere. Better: enforce a unique index on `(user_id, status=ACTIVE)`.

---

### C8 — `meter_event_name` matched too loosely on whitespace

**Failure scenario:** Operator types `meter_event_name = " wedding_active"` (leading space) into the admin form. The form doesn't trim. Mongo stores it with the space. Runtime hook calls `report_meter_event(event_name=" wedding_active")`. Stripe doesn't dedupe whitespace; the event creates a meter with event_name `" wedding_active"` (note leading space) on the fly — wait actually no, MeterEvent.create requires the event_name to MATCH an existing meter. So Stripe would reject this with "no meter found." → meter event silently fails → wedding marked `meter_pending=True`.

**Probability:** Medium (admin form has no trim).

**Severity:** Medium. Visible failure (`meter_pending`) but operator-confusion-inducing.

**Recommended fix:** Trim inputs in the admin form AND in the seed `_provision_meter_if_needed` BEFORE calling helpers.

---

## EDGE cases — pin or document

### E1 — `value` field type coercion across SDK versions

`payload={"stripe_customer_id": ..., "value": "-1"}` sends `value` as STRING. Different stripe-python versions may coerce differently. SDK 15 accepts strings; SDK 16 hypothetically might require numbers. Pin with a test that asserts the string survives the SDK call boundary.

### E2 — Test clock vs Meter aggregation interaction

Stripe test clocks affect Subscription period boundaries but the docs are silent on whether Meter aggregations honor test clocks. If they don't, the lifecycle driver's cross-period scenarios may not produce expected aggregations. **Verify before relying on test clocks for cross-period meter testing.**

### E3 — Stripe API version drift relative to SDK upgrade

We pinned `2026-04-22.dahlia` matching SDK 15.1.0's default. If someone upgrades to SDK 16.x, our pin is now a non-default version. Stripe deprecates old API versions over time; one day our pinned version may become unsupported.

**Recommendation:** add a CI check that asserts our pinned version is in the list of supported versions (Stripe publishes this list).

### E4 — `Meter.list` could return more than 100 results from a different account scope

If the Stripe account is part of a Connect platform, `Meter.list` might surface meters from connected accounts. Our `event_name` match is exact, so this is unlikely to cause a false positive — but worth noting if the platform model evolves.

### E5 — Currency hardcoded `"usd"`

`scripts/seed_subscription_plans.py:310,324` and `app/services/stripe_service.py:330` hardcode `currency="usd"`. The mismatch detection in `ensure_price` checks `price.currency == "usd"` — would force-recreate every Price for any non-USD plan. Not a bug today; documented limitation.

### E6 — Stripe Meter beta/regional restrictions

Some Stripe accounts (newer regions, certain account types) don't have `billing.Meter` API access. Our seed would fail at `Meter.list` with a 403. We don't preflight-check for API availability.

### E7 — Plan deletion doesn't deactivate the Stripe Meter

`archive_stripe_product` deactivates the Product and Prices but leaves the Meter. Orphan accumulation over time. Cleanup if needed.

### E8 — `_provision_meter_if_needed` log line "Existing meter_id is invalid" can be a false alarm under rate limit

If `Meter.retrieve` returns a 429 (rate limited), `assert_meter_config` raises `ValueError("not found")` — wrong message. Misleading log.

### E9 — Soft-deleted weddings still match the daily batch query

`billing_jobs.py:69-74` queries `weddings` by `created_by + status="active"`. Soft-deleted weddings have `cancelled_at` set but may still have `status="active"` (the soft-delete sets status to "cancelled" per `wedding.py:425` but only in one path). If a planner has a soft-deleted wedding still showing `status="active"` (e.g., legacy data), the batch would fire meter events for it.

Per memory `project_subscription_lifecycle_bug_patterns` ("live-query missing soft-delete filter"), this is the exact bug class that has bitten before.

---

## Cross-cutting recommendation

Several of the criticals (SS1, SS5, C5, C7) share a root cause: **the codebase trusts Mongo as the runtime source of truth but doesn't lock or version-check writes against concurrent / delayed-webhook scenarios.** The optimistic-locking pattern already in `UserSubscriptionModel.version` is a good template — extend it to the metering writes.

For SS1 specifically, the `ensure_stripe_meter` race is the highest-leverage fix: a single Mongo-side mutex on `meter_provisioning_locks` collection would prevent every duplicate-meter scenario described above.

---

## What I recommend doing now

Pick from this menu (in priority order):

1. **SS1 fix** — `ensure_stripe_meter` race. Half-day, prevents duplicate meters in production deploys. The Mongo-mutex approach can be adapted from `couple_lifecycle_service` patterns.
2. **SS4 fix** — wrap meter-event success-path Mongo writes in try/except with explicit reconciliation logging. ~2h, prevents silent double-billing on Mongo blips.
3. **C2 fix** — `ensure_stripe_meter` calls `assert_meter_config` on existing matches. ~30min, prevents seed-success-then-runtime-failure ordering for hand-created meters.
4. **C5 fix** — extract `coerce_period_start` helper. ~1h, removes the duplication risk that has historically bitten this codebase.
5. **SS5 fix** — switch `Product.search` to Mongo-based lookup. ~1h, prevents duplicate Products on rolling deploys.

The other ship-stoppers (SS2 cross-customer migration, SS3 24h MeterEventAdjustment) gate on product decisions you've already flagged as open questions in the Part 2 review §7. Until those are answered, the only mitigation is the operational warning we already have in S6 of the testbed driver.

The CRITICAL items C1, C3, C4, C6, C7, C8 are each ~30min-2h fixes that could batch into a single follow-up "metering hardening" PR.

The EDGE cases (E1-E9) are mostly documentation or low-priority; pin them with tests as the codebase touches each area.

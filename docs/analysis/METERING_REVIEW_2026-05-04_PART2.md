# Stripe Metering — Code Review Part 2: Seed/API/Models + Stripe Docs Gap Analysis

**Date:** 2026-05-04
**Reviewer:** Claude (paired with Etastic)
**Status:** Read-only review. No code changes made.
**Scope expansion:** Per Etastic's request — review the seed script, the metering APIs, the DB schemas/models, then research Stripe's official documentation and report deviations.

**See also:**
- `docs/analysis/METERING_AUDIT.md` (2026-04-17) — original drift audit.
- `docs/analysis/METERING_REVIEW_2026-05-04.md` (Part 1) — code-review + testing-strategy on the runtime path.

---

## TL;DR

Two new findings dominate Part 2:

1. **The codebase is using the wrong Stripe API for reversals.** The wedding-delete hook emits `value="-1"` to "reverse" an earlier `+1` event. Stripe has a dedicated official API for this — `MeterEventAdjustment` with `cancellation_action: "cancel"` — which is documented as the supported reversal mechanism. The current pattern works mathematically on a `Sum` meter, but it is not what Stripe documents and has at least one known operational risk: finalized invoices cannot be retroactively corrected. (Finding **CC1** below.)

2. **The seed script can't actually persist `meter_event_name` or `meter_id`, even if you put them in the plan dict.** The `$set` block in `scripts/seed_subscription_plans.py:382-420` lists `is_metered` but **omits** `meter_event_name` and `meter_id`. That's why the metering setup feels manual — even if the seed dict declared `meter_event_name: "wedding_active"`, the upsert would silently drop it. (Finding **CC3** below.)

These two are bigger than anything in Part 1 because they explain why "scriptable seeding" hasn't worked: the seed path is structurally incomplete.

---

## 1. Current state — seed script

**Location:** `scripts/seed_subscription_plans.py` (446 lines, runs on container startup per `Dockerfile.coolify`).

### What it does today

1. Connects to Mongo, dedupes any same-name plans (lines 62-89).
2. Migrates legacy field names `stripe_monthly_price_id` → `stripe_price_id_monthly` (lines 91-108).
3. Configures Stripe SDK if `STRIPE_ENABLED=true` (line 119).
4. Has a **local stripped-down** `create_stripe_product_and_prices` (lines 133-210) that creates only flat-rate prices with `recurring={"interval": "month"}` — no `usage_type`, no `meter`.
5. Defines three plans with `is_metered: False` hardcoded (lines 222, 262, 308).
6. Upserts each plan with `$setOnInsert` for create-only fields and `$set` for everything else (lines 373-423).

### Critical gaps in the seed script

**CC3 — `$set` block omits metering fields.**

```python
"$set": {
    "name": ...,
    "is_metered": plan_with_stripe.get("is_metered", False),  # present
    # meter_event_name — MISSING
    # meter_id — MISSING
    ...
}
```

Even if you change the plan dict to `is_metered: True, meter_event_name: "wedding_active"`, the upsert never persists `meter_event_name`. The plan will land in Mongo with `is_metered=True` and a missing event name — which is a **half-configured state** that the metering hooks gate off (`plan.get("is_metered") and plan.get("meter_event_name")`) so nothing fires.

**Fix:** add `meter_event_name` and `meter_id` to the `$set` block.

**CC4 — Two parallel Stripe-sync code paths.**

The seed has its own `create_stripe_product_and_prices` (133-210) that doesn't know about metered prices. The runtime has `app/services/stripe_service.py:171-355` `sync_plan_to_stripe` that does. They will diverge.

**Fix:** delete the local function, import `stripe_service.sync_plan_to_stripe` instead. This was already recommended in the conversation; it remains the single biggest leverage change.

**CC5 — Stripe Meter resource is never provisioned by code.**

Nothing in the seed, the runtime, or the admin UI calls `stripe.billing.Meter.create`. The audit said this and the screenshot confirms the user is creating it manually in the Dashboard. There's no idempotent `ensure_stripe_meter(event_name, formula="sum")` helper. Every fresh environment requires a human in the Dashboard. (See Stripe docs section 4.1 below for the canonical creation shape.)

**Fix:** add `ensure_stripe_meter()` to `stripe_service.py` that does `Meter.list` → `Meter.create` if missing. Call it from the seed script before plan upserts.

---

## 2. Current state — APIs touching metering

| Endpoint | File | Purpose | Reads | Writes |
|---|---|---|---|---|
| `POST /admin/weddings` | `app/api/wedding.py:140-244` | Wedding create + meter `+1` | `subscription_plans`, `user_subscriptions`, `weddings` | `weddings.last_billed_at`, `billed_period`, `meter_pending`, `meter_pending_reason` |
| `DELETE /admin/weddings/{id}` | `app/api/wedding.py:355-413` | Wedding delete + meter `-1` (reversal) | same | `weddings.meter_reversed_period`, `meter_pending` |
| `POST /admin/metering/retry-pending` | `app/api/metering.py:16-133` | Re-fire meter events for `meter_pending=True` rows | same | `weddings.last_billed_at`, `meter_pending`, `meter_pending_reason` |
| `POST /admin/billing/sync-usage` | `app/api/billing_jobs.py:17-30` | Trigger daily catch-up batch | active subs + active weddings | `weddings.last_billed_at` |
| `POST /admin/system/sync-plans-to-stripe` | `app/api/subscription_management.py:298-321` | Recreate Stripe Products/Prices for all plans | `subscription_plans` | plan Stripe IDs |
| `POST /admin/system/seed-default-plans` | `app/api/subscription_management.py:324+` | Seed default catalog via API instead of script | (writes plans) | `subscription_plans` |
| `POST /admin/saas/plans` (CRUD) | `app/api/saas_config.py` | Admin plan editor backend | plan input | `subscription_plans` |

Three observations from this map:

- **No endpoint provisions a Stripe Meter.** The closest is `sync-plans-to-stripe` which calls `sync_plan_to_stripe` per plan; that function will *look up* an existing meter via `Meter.list` but won't create one.
- **The retry endpoint is ROOT_ADMIN only and not exposed to planners.** Operationally that means an operator must SSH/call manually. There's no UI button for "retry all pending meter events on my account" — even though the meter-pending badge is visible to the admin.
- **The daily batch (`/billing/sync-usage`) has no scheduler attached.** Already flagged in Part 1 as H1.

---

## 3. Current state — DB schemas/models touching metering

### `subscription_plans` collection (model: `SubscriptionPlanModel` in `app/models/subscription.py:93-156`)

| Field | Type | Purpose | Source |
|---|---|---|---|
| `is_metered` | bool, default False | Gate flag for metered billing | Plan editor / seed |
| `meter_event_name` | str, optional | Stripe meter event name (e.g. `wedding_active`) | Plan editor |
| `meter_id` | str, optional | Stripe meter ID `mtr_…` | Plan editor or auto-resolved via `Meter.list` |
| `stripe_product_id` | str, optional | Stripe product ID | `sync_plan_to_stripe` |
| `stripe_price_id_monthly`/`_yearly` | str, optional | Stripe price IDs (regenerated on flip) | `sync_plan_to_stripe` |

### `user_subscriptions` collection (model: `UserSubscriptionModel` in `app/models/subscription.py:170+`)

| Field | Type | Purpose | Source |
|---|---|---|---|
| `stripe_customer_id` | str | Used as `payload.stripe_customer_id` on every meter event | Stripe customer creation |
| `stripe_subscription_id` | str | Identifies the subscription whose price is metered | Stripe subscription creation |
| `current_period_start` | datetime | Used to gate "already billed this period" | Stripe webhook (likely) |
| `plan_snapshot` | dict | Grandfathered limits — **does NOT carry metering fields** | `subscription_service.assign_subscription:240-257` |

### `weddings` collection (model: `WeddingModel` in `app/models/wedding.py:285-297`)

| Field | Type | Purpose |
|---|---|---|
| `last_billed_at` | datetime | When the `+1` meter event landed |
| `billed_period` | str (`YYYY-MM`) | Period of last successful meter event |
| `meter_pending` | bool | True if a meter event failed and needs retry |
| `meter_pending_reason` | str | Failure reason for ops visibility |
| `meter_reversed_period` | str (`YYYY-MM`) | Period of last `-1` reversal |

### Schema-level observations

- The wedding model's metering fields are well-documented and mirror the runtime contract in `app/api/wedding.py`.
- The plan model exposes `is_metered`/`meter_event_name`/`meter_id` correctly, but the seed script can't *write* the latter two (CC3).
- The `plan_snapshot` omission for metering fields (Part 1 finding C3) is a real grandfather risk if metering is ever flipped on a same-`plan_id` mid-life.
- `current_period_start` is parsed in two places (`wedding.py` and `billing_jobs.py`) with duplicated coercion logic. Already flagged in Part 1 as L2.

---

## 4. What Stripe officially documents (research summary)

### 4.1 Meter creation — canonical shape

From the API reference for `stripe.billing.Meter.create`:

```python
stripe.billing.Meter.create(
    display_name="Wedding Active",
    event_name="wedding_active",
    default_aggregation={"formula": "sum"},
    customer_mapping={
        "type": "by_id",
        "event_payload_key": "stripe_customer_id",
    },
    value_settings={"event_payload_key": "value"},
)
```

**Stripe's documented requirements:**
- `event_name` — string, must match the `event_name` on every `MeterEvent` created against this meter.
- `default_aggregation.formula` — one of `sum`, `count`, `last`. (`Sum` is what the codebase requires.)
- `customer_mapping` — tells Stripe which payload key carries the customer attribution.
- `value_settings.event_payload_key` — tells Stripe which payload key carries the numeric value to aggregate.

The codebase emits `payload={"stripe_customer_id": ..., "value": "1"}` which maps cleanly to the canonical config above.

### 4.2 Recording usage — `MeterEvent.create`

- `event_name` is required and must match the meter's `event_name` exactly.
- `payload` is required; must contain the keys the meter's `customer_mapping` and `value_settings` expect.
- `identifier` is optional but recommended — Stripe enforces uniqueness within a rolling 24-hour window.
- Stripe recommends UUID-like identifiers (the codebase uses deterministic `wedding_*_{wid}_{cid}_{YYYY-MM}` keys instead — also valid).
- `timestamp` is optional; defaults to "now."

### 4.3 Reversing a meter event — **`MeterEventAdjustment`**

This is the new finding. From Stripe's API reference:

> "A billing meter event adjustment is a resource that allows you to cancel a meter event. For example, to cancel a meter event that was created in error or attached to the wrong customer."

Key constraints:
- **24-hour window.** "You can only cancel events sent to Stripe within the last 24 hours."
- **Finalized invoices are NOT corrected.** "If you cancel usage that's included on a finalised invoice, we won't update the invoice or issue a corrected invoice for the cancelled usage."
- `cancellation_action` parameter supports `cancel` for a single event. Time-period cancellation is not yet supported.

The codebase's `value: "-1"` pattern is **NOT** the documented reversal mechanism. It works by exploiting the `Sum` aggregation arithmetic — and only because `Sum` aggregation accepts negative values. Two implications:

1. The codebase's reversal works *only* on `Sum` meters, *only* if the meter accepts negative values, and *only* for cycle-total math — not for invoice correction.
2. For "delete a wedding within 24h of creation," the codebase should arguably be calling `MeterEventAdjustment.create` instead of emitting `value="-1"`. That's the official path.
3. For "delete a wedding > 24h after creation" (e.g., next billing period), neither pattern produces a customer refund automatically. The customer paid for an active wedding in month A; deleting in month B reduces month B's cycle total but doesn't refund month A.

### 4.4 Meter-event coupling to Price

For Stripe to bill anything, you also need a Price with:

```python
recurring={
    "interval": "month",  # or "year"
    "usage_type": "metered",
    "meter": "mtr_…",
}
```

The codebase's `sync_plan_to_stripe.ensure_price` does this correctly (lines 271-275, 314-316). When a plan flips from flat to metered, the function creates a new metered price and deactivates the old flat one.

### 4.5 Meter Event Summary — readback

Stripe exposes `stripe.billing.MeterEventSummary.list(customer, meter, start_time, end_time)` to read back the aggregated usage for a customer over a window. This is what the testing strategy gap **G1** in Part 1 should use to verify "the meter event actually landed."

---

## 5. Codebase vs Stripe docs — gap analysis

### NEW CRITICAL findings (extending Part 1)

**CC1. Reversal pattern (`value="-1"`) is not the documented Stripe API.**

What the code does (`app/api/wedding.py:386-392`): emits a second `MeterEvent.create` with `value="-1"`.

What Stripe documents: `MeterEventAdjustment.create(event_name, cancellation_action="cancel", reason=...)` for events within the 24-hour cancellation window.

Why it matters:
- Stripe could deprecate or restrict negative `value` on Sum meters at any time. The official adjustment API would not break.
- Cross-period reversals (delete in month B for create in month A) are unsupported by either pattern in the way the codebase implies. The negative `+1`/`-1` arithmetic *appears* to work on the cycle total, but Stripe's docs explicitly say finalized invoices are not retroactively corrected. So if a customer was billed in month A's invoice for that wedding, and then deletes it in month B, the customer is not refunded — they just have a `-1` on month B's cycle total which may clamp to zero.

**Fix (in priority order):**
1. For deletes within 24h of create: call `MeterEventAdjustment.create` (the supported API).
2. For deletes after 24h: clearly document that no automatic refund happens. The current `value="-1"` semantics need a product decision: do we issue a credit memo? Do we just stop charging starting next period? Per Stripe docs, the answer cannot be "Stripe does it for us."
3. Update `wedding.py` to branch on `now - last_billed_at < 24h` and use the right API.

**CC2. The codebase doesn't preflight `default_aggregation.formula` on the live meter.**

Stripe's docs are clear: a meter created with `Count` or `Last` would silently break the codebase's reversal arithmetic. There's no `stripe.billing.Meter.retrieve(meter_id)` check anywhere. (Already flagged as Part 1 C1; the Stripe-docs research now confirms this is the correct mitigation, not a paranoid one.)

**Fix:** add to `sync_plan_to_stripe`:

```python
if is_metered and meter_id:
    meter = stripe.billing.Meter.retrieve(meter_id)
    formula = meter.default_aggregation.formula
    if formula != "sum":
        raise HTTPException(
            status_code=400,
            detail=f"Meter {meter_id} aggregation is {formula!r}, must be 'sum'."
        )
```

**CC3. Seed `$set` block omits `meter_event_name` and `meter_id`.** (See §1 above.)

**CC4. Two parallel Stripe-sync paths (seed vs runtime).** (See §1 above.)

**CC5. Stripe Meter is never code-provisioned — only via Dashboard.** (See §1 above.)

### NEW HIGH findings

**HH1. Seed script has no concept of `ensure_stripe_meter`.**

Stripe documents `Meter.list` for searching and `Meter.create` for creating. The pattern `existing_products.search(query=...)` is already used in the seed for products (line 143). The same pattern should exist for meters:

```python
def ensure_stripe_meter(event_name: str, display_name: str) -> str:
    meters = stripe.billing.Meter.list(status="active", limit=100)
    for m in meters.auto_paging_iter():
        if m.event_name == event_name:
            return m.id
    new_meter = stripe.billing.Meter.create(
        display_name=display_name,
        event_name=event_name,
        default_aggregation={"formula": "sum"},
        customer_mapping={"type": "by_id", "event_payload_key": "stripe_customer_id"},
        value_settings={"event_payload_key": "value"},
    )
    return new_meter.id
```

This unblocks fully scriptable provisioning.

**HH2. Stripe API version not pinned anywhere obvious.**

`app/services/stripe_service.py` imports `stripe` and uses `stripe.api_key = …`. Stripe's API version is set on the account level by default. `MeterEvent` and `MeterEventAdjustment` are still relatively new APIs (the v2 namespace `mcp__22b31cfb-…__list_diffs`-style endpoints exist for some adjustment endpoints). Without pinning `stripe.api_version`, behavior could shift on a Stripe-side default change.

**Fix:** pin `stripe.api_version = "2024-09-30.acacia"` (or current at time of audit) in `stripe_service.__init__`.

**HH3. `MeterEventSummary` readback is the only way to verify billing accuracy — and it's not used.**

The testbed driver verifies Mongo state but never reads back `stripe.billing.MeterEventSummary.list` to confirm Stripe agrees on the cycle total. (Already flagged as Part 1 G1; Stripe docs research confirms this is the canonical assertion endpoint.)

### NEW MEDIUM findings

**MM1. The 24-hour idempotency window means deterministic monthly keys are mostly safe — but stale retries past 24h won't dedupe.**

The codebase uses keys like `wedding_create_{wid}_{cid}_2026-04`. If the retry endpoint runs more than 24h after the original attempt, Stripe will *not* dedupe — meaning a successful original + a retry could double-bill. The duplicate-error normalization in `report_meter_event:437-445` only fires if Stripe returns a duplicate error, which it won't outside the window.

**Fix:** in the retry endpoint, additionally check `wedding.last_billed_at` Mongo-side before re-firing. The current logic does this implicitly (if `last_billed_at` is set, it skips), but it's worth documenting explicitly.

**MM2. Stripe recommends UUID-like identifiers; we use deterministic prefixed keys.**

Both are valid. Deterministic keys are *better* for our use case because they make idempotency reasoning easy. Document the deviation in `stripe_service.py:report_meter_event` so future readers know it's intentional.

**MM3. `customer_mapping` and `value_settings` are not currently asserted at preflight.**

If someone creates the meter manually with `event_payload_key: "customer_id"` instead of `stripe_customer_id`, every meter event will be rejected. The preflight check from CC2 should also assert these fields.

```python
assert meter.customer_mapping.event_payload_key == "stripe_customer_id"
assert meter.value_settings.event_payload_key == "value"
```

---

## 6. Updated remediation list (combined Parts 1 + 2)

In dependency order — earlier items unblock later ones.

| # | Item | Layer | Effort | New in Part 2? |
|---|---|---|---|---|
| 1 | **CC3** Add `meter_event_name`/`meter_id` to seed `$set` block | Seed | 5min | Yes |
| 2 | **HH1** Add `ensure_stripe_meter()` to `stripe_service` | Service | 1h | Yes |
| 3 | **CC4** Replace seed's local `create_stripe_product_and_prices` with `sync_plan_to_stripe` | Seed | 1-2h | Yes |
| 4 | **CC5** Call `ensure_stripe_meter()` from seed before plan upsert | Seed | 30min | Yes |
| 5 | **CC2 / Part 1 C1** Preflight `formula="sum"` + `customer_mapping` + `value_settings` in `sync_plan_to_stripe` | Service | 1h | Extends Part 1 |
| 6 | **CC1** Branch wedding-delete on `<24h` to use `MeterEventAdjustment` | API | 2-3h | Yes |
| 7 | **Part 1 H3** Add cross-period delete test in testbed driver | Test | 2h | (Part 1) |
| 8 | **Part 1 G1 / HH3** Add `MeterEventSummary` readback assertion | Test | 2-3h | (Part 1) |
| 9 | **Part 1 H1** Wire Cloudflare cron to `/billing/sync-usage` | Infra | 1h | (Part 1) |
| 10 | **HH2** Pin `stripe.api_version` | Service | 5min | Yes |
| 11 | **MM3** Assert meter `customer_mapping` + `value_settings` at preflight | Service | 30min | Yes |
| 12 | **Part 1 C3** Decide snapshot policy for metering fields and pin with a test | Service | 1h | (Part 1) |
| 13 | **Part 1 M1** Centralize `wedding_active` constant; admin form selects rather than free-text | UI + Service | 2h | (Part 1) |
| 14 | **Part 1 M2** Mirror create-path's `last_billed_at` check on delete-path | API | 30min | (Part 1) |

Items 1-4 alone make the metering setup **fully scriptable** — answering Etastic's question from this turn. Items 5-6 close the two new critical correctness gaps surfaced by the Stripe-doc research.

---

## 7. Open product questions (refined)

1. **24-hour boundary handling on delete.** Should `wedding.py` branch on time-since-create and use `MeterEventAdjustment` for in-window cancellations, or keep the uniform `value="-1"` pattern? The official-API path is more correct but more code.
2. **Cross-period refund semantics.** When a wedding is created in month A (billed) and deleted in month B, what *does* the customer experience? Per Stripe docs: nothing automatic. Do we want code to issue a `stripe.Credit Note` or `Coupon`? Or do we accept that "delete in month B doesn't refund month A"?
3. **Existing-customer migration.** Same question as Part 1 — when a flat plan is flipped metered, are existing customers auto-migrated? `sync_plan_to_stripe` deactivates the old price but doesn't `Subscription.modify` to swap.
4. **`max_weddings` semantics under metering.** Hard cap or soft "starts charging overage"?
5. **Plan-snapshot policy.** Live-read metering fields (current behavior, undocumented) vs snapshot them (matches the rest of the snapshot model, breaks "flip plan to metered" mid-life)?

---

## 8. Files referenced

Read-only, no edits.

- `scripts/seed_subscription_plans.py` (full file 1-446)
- `app/api/wedding.py` (140-244, 355-413)
- `app/api/metering.py` (full file 1-133)
- `app/api/billing_jobs.py` (17-141)
- `app/api/subscription_management.py` (298-321 sync, 324+ seed-via-API)
- `app/api/saas_config.py` (referenced)
- `app/services/stripe_service.py` (171-355, 393-447)
- `app/services/subscription_service.py` (240-257 plan_snapshot)
- `app/models/subscription.py` (Plan 93-156, UserSubscription 170-322, UsageTracking 325-355, request models 358-409)
- `app/models/wedding.py` (285-297)
- `app/admin/saas/page.tsx` (1350-1577 plan editor)

External (Stripe official docs):
- [Meter Events | Stripe API Reference](https://docs.stripe.com/api/billing/meter-event)
- [Meters | Stripe API Reference](https://docs.stripe.com/api/billing/meter)
- [Create and configure a meter | Stripe Documentation](https://docs.stripe.com/billing/subscriptions/usage-based/meters/configure)
- [Record usage for billing | Stripe Documentation](https://docs.stripe.com/billing/subscriptions/usage-based/recording-usage)
- [Meter Event Adjustment | Stripe API Reference](https://docs.stripe.com/api/billing/meter-event-adjustment)
- [Create a billing meter event adjustment | Stripe API Reference](https://docs.stripe.com/api/v2/billing/meter-event-adjustments/create)
- [Meter Event Summary | Stripe API Reference](https://docs.stripe.com/api/billing/meter-event-summary)
- [Set up a pay-as-you-go pricing model | Stripe Documentation](https://docs.stripe.com/billing/subscriptions/usage-based/implementation-guide)
- [Idempotent requests | Stripe API Reference](https://docs.stripe.com/api/idempotent_requests)

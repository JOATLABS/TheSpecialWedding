# Stripe Metering — Code Review + Testing Strategy

**Date:** 2026-05-04
**Reviewer:** Claude (paired with Etastic)
**Status:** Read-only review. No code changes made.
**Trigger:** User staging Stripe meter creation (screenshot showed `Sum` aggregation in the Create-meter dialog) and configuring a plan with `Meter Event Name = wedding_active`. Wanted confirmation the flow matches code expectations before flipping a plan metered.

**See also:** `docs/analysis/METERING_AUDIT.md` (2026-04-17) — the prior infrastructure-vs-config drift audit. This document layers a code-quality + testing review on top of that audit.

---

## TL;DR

The Stripe-side aggregation choice in the screenshot (`Sum`) is correct and matches what the code requires. The Meter Event Name (`wedding_active`) is correct. Empty Stripe Meter ID is acceptable but should be persisted back after first sync.

Three things must be true *before* flipping a production plan to metered:

1. The Stripe meter's `event_name` exactly equals `wedding_active` (the screenshot's template default `api_requests` must be changed).
2. The Stripe meter's `default_aggregation.formula` equals `sum`. The reversal pattern (`value="-1"`) only nets correctly on Sum. The code does NOT preflight-check this — see Finding C1.
3. After plan save, `sync_plan_to_stripe` runs and creates a new Stripe Price with `recurring.usage_type=metered`. This is automatic on plan create/update via `subscription_service.assign_subscription`.

The current code is structurally sound but has **3 critical correctness risks** and **5 testing gaps** that should be closed before production traffic hits the metered path.

---

## 1. Aggregation/flow correctness — what the screenshots tell us

### Stripe Create-meter dialog
| Field | Required | Status |
|---|---|---|
| `event_name` | `wedding_active` | ⚠ Currently shows template default `api_requests` — must be changed |
| `aggregation` | `Sum` (the code emits ±1 values; only Sum nets correctly) | ✅ Selected |
| status | `active` | ✅ Default on creation |

### Admin Edit Plan dialog
| Field | Required | Status |
|---|---|---|
| Enable metered billing | toggle on | ✅ Checked |
| Meter Event Name | `wedding_active` (must match Stripe `event_name` byte-for-byte) | ✅ Placeholder shown |
| Stripe Meter ID | `mtr_…` (optional; auto-resolved on first sync via `Meter.list` lookup) | ⚠ Empty — recommend pasting after meter is created |

### What's not visible in either screenshot but the code requires
- `sync_plan_to_stripe` must run after save to create a new Price with `recurring.usage_type=metered`. Wired automatically through `subscription_service.assign_subscription:48,122`.
- Existing customers on the flat price are NOT auto-migrated to the metered price. Their subscription continues on the deactivated old price until manually swapped via `stripe.Subscription.modify`. Mid-life migration is a separate product decision.

---

## 2. Code review — findings

Ratings:

| Dimension | Rating |
|---|---|
| Security | Good — endpoint gating, idempotency, secret handling all sound |
| Performance | Good — daily batch streams, but `Meter.list` re-runs and current-period parsing is duplicated |
| Correctness | **At risk** — aggregation-method choice, snapshot drift, and asymmetric reversal logic are real |
| Maintainability | Good — strong audit doc, distinct idempotency-key prefixes, but bare `"wedding_active"` should be a constant |

### CRITICAL

**C1. Aggregation method is implicit — no preflight check.** `app/api/wedding.py:386-392` emits `value: "-1"` to reverse a prior `+1`. This only works when the Stripe meter is `aggregation=Sum`. The screenshot shows Sum is selected, but **nothing in the code verifies the live meter's formula**. If anyone recreates the meter as Count or Last, the reversal silently fails to net out and the customer is overbilled. **Fix:** add `stripe.billing.Meter.retrieve(meter_id)` to `sync_plan_to_stripe`, assert `default_aggregation.formula == "sum"`, raise 400 otherwise.

**C2. `value="-1"` reversal correctness is unverified at the Stripe boundary.** `value` is sent as a string. The current SDK accepts it, but no test reads back the Stripe meter event summary to prove the period total actually decreased. **Fix:** add a phase to `testbed/verify_planner_metered_lifecycle.py` that calls `stripe.billing.MeterEventSummary.list` after a delete and asserts the cycle total dropped.

**C3. `plan_snapshot` omits metering fields.** `app/services/subscription_service.py:240-257` snapshots cap data and prices but not `is_metered`/`meter_event_name`/`meter_id`. Today the metering path re-reads the live plan, so this is harmless. But if a planner is grandfathered onto an old flat plan and the admin later toggles the same plan to metered, that planner starts being metered without their snapshot reflecting the change. There's no test pinning this design choice. **Fix:** either extend the snapshot to capture metering fields OR add a test asserting the omission is intentional and document why.

### HIGH

**H1. No scheduler wired to `/billing/sync-usage`.** The daily batch is the safety net for transient meter-event failures, but it's only triggered by manual `POST /billing/sync-usage`. If the real-time hook fails, weddings sit `meter_pending=True` indefinitely. **Fix:** wire a Cloudflare cron trigger (the repo has `cloudflare-workers/`) or document the externally-scheduled call.

**H2. `Meter.list` lookup pages cap at 100 + isn't always persisted.** `stripe_service.py:213-222` resolves missing `meter_id` from `event_name` via `Meter.list(status="active")`. No pagination — if the account ever has >100 meters, the lookup misses. The resolved ID is *returned* to the caller but the caller doesn't always persist back. **Fix:** add `auto_paging_iter()`; ensure callers `update_one({"_id": plan_id}, {"$set": sync_result})` after every `sync_plan_to_stripe`.

**H3. Cross-period reversal semantics unverified.** `wedding.py:382` reverses once per period via `meter_reversed_period == current_period` check. The "create month A, delete month B" path produces `+1` in month A and `-1` in month B → month B may have a negative cycle total, which Stripe may clamp to 0. No test for this. **Fix:** add a test-clock phase that crosses a period boundary.

### MEDIUM

**M1. Bare `"wedding_active"` string is the de facto enum.** Per the centralized-enum rule, callsites should import from a constants module. Today the string lives in 5+ files including UI and tests. **Fix:** add `app/utils/metering_constants.py`; have the admin form select from a list rather than free-text.

**M2. Reverse path doesn't check "was this wedding billed this period".** `wedding.py:376-413` fires `-1` if `meter_reversed_period != current_period` — but never checks `last_billed_at >= current_period_start`. A delete on a wedding that was never billed (e.g., created on a flat plan, then plan flipped, then deleted) emits a stray `-1`. **Fix:** mirror the create-path's `last_billed_at` check before emitting reversal.

**M3. `meter_id` empty-but-resolvable state has no UX feedback.** The admin form lets you save with empty `Stripe Meter ID`; the backend resolves it via `Meter.list` but the UI gives no signal whether resolution succeeded. **Fix:** after save, refetch and display "Resolved meter_id: `mtr_…`" inline.

### LOW

**L1.** `report_meter_event` returns `event_id = identifier` on duplicate path — misleading field naming. **L2.** `current_period_start` parsing duplicated between `wedding.py` and `billing_jobs.py` — extract a helper. **L3.** `Meter.list` match doesn't double-check `status == "active"` (filter prevents it but defense in depth is cheap).

---

## 3. Testing strategy — gaps

The pyramid shape is right (`tests/backend/test_metering_gating.py` for unit, `testbed/verify_planner_metered_lifecycle.py` for integration, Chrome for UX). The depth is uneven.

### Top 7 gaps, in priority order

| # | Gap | Layer | Why it matters | Effort |
|---|---|---|---|---|
| 1 | **G1** No test reads Stripe back to verify the meter event landed and the cycle total is what we think it is. Every test asserts Mongo state only. | Integration | Without this, every other meter test is "we *think* we billed" — bug-hiding | 2-3h |
| 2 | **G4** No preflight check that the meter's `default_aggregation.formula == "sum"` | Integration (preflight) | Closes C1 — the silent-overbill risk | 30min |
| 3 | **G2** No cross-period create→delete test | Integration (test clock) | Closes H3 — Stripe-clamping question | 2h |
| 4 | **G5** Daily batch query (`created_by + status=active`) doesn't test soft-delete or planner reassignment | Unit | Per memory `project_subscription_lifecycle_bug_patterns`, this exact filter shape has bitten us | 1-2h |
| 5 | **G3** Flat→metered plan migration untested in `sync_plan_to_stripe` | Unit (mocked Stripe) | The path that fires when the user toggles `is_metered` in the UI | 1h |
| 6 | **G7** Chrome verification checklist for metering UX is undocumented | Documentation | Per `feedback_e2e_chrome.md`, Chrome with user watching is the only verification | 30min |
| 7 | **G6** Retry-endpoint partial-failure fan-out untested | Unit | The summary `{retried, succeeded, failed[]}` shape is the operator's only signal | 1h |

### Coverage targets

- **Unit:** 100% of branches in `report_meter_event`, `sync_plan_to_stripe.ensure_price`, the `wedding.py` create/delete-meter blocks, the daily batch filter, the retry endpoint's batch summary. **Today: ~30%.**
- **Integration (testbed):** 7 testable lifecycle states (single-period create, second create same period, delete same period, delete next period, retry pending, plan-flip flat→metered, plan-flip metered→flat). **Today: 4 of 7.**
- **E2E (Chrome):** 5 UX checkpoints — toggle reveals fields; save with empty meter_id resolves and persists; metered badge renders on plan card; no meter-pending badge after a clean wedding create; meter-pending badge renders with reason after forced failure. **Today: 0 documented.**

### Documented Chrome checklist for the metering UX (G7)

The five things that must be visually confirmed by the user during live verification:

1. Plan editor: the "Enable metered billing" checkbox toggles the conditional `meter_event_name` + `meter_id` fields.
2. Saving with `meter_event_name=wedding_active` and empty `meter_id` resolves and persists the `mtr_…` after backend roundtrip (refresh and verify).
3. The "Metered: wedding_active" badge appears on the plan card after save.
4. After a wedding is created on a metered plan, `/admin/weddings` shows no "Meter pending" badge for that row.
5. With a forced-failure row (testbed phase E4), the "Meter pending" badge renders inline with the failure reason; after `/metering/retry-pending` succeeds, the badge disappears on refresh.

---

## 4. Pre-production checklist (what to do before flipping a plan metered in prod)

Order matters — each step depends on the previous.

1. **Create the Stripe meter** (left screenshot). Set:
   - Meter name: `Wedding Active` (display)
   - Event name: `wedding_active` (NOT the template `api_requests`)
   - Aggregation: `Sum`
2. Capture the `mtr_…` ID from the Stripe Meter detail page.
3. In the admin plan editor, edit the target plan:
   - Enable metered billing: ON
   - Meter Event Name: `wedding_active`
   - Stripe Meter ID: paste `mtr_…`
4. Save. This triggers `sync_plan_to_stripe` which creates a new Stripe Price with `recurring.usage_type=metered, meter=mtr_…` and deactivates the old flat price.
5. Verify in Stripe Dashboard → Products → the plan: a new active price exists with metered config, old flat price is inactive.
6. Run `testbed/verify_planner_metered_lifecycle.py` — preflight will skip cleanly if any of (a) plan not metered in Mongo, (b) meter not provisioned in Stripe is missing. If it runs, E1-E5 will exercise create/delete/retry.
7. Decide explicitly what happens to existing customers on the old flat price. They are NOT auto-migrated. Document the migration plan separately.
8. Add the Cloudflare cron for `/billing/sync-usage` before any meaningful production volume.
9. Run the Chrome UX checklist above with you watching the screen.

Only after step 9 is the flow verified. Per `CLAUDE.md`: code merged without both layers (automated + Chrome) passing is not verified.

---

## 5. Open questions for the user

1. **Existing-customer migration.** When you flip a production plan metered, what's the intended behavior for planners already on a flat price? (Auto-modify their Stripe subscription to the new price? Wait for renewal? Grandfather forever?)
2. **`max_weddings` semantics under metering.** The Boutique plan currently has `max_weddings=3`. If billing is per-wedding, is the cap still enforced as a hard cap, or does it become a soft "after 3 you start paying overage"?
3. **`current_period_start` source of truth.** When the live plan and the snapshot disagree (post-flip), should metering follow the live plan or the snapshot? (My read: live plan, per the audit's stance — but this is worth pinning explicitly.)
4. **Negative-cycle handling.** What's the desired behavior when a delete in a later period drives the cycle total negative? (Stripe may clamp to 0; do we want a real credit memo instead?)

These don't block flipping a *test* plan metered, but the production migration depends on answers.

---

## 6. Files referenced

Read-only review. No edits.

- `app/services/stripe_service.py` (`sync_plan_to_stripe` 195-355, `report_meter_event` 393-447)
- `app/api/wedding.py` (create hook 140-244, delete hook 355-413)
- `app/api/billing_jobs.py` (daily batch 17-141)
- `app/api/metering.py` (retry endpoint, full file 1-133)
- `app/services/subscription_service.py` (plan_snapshot 240-257)
- `app/models/subscription.py` (Plan model 100-153)
- `app/admin/saas/page.tsx` (plan editor 1350-1577)
- `tests/backend/test_metering_gating.py` (full file 1-304)
- `testbed/verify_planner_metered_lifecycle.py` (full file 1-572)
- `docs/analysis/METERING_AUDIT.md` (2026-04-17 baseline)

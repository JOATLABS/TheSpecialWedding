# Stripe Metering — Scriptable-Seed Implementation Hand-off

**Date:** 2026-05-04
**Author:** Claude (paired with Etastic)
**Status:** Code changes uncommitted in working tree. Pytest passes for new tests + applicable existing tests. Ready for review + Chrome verification.

**Companion docs:**
- `docs/analysis/METERING_AUDIT.md` (2026-04-17 — original drift audit)
- `docs/analysis/METERING_REVIEW_2026-05-04.md` (Part 1 — code-review + testing-strategy)
- `docs/analysis/METERING_REVIEW_2026-05-04_PART2.md` (Part 2 — seed/API/models + Stripe-doc gap analysis)

---

## What this PR does

Closes **CC2, CC3, CC4, CC5, HH1, HH2, MM3** from the Part 2 review — the "scriptable seeding + correctness preflight" batch. After this lands, deploying a fresh environment with a metered plan in the seed dict provisions everything end-to-end with **no Stripe Dashboard clicks**.

Specifically:

- **`ensure_stripe_meter(event_name, display_name)`** — idempotent provisioner. Searches active meters by `event_name`, returns existing id, otherwise creates with the canonical config (`sum` + `by_id` on `stripe_customer_id` + value key `value`).
- **`assert_meter_config(meter_id)`** — preflight check. Verifies a live meter has the required formula and payload key mappings; raises `ValueError` with an explicit reason on any deviation. Wired into `sync_plan_to_stripe` so any plan sync that references a misconfigured meter fails fast with HTTP 400.
- **`stripe.api_version` pinned** to `"2026-04-22.dahlia"` in both runtime (`stripe_service.py`) and seed (`seed_subscription_plans.py`). Matches the SDK 15.1.0 default; pinning prevents drift on Stripe-side default changes between SDK upgrades.
- **Seed script collapsed** to a single Stripe-sync path that handles flat AND metered plans. The local `create_stripe_product_and_prices` now provisions the meter (when `is_metered=True`), creates Stripe Prices with `recurring.usage_type="metered"` and `recurring.meter=<id>` for metered plans, and falls back to flat-rate Prices otherwise.
- **Seed `$set` block fixed** to persist `meter_event_name` and `meter_id` (CC3 — the structural bug that made the setup feel manual). Without this fix, even putting these fields in the plan dict had no effect on update.

The implementation deliberately does **not** flip any plan to `is_metered=True` — that remains a separate product decision per `METERING_AUDIT.md §3`. What it does is **make flipping it actually work** by code change alone, no Dashboard step.

---

## Files changed

```
NEW   app/services/stripe_meter_helpers.py        (+237)  shared helpers, zero mongo deps
MOD   app/services/stripe_service.py              ( +21)  pin api_version + assert_meter_config preflight
MOD   scripts/seed_subscription_plans.py          (+168, -26)  metered-aware Product/Price; provision meter; fix $set
NEW   tests/backend/test_stripe_meter_helpers.py  (+212)  11 unit tests for the new helpers
```

Two other doc files were written during the analysis (not strictly part of this code PR):

```
NEW   docs/analysis/METERING_REVIEW_2026-05-04_PART2.md
NEW   docs/analysis/METERING_IMPLEMENTATION_2026-05-04.md  (this file)
```

---

## Architectural choice — why a separate `stripe_meter_helpers.py`

The seed script (`scripts/seed_subscription_plans.py`) intentionally has zero `app/` imports today. It runs at container startup using sync `pymongo`, before the FastAPI app boots. Pulling it into `app/services/stripe_service.py` would drag in `app/core/database` (motor / async) and the entire service-layer chain, which can hang or fail at startup depending on Mongo readiness.

The helpers module is a tiny mongo-independent file:

- ZERO imports from `app/core/*`, no `motor`, no `pymongo`.
- Only depends on the `stripe` SDK and `logging`.
- Both the seed script and `stripe_service.py` import from it.
- All canonical-config constants live in one place (`METER_AGGREGATION_FORMULA`, `METER_CUSTOMER_MAPPING_KEY`, `METER_VALUE_KEY`, `METER_EVENT_NAME_WEDDING_ACTIVE`).

This satisfies the user's "collapse to one path" intent without forcing a heavier service-layer refactor. Keep it that way: if a third caller needs meter logic, import from the helpers — don't duplicate.

---

## Test results (sandbox)

**New tests — 11/11 passing:**

```
tests/backend/test_stripe_meter_helpers.py::test_ensure_stripe_meter_returns_existing_when_event_name_matches PASSED
tests/backend/test_stripe_meter_helpers.py::test_ensure_stripe_meter_creates_when_no_match PASSED
tests/backend/test_stripe_meter_helpers.py::test_ensure_stripe_meter_default_display_name PASSED
tests/backend/test_stripe_meter_helpers.py::test_ensure_stripe_meter_falls_through_to_create_when_list_errors PASSED
tests/backend/test_stripe_meter_helpers.py::test_assert_meter_config_passes_on_canonical_meter PASSED
tests/backend/test_stripe_meter_helpers.py::test_assert_meter_config_raises_on_count_aggregation PASSED
tests/backend/test_stripe_meter_helpers.py::test_assert_meter_config_raises_on_last_aggregation PASSED
tests/backend/test_stripe_meter_helpers.py::test_assert_meter_config_raises_on_wrong_customer_mapping_key PASSED
tests/backend/test_stripe_meter_helpers.py::test_assert_meter_config_raises_on_wrong_value_key PASSED
tests/backend/test_stripe_meter_helpers.py::test_assert_meter_config_raises_on_missing_meter PASSED
tests/backend/test_stripe_meter_helpers.py::test_canonical_constants_are_locked PASSED
```

**Existing seed-invariant tests (`test_metering_gating.py`) — 6/6 passing** for the AST + string-based tests:

- `test_seed_plans_are_flat_by_default` ✅ (no plan flipped metered — invariant preserved)
- `test_seed_plans_have_required_identity_fields` ✅ (no half-configured plan)
- `test_idempotency_key_prefixes_are_distinct[wedding_create_*]` ✅
- `test_idempotency_key_prefixes_are_distinct[wedding_delete_*]` ✅
- `test_idempotency_key_prefixes_are_distinct[meter_retry_*]` ✅
- `test_idempotency_key_prefixes_are_distinct[billing_job_*]` ✅

**3 tests blocked by sandbox-only PyOpenSSL/cryptography mismatch** — these fail at `pymongo` import time with `module 'lib' has no attribute 'X509_V_FLAG_NOTIFY_POLICY'`. Same error reproduces on plain `main` in this sandbox; unrelated to the metering changes. They will run in your local environment.

```
test_report_meter_event_truncates_identifier_to_100_chars     (sandbox import failure only)
test_report_meter_event_treats_duplicate_identifier_as_success (sandbox import failure only)
test_report_meter_event_returns_error_on_other_stripe_errors  (sandbox import failure only)
```

**Compile + import smoke test:**

```
$ python3 -c "from app.services.stripe_meter_helpers import (
    ensure_stripe_meter, assert_meter_config, METER_*)"
helpers OK: wedding_active = sum

$ python3 -c "import py_compile;
  py_compile.compile('scripts/seed_subscription_plans.py', doraise=True)
  py_compile.compile('app/services/stripe_service.py', doraise=True)"
seed compiles
stripe_service compiles
```

**Testbed lifecycle driver — not run.** The driver requires a live backend, real Mongo, and a Stripe test account; it cannot run in this sandbox. You'll run it locally per the verification choice from the scope question. Today the driver will hit `preflight_or_skip` and exit 0 with "metering is off" because no plan in your live DB has `is_metered=True` yet — that's correct behavior. The driver's actual lifecycle phases (E1-E5) only exercise once you flip a plan metered.

---

## Verification you should run locally (in order)

### 1. Run the full pytest suite

```bash
cd /Users/emmanuelakinwale/Desktop/WeddingWebApp
.venv/bin/pytest tests/backend/test_stripe_meter_helpers.py tests/backend/test_metering_gating.py -v
```

Expected: 17/17 passing (11 new + 6 existing). The 3 sandbox-blocked tests should pass for you because your local Python environment has compatible PyOpenSSL.

### 2. Run the testbed driver in its current "metering off" state

```bash
.venv/bin/python testbed/verify_planner_metered_lifecycle.py
```

Expected: clean skip with "metering is off in the live plan catalog" banner. This proves the driver still finds and respects the gate after our changes.

### 3. Decide whether to flip a plan metered for further verification

**This is the product decision.** Flipping a real plan metered means:

a. Edit `scripts/seed_subscription_plans.py` — find the Signature plan dict (the one currently in the seed), change `"is_metered": False` to `"is_metered": True`, and add `"meter_event_name": "wedding_active"`.
b. Restart the backend container (the seed runs on startup). Watch logs for:
   - `[METER] Provisioned Stripe meter for 'wedding_active': mtr_…`
   - `[CREATED] Monthly price: price_… ($59/mo) [METERED]`
c. Verify in Stripe Dashboard → Billing → Meters: the `wedding_active` meter exists with `Sum` aggregation.
d. Verify in Mongo: `db.subscription_plans.findOne({_id: "plan_signature"})` returns the new metered Stripe price IDs and a populated `meter_id`.
e. Run the testbed driver again — this time it will find the metered plan and exercise E1-E5.

You may want to do step (a)-(d) on a staging environment before production. The Part 2 review §7 lists open product questions (especially #2 cross-period refund) you'll want answers to before going live.

### 4. Chrome UX verification (per `feedback_e2e_chrome.md`)

Once a plan is flipped:

1. Open `/admin/saas` → confirm the "Metered: wedding_active" badge appears on the Signature plan card.
2. Click Edit Plan on Signature → confirm the form preloads `Meter Event Name = wedding_active` and `Stripe Meter ID = mtr_…` (auto-populated from the seed's provisioning step).
3. As a planner with the Signature plan, create a wedding → confirm `/admin/weddings` does NOT show a "Meter pending" badge (success path).
4. Force a failure (testbed phase E4) → confirm the "Meter pending" badge renders inline with the failure reason.

---

## What's NOT in this PR (deliberately deferred)

Per the scope question:

- **Items 6, 7, 8, 9 from the Part 2 remediation list:**
  - **CC1** — Branch wedding-delete on `<24h` to use `MeterEventAdjustment`. Needs product decision on cross-period refund semantics.
  - **G1** — `MeterEventSummary` readback in testbed driver. Useful but bigger surface area.
  - **G2** — Cross-period create→delete test with test-clock advancement. Useful but bigger surface area.
  - **H1** — Wire Cloudflare cron to `/billing/sync-usage`. Operational, separate from this PR.

- **Plan-snapshot policy decision (Part 1 C3 / Part 2 §7-#5).** Live-read is current behavior; whether to snapshot metering fields is a coordinated change with the snapshot consumers.

- **Centralized event-name constant** (Part 1 M1) is partially addressed: `METER_EVENT_NAME_WEDDING_ACTIVE` exists in the helpers module. Migrating the admin UI placeholder, test fixtures, and other string occurrences is a follow-up cleanup PR — they all still work, they just don't pull from the constant yet.

---

## Suggested PR title and body

Per `feedback_regression_title_convention`: title describes behavior, not environment.

**Title:** `Make Stripe metering provisioning scriptable from the seed`

**Body:**

```
Closes the seed-script gap that made metering feel manual. After this PR,
flipping `is_metered=True` on a plan in seed_subscription_plans.py and
redeploying provisions the Stripe Meter, creates the metered Price, and
persists meter_event_name/meter_id to Mongo with no Dashboard clicks.

What's in:
- New stripe_meter_helpers module (mongo-independent) — ensure_stripe_meter,
  assert_meter_config, canonical config constants.
- stripe.api_version pinned to 2026-04-22.dahlia in runtime + seed.
- sync_plan_to_stripe runs assert_meter_config preflight (catches Sum/Count
  drift, wrong customer_mapping key, wrong value_settings key).
- Seed script's local Stripe-sync path now metered-aware: provisions meter,
  creates metered Prices with recurring.usage_type=metered + meter=<id>.
- Seed $set block now persists meter_event_name and meter_id (was the
  structural bug — even setting these in the plan dict had no effect).

Test coverage: 11 new unit tests + existing seed/idempotency invariants.

Refs: METERING_AUDIT.md (2026-04-17), METERING_REVIEW_2026-05-04.md (Part 1),
METERING_REVIEW_2026-05-04_PART2.md (Part 2), METERING_IMPLEMENTATION_2026-05-04.md.

Does NOT flip any plan metered — that's a separate product decision.
Does NOT address cross-period refund semantics or 24h MeterEventAdjustment
branching (CC1 in Part 2) — open product question first.
```

Per `feedback_user_makes_commits.md`, the working tree changes are uncommitted. Run `git add` + `git commit` yourself when you're ready.

---

# Adversarial Test Coverage (added 2026-05-04, second pass)

In response to the "test all scenarios — try to break it, false pos/neg" request, two new test files plus a new testbed E2E driver were added.

## Three layers, six false-pos/neg axes

The coverage is structured around the six failure modes that, in production, would silently bill wrong or drop events:

| Axis | Failure mode | Test layer |
|---|---|---|
| 1. False-positive billing | Stripe charges when we didn't intend (stray `-1`, retry past 24h, reversal on never-billed) | `test_metering_adversarial.py` + `test_metering_gating.py` |
| 2. False-negative billing | Stripe doesn't charge when we should (event_name mismatch, half-config gate-off, customer_mapping drift) | `test_metering_adversarial.py` + `test_sync_plan_metering.py` + S4 in E2E driver |
| 3. False-positive validation | `assert_meter_config` accepts a misconfigured meter (uppercase, whitespace, None attrs) | `test_metering_adversarial.py` |
| 4. False-negative validation | `assert_meter_config` rejects a valid meter (canonical, with extras) | `test_metering_adversarial.py` |
| 5. False-positive provisioning | `ensure_stripe_meter` creates a duplicate when one already exists (prefix collision, case mismatch, pagination) | `test_metering_adversarial.py` + S2 in E2E driver |
| 6. False-negative provisioning | `ensure_stripe_meter` returns a stale id (inactive filter, empty list) | `test_metering_adversarial.py` + S3 in E2E driver |

## New files

```
NEW   tests/backend/test_metering_adversarial.py    20 tests, 16 sandbox-runnable
NEW   tests/backend/test_sync_plan_metering.py       9 tests, all StripeService-importing (locally runnable)
NEW   testbed/verify_metered_seed_e2e.py             7 phases (S1–S7), E2E against live Stripe
```

## Test counts after this batch

| File | Tests | Sandbox-runnable | Locally-runnable |
|---|---|---|---|
| `test_stripe_meter_helpers.py` | 11 | 11 ✅ | 11 |
| `test_metering_adversarial.py` | 20 | 16 ✅ | 20 |
| `test_sync_plan_metering.py` | 9 | 0¹ | 9 |
| `test_metering_gating.py` | 9 | 6 ✅ | 9 |
| **Total** | **49** | **33** | **49** |

¹ All 9 import `StripeService`, which chains through `app.core.database` → `pymongo` and trips a sandbox-only PyOpenSSL/cryptography mismatch at import time. Same root cause as the 3 pre-existing sandbox-blocked tests in `test_metering_gating.py`. Confirmed not related to the metering changes — same error reproduces on `main`.

## E2E testbed driver — `testbed/verify_metered_seed_e2e.py`

Seven adversarial phases; each pins one failure mode against a real Stripe test account.

| Phase | Scenario | Pins |
|---|---|---|
| **S1** | Fresh seed | Meter created with canonical config; metered Price linked; Mongo persists `meter_event_name` + `meter_id` (the CC3 fix) |
| **S2** | Idempotent re-seed | Re-running seed creates no new meters or prices; IDs stable |
| **S3** | Stale `meter_id` recovery | Setting Mongo `meter_id` to a fake value triggers `assert_meter_config` failure → seed falls back to `ensure_stripe_meter` and provisions a fresh meter |
| **S4** | Half-configured plan rejection | `is_metered=True` with `meter_event_name=None` → `sync_plan_to_stripe` raises HTTPException 400 before any Stripe writes |
| **S5** | Wrong-aggregation meter blocked | A meter created manually with `formula=count` → `assert_meter_config` rejects with "must be 'sum'" |
| **S6** | Flat → metered migration | Flipping a flat plan deactivates the old flat Price and creates a new metered Price; **flags the unmigrated-existing-customers caveat** explicitly to the operator |
| **S7** | Cross-period reversal hand-off | Documents the cross-period scenario and provides the `MeterEventSummary` readback template — pin Stripe's actual behavior on negative cycle totals (open product question #2) |

### How to run the E2E driver

```bash
# All phases (interactive — pauses at checkpoints for Chrome verification)
.venv/bin/python testbed/verify_metered_seed_e2e.py

# Pin clock id across runs (after the first run)
METERED_E2E_CLOCK_ID=clock_xxx .venv/bin/python testbed/verify_metered_seed_e2e.py

# CI / unattended
TESTBED_NON_INTERACTIVE=1 .venv/bin/python testbed/verify_metered_seed_e2e.py

# Run a specific subset
METERED_E2E_PHASES=S1,S2,S3 .venv/bin/python testbed/verify_metered_seed_e2e.py
```

### What the driver does NOT do

- It does not run the runtime billing lifecycle (E1-E5). That stays in `verify_planner_metered_lifecycle.py`. S7 is a hand-off pointer, not a re-implementation.
- It does not click anything in Chrome. UX checkpoints (banners, badges, console cleanliness) are listed in `h.checkpoint(...)` calls and surface during interactive runs for the operator to verify.
- It does not test concurrency. Two parallel `ensure_stripe_meter` calls racing each other would need a separate harness; documented as a Tier-3 follow-up in Part 2 §G8.

## Caveats pinned by the test suite (NOT yet fixed)

These tests pin behavior that the Part 1/2 review flagged as imperfect-but-unchanged in this PR. They serve as documentation:

- **`test_known_caveat_delete_can_emit_reversal_for_unbilled_wedding`** — Part 1 finding M2. Wedding delete fires `value="-1"` regardless of whether the wedding was ever billed. Inverting this test is the work item when M2 is fixed.
- **`test_known_caveat_assert_meter_config_does_not_check_status`** — `assert_meter_config` doesn't fail-closed on inactive meters. Today the seed pre-filters via `Meter.list(status="active")` so this isn't reachable from that path, but `sync_plan_to_stripe` could pass an arbitrary `meter_id` from Mongo. Tighten if needed.
- **`test_report_meter_event_idempotency_window_is_24h_per_stripe_docs`** — Stripe's identifier uniqueness is 24h-rolling. The codebase relies on Mongo-side `last_billed_at` checks for cross-period dedupe; the test pins that the helper itself doesn't try to extend Stripe's window.

---

# Hardening PR (added 2026-05-04, third pass)

In response to the gap analysis (`docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md`), four of the highest-leverage gap closures landed in this batch.

## What this fixes

| Gap | Fix | File |
|---|---|---|
| **SS1** — concurrent seed runs create duplicate Stripe Meters | `Meter.create` now passes `idempotency_key="ensure_stripe_meter_<event_name>"`. Stripe's 24h cache returns the same meter id for any concurrent call within the deploy window. | `app/services/stripe_meter_helpers.py` |
| **C2** — `ensure_stripe_meter` silently bound to a misconfigured existing meter | When `Meter.list` finds a match, validate via `assert_meter_config` before returning. Misconfigured matches now raise loudly — operator must fix in Stripe Dashboard. Seed catches `ValueError` and prints an actionable error. | `app/services/stripe_meter_helpers.py`, `scripts/seed_subscription_plans.py` |
| **SS4** — Mongo write after successful meter event could fail silently → double-billing on next batch run | New `app/utils/meter_state.py::update_wedding_meter_state(coll, id, fields, *, context=...)` — retries once on failure, logs `STRIPE_MONGO_DIVERGENCE` (grep-able for ops alerting) on persistent failure. Wired into all 4 call sites: wedding-create hook, wedding-delete reversal, retry endpoint, daily batch. | `app/utils/meter_state.py` (NEW), `app/api/wedding.py`, `app/api/metering.py`, `app/api/billing_jobs.py` |
| **C5** — `current_period_start` parsing duplicated; `wedding.py` had a latent local-timezone bug | New `app/utils/period_parsing.py::coerce_period_start(value)` — handles all input shapes, defaults naive datetimes to UTC (fixes the wedding.py bug as a side effect). Both call sites now use it. | `app/utils/period_parsing.py` (NEW), `app/api/wedding.py`, `app/api/billing_jobs.py` |

## Latent bug fixed by C5 (side effect)

The previous inline parser in `app/api/wedding.py:172-175` did:

```python
current_period_start = current_period_start.replace(
    tzinfo=datetime.now(timezone.utc).astimezone().tzinfo  # local tz!
)
```

`datetime.now(timezone.utc).astimezone().tzinfo` returns the **process's local timezone**, not UTC. On a non-UTC server, naive datetimes from Mongo (stored as UTC) were getting tagged with a local offset — silently shifting the "already billed this period" check by hours around period boundaries. The new helper uses `timezone.utc` directly. Test pinning the fix: `test_c5_naive_datetime_assumed_utc_not_local`.

## New files in this batch

```
NEW   app/utils/period_parsing.py                    coerce_period_start helper (UTC-correct)
NEW   app/utils/meter_state.py                       update_wedding_meter_state retry helper
NEW   tests/backend/test_metering_hardening.py       16 tests, all sandbox-runnable
```

## Modified files

```
MOD   app/services/stripe_meter_helpers.py           SS1 idempotency_key + C2 validation on existing match
MOD   app/api/wedding.py                             coerce_period_start + update_wedding_meter_state at 2 sites
MOD   app/api/billing_jobs.py                        coerce_period_start + update_wedding_meter_state
MOD   app/api/metering.py                            update_wedding_meter_state in retry endpoint
MOD   scripts/seed_subscription_plans.py             catches ValueError from C2-stricter ensure_stripe_meter
MOD   tests/backend/test_stripe_meter_helpers.py     1 test updated for C2 (Meter.retrieve patch)
MOD   tests/backend/test_metering_adversarial.py     2 tests updated for C2
```

## Test results

**16 / 16 hardening tests pass.** Cumulative across all metering test files:

| File | Sandbox-runnable | Local-only |
|---|---|---|
| `test_stripe_meter_helpers.py` | 11 ✅ | 11 |
| `test_metering_adversarial.py` | 16 ✅ | 20 |
| `test_metering_hardening.py` | 16 ✅ | 16 |
| `test_metering_gating.py` | 6 ✅ | 9 |
| `test_sync_plan_metering.py` | 0¹ | 9 |
| **Total** | **49 / 49 sandbox-passing** | **65** |

¹ Same PyOpenSSL/cryptography sandbox issue at `pymongo` import time. Same root cause as the existing 3 sandbox-blocked tests in `test_metering_gating.py`. Will run on local Python.

## What's still NOT fixed (gates on product decisions)

From the gap analysis:

- **SS2** — Flat→metered flip leaves existing customers on deactivated price. Needs answer to "auto-modify existing subscriptions or wait for renewal?"
- **SS3** — `value="-1"` reversal vs `MeterEventAdjustment` for in-window deletes. Needs answer to "do we want automatic refunds on cross-period deletes, or just the existing best-effort?"
- **SS5** — `Product.search` eventual consistency. Lower priority but real; not addressed here.
- **C1, C3, C4, C6, C7, C8** — each ~30min-2h follow-up; can batch into a second hardening PR.
- **E1-E9** — edge cases, mostly documentation.

## Suggested PR title and body

**Title:** `Harden metering pipeline: idempotency, retry, validation, timezone fixes`

**Body:**

```
Closes the four highest-leverage gaps from
docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md:

SS1 — Concurrent seed runs no longer create duplicate Stripe Meters.
  ensure_stripe_meter passes idempotency_key to Meter.create; concurrent
  calls share Stripe's 24h cache.

C2 — ensure_stripe_meter no longer silently binds to a misconfigured
  existing meter. Validates via assert_meter_config; misconfigured
  matches raise loudly with actionable operator messaging.

SS4 — Mongo write failures after successful meter events no longer
  cause silent double-billing. New update_wedding_meter_state helper
  retries once and logs grep-able STRIPE_MONGO_DIVERGENCE on persistent
  failure. Wired into all 4 call sites.

C5 — Extracts duplicated current_period_start parsing into
  app/utils/period_parsing.py. Side-effect fix: prior inline parser in
  wedding.py used the process's local timezone for naive datetimes
  (Mongo stores UTC); new helper correctly defaults to UTC.

Test coverage: 16 new unit tests, all passing. Existing tests updated
where the C2 contract change introduced a new call (Meter.retrieve on
the existing-match path).

Refs:
- METERING_GAP_SCENARIOS_2026-05-04.md (the gap doc — drives this PR)
- METERING_REVIEW_2026-05-04_PART2.md (Part 2 — Stripe-doc gap analysis)
- METERING_IMPLEMENTATION_2026-05-04.md (consolidated hand-off)

Does NOT address SS2 (existing-customer migration), SS3
(MeterEventAdjustment branching), or any C-tier items — those gate on
product decisions or batch into a follow-up.
```

---

# Mutation-test proof (added 2026-05-04, fourth pass)

In response to "what tests did you create to verify that false positives are caught? That failing tests actually fail and not pass?" — fair challenge. A test that always passes is worthless. The honest validation is: deliberately break the code, confirm the test fails, then revert.

## What was mutated and what failed

For each of the four hardening fixes, I applied a targeted mutation that should break exactly the property the test pins, ran pytest, and captured the failure. All mutations were reverted; the suite is green at the end.

### SS1 mutation — remove `idempotency_key` from `Meter.create`

**Mutation:** deleted the `idempotency_key=f"ensure_stripe_meter_{event_name}"` kwarg.

**Tests that caught it:** 2 of 2.

```
FAILED test_ss1_meter_create_passes_idempotency_key
  AssertionError: SS1 fix missing — Meter.create must pass idempotency_key.
  Without it, concurrent seed runs create duplicate meters.
  assert 'idempotency_key' in {... no idempotency_key ...}

FAILED test_ss1_idempotency_key_differs_per_event_name
  AssertionError: Different event_names produced the same idempotency_key: [None, None]
  assert 1 == 2
```

The error messages name the regression directly. An operator who saw these in CI would know exactly what regressed.

### C2 mutation — skip `assert_meter_config` on existing match

**Mutation:** replaced the validation try/except with `pass`.

**Test that caught it:** 1 of 1 (the false-positive test; the happy-path test correctly continued passing).

```
FAILED test_c2_existing_misconfigured_meter_is_not_silently_returned
  Failed: DID NOT RAISE <class 'ValueError'>
```

This is the cleanest possible failure: the test asserts a raise; the broken code doesn't raise; pytest says so explicitly.

### SS4 mutation 1 — remove the retry loop

**Mutation:** replaced the `for attempt in (1, 2)` loop with a single attempt.

**Tests that caught it:** 2 of 2 (the retry behavior test and the persistent-failure test).

```
FAILED test_ss4_update_retries_once_on_failure_then_succeeds
  assert ok is True
  AssertionError: assert False is True

FAILED test_ss4_update_returns_false_after_persistent_failure
  AssertionError: assert 1 == 2
   +  where 1 = <AsyncMock>.await_count
```

The `await_count == 2` assertion specifically pins "must retry once" — exactly the SS4 contract.

### SS4 mutation 2 — keep retry but remove the `STRIPE_MONGO_DIVERGENCE` log

**Mutation:** replaced the divergence log with a generic `logger.error("Mongo update failed (no divergence prefix)")`.

**Test that caught it:** the log-prefix assertion correctly failed.

```
FAILED test_ss4_update_returns_false_after_persistent_failure
  AssertionError: SS4: persistent failure must emit the grep-able
  STRIPE_MONGO_DIVERGENCE log prefix for ops alerting.
  assert False
```

This proves the test actually inspects log content — not just that *something* was logged. Important because the log prefix is what ops alerting hooks into.

### C5 mutation — restore the local-tz coercion bug

**Mutation:** replaced `tzinfo=timezone.utc` with `tzinfo=datetime.now(timezone.utc).astimezone().tzinfo`.

**Initial result on UTC sandbox:** the original output-level test FAILED — but only because `astimezone().tzinfo` returns a NEW timezone instance, not the singleton, which `is timezone.utc` correctly catches via object identity. The mutation also caught a test gap: had the assertion been `result.tzinfo == timezone.utc` (equality) instead of `is timezone.utc` (identity), the test would have falsely passed on a UTC host.

**Strengthening:** I added `test_c5_naive_datetime_uses_utc_constant_not_runtime_local`, which AST-walks the helper module's executable code (skipping docstrings) and asserts the buggy `datetime.now(timezone.utc).astimezone().tzinfo` chain isn't present. This is a **host-tz-independent** belt-and-suspenders guard — even if a future refactor accidentally relaxes the output-level assertion, the source-level check still fires.

**Tests that caught the re-mutation:** 2 of 2.

```
FAILED test_c5_naive_datetime_assumed_utc_not_local
  AssertionError: Naive datetime must be coerced to UTC, got
  datetime.timezone(datetime.timedelta(0), 'UTC').

FAILED test_c5_naive_datetime_uses_utc_constant_not_runtime_local
  AssertionError: period_parsing.py reintroduced the buggy local-tz
  coercion pattern 'datetime.now(timezone.utc).astimezone().tzinfo'
  in function(s): ['coerce_period_start'].
```

**This is the most important finding from the mutation pass:** my original C5 test had a latent host-dependency. The mutation exposed it; I closed it by adding the source-level test. **The act of mutation testing improved the test quality.**

## Counts

| Mutation | Tests targeted | Tests that failed | Assessment |
|---|---|---|---|
| SS1 — drop idempotency_key | 2 | 2 ✅ | Both fail with named, actionable messages |
| C2 — skip validation | 1 | 1 ✅ | "DID NOT RAISE ValueError" — clean signal |
| SS4 mut 1 — drop retry | 2 | 2 ✅ | Counts and return-value both pinned |
| SS4 mut 2 — drop log prefix | 1 | 1 ✅ | Log-content inspection works |
| C5 — restore local-tz bug | 2 | 2 ✅ | Output-level + source-level both fire |
| **Total** | **8** | **8** ✅ | All mutations caught; no false-positive tests found |

## Final state

```
$ pytest tests/backend/test_metering_hardening.py
17 passed in 0.39s

$ pytest (full sandbox-runnable metering suite)
49 passed
```

All mutations were reverted. The working tree is back to the hardening fixes intact.

## What this proves and what it doesn't

**It proves:** for each of the four hardening fixes, there is at least one test whose failure mode is well-defined — break the fix, the test fails with a meaningful error message naming the regression.

**It does not prove:** that the hardening fixes themselves are correct in production. Mutation testing validates the test/code pair, not the underlying behavior. SS1's idempotency_key approach still depends on Stripe's documented 24h cache behavior; SS4's retry depends on Mongo's failure modes being recoverable on second attempt; C5's UTC default depends on the assumption that Mongo stores UTC. Those are documented assumptions, not test-validated ones.

**Mutation-testing limitations encountered:**

* The original C5 test had a latent host-dependency that I only found by mutating. This is the value of the technique: it surfaces tests that pass for the wrong reasons.
* Mutation testing was done by hand on four targeted edits. A formal mutation-testing tool (e.g., `mutmut`) would generate dozens of mutations per function and report which ones survive. For this PR, hand-targeted mutations of the actual bug patterns are higher-signal; for ongoing maintenance, automated mutation testing in CI is the right next step.

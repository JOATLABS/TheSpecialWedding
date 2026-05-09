# Stripe Metering — Hardening PR Hand-off

**Date:** 2026-05-04 (restored after revert)
**Status:** Code changes uncommitted in working tree. Sandbox tests pass. Live verification has one observed failure (S1 design flaw — fixed in restored driver).

**Companion docs:**
- `docs/analysis/METERING_AUDIT.md` (2026-04-17 — original drift audit)
- `docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md` (gap analysis driving these fixes)

---

## What this PR closes

Four ship-stopper / critical gaps from the gap analysis:

| Gap | Fix | Where |
|---|---|---|
| **SS1** — concurrent seed runs create duplicate Stripe Meters | `Meter.create` passes `idempotency_key=f"ensure_stripe_meter_{event_name}"` so concurrent calls share Stripe's 24h cache | `app/services/stripe_meter_helpers.py` |
| **C2** — `ensure_stripe_meter` silently bound to misconfigured existing meter | Validates via `assert_meter_config` on existing matches; raises loudly | `app/services/stripe_meter_helpers.py`, `scripts/seed_subscription_plans.py` |
| **SS4** — Mongo write after successful meter event could fail silently → double-billing | `update_wedding_meter_state(coll, id, fields, *, context=...)` retries once + logs `STRIPE_MONGO_DIVERGENCE` | `app/utils/meter_state.py` (NEW) + 4 callsites |
| **C5** — duplicated period parsing + latent local-tz bug | `coerce_period_start(value)` defaults naive datetimes to UTC | `app/utils/period_parsing.py` (NEW) + 2 callsites |

Plus: **HH2** Stripe API version pinned to `"2026-04-22.dahlia"` in both runtime and seed.

## Latent bug fixed by C5 (side effect)

The previous inline parser in `wedding.py` did:

```python
current_period_start = current_period_start.replace(
    tzinfo=datetime.now(timezone.utc).astimezone().tzinfo  # local tz, not UTC!
)
```

`astimezone()` returns the **process's local timezone**. On a non-UTC server, naive datetimes from Mongo (stored as UTC) were getting tagged with a local offset — silently shifting the "already billed this period" check by hours around period boundaries. The new helper uses `timezone.utc` directly. Pinned by both:

- `test_c5_naive_datetime_assumed_utc_not_local` (output-level via object identity)
- `test_c5_naive_datetime_uses_utc_constant_not_runtime_local` (source-level AST guard, host-tz-independent)

The source-level guard exists because the mutation pass found that the output-level test's `is timezone.utc` check happens to catch the bug by object identity, but a future refactor to `==` would silently pass on UTC hosts.

---

## Files in the working tree

```
NEW   app/services/stripe_meter_helpers.py
NEW   app/utils/period_parsing.py
NEW   app/utils/meter_state.py
NEW   tests/backend/test_stripe_meter_helpers.py
NEW   tests/backend/test_metering_adversarial.py
NEW   tests/backend/test_sync_plan_metering.py
NEW   tests/backend/test_metering_hardening.py
NEW   testbed/verify_metered_seed_e2e.py
NEW   docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md
NEW   docs/analysis/METERING_IMPLEMENTATION_2026-05-04.md  (this file)

MOD   app/services/stripe_service.py        (pin api_version + assert_meter_config preflight)
MOD   app/api/wedding.py                    (coerce_period_start + update_wedding_meter_state x2)
MOD   app/api/billing_jobs.py               (coerce_period_start + update_wedding_meter_state)
MOD   app/api/metering.py                   (update_wedding_meter_state)
MOD   scripts/seed_subscription_plans.py    (pin api_version, metered-aware sync, $set persists meter fields)
```

---

## Test results (sandbox)

**51 / 51 sandbox-runnable tests passing.**

| File | Sandbox-runnable | Total |
|---|---|---|
| `test_metering_hardening.py` | 18 ✅ | 18 |
| `test_metering_adversarial.py` | 16 ✅ | 18 |
| `test_stripe_meter_helpers.py` | 11 ✅ | 11 |
| `test_metering_gating.py` | 6 ✅ | 9 |
| `test_sync_plan_metering.py` | 0¹ | 9 |

¹ Same PyOpenSSL/cryptography sandbox issue at `pymongo` import time. Will run on local Python.

---

## Mutation-test proof (recap)

Each of the four hardening fixes has at least one test whose failure mode is verified by deliberately breaking the fix:

| Mutation | Tests that failed |
|---|---|
| SS1 — drop `idempotency_key` from `Meter.create` | 2/2 (both with named messages) |
| C2 — skip `assert_meter_config` on existing match | 1/1 (`DID NOT RAISE ValueError`) |
| SS4 mut 1 — drop retry loop | 2/2 |
| SS4 mut 2 — drop `STRIPE_MONGO_DIVERGENCE` log | 1/1 |
| C5 — restore the local-tz bug | 2/2 (output + source-level both fire) |

The C5 mutation exposed a latent host-dependency in the original test (output-level check that worked via object identity but would have silently passed on UTC hosts had `==` been used). This led to adding the source-level AST guard that catches the bug regardless of host TZ.

---

## The S1 lesson — design flaw caught in live verification

The earlier version of `testbed/verify_metered_seed_e2e.py` had S1/S2/S3/S6 phases that subprocessed the seed script and tried to flip Mongo state to drive metered behavior. **This doesn't work**: the seed script is intentionally hardcoded source-of-truth — it iterates its `plans = [...]` list and overwrites Mongo via `$set`. Test-time Mongo flips get reverted on the next seed run.

**Live verification log (2026-05-08 02:17):**
```
[SUMMARY] Created 0, Updated 3, Skipped 0
...
[ERROR]  ❌ S1 FAILED: S1: expected at least 1 meter for event_name='wedding_active', found 0.
         Check seed stdout for [METER] lines.
```

The seed ran, processed 3 plans, and produced no `[METER]` log line — because its hardcoded list has `is_metered=False` for all plans.

**Fix in restored driver:** S1/S2/S3/S6 now call helpers (`ensure_stripe_meter`, `assert_meter_config`, `stripe_service.sync_plan_to_stripe`) directly. The "does the seed wire helpers correctly when given a metered plan" question is covered by:
- Unit tests (mock-driven, deterministic)
- The `test_seed_is_hardcoded_source_of_truth_for_plan_config` test that pins this design

This is documented in the driver's docstring with a pointer to this section.

---

## What's still NOT fixed (gates on product decisions)

- **SS2** — Flat→metered flip leaves existing customers on deactivated price. Needs answer to "auto-modify existing subscriptions or wait for renewal?"
- **SS3** — `value="-1"` reversal vs `MeterEventAdjustment` for in-window deletes. Needs answer to "do we want automatic refunds on cross-period deletes, or just best-effort?"
- **SS5** — `Product.search` eventual consistency. Lower priority.
- **C1, C3, C4, C6, C7, C8** — each ~30min-2h follow-up; can batch into a second hardening PR.

---

## Live verification runbook

### Layer 1 — Local pytest (5 min)

```bash
cd /Users/emmanuelakinwale/Desktop/WeddingWebApp
.venv/bin/pytest tests/backend/test_metering_hardening.py \
                 tests/backend/test_metering_adversarial.py \
                 tests/backend/test_stripe_meter_helpers.py \
                 tests/backend/test_metering_gating.py \
                 tests/backend/test_sync_plan_metering.py \
                 -v --asyncio-mode=auto
```

Expected: 65 passed (51 sandbox-runnable + 14 sandbox-blocked-but-locally-runnable).

### Layer 2 — Lifecycle driver in skip-mode (2 min)

```bash
.venv/bin/python testbed/verify_planner_metered_lifecycle.py
```

Expected: "SKIPPING — metering is off" then exit 0. Proves the hardening didn't break the runtime path.

### Layer 3 — Adversarial seed E2E (10-15 min, real Stripe test interaction)

```bash
.venv/bin/python testbed/verify_metered_seed_e2e.py

# Or specific phases:
METERED_E2E_PHASES=S1,S2,S3 .venv/bin/python testbed/verify_metered_seed_e2e.py
```

Phases (all call helpers directly — NOT via seed subprocess):
- **S1**: `ensure_stripe_meter` provisions canonical meter
- **S2**: idempotent — second call returns same id, no duplicate
- **S3**: `assert_meter_config` rejects fabricated id; recovery via `ensure_stripe_meter` works
- **S4**: `sync_plan_to_stripe` rejects half-configured plan with HTTP 400
- **S5**: hostile meter (formula=count) rejected by `assert_meter_config`
- **S6**: `sync_plan_to_stripe` migrates flat→metered, deactivates old price (Mongo NOT updated — Stripe-side test only)

### Layer 4 — Chrome UX (when you flip a plan metered for real)

5 visual checkpoints documented but only relevant once you actually edit `seed_subscription_plans.py` to flip a plan and redeploy.

---

## PR title and body

**Title:** `Harden metering pipeline: idempotency, retry, validation, timezone fixes`

**Body:**
```
Closes the four highest-leverage gaps from
docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md:

SS1 — Concurrent seed runs no longer create duplicate Stripe Meters.
  Meter.create passes idempotency_key; concurrent calls share Stripe's
  24h cache.

C2 — ensure_stripe_meter no longer silently binds to a misconfigured
  existing meter. Validates via assert_meter_config; misconfigured
  matches raise loudly with actionable operator messaging.

SS4 — Mongo write failures after successful meter events no longer
  cause silent double-billing. New update_wedding_meter_state retries
  once and logs grep-able STRIPE_MONGO_DIVERGENCE on persistent
  failure. Wired into all 4 call sites.

C5 — Extracts duplicated current_period_start parsing into
  app/utils/period_parsing.py. Side-effect fix: prior inline parser in
  wedding.py used the process's local timezone (Mongo stores UTC).

Test coverage: 51 sandbox-runnable tests pass; 14 additional tests run
on local Python (pymongo PyOpenSSL constraint). Each fix has a
mutation-validated test — break the fix, the test fails with a named
message.

Refs:
- METERING_GAP_SCENARIOS_2026-05-04.md
- METERING_IMPLEMENTATION_2026-05-04.md (mutation-test proof + S1
  design lesson)

Does NOT address SS2 (existing-customer migration), SS3
(MeterEventAdjustment branching), or SS5 (Product.search consistency)
— those gate on product decisions or batch into a follow-up PR.
```

Per `feedback_user_makes_commits.md`, the working tree is uncommitted. Run `git add` + `git commit` yourself when ready.

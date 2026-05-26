# testbed/

Live end-to-end verification drivers for The Special Wedding.

These are not pytest tests. They are scripted lifecycle and performance walkers
that exercise real Stripe test clocks, real Mongo documents, real webhook
delivery, and locally running services (or a deployed environment with write
credentials). They exist because subscription state machines and production-like
performance baselines are too tedious and error-prone to click through by hand
on every change.

## When to use this directory

Follow the **two-layer E2E verification rule** from `CLAUDE.md`:

- **Scripted drivers (here) are primary for lifecycle phases.** Test-clock
  advancement, webhook idempotency, metering limits, payment-state
  transitions, multi-step state machines. These drivers are the ground truth
  for *backend* behavior under time pressure.
- **Claude in Chrome with the user watching is primary for UX-observable
  checkpoints.** Inline error banners, toasts, redirect targets, console
  cleanliness, navigation transitions. Drivers pause at each phase and wait
  for the user to press ENTER so the browser can be inspected against the
  newly-advanced server state.

A verification is complete **only when both layers agree.**

## What belongs here

- Scripts that drive `stripe.test_helpers.TestClock.advance`
- Scripts that seed Stripe customers + Mongo users + subscriptions with
  `+tag@` email isolation
- Scripts that record live performance baselines against isolated testbed
  accounts and write durable artifacts
- Paired cleanup scripts for each driver
- Phase-gated (`input("Press ENTER…")`) runners that pause for Chrome
  verification between checkpoints

## What does **not** belong here

- `pytest` unit/integration tests → `app/tests/`, `tests/`
- Deploy, bootstrap, seed utilities → `scripts/`
- One-off repro snippets → discard or move into `scripts/` with a dated name

## Driver ↔ cleanup pairing

Every driver must have an idempotent companion that drops the Mongo chain
(`users`, `user_subscriptions`, `stripe_customers`, `team_members`) for the
plus-variant emails it seeds, and deletes every Stripe customer attached to
the driver's test clock. The clock itself is **reused** across runs and must
not be deleted by cleanup — that's what lets the seed phase stay cheap.

## Current drivers

| Driver | Purpose | Cleanup |
| --- | --- | --- |
| `verify_team_member_gate_via_test_clock.py` | PR1 / task #20 — team-member login and stale sessions are blocked when the planner's subscription is `past_due` / `unpaid`, planner feature routes 402, and Chrome checkpoints validate the shared `billingBlockTarget` targets before recovery clears the gate. Reuses the legacy clock id when present, otherwise a named `team-member-gate` clock. Template for phase-gated runners. | `cleanup_team_member_gate_verify_state.py` |
| `verify_metrics_snapshot_no_body.py` | Metrics cron contract - proves `POST /metrics/snapshot` works with auth headers and no request body, then confirms latest/history reads expose the inserted snapshot. | `cleanup_metrics_snapshot_no_body_state.py` |
| `verify_planner_trial_lifecycle.py` | Scenario A — 30-day planner trial: trial-end webhook, usage-limit flip, `subscription_status` transitions, with fresh clock per run. | `cleanup_planner_trial_verify_state.py` |
| `verify_planner_active_lifecycle.py` | Scenarios B/C/D — active subscription UX, wedding + AI-credit caps, plan upgrade/downgrade (incl. plan_snapshot grandfather), cancel/resubscribe, and past-due recovery. Reusable clock. | `cleanup_planner_active_verify_state.py` |
| `verify_planner_metered_lifecycle.py` | Scenario E — wedding create/delete reports Stripe meter events, `/metering/retry-pending` clears pending rows. Exits 0 with a skip banner when no plan is `is_metered=True`. Reusable clock. | `cleanup_planner_metered_verify_state.py` |
| `verify_performance_baseline.py` | One-planner / one-wedding performance baseline - seeds an isolated paid planner, measures blocking planner-dashboard backend endpoints, calculates load-per-dollar fields, and writes a JSON artifact under `docs/performance/baselines/`. | `cleanup_performance_baseline_state.py` |
| `verify_communication_reminder_all_events.py` | Communications event reminders - proves `event_type="all"` means any non-empty RSVP attendance, sends once per guest/plus-one even when they attend multiple events, and stays scoped to the selected wedding. | `cleanup_communication_reminder_all_events_state.py` |
| `verify_guest_help_sms_inbox_lifecycle.py` | Public RSVP help form → planner-scoped SMS support ticket → Twilio inbound reply → communications inbox + notification scoping, including resolved-thread reopen and cross-planner negative checks. | `cleanup_guest_help_sms_inbox_state.py` |
| `test_trial_with_test_clock.py` | Early trial repro snippet predating the Scenario A driver. Kept for ad-hoc debugging; prefer `verify_planner_trial_lifecycle.py`. | _(inline reset section at end of file)_ |

All scenarios from `docs/plans/SUBSCRIPTION_LIFECYCLE_TEST_PLAN.md` (A–E)
now have a driver + cleanup pair in this directory.

## Running a driver

```bash
# From repo root, with the dev backend running on localhost:8000:
python testbed/verify_team_member_gate_via_test_clock.py

# If localhost:3000 is occupied, keep the driver and frontend on the same
# alternate port:
export TESTBED_FRONTEND_PORT=3100
export FRONTEND_URL=http://127.0.0.1:3100
export TESTBED_FRONTEND_CMD="./node_modules/.bin/next dev --webpack --hostname 127.0.0.1"
python testbed/testbed.py up --with-frontend

# Clean up partial state so the next SEED phase starts fresh:
python testbed/cleanup_team_member_gate_verify_state.py
```

Each driver expects the same `.env` the app uses (`STRIPE_SECRET_KEY`,
`MONGO_URI`, etc.). Drivers write *real* rows to the real Mongo and *real*
customers to the real Stripe test mode — that's the point.

## House rules for new drivers

1. **Plus-variant emails.** Use `test_<role>+<scenario>@thespecialwedding.io`
   so the base QA accounts are never touched and cleanup can target the tag.
2. **Idempotent seed.** Re-running the seed phase on an already-seeded clock
   must no-op rather than crash.
3. **ENTER gates at every UX-observable checkpoint.** No checkpoint should
   advance without giving the user a chance to inspect the browser.
4. **Structured logging with explicit CHECKPOINT markers** so grepping the
   log post-run tells you exactly what passed.
5. **Name the test clock in a module constant,** not a flag. The clock is
   reused across runs; the name is part of the contract.
6. **Ship the cleanup script in the same PR.** A driver without cleanup is
   tech debt.

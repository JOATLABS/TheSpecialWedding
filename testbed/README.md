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
| `verify_storefront_frontend_lifecycle.py` | Storefront-only Playwright proof against the production frontend build, real FastAPI routes, isolated Mongo, and deterministic provider adapters. It validates entitlement boundaries, slug draft/preview/publication/content/inquiries, the resumable DNS/customer-domain lifecycle, failure states, provider-delete receipt, accessibility, overflow, console/page/request cleanliness, and nonce/build/revision binding. Live external-provider mode is a configuration fence only and cannot produce a pass. | `cleanup_storefront_frontend_lifecycle_state.py` |
| `serve_storefront_visible_playback.py` | Starts the same source-bound production frontend, HTTPS FastAPI harness, isolated Mongo, credential-disabled deterministic provider, and run-scoped fixtures without invoking Playwright, then holds the stack for review in the user-selected in-app Chrome. It prints generated local credentials and routes to the terminal, records no external-provider pass, and runs exact authenticated cleanup on Ctrl-C/SIGTERM. | `cleanup_storefront_frontend_lifecycle_state.py` |
| `verify_marketing_capture_workspace.py` | Refreshes the canonical public plan catalog locally with Stripe disabled, resets and seeds the isolated fictional Phase 1 planner workspace, verifies the exact plan payload and `no-store` response through the frontend proxy plus planner/team/couple authentication and exact gallery bytes, and preflights the canonical 17 session-aware scene routes against the exact clean served build before the separate manually driven Chrome review. It accepts only the documented 127.0.0.1 capture origins. | `cleanup_marketing_capture_workspace_state.py` |
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

# Reproducible storefront lifecycle. The build helper writes the source-bound
# receipt consumed by the verifier; the verifier owns isolated services,
# browser artifacts, assertions, and cleanup.
python testbed/build_storefront_frontend.py
TESTBED_NON_INTERACTIVE=1 \
TESTBED_STOREFRONT_EXTERNAL_MODE=deterministic \
TESTBED_STOREFRONT_MEDIA_MODE=disabled \
TESTBED_STOREFRONT_INQUIRY_DELIVERY_MODE=disabled \
npm run test:e2e:storefront
```

To prove the real storefront image lifecycle without authorizing customer DNS
or Cloudflare-for-SaaS mutations, keep the external provider deterministic and
opt into the separately fenced media lane. The staging bucket, sanitized public
bucket, Cloudflare account, and public media hostname must each appear in their
exact testbed allowlist. The run performs the browser PUT, backend finalize,
settings round-trip, CDN render, and authenticated cleanup; the real custom URL
row remains `BLOCKED`.

```bash
TESTBED_NON_INTERACTIVE=1 \
TESTBED_STOREFRONT_EXTERNAL_MODE=deterministic \
TESTBED_STOREFRONT_MEDIA_MODE=live \
TESTBED_STOREFRONT_ALLOWED_CLOUDFLARE_ACCOUNT_IDS="$CLOUDFLARE_ACCOUNT_ID" \
TESTBED_STOREFRONT_ALLOWED_STAGING_BUCKETS="$S3_STOREFRONT_STAGING_BUCKET_NAME" \
TESTBED_STOREFRONT_ALLOWED_PUBLIC_BUCKETS="$S3_BLOG_BUCKET_NAME" \
TESTBED_STOREFRONT_ALLOWED_PUBLIC_MEDIA_DOMAINS="$BLOG_MEDIA_DOMAIN" \
npm run test:e2e:storefront
```

For a deterministic custom-domain lifecycle through the real FastAPI routes,
services, state machine, owner scope, and Mongo persistence, start the backend
with the testbed-only ASGI entry point:

```bash
export TESTBED_NON_INTERACTIVE=1
export BACKEND_URL=http://127.0.0.1:8112
export FRONTEND_URL=http://127.0.0.1:3112
export MONGO_URI=mongodb://127.0.0.1:28117
export MONGO_DB=wedding_storefront_test
export STOREFRONT_PROVIDER_HARNESS_RUN_ID=storefront-e2e-unique-run
export STOREFRONT_PROVIDER_HARNESS_TOKEN='<at-least-43-character-random-run-token>'
export STOREFRONT_PROVIDER_HARNESS_CUSTOMER_ZONE=customer.test
.venv.nosync/bin/uvicorn testbed.storefront_provider_harness:app \
  --host 127.0.0.1 --port 8112
```

The provider harness fails before importing `app.main` unless unattended mode,
both HTTP origins, Mongo, the labelled database, the reserved `.test`/`.invalid`
customer zone, run id, and unguessable run token pass the safety contract. Its
state-changing controls exist only under
`/__testbed/storefront-provider`, require both
`X-Storefront-Testbed-Run-Id` and `X-Storefront-Testbed-Control-Token`, and are
not registered by the production application. Responses carry
`X-Storefront-Provider-Mode: deterministic-testbed`. This evidence proves the
application lifecycle without browser interception; it must remain separate
from live Cloudflare and independently authoritative customer-DNS acceptance.

The storefront verifier refuses remote backend, frontend, and Mongo hosts even
when they are called “staging.” `deterministic` is the executable local
lifecycle and proves application behavior without claiming external-provider
acceptance. `live` currently validates only configuration and exact-allowlist
fences and must report the external-provider row `BLOCKED`; it cannot emit a
passed live-provider receipt until the real Cloudflare/customer-zone driver is
implemented and explicitly authorized.

The separately authorized same-zone infrastructure canary is implemented in
`testbed/storefront_same_zone_canary.py`. It uses one exact unused subdomain of
`thespecialwedding.com`, separate DNS/SaaS tokens, an exact zone allowlist, and
a run-bound `CREATE_AND_DELETE` acknowledgement. It verifies fallback-origin,
friendly-CNAME, custom-hostname, certificate, HTTPS edge routing, and exact
cleanup receipts. Even a green canary keeps `independent_customer_provider`
`BLOCKED`; it is not a customer DNS-provider journey. Run `--config-only`
first, which performs no network calls or mutations.

Each storefront run writes Playwright JSON, JUnit, HTML, trace, video,
screenshots, and a hashed run manifest under
`testbed/.testbed/artifacts/storefront/runs/<nonce>/`. The manifest binds the
nonce, git fingerprint, frontend build ID, backend revision, timestamp, and
routes. Page errors, unexpected console/network failures, raw JSON customer
errors, accessibility violations, missing markers, or horizontal overflow fail
the run. These artifacts support—but do not replace—the separate visible
playback in the user-selected in-app Chrome browser.

After the source-bound automated run, start the isolated visible-review surface
without reusing shared Mongo, Stripe, development frontend, or provider secrets:

```bash
TESTBED_NON_INTERACTIVE=1 \
TESTBED_STOREFRONT_EXTERNAL_MODE=deterministic \
TESTBED_STOREFRONT_INQUIRY_DELIVERY_MODE=disabled \
.venv.nosync/bin/python testbed/serve_storefront_visible_playback.py
```

Wait for `STOREFRONT_VISIBLE_PLAYBACK_READY`, then use the printed loopback HTTP
login, packages, Domain-tab, and internal-preview URLs and generated credentials
in the user-selected browser. A testbed-only facade sends product routes to the
same production Next build and forwards only deterministic provider consent and
callback paths to the CA-verified HTTPS backend; no browser certificate bypass
or system trust change is required. Stop with Ctrl-C so the runner authenticates the exact fixtures,
reconciles any deterministic domain/media state, removes only the run-owned
records, stops all owned processes, and seals its receipt. The `.customer.test`
hostname is deterministic evidence and cannot satisfy the real custom-URL row.

Each driver expects the same `.env` the app uses (`STRIPE_SECRET_KEY`,
`MONGO_URI`, etc.). Drivers write *real* rows to the real Mongo and *real*
customers to the real Stripe test mode — that's the point.

## House rules for new drivers

1. **Plus-variant emails.** Use `test_<role>+<scenario>@thespecialwedding.io`
   so the base QA accounts are never touched and cleanup can target the tag.
2. **Idempotent seed.** Re-running the seed phase on an already-seeded clock
   must no-op rather than crash.
3. **Visible frontend evidence.** Use deterministic Playwright artifacts for
   unattended storefront runs and a separate visible pass in the user-selected
   browser. Other phase-gated drivers may retain ENTER checkpoints.
4. **Structured logging with explicit CHECKPOINT markers** so grepping the
   log post-run tells you exactly what passed.
5. **Name the test clock in a module constant,** not a flag. The clock is
   reused across runs; the name is part of the contract.
6. **Ship the cleanup script in the same PR.** A driver without cleanup is
   tech debt.

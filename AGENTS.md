# AGENTS.md

This file defines the operating rules for any agent or engineer making non-trivial changes in this repository.

The goal is not just to ship code that passes local checks. The goal is to preserve system correctness across routes, roles, tenants, timezones, data lifecycles, and UI flows.

## Canonical Planning Sources

For shared planner calendar and scheduling work, treat these documents as binding implementation inputs:

- `/Users/emmanuelakinwale/Downloads/roadmap.md`
- `/Users/emmanuelakinwale/Downloads/shared_planner_team_calendar_e_2_e_runbook.md`

If code, tests, or UI behavior diverge from those documents:

1. stop and identify the mismatch explicitly
2. decide whether the code or the document is wrong
3. update both the implementation and the source of truth before calling the work done

Do not treat these docs as optional reading after implementation. They are acceptance criteria.

## Required Delivery Process For Any Feature Touching 2+ Modules

Before implementation:

1. Build an acceptance matrix from the relevant roadmap, runbook, issue, or spec.
2. List every entry point that can create, edit, delete, sync, or display the same domain object.
3. Identify the canonical source of truth for that domain object.
4. Write down the invariants that must survive create, edit, reconnect, disconnect, cancel, retry, and delete flows.

During implementation:

1. Update all affected routes and flows, not just the new or most obvious one.
2. Preserve explicit user intent. Defaults are allowed only when the user has not chosen.
3. Fail closed when authorization, sync targeting, or ownership is ambiguous.
4. Do not silently coerce invalid or unsupported behavior into a different behavior.

Before sign-off:

1. Run the hostile review checklist in this file.
2. Verify behavior against the acceptance matrix.
3. Verify old and new entry points behave consistently.
4. Do not call the work complete based only on type checks, unit tests, or happy-path UI checks.

## Route And Flow Parity Rule

Never implement a domain rule in only one route family.

If a feature touches a domain object that is reachable from multiple surfaces, you must inventory and reconcile all of them. Examples:

- admin planner routes
- couple portal routes
- callback routes
- background sync flows
- retry flows
- disconnect or delete flows
- edit forms and create forms

For every new rule, answer these questions before merging:

1. Where else can this same entity be created?
2. Where else can it be edited?
3. Where else can it be cancelled or deleted?
4. Where else can permissions be bypassed?
5. Where else can stale state survive?

If you cannot answer all five, you are not done investigating.

## Authorization And Tenant Boundary Rule

Role checks are not enough.

Every read and mutation must verify both:

1. the actor has the required permission
2. the target resource belongs to the actor's owner scope or explicitly allowed scope

Never assume a planner, team member, or admin can act on a resource just because they have a broad role. Resource ownership must be checked at the document level.

For any multi-tenant or owner-scoped domain:

- mutation endpoints must verify owner scope
- background jobs must verify owner scope
- reconnect, disconnect, retry, and healthcheck flows must verify owner scope
- IDs from the client are never trusted without owner-scope verification

## Source Of Truth Rule

Every feature must declare its source of truth before implementation.

For shared planner calendar v1:

- `planner_tasks` is the canonical schedule-item store
- meetings are `schedule_item_type="meeting"` records inside `planner_tasks`
- external calendars are projections of internal meetings, not the source of truth

If a provider disconnects, reconnects, errors, or diverges:

- internal data stays authoritative
- child sync records reflect the provider state
- the system must not guess a new external target silently

## Explicit Intent And Safe Fallback Rule

Do not overwrite explicit user choices with inferred defaults.

Priority order:

1. explicit user selection
2. documented default behavior when nothing was selected
3. safe internal-only fallback

Never introduce a "helpful" fallback that changes user intent.

If no permitted external target exists:

- create or keep the internal record
- mark external sync as not configured or equivalent
- surface the condition clearly
- do not guess based on actor email, previous state, or any other implicit shortcut

## Edit-Flow Persistence Rule

Create flow and edit flow must round-trip the same state.

If a value can be set on create, verify all of the following:

1. it is returned by the API
2. it is loaded into edit UI state
3. it survives edit-save without being silently cleared
4. disabling it explicitly clears it intentionally
5. leaving it untouched preserves the existing value

This is mandatory for:

- explicit sync targets
- override flags
- privacy and visibility modes
- invite modes
- connection sharing settings
- default-write-target settings

## Lifecycle Integrity Rule

For any connected provider or child-record architecture, implementation is incomplete unless lifecycle behavior is handled across:

- connect
- callback
- refresh
- reconnect
- healthcheck
- disconnect
- retry
- cancel
- delete

At minimum:

- disconnect must clean up or orphan dependent records safely
- reconnect must preserve owner-managed settings unless the user explicitly changed them
- delete or cancel must propagate to all child mappings that still exist
- stale child records must not keep calling deleted parents

## Time And Timezone Rule

Never serialize local wall-clock input as UTC by appending `Z`.

For scheduling features:

- preserve the selected IANA timezone
- attach timezone to naive user-entered values at the backend boundary
- store and transmit a semantically correct instant
- test all-day, date-only, naive, and aware datetime cases
- verify display round-trips in the event timezone, not only the browser timezone

No scheduling work is complete until timezone semantics have been tested end-to-end.

## Permissions Rule

New domain permissions must be enforced everywhere the action can happen.

Do not add a new permission family in one route and leave older routes on legacy permission checks.

When adding a permission such as calendar scheduling, invite sending, or connection management:

1. update the role model
2. update route dependencies
3. update legacy endpoints that hit the same domain
4. update UI gating
5. add negative tests proving unauthorized users are blocked

## Centralized Constants And Enums Rule

Domain string literals must live in a single canonical module, never scattered across services as ad-hoc strings.

This applies to:

- user roles (`team_member`, `wedding_planner`, `advertising_vendor`, etc.)
- registration sources (`public_signup`, `invite`, etc.)
- subscription statuses (already centralized in `app/models/subscription.py` — follow that pattern)
- HTTP status codes used as business signals (e.g. 402-as-billing-block)

Rules:

1. New role or status names land in a constants module (`app/constants/roles.py`, `app/models/subscription.py`, etc.) before they are referenced anywhere else.
2. Predicate helpers (e.g. `is_planner_billing_role`, `is_team_member`) live alongside the constants and are the only thing services should call.
3. Direct string comparisons against role or status values in service code are a code smell and require justification in review.
4. Typo drift on a string literal must be impossible — a typo on an enum import is a `NameError` at startup; a typo on `"team_members"` (plural) silently bypasses an authorization gate.

Status as of 2026-04-21: role checks are still partially scattered. `app/services/auth_service.py` references `"team_member"` (line 83), `"public_signup"` (line 54), and `"advertising_vendor"` (line 161) as bare strings. The good pattern lives at `app/utils/planner_billing_scope.is_planner_billing_role`, and is also followed by `app/utils/messaging_roles.py` for the `couple_messages.sender_role` field. Migration is open tech debt — do not introduce new role-string callsites; fold existing ones into the constants module as you touch surrounding code.

## Regression And Bug-Title Convention

Regression and bug-fix titles describe the *behavior* being fixed, not the environment that exposed it.

- bad: `Fix Staging Timezone Bug`
- good: `Fix Timezone Shift In Shared Calendar`

Staging-only or prod-only framing in a title misleads reviewers into thinking the fix is environment-scoped, when it almost always lands in shared code paths. Reserve environment qualifiers for *symptoms* documented in the body, not for titles.

## Testing Gate

Static checks are necessary, not sufficient.

No multi-module feature is done until coverage exists for:

- authorization boundary failures
- owner-scope or tenant-scope failures
- create/edit parity
- reconnect/disconnect lifecycle
- delete or cancel propagation
- timezone correctness
- privacy and visibility behavior
- explicit user intent preservation
- public/help/legal surface accuracy when applicable

For shared planner calendar work, the E2E runbook is the minimum scenario list, not a nice-to-have.

Live end-to-end lifecycle and contract drivers (real Mongo plus Stripe test clocks / webhooks when applicable) live under `testbed/` — not `scripts/`. See `testbed/README.md` for the directory contract and driver list. `scripts/` is reserved for deploy, bootstrap, and seed utilities.

## Repo Command Canon

Prefer the repo's documented commands over ad-hoc equivalents.

- Frontend dependency workflow is `npm`-only. `package-lock.json` is the canonical lockfile.
- Fresh or repaired frontend installs use `npm ci` and then `npm run deps:doctor`.
- If `scripts/ensure-deps.mjs` reports dependency drift or missing local binaries, recover with `rm -rf node_modules`, `npm ci`, then `npm run deps:doctor`.
- If you intentionally change frontend dependencies, use `npm install` and commit the updated `package-lock.json`.
- CI-aligned frontend verification is `npm run lint`, `npm run type-check`, `npm test`, and `npm run build`.
- CI-aligned backend verification is `ruff check app/`, `ruff format --check app/`, `pytest tests/backend/test_app_boot_smoke.py -v --tb=short`, and `pytest tests/backend/ tests/test_id_utils.py -v --tb=short`.
- Full-stack integration verification uses `docker compose -f docker-compose.test.yml up -d --build --wait`, then `pytest tests/integration/ -v --tb=short -x`, then `docker compose -f docker-compose.test.yml down -v`.
- For manual browser runbooks without the harness, local start commands are `uvicorn app.main:app --reload --port 8000` and `npm run dev`.
- For live lifecycle or contract verification, prefer the tmux-backed harness: `python testbed/testbed.py up`, `python testbed/testbed.py up --with-frontend`, `python testbed/testbed.py seed`, `python testbed/testbed.py status`, `python testbed/testbed.py attach`, `python testbed/testbed.py doctor`, and `python testbed/testbed.py down`.
- Drivers in `testbed/` stay paired with cleanup scripts, and unattended runs use `TESTBED_NON_INTERACTIVE=1` when the driver supports it.

## Required Adversarial Review Before Completion

Before saying "implemented", review the diff as if you hate it and want to break it.

You must ask:

1. Can one tenant mutate another tenant's resource?
2. Can an old route bypass the new rule?
3. Can edit-save silently erase state set during create?
4. Can reconnect reset user-managed settings?
5. Can disconnect leave child records pointing at deleted parents?
6. Can timezone handling shift the meeting time incorrectly?
7. Can the UI display one thing while the backend persists another?
8. Did a convenience fallback violate an explicit business rule?
9. Are the docs, UI copy, and actual behavior aligned?

If any answer is "maybe", the work is not ready to close.

## Completion Standard

Do not claim completion because:

- mypy passes
- pytest passes
- TypeScript compiles
- the happy path works once in the browser

Claim completion only when:

1. the acceptance matrix is satisfied
2. route parity has been checked
3. owner-scope authorization has been checked
4. lifecycle cleanup has been checked
5. edit-state persistence has been checked
6. timezone semantics have been checked
7. hostile review has been performed

## Known Open Issues — Auth, Session, And 402 Handling Cluster

This cluster is load-bearing context for any work on `app/services/auth_service.py`, `app/dependencies/auth_extended.py`, `app/utils/auth_utils.py`, `proxy.ts`, `app/contexts/AdminContext.tsx`, or anything that throws or catches 402. Update this list when you close items or discover new ones.

As of 2026-04-26, the following are open:

1. **Middleware converts 422 to 500.** The security error handler crashes with `TypeError: Object of type bytes is not JSON serializable` when serializing the raw request body during a FastAPI `RequestValidationError`. Any legitimate validation error is returned to callers as a 500, masking the real feedback.
2. ~~**`AdminContext.login` throws raw `Error` on 402.**~~ **CLOSED 2026-04-26.** Fix expanded the original 402-only special case to cover all non-2xx login responses. Any HTTP-level failure (401, 402, 403, 429, etc.) now sets `isExpectedHttpError=true`; the catch block keys off either `isExpectedHttpError` or the legacy `isAuthBlock` flag and skips the `console.error("Login flow threw: ...")` + duplicate toast. Only true `fetch` rejections (CORS, DNS, backend down) still land in the diagnostic branch. Live-verified — 3× 401 returned, 0× console noise.
3. **Two frontend services bypass `AdminContext.apiRequest` on 402.**
   - `app/services/behavioralAnalyticsApi.ts:186` — `throw new Error(body?.detail || 'Failed to fetch engagement signals')`
   - `app/services/campaignAdvertisingApi.ts:477` — `throw new Error(error.detail?.message || error.detail || errorPrefix)`
   Both paths bypass the centralized 402-as-billing-block branch in `AdminContext.apiRequest`, so a planner whose subscription flips to blocked mid-session will not be logged out through these call sites.
4. **Billing-block state is fragmented across four layers.** `AdminRouteGuard.tsx` (preemptive, `router.replace`), `AdminContext.login` post-login branches (`router.replace` + toast + state commit), `checkSubscriptionStatus` polling (silent → triggers Layer 1), and `adminApiAuthGuard.redirectOnBillingBlock` (reactive, `window.location.href`) each independently decide what "billing-blocked" means and how to navigate. The `router.replace` vs `window.location.href` split is currently deliberate (preserve in-memory state when the profile is fresh; force hard nav when it is stale), but the policy lives in four places. **Pre-prod blocker.** Plan: expose a derived `billingBlockTarget` state on `AdminContext`, have all four layers consume it, and centralize the navigation strategy. This is a refactor — must not be bundled with reactive bug fixes (items 2/3). Ticket: task #20.

## Changelog Discipline

For significant changes, add a concise entry to `CHANGELOG.md` that records:

- what changed
- what risk or bug class it addressed
- any follow-up gaps that still remain

Do not use the changelog as marketing copy. Use it as engineering memory.

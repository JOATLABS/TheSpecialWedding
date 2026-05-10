# Billing Stabilization Status

**Date:** 2026-05-10
**Goal:** Make The Special Wedding billing behavior explicit, boring, and production-safe before the next marketing push.

## Scope

This stabilization covers:

1. Metering, subscription plan seeding, Stripe plan sync, subscription snapshots, public pricing, and root-admin plan editing.
2. Frontend 402-as-billing-block handling for behavioral analytics and campaign advertising service paths.

Live Stripe or production Mongo verification is out of scope for this local pass unless an operator explicitly configures and runs the testbed drivers.

## Accepted Product Decision

Path A is accepted: canonical public plans are intentionally **metered per active wedding**.

Boutique, Signature, and Enterprise seed with `billing_model="metered"`, `is_metered=True`, and `meter_event_name="wedding_active"`. Seed owns the billing model and Meter shape; root-admin plan management owns mutable pricing, limits, feature flags, public feature highlights, and public visibility after a plan exists. Existing flat Stripe subscriptions are not silently migrated by a local plan flip; billing-model transitions remain blocked while active subscriptions exist unless `TSW_ALLOW_PLAN_BILLING_MODEL_MIGRATION=true` is set for an explicit operator migration run.

## Acceptance Matrix

| A. Metering / plan / Stripe behavior | B. 402 frontend billing-block behavior |
| --- | --- |
| Source of truth for canonical public plan billing shape is `scripts/seed_subscription_plans.py`, mirrored by `/system/seed-default-plans`; root admin owns mutable price/features/visibility after creation. | Source of truth for protected admin API calls is `AdminContext.apiRequest`, because it has user-profile context for planner vs. team-member 402 handling. |
| Current production billing model is metered monthly/yearly pricing per active wedding using the `wedding_active` Stripe Meter. | Planner 402 must hard-redirect to `/admin/planner/billing`. |
| Canonical public plans Boutique, Signature, and Enterprise declare `billing_model="metered"`, `is_metered=True`, and `meter_event_name="wedding_active"`. | Team-member 402 must log out and redirect to `/admin/login?error=<backend reason>`. |
| Stripe Product/Price/Meter sync is seed-driven and admin-driven; both paths validate or provision the Stripe Meter before creating metered Prices. | `redirectOnBillingBlock(response)` is planner-only and cannot replace `apiRequest` for team-member-aware calls. |
| Root admin can change plan pricing, limits, active/featured state, feature flags, and public feature highlights without dropping seeded fields or being overwritten by redeploy seed. | Protected behavioral analytics calls now use injected `apiRequest`. |
| Billing-model flips while active subscriptions exist are blocked unless `TSW_ALLOW_PLAN_BILLING_MODEL_MIGRATION=true`. | Protected campaign advertising admin/planner calls now use injected `apiRequest`. |
| Existing Stripe subscriptions do not migrate just because a local plan changes billing model; subscription-item migration remains an operator task. | Vendor portal advertising calls keep vendor auth and raw fetch because they are not AdminContext admin-session surfaces. |
| New plan snapshots include `billing_model`, `is_metered`, `meter_event_name`, and `meter_id` for grandfathering. | Couple portal behavioral helpers keep couple-auth raw fetch because they are not AdminContext admin-session surfaces. |
| `/billing/sync-usage` exists as a manual root-admin endpoint; no scheduler wiring was found in the repo. | `apiRequest` returning `undefined` is treated as navigation/logout already handled, not as a UI load error. |

## Metering Active / Guarded Matrix

| Path | Status now | Notes |
| --- | --- | --- |
| Canonical seed plans | Active metered | `plan_boutique`, `plan_signature`, and `plan_enterprise` seed `wedding_active`. |
| Stripe Meter provisioning | Active where Stripe seed/sync runs | Seed uses `ensure_stripe_meter`; admin sync resolves/validates meter shape. |
| Metered Stripe Price sync | Active and fail-closed | Missing or invalid Stripe Meter blocks sync instead of creating flat Prices. |
| Wedding create/delete MeterEvent calls | Active for metered subscriptions | Runs only when the subscribed plan is metered and has `meter_event_name`. |
| Daily usage sync | Manual | Root-admin endpoint exists; production cron/scheduler wiring was not found. |
| Retry pending meter events | Manual | Root-admin endpoint exists for `meter_pending` recovery. |
| Flat-to-metered migration | Guarded | Required for existing flat subscribers; blocked without `TSW_ALLOW_PLAN_BILLING_MODEL_MIGRATION=true`. |

## 402 Caller Inventory

### Behavioral Analytics

| Function | Callers | Surface | Transport decision |
| --- | --- | --- | --- |
| `fetchBehavioralAnalytics` | `app/admin/saas/page.tsx` | Root-admin SaaS analytics | Uses `apiRequest`. |
| `fetchEngagementSignals` | `app/admin/planner/page.tsx` | Planner/team-member dashboard | Uses `apiRequest`. |
| `fetchNonResponders` | No current in-repo caller | Admin/planner helper | Requires `apiRequest` when used. |
| `fetchBudgetBreakdown` | No current in-repo caller | Admin/planner helper | Requires `apiRequest` when used. |
| `fetchCoupleNonResponders` | None currently; couple dashboard has inline equivalent | Couple portal | Keeps couple-auth raw fetch. |
| `fetchCoupleBudgetBreakdown` | None currently; couple dashboard has inline equivalent | Couple portal | Keeps couple-auth raw fetch. |

### Campaign Advertising

| Family | Callers | Surface | Transport decision |
| --- | --- | --- | --- |
| `/portal/ads/*` vendor campaign, creative, lead, billing helpers | `app/portal/ads/**` | Vendor portal | Keeps vendor token raw fetch. |
| Admin review/campaign/revenue/config/free-tier/vendor-account helpers | `app/admin/ads/page.tsx`, `app/admin/saas/page.tsx` | Root-admin console | Uses `apiRequest`. |
| Planner sponsored cards, directory add, quote request, quote draft, ad preferences | `app/admin/vendors/components/*` | Planner/team-member admin | Uses `apiRequest`. |

## Code Changes Made

- Made `app/constants/billing.py` declare canonical public billing as metered with the `wedding_active` event.
- Updated seed and `/system/seed-default-plans` so canonical public plans seed metered.
- Changed seed ownership so it enforces billing model/Meter fields but preserves existing root-admin pricing, limits, features, highlights, and visibility.
- Added seed-side transition protection so active flat subscribers cannot be silently stranded on old Stripe Prices during a redeploy.
- Made Stripe seed fail closed if a metered plan cannot provision or validate a Stripe Meter before Price creation.
- Let root admin create and edit metered plans by default while retaining `meter_event_name` validation and active-subscription billing-model transition guards.
- Exposed `billing_model` and `is_metered` in public pricing DTOs so public/signup/planner billing surfaces render the metered unit honestly.
- Added a root-admin feature configuration helper so seeded feature flags and future unknown flags are preserved instead of being dropped by the modal.
- Added editable public feature highlights, yearly price, guests-per-wedding, staff seats, active/featured state, and display order to the plan editor payload.
- Soft-archived canonical plan deletes so root-admin removal hides the plan from public pricing and survives seed, while non-canonical deletions still delete when no active subscribers exist.
- Added `app/services/adminApiRequest.ts` and moved protected behavioral analytics and campaign advertising paths to injected `AdminContext.apiRequest`.
- Updated `AGENTS.md` to close the two-service 402 bypass item while leaving the broader billing-block-state refactor open.

## Tests Added Or Updated

- `tests/backend/test_billing_model_lock.py`
  - Canonical public billing model is metered.
  - Seed canonical plans declare `wedding_active` metering.
  - System Stripe sync routes through guarded subscription service.
  - New plans default to metered `wedding_active`.
  - Metered plans require `meter_event_name`.
  - Stripe Meter validation errors are preserved.
  - Billing-model flips with active subscriptions are rejected without the migration flag.
  - Root-admin price, feature, public-highlight, and visibility edits work on existing metered plans with active subscriptions.
- `tests/backend/test_metering_gating.py`
  - Seed plans are metered by default and retain Stripe MeterEvent idempotency guards.
- `tests/backend/test_plan_change_snapshot.py`
  - Snapshot writers must include `billing_model`, `is_metered`, `meter_event_name`, and `meter_id`.
- `tests/unit/saasPlanFeatureConfig.test.ts`
  - Root-admin feature config preserves seeded and future feature keys.
  - Public feature highlight textarea round-trips one line per highlight.
- `tests/unit/adminBillingApiRequest.test.ts`
  - Engagement signals and admin campaign paths use `apiRequest`.
  - Team-member 402 handling stays in `apiRequest`.
  - Vendor portal advertising paths are not forced through AdminContext.
  - Non-402 errors still surface.
  - Analytics and campaign services cannot re-import `redirectOnBillingBlock`.

## Commands Run

| Command | Result |
| --- | --- |
| `PYTHONPATH=$PWD /Users/emmanuelakinwale/Desktop/WeddingWebApp/.venv/bin/python -m pytest tests/backend/test_billing_model_lock.py tests/backend/test_metering_gating.py -v --tb=short` | Passed: 17 passed. |
| `npx tsx --test tests/unit/saasPlanFeatureConfig.test.ts` | Passed: 3 passed. |
| `npx tsx --test tests/unit/saasPlanFeatureConfig.test.ts tests/unit/adminBillingApiRequest.test.ts` | Passed: 9 passed. |
| `PYTHONPATH=$PWD /Users/emmanuelakinwale/Desktop/WeddingWebApp/.venv/bin/python -m pytest tests/backend/test_metering_hardening.py tests/backend/test_billing_model_lock.py tests/backend/test_metering_gating.py -v --tb=short` | Passed: 36 passed. |
| `PYTHONPATH=$PWD /Users/emmanuelakinwale/Desktop/WeddingWebApp/.venv/bin/python -m pytest tests/backend -k "meter or metered or subscription or stripe" -v --tb=short` | Passed: 146 passed, 1210 deselected. |
| `npm run type-check` | Passed. |
| `npm run lint` | Passed with existing warnings in `PayoutsCard.tsx` and `ssrBootProbe.ts`. |
| `npm test` | Passed: 128 passed. |
| `PYTHONPATH=$PWD /Users/emmanuelakinwale/Desktop/WeddingWebApp/.venv/bin/python -m ruff check app/` | Passed. |
| `PYTHONPATH=$PWD /Users/emmanuelakinwale/Desktop/WeddingWebApp/.venv/bin/python -m ruff format --check app/` | Passed after formatting `app/models/subscription.py`: 265 files already formatted. |
| `PYTHONPATH=$PWD /Users/emmanuelakinwale/Desktop/WeddingWebApp/.venv/bin/python -m pytest tests/backend/test_app_boot_smoke.py -v --tb=short` | Passed: 1 passed. |
| `PYTHONPATH=$PWD /Users/emmanuelakinwale/Desktop/WeddingWebApp/.venv/bin/python -m pytest tests/backend/ tests/test_id_utils.py -v --tb=short` | Failed locally: 4 `test_marketing_lead_capture.py` assertions because WeasyPrint cannot load `libpango-1.0-0`; 1376 passed, 12 skipped. |

## Live Stripe / Testbed Status

Not run locally. No live Stripe/Mongo testbed configuration was asserted for this pass, and the requested direction says not to fake live validation.

Operator command for intentional live metering verification:

```bash
TESTBED_NON_INTERACTIVE=1 python testbed/verify_metered_seed_e2e.py
```

## Hostile Billing Review

| Question | Result |
| --- | --- |
| Can a blocked planner remain on a protected admin page through these services? | No billing-specific bypass found. Protected analytics and ads calls use `apiRequest`; AdminRouteGuard still blocks render for known blocked profiles. |
| Can a blocked team member see planner-owned data through these services? | No billing-specific bypass found. Team-member 402 handling stays in `apiRequest`, which logs out to `/admin/login?error=<reason>`. |
| Can a raw fetch throw a generic 402 before billing handling? | Not in the migrated services. Remaining raw 402 paths are intentional: AI credits on planner insights and Quick Remind's inline mirror of `apiRequest`. |
| Can a canonical metered plan become half-configured? | Guarded: metered plans require `meter_event_name`, Stripe sync validates the Meter, and seed refuses to create flat Prices for metered plans. |
| Can existing Stripe subscriptions remain flat while the local plan says metered? | Yes if the live system already has flat subscription items; the transition is blocked while active subscriptions exist unless `TSW_ALLOW_PLAN_BILLING_MODEL_MIGRATION=true` is set for an explicit migration. |
| Can seed overwrite admin changes silently? | Billing model/Meter fields are enforced by seed. Root-admin mutable pricing/features/visibility are preserved for existing plans, and canonical deletes soft-archive instead of being recreated. |
| Can plan snapshots lose billing model data needed for grandfathering? | New snapshot writers are guarded by tests and include billing model fields. Historical old snapshots may still need backfill. |
| Can Stripe meter events fire but Mongo fail to mark them billed? | Existing metering hardening retries and marks `meter_pending`; cron/scheduler coverage is still a required deployment follow-up. |
| Can a live deploy create duplicate Stripe products/meters? | Meter creation has deterministic idempotency; Stripe Product search eventual consistency remains an open follow-up from the metering gap doc. |
| Do docs and AGENTS.md match the actual code? | This file, `METERING_AUDIT.md`, `CHANGELOG.md`, and AGENTS item 3 now align after the metering pivot. AGENTS item 4 remains open. |

## Unresolved Risks

- Live Mongo may already contain active flat subscription items; those need an explicit Stripe subscription-item migration before relying on metered billing for those customers.
- `/billing/sync-usage` has no repo-managed cron or scheduler.
- Existing historical subscriptions may lack the new billing-model snapshot fields until they are resynced or repaired.
- The metering implementation still has open audit risks from `docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md`, including negative usage reversal policy and Stripe Product search eventual consistency.
- Billing-block navigation policy remains fragmented across `AdminRouteGuard`, `AdminContext.login`, subscription polling, and `redirectOnBillingBlock`.
- Full backend local validation has previously been blocked by missing native WeasyPrint dependency `libpango-1.0-0`; rerun status is recorded above.

## Follow-Up Tickets

1. Write the subscription-item migration runbook and operator command for any existing flat Stripe subscribers.
2. Decide whether meter delete reversals should use Stripe MeterEventAdjustment instead of negative `value="-1"` events.
3. Add scheduled production wiring for `/billing/sync-usage`.
4. Replace Stripe Product search dependency in seed/sync with a more deterministic lookup strategy.
5. Backfill or repair billing-model snapshot fields on old active subscriptions.
6. Complete AGENTS.md item 4: centralize billing-block target/navigation state.
7. Fix local/CI native dependencies for WeasyPrint-backed marketing lead capture tests if they continue failing.

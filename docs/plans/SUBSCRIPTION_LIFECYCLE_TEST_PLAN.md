# Subscription Lifecycle Test Plan

**Status:** Draft for review — no code yet
**Pattern:** Stripe Test Clock scripts in the shape of `testbed/verify_team_member_gate_via_test_clock.py`, paired with Claude-in-Chrome checkpoints per `CLAUDE.md` → "E2E verification" (both layers must agree before a scenario is considered verified).
**Anchor date:** 2026-04-21

---

## 1. Goals

Verify planner-facing subscription lifecycle behavior end-to-end, using real Stripe webhooks and real test-clock time travel, with the same discipline the team-member gate verification already demonstrates:

1. **Trial lifecycle** — what the system does across the 30-day trial, the 7-day warning window, and the trial-end boundary.
2. **Active monthly subscription lifecycle** — what the planner sees and what the system enforces across wedding count (0 / 1 / 2+), AI credit consumption, cancellation, and plan up/downgrade.
3. **Metering scoping clarification** — explicit assertion that today's canonical public plans are metered on `wedding_active`, matching the state described in `METERING_AUDIT.md`.

Non-goals for this round: vendor billing, ad billing, team-member seats beyond the already-verified gate, couple-portal flows.

---

## 2. Prerequisites and reusable pieces

Already in repo, reuse as-is:

- `testbed/verify_team_member_gate_via_test_clock.py` — reference template for phase structure, pause-on-ENTER checkpointing, Stripe clock re-use, Mongo linking, PM swap, webhook settle wait.
- `testbed/test_trial_with_test_clock.py` — existing trial driver, 584 lines. Good bones for webhook phase verification but predates the PR1 gate conventions (no explicit per-checkpoint Chrome pause, no identity isolation via `+tag@` emails). Will be **wrapped**, not replaced.
- `testbed/cleanup_team_member_gate_verify_state.py` — reset script shape to mirror for each new scenario.
- `scripts/seed_subscription_plans.py` — plans reference: Boutique (`max_weddings=3`, `ai_credits_monthly=100`), Signature (`max_weddings=10`, `ai_credits_monthly=300`), Enterprise (`max_weddings=-1`, `ai_credits_monthly=1000`). All canonical plans seed `is_metered=True` with `meter_event_name="wedding_active"`.
- `app/utils/subscription_decorators.py` — `enforce_subscription_limit(resource_type, amount)` raises **402** when exceeded; `check_feature_access(feature_name)` raises **402** when feature not in plan. These are the gate points the tests need to exercise, not the UI banners.
- `app/services/subscription_service.py::check_usage_limits` (lines 652–723) — authoritative limit logic. Reads `plan_snapshot` first (grandfathered limits), falls back to current plan. Tests must confirm both paths.
- `app/services/trial_expiration_service.py` — batch job that stamps `subscription_status="expired"` on users whose `trial_end_date < now`. Triggered via internal endpoint/cron, not Stripe webhook.
- `METERING_AUDIT.md` — authoritative source for "what metering actually does today." Metered-plan tests must verify a Stripe Meter resource, prices with `usage_type="metered"`, and explicit migration handling for any existing flat Stripe subscription items.

Identities to provision in `staging` GitHub environment (currently only planner + couple smokes exist — see `CLAUDE.md` → "Deployment follow-ups"):

- `test_planner+trial@thespecialwedding.io` — fresh 30-day trial clock account.
- `test_planner+billing@thespecialwedding.io` — active paying planner, Boutique plan.
- `test_planner+signature@thespecialwedding.io` — active paying planner, Signature plan (metering-ready if/when metering is enabled).
- `test_planner+downgrade@thespecialwedding.io` — paying planner used for upgrade/downgrade scenarios.

Each gets its own Stripe test-clock id, persisted in the script header so reruns share state like `clock_1TNGs4JbfaNLE8qUOMEjk2ZU` does for the team-member gate.

---

## 3. Test matrix

Legend for columns: **Auto** = scripted test-clock driver. **Chrome** = live Claude-in-Chrome verification with user watching. **Unit** = pytest-level. **Int** = backend integration (FastAPI TestClient + Stripe mocked or captured).

### 3.1 Scenario A — 30-day trial lifecycle

| # | Checkpoint | What's asserted | Auto | Chrome | Unit | Int |
|---|---|---|---|---|---|---|
| A0 | Fresh planner signs up on a test clock, subscription state = `trial`, `trial_end_date = now + 30d` | `users.subscription_status=="trial"`, `user_subscriptions.status=="trial"`, `plan_snapshot` stored | ✓ | ✓ | — | ✓ |
| A1 | Trial user creates 1 wedding successfully | `/admin/weddings` POST returns 200, `usage.weddings_count==1` | ✓ | ✓ | — | — |
| A2 | Trial user hits plan wedding cap (Boutique: 4th create) | POST returns **402** with `Wedding limit exceeded` | ✓ | ✓ | ✓ | ✓ |
| A3 | Trial user consumes AI credits up to and past the monthly cap | AI endpoint returns **402** on the request that crosses `ai_credits_monthly`; `check_credits` (`app/services/ai_service.py:930`) matches | ✓ | ✓ | ✓ | — |
| A4 | Clock advance to `trial_end - 7d` → trial warning webhook/email | Stripe webhook fires, email sent, UI banner shows "trial ending" | ✓ | ✓ | — | ✓ |
| A5 | Clock advance past `trial_end`, trial-maintenance job runs | `subscription_status` flips to `expired`, `is_active` stays `True` (see `trial_expiration_service.py:57-61` — users can still log in to upgrade) | ✓ | ✓ | ✓ | — |
| A6 | Expired trial user tries to create a 2nd wedding | POST returns **402** (no active subscription); login still succeeds; `/admin/billing` accessible; `/admin/planner` redirects per PR1 `isAllowedForExpired` guard | ✓ | ✓ | ✓ | ✓ |
| A7 | Expired trial user adds PM + subscribes | Status transitions expired → active; webhook settles; limits refresh from new plan snapshot | ✓ | ✓ | — | ✓ |

Chrome-observed UX-only checkpoints (not scripted):

- Banner copy + dismissibility on A4, A5, A6.
- `/admin/planner/billing` renders the Stripe portal link + plan-select grid correctly.
- No console noise on A5 redirect (PR1 item 4 regression guard).

### 3.2 Scenario B — Active monthly subscription, wedding metering by count

All three sub-matrices are run against **Boutique** (`max_weddings=3`) as the canonical cap. Signature and Enterprise get a smaller smoke subset (B1 + B5 only) because their cap behavior is the same code path with different numbers.

**B.0 — Zero weddings**

| # | Checkpoint | Asserts |
|---|---|---|
| B0.1 | Subscribe, never create a wedding. `/admin/planner` renders empty-state. | `usage.weddings_count==0`, dashboard shows empty-state, no 402 anywhere. |
| B0.2 | First renewal tick of the clock | Stripe `invoice.paid` webhook, `user_subscriptions.current_period_start/end` roll forward, `ai_credits_used_month` resets to 0 (`reset_monthly_usage`), `weddings_count` is **preserved** (see `subscription_service.py:798`). |

**B.1 — One wedding**

| # | Checkpoint | Asserts |
|---|---|---|
| B1.1 | Create wedding #1 | `usage.weddings_count==1`; canonical metered plans report `stripe.billing.MeterEvent.create` with `wedding_active` unless Stripe reporting fails and sets `meter_pending=True`. |
| B1.2 | Monthly renewal | Wedding count preserved, AI credits reset. |
| B1.3 | Delete the wedding | Cascade delete + `cascade_delete_service.py` touches `data_access_suspended_at` correctly; metered plans set `meter_reversed_period` after the reversal event. Counter decremented. |
| B1.4 | Recreate with same couple after delete | Must not double-bill in metered mode; idempotency key `wedding_create_{wedding_id}_{customer_id}_{YYYY-MM}` prevents duplicates (per `METERING_AUDIT.md` 2.4). Recreate-in-same-period test only meaningful when `is_metered=True` — scoped to Scenario D. |

**B.2 — Two weddings under cap (Boutique allows 3)**

| # | Checkpoint | Asserts |
|---|---|---|
| B2.1 | Create wedding #2 | `weddings_count==2`, no 402. |
| B2.2 | Create wedding #3 | `weddings_count==3`, no 402, AI-credit gate still independent of wedding gate. |
| B2.3 | Create wedding #4 | **402** with `Wedding limit exceeded. Plan allows 3 weddings, you have 3`. Message must match `subscription_service.py:687` verbatim so frontend regex stays valid. |

### 3.3 Scenario C — AI credits gate (independent from wedding gate)

| # | Checkpoint | Asserts |
|---|---|---|
| C1 | Consume credits up to `ai_credits_monthly - 1` | All AI endpoints return 200, response includes `credits_used`, `remaining`. |
| C2 | Final credit request | 200, `remaining==0`. |
| C3 | One more request | **402** `AI credits limit exceeded…`. Gate raised by `subscription_service.check_usage_limits("ai_credits")` path, not by AI service alone. |
| C4 | Clock advances past renewal | `ai_credits_used_month` resets to 0 inside `reset_monthly_usage`; next AI request succeeds. |
| C5 | Downgrade mid-month from Signature (300) → Boutique (100) while `ai_credits_used_month==150` | The plan-snapshot grandfather rule: does the active-period limit snap to the old or new value? Expected per `check_usage_limits` that `plan_snapshot` is authoritative for the current period — test pins behavior. **Open question if snapshot is not updated on downgrade.** |

### 3.4 Scenario D — Plan change + cancellation

| # | Checkpoint | Asserts |
|---|---|---|
| D1 | Upgrade Boutique → Signature mid-cycle | Stripe proration invoice fires; `plan_snapshot` updated; `max_weddings` jumps 3 → 10; existing 3 weddings unaffected. |
| D2 | Downgrade Signature → Boutique while `weddings_count > new_cap` | Open question: does the system **block the downgrade**, allow but freeze creates, or quietly accept? Test pins actual behavior. Likely gap. |
| D3 | Cancel subscription at period end | `user_subscriptions.cancel_at_period_end=True`, status stays `active` until period end, planner retains access. |
| D4 | Clock advances past period end after cancel | Webhook fires, status → `canceled`, `users.subscription_status="cancelled"`, `is_active=False` (`subscription_service.py:458`). Login returns 402 or redirects to billing — **test must pin which**, since PR1 `isAllowedForExpired` guard covers `expired` but the canceled path may differ. Likely gap. |
| D5 | Resubscribe from canceled state | New subscription row, new `plan_snapshot`, usage counters reset. |
| D6 | Past-due → recovery (mirror PR1 pattern exactly) | PM swap to 4000-0341 → clock past renewal → 402 on planner login → PM swap back → clock advance → 402 clears. This duplicates the team-member verify for the planner identity specifically. |

### 3.5 Scenario E — Metering on (conditional)

Only run when at least one plan is provisioned with `is_metered=True` + `meter_event_name` + a Stripe Meter resource. Per `METERING_AUDIT.md`, **today's seed does not enable this.** The test script must assert that state at startup and skip if metering is off, rather than silently misbehave.

| # | Checkpoint | Asserts |
|---|---|---|
| E1 | Metering-enabled plan, create wedding | `stripe.billing.MeterEvent.create` called exactly once, `value="1"`, idempotency key matches the documented format. `weddings.last_billed_at` set. |
| E2 | Create same-month second wedding | Second meter event with distinct id. |
| E3 | Delete a wedding | `value="-1"` meter reversal call, `meter_reversed_period` set. |
| E4 | Retry a `meter_pending=True` wedding via `/admin/weddings/{id}/retry-meter` | Success clears `meter_pending`. |
| E5 | Wedding create with Stripe API unreachable | `meter_pending=True` with a reason string, admin badge renders. |

---

## 4. Script layout

Mirror the team-member gate verifier. One driver per scenario, each pairable with its own cleanup. All live-lifecycle drivers live under `testbed/` (see `testbed/README.md` and `CLAUDE.md` → E2E verification); `scripts/` stays reserved for deploy, bootstrap, and seed utilities.

```
testbed/
  verify_team_member_gate_via_test_clock.py   (existing, reference)
  cleanup_team_member_gate_verify_state.py    (existing, reference)
  verify_planner_trial_lifecycle.py           (existing — Scenario A)
  cleanup_planner_trial_verify_state.py       (existing)
  verify_planner_active_lifecycle.py          (NEW — Scenarios B, C, D)
  cleanup_planner_active_verify_state.py      (NEW)
  verify_planner_metered_lifecycle.py         (NEW — Scenario E, skipped by default)
  cleanup_planner_metered_verify_state.py     (NEW)
```

Drivers assume a local backend + Stripe webhook forwarder are up. Use the `testbed/testbed.py` CLI (`up` / `seed` / `preflight`) to bring those services up instead of hand-starting uvicorn and `stripe listen` per run.

Each driver inherits the template's conventions verbatim:

- Per-phase pauses that wait on explicit ENTER before advancing.
- Stripe clock id pinned in the module header; re-used across runs.
- `+tag@` email identities so the base QA accounts are never touched.
- Mongo linking in the same shape (`stripe_customers` upsert, invite-token lookup when relevant).
- Hard guard-rail at startup for missing env (`STRIPE_SECRET_KEY`, `MONGO_URI`, `ROOT_ADMIN_PASSWORD`).
- Phase names in CAPS so grep against logs stays legible: `SEED`, `TRIAL_CREATE`, `TRIAL_CAP`, `TRIAL_CREDIT_CAP`, `TRIAL_WARN`, `TRIAL_EXPIRE`, `TRIAL_RECOVER`, etc.

Each checkpoint that has a Chrome component must surface a clear prompt like the reference does:

```
Press ENTER once you've verified this checkpoint in Chrome
  1. /admin/weddings shows the 4th create as blocked with planner-readable copy
  2. Browser devtools shows the 402 response body includes {detail: "Wedding limit exceeded..."}
  3. No console errors after the 402 (PR1 item 4 regression guard)
```

---

## 5. Unit / integration coverage backfill

These are code-level gaps that the scripted drivers will exercise but that deserve their own fast pytest coverage too, because the scripts are slow and require a live Stripe CLI:

1. **`tests/backend/test_subscription_limits.py`** — parametrized over `(plan, resource_type, current_usage, requested_amount, expected_allowed)`. Mirrors `check_usage_limits` branches including the `plan_snapshot` fallback to current plan.
2. **`tests/backend/test_subscription_decorators.py`** — FastAPI TestClient with an endpoint decorated `@enforce_subscription_limit("weddings")`; assert 402 on exceed, 401 on missing auth, bypass for `is_root_admin`.
3. **`tests/backend/test_trial_expiration_service.py`** — mock clock to `trial_end_date + 1s`; assert status flips to `expired` and `is_active` stays `True` (enforces `trial_expiration_service.py:57-61` invariant that expired planners can still reach billing).
4. **`tests/backend/test_plan_change_snapshot.py`** — assert `plan_snapshot` is updated on upgrade, and pin the current behavior on downgrade-while-over-cap (this is the open question in D2).
5. **`tests/unit/subscriptionStatus.test.ts`** (already exists) — extend with `canceled`-state rendering so D4 frontend behavior has a fast test.
6. **`tests/backend/test_metering_gating.py`** — assert canonical seed plans remain metered on `wedding_active` and that Stripe MeterEvent idempotency behavior stays safe for retries.

---

## 6. Explicit open questions the tests will resolve

The matrix is written to **pin behavior**, not assume it. These questions should be answered by the first run, with the answer captured in the driver's commit message, the paired cleanup-PR body, or a dated entry under `docs/reports/` — not back-filled into `CLAUDE.md` (which is conventions and durable pointers only, per the scope note at the top of that file).

- **Q1** What happens to `plan_snapshot` on downgrade? Does mid-period downgrade apply new limits immediately or at period end?
- **Q2** On downgrade-over-cap (D2), is the downgrade blocked, allowed-and-locked, or silently accepted?
- **Q3** On `canceled` status after period end (D4), does the PR1 `isAllowedForExpired` guard catch canceled the same way as expired, or is there a separate gate? Open Issue #8 in `AGENTS.md` → "Known Open Issues" is the obvious landing place if they diverge.
- **Q4** AI credit gate on mid-month downgrade (C5) — does `remaining` ever go negative?
- **Q5** Does the wedding cap gate fire before or after side effects in `create_wedding`? (Important for idempotency if the endpoint retries.)
- **Q6** On D6 past-due recovery specifically for the planner identity (not team member), does the planner see a past-due banner on their own dashboard, or only at login? PR1 work only verified the team-member path; the planner's own past-due UX has not been live-verified.

---

## 7. Sequencing

Order of execution once this plan is approved:

1. **Scenario A + Scenario D trial→cancel paths** first, because they cover the largest behavior surface per script minute and hit the most open questions (Q3, Q6).
2. **Scenario B (wedding counts) + C (AI credits)** second. These are mostly additive and low-risk since the gates already exist.
3. **Unit/integration backfill** in parallel with #2 — fast tests unblock CI signal for every future change.
4. **Scenario E** only after a concrete decision to turn metering on for at least one plan. Until then it stays behind a skip.

Each scenario follows the CLAUDE.md two-layer rule: script green **and** Chrome checkpoint acknowledged before the scenario is marked verified. Either half alone is insufficient.

---

## 8. Deliverables when executing this plan

For each scenario, the final artifacts are:

- A runnable `testbed/verify_planner_<scenario>_lifecycle.py` with pinned test-clock id in the header.
- A matching `testbed/cleanup_*` script (idempotent, deletes the plus-variant Mongo chain and every Stripe customer attached to the clock — see `testbed/README.md` house rules).
- A one-paragraph entry in `CHANGELOG.md` describing what the script verifies and what behavior it pins.
- A one-line pointer in `AGENTS.md` → "E2E verification" so the script is discoverable without grep.
- Answers to the Section 6 open questions recorded in the PR body and (when load-bearing) a dated file under `docs/reports/`. Do not write per-run answers into `CLAUDE.md` — that file is for conventions, not time-bound findings.

---

## 9. What this plan deliberately does not do

- Does not add UI tests for the billing page — Playwright coverage is out of scope here and handled by `wedding-planner-dashboard.spec.ts`.
- Does not change plan definitions or enable metering by default. Any Stripe-side config changes (creating a Meter, changing prices) are gated on a separate approval per `METERING_AUDIT.md` §1.
- Does not touch the team-member gate; that is already verified end-to-end.
- Does not propose new decorators, helpers, or service refactors. If the tests surface behavior that needs centralizing (e.g., the `expired` vs `canceled` gate paths), that lands as follow-up work, not inside this test-plan scope.

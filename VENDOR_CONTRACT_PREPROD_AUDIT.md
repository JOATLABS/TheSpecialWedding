# Vendor Contract Pre-Prod Blockers — Audit (2026-05-01)

Read-only sweep of `VENDOR_CONTRACT_PREPROD_TICKETS.md` against the codebase at HEAD `55b7012` on `main`. No edits.

## Summary

| # | Ticket | Status | Headline gap |
|---|---|---|---|
| 1 | Cross-tenant write | **PARTIAL** | Helper landed correctly, but no pytest tests, no `regression_red` markers, no live Chrome — and a **parallel cross-tenant hole** exists in `contract_service.py` on the `/admin/client-contracts` surface that this ticket left untouched. |
| 2 | Dashboard aggregation | **PARTIAL** | Backend is planner-scoped and correct; UI cards have no scope copy/aria-label, no CHANGELOG entry, no live Chrome. AGENTS.md "Source Of Truth Rule" section the AC cites doesn't exist. |
| 3 | Form-data apply | **PARTIAL** | Write path is owner-scoped via `_get_owned_form_submission`, but the **read-side `get_form_data_for_contract` is NOT owner-scoped** — the UI picker can list cross-tenant submissions tied to the same vendor email. |
| 4 | Email XSS | **PARTIAL** | All 9 HTML composers escape correctly. **No driver, no XSS test, no lint rule, no Pydantic max-length on `message`, no CHANGELOG.** Frontend uses `dangerouslySetInnerHTML` on email previews — currently safe only because the backend escapes. |
| 5 | Milestone payment | **PARTIAL** | Rules 1/2/3 + AR-6 timezone + AR-7 UI all met. **AR-5 refund handling does not exist** (no handler, no schema, no field). **Parallel `contract_service.record_milestone_payment` mutates `paid_amount` directly** on `scheduled_payments`, bypassing the helper. Named driver missing. |

**Ship readiness: BLOCKED.** All five are PARTIAL. Two of them (#1 and #5) carry parallel-surface holes in `contract_service.py` that mean the AR-2 "old route bypass" gate is open for both. Refund lifecycle (#5 AR-5) is unimplemented. None of the five have live Chrome verification evidence — Definition of Done #5 fails uniformly.

---

## Ticket #1 — Cross-Tenant Write
**Overall: PARTIAL**

| AC | Status | Evidence |
|---|---|---|
| AR-1 (cross-tenant mutate) | **PARTIAL** | Driver `testbed/verify_vendor_contract_cross_tenant_isolation.py:267,279,290,302,311,322,343` covers all four endpoints with `_expect_404`. **No backend pytest** — `tests/backend/test_vendor_contract_security.py` has zero `cross_tenant` / `foreign` / `other_planner` cases. AC asks for pytest specifically. |
| AR-2 (route bypass) | **MET in scope / PARTIAL across surface** | All five target methods route through helpers: `create_contract` (`vendor_service.py:2007, :2013`), `assign_vendor_to_wedding` (`:1707, :1713`), `update_assignment_status` (`:1815` + TOCTOU re-scope at `:1831`), `upload_contract_document` (`:3952` + re-scoped update at `:3984`), `upload_contract_pdf` (`:4061, :4067`). **Out-of-scope leak:** `contract_service.py:1431` (`create_contract`) and `:135 / :140` (`_get_wedding_record`) look up `vendor_profiles` / `weddings` by `_id` only with no ownership filter. Backs `/admin/client-contracts/...` (`api/contracts.py:278-322`). Different router, same risk class. |
| AR-7 (404 not 403) | **MET** | `_get_owned_*` returns `None`; service raises `HTTPException(404, "Vendor/Wedding/Assignment/Contract not found")` (`vendor_service.py:1709, :1715, :1817, :3954, :4063, :4069, :2009, :2015`). Generic detail strings — no leak. |
| AR-8 (no convenience fallback) | **MET** | Helpers (`:683-914`) only inject `_id` + `created_by`. Root-admin bypass is explicit `actor_email=None`. Routes pass `owner_email = None if current_user.is_root_admin else current_user.email` (`vendor_management.py:262`). |
| Constants discipline | **MET** | Zero new bare-string role checks in `vendor_service.py` or `vendor_management.py`. |
| Driver red assertions | **NOT MET** | Driver covers all four scenarios but `regression_red` markers are not in the file (or anywhere in `tests/`). DoD #4 unmet. |
| Helper module location | **DEVIATION (functionally OK)** | Helpers are private methods on `VendorService` (`_get_owned_vendor_profile` etc.), not the plan's suggested `app/utils/vendor_owner_scope.py`. Functionally equivalent for #1; blocks reuse from `contract_service.py` (which is exactly the parallel-hole site above). |
| Live Chrome evidence | **NOT FOUND** | No CHANGELOG entry; no `.github/` directory; no commit message references a live verification session. |

**Open work:**
- File or fold a follow-up ticket to fix `contract_service.py:_get_wedding_record` and `create_contract:1431` (parallel `/admin/client-contracts` surface). This is the AR-2 gap for this ticket.
- Promote helpers from private `VendorService._get_owned_*` to a shared `app/utils/vendor_owner_scope.py` module so `contract_service.py` can use them without taking a `VendorService` dependency.
- Add backend pytest negative cases for the four endpoints (planner A vs planner B fixture pattern, `expect 404`).
- Register `regression_red` marker in `pytest.ini` and check in pre-fix red assertions.
- Run live Chrome checkpoint (5 scenarios in playbook); record in CHANGELOG.

---

## Ticket #2 — Dashboard Aggregation
**Overall: PARTIAL**

| AC | Status | Evidence |
|---|---|---|
| AR-1 (cross-tenant) | **MET** | `vendor_service.py:1597-1660` — vendor/contract/milestone queries inject `created_by` when not `None`. `$match` lands before `$group` (`:1644`). Covers `total_paid`, `total_due`, `pending_count`, `overdue_count`. `get_payment_milestones` filters at `:3610-3611`. (Note: AC mentions `total_overdue` but only `overdue_count` is exposed — clarify spec or add the sum.) |
| AR-2 (route bypass) | **MET** | Two production callsites: `vendor_management.py:502, :591, :605`. All pass `owner_email = None if root_admin else current_user.email`. No cron / background callers. |
| AR-7 (UI vs backend) | **NOT MET** | `app/admin/vendors/page.tsx:464-484` KPI cards have no tooltip, no aria-label, no "your team's" / planner-scoped copy. UI is silent on scope. |
| AR-9 (docs/UI/behavior) | **NOT MET** | `AGENTS.md` does not contain a "Source Of Truth Rule" section (grep returned 0 hits). The plan cites it; it doesn't exist. No `docs/` analytics doc. |
| Read-side `update_many` fix | **MET** | `vendor_service.py:3631-3643` — `update_filter` adds `created_by` when provided, before `update_many`. Inline comment cites the AGENTS.md tenant-boundary rule. |
| Driver | **PARTIAL** | `verify_dashboard_payment_aggregation_isolation.py` has CASE 1/2/3 + sanity (`:406-467`). No `regression_red` markers anywhere. |
| CHANGELOG entry | **NOT MET** | No entry naming this ticket. Inline code comment at `vendor_service.py:1594` mentions the fix but CHANGELOG is silent. |
| Live Chrome evidence | **NOT FOUND** | No PR description or commit referencing a verification session. |

**Open work:**
- Add `aria-label` (or visible sub-line) to the four KPI cards clarifying scope. Without this, AR-7 fails — backend is right but the user can't tell whether they're seeing their data or everyone's.
- Add a "Source Of Truth Rule" section to `AGENTS.md` (or extend a sibling rule) defining these dashboard metrics as planner-scoped, root-admin as explicit bypass.
- Add CHANGELOG `[Unreleased]` entry recording the cross-tenant roll-up fix and the read-side `update_many` hardening.
- Either expose `total_overdue` in `$group` to match the AC literally, or amend the ticket text to say `overdue_count`.
- Register `regression_red` marker; add a checked-in pytest with the pre-fix red assertions.
- Run live Chrome checkpoint (planner A confirms $30k breakdown; planner B sees their own; planner C sees zeros).

---

## Ticket #3 — Form-Data Apply
**Overall: PARTIAL**

| AC | Status | Evidence |
|---|---|---|
| AR-1 (cross-tenant) | **PARTIAL** | Driver `verify_form_data_apply_isolation.py:322-363` covers cross-tenant 404 + sentinel never read + sections unchanged. **No backend pytest.** |
| AR-2 (route bypass — write side) | **MET** | `apply_form_data_to_contract` routes through `_get_owned_form_submission` (`vendor_service.py:3376`) with fallback through `_get_owned_form` (`:3383`); contract gated by `get_contract(... created_by=applied_by)` at `:3356`. |
| AR-2 (route bypass — read picker) | **NOT MET** | **`get_form_data_for_contract` (`vendor_service.py:3181-3260`) queries `vendor_submissions` / `vendor_forms` by `vendor_email` only at `:3203 / :3210` with NO planner-ownership filter.** If the same vendor email exists in another planner's submissions, those rows surface in the UI picker. The mutation is gated; the read isn't. |
| AR-3 (round-trip) | **UNKNOWN** | Driver verifies the apply itself persists (`:392-408`) but does not exercise a follow-up `update_contract` / `update_contract_sections` call. No pytest covers it. |
| AR-7 (UI vs backend) | **NOT MET** | `ContractDetailPageClient.tsx:596-642` reads `formData.vendor_submissions` from the leaky read endpoint above. The UI auto-applies `vendor_submissions[0]` rather than presenting a real picker — but the backing list is leak-prone, so even the auto-apply could pull a foreign-tenant value if vendor emails collide. |
| Activity log | **PARTIAL** | `_log_contract_activity` at `vendor_service.py:3479-3496` runs after `update_one` succeeds (failure path skips). Records `source_form_submission_id` and `source_vendor_id` with fallback chain (`:3474-3478`) — fallback to `vendor_email` means `source_vendor_id` may be a string email. Driver does not assert "no activity row written" on the failed cross-tenant attempt. |
| Driver | **PARTIAL** | Three scenarios: cross-tenant, same-tenant, forged ID. **Idempotent reapply not covered.** No `regression_red` markers. |

**Open work:**
- **Tighten `get_form_data_for_contract`** (`vendor_service.py:3181`) to constrain `vendor_submissions` / `vendor_forms` by `created_by` (or join via owned `vendor_profiles`). This is the active leak.
- Replace the `vendor_submissions[0]` auto-apply in `ContractDetailPageClient.tsx:610` with an actual picker once the backend is owner-scoped.
- Add backend pytest for cross-tenant `apply_form_data_to_contract`.
- Add a driver assertion that no `form_data_applied` activity row was written on the failed cross-tenant attempt.
- Add an AR-3 round-trip scenario (apply → update_contract_sections → reload → assert).
- Register `regression_red` marker; check in pre-fix red assertions.
- Run live Chrome checkpoint.

---

## Ticket #4 — Email XSS
**Overall: PARTIAL**

| AC | Status | Evidence |
|---|---|---|
| AR-2 (every composer escapes) | **MET** | All 9 HTML composers escape: `vendor_service.py:2693, :2945, :4356`; `contract_email_service.py:215, 332, 570, 717, 886, 1026`. Both files import `html` and call `html.escape(..., quote=True)` on every interpolated user value. |
| AR-7 (UI vs backend persists) | **PARTIAL** | (a) Vendor inbox HTML — MET. (b) `ContractDetailPageClient.tsx:373, 521, 708, 711, 896, 969` uses safe React text-interpolation; no `dangerouslySetInnerHTML`. (c) Activity log render at `:936-955` — safe React. (d) **Email-preview surfaces use raw HTML rendering**: `CommunicationsInboxView.tsx:1170` `dangerouslySetInnerHTML={{ __html: selectedEmailDetail.html_body }}` and `CommunicationsRemindersView.tsx:1329` `<iframe srcDoc={emailPreviewHtml}>`. Currently safe only because the backend escapes — no defense in depth on the frontend. |
| AR-9 (docs/UI/behavior aligned) | **PARTIAL** | `vendor_name` has `min_length=1, max_length=200` (`vendor.py:211`). `contract_title` has `max_length=300` (`vendor_contracts.py:57`) — but only on UPDATE. **`SendVendorContractRequest.message` (`vendor_contracts.py:143`) has NO `max_length`.** Payment-link `description / payer_name / recipient_name / email_message / custom_message` not verified to have explicit Pydantic limits. |
| Snapshot test | **NOT MET** | Commit `19f7fbb`'s test diff is an unrelated conftest fix. No XSS-specific test exists in `tests/backend/`. The only escape test (`test_planner_onboarding_email_service.py:434-461`) is a different surface. |
| Lint rule | **NOT MET** | `.pre-commit-config.yaml` runs bandit/ruff/detect-secrets — none target f-string HTML. No grep-based test. New unescaped composers can land without signal. |
| Driver | **NOT MET** | `testbed/verify_vendor_email_xss_escaping.py` does not exist. |
| Commit 19f7fbb scope | **PARTIAL** | Touched only `vendor_service.py` (3 composers) + an unrelated test fix. Did not touch `contract_email_service.py` (escaped in a separate commit), did not touch frontend, did not add an XSS test. |
| CHANGELOG entry | **NOT MET** | No entry; the only XSS mention (line 2266) is unrelated. |

**Open work:**
- Build `testbed/verify_vendor_email_xss_escaping.py` — seed planner with `<script>`, `<img onerror>`, `javascript:` payloads in `vendor_name`, `contract_title`, `message`. Capture mocked Resend HTML; assert via BeautifulSoup zero `<script>` / zero `on*` / zero `javascript:` href. Cover both `send_contract` and `send_payment_link`.
- Add backend snapshot test against vendor_service composers AND every method in `contract_email_service.py`.
- Add `max_length` to `SendVendorContractRequest.message` and the payment-link send fields.
- Add a grep-based test (or a custom ruff rule) that fails when any new email-module composer introduces an `f"...<...{var}..."` HTML pattern that doesn't reference a `safe_*` value.
- Add CHANGELOG entry covering vendor_service + contract_email_service + open follow-up gaps.
- Run live Chrome checkpoint — render contract detail page for the malicious-input vendor; verify literal text in the card AND in the email-preview iframe; confirm DevTools shows no script execution.

---

## Ticket #5 — Milestone Payment
**Overall: PARTIAL**

| AC | Status | Evidence |
|---|---|---|
| AR-2 (one-helper rule) | **PARTIAL** | Sole vendor-side `$inc paid_amount` at `vendor_service.py:3803` (rolling up to `vendor_assignments`, inside `record_payment` transaction). Webhook routes through `record_payment` (`:4617`). **However:** `contract_service.record_milestone_payment` (`contract_service.py:1855-1883`) directly mutates `paid_amount` on `scheduled_payments` with no idempotency, no status guard, no clamp, no rollups. Wired to `/admin/contracts/milestones/{id}/pay` (`api/contracts.py:587`). Different collection, but the AR-2 rule says "every increment of `paid_amount`". |
| AR-4 (Stripe retry) | **MET** | Intent-idempotency check at `vendor_service.py:3708-3729`: same milestone + same intent → idempotent ack; same intent on different milestone → 409. Webhook translates record_payment 409 into `processed=True` to stop Stripe retries (`:4662-4676`). |
| AR-5 (refund) | **NOT MET** | **No refund handler** in `vendor_service.py` (grep `refund` → 0 hits). No `refunded_amount` field. No `charge.refunded` / `payment_intent.refunded` webhook branch. Schema choice unmade. |
| AR-6 (timezone) | **MET** | All `paid_at` writes use `datetime.now(timezone.utc)` (`vendor_service.py:3780, 3783, 4731, 4736, 4779`). No `datetime.utcnow()` in file. Frontend `paymentDate` uses `getLocalDateString()` (`PaymentMilestones.tsx:104` → `dateFormat.ts:288-298`) with explicit local-component construction, not UTC slice. |
| AR-7 (UI vs backend) | **MET** | `PaymentMilestones.tsx:387` renders `milestone.paid_amount` from server. 409 handling at `:206-226` surfaces specific toasts ("This payment is recorded against a different milestone", "Payment already recorded"). |
| AR-8 (convenience fallback) | **MET (helper)** | Intent check is gated `if stripe_payment_intent_id:` (`:3708`) — when None, skipped (correct: manual record has no intent so duplicate-intent check is meaningless; status guard + clamp still fire). Webhook always passes intent (`:4623`). |
| Rule 1 (status guard) | **MET** | `vendor_service.py:3737-3741` — 409 when `milestone.status == PaymentMilestoneStatus.PAID.value`. |
| Rule 2 (amount clamp) | **MET** | `vendor_service.py:3748-3758` — 400 with "exceeds remaining balance" (0.005 float-tolerance). |
| Rule 3 (idempotency) | **MET (manual 409 / webhook 200)** | Manual: `:3719-3729` raises 409 "already recorded against another milestone". Same-milestone retry returns 200 with milestone dict (`:3713-3718`). Webhook → 200 ack via `:4662-4676`. |
| Rollup integrity | **PARTIAL** | Inside `_record_in_transaction` (`:3789-3819`): `vendor_assignments.paid_amount $inc` (3803), `vendor_profiles.total_revenue $inc` (3810), `budget_categories.actual_spent $inc` (3817). All three are independent `$inc`, not recompute-from-milestones. Correct because guards prevent over-credit at source — but no self-healing if a milestone document drifts. |
| Driver | **NOT MET (named) / PARTIAL (adjacent)** | `testbed/verify_milestone_payment_idempotency.py` doesn't exist. `verify_payment_link_webhook_record_payment_routing.py` covers cases A (first-time webhook + rollups), B (replay/idempotency), C (fresh contract). Missing: D (manual+webhook race), E (overflow/clamp), F (refund), G (manual-double-record on same intent). |
| Commit 65c1c2e | **PARTIAL — not for this ticket** | Touched `vendor_service.py` for budget_category_id inheritance (different work), not `paid_at` timezone. AR-6 is met by other code, not this commit. Did not touch `PaymentMilestones.tsx`. |
| CHANGELOG entry | **PARTIAL** | `CHANGELOG.md:90` (2026-04-29) describes the payment-link webhook re-routing "with full guard inheritance (idempotency, soft-delete filter, contract version pinning) and transactional rollups". Bundled into the inverted-payer-flow sunset, not named as the milestone-payment ticket. No standalone entry naming Rules 1/2/3. |

**Open work:**
- **Decide and ship refund schema** (decrement `paid_amount` vs separate `refunded_amount`). Add `charge.refunded` / `payment_intent.refunded` webhook branch in `handle_payment_link_webhook`. AR-5 is currently uncovered.
- **Audit `contract_service.py:1855-1883 record_milestone_payment`** on `scheduled_payments` — either route through a shared helper enforcing the three rules, or document why client-contract scheduled payments are exempt. As written, it violates AR-2.
- Build `testbed/verify_milestone_payment_idempotency.py` covering scenarios D/E/F/G.
- Optional: promote rollup pattern from independent `$inc` to recompute-from-milestones, or add a periodic reconciliation job.
- Add a dedicated CHANGELOG entry naming this ticket independently of the inverted-payer-flow sunset.
- Run live Chrome checkpoint (double-submit, overflow, refund, timezone-spoof).

---

## Cross-cutting

### `regression_red` marker — NOT REGISTERED
`pytest.ini` (1-11) has no `[pytest] markers = ...` section. No `pyproject.toml` at root. Repo-wide grep for `regression_red` → 0 hits. Pytest will emit `PytestUnknownMarkWarning` for any check-in. **Definition of Done #4 unmet for all five tickets.**

### CHANGELOG entries — MISSING for all five
| Ticket | Status |
|---|---|
| #1 | Missing — no entry naming the four endpoints |
| #2 | Missing — code comment cites the fix; CHANGELOG is silent |
| #3 | Missing |
| #4 | Missing — only the unrelated 2024 guest-name escape entry exists |
| #5 | Partial — bundled into 2026-04-29 inverted-payer-flow sunset, not standalone |

**Definition of Done #6 unmet for all five.**

### `AGENTS.md` Known Open Issues cluster
"As of 2026-04-26" (AGENTS.md:297). Vendor-contract tickets do not touch the auth/session/402 surface. No update required. **DoD #7 met (vacuously) for all five.**

### Bare-string role checks introduced in scope
None found in `vendor_service.py`, `vendor_management.py`, or `contract_email_service.py`. Constants discipline holds in the diff scope.

### Live Chrome verification evidence
**None for any of the five tickets.** Searched `.md`, commit messages, `.github/`. The only "live-verified" hits are unrelated to these tickets. **Definition of Done #5 unmet for all five — this is the manual gate the user must perform.**

---

## Ship readiness verdict

**Ship-blocked, on every one of the five tickets, for at least three independent reasons.** First, the AR-2 "old route bypass" gate is open on **two** parallel surfaces in `app/services/contract_service.py` — `_get_wedding_record` / `create_contract:1431` (Ticket #1's same-class hole on `/admin/client-contracts`) and `record_milestone_payment:1855-1883` (Ticket #5's same-class hole on `scheduled_payments`). Either one is sufficient to keep the surface non-shippable; both together mean the centralized-helper pattern the plan asked for didn't actually land as a centralized helper. Second, the read-side leak in `get_form_data_for_contract` (Ticket #3) means the UI picker can list cross-tenant submissions tied to the same vendor email — the write was scoped, the read wasn't. Third, **none** of the five tickets has live Chrome verification evidence, which is the user's hard requirement and Definition of Done #5; per `feedback_e2e_chrome.md` and `CLAUDE.md` §"E2E verification", scripted drivers do not substitute for it. Adjacent gaps that don't block ship on their own but should land in the same wave: refund handling for Ticket #5 (AR-5 is unimplemented, not just untested), the missing XSS driver and `message` length cap for Ticket #4, the missing UI scope copy for Ticket #2, and the `regression_red` marker plus CHANGELOG entries cross-ticket. Recommended next move: file the two `contract_service.py` parallel-hole findings as Ticket #1b and #5b so the helper pattern actually consolidates; promote the `_get_owned_*` private methods to `app/utils/vendor_owner_scope.py` so #1b can reuse them; then run a single multi-ticket live Chrome session for #1, #2, #3, #4, #5 to close DoD #5 in one sitting once the parallel-hole fixes land.

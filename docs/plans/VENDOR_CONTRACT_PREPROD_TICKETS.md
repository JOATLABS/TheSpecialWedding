# Vendor Contract & Payment — Pre-Prod Blocker Tickets

Five tickets that must close before the planner-dashboard vendor-directory contract+payment surface ships. Each ticket is independently mergeable. Each carries adversarial-review acceptance criteria from `AGENTS.md` §"Required Adversarial Review Before Completion", a `testbed/` driver plan, **and** a live Chrome verification protocol with the user watching. Per `CLAUDE.md` §"E2E verification", scripted drivers are sanity checks; **live Chrome with the user watching is the only thing that counts as verification**. No ticket closes on green tests alone — not even backend-only fixes.

Title convention follows `AGENTS.md` §"Regression And Bug-Title Convention" — titles describe behavior, not the environment that exposed it.

Suggested merge order: **#1 → #3 → (#2, #4, #5 in parallel)**. #3 depends on the planner-scoped fetch helper introduced in #1; the rest are independent.

---

## Ticket 1 — Fix Cross-Tenant Write On Vendor Contract Create And Upload Paths

**Severity:** Critical · Pre-prod blocker
**AGENTS.md sections engaged:** §"Authorization And Tenant Boundary Rule", §"Route And Flow Parity Rule"

### Behavior to fix
An authenticated planner can:
- create a vendor contract whose `vendor_profile_id` and/or `wedding_id` belong to a different `created_by` (different tenant);
- upload a PDF and have it persist as a contract record against another tenant's vendor/wedding;
- overwrite another tenant's `document_url` on a signed contract via the document-upload route;
- mutate another tenant's `vendor_assignment` via the assignment-status endpoint.

### Affected files (verify line numbers before editing)
- `app/services/vendor_service.py` — `create_contract` (~:1540), `upload_contract_pdf` (~:3266), `upload_contract_document` (~:3166), `assign_vendor_to_wedding` (~:1302), `update_assignment_status` (~:1389)
- `app/api/vendor_management.py` — `POST /admin/contracts`, `POST /admin/contracts/{id}/upload`, `POST /admin/directory/{vendor_id}/assign`, `PUT /admin/assignments/{id}/status`

### Root cause
Vendor-profile and wedding lookups query by `_id` alone with no `created_by` filter, so ID-from-client is trusted. Same shape on the assignment update.

### Acceptance criteria (Adversarial Review checklist)
- [ ] **AR-1 (cross-tenant mutate):** Negative pytest case for each of the four endpoints proves planner A receives **404** when acting on a resource owned by planner B; no document is written.
- [ ] **AR-2 (old route bypass):** Grep audit lists every callsite of `vendor_profiles.find_one`, `weddings.find_one`, `vendor_assignments.find_one`, and confirms each one in mutation paths flows through a single scoped helper (e.g. `_get_owned_vendor_profile(actor_email, profile_id)`).
- [ ] **AR-7 (UI vs backend alignment):** 404 (not 403) is returned for foreign-owned IDs so the planner UI cannot infer the existence of another tenant's records.
- [ ] **AR-8 (convenience fallback):** No "if-not-found, look up by email" or other implicit fallback is introduced. Root-admin bypass remains explicit and is the only escape hatch.
- [ ] **Constants discipline:** No new bare-string role checks (`AGENTS.md` §"Centralized Constants And Enums Rule") — use `app/utils/planner_billing_scope.is_planner_billing_role` or extend `app/utils/messaging_roles.py` patterns.

### Testbed reproduction
- New driver: `testbed/verify_vendor_contract_cross_tenant_isolation.py`
- Pattern: idempotent fixture seed + scripted reset (mirror `testbed/verify_team_member_gate_via_test_clock.py`).
- Seed: planner A → vendor V_A, wedding W_A; planner B → vendor V_B, wedding W_B.
- Scenarios per endpoint:
  - **Create:** planner A POSTs `/admin/contracts` with `vendor_profile_id=V_B`, `wedding_id=W_B`. Pre-fix expectation: 200 + cross-tenant contract created. Post-fix expectation: 404, no row in `vendor_contracts`.
  - **Upload PDF:** same shape against `/admin/contracts/{C_B}/upload-pdf`.
  - **Upload doc:** planner A POSTs document upload against contract `C_B` owned by planner B. Pre-fix: planner B's `document_url` is overwritten. Post-fix: 404, S3 object not written, audit row not created.
  - **Assign / status:** planner A flips `vendor_assignments[A_B].status`. Pre-fix: success. Post-fix: 404.
- Cleanup: scripted teardown of all created contracts, weddings, vendor profiles, assignments, S3 objects.
- Run flag: supports `TESTBED_NON_INTERACTIVE=1`.

### Live UX checkpoint (Claude in Chrome with user watching)
Driven from a logged-in planner-A session in Chrome, user watching, console + network panels open:

1. **Direct URL escape:** navigate to `/admin/vendors/contracts/<C_B>` where `C_B` is a known planner-B contract id. Expected: "Contract Not Found" empty state renders; network panel shows 404 on `GET /admin/contracts/<C_B>`; no other-tenant data appears in any sidebar, badge, or activity log on the page.
2. **Forged create:** open `/admin/vendors/contracts/new`, walk through the wizard with a legitimate planner-A vendor + wedding, but in DevTools intercept the outgoing `POST /admin/contracts` and substitute `vendor_profile_id=V_B` or `wedding_id=W_B`. Submit. Expected: toast surfaces "Failed to create contract" or a 404-derived message (not 500); no row created (verify by reload of `/admin/vendors`); no other-tenant vendor/wedding name flashes in the UI mid-flow.
3. **Forged PDF upload:** invoke the upload-pdf flow against `C_B`'s id via DevTools-modified network request. Expected: 404, no progress-bar success state, no S3 URL written into the page state.
4. **Forged assignment status:** invoke `PUT /admin/assignments/<A_B>/status` against a planner-B assignment id. Expected: 404, the assignment list re-fetch shows no change.
5. Refresh planner-A's vendor list and confirm no cross-tenant data leaked into local state during the failed attempts.

Treat the run as failed if any console error, broken empty-state render, or cross-tenant string appears.

---

## Ticket 2 — Fix Cross-Tenant Roll-Up In Planner Dashboard Payment Aggregation

**Severity:** Critical · Pre-prod blocker
**AGENTS.md sections engaged:** §"Authorization And Tenant Boundary Rule", §"Source Of Truth Rule"

### Behavior to fix
The admin dashboard's payment-milestone aggregation filters by `wedding_id` only (and not at all when no wedding filter is applied). A planner viewing `/admin/dashboard` sees totals computed across every other planner's milestones in the database.

### Affected files
- `app/services/vendor_service.py` — `get_dashboard_counts` (~:1227–1257), `get_payment_milestones` (~:2934)

### Root cause
The Mongo aggregation pipeline omits the requesting planner's `created_by` (or the planner's owned-vendor set) from the milestone match stage. The read-side overdue-marking `update_many` in `get_payment_milestones` filters only on `_id IN […]`, which is fragile against future callers.

### Acceptance criteria
- [ ] **AR-1 (cross-tenant):** Dashboard totals for planner A never include milestones owned by planner B. Verified for `total_due`, `total_paid`, `total_overdue`, milestone count, and the per-status breakdown.
- [ ] **AR-2 (old route bypass):** Grep every callsite of `get_dashboard_counts` and `get_payment_milestones`. Each call passes the actor's `created_by` (or equivalent owner scope). Internal callers do not bypass.
- [ ] **AR-7 (UI vs backend):** Dashboard cards' tooltip / aria-label match the new "your team's payments" semantics. If existing copy implied "all", update to match.
- [ ] **AR-9 (docs/UI/behavior aligned):** The dashboard's analytics docs (if any in `docs/`) and the metric definitions in `AGENTS.md` §"Source Of Truth Rule" reflect the planner-scoped definition.
- [ ] Read-side `update_many` in the overdue-marking branch includes `created_by` in addition to `_id IN […]`.

### Testbed reproduction
- New driver: `testbed/verify_dashboard_payment_aggregation_isolation.py`
- Seed: planner A → 3 milestones totaling $30,000 (1 paid $10k, 2 scheduled $10k each). Planner B → 5 milestones totaling $500,000 (all paid).
- Scenarios:
  - **No filter:** planner A hits `/admin/dashboard`. Pre-fix: response sums > $30k (leak from B). Post-fix: response is exactly the seeded $30k breakdown.
  - **Wedding filter:** planner A passes `wedding_id=W_A`. Result equals the seeded breakdown for W_A only.
  - **Empty state:** planner C with zero milestones sees zeros, not other tenants' totals.
- Cleanup: scripted teardown of all seeded contracts and milestones.

### Live UX checkpoint
Open `/admin/dashboard` as planner A in Chrome (with user watching). Confirm the four KPI cards match the seed exactly. Switch to planner B's session (or a fresh seed). Confirm B sees their $500k total, not the union.

---

## Ticket 3 — Fix Cross-Tenant Form-Submission Read Via apply_form_data_to_contract

**Severity:** Critical · Pre-prod blocker
**AGENTS.md sections engaged:** §"Authorization And Tenant Boundary Rule"
**Depends on:** Ticket #1 (use the planner-scoped fetch helper landed there)

### Behavior to fix
`POST /admin/contracts/{id}/apply-form-data` accepts a `form_submission_id` from the client and merges that submission's content into the planner's contract sections without verifying the submission's ownership. A planner can paste another tenant's form-submission data into their own contract and read it back via `GET /admin/contracts/{id}` (sections + T&Cs are returned).

### Affected files
- `app/services/vendor_service.py` — `apply_form_data_to_contract` (~:2735)
- `app/api/vendor_management.py` — `POST /admin/contracts/{id}/apply-form-data`

### Root cause
The contract is planner-scoped via `get_contract`, but the subsequent lookup against `vendor_form_submissions` / `vendor_forms` queries by `_id` alone with no ownership constraint.

### Acceptance criteria
- [ ] **AR-1 (cross-tenant read):** Negative pytest case proves planner A applying a `form_submission_id` owned by planner B receives 404; the contract is unmodified. The sentinel value from B's form does not appear in A's contract sections.
- [ ] **AR-2 (old route bypass):** Grep every callsite that resolves a form submission by ID. Each one routes through the new ownership-checking helper.
- [ ] **AR-7 (UI vs backend):** The "Apply form data" button in `ContractDetailPageClient.tsx` lists only submissions the planner owns. Defense in depth: server-side enforcement is the source of truth, the UI list is the convenience layer.
- [ ] **AR-3 (edit-save round-trip):** After fix, applying a legitimate form submission still persists correctly across edit/save in `update_contract` and `update_contract_sections`.
- [ ] Activity log: `form_data_applied` row records `source_form_submission_id` and `source_vendor_id`. Verified to never reference a foreign tenant's form.

### Testbed reproduction
- New driver: `testbed/verify_form_data_apply_isolation.py`
- Seed: planner A → vendor V_A, draft contract C_A with placeholder `{{lead_singer_name}}`. Planner B → vendor V_B, vendor-form submission F_B containing `lead_singer_name=SENTINEL_FROM_B`.
- Scenarios:
  - **Cross-tenant apply:** planner A POSTs `/admin/contracts/C_A/apply-form-data` with `form_submission_id=F_B`. Pre-fix: 200, sentinel appears in C_A.sections. Post-fix: 404, C_A.sections unchanged, sentinel never read.
  - **Same-tenant apply:** planner A applies a legitimate submission `F_A`. Both before and after fix: 200, placeholder replaced, activity row recorded.
  - **Forged submission ID:** planner A applies an invalid ObjectId. 400/404 both before and after.

### Live UX checkpoint (Claude in Chrome with user watching)
Driven from planner-A's session, user watching, console + network panels open:

1. **Same-tenant happy path:** open contract `C_A` detail page → "Vendor Form Data Available" panel → click "View & Apply Form Data". Expected: legitimate form values populate the contract sections; activity tab shows a `form_data_applied` row with planner-A's source form id; no console errors.
2. **Cross-tenant attempt via DevTools:** with the same page open, intercept the outgoing `POST /admin/contracts/<C_A>/apply-form-data` and substitute `form_submission_id=<F_B>` (a known planner-B submission). Expected: 404 in the network panel; a user-facing error toast surfaces; the contract sections in the live UI are unchanged after refetch; no value from planner-B's form ever appears as text on the page mid-flight.
3. **Persistence check:** refresh the contract detail page and reopen the activity tab. Expected: no `form_data_applied` row was written for the failed attempt.
4. **Authorization parity (UI):** confirm that the "Apply Form Data" CTA's submission picker only lists planner-A's own submissions — defense in depth on top of the server-side fix.

Treat the run as failed if any planner-B field name, value, or vendor-name string flashes in the page DOM at any point during the failed attempt.

---

## Ticket 4 — Fix Stored XSS In Vendor Contract And Payment-Link Emails

**Severity:** High · Pre-prod blocker
**AGENTS.md sections engaged:** §"Required Adversarial Review Before Completion" Q7 (UI vs backend persists)

### Behavior to fix
`send_contract` and `send_payment_link` interpolate planner-supplied strings (`vendor_name`, `couple_names`, `contract_title`, `message`) directly into HTML email f-strings. An attacker (or a legitimate planner pasting an untrusted vendor name) can inject `<script>` or arbitrary HTML that renders in the vendor's inbox preview and any in-app HTML re-display surface.

### Affected files
- `app/services/vendor_service.py` — `send_contract` (~:2120), `send_payment_link` (~:3537)
- `app/services/contract_email_service.py` — review every method for the same pattern
- (Optional) frontend `VendorContractPreview` — confirm escaping parity in the markdown renderer

### Root cause
No HTML escaping on user-supplied values; emails composed via plain Python f-strings.

### Acceptance criteria
- [ ] **AR-2 (old route bypass):** Every email composer in `vendor_service.py` and `contract_email_service.py` either renders via Jinja with autoescape on, or runs every interpolated user value through `html.escape`. A grep-based test (or ruff custom rule) rejects new f-string HTML composition in the email modules.
- [ ] **AR-7 (UI vs backend persists):** A vendor named `<script>alert(1)</script>` renders as literal text in (a) the vendor's inbox HTML email, (b) the contract preview surface in `ContractDetailPageClient.tsx`, (c) the planner-side activity log. No script execution; no `<script>` tags survive parsing.
- [ ] **AR-9 (docs/UI/behavior aligned):** Vendor name input in the admin UI documents the max length and allowed character class. Backend Pydantic validation matches.
- [ ] Snapshot test: a fixture containing `<script>`, `<img onerror>`, and `javascript:` URLs in `vendor_name`, `contract_title`, and `message` produces an HTML body that, parsed via BeautifulSoup, contains zero `<script>` tags and zero `on*` event-handler attributes.

### Testbed reproduction
- New driver: `testbed/verify_vendor_email_xss_escaping.py`
- Pattern: same idempotent-fixture model. Replace the actual SES/Resend client with the existing test mock that captures rendered HTML.
- Seed: planner A → vendor with `vendor_name=<script>alert('xss')</script>`, contract title `<img src=x onerror=alert(1)>`, planner-supplied `message=<a href="javascript:alert(1)">click</a>`.
- Scenarios:
  - **send_contract:** Pre-fix: captured HTML contains raw `<script>` and `onerror`. Post-fix: only escaped entities (`&lt;script&gt;`); no `<script>` tags after parsing.
  - **send_payment_link:** same input set, same assertions.
  - **Re-display:** dump the contract via `GET /admin/contracts/{id}`; confirm fields come back as stored, not double-escaped.

### Live UX checkpoint
Open the contract detail page in Chrome (with user watching) for the malicious-input vendor. Confirm:
- the vendor card shows literal `<script>...</script>` text;
- DevTools console shows no script execution and no CSP violation beyond expected;
- the "Send Contract" preview modal renders the same.

---

## Ticket 5 — Fix Vendor Milestone Payment Overflow And Double-Recording

**Severity:** High · Pre-prod blocker
**AGENTS.md sections engaged:** §"Lifecycle Integrity Rule", §"Required Adversarial Review Before Completion" Q4/Q5 (reconnect/disconnect, retry semantics)

### Behavior to fix
`record_payment` unconditionally adds `amount` to `paid_amount`. There is no rejection when the milestone is already PAID, no clamp against the milestone's `amount`, and no idempotency check on `stripe_payment_intent_id`. Combined with `handle_payment_link_webhook` retries (Stripe retries webhooks on non-2xx and on its own schedule), a single payment can be recorded twice and the milestone over-credited. Downstream rollups in `vendor_assignments.paid_amount` and `vendor_profiles.total_revenue` inherit the inflation.

### Affected files
- `app/services/vendor_service.py` — `record_payment` (~:3015), `handle_payment_link_webhook` (~:3646)
- (Adjacent) `vendor_assignments` and `vendor_profiles` rollup writes inside the same service

### Root cause
Missing pre-conditions and missing idempotency join on `stripe_payment_intent_id`. The webhook handler treats `payment_link.amount` as the source of truth instead of the actual webhook total.

### Acceptance criteria
- [ ] **AR-2 (old route bypass):** Every increment of `paid_amount` in the codebase (manual record, webhook, any cron) routes through one helper that enforces the three rules below. No direct `$inc: {paid_amount: …}` in service code outside that helper.
- [ ] **AR-4 / AR-5 (retry / lifecycle):** Stripe retrying a webhook for the same `payment_intent_id` is a no-op after the first success. A refunded payment correctly decrements `paid_amount` (or maintains a separate `refunded_amount` field) without flipping status incorrectly.
- [ ] **AR-6 (timezone):** `paid_at`, `last_attempt_at`, and `next_retry_at` are stored timezone-aware (UTC). Frontend `paymentDate` initial value uses local-timezone date construction, not `new Date().toISOString().split('T')[0]` (UTC).
- [ ] **Rule 1 — Status guard:** Reject when `milestone.status == PAID` with HTTP 409 Conflict.
- [ ] **Rule 2 — Amount clamp:** Reject when `amount > (milestone.amount - milestone.paid_amount)` with HTTP 400.
- [ ] **Rule 3 — Idempotency:** When `stripe_payment_intent_id` is provided, refuse if any milestone (or `payment_history` entry) already references that intent. Return the first record's success response.
- [ ] **AR-7 (UI vs backend):** `PaymentMilestones.tsx` renders the actual `paid_amount` from the server, not an optimistic sum. Reload after action shows the same number. Conflict (409) surfaces as a toast, not a generic "Failed to record payment".

### Testbed reproduction
- New driver: `testbed/verify_milestone_payment_idempotency.py`
- Pattern: Stripe test clocks + idempotent fixtures, mirroring `testbed/verify_team_member_gate_via_test_clock.py`.
- Seed: contract C with milestone M (amount=$1000, paid_amount=0). Stripe customer with valid card. PaymentIntent `pi_test_123`.
- Scenarios:
  - **A. Double-record same intent (manual):** Hit `record_payment` twice with `stripe_payment_intent_id=pi_test_123, amount=$1000`. Pre-fix: paid=$2000, status=PAID, two `payment_history` rows. Post-fix: first 200 (paid=$1000), second 409, paid stays $1000, exactly one `payment_history` row.
  - **B. Webhook + manual race:** Manual `record_payment` for `pi_test_123` succeeds. Stripe webhook for the same intent then fires. Pre-fix: paid=$2000. Post-fix: webhook recognizes the intent is already recorded; no double-write; webhook returns 200 (idempotent ack).
  - **C. Overflow:** record $1500 against a $1000 milestone with paid_amount=0. Pre-fix: paid=$1500, status=PAID. Post-fix: 400, paid unchanged.
  - **D. Refund:** record $1000, then refund. Final state: paid_amount=0 (or refunded_amount=$1000), status reflects refund. Subsequent record-payment with a new intent succeeds normally.
  - **E. Rollup integrity:** after each scenario, assert `vendor_assignments.paid_amount` and `vendor_profiles.total_revenue` match the milestone state.
- Cleanup: scripted teardown of contracts, milestones, Stripe customers, payment intents.

### Live UX checkpoint
Open the contract detail page → Payments tab in Chrome (with user watching). Click "Record Payment" on a milestone, fill in $X, submit; before the modal closes, click submit a second time (or refresh and re-submit). Confirm:
- the second submission either no-ops or surfaces a "already recorded" toast;
- reload shows `paid_amount` equals $X exactly;
- DevTools network tab shows the second request returned 409 (not 500).

---

## Definition of done — applies to all five tickets

Per `CLAUDE.md` §"E2E verification" and `AGENTS.md` §"Completion Standard", **none** of these tickets close until all of the following are true. Do not claim completion based on `pytest` + TypeScript compile + happy-path browser only.

1. The acceptance matrix above is fully checked.
2. Every adversarial-review question in `AGENTS.md` §"Required Adversarial Review Before Completion" has been answered with "no" — not "maybe".
3. The new `testbed/` driver runs green against the live harness (`python testbed/testbed.py up`, run driver, `python testbed/testbed.py down`). **This is a sanity check, not verification.**
4. The before-fix red assertions are checked in (skipped via marker) so the next regression is caught — not deleted.
5. **The live Chrome checkpoint has been performed with the user watching for every ticket — including the backend-only ones.** Scripted tests prove the API behaves; only Chrome with the user watching proves the planner experience behaves. If the protocol can't be exercised from the UI directly (e.g. forged IDs), drive the request from DevTools while the page is loaded so any state contamination, console error, or broken render is observed in real time. No ticket closes on green tests alone.
6. `CHANGELOG.md` records: what changed, what risk class it addressed, any follow-up gaps.
7. The "Known Open Issues" cluster in `AGENTS.md` is updated if any of these touch the auth/session/402 cluster.

## Tracker fields (for paste-into-Linear/Jira)

For each ticket include:
- **Title:** as above (behavior, not environment)
- **Severity:** Critical / High
- **Component:** `vendor-management`, `contracts`, `payments`
- **Labels:** `pre-prod-blocker`, `security` (where applicable), `multi-tenant`
- **Linked driver:** `testbed/verify_*.py`
- **Adversarial review checklist:** copy from this doc
- **Reviewer assignment:** require security review on #1, #2, #3, #4

## Appendix — verifier commands

Backend:
```
ruff check app/
ruff format --check app/
pytest tests/backend/test_app_boot_smoke.py -v --tb=short
pytest tests/backend/ tests/test_id_utils.py -v --tb=short
```

Live lifecycle:
```
python testbed/testbed.py up
python testbed/verify_vendor_contract_cross_tenant_isolation.py
python testbed/verify_dashboard_payment_aggregation_isolation.py
python testbed/verify_form_data_apply_isolation.py
python testbed/verify_vendor_email_xss_escaping.py
python testbed/verify_milestone_payment_idempotency.py
python testbed/testbed.py down
```

Frontend (after #4 and #5 ship UI updates):
```
npm run lint
npm run type-check
npm test
npm run build
```

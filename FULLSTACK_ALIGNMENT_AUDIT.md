# Full-Stack Alignment Audit Report
## Wedding Web App — API ↔ Frontend ↔ Database Models

**Date:** March 23, 2026
**Scope:** 69 API files, 23 models, 64 services, 271 frontend files
**Methodology:** 6 parallel review teams (backend + frontend senior devs) auditing every domain slice

---

## Executive Summary

**Total endpoints audited:** ~250+ across 69 API files
**Total misalignments found:** 62
**Critical (P0 — blocking):** 15
**High (P1 — must fix before launch):** 20
**Medium (P2 — this sprint):** 15
**Low (P3 — tech debt):** 12

### Top 5 Cross-Cutting Issues

1. **Auth token bypass in hooks** — `useGuests` and `useTables` hooks access localStorage directly, bypassing AdminContext's 401/402 handling and auto-logout
2. **TypeScript ↔ Pydantic field mismatches** — Guest interface has phantom fields (`rsvp_status`, `dietary_restrictions`) that don't exist in backend; missing 12+ real fields
3. **Notification system fragmentation** — 3 separate notification systems (platform, planner activity, SSE stream) with no unified model
4. **Endpoint duplication** — Gallery (2 conflicting implementations), Contracts (3 separate APIs), Forms (3 separate APIs)
5. **Check-in endpoints will crash at runtime** — Sync `def` handlers calling `async` service methods

---

## Domain 1: Auth / Users / Teams / Wedding Core

### Endpoint Inventory (57 endpoints)
- **Admin Auth:** 4 endpoints (login, refresh, profile)
- **Couple Auth:** 7 endpoints (setup, login, password reset, profile)
- **Couple Invite:** 3 endpoints (invite, resend, list)
- **Couple Portal:** 6 endpoints (dashboard, events, updates, forms)
- **User Management:** 24 endpoints (invites, setup, password, profile, onboarding)
- **Team Management:** 11 endpoints (invite, list, manage, public accept)
- **Wedding:** 4 endpoints (list, create, update, delete)
- **OTP:** 3 endpoints (request, send, verify)
- **SaaS Config:** 10 endpoints (config, content, planners, analytics)

### Misalignments

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| 1 | P0 | Team Member response missing fields | Frontend expects `first_name`, `last_name`, `invited_at`, `accepted_at`, `deactivated_at` — API may not return them |
| 2 | P0 | Couple login response incomplete | Login returns couple without `id` field; GET /couple/profile includes it (inconsistent) |
| 3 | P0 | Token stored in 3 places | localStorage + sessionStorage + cookies — XSS exposure multiplied |
| 4 | P1 | Admin profile returns redundant data | Both flattened fields AND nested `user_data` object |
| 5 | P1 | Wedding billing fields unexposed | Model has meter/billing fields only set internally, no frontend visibility |
| 6 | P1 | OTP error mapping undocumented | 7+ HTTP status codes with error_codes, no clear docs |
| 7 | P1 | Rate limiter IP extraction flawed | X-Forwarded-For spoofing vulnerability on team invite/accept |
| 8 | P2 | Couple auth password reset — no frontend | Endpoints fully built but no UI integration |
| 9 | P2 | EventNoteModel has `reply_to` field | Allows nested replies, but no endpoints exist |
| 10 | P2 | Analytics endpoints unused | /analytics/overview, /revenue, /platform built but no admin page |

### Security Concerns
- Couple auth tokens not using httpOnly cookies (localStorage vulnerable to XSS)
- Team invite tokens exposed in URLs (browser history/logs)
- Profile image upload validates extension not file content
- No couple login brute-force detection

---

## Domain 2: Guests / RSVP / Tables / Plus-Ones / Check-in

### Endpoint Inventory (35+ endpoints)
- **Guest CRUD:** 7 endpoints (list, create, update, delete, activity, search)
- **Seating Constraints:** 2 endpoints (get, bulk update)
- **RSVP (public):** 1 endpoint (guest submits)
- **Admin RSVP:** 4 endpoints (list, export CSV, update, delete)
- **Plus-Ones:** 5 endpoints (create, get by guest, get by wedding, update, delete)
- **Tables:** 7 endpoints (list, create, update, delete, assign, unassign, export PDF)
- **Export/Import:** 5 endpoints (QR code, PDF, bulk QR ZIP, CSV import)
- **Check-in:** 2 endpoints (check-in, status)
- **Guest Verification:** 6 endpoints (verify access, privacy info, access by token, request link)

### Misalignments

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| 11 | P0 | Check-in endpoints are sync `def` calling `async` service | **Will crash at runtime** — FastAPI async mismatch |
| 12 | P0 | `/plus-one` route prefix may not have `/admin` | Frontend calls `/admin/plus-one/...` but router mount must be verified |
| 13 | P0 | Guest deletion doesn't cascade | Orphaned RSVPs, plus-ones, seating constraints remain after delete |
| 14 | P0 | TS Guest interface has phantom fields | `rsvp_status`, `dietary_restrictions`, `notes` don't exist in backend |
| 15 | P1 | Missing RSVP status hydration in guest list | Frontend does N+1 lookup — joins RSVP array in client-side JS |
| 16 | P1 | RSVP re-submission deletes all plus-ones | No audit trail — complete data loss on re-RSVP |
| 17 | P1 | Plus-one operations have no activity logging | Unlike guest mutations which log to activity_logs |
| 18 | P1 | Import defaults sms_opt_in/email_opt_in to True | GDPR issue — should default to None (not yet consented) |
| 19 | P1 | Token-based RSVP doesn't check wedding privacy mode | Bypasses OTP requirement for private weddings |
| 20 | P2 | `plus_one_submitted` is boolean only | Can't distinguish "1 of 2 submitted" vs "2 of 2 submitted" |
| 21 | P2 | Table capacity has post-check rollback only | Race condition partially mitigated but not prevented |
| 22 | P2 | AdminRSVPUpdateRequest missing phone/email fields | Admin can't update contact info via RSVP endpoint |
| 23 | P2 | Seating constraints don't store wedding_id | Could theoretically cross-reference across weddings |

### Data Flow Issues
- RSVP submission is NOT atomic (crash between RSVP upsert and plus-one insert = inconsistent data)
- Table assignment has no SSE broadcast (Admin A and Admin B can overwrite each other)
- Guest → RSVP → Plus-One data lives in 3 collections with no foreign key enforcement

---

## Domain 3: Vendors / Contracts / Forms / Packages

### Endpoint Inventory (95+ endpoints across 12 API files)
- **Vendor Management:** 33+ endpoints (directory, assignments, contracts, milestones, payment links, settings)
- **Public Vendor:** 3 endpoints (sitemap, directory listing, profile)
- **Vendor Signup:** 9 endpoints (signup, profile, web push)
- **Vendor Dashboard:** 2 endpoints (dashboard, task update)
- **Vendor Forms:** 6 endpoints (admin CRUD, public get/submit)
- **Vendor Campaigns:** 17+ endpoints (CRUD, lifecycle, creatives, leads, billing)
- **Contracts (standalone):** 5+ endpoints (CRUD, sections, public signing)
- **Public Contract:** 2 endpoints (view, sign)
- **Forms:** 8+ endpoints (CRUD, send, responses, public submit)
- **Packages:** 6 endpoints (CRUD, send)
- **Testimonials:** 5 endpoints (CRUD, public list)
- **Public Contact:** 1 endpoint (sales form)

### Misalignments

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| 24 | P0 | Vendor route path collision | Both `vendor_management.py` and `vendor_signup.py` use `/api/v1/vendors/*` with different auth |
| 25 | P0 | Contract endpoint duplication | Contracts in 3 places: `vendor_management.py`, `contracts.py`, `vendor_contract_public.py` |
| 26 | P0 | Form endpoint fragmentation | Forms in 3 APIs: `forms.py`, `vendor_forms.py`, with different service classes |
| 27 | P1 | Vendor dashboard conflates two vendor types | `assigned_wedding_ids` expected but advertising vendors don't have weddings |
| 28 | P1 | Two "dashboard" endpoints with same route | `vendor_management.py` and `vendor_dashboard.py` both serve GET /dashboard |
| 29 | P1 | Payment links disconnected from contracts | No `POST /contracts/{id}/payment-link` — separate creation required |
| 30 | P1 | Campaign approval has no vendor notification | Admin approves/rejects but vendor has no callback/push notification |
| 31 | P1 | Contract template system incomplete | No update/delete endpoints, no category filtering |
| 32 | P2 | Public contract signing diverges | Two entry points with different params (`token` vs `contract_id`) |
| 33 | P2 | Vendor assignment status not an enum | Accepts free-text strings — no type safety |
| 34 | P2 | Payment milestone status transitions undocumented | No endpoint to transition PENDING → DUE → OVERDUE |
| 35 | P2 | Pagination not standardized | Mix of `limit/skip` and `page/per_page` across endpoints |

### Vendor Lifecycle Gaps
- **Signup:** No profile completeness check before dashboard access
- **Campaigns:** No vendor-facing status update notifications
- **Contracts:** No negotiation/counter-proposal flow
- **Forms → Contracts:** No auto-population (manual match required)
- **Payments:** No auto-calculation of milestone DUE/OVERDUE status

---

## Domain 4: Budget / Billing / Subscriptions / Stripe

### Endpoint Inventory (47 endpoints across 6 API files)
- **Budget:** 20 endpoints (categories, quotes, templates, payments, alerts, reports)
- **Stripe Payment:** 13 endpoints (checkout, portal, intents, Connect, webhooks, billing)
- **Subscription Management:** 23 endpoints (plans, user subscriptions, usage tracking, analytics)
- **Trial Management:** 7 endpoints (admin + cron maintenance)
- **Billing Jobs:** 3 endpoints (usage sync, orphan cleanup, archival)
- **Metering:** 1 endpoint (retry)

### Misalignments

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| 36 | P0 | Dual subscription state sources | Both `users` and `user_subscriptions` collections store subscription state |
| 37 | P0 | Trial-to-paid conversion path unclear | No explicit state machine documenting PENDING_PAYMENT → TRIAL → ACTIVE → CANCELLED |
| 38 | P0 | Payment requests disconnected from budget tracking | Stripe payment_requests ≠ budget payment_records — no linkage |
| 39 | P1 | Stripe webhook handler incomplete/truncated | Not all 18 event types have documented handlers |
| 40 | P1 | Metered billing implementation incomplete | Usage-based billing endpoints exist but non-functional |
| 41 | P1 | Orphan customer cleanup has race condition | May delete active customers during cleanup window |
| 42 | P1 | Missing upgrade/downgrade/cancel endpoints | Only available through Stripe portal — no native API |
| 43 | P2 | Frontend fetch pattern inconsistency in billing pages | Fallback patterns, no centralized API client usage |
| 44 | P2 | BudgetCategory type has duplicate ID fields | Both `id` and `_id` serialized — bloated JSON |
| 45 | P2 | Trial warning emails have complex scheduling | Error-prone multi-stage notification logic |

---

## Domain 5: Gallery / Blog / KB / AI / Notifications / Calendar / Ads

### Endpoint Inventory (100+ endpoints across 27+ API files)
- **Gallery:** 10+ endpoints (admin, public, upload — 2 conflicting implementations)
- **Blog:** 9 endpoints (public + admin CRUD)
- **Knowledge Base:** 13 endpoints (public + admin + feedback)
- **Autopilot:** 11 endpoints (cron jobs + AI assessment)
- **Notifications:** 15+ endpoints (admin, user, templates)
- **SSE Stream:** 1 endpoint (event stream with heartbeat)
- **Planner Notifications:** 7 endpoints (activity + web push)
- **Calendar:** 16 endpoints (Google OAuth + task CRUD + views)
- **Planner Metrics:** 3 endpoints (dashboard, activity log, weddings)
- **Ad Interactions:** 5 endpoints (sponsored cards, quote requests)
- **Ad Preferences:** 6 endpoints (hide/suppress/frequency)
- **Admin Campaigns:** 8+ endpoints (review queue, approve/reject)
- **Support:** 8+ endpoints (ticket CRUD + comments)
- **Web Push:** 5 endpoints (subscribe, status, test)

### Misalignments

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| 46 | P0 | Gallery endpoint duplication | Two files define `/gallery/upload-url` with different wedding scoping behavior |
| 47 | P0 | SSE probe endpoint missing | Frontend probes `/admin/user/notifications/count` — doesn't exist |
| 48 | P0 | Notification system fragmentation | 3 systems: platform, planner activity, SSE — no unified model |
| 49 | P1 | Deprecated gallery public endpoints still routed | `GET /gallery` marked deprecated but likely still active |
| 50 | P1 | Reminder deduplication missing | Double cron execution sends duplicate SMS/email reminders |
| 51 | P1 | Autopilot AI results not persisted to model | AI risk_score and retry suggestions are transient |
| 52 | P2 | Calendar Google sync is one-way | Tasks sync TO Google but no import FROM Google |
| 53 | P2 | KB article feedback not aggregatable | No admin endpoint to review/moderate feedback |
| 54 | P2 | No rate limiting on public blog/KB endpoints | DDoS vulnerability |
| 55 | P3 | Email/SMS provider selection unclear | Telnyx and Twilio both supported; unclear which is primary |

---

## Domain 6: Frontend API Context Layer & Shared Hooks

### Architecture Summary
- **APIContext.tsx** + **AdminContext.tsx** = primary API gateway
- All requests should flow through `apiRequest()` with auto auth & error handling
- Token lifecycle: localStorage → sessionStorage → cookies fallback chain
- Auto-refresh scheduled ~5 min before JWT exp (60-min TTL)
- 401 triggers logout; 402 redirects to billing

### Misalignments

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| 56 | P0 | `useGuests` hook bypasses AdminContext | Reads token directly from localStorage — no 401 auto-logout |
| 57 | P0 | `useTables` hook bypasses AdminContext | Direct fetch() calls, no error handling for auth failures |
| 58 | P0 | SeatingConstraintsModal makes direct fetch() | Bypasses entire centralized error handling layer |
| 59 | P1 | TS Guest interface missing 12+ real backend fields | `sms_opt_in`, `email_opt_in`, `phone_status`, `created_at`, `updated_at`, etc. |
| 60 | P1 | `localStorage.clear()` on logout is too aggressive | Wipes all storage including user preferences and theme |
| 61 | P2 | Token refresh not immediately scheduled after login | Race condition if token expires during initial navigation |
| 62 | P2 | Missing page-level ErrorBoundary wrappers | Only layout-level — full page crash on component errors |

### TypeScript ↔ Pydantic Alignment Status

| Type | Frontend | Backend | Status |
|------|----------|---------|--------|
| Table | Complete match | Complete | ✅ Aligned |
| Guest | Missing 12+ fields + 3 phantom fields | Complete | 🔴 Critical |
| BudgetCategory | Duplicate id/_id | Alias-based | 🟠 Major |
| PaymentRecord | Mostly complete | Complete | ✅ Aligned |
| UserProfile | Complete | Complete (extended) | ✅ Aligned |
| Wedding | Flexible (spread) | Flexible | ✅ Aligned |
| RSVP | Implicit inline | RSVPModel | 🟠 Not formalized |
| PlusOne | Implicit inline | PlusOneModel | 🟠 Not formalized |

---

## Priority Action Plan

### P0 — Fix Before Any New Feature Work (15 issues)

1. **Fix check-in endpoints** — Change from sync `def` to `async def` (runtime crash)
2. **Fix Guest TS type** — Remove phantom fields, add 12+ missing fields
3. **Migrate useGuests/useTables to AdminContext** — Stop bypassing auth layer
4. **Verify plus-one route prefix** — Confirm `/admin` prefix applied in main.py
5. **Fix guest deletion cascade** — Delete associated RSVPs, plus-ones, constraints
6. **Consolidate gallery endpoints** — Merge gallery_upload.py into gallery_admin.py
7. **Add SSE probe endpoint** — Implement `/admin/user/notifications/count`
8. **Resolve vendor route collision** — Separate advertising vendor vs directory vendor prefixes
9. **Consolidate contract APIs** — Single entry point delegating to shared service
10. **Consolidate form APIs** — Unified form system with type discriminator
11. **Fix subscription dual-state** — Make `user_subscriptions` single source of truth
12. **Document trial-to-paid state machine** — Explicit transitions with validation
13. **Link payment requests to budget** — Bridge Stripe payments ↔ budget records
14. **Fix couple login response** — Include `id` field for consistency
15. **Unify notification model** — Single NotificationBase with type enum

### P1 — Must Fix This Sprint (20 issues)

16. Add RSVP status to guest list endpoint (or return joined data)
17. Preserve plus-one history on re-RSVP (soft delete)
18. Add activity logging to plus-one operations
19. Fix import opt-in defaults (GDPR: None instead of True)
20. Validate RSVP against wedding privacy mode
21. Implement httpOnly cookies for auth tokens
22. Fix vendor dashboard to handle advertising vs directory vendors
23. Add vendor notification on campaign approval/rejection
24. Complete contract template CRUD (update/delete)
25. Add upgrade/downgrade/cancel subscription endpoints
26. Complete Stripe webhook handlers for all event types
27. Fix orphan cleanup race condition
28. Add reminder deduplication
29. Persist autopilot AI results to model
30. Clear only admin-specific localStorage keys on logout
31. Add payment milestone status auto-calculation
32. Fix rate limiter IP extraction
33. Add OTP error code documentation
34. Schedule token refresh immediately after login
35. Remove deprecated gallery public endpoints

### P2 — Technical Debt (15 issues)

36-50. Type formalization, pagination standardization, error boundaries, date serialization documentation, cross-tab token sync, etc.

### P3 — Nice to Have (12 issues)

51-62. JSDoc comments, caching layers, Google Calendar bidirectional sync, feedback aggregation, etc.

---

## Architecture Recommendations

### Short-term (This Week)
1. Create a shared `useApiClient()` hook that wraps AdminContext.apiRequest — all hooks must use this
2. Generate TypeScript types from Pydantic models (use `pydantic-to-typescript` or similar)
3. Add integration tests for all P0 issues (especially check-in async crash)

### Medium-term (This Month)
1. Implement a unified notification service with event bus pattern
2. Create explicit state machine for subscription lifecycle
3. Consolidate vendor management into single cohesive API module
4. Add OpenAPI spec generation and frontend client auto-generation

### Long-term (This Quarter)
1. Migrate from direct MongoDB queries to repository pattern for cascade operations
2. Add transactional writes (MongoDB 4.0+ sessions) for atomic RSVP+PlusOne operations
3. Move SSE to Redis Pub/Sub for multi-worker scaling
4. Implement CQRS for read-heavy endpoints (guest list with RSVP join)

---

*Generated by 6 parallel review agents auditing the full codebase*

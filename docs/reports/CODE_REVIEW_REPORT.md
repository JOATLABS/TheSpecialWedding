# Code Review: Frontend-Backend Alignment Audit

**Date:** 2026-03-02
**Branch:** `feature-twilio-otp-improvement-final-submitted`
**Scope:** All 63 fixes across 19 files (13 backend, 6 frontend)

---

## Summary

After a systematic review of every modified file and their counterpart API consumers/providers, **the implementation is well-aligned**. The fixes correctly match backend routes, response shapes, and auth patterns. I found **3 issues** (1 critical, 2 medium) and **2 observations** — **all now resolved** (see fix notes below).

---

## Critical Issues

### 🔴 C-1: Public Contract Frontend Uses Wrong URL Pattern

**File:** `app/services/vendorManagementApi.ts` (lines 967-1004)
**Severity:** Critical — **will cause 404 errors** for public contract signing

The frontend `getPublicContract` and `signPublicContract` functions use:
```
GET  {API_BASE}/admin/public/contracts/{contractId}?token={accessToken}
POST {API_BASE}/admin/public/contracts/{contractId}/sign?token={accessToken}&signer_name=...&signer_email=...
```

But the backend `contracts.py` registers these routes **without** the `/admin` prefix (line 260 of `main.py`):
```python
app.include_router(contracts_router, tags=["Public Contracts"])  # No prefix!
```

So the actual backend paths are:
```
GET  /public/contracts/{token}          ← token IS the path param, not a query param
POST /public/contracts/{token}/sign     ← expects JSON body (SignContractRequest), not query params
```

**Three mismatches:**
1. Frontend prepends `/admin` — backend has no prefix
2. Frontend passes `token` as a query param — backend expects it as a path parameter
3. Frontend passes `signer_name`/`signer_email` as query params — backend expects a JSON body (`SignContractRequest` with `signature_name`, `stripe_customer_id`, `stripe_payment_method_id`, `accept_terms`)

**Impact:** Public contract viewing and signing will 404. This is on the critical path for couples receiving contracts.

**Fix:** Update `vendorManagementApi.ts` to match the backend's actual routes and request format.

**✅ RESOLVED:** After deeper investigation, found there are TWO contract systems: (1) the legacy vendor contract system via `vendor_management.py` registered at prefix `/vendor-contract`, and (2) the new contract system via `contracts.py` at root. The old `vendor-contract/[id]/page.tsx` and `vendorManagementApi.ts` were calling `/admin/public/contracts/...` when they should have been calling `/vendor-contract/public/contracts/...`. Fixed the prefix in both files. The new `contracts/[token]/page.tsx` was already correctly aligned.

---

## Medium Issues

### 🟡 M-1: Money Page Uses Unprefixed Contract Routes

**File:** `app/admin/money/page.tsx`
**Severity:** Medium

The money page fetches contracts using:
```
GET {baseUrl}/contracts?status=signed
GET {baseUrl}/contracts/{contractId}/payments
POST {baseUrl}/payments/{paymentId}/retry
```

These contract routes ARE registered without prefix at line 260 of `main.py`, so `/contracts` resolves correctly. However, the `/payments/...` routes (retry, cancel, mark-paid-externally) are also on the contracts router without prefix, so they resolve at:
```
POST /payments/{payment_id}/retry
POST /payments/{payment_id}/cancel
POST /payments/{payment_id}/mark-paid-externally
```

**This is currently correct** — but fragile. If the contracts router is ever given a prefix, these will break.

**✅ RESOLVED:** Added documentation comment at the top of `money/page.tsx` explaining the route dependency.

### 🟡 M-2: Budget Alert Endpoints Return Placeholder Data

**File:** `app/api/budget.py` (lines 540-559)
**Severity:** Medium — not blocking but misleading

The `GET /admin/budget/alerts/{wedding_id}` endpoint was fixed (B8) but still returns placeholder data:
```python
return {"alerts": [], "message": "Budget alerts feature coming soon"}
```

The `PUT /admin/budget/alerts/{alertId}/read` and `PUT /admin/budget/alerts/{alertId}/resolve` endpoints were added (B9) but there's no backend logic to actually create alerts. The frontend `budgetApi.ts` properly handles the empty array, so this won't crash — but the "mark as read" and "resolve" endpoints will 404 since no alerts exist to reference.

**✅ RESOLVED:** Fully implemented budget alerts:
- Added `get_budget_alerts()`, `mark_alert_as_read()`, `resolve_alert()` methods to `budget_service.py` (the `_check_budget_alerts` method was already generating and storing alerts in MongoDB — the endpoint was just ignoring them)
- Wired `GET /budget/alerts/{wedding_id}` to `budget_service.get_budget_alerts()` instead of returning empty placeholder
- Added `PUT /budget/alerts/{alert_id}/read` and `PUT /budget/alerts/{alert_id}/resolve` endpoints to `budget.py`, matching the URLs in `budgetApi.ts`

---

## Observations (Non-blocking)

### ℹ️ O-1: Contract Status Type Mismatch

The frontend `ContractStatus` type includes `'expired'` as a valid status:
```typescript
export type ContractStatus = 'draft' | 'pending_review' | 'sent' | 'viewed' | 'signed' | 'completed' | 'cancelled' | 'expired';
```

But the backend constants in `contract_service.py` do not include `expired`:
```python
CONTRACT_STATUS_DRAFT = "draft"
CONTRACT_STATUS_PENDING_REVIEW = "pending_review"
CONTRACT_STATUS_SENT = "sent"
CONTRACT_STATUS_VIEWED = "viewed"
CONTRACT_STATUS_SIGNED = "signed"
CONTRACT_STATUS_ACTIVE = "active"
CONTRACT_STATUS_COMPLETED = "completed"
CONTRACT_STATUS_CANCELLED = "cancelled"
```

Also note `'active'` is in the backend but NOT in the frontend type. This is unlikely to cause runtime issues (TypeScript types don't enforce at runtime) but could lead to confusing UI states.

**✅ RESOLVED:** Added `'active'` to the `ContractStatus` type union and added `active: 'bg-teal-100 text-teal-800'` to the status color map in `vendorManagementApi.ts`.

### ℹ️ O-2: VendorContract Interface Uses `_id` but Backend Returns Both `id` and `_id`

The frontend `VendorContract` interface has `_id: string` as the primary identifier. The backend `_serialize_contract` method returns both `"id"` and `"_id"` (both as string). The contract detail page (`[id]/page.tsx`) fetches via `getContract` which returns the response directly. Since the backend returns the contract object directly (not wrapped in `{contract: ...}`), this aligns correctly — but the frontend should prefer `id` over `_id` for consistency.

**✅ RESOLVED:** Two-part fix:
1. **Backend:** Added `_serialize_doc()` helper to `vendor_service.py` that normalizes MongoDB documents to return both `id` and `_id` as strings. Applied to all contract CRUD methods (create, list, get, get_by_token, create PDF contract). Previously only `_id` was set.
2. **Frontend:** Added `id?: string` to both `VendorContract` and `PublicContract` interfaces in `vendorManagementApi.ts`. Existing `_id` references continue to work; new code should prefer `id`.

---

## What Looks Good

**Budget API (budgetApi.ts ↔ budget.py):** All 12 fixes verified correct. Routes, response unwrapping (`payload.quotes`, `payload.category`), and singular `category` path all match. The `check_wedding_access()` security additions are properly placed.

**AI API (ai.py):** Request model validations (A6) use sensible `max_length` limits. Health endpoint (A7) response time metric is well-implemented. Credit pre-check (A8) correctly uses fail-open pattern for the credit check itself while failing correctly on insufficient credits.

**Seating/Tables (tables.py ↔ guest.py ↔ guest_service.py):** T1 (invalid guest ID validation), T4 (capacity check), T8 (concurrent assignment rollback) are solid. The rollback pattern on line 208 of `tables.py` is correct — it re-queries post-update and reverses if capacity exceeded. Guest service `list_guests_by_wedding` properly converts `_id → id`.

**Autopilot (autopilot.py):** A2 fail-closed CRON_SECRET guard is correct — returns 503 when unset rather than silently allowing access.

**Stripe/Billing:** S2 fix (`admin_token` instead of `authToken`) aligns with the pattern used everywhere else. S3 subscription fetch uses user profile ID correctly. Feature gates (S8) now check both `user_email` and `user_id` with proper fallback chain.

**Contract Service (contract_service.py):** C5 auto-generated contract numbers, C11 30-day token expiry, C13 status transition guards — all well-implemented. The `_serialize_contract` method correctly handles date serialization.

**Route Ordering (contracts.py):** Static paths (`/contracts/stats`, `/contracts/followup-drafts`) are correctly placed before `{contract_id}` parameterized routes, preventing FastAPI from matching literal path segments as IDs.

---

## Verdict

**All issues resolved.** The codebase is now aligned across frontend and backend for all modified endpoints. Ready for deployment testing.

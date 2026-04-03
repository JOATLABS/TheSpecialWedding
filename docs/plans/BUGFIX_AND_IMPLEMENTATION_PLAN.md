# Bug Fix & Implementation Plan

**Date:** March 14, 2026
**Scope:** AdminContext crash fix, AI service bugs, advertising verification, public vendor profile page

---

## Phase 1: Investigation (Completed)

All bugs below have been confirmed by reading source code. No ambiguity remains.

### CRITICAL — App Crash

| ID | File | Lines | Issue | Impact |
|----|------|-------|-------|--------|
| BUG-CTX | `app/contexts/AdminContext.tsx` | 378-396 | Provider value references `auth.isAuthenticated`, `auth.token`, `auth.login`, `auth.logout`, `auth.fetchUserProfile`, `api.apiRequest` — but no `auth` or `api` objects exist. All values are standalone variables/functions in the component scope. | **Every page crashes** with `TypeError: Cannot read properties of undefined (reading 'isAuthenticated')`. The entire admin UI is broken. |

### HIGH — AI Feature Bugs

| ID | File | Lines | Issue | Impact |
|----|------|-------|-------|--------|
| BUG-001 | `app/api/ai.py` | 1261 | `credit_check.get("has_credits", True)` — but `check_credits()` returns `{"allowed": bool}`, not `{"has_credits": bool}`. Key mismatch means the check always passes (defaults to `True`). | Credit limits never enforced for contract generation pre-check. |
| BUG-002 | `app/api/ai.py` | 1262-1265 | `InsufficientCreditsError(required=..., available=...)` — missing required `message` positional parameter. Constructor signature is `__init__(self, message, required, available)`. | `TypeError` crash if credit check ever triggers (currently masked by BUG-001). |
| BUG-005 | `app/api/ai.py` | 1432 | `tenant_id=request.wedding_id or user_id` — vendor recommendations falls back to `user_id` as tenant when no `wedding_id` provided. Cached results keyed to user_id are shared across all their weddings. | Cache pollution: vendor recommendations for Wedding A served to Wedding B. |
| BUG-006 | `app/services/ai_service.py` | 1044 | `model=model` in except block — `model` is defined at line 950 inside the try block. If an error occurs before line 950 (e.g., during `_select_model_and_check_credits`), `model` is undefined. | `NameError` crash in the error-logging path, which means the original error is swallowed silently. |
| BUG-008 | `app/services/ai_service.py` | 1194-1197 | JSON parse failure returns `{"text": response_text, "raw": True}`. Downstream code expects structured JSON with specific keys (e.g., `result["response"].get("insights", [])`). | `KeyError`/`AttributeError` crash when AI returns non-JSON. Features fail instead of gracefully degrading. |
| BUG-009 | `app/services/ai_service.py` | 957-962 | `increment_usage()` called immediately after `_call_gemini()` succeeds, but BEFORE response validation/parsing. If parsing fails (BUG-008 path), credits are already deducted. | Users charged for failed/unusable AI responses. No refund mechanism. |

### MEDIUM — Advertising Wiring

| ID | Area | Issue |
|----|------|-------|
| ADV-001 | End-to-end | Advertising feature was built this session but never tested. Need to verify: router registration, API endpoints respond, frontend pages render, sponsored rail loads. |
| ADV-002 | Public vendor page | No `/vendors/{id}` public page exists. When a planner clicks a sponsored vendor card, there's nowhere to land. |

---

## Phase 2: Implementation (Ordered by Priority)

### Fix 1: AdminContext.tsx Crash (BUG-CTX) — BLOCKING

**Current code (lines 378-396):**
```tsx
value={{
    isAuthenticated: auth.isAuthenticated,  // ❌ auth is undefined
    isLoading: auth.isLoading,
    token: auth.token,
    userProfile: auth.userProfile,
    login: auth.login,
    logout: auth.logout,
    fetchUserProfile: auth.fetchUserProfile,
    apiRequest: api.apiRequest,             // ❌ api is undefined
}}
```

**Fix:** Replace with direct references to the variables defined in the component:
```tsx
value={{
    isAuthenticated: !!token,
    isLoading,
    token,
    userProfile,
    login,
    logout,
    fetchUserProfile,
    apiRequest,
}}
```

**Files changed:** 1 (`app/contexts/AdminContext.tsx`)

---

### Fix 2: AI Credit Check Key Mismatch (BUG-001)

**Current:** `credit_check.get("has_credits", True)`
**Fix:** `credit_check.get("allowed", True)`

**File:** `app/api/ai.py`, line 1261

---

### Fix 3: InsufficientCreditsError Constructor (BUG-002)

**Current:**
```python
raise InsufficientCreditsError(
    required=credit_check.get("required", 1),
    available=credit_check.get("available", 0)
)
```

**Fix:**
```python
raise InsufficientCreditsError(
    message=credit_check.get("message", "Insufficient AI credits"),
    required=credit_check.get("credits_needed", 1),
    available=credit_check.get("credits_remaining", 0)
)
```

Note: also fixes response key names to match what `check_credits()` actually returns (`credits_needed`, `credits_remaining`, `message`).

**File:** `app/api/ai.py`, lines 1262-1265

---

### Fix 4: Undefined `model` in Error Handler (BUG-006)

**Current:** `model=model` (line 1044) — `model` may not exist
**Fix:** `model=locals().get("model", "unknown")`

**File:** `app/services/ai_service.py`, line 1044

---

### Fix 5: Credits Deducted Before Validation (BUG-009)

**Current flow:**
1. `_call_gemini()` → raw response
2. `increment_usage()` → credits deducted
3. `_parse_response()` → may fail

**Fixed flow:**
1. `_call_gemini()` → raw response
2. `_parse_response()` → validate first
3. `increment_usage()` → only if valid

**File:** `app/services/ai_service.py`, lines 957-975 (reorder operations)

---

### Fix 6: Plain Text Fallback (BUG-008)

**Current:** Returns `{"text": response_text, "raw": True}` on JSON parse failure
**Fix:** Raise `AIInvalidResponseError` instead, which triggers the cached fallback path (lines 1050-1065). This is better than silently returning a misshapen object.

**File:** `app/services/ai_service.py`, lines 1194-1197

---

### Fix 7: Vendor Recommendation Cache Pollution (BUG-005)

**Current:** `tenant_id=request.wedding_id or user_id`
**Fix:** Require `wedding_id` — if not provided, skip caching entirely or use a unique key:
```python
tenant_id = request.wedding_id
if not tenant_id:
    # No wedding context = no caching, generate fresh each time
    force_refresh = True
    tenant_id = f"user_{user_id}_no_wedding"
```

**File:** `app/api/ai.py`, lines 1430-1437

---

### Build 1: Public Vendor Profile Page (ADV-002)

Create a public-facing vendor profile page at `/vendors/[id]/page.tsx` that:
- Fetches vendor profile from a new public API endpoint `GET /api/v1/vendors/{id}/public`
- Displays: business name, service category, description, portfolio images, contact info
- Has a "Request Quote" CTA (links to planner sign-up if not logged in)
- Renders without authentication (public page)
- Includes meta tags for SEO

**New files:**
- `app/vendors/[id]/page.tsx` — Public vendor profile page
- `app/api/vendor_directory.py` — Add `GET /api/v1/vendors/{id}/public` endpoint

---

## Phase 3: Testing

### Critical Path Tests (Must Pass)

| # | Test | How to Verify | Pass Criteria |
|---|------|---------------|---------------|
| T-01 | Admin login works | Login as planner → check redirect to `/admin/planner` | No crash, profile loads, sidebar renders |
| T-02 | AdminContext provides values | After login, check `useAdmin()` returns valid `token`, `userProfile`, `isAuthenticated` | All values defined, no `undefined` |
| T-03 | AI credit check enforces limits | Call contract generation with 0 credits | Returns 402/403 with meaningful error, not `TypeError` |
| T-04 | AI handles non-JSON response | Mock Gemini returning plain text | Graceful fallback to cached data or clean error, not crash |
| T-05 | Credits not deducted on failure | Trigger AI call that fails during parse | Credit balance unchanged |
| T-06 | Advertising page loads | Navigate to `/admin/advertising` as root admin | Page renders with 3 tabs, no console errors |
| T-07 | Sponsored vendor CRUD | Create, read, update, delete a sponsored vendor via admin UI | All operations succeed, list updates |
| T-08 | Sponsored rail renders | Navigate to vendor page as planner | Rail component renders (empty state OK if no sponsored vendors) |

### Integration Tests

| # | Test | How to Verify | Pass Criteria |
|---|------|---------------|---------------|
| T-09 | Feature flag toggle | Toggle advertising on/off | Sponsored rail appears/disappears accordingly |
| T-10 | Ad event tracking | Click a sponsored vendor card | Event recorded in DB, click count increments |
| T-11 | Vendor recommendations per-wedding | Request recommendations for Wedding A, then Wedding B | Different results (not cross-cached) |
| T-12 | Token refresh | Wait for token to approach expiry | Auto-refresh fires, new token stored, no logout |
| T-13 | Public vendor page | Visit `/vendors/{id}` while logged out | Page renders with vendor info, no auth required |

### Edge Case Tests

| # | Test | How to Verify | Pass Criteria |
|---|------|---------------|---------------|
| T-14 | Expired token on load | Set expired token in localStorage, refresh | Clears storage, redirects to login (no crash loop) |
| T-15 | AI error logging with no model | Cause error before model selection in `generate()` | Error logged with `model="unknown"`, no `NameError` |
| T-16 | Team member sees filtered nav | Login as team member with limited permissions | Only permitted nav items shown |

---

## Execution Order

1. **Fix BUG-CTX** (AdminContext crash) — unblocks everything
2. **Fix BUG-001 + BUG-002** (credit check) — quick, same file
3. **Fix BUG-006** (model undefined) — one-liner
4. **Fix BUG-009 + BUG-008** (credits + parse) — related, same file
5. **Fix BUG-005** (cache pollution) — one-liner
6. **Run T-01 through T-05** (verify critical fixes)
7. **Run T-06 through T-08** (verify advertising)
8. **Build public vendor page** (ADV-002)
9. **Run T-09 through T-16** (integration + edge cases)

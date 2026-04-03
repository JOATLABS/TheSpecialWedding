# Browser E2E Testing — Known Issues

**Test Date:** 2026-03-26
**Tester:** Claude (automated browser walkthrough via Claude in Chrome)
**Runbook:** `docs/testing/deployment-browser-e2e-runbook.md`
**Environment:** localhost (frontend :3000, backend :8000, MongoDB :27017)

---

## DEPLOYMENT BLOCKERS

### DB-1: Auth token stored in localStorage instead of cookies
- **Severity:** CRITICAL — Deployment Blocker
- **Scenario:** A (Auth Token Storage)
- **Affected Roles:** Planner, Root Admin (all admin portal logins)
- **Expected:** `admin_token` stored as an HTTP-only cookie; localStorage and sessionStorage should contain NO tokens
- **Actual:** `admin_token` is stored in `localStorage`. No cookie-based token storage is used at all.
- **Storage Check Result:**
  ```json
  {
    "admin_token_ls": "eyJhbGciOiJIUzI1NiIs...",
    "cookie_admin": false
  }
  ```
- **Impact:** XSS vulnerability — any injected script can exfiltrate the JWT from localStorage. The runbook explicitly marks this as a GO/NO-GO blocker.
- **Recommendation:** Move token storage to HTTP-only, Secure, SameSite=Strict cookies on the backend. Remove all `localStorage.setItem('admin_token', ...)` calls from the frontend.

### DB-2: Planner logout does NOT clear admin_token from localStorage
- **Severity:** CRITICAL — Deployment Blocker
- **Scenario:** B (Logout & Token Cleanup)
- **Affected Roles:** Planner
- **Expected:** On logout, `admin_token` is removed from all storage (localStorage, sessionStorage, cookies)
- **Actual:** After clicking Logout on planner dashboard, `admin_token` persists in localStorage. Navigating back to `/admin/planner` re-authenticates the user automatically.
- **Impact:** Session hijacking risk. Users who "log out" on shared machines remain authenticated.
- **Recommendation:** Ensure the logout handler calls `localStorage.removeItem('admin_token')` (or `localStorage.clear()`) and invalidates the server-side session/token.

---

## HIGH PRIORITY BUGS

### H-1: Couple dashboard shows $0 Total Budget despite planner setting $30,000
- **Severity:** HIGH
- **Scenario:** F (Cross-Role Data Sync)
- **Expected:** Couple portal budget reflects the budget set by the planner ($30,000 for "James and Mel" wedding)
- **Actual:** Couple dashboard Budget Overview shows "$0 Total budget", "$0 Remaining"
- **Impact:** Couples see incorrect financial data. Core data sync between planner and couple views is broken.
- **Recommendation:** Investigate whether the couple budget API reads from the same wedding document field that the planner writes to. Likely a field name mismatch or missing population in the couple-facing budget endpoint.

### H-2: Wedding date formatting bug — "February 15, 20270" instead of "2027"
- **Severity:** HIGH
- **Scenario:** D (Planner Dashboard)
- **Expected:** Wedding date displays as "February 15, 2027"
- **Actual:** Displays as "February 15, 20270" on the planner dashboard
- **Impact:** Visible data corruption in the UI. Likely a string concatenation bug in date formatting (appending "0" to the year).
- **Recommendation:** Check the date formatter — likely `toLocaleDateString()` is receiving a malformed date string or there's a concatenation issue in the template.

### H-3: Error count mismatch on Platform Errors page
- **Severity:** HIGH
- **Scenario:** I (Platform Error Detail & Acknowledge)
- **Expected:** Tab label, summary cards, and table pagination should show consistent error counts
- **Actual:**
  - Tab label: "Errors (22)"
  - Total Errors (30d) card: 232
  - Showing: "1–50 of 232 errors" (5 pages)
  - Critical (this page): 14, Warnings (this page): 11 — but 50 items on page (14 + 11 = 25, not 50; "high" severity is not counted)
- **Impact:** Confusing/misleading error metrics for platform administrators. The tab count, card totals, and severity breakdown are all inconsistent.
- **Recommendation:** Align the tab badge with the actual queryable total. Add a "High" severity count card. Clarify whether "30d" vs "24h" scoping differs between tab badge and body.

---

## MEDIUM PRIORITY BUGS

### M-1: AI Insights returns authentication failure
- **Severity:** MEDIUM
- **Scenario:** D (Planner Dashboard)
- **Expected:** AI Insights panel generates actionable insights for the wedding
- **Actual:** Shows "AI generation failed: AI service authentication failed"
- **Impact:** AI features non-functional. Likely a missing or expired Gemini API key configuration issue.
- **Recommendation:** Verify `GEMINI_API_KEY` is valid and the AI service endpoint is correctly configured.

### M-2: Vendor test account cannot log into Ad Portal
- **Severity:** MEDIUM
- **Scenario:** G (Vendor Ad Portal)
- **Expected:** `test_vendor1@thespecialwedding.io` / `testVendorPass123!` logs into `/portal/ads/login`
- **Actual:** Returns "Invalid credentials"
- **Impact:** Cannot test vendor-specific ad portal flows without falling back to root admin
- **Recommendation:** Ensure the vendor test account is seeded with the correct role/permissions for the ad portal system. The vendor may exist in the planner system but not in the ad portal's user store.

---

## TEST DATA GAPS (Non-blocking)

### TD-1: No budget templates seeded
- **Scenario:** H (Budget Template)
- **Impact:** Cannot test "Apply Template" flow — template list is empty
- **Recommendation:** Seed 2–3 budget templates (e.g., "Standard Wedding $15K", "Premium Wedding $30K") for testing

### TD-2: No guest data seeded
- **Scenario:** H (Guest Management)
- **Impact:** Cannot test guest filter, sort, pagination, or bulk operations — guest list is empty
- **Recommendation:** Seed 20+ guest records across RSVP statuses for the test wedding

---

## PASSING SCENARIOS

| Scenario | Description | Result |
|----------|-------------|--------|
| C | Session Persistence (hard refresh) | PASS — planner session survives F5 reload |
| D | Planner Dashboard (navigation, widgets) | PASS (with H-2 date bug noted) |
| E | Couple Portal — Registry CRUD | PASS — Create, Read, Update, Delete all work with toast confirmations |
| E | Couple Portal — FAQ CRUD | PASS — Create, Read, Update, Delete all work with toast confirmations |
| E | Couple Portal — Messaging | PASS — send message, appears in thread, conversation preview updates |
| G | Vendor Ad Portal (via root admin) | PASS — Campaigns, Billing, Leads, Settings all load; no tokens in localStorage/sessionStorage |
| I | Platform Error Detail & Acknowledge | PASS — detail page loads, "Mark as Acknowledged" updates to "Acknowledged", list reflects "Ack'd" status and unacknowledged count decrements |

---

## GO / NO-GO SUMMARY

| Check | Status |
|-------|--------|
| Zero tokens in localStorage / sessionStorage | **FAIL** — admin_token in localStorage (DB-1) |
| Logout clears all auth artifacts | **FAIL** — admin_token persists after logout (DB-2) |
| Couple ↔ Planner data sync correct | **FAIL** — budget shows $0 on couple side (H-1) |
| Error acknowledge flow works | PASS |
| CRUD operations functional | PASS |

**Deployment Decision: NO-GO** — DB-1 and DB-2 must be resolved before production deployment.

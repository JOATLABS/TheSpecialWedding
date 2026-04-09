# Couple & Team Access E2E Runbook — Test Findings Report

**Date:** April 8, 2026  
**Tester:** Claude (automated via Chrome MCP)  
**Runbook:** `docs/testing/couple-team-access-e2e-runbook.md`  
**Environment:** localhost:3000 (frontend) / localhost:8000 (backend)  
**Test Account:** test_planner2@thespecialwedding.io (signed up via frontend pricing flow)

---

## Executive Summary

Testing revealed **1 critical blocker**, **2 high-severity issues**, and **4 medium-severity gaps** between the runbook and the actual application behavior. The couple setup flow is completely broken due to a crash loop, which blocks Scenarios 7.2–7.4 and 7.7 from being executed.

---

## Scenarios Executed

| Scenario | Status | Result |
|----------|--------|--------|
| 7.1 — Planner Owner Baseline | Executed | PASS (with caveats) |
| 7.2 — Couple Invite & Setup | Partially Executed | BLOCKED — crash loop |
| 7.3 — Revoke / Restore | Not Executed | BLOCKED (depends on 7.2) |
| 7.4 — Cancellation / Reactivation | Not Executed | BLOCKED (depends on 7.2) |
| 7.5 — Archived Wedding | Not Executed | Needs manual setup |
| 7.6 — Team Permission Matrix | Not Executed | Needs team member accounts |
| 7.7 — Couple Messaging | Not Executed | BLOCKED (depends on 7.2) |
| 7.8 — Meeting Ownership | Not Executed | Needs manual setup |

---

## Critical Issues

### CRIT-1: Couple Setup Page Crash Loop (Blocks 7.2, 7.3, 7.4, 7.7)

**Severity:** Critical / Blocker  
**URL:** `http://localhost:3000/couple/setup/{token}`  
**Symptom:** After the planner sends a couple invitation (which succeeds — status shows "Pending Setup"), opening the couple setup link causes the page to rapidly alternate between "Verifying your invitation..." spinner and Chrome's "This page couldn't load" error. The browser eventually gives up.

**Observed behavior:**
1. Page loads, shows "Verifying your invitation..." 
2. Page crashes to "This page couldn't load — Reload to try again, or go back."
3. Loop repeats rapidly

**Code analysis:** The route guard (`CoupleRouteGuard.tsx`) and auth context (`CoupleAuthContext.tsx`) both correctly exempt `/couple/setup` as a public path. The `CoupleSetupPageClient` component has proper try/catch error handling in the verify useEffect. The backend endpoint `GET /couple/verify-invite/{token}` looks structurally sound.

**Likely root cause candidates:**
- Backend `_resolve_portal_access()` throwing an unhandled error (e.g., wedding document missing expected fields)
- Next.js hydration mismatch between server and client rendering causing repeated recovery attempts
- The `ErrorBoundary` component in `CoupleLayoutClient` catching the crash and re-mounting the component, creating an infinite loop

**Impact:** The entire couple-facing flow is untestable. Scenarios 7.2 through 7.4 and 7.7 cannot be executed.

---

## High-Severity Issues

### HIGH-1: Login Endpoint Returns 500 (Root Admin)

**Severity:** High  
**Endpoint:** `POST /admin/token`  
**Symptom:** Logging in as root admin (`thedeveloper@thespecialwedding.io`) returns HTTP 500 "An unexpected error occurred." This was tested via both the UI form and direct fetch from the browser.

**Impact:** Root admin cannot log in. This blocks any admin-level testing or user management.

**Note:** Login with the test planner account (`test_planner2@thespecialwedding.io`) works correctly, suggesting the issue is specific to the root admin user record (possibly a field mismatch or missing data in the DB document).

### HIGH-2: Dashboard "No Weddings" Message Wrong for Planner Owner

**Severity:** High (UX)  
**Page:** `/admin/planner` (Dashboard)  
**Symptom:** After signing up as a new planner and logging in, the dashboard says: "No weddings assigned — Contact your administrator to get weddings assigned to you."

**Expected:** A new planner owner should see something like "Create your first wedding to get started" with a CTA button. The "contact your administrator" message implies this is a team member, not the owner.

**Note:** The Weddings page (`/admin/weddings`) correctly shows "No weddings found. Create your first wedding to get started." — so this is specifically a Dashboard page issue.

---

## Medium-Severity Issues (Code Review Gaps)

### MED-1: `canAccessSupportInbox()` Overly Permissive

**File:** `app/admin/utils/teamAccess.ts`  
**Issue:** The function returns `true` for ANY team member with a truthy `team_permissions` object, even `{}`. This means a team member with zero actual permissions could still see the Support Inbox.

```typescript
export function canAccessSupportInbox(userProfile?: UserProfile | null): boolean {
  if (!userProfile) return false;
  return Boolean(
    userProfile.is_root_admin ||
    userProfile.is_wedding_planner ||
    (userProfile.is_team_member && userProfile.team_permissions) // {} is truthy!
  );
}
```

**Runbook impact:** The permission matrix in Scenario 7.6 may not accurately reflect actual behavior for edge cases.

### MED-2: Runbook Omits Inbox from "Guest Communications Only" Visible Tabs

**File:** `app/admin/communications/components/CommunicationsTabs.tsx`  
**Issue:** The runbook's Scenario 7.6 Case C (team member with `send_reminders` only) states visible tabs should be "Reminders, Individual, History". But `canAccessAnyCommunicationsInbox()` is `true` when `canSendReminders()` is `true` (via `canAccessGuestCommunications`), which means the **Inbox tab would also be visible**.

### MED-3: Runbook Preconditions Don't Explain Account Creation

**Issue:** The runbook lists TEST_* accounts in `.env` as prerequisites but doesn't explain that these are config-only values — NOT auto-seeded DB records. The `setup_admin_user.py` script only seeds the root admin. Test planner and couple accounts must be created manually through the signup flow (or directly in MongoDB).

**Recommendation:** Add explicit steps to Section 2 (Preconditions) explaining how to create each test account.

### MED-4: Email Verification Blocks Public Signup Login

**Issue:** Users who sign up via the public pricing flow (`registration_source: "public_signup"`) are blocked from logging in until `email_verified` is set to `true`. In local dev without email service configured, there's no way to verify the email through the UI. The runbook should document a workaround (e.g., direct MongoDB update or a dev-mode bypass).

---

## Signup Flow Observations

The end-to-end planner signup flow was tested successfully:
1. Homepage → Pricing Section → "Try Boutique Free" → Signup Modal opens
2. Step 1: Email + Password + Confirm Password → Continue
3. Step 2: First Name, Last Name, Company, Phone, Accept Terms → "Continue to payment"
4. Backend `POST /public/register` succeeds, creates user with `email_verified: false`
5. Redirects to Stripe Checkout (`checkout.stripe.com`)
6. After completing (or skipping) Stripe, login works once `email_verified` is set

**Note:** The signup modal is a multi-step form with good React-hook-form integration. The `form_input` Chrome MCP tool doesn't trigger React state properly — only native keyboard typing works reliably.

---

## What's Working Well

- Planner login flow (for non-root-admin accounts)
- Sidebar navigation: all expected items present (Dashboard, Calendar, Weddings, Packages, Guests, Communications, Gallery, Budget, Money, Forms, Vendors, Notifications, Seating, Team, Support)
- Communications tabs for planner owner: Inbox, Invites, Reminders, Individual, History — all visible and functional
- Wedding creation flow: clean form, proper validation, instant creation
- Couple Access tab: visible on wedding configure page with "+ Invite Couple" button
- Couple invitation: sends successfully, shows "Pending Setup" status with "Resend" option
- Pricing page: all 4 plans rendered correctly (Boutique, Signature, Enterprise, Agency)

---

## Recommendations

1. **Fix CRIT-1 immediately** — the couple setup crash loop blocks the entire couple-facing product. Check the backend logs for the `verify-invite` endpoint and the Next.js server console for hydration errors.
2. **Investigate HIGH-1** — check the root admin user document in MongoDB for missing or malformed fields that the auth service expects.
3. **Fix HIGH-2** — update the Dashboard empty state to detect planner owner vs. team member and show the appropriate message/CTA.
4. **Update the runbook** to include account creation steps and email verification workarounds (MED-3, MED-4).
5. **Add a permission check** for empty `team_permissions` objects in `canAccessSupportInbox()` (MED-1).
6. **Re-run this test suite** after fixing CRIT-1 to complete Scenarios 7.2–7.8.

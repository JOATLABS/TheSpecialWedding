# Deployment Browser E2E Runbook

**Purpose:** manual browser validation for deployment readiness after auth, security, contract-alignment, and portal changes.

**Last Updated:** March 25, 2026

**Primary Browser:** Chrome latest

**Secondary Smoke Browser:** Safari latest on macOS or iOS, or Firefox latest if Safari is unavailable

## 1. Scope

Run this test plan before promoting a build from staging to production when any of these areas changed:

1. Authentication or session handling
2. Planner, couple, or vendor portal login flows
3. Planner inbox or couple inbox rendering
4. Budget templates, campaign stats, or guest management
5. Homepage, features page, or resources/blog public surfaces

This runbook is intentionally risk-based. It focuses on the flows most likely to break deployment readiness:

1. Auth and session persistence for all roles
2. High-risk planner and couple portal workflows
3. Security regressions around token exposure and inbox HTML rendering
4. Frontend/backend contract regressions in budget and advertising surfaces
5. Public marketing and SEO-critical routes

## 2. Environment Setup

Use either staging or a local environment that mirrors staging data closely.

### Local Start Commands

1. Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

2. Start the frontend:

```bash
npm run dev
```

### Required Services

1. MongoDB reachable by the backend
2. Email provider configured if password reset or inbox ingestion must be tested end-to-end
3. Stripe test mode configured if billing and connect flows must be exercised
4. Web push keys configured if push notification flows must be verified

### Required Test Accounts

Do not hardcode secrets into this document. Pull credentials from the secure team source, `.env`, seeded fixtures, or your password manager.

Prepare these accounts before starting:

| Role | Minimum Data Required |
|---|---|
| Wedding planner | Active subscription, at least 1 wedding, at least 1 couple account, at least 1 form, at least 1 budget template, at least 1 inbox thread |
| Root admin | Access to `/admin/platform`, `/admin/saas`, and vendor portal |
| Couple | Existing active account for login tests |
| Couple invite | Fresh invite token for setup-password test |
| Couple reset | Mailbox access or seeded reset token for reset-password test |
| Advertising vendor | Vendor portal credentials with at least 1 campaign and billing record |

### Recommended Test Data

Seed or confirm the following data exists:

1. A wedding with 100+ guests and a mix of RSVP states
2. At least one guest with plus-ones
3. One form assigned to the couple
4. One contract or payment schedule visible in the couple portal
5. One budget template that can be applied to a wedding
6. One advertising campaign with impressions, clicks, conversions, and spend
7. One inbox item created from an external email or seeded email payload

## 3. Tester Preparation

Before starting each role flow:

1. Open a fresh browser profile or incognito window.
2. Open DevTools on the `Application`, `Network`, and `Console` tabs.
3. Clear site data once before the first scenario for that role.
4. Keep screenshots for any failure or unexpected UI state.

### Storage Checks to Run

Use the DevTools console after successful login for each role:

```js
localStorage.getItem('admin_token')
sessionStorage.getItem('admin_token')
localStorage.getItem('couple_token')
localStorage.getItem('vendor_ad_token')
document.cookie.includes('admin_token')
document.cookie.includes('couple_token')
```

Expected result:

1. All storage lookups return `null`
2. The `document.cookie.includes(...)` checks return `false`
3. Authenticated API requests still succeed after hard refresh

## 4. Pass / Fail Standard

A scenario passes only if all of these are true:

1. The UI completes the flow without a visible error state
2. No blocking console errors appear
3. The expected network request succeeds with the expected status
4. The resulting screen state matches the backend action
5. No token is exposed in browser storage

A deployment should be blocked if any of these fail:

1. Planner, couple, or vendor login/logout is broken
2. Session does not survive a hard refresh
3. Session does not clear on logout
4. Inbox HTML executes script or unsanitized markup
5. Budget template apply or campaign stats show obviously incorrect data
6. Public homepage or features page fails to render

## 5. Scenario A: Public Routes, Marketing, and SEO Surfaces

### Objective

Verify that public discovery pages render correctly and remain indexable.

### Steps

1. Load `/`.
2. Verify hero, features section, pricing/CTA sections, and feature images render without broken assets.
3. Open `/features`.
4. Verify the feature list matches the homepage feature section in copy and imagery.
5. Open `/resources`.
6. Open at least one blog detail page from `/resources/blog/[slug]`.
7. Inspect page source or DevTools for title, description, canonical, and social metadata.
8. Load `/robots.txt`.
9. Load `/sitemap.xml`.

### Expected Results

1. No 404 or broken image placeholders on homepage or features page
2. Homepage and features page describe the same current feature set
3. Resources index and blog detail pages load correctly
4. Metadata is present and relevant
5. `robots.txt` and `sitemap.xml` return 200

### Evidence

Capture:

1. Homepage screenshot
2. Features page screenshot
3. One blog detail screenshot
4. Metadata screenshot or copy of the inspected tags

## 6. Scenario B: Planner Login, Session, and Logout

### Objective

Verify planner auth is cookie-backed, survives refresh, and fully clears on logout.

### Steps

1. Open `/admin/login`.
2. Enter valid planner credentials and submit.
3. Confirm redirect to `/admin/planner`.
4. Run the storage checks from Section 3.
5. Hard refresh the page.
6. Navigate to another planner route such as `/admin/guests` or `/admin/forms`.
7. Reload again.
8. Log out using the visible planner logout control.
9. Attempt to open `/admin/planner` directly in the same tab.
10. Attempt login with an invalid password once.

### Expected Results

1. Login succeeds and lands on the planner dashboard
2. No auth token appears in `localStorage` or `sessionStorage`
3. Hard refresh does not log the user out
4. Authenticated routes continue to load after refresh
5. Logout returns the browser to `/admin/login`
6. Direct navigation back to `/admin/planner` after logout redirects to login
7. Invalid credentials show an error and do not create a session

### Network Checks

Verify:

1. `POST /admin/token` returns success on valid credentials
2. `GET /admin/profile` returns success after login
3. `POST /admin/logout` returns success on logout

## 7. Scenario C: Root Admin Access and Restricted Admin Pages

### Objective

Verify the root admin can access platform-only screens and that the session behavior matches planner auth.

### Steps

1. Log in as root admin.
2. Open `/admin/platform`.
3. Open `/admin/saas`.
4. Open `/admin/billing`.
5. Open `/portal/ads` from the same authenticated browser.
6. Hard refresh each page at least once.
7. Log out and verify access is removed.

### Expected Results

1. Root admin can access root-admin pages
2. Root admin can enter the vendor advertising portal
3. Refresh does not break the session
4. Logout removes access everywhere

## 8. Scenario D: Couple Invite, Setup, Login, and Reset Flow

### Objective

Verify both the first-time invite flow and the returning login/reset flows.

### D1. Invite Setup Flow

1. Open `/couple/setup?token=<fresh_invite_token>`.
2. Confirm the invite verifies and the setup form renders.
3. Set a password and submit.
4. Confirm redirect to `/couple/dashboard`.
5. Run the storage checks from Section 3.
6. Hard refresh the dashboard.
7. Log out.

Expected results:

1. Invite token validates successfully
2. Account setup succeeds
3. Couple lands on dashboard immediately
4. No couple token appears in browser storage
5. Refresh keeps the user authenticated
6. Logout removes access

### D2. Returning Login Flow

1. Open `/couple/login`.
2. Sign in with a valid existing couple account.
3. Confirm redirect to `/couple/dashboard`.
4. Hard refresh.
5. Navigate to one form route under `/couple/forms/[formId]`.
6. Log out.
7. Try one invalid password attempt.

Expected results:

1. Valid login succeeds
2. Refresh preserves the session
3. Protected routes remain accessible while logged in
4. Logout removes access and redirects to login on the next protected navigation
5. Invalid credentials do not create a session

### D3. Forgot Password and Reset Flow

1. Open `/couple/forgot-password`.
2. Submit the couple email.
3. Retrieve the reset email or use the seeded reset token.
4. Open `/couple/reset-password?token=<reset_token>`.
5. Confirm the token validates.
6. Set a new password and submit.
7. Confirm redirect to `/couple/dashboard`.
8. Hard refresh.

Expected results:

1. Forgot-password request returns the generic success message
2. Reset link opens the reset screen successfully
3. Reset submission logs the couple in automatically
4. Refresh preserves the authenticated session

## 9. Scenario E: Couple Portal Functional Regression

### Objective

Verify the cookie-backed auth rewrite did not break the main couple portal workflows.

### Steps

1. Log in as the couple.
2. On `/couple/dashboard`, confirm the overview data loads.
3. Open the onboarding modal if it appears and complete or dismiss it.
4. Open the timeline section and add a note if event notes are available.
5. Open the forms section and submit or update one form.
6. Open the inbox section and send one message.
7. Open the registry section and add, edit, then delete one registry item.
8. Open the FAQ section and add, edit, then delete one FAQ item.
9. Open the payments section and confirm contract/payment summary loads if seeded.
10. Reload the dashboard after each write-heavy action at least once.

### Expected Results

1. Dashboard data loads without a 401 or broken state
2. Onboarding progress persists after completion or dismissal
3. Form submissions save and re-open correctly
4. Inbox messages send and appear after refresh
5. Registry and FAQ mutations persist after refresh
6. Payments and contract summary render if the account has seeded data

### Network Checks

Spot-check these requests:

1. `GET /couple/portal/dashboard`
2. `PUT /couple/profile/onboarding`
3. `POST /couple/portal/forms/submit`
4. `POST /couple/portal/messages`
5. `POST|PUT|DELETE /couple/portal/registries/*`
6. `POST|PUT|DELETE /couple/portal/faqs/*`

## 10. Scenario F: Vendor Advertising Portal Login and Session

### Objective

Verify vendor portal auth works without vendor token storage and that root admin fallback access still works.

### Steps

1. Open `/portal/ads`.
2. Log in as an advertising vendor.
3. Confirm redirect or in-place load into the vendor dashboard.
4. Run the storage checks from Section 3, plus confirm `localStorage.getItem('vendor_ad_token')` is `null`.
5. Hard refresh the page.
6. Open Campaigns, Billing, Leads, and Settings.
7. Log out.
8. Repeat the portal entry with a root admin session and confirm access still works.

### Expected Results

1. Vendor login succeeds
2. No vendor auth token is stored in localStorage
3. Refresh preserves the session
4. Key vendor portal sections load
5. Logout removes access
6. Root admin can still access the portal

## 11. Scenario G: Planner Inbox HTML Sanitization

### Objective

Verify inbound HTML is sanitized before rendering in the planner inbox.

### Test Payload

Use a seeded email or send a real test email containing at least these snippets:

```html
<p>Safe content</p>
<script>alert('xss')</script>
<img src="x" onerror="alert('xss')" />
<a href="javascript:alert('xss')">bad link</a>
<strong>Allowed formatting</strong>
```

### Steps

1. Ensure the email is ingested into the planner inbox.
2. Open the relevant planner inbox thread.
3. View the rendered email detail.
4. Watch the browser console while the email renders.
5. Inspect the rendered DOM if needed.

### Expected Results

1. No alert executes
2. No script executes
3. Dangerous attributes and `javascript:` links are stripped
4. Safe formatting such as paragraphs and bold text still renders
5. No new console security errors appear

### Blocker Rule

If any script executes, the build is not deployable.

## 12. Scenario H: Budget Template, Campaign Stats, and Guest Management

### H1. Budget Template Apply Contract

1. Log in as planner.
2. Open `/admin/budget/templates`.
3. Apply an existing budget template to a wedding.
4. Open the target wedding budget view.
5. Confirm the created categories appear and no blank state or crash occurs.

Expected results:

1. The apply action succeeds
2. Budget categories appear correctly
3. No frontend exception occurs after the API response returns

### H2. Advertising Campaign Stats Contract

1. Log in as advertising vendor or root admin in the vendor portal.
2. Open one seeded campaign with known activity.
3. Inspect the campaign stats UI.
4. Confirm impressions, clicks, conversions, CTR, conversion rate, and spend render without `undefined`, `NaN`, or blank totals.

Expected results:

1. Stats load without runtime errors
2. Spend and conversion rate are present
3. Totals look internally consistent

### H3. Guest Management Performance Check

1. Log in as planner.
2. Open `/admin/guests` for a wedding with a large guest list.
3. Use at least three filters in sequence.
4. Sort by RSVP and plus-one related columns if available.
5. Paginate forward and back.
6. Watch for long UI stalls, frozen scrolling, or repeated loading states.

Expected results:

1. Filter and sort interactions remain responsive
2. Pagination works consistently
3. No console errors appear
4. The page does not refetch obviously redundant full-page data on every small interaction

## 13. Scenario I: Platform Error Detail and Acknowledge Flow

### Objective

Verify root-admin platform diagnostics still work after the auth cleanup.

### Steps

1. Log in as root admin.
2. Open `/admin/platform`.
3. Switch to the errors tab.
4. Open one error detail page.
5. Acknowledge the error.
6. Return to the list and confirm the state updates.

### Expected Results

1. Error list loads
2. Error detail page loads
3. Acknowledge action succeeds
4. The list and detail state stay consistent after refresh

## 14. Cross-Role Isolation Check

Run this after planner, couple, and vendor flows all pass individually.

### Steps

1. In one browser profile, log in as planner and stay logged in.
2. In a second incognito profile, log in as couple.
3. In a third profile, log in as vendor or root admin vendor portal access.
4. Refresh all three sessions independently.
5. Log out from only one profile.
6. Confirm the other two sessions remain intact.

### Expected Results

1. Sessions do not overwrite each other
2. Logout in one profile does not log out the others
3. Each role only sees its own allowed routes

## 15. Console and Network Failure Rules

Mark the run as failed if any of these appear:

1. Repeated 401s after a successful login
2. Redirect loops between login and a protected route
3. React hydration errors on the tested route
4. `undefined`, `NaN`, or empty totals in budget or campaign stats
5. Console errors on send/save flows
6. Any evidence of JS-readable auth token persistence

## 16. Final Go / No-Go Checklist

Approve deployment only if all items below are true:

1. Planner login, refresh persistence, and logout pass
2. Root admin login and platform pages pass
3. Couple setup, login, reset, refresh persistence, and logout pass
4. Vendor portal login, refresh persistence, and logout pass
5. Planner inbox sanitization passes with no script execution
6. Couple portal forms, inbox, registry, and FAQ flows pass
7. Budget template apply passes
8. Advertising campaign stats display correctly
9. Guest management remains responsive on a large wedding
10. Homepage, features, resources, `robots.txt`, and `sitemap.xml` pass
11. No auth token is stored in browser storage
12. No blocking console or network issues remain

## 17. Test Report Template

Use this template for each run:

```md
# Browser E2E Report

- Build/commit:
- Environment:
- Browser:
- Tester:
- Date:

## Summary

- Pass:
- Fail:
- Blocked:

## Failures

1. Scenario:
   Route:
   Steps to reproduce:
   Expected:
   Actual:
   Screenshot:
   Console/network notes:

## Go / No-Go

- Decision:
- Reason:
```

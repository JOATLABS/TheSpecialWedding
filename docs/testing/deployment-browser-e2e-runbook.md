# Deployment Browser E2E Runbook

**Purpose:** manual browser validation for deployment readiness after auth, security, contract-alignment, and portal changes.

**Last Updated:** March 26, 2026

**Primary Browser:** Chrome latest

**Secondary Smoke Browser:** Safari latest on macOS or iOS, or Firefox latest if Safari is unavailable

## 1. Scope

Run this test plan before promoting a build from staging to production when any of these areas changed:

1. Authentication or session handling
2. Planner, couple, or vendor portal login flows
3. Planner inbox or couple inbox rendering
4. Budget templates, campaign stats, or guest management
5. Homepage, pricing, features page, or resources/blog public surfaces

This runbook is intentionally risk-based. It focuses on the flows most likely to break deployment readiness:

1. Auth and session persistence for all roles
2. High-risk planner and couple portal workflows
3. Security regressions around token exposure and inbox HTML rendering
4. Frontend/backend contract regressions in budget and advertising surfaces
5. Public marketing, pricing, and SEO-critical routes

## 1A. Testing Principle

This runbook is for functional end-to-end validation, not visual QA alone.

Use visual checks only as the first signal that a screen rendered. Do not mark a scenario as passed just because the UI looks correct. A scenario is only valid when you confirm:

1. the user can actually perform the intended action
2. the correct request is sent
3. the backend accepts it successfully
4. the updated state can be reread after refresh
5. persisted data matches the expected result when DB access is available

For read-only screens such as homepage, features, resources, and dashboard views, the test still needs to confirm more than appearance:

1. the page loads without runtime or network failures
2. the data shown matches the active backend configuration or seeded fixture
3. links, filters, tabs, modals, and retry states behave correctly
4. refresh and direct-entry routes still work

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
8. One planner account with no active subscription, or an expired/cancelled subscription, for billing preselection testing
9. One active public subscription plan ID that can be inserted into `/admin/planner/billing?plan=<plan_id>&interval=yearly`

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

Important:

1. Do not treat `document.cookie` as proof that cookie-backed auth is broken. `HttpOnly` auth cookies are intentionally invisible to JavaScript and should not appear there.
2. If you need to verify the auth cookie itself, use the browser `Application` panel or inspect the `Set-Cookie` header on login or refresh responses in the `Network` tab.
3. The pass condition is:
   no auth token in `localStorage` or `sessionStorage`, successful authenticated rereads after refresh, and loss of access after logout.

### Write Validation Ladder

For any frontend action that is supposed to create or update data, validate it in this order:

1. Confirm the UI accepts the action and shows the expected success state.
2. Confirm the mutation request returns `200`, `201`, or the expected success status in the Network tab.
3. Confirm the response body contains the expected identifiers, counts, or confirmation message.
4. Hard refresh the page and confirm the new state is still present from a fresh read.
5. If you have MongoDB access, verify the persisted document in Compass or `mongosh`.

If step 1 passes but steps 2 through 5 do not, treat it as a failed deployment check. The goal is not just that the frontend looked successful for one render, but that the write actually persisted and can be read back.

### Optional Persistence Map

Use this map when you need to prove that a frontend action updated the database correctly. This app uses MongoDB collections and embedded documents rather than SQL tables.

| Flow | Mutation to Watch | Fresh Read to Confirm | Mongo Persistence Target |
|---|---|---|---|
| Couple onboarding completion | `PUT /couple/profile/onboarding` | `GET /couple/profile/onboarding` after refresh | `couple_users` document for that couple. Check `onboarding_completed`, `onboarding_completed_at`, `onboarding_steps_completed`. |
| Couple form submission | `POST /couple/portal/forms/submit` | Reload `/couple/forms/[formId]` or refetch the form submission | `form_submissions` document keyed by `form_id` and `submitted_by`. Check `responses`, `updated_at`, `submitted_by_type: "couple"`. |
| Couple message send | `POST /couple/portal/messages` | `GET /couple/portal/messages` after refresh | `couple_messages` document keyed by `wedding_id`. Check `sender_role: "couple"`, `sender_email`, `content`, `created_at`. |
| Couple registry add/edit/delete | `POST|PUT|DELETE /couple/portal/registries/*` | `GET /couple/portal/registries` after refresh | Embedded `registries` array on the related `weddings` document. |
| Couple FAQ add/edit/delete | `POST|PUT|DELETE /couple/portal/faqs/*` | `GET /couple/portal/faqs` after refresh | Embedded `faqs` array on the related `weddings` document. |
| Budget template apply | `POST /admin/weddings/{wedding_id}/budget/apply-template` | Reload the wedding budget screen and confirm categories | `budget_categories` collection for that `wedding_id`, plus the `weddings` document fields `total_budget` and `budget_template_applied`. |
| Public pricing read path | `GET /public/subscription-plans` | Compare homepage cards and signup modal plan choices | `subscription_plans` collection filtered to active plans. Public response should match active plan names, prices, and feature highlights. |
| Resources/blog public read path | `GET /api/v1/blog/articles`, `GET /api/v1/blog/articles/slug/{slug}` | Reload `/resources` and the direct `/resources/blog/[slug]` page | `blog_articles` collection. Article must have `status: "published"` and the matching `slug`. |

### Optional MongoDB Check Tips

If you have direct DB access, prefer verifying by business key instead of copying raw `_id` values from the UI:

1. Couple onboarding: search `couple_users` by `email`
2. Couple form submission: search `form_submissions` by `form_id` and `submitted_by`
3. Couple messages: search `couple_messages` by `wedding_id` and recent `created_at`
4. Registry and FAQ changes: inspect the target `weddings` document by `_id`
5. Budget template apply: inspect `budget_categories` by `wedding_id`
6. Public pricing: inspect active documents in `subscription_plans`
7. Public blog/resources: inspect published documents in `blog_articles`

### Optional `mongosh` Examples

Use these only if you have local or staging MongoDB access. Replace placeholders with real values from the tested scenario.

```javascript
// Couple onboarding
db.couple_users.findOne(
  { email: "couple@example.com" },
  { onboarding_completed: 1, onboarding_completed_at: 1, onboarding_steps_completed: 1 }
)

// Couple form submission
db.form_submissions.findOne(
  { form_id: "FORM_ID", submitted_by: "couple@example.com" },
  { responses: 1, updated_at: 1, submitted_by_type: 1 }
)

// Couple message send
db.couple_messages.find(
  { wedding_id: "WEDDING_ID", sender_email: "couple@example.com" }
).sort({ created_at: -1 }).limit(3)

// Registry / FAQ persistence on the wedding document
db.weddings.findOne(
  { _id: "WEDDING_ID" },
  { registries: 1, faqs: 1, total_budget: 1, budget_template_applied: 1 }
)

// Budget template apply
db.budget_categories.find(
  { wedding_id: "WEDDING_ID" }
).sort({ created_at: -1 }).limit(20)

// Public pricing
db.subscription_plans.find(
  { is_active: true },
  { name: 1, price_monthly: 1, price_yearly: 1, is_featured: 1, display_order: 1 }
).sort({ display_order: 1 })

// Published blog articles
db.blog_articles.find(
  { status: "published" },
  { slug: 1, title: 1, updated_at: 1, published_at: 1 }
).sort({ published_at: -1 }).limit(20)
```

If you do not have DB access, the minimum acceptable proof is:

1. successful mutation response in the Network tab
2. hard refresh
3. fresh read endpoint or page still showing the updated state
4. no console or network errors during the reread

## 4. Pass / Fail Standard

A scenario passes only if all of these are true:

1. The UI completes the flow without a visible error state
2. The tested functionality behaves correctly, not just visually
3. No blocking console errors appear
4. The expected network request succeeds with the expected status
5. The resulting screen state matches the backend action
6. No token is exposed in browser storage

A deployment should be blocked if any of these fail:

1. Planner, couple, or vendor login/logout is broken
2. Session does not survive a hard refresh
3. Session does not clear on logout
4. Inbox HTML executes script or unsanitized markup
5. Budget template apply or campaign stats show obviously incorrect data
6. Public homepage or features page fails to render
7. A screen looks correct but the underlying action, reread, or persistence check fails

## 5. Scenario A: Public Routes, Marketing, and SEO Surfaces

### Objective

Verify that public discovery pages function correctly, render correctly, and remain indexable.

### Steps

1. Load `/`.
2. Verify hero, features section, pricing/CTA sections, and feature images render without broken assets.
3. In the homepage pricing section, confirm the visible plan names and prices match the currently active root-admin-configured plans.
4. Click one non-Agency pricing CTA such as `Start your free trial`.
5. Confirm the signup modal opens with the clicked plan preselected.
6. Click the Agency pricing CTA and confirm it opens the sales email flow or `mailto:` target.
7. Open `/features`.
8. Verify the feature list matches the homepage feature section in copy and imagery.
9. Open `/resources`.
10. In the split-panel blog experience, click one article card and confirm the reader panel loads that article.
11. Use `Open article page` from one card and confirm the direct `/resources/blog/[slug]` page loads.
12. If the blog API is unavailable in the environment, or can be simulated safely, confirm `/resources` shows an explicit unavailable state with a retry action instead of a misleading empty-results state.
13. Inspect page source or DevTools for title, description, canonical, and social metadata.
14. Load `/robots.txt`.
15. Load `/sitemap.xml`.
16. Open one blog URL returned by `sitemap.xml` and confirm it resolves to a live article page.

### Expected Results

1. No 404 or broken image placeholders on homepage or features page
2. Homepage pricing reflects the current active plan configuration
3. Clicking a non-Agency homepage pricing CTA opens the signup modal with the correct plan selected
4. Agency CTA opens the expected sales email flow
5. Homepage and features page describe the same current feature set
6. Resources split-panel and direct blog detail pages both load correctly
7. If the blog feed is unavailable, `/resources` shows an explicit unavailable state and retry action rather than pretending there are zero articles
8. Metadata is present and relevant
9. `robots.txt` and `sitemap.xml` return 200
10. Blog URLs emitted by `sitemap.xml` resolve to live article pages

### Evidence

Capture:

1. Homepage screenshot
2. Pricing modal screenshot after clicking a plan CTA
3. Features page screenshot
4. One blog detail screenshot
5. Metadata screenshot or copy of the inspected tags

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

### B2. Planner Billing Preselection Flow

Use a planner account without an active subscription, or with an expired/cancelled subscription, for this check.

1. While authenticated as that planner, open `/admin/planner/billing?plan=<valid_plan_id>&interval=yearly`.
2. Confirm the plan-selection state appears instead of the subscribed dashboard.
3. Confirm the requested plan card is visually highlighted.
4. Confirm the helper banner mentions the selected plan and the yearly interval.
5. Confirm the highlighted card button reads `Continue with yearly`.
6. Click the highlighted button.
7. Inspect the checkout-session network request body.

Expected results:

1. The selected-plan banner renders without a crash or blank state
2. The correct plan card is highlighted
3. The highlighted card shows the requested interval and CTA copy
4. `POST /stripe/create-checkout-session` sends the requested `plan_id` and `billing_interval`
5. The user is redirected into the billing checkout flow successfully

## 7. Scenario C: Root Admin Access and Restricted Admin Pages

### Objective

Verify the root admin can access platform-only screens and that the session behavior matches planner auth.

### Steps

1. Log in as root admin.
2. Open `/admin/platform`.
3. Open `/admin/saas`.
4. Open `/admin/billing`.
5. Open `/portal/ads` from the same authenticated browser.
6. On `/admin/saas`, confirm the active subscription plans shown there match the public homepage pricing cards.
7. Hard refresh each page at least once.
8. Log out and verify access is removed.

### Expected Results

1. Root admin can access root-admin pages
2. Root admin can enter the vendor advertising portal
3. Root-admin-managed plan configuration matches the public pricing surface
4. Refresh does not break the session
5. Logout removes access everywhere

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
3. The budget card reflects the same wedding budget configured from the planner side
4. Form submissions save and re-open correctly
5. Inbox messages send and appear after refresh
6. Registry and FAQ mutations persist after refresh
7. Payments and contract summary render if the account has seeded data

### Network Checks

Spot-check these requests:

1. `GET /couple/portal/dashboard`
2. `PUT /couple/profile/onboarding`
3. `POST /couple/portal/forms/submit`
4. `POST /couple/portal/messages`
5. `POST|PUT|DELETE /couple/portal/registries/*`
6. `POST|PUT|DELETE /couple/portal/faqs/*`

### Persistence Validation for Scenario E

Use these checks during the couple portal flow:

1. Onboarding:
   Confirm `PUT /couple/profile/onboarding` succeeds, refresh the dashboard, and verify the modal stays completed or dismissed.
   If you have DB access, confirm the `couple_users` document updated `onboarding_completed`, `onboarding_completed_at`, and `onboarding_steps_completed`.
2. Budget:
   Confirm the budget figures on `/couple/dashboard` match the planner-side wedding budget before approving the build.
   The couple dashboard should follow the planner budget source of truth: `weddings.total_budget` as the overall total, with spend derived from `budget_categories.actual_spent`.
   If you have DB access, compare the dashboard against the target `weddings` document and related `budget_categories` records for that `wedding_id`.
   If `weddings.total_budget` is set and the couple dashboard still shows `$0`, fail the build.
3. Forms:
   Confirm the submit response succeeds, reload `/couple/forms/[formId]`, and verify the saved answers rehydrate into the form.
   If you have DB access, confirm the `form_submissions` document for that `form_id` and `submitted_by` contains the updated `responses`.
4. Messages:
   Confirm the message appears immediately, then refresh and verify it still appears in the thread history.
   If you have DB access, confirm a new `couple_messages` document exists with the matching `wedding_id`, `sender_email`, and `content`.
5. Registry:
   After add, edit, and delete, refresh the dashboard each time and verify the registry list matches the latest action.
   If you have DB access, confirm the `weddings.registries` array reflects the final state.
6. FAQ:
   After add, edit, and delete, refresh the dashboard each time and verify the FAQ list matches the latest action.
   If you have DB access, confirm the `weddings.faqs` array reflects the final state.

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

Validation detail:

1. Inspect the `POST /admin/weddings/{wedding_id}/budget/apply-template` response and confirm it reports `categories_created` greater than `0`.
2. Reload the budget view and verify the newly created categories are still present from a fresh read.
3. If you have DB access, confirm new `budget_categories` documents exist for that `wedding_id` and the `weddings` document reflects `total_budget` and `budget_template_applied`.

### H2. Advertising Campaign Stats Contract

1. Log in as advertising vendor or root admin in the vendor portal.
2. Open one seeded campaign with known activity.
3. Inspect the campaign stats UI.
4. Confirm impressions, clicks, conversions, CTR, conversion rate, and spend render without `undefined`, `NaN`, or blank totals.

Expected results:

1. Stats load without runtime errors
2. Spend and conversion rate are present
3. Totals look internally consistent

Validation detail:

1. Confirm the stats values do not change unexpectedly across a hard refresh unless the underlying seeded data changed.
2. If you have DB or seed-data access, compare the rendered totals against the known campaign fixture before approving the build.

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

Validation detail:

1. In the Network tab, verify guest-list pagination and filter changes do not trigger unrelated wedding-wide data reloads on every click.
2. Confirm the visible guest rows after each filter/sort action still match the RSVP and plus-one data shown in the row UI.

## 13. Scenario I: Platform Error Detail and Acknowledge Flow

### Objective

Verify root-admin platform diagnostics still work after the auth cleanup.

### Steps

1. Log in as root admin.
2. Open `/admin/platform`.
3. Set the shared `Error window` control to `24 hours`, then note the counts in the health summary.
4. Switch to the errors tab.
5. Confirm the `Total Errors`, `Critical`, `Warnings`, and `Other Severities` cards reconcile with the selected window and filters.
6. Open one error detail page.
7. Acknowledge the error.
8. Return to the list and confirm the state updates.

### Expected Results

1. Error list loads
2. Health summary and Errors tab use the same selected error window
3. With `All Severities` and `All Status`, `Total Errors` equals `Critical + Warnings + Other Severities`
4. Error detail page loads
5. Acknowledge action succeeds
6. The list and detail state stay consistent after refresh

### Scope Validation

Validate the scope explicitly before marking this scenario passed.

1. The `Error window` selector controls both the `Health` tab error summary and the `Errors` tab list.
2. With `All Severities` and `All Status`, the health-tab `Total Errors` value should match the Errors-tab `Total Errors` value for the same selected window.
3. Inside the `Errors` tab, the cards summarize the full filtered result set, not just the visible page.
4. If you change `Severity` or `Status`, verify the cards and total update together for the filtered result.
5. A valid pass now requires the counts to reconcile for the selected window and active filters.

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
10. Homepage pricing CTA, signup-plan preselection, and Agency sales CTA pass
11. Planner billing preselection via `plan` and `interval` passes
12. Homepage, features, resources, `robots.txt`, and `sitemap.xml` pass
13. No auth token is stored in browser storage
14. No blocking console or network issues remain

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

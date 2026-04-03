# Sprint 1 Review: Couple Portal

**Date:** 2026-03-22
**Scope:** UX Copy Review + Engineering Code Review
**Files Reviewed:** 8 files (4 frontend, 4 backend)

---

## Part 1: UX Copy Review

### Overall Assessment: B+

The portal has a warm, wedding-appropriate tone with clean visual hierarchy. The navy/gold brand identity is consistent across all screens. Several copy improvements would sharpen clarity, reduce anxiety, and improve empty-state guidance.

---

### Login Page (`couple/login/page.tsx`)

**What works well:**
- "Welcome Back" heading sets a warm return-visit tone
- "Your planner will send you an invitation" is clear and avoids a dead-end for users without accounts
- "Powered by The Special Wedding" footer is appropriately subtle

**Recommended changes:**

| Element | Current | Recommended | Rationale |
|---------|---------|-------------|-----------|
| Page title | "Wedding Portal" | "Your Wedding Portal" | Possessive language makes it feel personal |
| Email placeholder | "your@email.com" | "name@example.com" | Avoid "your" — it reads oddly when they're typing their actual email |
| Loading button | (spinner only, no text) | "Signing in..." | Users need text feedback during loading, not just a spinner |
| Error toast (catch) | "Something went wrong. Please try again." | "We couldn't reach the server. Check your connection and try again." | Be specific about cause when possible |
| No "Forgot password" link | (missing) | Add "Forgot your password?" link below form | Couples WILL forget passwords. Even if the flow isn't built yet, the link should exist with a "Contact your planner" message |

---

### Setup Page (`couple/setup/page.tsx`)

**What works well:**
- "Welcome, {coupleName}!" with personalized names is an excellent first impression
- Green verification banner ("Invitation verified for email") reduces anxiety
- "Invalid or Expired Link" error state is clear with actionable guidance
- "Already have an account? Sign in" escape hatch on error state is good

**Recommended changes:**

| Element | Current | Recommended | Rationale |
|---------|---------|-------------|-----------|
| Subheading | "Set up your wedding portal account" | "Create a password to access your wedding details" | More specific about what they're doing and what they get |
| Password placeholder | "At least 8 characters" | Keep — this is good | Inline hint is effective |
| CTA button | "Set Up My Account" | "Create My Account" | "Set up" is vague; "Create" is a clearer action verb |
| Success toast | "Account setup complete! Welcome!" | "You're all set! Welcome to your wedding portal." | More celebratory, matches the occasion |
| Loading state text | "Verifying your invitation..." | Good as-is | Sets clear expectation |
| No password strength indicator | (missing) | Add visual strength meter | Reduces failed attempts and builds confidence |

---

### Dashboard (`couple/dashboard/page.tsx`)

**What works well:**
- Countdown hero section is emotionally engaging — "X days until your wedding" is exactly right
- "COUNTING DOWN" label in gold is on-brand
- Archived banner is warm: "You can still view your wedding details and memories"
- Tab labels are clear and concise
- Badge counts on tabs (pending forms, payment count) are good wayfinding

**Recommended changes:**

| Element | Current | Recommended | Rationale |
|---------|---------|-------------|-----------|
| Loading text | "Loading your wedding portal..." | "Getting your wedding details ready..." | More active, feels like something is happening |
| Error state | "Could not load your dashboard" | "We had trouble loading your dashboard" | Softer phrasing, less blame-sounding |
| Empty timeline | "No events scheduled yet" | "No events scheduled yet — your planner will add them as details are confirmed" | Empty states should always explain what happens next |
| Empty payments | "No payment schedule yet" / "Your planner will set this up soon" | Good as-is | Two-line pattern works well |
| Empty forms | "No forms to fill out yet" / "Your planner will share forms when needed" | Good as-is | Consistent with payments pattern |
| Empty updates | "No updates yet" / "Your planner will share updates here" | Good as-is | Consistent pattern |
| Tab: "Updates" count | Shows total update count | Show unread count instead (or nothing if no unread tracking yet) | Total count is less useful; "5 updates" when you've seen them all is misleading |
| Forms CTA | "Fill Out" / "Edit" | "Fill Out" / "Update Responses" | "Edit" is too generic; "Update Responses" matches the form context |
| Stat card label | "Guests Invited" | "Invited" | The Users icon + number already implies guests; shorter label scans better |
| Budget section label | "Budget Progress" | "Your Budget" | "Progress" implies a goal to complete; budgets are limits, not targets |
| Payment status: "succeeded" | Shows "Paid" | Good — mapping "succeeded" → "Paid" is correct | Stripe internal status correctly humanized |
| Update attribution | "From: planner@email.com" | "From: {planner_name}" | Show name, not email; email looks cold |
| Countdown: past wedding | Not shown (days > 0 check) | Show "Your wedding day has arrived!" or post-wedding message | Currently shows nothing if days <= 0 and not archived |

---

### Form Page (`couple/forms/[formId]/page.tsx`)

**What works well:**
- "Previously submitted — you can update your responses" is clear and reassuring
- Back button to dashboard is properly placed
- Submit button dynamically changes: "Submit Form" vs "Update Responses"
- Red asterisk for required fields is standard and clear

**Recommended changes:**

| Element | Current | Recommended | Rationale |
|---------|---------|-------------|-----------|
| Error: form not found | "Form not found" | "This form isn't available. It may have been removed by your planner." | Explain possible cause; avoid technical "not found" language |
| Error: load failed | "Failed to load form" | "We couldn't load this form. Please try again or contact your planner." | Add actionable guidance |
| Success toast | "Form submitted successfully!" | "Responses submitted! Your planner has been notified." | Confirm the outcome the user cares about — that the planner will see it |
| Checkbox label fallback | "Yes" | Consider: use field.label as the clickable text instead | "Yes" is meaningless without context; the label should be the interactive text |
| Select default option | "Select an option" | "Choose one..." or "Select..." | Slightly more conversational |

---

### Invitation Email (in `couple_invite.py`)

**What works well:**
- Branded header with THE SPECIAL WEDDING in gold
- "Your wedding planner {name} has invited you" establishes context
- "This link expires in 7 days" sets expectation
- CTA "Set Up Your Account" matches the setup page

**Recommended changes:**

| Element | Current | Recommended | Rationale |
|---------|---------|-------------|-----------|
| Subject line | "You're Invited to Your Wedding Portal - {couple_names}" | "Your wedding portal is ready — set up your account" | Action-oriented subject lines get higher open rates |
| Body: feature list | "view your wedding details, track payments, review contracts, and stay connected with your planner" | "view your wedding timeline, track payments, fill out forms, and get updates from your planner" | Match the actual features available in Sprint 1 (contracts not interactive yet) |
| Resend subject | "Reminder: Set Up Your Wedding Portal" | "Quick reminder: your wedding portal is waiting" | Warmer, less transactional |

---

## Part 2: Engineering Code Review

### Overall Rating

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Security | B | Good fundamentals, a few gaps |
| Performance | B+ | Clean async patterns, one N+1 concern |
| Correctness | B | Mostly solid, some edge cases missed |
| Maintainability | B+ | Clean structure, some duplication |

---

### Security

**Positive:**
- Bcrypt rounds=12 for password hashing — industry standard
- `secrets.token_urlsafe(48)` for invite tokens — cryptographically secure, good entropy
- Single-use invite tokens (nullified after setup)
- Timing attack mitigation with `DUMMY_PASSWORD_HASH` in `auth_utils.py`
- JWT scoped with `role: "couple"` for access control
- Wedding access checked via `check_wedding_access` in planner endpoints

**Issues found:**

| Severity | File | Issue | Fix |
|----------|------|-------|-----|
| **HIGH** | `couple_auth.py` L81 | JWT token doesn't include `wedding_id` in payload. The couple's wedding_id is only resolved via DB lookup in `get_authenticated_couple()`, but there's no check that the couple's wedding_id hasn't been tampered with in the DB. If a couple record's `wedding_id` is changed (admin error, injection), they'd see another wedding's data. | Include `wedding_id` in JWT payload and cross-check against DB on each request |
| **HIGH** | `couple_auth.py` L104 | Login doesn't use `DUMMY_PASSWORD_HASH` for timing attack mitigation when user not found. The `verify_password` call is skipped entirely if `couple` is None (line 106-107). | Add `verify_password(data.password, DUMMY_PASSWORD_HASH)` before raising 401 when user not found |
| **MEDIUM** | `couple_portal.py` L257-315 | The `create_update` endpoint does manual JWT extraction but doesn't use `check_wedding_access()` to verify the planner actually owns the wedding. Any authenticated planner could post updates to any wedding. | Add `check_wedding_access(current_user, data.wedding_id)` check |
| **MEDIUM** | `couple_invite.py` L186 | `setup_link` is returned in the API response. If the planner frontend exposes this in logs or network tab, the invite token is leaked. | Only return `setup_link` if `email_sent` is False (fallback scenario) |
| **LOW** | `couple_auth.py` L49 | `setup-password` endpoint has no rate limiting. An attacker could brute-force invite tokens. | Add rate limiting decorator (same pattern as login endpoints) |
| **LOW** | `couple_portal.py` L149-152 | Form submission doesn't verify the form is actually `shared_with_couple: true`. Any form for the wedding_id is accessible. | Add `$or` filter matching the same criteria used in `_get_shared_forms()` |

---

### Performance

**Positive:**
- Async/await throughout with Motor — no blocking calls
- Service layer aggregates data in a single `get_portal_dashboard()` call
- Pagination on updates endpoint (skip/limit)
- Budget calculation iterates in-memory (small dataset per wedding)

**Issues found:**

| Severity | File | Issue | Fix |
|----------|------|-------|-----|
| **MEDIUM** | `couple_portal_service.py` L188-218 | `_get_shared_forms()` has an N+1 query: for each form, it does a separate `find_one` on `form_submissions` to check if the couple submitted it. For 10 forms, that's 10 additional queries. | Use a single `find()` on `form_submissions` with `form_id: {$in: form_ids}` and build a lookup dict |
| **LOW** | `couple_portal_service.py` L83-112 | Guest stats runs 3 separate `count_documents` queries (total, confirmed, declined). | Use a single aggregation pipeline with `$group` to get all counts in one query |
| **LOW** | `couple_portal.py` L55-80 | Dashboard endpoint calls `get_portal_dashboard()` which runs ~7 DB queries serially. | Consider `asyncio.gather()` for parallel execution of independent queries (guest stats, budget, contracts, forms, updates) |
| **INFO** | No indexes defined | `couple_users` collection has no explicit indexes for `email`, `invite_token`, or `wedding_id`. | Add compound index `{email: 1, wedding_id: 1}` and single index `{invite_token: 1}` in `database_indexes.py` |

---

### Correctness

**Positive:**
- Proper error handling with try/catch blocks in service methods
- Graceful fallbacks (empty arrays, zero stats) when data is missing
- Upsert pattern for form submissions (update if exists, insert if not)
- Proper email normalization with `.lower().strip()`

**Issues found:**

| Severity | File | Issue | Fix |
|----------|------|-------|-----|
| **HIGH** | `couple_portal_service.py` L58-65 | Events serialization strips `order_of_events` and `event_notes` — only passes `type`, `date`, `details`. The new model fields won't reach the frontend. | Add `"order_of_events": e.get("order_of_events", [])` and `"event_notes": e.get("event_notes", [])` to the event serialization |
| **HIGH** | `couple_portal.py` L83-102 | Same issue in `get_events()` endpoint — only returns `type`, `date`, `details`. | Include `order_of_events` and `event_notes` in the response |
| **MEDIUM** | `couple_auth.py` L104 | Login normalizes email with `.lower().strip()` but `setup-password` (line 56-58) doesn't normalize — it only searches by token. The email stored in the couple record might not be normalized if the planner typed it with caps. | The invite flow normalizes (line 76 of `couple_invite.py`), so this is mitigated, but the login should also normalize on the stored side |
| **MEDIUM** | `couple_portal_service.py` L92-95 | RSVP query uses `attending: True/False` but the existing RSVP model may use different field names or structure. | Verify against `app/models/rsvp.py` to ensure field name alignment |
| **LOW** | `couple_portal_service.py` L144-147 | Contract lookup first tries `couple.email` match, then falls back to any contract for the wedding. If a wedding has multiple contracts (vendor contracts), the fallback could return the wrong one. | Add a `type: "couple"` or `is_primary: true` filter, or match on `package_name` |
| **LOW** | Dashboard `page.tsx` L19-31 | Dashboard defines its own `WeddingEvent` interface locally instead of importing from `types/wedding.ts`. The local type is missing `order_of_events` and `event_notes`. | Import from `@/types/wedding` instead of re-declaring |

---

### Maintainability

**Positive:**
- Clean file separation: auth, invite, portal, service
- Consistent error response format (HTTPException with `detail`)
- Pydantic models for all request bodies with validation
- Service layer pattern separates business logic from routes
- Well-documented docstrings on all endpoints

**Issues found:**

| Severity | File | Issue | Fix |
|----------|------|-------|-----|
| **MEDIUM** | `couple_auth.py` + `couple_portal.py` | Auth extraction (`get_authenticated_couple`) is duplicated. `couple_auth.py` has its own version in `get_couple_profile()`, and `couple_portal.py` has `get_authenticated_couple()`. | Extract into a shared dependency (FastAPI `Depends` pattern like `require_team_or_planner`) |
| **MEDIUM** | `couple_invite.py` L131-168 + L239-258 | Email HTML templates are duplicated (invite + resend). | Extract into a shared template function or use the existing email service's template system |
| **LOW** | `couple_invite.py` L22-28 + `couple_auth.py` L24-30 | `InviteCoupleRequest` is defined in both files with identical fields. | Remove from `couple_auth.py` (it's not used there — only the `CoupleSetupPasswordRequest` and `CoupleLoginRequest` are used) |
| **LOW** | `couple_portal.py` L270-293 | `create_update` does manual JWT extraction instead of using FastAPI's `Depends()` pattern. | Refactor to use `Depends(require_team_or_planner)` like the invite endpoints |

---

## Summary: Critical Fixes Before Sprint 2

**Must-fix (blocking):**

1. **Event serialization** — `order_of_events` and `event_notes` are stripped from API responses in both `couple_portal_service.py` and `couple_portal.py`. Sprint 2's order-of-events feature won't work without this fix.

2. **Timing attack on login** — Add `DUMMY_PASSWORD_HASH` comparison when couple not found in login endpoint.

3. **Wedding access check on updates** — `create_update` endpoint allows any planner to post to any wedding. Add `check_wedding_access()`.

**Should-fix (before launch):**

4. **N+1 in shared forms** — Single query for form submissions instead of per-form lookup.
5. **Shared auth dependency** — Extract `get_authenticated_couple` into a proper FastAPI `Depends()`.
6. **Form access control** — Verify form is actually shared with couple before allowing submission.
7. **Dashboard types** — Import from `types/wedding.ts` instead of local re-declaration.
8. **Database indexes** — Add indexes for `couple_users` and `couple_updates`.

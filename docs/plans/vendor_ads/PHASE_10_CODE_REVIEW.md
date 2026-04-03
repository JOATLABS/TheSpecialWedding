# Phase 10 Code Review — Vendor Signup / Onboarding Flow

**Date:** 2026-03-23
**Scope:** Map every existing touchpoint, identify reusable infrastructure, and catalog what must be created for the Vendor Signup/Onboarding Flow.
**Verdict:** 🟡 Request Changes — ~60-70% infrastructure exists; critical gaps in signup endpoint, approval workflow, temp password flow, and profile completeness gate.

---

## Summary

The mockup spec (V1) defines a clear 7-step flow: vendor submits signup → pending approval screen → root admin notification → admin approves → temp password email → vendor signs in & changes password → profile completeness gate before campaign creation. Phases 1–9 built substantial infrastructure that Phase 10 can leverage: the `advertising_vendor` role, vendor portal auth, bulk account creation logic, notification service, email service, and platform config flags. However, no public-facing signup path exists — all vendor creation is admin-initiated via bulk import. The approval workflow, temp password generation, and profile completeness gate are entirely absent.

---

## Mockup Spec (V1, lines 1111–1116)

| Step | Description | Status |
|------|-------------|--------|
| 1 | Vendor arrives at `vendor.thespecialwedding.io` signup page, submits basic info (name, email, category, location) | 🔴 Not built |
| 2 | "Thank you, your account is pending approval" confirmation screen | 🔴 Not built |
| 3 | Root admin gets in-app notification (bell icon) of new signup | 🟡 Notification service exists, no signup trigger |
| 4 | Admin reviews and approves vendor | 🔴 No approval endpoint (only campaign approval exists) |
| 5 | Temp password email sent to vendor on approval | 🔴 Not built |
| 6 | Vendor signs in, changes password, completes profile | 🟡 Login page + change_password exist, no force-change flow |
| 7 | Profile completeness gate: business_name, email, service_category, location, ≥1 image required before campaign creation | 🔴 Not built |

**Platform Config flags** (already in `ad_platform_config_service.py`):

| Flag | Default | Purpose |
|------|---------|---------|
| `vendor_domain` | `vendor.thespecialwedding.io` | Signup URL domain |
| `auto_approve_signups` | `False` | Skip manual admin approval |
| `require_profile_completion` | `True` | Enforce completeness gate |
| `min_images_for_campaign` | `1` | Minimum images before campaign creation |

---

## What Exists and Is Ready to Use

### 1. Auth System — `advertising_vendor` Role

| File | What's Ready |
|------|-------------|
| `app/dependencies/auth_extended.py:83` | `is_advertising_vendor = (role == "advertising_vendor")` — role check on every request |
| `app/api/vendor_campaigns.py:44-55` | `require_advertising_vendor()` dependency — gates all vendor portal endpoints |
| `app/portal/ads/layout.tsx:160-176` | `VendorAuthContext` with login/logout, localStorage token, admin fallback |

**No changes needed.** The role system is complete. New vendors just need to be created with `role: "advertising_vendor"`.

### 2. Vendor Account Creation Pattern

| File | What's Ready |
|------|-------------|
| `app/services/admin_campaign_service.py:906-997` | `bulk_create_vendor_accounts()` — creates users with `role: "advertising_vendor"`, `vendor_account_status: "pending_approval"` |

**Reusable pattern:** The field structure this method writes (`business_name`, `email`, `role`, `vendor_account_status`, `vendor_category`, `vendor_location`, metrics init) is the exact schema a public signup endpoint should produce. Can extract the single-vendor creation logic into a shared helper.

### 3. Vendor Portal Login

| File | What's Ready |
|------|-------------|
| `app/portal/ads/layout.tsx:344-424` | `LoginPage` component — email/password form, calls `POST /auth/login`, stores token |
| `app/portal/ads/layout.tsx:160-176` | `VendorAuthContext` — manages auth state, auto-login from localStorage |

**Minor modification needed:** After login, check if `must_change_password` flag is set and redirect to password change screen before showing portal.

### 4. Password Management

| File | What's Ready |
|------|-------------|
| `app/services/user_management_service.py:1139-1185` | `change_password(email, current_password, new_password)` — verifies current, hashes new, records timestamp |

**Gap:** No `set_initial_password()` or `generate_temp_password()` method. The existing `change_password` requires knowing the current password, which won't work for temp-password flow. Need a new admin-only `reset_password()` or `set_temp_password()` method.

### 5. Notification Service

| File | What's Ready |
|------|-------------|
| `app/services/notification_service.py:19-58` | `create_notification(data, created_by)` — supports `target_audience: "root_admin"`, priority levels, SSE broadcast |

**Ready to use as-is.** On vendor signup, create notification with `type: "vendor_signup"`, `target_audience: "root_admin"`, `priority: "high"`.

### 6. Email Service

| File | What's Ready |
|------|-------------|
| `app/services/email_service_resend.py:48-149` | `send_email()` — supports arbitrary recipients, subjects, HTML body, attachments |

**Ready to use.** Need to create email templates for: (a) signup confirmation to vendor, (b) temp password email on approval.

### 7. Admin Vendor List UI

| File | What's Ready |
|------|-------------|
| `app/admin/ads/page.tsx:847-919` | Vendor cards grid with status filter (`pending_approval`, `active`, `suspended`), status badges, campaign/lead metrics |
| `app/services/campaignAdvertisingApi.ts:26` | `VendorAccountStatus = 'pending_approval' \| 'active' \| 'suspended' \| 'inactive'` |

**Modification needed:** Add "Approve" / "Suspend" action buttons to vendor cards (currently only has "Make Free" toggle).

### 8. Platform Config Service

| File | What's Ready |
|------|-------------|
| `app/services/ad_platform_config_service.py:58-61` | All four vendor signup flags defined with defaults in `DEFAULT_CONFIG` |

**Ready to use.** Signup endpoint and approval flow should read these flags to determine behavior.

### 9. Vendor Public Directory

| File | What's Ready |
|------|-------------|
| `app/vendors/page.tsx` | Public vendor directory with CTA "Vendor registration is coming soon" |
| `app/api/vendor_public.py:61-120` | `GET /api/v1/vendors/directory` — public listing endpoint |

**Modification needed:** Update CTA to link to signup page once built. Change text from "coming soon" to "List Your Business" → `/signup`.

---

## What Needs Modification

### M1. Vendor Portal Layout — Force Password Change

**File:** `app/portal/ads/layout.tsx`
**Change:** After successful login, check `user.must_change_password` flag. If true, render a `ChangePasswordScreen` instead of the normal portal. After password change, clear the flag and reload.

### M2. Admin Vendor Cards — Approval Actions

**File:** `app/admin/ads/page.tsx`
**Change:** Add "Approve" button (visible when `status === 'pending_approval'`) and "Suspend"/"Reactivate" toggle. Wire to new API endpoints.

### M3. Admin Campaign API — Vendor Status Endpoints

**File:** `app/api/admin_campaigns.py`
**Change:** Add `POST /admin/ads/campaigns/vendors/{vendor_id}/approve` and `POST /admin/ads/campaigns/vendors/{vendor_id}/suspend` endpoints. These call the new service methods.

### M4. Admin Campaign Service — Vendor Status Methods

**File:** `app/services/admin_campaign_service.py`
**Change:** Add `approve_vendor_account(vendor_id, admin_email)` — sets `vendor_account_status: "active"`, generates temp password, sends email, creates notification. Add `suspend_vendor_account(vendor_id, admin_email, reason)`.

### M5. Campaign API TypeScript — New API Functions

**File:** `app/services/campaignAdvertisingApi.ts`
**Change:** Add `approveVendorAccount()`, `suspendVendorAccount()`, and expose them to the admin UI.

### M6. Vendor Campaign Service — Profile Completeness Gate

**File:** `app/services/vendor_campaign_service.py`
**Change:** Before `create_campaign()`, check profile completeness (business_name, email, service_category, location, ≥1 image). If `require_profile_completion` config flag is true and profile incomplete, return 403 with missing fields list.

### M7. Public Vendor Directory CTA

**File:** `app/vendors/page.tsx`
**Change:** Update CTA link from `"/"` to `/portal/ads/signup` (or wherever the signup page lands). Update text from "coming soon" to active signup prompt.

---

## What Must Be Created From Scratch

### N1. Public Vendor Signup Endpoint

**New file:** `app/api/vendor_signup.py`
**Route:** `POST /api/v1/vendors/signup`
**Auth:** None (public)
**Input:** `{ business_name, email, service_category, location, phone?, website? }`
**Logic:**
1. Validate email not already registered
2. Create user document with `role: "advertising_vendor"`, `vendor_account_status: "pending_approval"`, `is_active: false`
3. If `auto_approve_signups` config is true → auto-approve (generate temp password, send email, set active)
4. Otherwise → create root admin notification, send "pending approval" email to vendor
5. Return `{ status: "pending_approval", message: "..." }`

**Pattern reference:** Extract from `bulk_create_vendor_accounts()` in `admin_campaign_service.py:906-997`

### N2. Vendor Signup Page (Frontend)

**New file:** `app/portal/ads/signup/page.tsx`
**Design:** Match existing portal dark theme. Form fields: business name, email, service category (dropdown from VendorCategory enum), location, phone (optional), website (optional). Submit → API call → show confirmation screen ("Your account is pending approval").

### N3. Temp Password Generation Service

**New file or addition to:** `app/services/user_management_service.py`
**New methods:**
- `generate_temp_password()` → cryptographically random 12-char password
- `set_vendor_temp_password(email, admin_email)` → hash and store, set `must_change_password: true`, return plaintext for email
- `clear_must_change_password(email)` → called after successful password change

### N4. Vendor Approval Email Template

**Location:** Inline in the approval service method or as a template file
**Content:** "Your vendor account has been approved. Here is your temporary password: [password]. Please sign in and change it immediately."

### N5. Vendor Signup Confirmation Email Template

**Content:** "Thank you for signing up. Your account is pending review by our team. You'll receive an email once approved."

### N6. Profile Completeness Check Utility

**New file:** `app/services/vendor_profile_completeness.py`
**Function:** `check_profile_completeness(vendor_doc) → { is_complete: bool, missing_fields: list, completion_percentage: int }`
**Required fields:** `business_name`, `email`, `service_category`, `vendor_location`, and ≥1 entry in `portfolio_urls` or `logo_url`
**Used by:** Campaign creation gate + vendor portal profile page indicator

### N7. Vendor Profile/Settings Page

**New file:** `app/portal/ads/settings/page.tsx`
**Design:** Form to edit profile fields (business_name, email, phone, website, service_category, location, logo/image, description). Shows completeness indicator. Per mockup V2: "Profile fields update live across all campaigns. Creative fields are frozen per campaign."

### N8. Force Password Change Screen

**New file or component in:** `app/portal/ads/layout.tsx` (inline component)
**Design:** Simple form — current temp password, new password, confirm password. Calls `change_password()`, then `clear_must_change_password()`. Renders instead of portal when `must_change_password` is true.

---

## Critical Issues

| # | File | Issue | Severity |
|---|------|-------|----------|
| 1 | `admin_campaign_service.py` | No vendor approval/suspend workflow exists — only campaign approval. Vendors stuck in `pending_approval` forever. | 🔴 Critical |
| 2 | `vendor_campaigns.py` | No profile completeness gate — vendor with empty profile can create campaigns immediately. | 🔴 Critical |
| 3 | `user_management_service.py` | No temp password generation — `change_password()` requires current password, can't bootstrap first login. | 🔴 Critical |
| 4 | No file | No public signup endpoint — all vendor creation is admin-initiated via bulk import. | 🔴 Critical |
| 5 | `portal/ads/layout.tsx` | Login page says "Contact ads@thespecialwedding.io to get started" — no self-service path. | 🟡 Major |

---

## Suggestions

| # | Area | Suggestion | Category |
|---|------|------------|----------|
| 1 | Signup | Rate-limit the public signup endpoint (e.g., 5/hour per IP) to prevent abuse | Security |
| 2 | Approval | Add "Log in as vendor" button on admin vendor cards per mockup V1 free-tier shortcut | UX |
| 3 | Email | Use existing Resend email service; no new provider needed | Architecture |
| 4 | Database | Add index on `users` collection for `{ role: 1, vendor_account_status: 1 }` for admin queries | Performance |
| 5 | Config | `auto_approve_signups` flag already defaults to `False` — test both paths | Testing |
| 6 | Profile | Store `profile_completed_at` timestamp when gate first passes — useful for analytics | Data |

---

## What Looks Good

- **Role system is complete** — `advertising_vendor` role is checked consistently across all vendor portal endpoints via `require_advertising_vendor()` dependency.
- **Status enum is defined** — `VendorAccountStatus` in both Python (`advertising_campaign.py:104-108`) and TypeScript (`campaignAdvertisingApi.ts:26`) already includes `pending_approval`, `active`, `suspended`, `inactive`.
- **Admin UI already renders status badges** — vendor cards in `admin/ads/page.tsx` color-code by status including `pending_approval` (amber).
- **Platform config flags pre-defined** — all four vendor signup flags (`vendor_domain`, `auto_approve_signups`, `require_profile_completion`, `min_images_for_campaign`) exist with sensible defaults.
- **Notification infrastructure is robust** — supports targeted audiences, priority, SSE broadcast, and email delivery.
- **Bulk create pattern is extractable** — the single-vendor creation logic in `bulk_create_vendor_accounts()` can be cleanly refactored into a shared `create_vendor_account()` helper used by both bulk import and public signup.

---

## Dependency Map

```
                    ┌──────────────────────┐
                    │  Public Signup Page   │  (N2 — NEW)
                    │  /portal/ads/signup   │
                    └──────────┬───────────┘
                               │ POST
                    ┌──────────▼───────────┐
                    │  Signup API Endpoint  │  (N1 — NEW)
                    │  /api/v1/vendors/     │
                    │  signup               │
                    └──────────┬───────────┘
                               │ creates user doc
                    ┌──────────▼───────────┐
                    │  users collection     │  (EXISTS)
                    │  role: advertising_   │
                    │  vendor               │
                    │  status: pending_     │
                    │  approval             │
                    └──────────┬───────────┘
                               │ triggers
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
   ┌──────────────┐  ┌────────────────┐  ┌──────────────┐
   │ Notification  │  │ Confirmation   │  │ Platform     │
   │ to Root Admin │  │ Email to       │  │ Config Check │
   │ (EXISTS)      │  │ Vendor (N5)    │  │ auto_approve │
   └──────┬───────┘  └────────────────┘  │ (EXISTS)     │
          │                               └──────┬───────┘
          ▼                                      │
   ┌──────────────┐     if auto_approve ◄────────┘
   │ Admin Reviews │     = true, skip
   │ Vendor Card   │     admin step
   │ (M2 — MOD)   │
   └──────┬───────┘
          │ clicks Approve
   ┌──────▼───────┐
   │ Approve API  │  (M3 — NEW endpoint)
   │ Generates    │
   │ Temp Password│  (N3 — NEW service)
   └──────┬───────┘
          │ sends email
   ┌──────▼───────┐
   │ Vendor Logs  │  (EXISTS — portal login)
   │ In, Changes  │
   │ Password     │  (N8 — NEW force-change screen)
   └──────┬───────┘
          │
   ┌──────▼───────┐
   │ Complete     │  (N7 — NEW settings page)
   │ Profile      │
   └──────┬───────┘
          │ passes gate
   ┌──────▼───────┐
   │ Profile Gate │  (N6 — NEW utility + M6 — MOD)
   │ Enforced     │
   └──────┬───────┘
          │
   ┌──────▼───────┐
   │ Create First │  (EXISTS — vendor portal)
   │ Campaign     │
   └──────────────┘
```

---

## Integration Risks

| Risk | Mitigation |
|------|-----------|
| Signup endpoint is public — spam/abuse vector | Rate limit by IP, add honeypot field, consider CAPTCHA |
| Temp password in email — if email intercepted, account compromised | Force password change on first login, set 24-hour expiry on temp password |
| `auto_approve_signups` bypasses admin review — could let bad actors in | Default is `False`; document that enabling it is for dev/testing only |
| Profile completeness gate may block existing vendors retroactively | Only enforce on campaign creation, not on login; grandfather existing active vendors |
| Two vendor identity systems (planner directory `vendor_profiles` vs advertising `users` with `role: advertising_vendor`) | Keep them separate as designed; public directory shows `vendor_profiles`, ad portal uses `users` collection |

---

## Estimated Scope

| Category | Items | Effort |
|----------|-------|--------|
| New files | 5–7 (signup endpoint, signup page, settings page, completeness utility, email templates, force-change component) | Medium-High |
| Modified files | 7 (admin service, admin API, admin UI, vendor campaign service, portal layout, campaign API TS, vendor directory CTA) | Medium |
| Database changes | 1 new index, 2 new fields on user doc (`must_change_password`, `temp_password_expires_at`) | Low |
| **Total** | **12–14 files** | **~2 sessions** |

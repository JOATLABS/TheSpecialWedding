# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Password Reset Flow** (`app/forgot-password/page.tsx`, `app/reset-password/page.tsx`, `app/api/user_management.py`, `app/services/user_management_service.py`):
  - Complete forgot password / reset password functionality for users who cannot log in
  - New API endpoints:
    - `POST /forgot-password` - Request password reset email (public, no auth)
    - `GET /reset-password/validate/{token}` - Validate reset token (public)
    - `POST /reset-password` - Reset password with token (public)
  - New frontend pages: `/forgot-password` (email input) and `/reset-password` (token validation + password entry)
  - Added "Forgot password?" link to admin login page
  - New database fields in `users` collection: `password_reset_token`, `password_reset_expires`, `password_reset_requested_at`
  - Security: Tokens expire after 1 hour, single-use, same response regardless of email existence, confirmation email after reset
  - Reference: [OWASP Password Reset Guidelines](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)

- **Admin Activity Logging** (`app/services/admin_activity_service.py`, `app/api/admin_activity.py`, `app/admin/page.tsx`):
  - New service to track all important admin actions for audit and visibility
  - Activity types: `invitation_sent`, `invitation_resent`, `invitation_cancelled`, `planner_suspended`, `planner_activated`
  - New API endpoints:
    - `GET /admin/activity-log` - Paginated activity log (ROOT_ADMIN)
    - `GET /admin/activity-log/recent` - Recent activities for dashboard (ROOT_ADMIN)
  - Added "Recent Admin Activity" section to Platform Health Overview dashboard
  - New collection `admin_activity_log` with fields: `admin_id`, `action_type`, `title`, `message`, `metadata`, `created_at`

- **Invitation Management Enhancements** (`app/api/user_management.py`, `app/services/user_management_service.py`, `app/admin/users/page.tsx`):
  - New API endpoints for invitation visibility and control:
    - `GET /admin/invitations` - List invitations with status filtering (ROOT_ADMIN)
    - `GET /admin/invitations/stats` - Invitation counts by status (ROOT_ADMIN)
    - `POST /admin/invitations/{id}/resend` - Resend invitation email with new token (ROOT_ADMIN)
    - `POST /admin/invitations/{id}/cancel` - Cancel pending invitation (ROOT_ADMIN)
  - Added "Pending Invitations" stats card to Planner Management page
  - Added collapsible pending invitations section with email status indicators (sent/failed)
  - Enhanced `user_invitations` collection: `email_status`, `email_sent_at`, `resend_count`, `last_resent_at`, `cancelled_at`, `cancelled_by`

### Fixed

- **Frontend Password Validation Mismatch** (`app/setup-account/page.tsx`, `app/reset-password/page.tsx`):
  - Fixed password validation in account setup and reset pages to match backend requirements
  - Added visual password requirements checklist with real-time validation
  - Password now requires: 8+ characters, uppercase, lowercase, number, special character
  - Prevents user frustration from submitting valid-looking passwords that fail backend validation
  - Reference: Backend validators in `app/api/user_management.py:AccountSetupModel`, `ResetPasswordModel`

- **Success Message Not Displayed on Login** (`app/admin/login/page.tsx`):
  - Fixed login page to display success messages from URL query params
  - Messages now appear after account setup completion (`?message=Account setup completed!`)
  - Messages now appear after password reset (`?message=Password reset successful!`)
  - Auto-dismiss after 10 seconds with manual close button
  - Styled with emerald green success indicator matching app design

- **SAAS Admin Dashboard Hardcoded Statistics** (`app/admin/saas/page.tsx`):
  - Fixed "Total Weddings" showing hardcoded value `12` instead of actual database count
  - Fixed "Monthly Revenue" showing hardcoded value `$247` instead of real revenue data
  - Fixed "Plan Distribution" showing hardcoded user counts (`0 users`/`1 user`) instead of actual subscribers per plan
  - Added API calls to existing `/saas/analytics/overview` and `/saas/analytics/revenue` endpoints
  - Added `AnalyticsOverview`, `PlanBreakdown`, and `RevenueAnalytics` TypeScript interfaces
  - Dashboard now displays real-time statistics from the database

- **Planner Management Actions Dropdown Clipped** (`app/admin/users/page.tsx`):
  - Fixed Actions column 3-dot menu dropdown being cut off by parent container
  - Removed `overflow-hidden` from planners table card wrapper (line 919)
  - Changed table container from `overflow-x-auto` to `overflow-visible` (line 942)
  - Dropdown menu now renders fully visible outside the table boundaries

- **Profile Picture Upload Not Saving** (`app/api/user_management.py`):
  - Fixed profile image URL construction missing `https://` protocol prefix
  - URLs were being constructed as `media.domain.com/path` instead of `https://media.domain.com/path`
  - Added validation to ensure `MEDIA_DOMAIN` environment variable is set
  - Fixed both upload and delete endpoints to handle URL protocol consistently

- **Root Admin Settings Page UX** (`app/admin/components/TopHeader.tsx`, `app/admin/components/AccountSettingsModal.tsx`):
  - Converted ROOT_ADMIN settings from separate page to popup modal
  - Added dropdown menu to TopHeader username area with "Account Settings" and "Logout" options
  - Created `AccountSettingsModal` component with Profile Info, Change Password, and Change Email tabs
  - Profile picture upload/delete now works directly in the modal
  - Improves UX by matching planner settings popup pattern

- **Root Admin Subscription Management 404 Errors** (`app/admin/saas/page.tsx`):
  - Removed incorrect `/admin` prefix from subscription API calls
  - Changed `/admin/users/${id}/subscription` to `/users/${id}/subscription` at lines 705, 731, 767, 778
  - Fixes: Activate planner, deactivate planner, and assign plan operations now work correctly
  - Reference: subscription_router is registered without `/admin` prefix in `main.py`

- **Subscription Plans Not Showing in Admin** (`app/services/subscription_service.py:58`):
  - Fixed sort field mismatch: changed `display_order` to `sort_order`
  - Plans query now uses correct field name matching the model definition
  - Reference: `app/models/subscription.py:52` defines `sort_order: int`

- **Subscription Seed Script Errors** (`scripts/seed_subscription_plans.py`):
  - Added explicit null check for stripe module before accessing `stripe.api_key` (fixes Pylance error)
  - Updated exception handling to use `from stripe import StripeError` for Stripe v13+ compatibility
  - Replaced all emoji characters with text-based prefixes for professional logging:
    - `[SEED]`, `[INFO]`, `[OK]`, `[WARN]`, `[ERROR]`, `[DEBUG]`
    - `[EXISTS]`, `[CREATED]`, `[UPDATED]`, `[SKIP]`, `[PLAN]`
    - `[SUMMARY]`, `[VERIFY]`, `[DONE]`

### Changed

- **Custom Trial Duration for Planners** (`app/admin/saas/page.tsx`):
  - Added prompt for trial days when assigning subscriptions (lines 714, 787)
  - ROOT_ADMIN can now set custom trial periods (e.g., 150 days for 5-month trial)
  - Replaces hardcoded 14-day trial default

### Security

- **CRITICAL: Settings Validation** (`app/core/settings.py`):
  - Removed insecure default `secret_key="changeme"` - now required from environment
  - Added `field_validator` requiring SECRET_KEY to be 32+ characters and not a common default
  - Removed insecure default `cors_origins=[]` - now required from environment
  - Added validator ensuring CORS_ORIGINS has at least one configured origin
  - Reference: [Pydantic Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

### Fixed

- **CRITICAL: Build Failure - Unterminated Regexp Literal** (`app/admin/users/page.tsx`):
  - Added missing opening `<div>` tag after `</PageHeader>` component
  - File had 65 opening `<div` tags but only 58 closing `</div>` tags
  - Caused TypeScript/SWC parser to fail with misleading "Unterminated regexp literal" error
  - Root cause: JSX structure imbalance from orphan closing tag at line 1019

- **CRITICAL: Pricing Page TypeError - slice is not a function** (`app/components/saas/SignupModal.tsx:250`):
  - Fixed `(selectedPlan?.features || selectedPlan?.features_list || []).slice(0, 4)` pattern
  - Backend sends `features` as `Record<string, boolean>` (object), not array
  - When `features` is truthy (even `{}`), the `||` fallback to `features_list` never triggered
  - Objects don't have `.slice()` method, causing runtime TypeError on pricing page
  - Changed to: `(Array.isArray(selectedPlan?.features_list) ? selectedPlan.features_list : []).slice(0, 4)`

- **CRITICAL: N+1 Query Pattern** (`app/admin/guests/page.tsx`, `app/api/plus_one.py`, `app/services/plus_one_service.py`):
  - Added batch endpoint `GET /plus_one/plus-ones/wedding/{wedding_id}` to fetch all plus-ones for a wedding in single query
  - Replaced N individual API calls with single batch fetch, improving performance for large guest lists
  - Reference: [MongoDB Query Optimization](https://www.mongodb.com/docs/manual/core/query-optimization/)

- **HIGH: Race Condition in Plus-One Creation** (`app/services/plus_one_service.py:27-61`):
  - Implemented insert-then-verify pattern to prevent concurrent requests exceeding plus-one limits
  - If count exceeds limit after insert, rollback is performed automatically
  - Reference: [MongoDB Atomic Operations](https://medium.com/tales-from-nimilandia/handling-race-conditions-and-concurrent-resource-updates-in-node-and-mongodb-by-performing-atomic-9f1a902bd5fa)

- **HIGH: String/ObjectId Type Inconsistency** (`app/services/plus_one_service.py:124-162`):
  - Standardized `guest_id` storage as string in plus_ones collection
  - Fixed delete_plus_one to use ObjectId for guest collection lookups
  - Prevents lookup failures due to type mismatches

- **HIGH: Duplicate Router Registration** (`app/main.py:266-299`):
  - Removed 7 duplicate routers from admin_routers that were already registered publicly with route-level authentication
  - Affected routers: user_management, subscription, saas_config, forms, vendor_forms, vendor_management, contracts
  - Prevents redundant route registration and potential conflicts

- **HIGH: Plan Selection Race Condition** (`app/components/saas/SaasLandingPage.tsx:407-413`):
  - Added `useRef` to track if initial plan selection has been made
  - Removed `selectedPlan` from useEffect dependency array to prevent overwriting user's manual selection
  - Reference: [React useRef for Preventing Infinite Loops](https://blog.logrocket.com/solve-react-useeffect-hook-infinite-loop-patterns/)

- **Pricing Page TypeError** (`app/components/saas/SaasLandingPage.tsx`, `IntegratedHeroSection.tsx`, `SaasExperienceCarousel.tsx`):
  - Added `Array.isArray()` defensive checks before calling `.slice()` and spread operators
  - Prevents `Uncaught TypeError: .slice is not a function` during SSR hydration

### Verified (No Change Required)

- **Middleware Order** (`app/main.py:208-227`):
  - Verified CORS middleware executes BEFORE rate limiting (correct for preflight handling)
  - In FastAPI/Starlette, middleware added LAST executes FIRST on incoming requests
  - Reference: [FastAPI Middleware Ordering](https://medium.com/@saurabhbatham17/navigating-middleware-ordering-in-fastapi-a-cors-dilemma-8be88ab2ee7b)

## [1.6.1] - 2026-01-23

### Fixed

- **Cloudflare Workers - Deprecated MailChannels Replacement** (`cloudflare-workers/*.js`):
  - Replaced deprecated MailChannels API with [Resend API](https://resend.com/docs/api-reference/emails/send-email) in all workers
  - Updated email sending to use `POST https://api.resend.com/emails` with `Authorization: Bearer` header
  - Email configuration now uses environment variables: `ALERT_EMAIL` (from), `ROOT_ADMIN_EMAIL` (to)
  - Affected workers: `autopilot-cron.js`, `backup-cron.js`, `uptime-cron.js`

- **Cloudflare Workers - Request Timeout** (`cloudflare-workers/*.js`):
  - Added `fetchWithTimeout()` helper to all workers to prevent hanging requests
  - Uses `AbortController` with configurable timeout (10s default, 15s health checks, 30s API calls, 60s backups)
  - Reference: [Cloudflare Workers Context API](https://developers.cloudflare.com/workers/runtime-apis/context/)

- **Cloudflare Workers - Premature Termination** (`cloudflare-workers/backup-cron.js`):
  - Wrapped email sending calls with `ctx.waitUntil()` to prevent premature worker termination
  - Ensures async email operations complete even after response is returned
  - Reference: [Cloudflare Scheduled Handler](https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/)

- **Cloudflare Workers - Alert Spam Prevention** (`cloudflare-workers/uptime-cron.js`):
  - Implemented KV-based alert debouncing (max 1 alert per hour during outages)
  - Added recovery notifications when service comes back online
  - Added `/status` endpoint to check current downtime state and last alert time
  - Uses [Cloudflare KV](https://developers.cloudflare.com/kv/get-started/) for state persistence

- **Cloudflare Workers - Hardcoded Values Removed**:
  - Removed all hardcoded API URLs and email addresses from worker files and wrangler.toml configs
  - All configuration now pulled from GitHub secrets during deployment
  - Changed environment variable from `API_URL` to `NEXT_PUBLIC_API_BASE_URL` for consistency with project conventions
  - Updated `deploy-workers.yml` to set secrets via `wrangler secret put`

### Added

- **Automated KV Namespace Creation** (`.github/workflows/deploy-workers.yml`):
  - Deploy workflow now automatically creates KV namespace for uptime-cron worker
  - Extracts namespace ID and updates `uptime.wrangler.toml` during deployment
  - No manual `wrangler kv:namespace create` step required
  - Reference: [Wrangler KV Commands](https://developers.cloudflare.com/kv/reference/kv-commands/)

### Changed

- **Deploy Workers Workflow** (`.github/workflows/deploy-workers.yml`):
  - Updated all workers to use `NEXT_PUBLIC_API_BASE_URL` instead of `API_URL`
  - Added `ALERT_EMAIL` and `ROOT_ADMIN_EMAIL` secrets to all worker deployments
  - Added KV namespace creation step before uptime worker deployment

## [1.6.0] - 2026-01-10

### Added

- **Plan Switching Endpoint** (`app/api/subscription_management.py`):
  - New endpoint `PATCH /users/{user_id}/subscription/billing-interval`
  - Allows users to switch between monthly and yearly billing with automatic proration
  - Users can only change their own subscription; ROOT_ADMIN can change any user's
  - Comment: "Proration is applied automatically: Switching to yearly credits unused monthly time"

- **AI Seating Validation** (`app/api/ai.py`):
  - New `validate_seating_suggestions()` function validates AI-generated table assignments
  - New `_extract_guest_id()` helper handles mixed string/object guest formats from different AI tiers
  - Validates guest IDs exist in original data, checks table capacity limits
  - Returns validation results with unassigned guests and over-capacity warnings
  - Comment: "Extract guest ID from various formats AI might return"

- **Enhanced Contract Follow-up Context** (`app/services/contract_followup_service.py`):
  - Added wedding context fields: venue_name, venue_location, cultural_style, guest_count, wedding_title
  - AI prompts now reference cultural considerations and wedding details
  - Batch fetch optimization to avoid N+1 queries (reduced from 100+ to ~3 queries)
  - Comment: "Batch fetch all weddings and planners to avoid N+1 queries"

- **AI System Prompts** (`app/services/ai_service.py`):
  - Added missing system prompts for `seating_medium` and `seating_large` AI tiers
  - Medium tier (150-300 guests): Focuses on family dynamics and relationship patterns
  - Large tier (300+ guests): Handles multiple sections, VIP tables, dietary clustering

- **Guest Table Assignment Field** (`app/models/guest.py`):
  - Added `table_id: Optional[str]` field to GuestModel and UpdateGuestRequest
  - Comment: "ID of assigned seating table"

### Fixed

- **MRR Calculation** (`app/services/subscription_service.py`):
  - Fixed Monthly Recurring Revenue to include BOTH monthly AND yearly subscriptions
  - Yearly subscriptions now calculated as `price_yearly / 12` (monthly equivalent)
  - Added MRR breakdown: from_monthly_billing, from_yearly_billing, subscriber counts
  - Added Annual Recurring Revenue (ARR) calculation
  - Comment: "MRR calculation - includes both monthly AND yearly. For yearly subscriptions, we calculate the monthly equivalent (price_yearly / 12)"

- **Stale Metering Retry Keys** (`app/api/metering.py`):
  - Fixed idempotency key generation to ALWAYS use current billing period
  - Previous bug used stale `billed_period` from wedding record which could be months old
  - Comment: "Idempotency key for retry: ALWAYS use current period since we're billing for NOW. Note: billed_period stores the LAST successful billing, not the target period"

- **Trial Days Default** (Multiple files):
  - Removed unintended 14-day trial default (user has no free trials)
  - `app/models/subscription.py`: AssignSubscriptionRequest.trial_days default 14→0
  - `app/api/subscription_management.py`: Removed `or 14` fallback in trial_days
  - `app/services/subscription_service.py`: assign_subscription trial_days default 14→0
  - `app/core/settings.py`: free_trial_days default 14→0
  - Comment: "Trial days (0 = no trial)"

- **useGuests Hook Race Condition** (`app/admin/hooks/useGuests.ts`):
  - Added AbortController to cancel in-flight requests when wedding changes
  - Added currentWeddingIdRef to prevent stale state updates
  - Clears guests on wedding switch to prevent stale data flash
  - Comment: "Track current request to prevent race conditions"

- **SignupModal Body Scroll** (`app/components/saas/SignupModal.tsx`):
  - Added body scroll lock when modal is open
  - Prevents background page scrolling while signup modal is displayed

- **CSS @import Order** (`app/styles/globals.css`):
  - Moved font @import to top of file (before @tailwind directives)
  - Fixes CSS rule ordering error: "@import rules must precede all rules"

### Changed

- **Stripe Service** (`app/services/stripe_service.py`):
  - Added `change_subscription_billing_interval()` method for plan switching
  - Uses Stripe's subscription modification with `proration_behavior: "create_prorations"`
  - Updates local database with new billing interval and period dates

## [1.5.0] - 2025-01-10

### Added

- **Payment Processing Safety**: Critical fixes for payment reliability
  - **Idempotency Keys**: All Stripe PaymentIntent.create calls now include idempotency keys to prevent double-charging
    - `autopilot_service.py`: Uses `autopilot_{payment_id}_attempt_{attempt_count}` format
    - `contract_service.py`: Uses `deposit_{contract_id}_{payment_id}` format
  - **Atomic Status Checks**: Payment retry and processing operations now use atomic MongoDB updates with status guards
    - Prevents race conditions when multiple cron instances or retry requests process the same payment
    - Both `retry_failed_payments()` and `_process_single_payment()` check status before proceeding

- **Subscription System Hardening**: Production-ready improvements for billing reliability
  - **Plan Grandfathering** (`app/services/subscription_service.py`):
    - Snapshot plan limits at subscription creation time
    - Users keep their original limits even if plan pricing/limits are modified later
    - Backwards compatible with existing subscriptions (falls back to current plan)
  - **Pricing Page Resilience** (`app/components/saas/PricingSection.tsx`):
    - Retry with exponential backoff (3 attempts: 1s → 2s → 4s)
    - localStorage cache (5-minute TTL) for offline resilience
    - User-friendly "Retrying..." status during fetch failures
    - Falls back to cached data if API is temporarily unavailable
  - **Atomic Seed Script** (`scripts/seed_subscription_plans.py`):
    - MongoDB upsert prevents race conditions on multi-container startup
    - `$setOnInsert` for created_at/created_by, `$set` for updateable fields
    - Idempotent Stripe product/price creation

### Fixed

- **Coolify Docker Build ARG Injection Bug** (`Dockerfile.coolify`):
  - Fixed CORS/API unreachable issue after Coolify deployment
  - Root cause: Coolify bug #7118 injects ARG statements at line 2, but Dockerfile starts with comments
  - ARG was being placed before `FROM` instruction, making it unavailable in build stage
  - Solution: Explicitly declare `ARG NEXT_PUBLIC_API_BASE_URL` after `FROM` instruction
  - Removed hardcoded default value - relies on Coolify's "Build Variable" setting
  - Reference: [Coolify Issue #7118](https://github.com/coollabsio/coolify/issues/7118)

- **Public API Security** (`app/api/subscription_management.py`):
  - Sanitized `/public/subscription-plans` response to exclude sensitive fields
  - Removed: `stripe_product_id`, `stripe_price_id_*`, `created_by`, `created_at`
  - Only returns public-safe fields needed for pricing display

- **S3 Variable Naming Mismatch**: Aligned code with `.env` file naming
  - Fixed `settings.py` aliases: `S3_ACCESS_KEY` → `S3_ACCESS_KEY_ID`, `S3_SECRET_KEY` → `S3_SECRET_ACCESS_KEY`
  - Added S3 variables to config_validator.py recommended list
  - Updated `DEPLOYMENT_SETUP.md` to use correct `S3_` prefix instead of `CLOUDFLARE_`

- **Stripe Webhook Secret**: Added `STRIPE_WEBHOOK_SECRET` to recommended environment variables in config validator

### Changed

- **SaaS Landing Page Hero**: Cleaned up broken demo functionality
  - Removed secondary CTA button ("Watch Demo") that opened non-existent demo_url
  - Changed header button from "Watch product tour" to "Explore features" linking to #features section
  - Made `hero_cta_secondary` optional in IntegratedHeroSection interface

- **Environment Variable Configuration**: Single source of truth policy
  - Removed all hardcoded URL fallbacks from `app/core/config.py` and `app/core/settings.py`
  - Missing critical env vars now trigger root admin notification at startup
  - Config validator (`app/services/config_validator.py`) notifies via Ntfy push + in-app notification

### Added

- **Ntfy Push Notifications**: Instant mobile/desktop push notifications for wedding planners via self-hosted Ntfy server
  - **New Service** (`app/services/ntfy_service.py`):
    - Self-hosted Ntfy integration (deployed on Coolify)
    - Unique topic per planner (hashed for privacy)
    - Emoji tags and priority levels per notification type
    - Helper methods: `send_rsvp_notification()`, `send_form_notification()`, `send_payment_notification()`, `send_contract_notification()`
  - **Config** (`app/core/config.py`): Added `SERVICE_URL_NTFY` environment variable
  - **Auto-Push**: Every planner activity notification also sends a push notification (non-blocking)
  - **New API Endpoints**:
    - `GET /admin/planner/push-subscription` - Get planner's unique Ntfy subscription URL
    - `POST /admin/planner/push-test` - Send test push notification
  - **Notification Types with Emoji Tags**:
    - Form submission: page_facing_up, inbox_tray
    - RSVP update: white_check_mark, busts_in_silhouette
    - Payment received: money_with_wings (high priority)
    - Payment failed: x, credit_card (urgent priority)
    - Contract signed: memo, black_nib (high priority)
    - Vendor response: package, handshake
  - **How Planners Subscribe**:
    1. Call `GET /admin/planner/push-subscription` to get unique topic URL
    2. Subscribe in Ntfy app (iOS/Android) or web browser
    3. Receive instant push notifications for all wedding activities

- **Planner Activity Notifications System**: Real-time activity notifications for wedding planners
  - **New MongoDB Collection**: `planner_notifications` for storing activity events
  - **Model** (`app/models/planner_notification.py`):
    - Notification types: `form_submission`, `rsvp_update`, `guest_message`, `payment_received`, `payment_failed`, `contract_signed`, `vendor_response`, `reminder`, `system`
    - Priority levels: low, medium, high
    - Deep links to relevant pages (action_url)
  - **Service** (`app/services/planner_notification_service.py`):
    - CRUD operations for planner notifications
    - Trigger helpers: `notify_form_submission()`, `notify_rsvp_update()`, `notify_payment_received()`, `notify_payment_failed()`, `notify_contract_signed()`, `notify_vendor_response()`
  - **API** (`app/api/planner_notifications.py`):
    - `GET /admin/planner/activity-notifications` - List notifications with filtering
    - `GET /admin/planner/activity-notifications/count` - Get unread count
    - `PUT /admin/planner/activity-notifications/{id}/read` - Mark as read
    - `PUT /admin/planner/activity-notifications/read-all` - Mark all as read
    - `DELETE /admin/planner/activity-notifications/{id}` - Delete notification
  - **Event Triggers**: Automatic notifications on:
    - RSVP submission → "John Doe confirmed attendance for 2 guests"
    - Form submission → "Jane Smith submitted a Contact Form"
    - Payment received → "$500.00 received from Customer"
    - Contract signed → "John Smith signed the contract"
  - **Bell Count**: Combined platform announcements + activity notifications
  - **Notifications Page**: Shows both platform and activity notifications, sorted by date
  - **Mark as Read**: Click notification to mark as read, "Mark all as read" button
  - **Real-time Bell Updates**: Bell refreshes on window focus and custom `notifications-updated` event
  - **New Notification Types**: Added colors for payment_received (emerald), payment_failed (red), contract_signed (indigo), vendor_response (amber)

- **Multi-Tenant Frontend Isolation**: Proper role-based access control
  - **Platform Page Consolidation**: Merged `/admin/platform/metrics` and `/admin/platform/errors` into single `/admin/platform` with tabs (Health, Errors, Performance, Backups)
  - **Root Admin Guards**: Added frontend access guards to `/admin/metrics`, `/admin/users`, `/admin/platform`
  - **Best Practices**: Toast notifications, loading states, `Promise.allSettled` for batch operations

- **Wedding Finance Autopilot (WFA)**: Automated payment collection system for wedding planners
  - **Package → Contract → Autopilot Flow**: Define packages once, couples sign, money flows automatically
  - **Data Models** (`app/models/autopilot.py`):
    - `Package`: Reusable service package templates with payment schedules
    - `Contract`: Signed agreements with couple info and Stripe payment methods
    - `ScheduledPayment`: Individual payment instances with retry logic
  - **AI Service Layer** (`app/services/ai_service.py`, `app/services/ai_cache_service.py`):
    - Gemini 2.0 Flash integration for budget insights, seating optimization, email drafting
    - Credit-based system: Boutique (100/mo), Signature (300/mo)
    - Content-addressed caching with TTL and event-driven invalidation
  - **Autopilot Engine** (`app/services/autopilot_service.py`):
    - Automatic payment processing via Stripe
    - Exponential backoff retry logic (24h → 48h → 96h)
    - Failed payment notifications
  - **Money Dashboard** (`app/admin/money/page.tsx`):
    - Unified financial view for planners
    - Incoming/outgoing payment tracking
    - Subscription summary with usage (weddings, AI credits)
    - Quick actions for payment retry, cancel, mark external, refund
  - **Contract API** (`app/api/contracts.py`):
    - Full CRUD for packages and contracts
    - Public signing endpoints (token-based, no auth)
    - Payment actions: retry, cancel, mark-paid-externally, refund
  - **Couple Portal**: Public dashboard for couples to view contracts and payment history
  - **Cloudflare Cron Workers**: Replaced Vercel crons with Cloudflare Workers
    - `uptime-cron.js`: Backend health monitoring every 5 minutes
    - `autopilot-cron.js`: Payment processing (due payments, retries, reminders)
  - **Cache Invalidation**: Budget and guest changes invalidate AI cache automatically

- **Enhanced Vendor Management System**: Comprehensive CRM for managing vendors, contracts, and payments
  - **Linear Tracking**: Epic [JOA-133](https://linear.app/joatlabs/issue/JOA-133) with 10 sub-tasks
  - **Backend Complete**: JOA-134 to JOA-140 (7 tickets)
  - **Frontend In Progress**: JOA-141 (Contract Canvas), JOA-142 (Payment Milestones), JOA-143 (VendorPaymentModal)
  - **PDF Contract Upload**: Planners can upload their own contract PDFs instead of using templates
    - S3 storage integration for secure document hosting
    - Full tracking workflow (draft → sent → viewed → signed)
    - Works alongside template-based contracts
  - **Form Data Integration**: Use vendor form submissions to populate contracts
    - Auto-extract fields from vendor inquiry forms
    - Smart suggestions for contract placeholders
    - One-click insertion of package details, pricing, and terms
  - **Contract Customization**: Edit contract sections after creation
    - Add/edit/remove sections with rich content
    - Custom clauses and terms additions
    - Modify terms & conditions and cancellation policies
  - **Payment Links**: Send Stripe payment links to vendors or couples
    - Multiple payment scenarios:
      - Couple → Vendor (vendor payment)
      - Couple → Planner (planning fee)
      - Vendor → Planner (referral commission)
    - Custom email messages and due dates
    - Real-time payment status tracking
    - Stripe webhook integration for automatic updates
  - **New Models**: `PaymentLink`, `ContractType`, `PayerType`, `RecipientType`
  - **New API Endpoints**:
    - `POST /admin/contracts/upload-pdf` - Upload existing PDF contracts
    - `GET /admin/contracts/{id}/form-data` - Get form data for contract
    - `POST /admin/contracts/{id}/apply-form-data` - Apply form data to placeholders
    - `PUT /admin/contracts/{id}/sections` - Update contract sections
    - `POST /admin/payment-links` - Create payment link
    - `POST /admin/payment-links/{id}/send` - Send payment link email
    - `GET /admin/payment-links` - List payment links
  - **Subscription Feature Gating**: `vendor_management` feature flag for plans
  - **Planner-Configurable Contract Settings**: Replaced hardcoded contract configuration with layered settings
    - Settings flow: `System Defaults (env vars) → Planner Preferences → Contract Creation`
    - Configurable options:
      - `token_expiry_days` (7-90): How long contract access links remain valid
      - `deposit_due_days` (1-60): Days after signing for deposit to be due
      - `payment_reminder_days`: Array of days before due date to send reminders
      - `auto_followup_days` (1-14): Days to auto-generate follow-up for unsigned contracts
      - `default_currency`: Default currency for contracts
    - New API endpoints:
      - `GET /vendors/settings/contract` - Get current settings with defaults
      - `PUT /vendors/settings/contract` - Update planner preferences
    - Added `ContractSettings` model and `contract_settings` field to `UserModel`

### Fixed

- **Vendor Service Security & Code Quality Fixes** (`app/services/vendor_service.py`):
  - **Authorization Hardening**: Added `created_by` parameter to `get_contract()` for ownership verification
    - All internal callers now pass `created_by` to enforce authorization: `send_contract()`, `update_contract()`, `update_contract_sections()`, `get_form_data_for_contract()`, `apply_form_data_to_contract()`, `create_payment_milestones()`
  - **Performance**: Added `get_dashboard_counts()` method using MongoDB aggregation
    - Replaced full document loads with efficient `count_documents()` and `$group` pipelines
    - Dashboard now fetches counts separately from limited recent items
  - **Data Integrity**: Fixed `get_payment_milestones()` to persist overdue status to database
    - Previously only marked milestones as overdue in memory, not persisted
    - Now updates MongoDB when milestones become overdue
  - **Code Quality**:
    - Added `validate_object_id()` utility function for consistent ObjectId validation
    - Added configuration constants: `TOKEN_EXPIRY_DAYS`, `DEPOSIT_DUE_DAYS`, `MAX_FILE_SIZE_MB`, `MEDIA_DOMAIN`
    - Renamed `type` parameter to `comm_type` in `_log_communication()` to avoid shadowing Python builtin
    - Moved `stripe` and `settings` imports to top-level (were inside functions)
    - Fixed silent error swallowing in `get_vendor_communications()` and `get_payment_links()` - now raise `HTTPException` instead of returning empty list
  - **Payment Links Expiration**: Added `expires_at` field to payment links
    - Expires 7 days after `due_date` or 30 days from creation if no due date
  - **Documentation**: Added docstring notes about atomic transaction limitations in `sign_contract()` and `record_payment()`
  - **Cleanup**: Removed unused model imports (`VendorProfile`, `VendorCategory`, etc.)

- **Budget Tracker API**: Fixed ObjectId serialization error causing "Failed to fetch budget summary"
  - Added proper serialization for MongoDB ObjectId fields in categories and alerts
  - Removed `ge=0` constraint on `remaining_budget` field to allow negative values when overspent
- **Wedding Party Sync**: Removed redundant "Wedding Party (Other)" group option
  - Wedding party now correctly comprises only: Maid of Honor, Bridesmaids, Best Man, Groomsmen
  - Updated guest group presets and wedding party sync mappings
- **Gallery Navigation**: Fixed 404 error on `/admin/gallery` - sidebar now correctly links to `/admin/gallery/upload`
- **Wedding Slug Collision**: Added unique slug enforcement to prevent URL conflicts when multiple planners use same couple names
  - Backend auto-appends suffix (e.g., `john-jane-2`) if slug already exists
  - Added unique database index on wedding slugs
- **Gallery Management Dark Mode**: Fixed dark mode styling on Gallery Management page
  - Updated titles, labels, tabs, cards, and badges for proper dark theme support
- **Wedding Party Sync API**: Fixed guest fetch using wrong API endpoint
  - Changed from `/admin/guests/{id}` to `/admin/guests?wedding_id={id}`
  - Added debug logging to help troubleshoot sync issues

## [1.4.0] - 2024-12-14

### Added
- **Planner Calendar & Task Management System**: Complete calendar feature for wedding planners to schedule and manage tasks
  - **Google Calendar Integration**:
    - OAuth 2.0 authentication flow with secure token storage
    - Two-way sync: tasks created in app sync to Google Calendar
    - Auto-refresh of expired tokens
    - Connect/disconnect functionality with token cleanup
  - **Task Management Backend** (`app/api/planner_calendar.py`):
    - Full CRUD operations for planner tasks
    - Task filtering by wedding, category, status, and date range
    - Bulk status updates for multiple tasks
    - Month view endpoint for calendar rendering
    - Upcoming tasks endpoint for dashboard widgets
  - **Calendar Models** (`app/models/calendar.py`):
    - `PlannerTaskModel` with comprehensive fields (priority, category, reminders, recurrence)
    - `CalendarTokenModel` for secure OAuth token storage
    - Support for all-day events and timed events
    - 17 wedding planning categories (venue, catering, photography, etc.)
  - **Google Calendar Service** (`app/services/google_calendar_service.py`):
    - Complete OAuth flow handling
    - Create, update, delete events in Google Calendar
    - Fetch events from connected calendar
    - Automatic token refresh on expiry
  - **Frontend Calendar UI** (`app/admin/planner/calendar/`):
    - Interactive month view calendar with task display
    - Click-to-create tasks on any date
    - Task modal for creating/editing with full field support
    - Google Calendar connection component with status display
    - Upcoming tasks sidebar widget
    - Priority-based color coding
    - OAuth callback page for handling Google authorization
  - **TypeScript API Client** (`app/services/calendarApi.ts`):
    - Full type definitions for tasks and calendar operations
    - Helper functions for formatting dates and priorities
    - Category and status label configurations
  - **Navigation**: Added "Calendar" item to planner sidebar navigation
  - **New Dependencies**: `google-api-python-client`, `google-auth-oauthlib`, `google-auth`, `icalendar`
  - **Database Collections**: Added `calendar_tokens` and `planner_tasks` collections
  - **Configuration**: Added Google OAuth settings to `app/core/config.py`
  - **Testing**:
    - Unit tests for calendar service (`tests/unit/test_calendar_service.py`)
    - E2E tests for calendar UI (`tests/planner-calendar.spec.ts`)
    - Pytest configuration (`pytest.ini`)
    - Added `pytest` and `pytest-asyncio` dependencies
- **Redis Service for Development**: Added Redis service to `docker-compose.yml` for development environment parity with production
- **System Metrics Monitoring**: Added `psutil` package to `requirements.txt` for CPU, memory, and disk monitoring in Platform Metrics dashboard
- **Authentication Loading State**: Added `isLoading` state to `AdminContext` for proper authentication state management
- **Comprehensive Dark Mode Support**: Full dark mode theming across all admin pages
  - Theme toggle in header supporting light/dark/system modes
  - ThemeContext for managing theme state with localStorage persistence
  - System preference detection via `prefers-color-scheme` media query
- Enhanced error handling and logging for SAAS configuration saves
- Clean configuration object creation to prevent circular references
- Authentication token validation for admin operations
- Type-safe parameter handling for configuration save operations
- **OTP Guest Verification System**: Complete one-time password verification flow for wedding guest access
  - New `/otp/send-by-contact` endpoint for sending verification codes by phone/email
  - Phone number normalization supporting multiple formats (E.164 variants)
  - Wedding-specific OTP verification with `wedding_id` context
  - Fallback mechanism for Twilio SMS (Messaging Service → Direct phone number)
- Security logging and rate limiting for guest verification attempts
- Debug logging throughout guest verification chain for troubleshooting

### Removed
- **Wedding Planners Tab from SaaS Page**: Removed duplicate "Wedding Planners" tab from `/admin/saas` page
  - Planner management is now exclusively accessed via the sidebar "Planners" navigation (`/admin/users`)
  - Eliminates duplicate functionality and reduces UI confusion
  - SaaS page now focuses on: Overview, Subscription Plans, SAAS Content, and Theme & Design

### Fixed
- **CRITICAL**: Fixed login redirect race condition in `AdminRouteGuard`
  - Added `isLoading` state to `AdminContext.tsx` to track authentication initialization
  - Updated `AdminRouteGuard.tsx` to wait for auth check completion before redirecting
  - Changed post-login navigation from `router.push()` to `window.location.href` for immediate redirect
  - Root cause: Guard was checking `isAuthenticated` before `useEffect` loaded token from storage
- **CRITICAL**: Fixed Platform Metrics page crashes due to undefined nested objects
  - Added optional chaining (`?.`) and nullish coalescing (`??`) throughout `app/admin/platform/metrics/page.tsx`
  - Protected access to `metrics.health.database`, `metrics.errors`, `metrics.business`, `metrics.performance`
  - Page now gracefully handles missing or incomplete API responses
- **CRITICAL**: Fixed API 404 errors for `/admin/platform/*` endpoints
  - Changed router prefix in `app/api/admin_platform_metrics.py` from `/admin/platform` to `/platform`
  - Router was included with `/admin` prefix in `main.py`, causing double prefix `/admin/admin/platform/`
- **Error Logs Page Dark Mode**: Fixed dark mode styling in `app/admin/platform/errors/page.tsx`
  - Added `bg-opacity-100 dark:bg-opacity-100` to Card components to prevent washed-out appearance
  - Fixed duplicate CSS classes in select dropdowns
  - Corrected hover state from `dark:bg-slate-700` to `dark:hover:bg-slate-700` on table rows
- **Missing Components**: Restored accidentally deleted files from git history
  - `app/contexts/ThemeContext.tsx` - Theme management context
  - `app/admin/components/Sidebar.tsx` - Admin sidebar navigation
  - `app/admin/components/TopHeader.tsx` - Admin top header component
- **Missing Dependencies**: Added `framer-motion` package for admin dashboard animations
- **Dark Mode Styling Fixes**: Comprehensive dark mode support across admin dashboard
  - Fixed `tailwind.config.js` to use `darkMode: 'class'` instead of `'media'` for class-based toggling
  - Fixed `Card` component (`app/components/ui/Card.tsx`) with `dark:bg-slate-800` backgrounds
  - Fixed `CardTitle` and `CardDescription` components with dark text variants
  - Fixed Platform Health Overview page (`/admin/page.tsx`) - all cards, tables, and metrics
  - Fixed SaaS Management page (`/admin/saas/page.tsx`) - navigation tabs and content
  - Fixed Platform Metrics page (`/admin/platform/metrics/page.tsx`) - hover states and quick action links
  - Fixed Error Details page (`/admin/platform/errors/[errorId]/page.tsx`) - all sections and badges
  - Removed hardcoded light backgrounds from vendors, guests, and weddings pages
  - Added dark mode hover states (`dark:hover:bg-slate-700`) throughout
  - Fixed select dropdowns, code blocks, and form elements for dark mode
- **CRITICAL**: Fixed async/await chain in guest verification flow preventing authentication
  - Made `verify_guest_access` async and added `await` to all service calls
  - Fixed coroutine access errors in `guest_verification_service.py`, `guest_verification.py`, `gallery_public.py`, `wedding.py`
- **CRITICAL**: Fixed OTP verification endpoint returning 403 when OTP is required
  - Now correctly returns `{otp_required: true, wedding_id}` response instead of throwing error
- **CRITICAL**: Fixed OTP service signature mismatch
  - Rewrote `verify_otp` method to accept `wedding_id`, `contact`, `otp_code` instead of `guest_id`, `otp`
  - Added phone number normalization for cross-format matching
- **CRITICAL**: Fixed frontend OTP endpoint URL from `/api/otp/send` to `/otp/send-by-contact`
- **CRITICAL**: Fixed NoneType error in OTP verification by adding missing Pydantic model fields
  - Added `otp_code` and `contact` fields to `GuestVerificationRequest` model
- Circular reference error in SAAS landing page content save functionality
- JSON stringify issues when saving SAAS configuration
- React state timing issues in modal save operations
- Improved error propagation and user feedback for failed saves
- Missing database fields in WeddingModel (`assigned_planner_id`, `updated_by`, `guest_count`, `total_budget`, `venue`)

### Changed
- Enhanced `handleSaveSaasConfig` function with better error handling
- Updated modal save handler to pass configuration directly
- Improved error message parsing from API responses
- **Guest Verification Flow**: Complete redesign from name/phone matching to secure OTP-based verification
  - Deprecated direct name/phone matching (vulnerable to social engineering)
  - Implemented two-step verification: contact submission → OTP validation
- Frontend `GuestVerificationModal.tsx` now captures and uses `wedding_id` from verification response
- Enhanced Twilio SMS service with automatic fallback from Messaging Service to direct phone number

### Security
- Added proper authentication checks for admin operations
- Implemented secure token validation for configuration saves
- **Enhanced Guest Verification Security**:
  - Input sanitization to prevent NoSQL injection attacks
  - Rate limiting (5 attempts per 5 minutes) to prevent brute force attacks
  - Security audit logging for all verification attempts
  - Constant-time password comparison to prevent timing attacks
  - Replaced vulnerable name/phone matching with secure OTP verification

## [1.3.0] - 2024-08-21

### Added
- Comprehensive SAAS platform features and landing page
- User management service with invitation handling
- Account setup workflow for wedding planners
- Subscription plan seeding functionality
- Modern3D background design for SAAS landing page
- Mobile-friendly responsive design updates

### Fixed
- Email service rate limiting issues with Resend API (added 600ms delay between sends)
- Admin RSVP service JSON serialization errors with MongoDB ISODate objects
- RSVP form functionality and guest display in admin panel
- Guest ID handling for both string and ObjectId formats

### Changed
- Removed emojis from SAAS landing page for cleaner professional appearance
- Improved RSVP query handling to avoid MongoDB mixed type issues
- Enhanced error handling for missing guest IDs in RSVP operations

### Security
- Added proper authentication checks for admin operations
- Implemented secure token validation for configuration saves

## Previous Versions

### [1.2.x] - Various dates
- Core wedding planning functionality
- Guest management and RSVP system
- Admin panel development
- Gallery and vendor management features
- Email reminder system with Telnyx integration
- Multi-tenant architecture foundation

---

## Release Notes

### How to Read This Changelog
- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

### Versioning
This project follows [Semantic Versioning](https://semver.org/):
- MAJOR version for incompatible API changes
- MINOR version for backwards-compatible functionality additions
- PATCH version for backwards-compatible bug fixes

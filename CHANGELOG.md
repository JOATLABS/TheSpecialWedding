# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.3] - 2026-03-03 — Email Service Type Safety & Root Admin Alerting

### Fixed

- **Type checker error on `email_service` calls** (`app/api/email_reminders.py`):

  - `email_service` is typed `Optional[ResendEmailService]` but four guard clauses only checked `if not email_available:` without narrowing the `None` type — added `or email_service is None` to guards at the `send_email_invites`, `send_email_invites_with_attachment`, `preview_invitation_email`, and `preview_reminder_email` endpoints to match the pattern already used in `send_email_reminders`, `send_individual_email`, and `get_email_logs`

- **Email service init error silently swallowed** (`app/api/email_reminders.py`):

  - The `except` block had a bare f-string `(f"Email service not available: {str(e)}")` that evaluated to nothing — replaced with `logger.error(...)` using the standard `logging.getLogger(__name__)` pattern used across other API modules

### Added

- **Root admin notification when email service fails to initialize** (`app/main.py`):

  - After environment validation in `lifespan()`, checks `email_available` flag and fires a `"critical"` priority in-app notification via `_create_root_admin_notification` from `config_validator.py` — covers runtime failures (bad API key, constructor exceptions) beyond the missing-env-var case already handled by the config validator

## [2.1.2] - 2026-03-03 — Email Reminders for Phoneless Guests, Plus-One Display Fix & Channel Picker

### Fixed

- **Email reminders not working for guests without phone numbers** (`app/admin/guests/page.tsx`, `app/api/email_reminders.py`, `app/admin/reminders/page.tsx`):

  - The reminder modal on the guests page was SMS-only — the send button was disabled when a guest had no phone number, and the handler only called the SMS endpoint (`/admin/reminders/send-to-guests`)
  - Added new `POST /admin/email/send-reminder-individual` endpoint in `email_reminders.py` with `IndividualEmailReminderModel` Pydantic model for sending a single reminder email via Resend
  - Rewrote `handleSendReminder` in `guests/page.tsx` to compute `sendSms`/`sendEmail` booleans based on selected channel and guest contact availability, then call the appropriate endpoint(s)
  - Fixed send button disabled logic from `!reminderModal.guest.phone` to `(!reminderModal.guest.phone && !reminderModal.guest.email)` so email-only guests can receive reminders
  - On the reminders page, fixed "Send Event Reminder" button disabled condition to allow email-only sends without requiring a custom message (`channel !== 'email'` guard)
  - Added error handling for email reminder API failures on the reminders page — errors were previously silently swallowed

- **Plus-one information not displaying in admin panel** (`app/services/admin_rsvp_service.py`, `app/api/plus_one.py`):

  - `admin_rsvp_service.py` used a dict comprehension `{guest_id: plus_one for ...}` which overwrote earlier entries when a guest submitted multiple plus-ones — changed to `setdefault(gid, []).append(p)` to preserve all plus-ones per guest
  - Added `plus_ones` array field to the RSVP response alongside backward-compatible singular `plus_one` field
  - Fixed broken `GET /plus_one/wedding/{id}` route in `plus_one.py` — was calling non-existent `get_plus_ones_by_wedding()` method, corrected to `get_plus_ones_by_wedding_id()`
  - Serialized `_id` fields to string in the plus-ones map to prevent ObjectId serialization errors

- **CSV export losing multiple plus-ones** (`app/services/admin_rsvp_service.py`):

  - `export_rsvps_to_csv` only exported the last plus-one per guest due to the same dict overwrite bug
  - Rewrote export to iterate `entry.get("plus_ones", [])` and create one CSV row per plus-one, with empty plus-one columns for guests without any

### Added

- **Channel picker for individual guest reminders** (`app/admin/guests/page.tsx`):

  - Planners can now choose to send reminders via **SMS**, **Email**, or **Both** using toggle buttons in the reminder modal
  - Channel picker auto-selects the best option based on guest contact info (e.g., defaults to Email if guest has no phone, SMS if no email, Both if both exist)
  - Send button label dynamically reflects selected channel ("Send via SMS", "Send via Email", "Send via SMS & Email")
  - Channel buttons are conditionally shown — SMS button hidden if no phone, Email button hidden if no email

---

## [2.1.1] - 2026-03-03 — Seating DnD Fix, Dark Mode Animation Portal & Infinite Scroll

### Fixed

- **Dark mode toggle animation only visible on nav header** (`app/components/landing-page/AnchorNav.tsx`):

  - The veil sweep, shimmer line, and ring ripple overlays used `position: fixed; inset: 0` but were rendered as children of the `<nav>` element which has `backdrop-blur-sm` (`backdrop-filter: blur(4px)`)
  - Per CSS spec, `backdrop-filter` creates a containing block for fixed-position descendants, so the "full-screen" overlays were actually clipped to the nav bar's bounds
  - Wrapped animation overlays in `createPortal(... , document.body)` to render them at the root DOM level, escaping the nav's containing block
  - Veil sweep and ring ripple now correctly cover the entire viewport during dark mode transition

- **Seating drag-and-drop not working** (`app/admin/components/seating/TableNode.tsx`, `app/admin/seating/page.tsx`):

  - Reverted incorrect `closestCenter` collision detection — it always returned the nearest droppable even when dropping in empty canvas space, causing unintended guest assignments. Replaced with `pointerWithin` which only triggers when the pointer is actually inside a droppable zone
  - Separated draggable and droppable refs in `TableNode`: draggable ref on outer positioned wrapper (for table movement), droppable ref on inner card div (for receiving guest drops) — previously both were composed onto the same element causing self-collision
  - Removed `overflow-hidden` from the TableNode inner card which was clipping dragged guest elements when they moved outside the card boundary
  - Removed unused `MeasuringStrategy` import

- **Infinite scroll parallax jump at loop point** (`app/components/ui/InfiniteScrollWrapper.tsx`, `app/components/landing-page/Modern3DBackground.tsx`, `app/components/landing-page/LandingLayout.tsx`):

  - `Modern3DBackground` used raw `window.scrollY` for parallax offset, causing a visual jump of `height × 0.15` pixels when `InfiniteScrollWrapper` reset scroll position
  - Added `onPrimaryHeight` callback prop to `InfiniteScrollWrapper` using `ResizeObserver` to report primary content height
  - Added `loopHeight` prop to `Modern3DBackground` which normalizes `scrollY` with modulo (`scrollY % loopHeight`) for seamless looping
  - Switched parallax from React state updates (re-render per scroll) to a `requestAnimationFrame` loop writing directly to a DOM ref for smoother performance
  - Lifted `loopHeight` state in `LandingLayout` to connect the two sibling components

---

## [2.1.0] - 2026-03-03 — Stripe Audit, Error Boundaries, KB Permissions & Animation Fixes

### Added

- **ErrorBoundary wired into layouts** (`app/[slug]/layout.tsx`, `app/admin/layout.tsx`):

  - Connected the existing `ErrorBoundary.tsx` class component as a wrapper in both guest-facing and admin layouts
  - Created `app/[slug]/error.tsx` — Next.js route-level error boundary for guest pages with rose-themed UI and "Try Again" button
  - Created `app/admin/error.tsx` — Next.js route-level error boundary for admin pages with blue-themed UI and "Try Again" button
  - Guest and admin pages now have zero-downtime error recovery instead of full page crashes

- **PaymentCollectionButton wired into wedding management** (`app/admin/weddings/[id]/page.tsx`):

  - Connected the existing `PaymentCollectionButton.tsx` into the wedding detail page header actions (between "Seating Plan" and "Save Changes")
  - Planners can now collect payments from couples via Stripe directly from the wedding management page
  - Full payment flow verified end-to-end: button → modal → `POST /stripe/create-payment-intent` → shareable `/pay/{id}` link → Stripe Elements checkout → `/pay/success`

- **LiquidBackground wired into seating planner** (`app/admin/weddings/[id]/seating/page.tsx`):

  - Connected the existing Three.js `LiquidBackground.tsx` as a background layer behind the sidebar and canvas
  - Wrapped in `print:hidden` to exclude from print output
  - Content layers given `relative z-10` to sit above the background

- **Dark mode toggle animation** (`app/components/landing-page/AnchorNav.tsx`):

  - Ported veil sweep, shimmer line, and ring ripple animations from the orphaned `WeddingDarkModeToggle.tsx` into the existing compact `NavDarkModeToggle`
  - Full-screen veil sweep overlay with theme-aware gradient (reads `--theme-primary` / `--theme-secondary` CSS variables)
  - Shimmer line follows the veil sweep edge with glow effect
  - 3 staggered ring ripples expand outward from the button position
  - Button disabled during 1-second animation cycle; theme flips at 500ms midpoint
  - Added `AnimationStyles` component injecting global `@keyframes` via `<style jsx global>`

- **Knowledge Base seed script** (`app/scripts/seed_knowledge_base.py`):

  - 7 planner-facing articles seeded into `kb_articles` MongoDB collection on first deploy: Getting Started, Collect Payments, RSVP via SMS, Guest Management, Seating Planner, Theme Configuration, Troubleshooting
  - All articles marked `is_official: True`, `status: "published"`, authored by `root@thespecialwedding.io`
  - Idempotent — checks by slug before inserting to avoid duplicates on redeploy
  - Wired into `app/main.py` lifespan startup (after config validation, wrapped in try/except so failures don't prevent app start)

### Changed

- **Knowledge Base permissions locked to root admin** (`app/api/knowledge_base.py`, `app/admin/components/kb/KnowledgeBase.tsx`, `app/admin/components/kb/ArticleView.tsx`):

  - `POST /kb/articles` (create), `PUT /kb/articles/{id}` (update), `DELETE /kb/articles/{id}` (delete), `GET /kb/my-articles` — all changed from `require_admin_or_planner` to `require_root_admin`
  - Read endpoints and feedback endpoint remain `require_admin_or_planner` so planners can still browse and give feedback
  - Frontend: "Write Article" and "My Articles" buttons wrapped in `{isRootAdmin && ...}` conditional
  - Planner empty state updated to "No articles available in this category yet. Check back soon!"
  - `ArticleView.tsx` `canEdit` simplified from `isRootAdmin || author === currentUser` to just `isRootAdmin`

- **Stripe Checkout Session uses dynamic payment methods** (`app/services/stripe_service.py`):

  - Removed hardcoded `payment_method_types=["card"]` from `stripe.checkout.Session.create()`
  - Stripe now dynamically selects the optimal payment methods per customer from methods enabled in the Stripe Dashboard
  - Automatically enables Apple Pay, Google Pay, and other methods without code changes

- **Stripe exception imports modernized** (`app/services/stripe_service.py`):

  - Changed all `stripe.error.StripeError`, `stripe.error.InvalidRequestError`, `stripe.error.SignatureVerificationError` to direct imports: `from stripe import StripeError, InvalidRequestError, SignatureVerificationError`

### Fixed

- **Stripe `/config` endpoint blocked public payment page** (`app/api/stripe_payment.py`):

  - `GET /stripe/config` had `require_admin_or_planner` dependency, but the couple-facing payment page (`/pay/[id]`) calls it without authentication to initialize Stripe.js
  - Removed auth requirement — the publishable key (`pk_live_` / `pk_test_`) is designed by Stripe to be exposed in client-side code
  - Without this fix, every couple who clicked a payment link would get a 401 error and see a blank page

- **Dark mode animation veil color flipped mid-animation** (`app/components/landing-page/AnchorNav.tsx`):

  - Veil gradient was reading `!isDark` to determine color, but `isDark` flips at 500ms via `setTimeout`, causing React re-render that swapped the veil color halfway through the sweep
  - Added `goingDark` state that locks the transition direction at click time and doesn't change during animation
  - Veil gradient now reads `goingDark` instead of `!isDark`

- **Dark mode animation ring ripples popping in** (`app/components/landing-page/AnchorNav.tsx`):

  - Ring ripple elements had `opacity: 0` inline but keyframe `0%` set `opacity: 1`
  - During staggered animation delay (0s, 0.15s, 0.3s), the inline style took precedence, making rings invisible until delay ended then abruptly visible
  - Changed `animation-fill-mode` from `forwards` to `both` so keyframe `0%` values (including `opacity: 1`) apply during the delay period

### Dead Code Identified (pending removal)

- `app/components/GuestVerificationModalOld.tsx` — superseded by current verification flow
- `app/admin/components/AdminHeader.tsx` — unused legacy header
- `app/utils/tinyInvariantFallback.ts` — unused utility
- `app/admin/components/RootAdminGuard.tsx` — unused guard component
- `app/components/rsvp/SmsOptInForm.tsx` — SMS opt-in built directly into RSVPForm
- `app/components/landing-page/ParallaxSlideshow.tsx` — replaced by Modern3DBackground
- `app/admin/components/PermissionGate.tsx` — only 3 roles exist, no need for generic permission gate
- `app/dependencies/auth.py` — superseded by `auth_extended.py`
- `app/dependencies/auth_basic.py` — superseded by `auth_extended.py`

---

## [2.0.1] - 2026-03-03 — Guest-Facing Theme & Admin Modal Polish

### Changed

- **RSVP Modal Dynamic Theme Colors** (`app/components/RSVPModal.tsx`):

  - Replaced all hardcoded `wedding-rose` (#D4A5A5), `wedding-gold` (#E9C46A), and `wedding-blush` (#F8E8E8) Tailwind classes with dynamic colors pulled from the couple's `theme_config` (accent_color, secondary_color)
  - Added `hexToRgb()` and `lightenColor()` helper functions for computing rgba variants and blush tones at runtime
  - Sets CSS custom properties (`--rsvp-accent`, `--rsvp-accent-rgb`, `--rsvp-secondary`, `--rsvp-secondary-rgb`, `--rsvp-blush`) on `Dialog.Panel` so child components inherit theme colors via cascade
  - Background gradient glow now uses the couple's accent and secondary colors instead of hardcoded values
  - All buttons, error states, spinners, icons, and OTP input focus rings now reflect the couple's chosen palette
  - Safe fallbacks to original hardcoded values when `theme_config` is missing or incomplete

- **RSVP Form Dynamic Theme Colors** (`app/components/RSVPForm.tsx`):

  - Reads `wedding.theme_config` via the existing `useWedding()` hook
  - `FormCard` section titles use CSS variable `var(--rsvp-accent, #D4A5A5)` with built-in fallback
  - Focus rings use Tailwind's internal `--tw-ring-color` CSS variable override for dynamic accent color
  - Checkboxes and radios use the CSS `accent-color` property for native element theming
  - Error state inputs show dynamic accent-colored borders and backgrounds via `accentRgba()` helper
  - Event card hover borders, "Add Guest" button, and "Download Calendar Invite" button all use dynamic theme colors
  - All ~25 hardcoded `wedding-rose`/`wedding-gold`/`wedding-blush` references replaced with inline styles

- **Already RSVPed Screen Dynamic Theme Colors** (`app/components/AlreadyRSVPedScreen.tsx`):

  - Added `useContext(WeddingContext)` for null-safe theme access (avoids throwing unlike `useWedding()`)
  - Gradient accent bar, icon backgrounds, section titles, and buttons now use couple's theme colors
  - All ~8 hardcoded color references replaced

- **Seating Constraints Modal Redesign** (`app/admin/components/seating/SeatingConstraintsModal.tsx`):

  - Replaced green gradient header with app-standard purple/indigo gradient (`from-purple-600 to-indigo-600`) matching other admin modals
  - Added icon badge, subtitle, and styled close button in header
  - Constraint type toggles redesigned as card-style buttons (indigo for "Sit Together", rose for "Keep Apart")
  - Full-width dashed border "Add New Constraint" button with hover accent
  - Group hover reveal for delete buttons (Trash2 icon) instead of always-visible delete
  - Section headers with colored icon badges and count pills
  - Info footer showing constraint summary
  - `backdrop-blur-sm` overlay matching the app's modal design system
  - More breathing room with increased padding throughout

### Fixed

- **Hover Handler Event Target Safety** (`app/components/RSVPForm.tsx`, `app/components/AlreadyRSVPedScreen.tsx`):

  - Changed `e.target` to `e.currentTarget` in `onMouseEnter`/`onMouseLeave` handlers on "Download Calendar Invite Again", "+ Add Guest", and "View Wedding Page" buttons
  - Prevents broken hover effects if button content is ever wrapped in child elements (spans, icons), since `e.target` would reference the child instead of the button
  - Now consistent with event card hover handlers that already used `e.currentTarget`

- **Removed Dead Inline Style** (`app/components/RSVPForm.tsx`):

  - Removed `style={{ borderColor: undefined }}` from the "Download Calendar Invite Again" button — was a no-op that could confuse future maintainers

## [2.0.0] - 2026-03-01 — 1st Release: The Special Wedding SaaS Platform

The first production release of The Special Wedding as a full multi-tenant SaaS platform. This release transforms the original single-wedding website (v1.x at `thespecialwedding.com`) into a scalable platform for wedding planners at `thespecialwedding.io`. Built over 8+ months across 463 commits, consolidating all work from v1.3.0 through v1.7.0-rc.1.

**Key feature pillars:**

- **Multi-Tenant SaaS Architecture** — Org management, role-based access (Root Admin / Planner / Vendor), planner invitations with custom trial durations
- **Stripe Billing** — Subscription plans, checkout sessions, webhook idempotency, credit management
- **OTP Guest Verification** — Twilio SMS/email OTP for secure guest RSVP access, rate limiting, error-specific messages
- **AI-Powered Insights** — Google Gemini integration for budget insights, dashboard insights, seating optimization, contract drafting, with three-tier cache fallback
- **Vendor & Contract Management** — Contract creation, token-based vendor access, milestone payments, PDF generation, email delivery
- **Seating Chart System** — Drag-and-drop canvas, PDF/banner export (WeasyPrint), printable seating charts, capacity validation
- **Web Push Notifications** — VAPID-based browser push replacing self-hosted Ntfy, with per-device subscriptions
- **SMS Delivery Tracking** — Twilio webhook status callbacks, delivery health monitoring, phone status tracking, error classification
- **RSVP Enhancements** — Modal-based flow, already-RSVPed detection, Request RSVP Link for lost invitations, calendar ICS with timezone support, plus-one event inheritance
- **Activity & Audit Logging** — Comprehensive activity feed, TTL-based auto-cleanup, export/compliance endpoints
- **Cloudflare R2 Media Storage** — Gallery uploads with S3v4 signatures, presigned URLs, privacy-aware access
- **Coolify Deployment** — Single-server Docker deployment via `Dockerfile.coolify`, Cloudflare Workers for cron jobs
- **UI Overhaul** — Glassmorphism redesign, comprehensive dark mode, accessibility improvements, infinite scroll landing pages

### Added

- **AI Cache Stable Fallback Lookup** (`app/services/ai_cache_service.py`):

  - New `get_latest_cached_response(feature, tenant_id)` method finds the most recent cached AI response for a feature+tenant pair regardless of context hash
  - First tries non-expired entries, then falls back to expired entries as a last resort
  - Enables the "stale insights > no insights" resilience pattern across all AI features
- **Stable Cache Key Context for AI Endpoints** (`app/api/ai.py`):

  - Both `get_budget_insights` and `get_dashboard_insights` endpoints now pass a stable `cache_context` dict containing only primitive, non-volatile values (budget totals, guest counts, wedding date) to the AI service
  - Excludes volatile data (upcoming_tasks, vendor_payments, days_until_wedding) from cache key generation while still sending full context to the Gemini model for analysis
  - Prevents unnecessary cache misses on page reload when only dynamic/computed fields change
- **Three-Tier AI Fallback Chain** (`app/services/ai_service.py`):

  - Added `cache_context` parameter to `generate()` for stable cache key generation separate from the full AI context
  - Pre-API fallback: when exact cache key misses, checks for any recent cached response before making a Gemini API call
  - Post-failure fallback: on `InsufficientCreditsError` or generic exceptions, returns cached data with a warning instead of hard-erroring
  - Each fallback tier is logged with status (`cached`, `cached_fallback`, `error`) for operational visibility

### Fixed

- **AI Insights Fail to Reload After First Load** (`app/services/ai_service.py`, `app/api/ai.py`):

  - Root cause: volatile context data (upcoming_tasks, vendor_payments, computed days_until_wedding) changed on every page reload, generating a new SHA256 cache key hash each time, causing cache misses → Gemini API calls → credit burn → eventual credit exhaustion → hard error with no recovery
  - Fix: separated cache key generation (`cache_context` with stable primitives) from the full AI context sent to Gemini
- **AI Insights UI Destroyed on Error — Planner Dashboard** (`app/admin/planner/page.tsx`):

  - Error state no longer clears existing insights; previous insights remain visible below an amber warning banner
  - Added specific error messages for HTTP 402 (credits), 429 (rate limit), 503 (unavailable), 504 (timeout)
  - "Try again" retry button now passes `forceRefresh=true` so retry actually attempts a fresh Gemini call instead of hitting the cache again
- **AI Insights UI Destroyed on Error — Budget Page** (`app/admin/budget/page.tsx`):

  - Same pattern as planner dashboard: error no longer clears existing insights
  - Error display changed from red destructive alert to amber warning banner with retry button
  - Panel stays visible on error (`setShowAiInsights(true)` in catch block) so user sees error alongside any previous insights
  - Removed unnecessary toast notification for cached results
- **SMS Error Classifier Utility** (`app/utils/sms_error_classifier.py`):

  - New module that categorizes Twilio error codes into actionable groups: `temporary`, `permanent_recipient`, `account_level`, `compliance`, `unknown`
  - Helper functions: `classify_error()`, `should_retry()`, `is_account_level()`, `is_permanent_recipient()`, `is_compliance()`
  - Used by `_handle_delivery_failure()` in `twilio_webhooks.py` to route each failure to the correct handler
- **Phone Status Tracking on Guest Model** (`app/models/guest.py`):

  - Added `phone_status` field (values: `unknown`, `valid`, `invalid`, `landline`, `unreachable`, `unsubscribed`) and `phone_status_updated_at` to `GuestModel` and `UpdateGuestRequest`
  - Webhook failure handler now sets granular phone status based on Twilio error code (30006 → landline, 30003/30005 → unreachable, 21211/21612/21614 → invalid, 21610/30004/30007 → unsubscribed)
- **Planner Delivery Notification Helpers** (`app/services/planner_notification_service.py`):

  - `notify_delivery_failure()` — creates an in-app notification when an individual SMS or email delivery fails
  - `notify_bulk_delivery_summary()` — creates a summary notification after a bulk send with sent/failed/skipped counts
- **Skip Counters for Email Bulk Sends** (`app/services/email_service_resend.py`):

  - `send_rsvp_invitations()` now returns `skipped_no_email`, `skipped_no_token`, `skipped_opted_out`, and `unreachable_guests` alongside `sent`/`failed`
  - `send_reminders()` now returns `skipped_no_email` and `skipped_opted_out`
  - Planners can see exactly why guests were skipped instead of silent omission
- **Unreachable Guest Warnings in Reminders Page** (`app/admin/reminders/page.tsx`):

  - Wedding Details section now shows amber/red warnings for guests with no contact info, invalid/unreachable phones, or SMS opt-outs
  - Added `phone_status` and `sms_opt_in` to the `Guest` TypeScript interface
- **Skip Detail Display After Bulk Sends** (`app/admin/reminders/page.tsx`):

  - `handleSendInviteLinks`: Success message now shows skip breakdown (e.g., "Skipped: 3 no phone, 2 opted out")
  - `handleSendIndividualMessage`: Displays per-guest `failure_reasons` from the API response
  - All send handlers now call `fetchGuests()` after completion to refresh phone_status changes
- **Infinite Scroll Wheel Effect — SaaS Landing Page & Wedding Slug Page**:

  - Added continuous infinite scroll "wheel" effect where sections cycle in a smooth loop
  - **New file**: `app/components/ui/InfiniteScrollWrapper.tsx` — Reusable infinite scroll engine component
  - **SaaS landing page** (`app/page.tsx`): Rewritten to use `InfiniteScrollWrapper` for marketing sections
  - **Wedding slug page** (`app/components/landing-page/LandingLayout.tsx`): Rewritten to use `InfiniteScrollWrapper` for guest-facing sections
  - **Modified**: `app/components/landing-page/SectionWrapper.tsx` — Made `id` prop optional to support cloned sections
- **Banner-Quality Seating Chart Print** (`app/admin/components/seating/PrintableSeatingChart.tsx`):

  - **New file**: Full-screen print preview modal that renders positioned tables exactly as on the canvas
  - Opens a new browser window with complete HTML/CSS for clean printing
  - `@page` size set to 24×18 inches landscape for banner printing at print shops
  - `-webkit-print-color-adjust: exact` and `print-color-adjust: exact` for color fidelity
  - Wedding-themed design: gold (#E9C46A) decorative corner accents, navy (#1D3557) table headers, Playfair Display headings
  - Unseated guests shown in amber section at the bottom
  - Table cards display guest names with gold dot bullets and group labels
- **Seating Canvas Zoom Controls** (`app/admin/seating/page.tsx`):

  - Added zoom in/out/reset buttons for the seating canvas
  - Canvas uses CSS `transform: scale()` with delta adjustments for table positioning during drag
  - Stats bar showing tables, seated, unseated, and capacity counts

### Fixed

- **Unawaited Async Calls in Email Reminders API** (`app/api/email_reminders.py`):

  - Three endpoints were calling `email_service.send_rsvp_invitations()` and `email_service.send_reminders()` without `await`, returning coroutine objects instead of actual `{"sent": N, "failed": N}` results
  - All three calls now properly awaited
- **Sync Endpoint Calling Async Service — SMS Reminders** (`app/api/reminder_twilio.py`):

  - `send_reminder_twilio` was defined as `def` (sync) but calling an async service method
  - Changed to `async def` with `await`
- **Blocking `time.sleep()` in Email Service** (`app/services/email_service_resend.py`):

  - `time.sleep(0.6)` rate-limit delay was blocking the entire event loop for 0.6s per email
  - Replaced with `await asyncio.sleep(0.6)` in both `send_rsvp_invitations()` and `send_reminders()`
- **ObjectId Conversion Bug in Twilio Webhook Failure Handler** (`app/api/twilio_webhooks.py`):

  - `_handle_delivery_failure()` permanent_recipient and compliance handlers used `{"_id": guest_id}` where `guest_id` is a string — MongoDB `_id` fields require `ObjectId`, so these queries silently matched zero documents and never updated guest records
  - The broken fallback pattern `{"token": {"$exists": True}, "_id": guest_id}` was replaced with proper `_to_object_id(guest_id)` conversion
  - Extracted shared `_to_object_id()` helper to eliminate 5 duplicate inline `from bson import ObjectId` + try/except blocks across `_handle_delivery_failure`, `_attempt_email_fallback`, and `_notify_planner_delivery_failure`
- **Webhook Using Wrong Field for Phone Status** (`app/api/twilio_webhooks.py`):

  - Permanent recipient handler was setting `phone_verified: False` — a field that doesn't exist on the guest model
  - Now sets `phone_status` with granular values (`invalid`, `landline`, `unreachable`) plus `phone_status_updated_at`
  - Compliance handler now also sets `phone_status: "unsubscribed"` and records `sms_opt_out_reason` for all compliance codes (not just 21610)
- **Delivery Health Banner Mixing SMS and Email Metrics** (`app/admin/reminders/page.tsx`):

  - The "Last 24h Delivery" banner was computing rate from all `messageHistory` records including email logs, which inflated the "delivered" count via the `status === 'success'` fallback (email logs don't have Twilio's `delivery_status`)
  - Now pre-filters to SMS records only (`provider === 'twilio' || provider === 'telnyx'`) before computing delivery rate
  - Renamed banner to "Last 24h SMS Delivery" for clarity
- **N+1 Query in SMS Reminder Service** (`app/services/reminder_service_twilio.py`):

  - `send_reminders()` was doing a `find_one()` RSVP lookup per guest (N+1 queries)
  - Replaced with a single bulk query `rsvp_collection.find({"attending": event_type})` pre-loaded into a dictionary lookup
  - For a 200-guest wedding this reduces MongoDB round-trips from ~200 to 1
- **Seating Drag and Drop Not Working** (`app/admin/seating/page.tsx`, `app/admin/components/seating/*`):

  - **Problem**: Guests could not be dragged from the sidebar onto the seating canvas — dragged element was clipped by `overflow-hidden` on the sidebar container
  - **Root cause**: Missing `DragOverlay` component from `@dnd-kit/core`. Without it, the dragged DOM element stays within its parent container and gets clipped at the boundary
  - **Solution**: Added `DragOverlay` that renders a floating copy of the dragged item above all containers. Original item reduces opacity during drag (0.3 for guests, 0.5 for tables). Added `DragStartEvent`, `KeyboardSensor` for accessibility
  - **Impact**: Guests can now be smoothly dragged from sidebar to canvas and between tables
- **Seating Page Not Aligned with Dashboard Theme** (`app/admin/seating/page.tsx`, `app/admin/components/seating/*`):

  - **Problem**: Seating page used raw `bg-white dark:bg-slate-800` cards that didn't match the glass morphism pattern used across the planner dashboard
  - **Solution**:
    - All cards now use the dashboard glass pattern: `bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl border-white/50 dark:border-slate-700/50`
    - Removed heavy `LiquidBackground` (Three.js 3D sphere animation) — replaced with subtle CSS dot-grid pattern
    - `SeatingCanvas.tsx`: Dot grid, zoom support, empty state placeholder
    - `TableNode.tsx`: Glass theme, capacity utilization bar (green/amber/red), drag handle and delete icons on hover
    - `GuestItem.tsx`: Compact mode, drag opacity, glass styling
    - `Sidebar.tsx`: Glass theme, Lucide icons, group count badges, clear search button, `print:hidden`
    - `GlassButton.tsx`: Added `dark:` classes to `secondary` and `ghost` button variants
- **Dark Mode Text Invisible on Wedding Slug Page** (`app/hooks/useTheme.ts`, `app/styles/globals.css`, `app/components/landing-page/EventLocationSection.tsx`, `app/components/landing-page/OurStorySection.tsx`, `app/[slug]/page.tsx`):

  - **Problem**: On the couple's wedding slug page (e.g., `/emmanuel-peace`), many headings and text elements were invisible in dark mode. Section headings like "Wedding Details", "Our Story", "Wedding Party", venue names, dress code text, and side labels ("Bride's Side", "Groom's Side") all disappeared against dark backgrounds
  - **Root cause**: Two issues working together:
    1. The `.theme-primary`, `.theme-secondary`, and `.theme-accent` CSS classes used `color: var(--theme-primary)` with no dark mode variant — the theme primary color `#1e3a5f` (dark navy) was applied identically in both modes
    2. Multiple components used inline `style={{ color: theme?.primary_color }}` which overrides any Tailwind `dark:` class due to CSS specificity, making the globals.css fix insufficient on its own
  - **Solution**:
    - `useTheme.ts`: Added `lightenHex()` utility that lightens hex colors by a configurable percentage. Hook now computes and sets `--theme-primary-light`, `--theme-secondary-light`, `--theme-accent-light` CSS custom properties on the document root
    - `globals.css`: Added `:root` fallback values for the `-light` variables. Added `.dark` overrides for `.theme-primary`, `.theme-secondary`, `.theme-accent` (text) and `.theme-border-primary`, `.theme-border-secondary`, `.theme-border-accent` (border) that switch to the lightened variants
    - `EventLocationSection.tsx`: Removed 3 inline `style={{ color: theme?.primary_color }}` overrides (event dropdown, venue name, dress code). Replaced with `.theme-primary` and `.theme-border-primary` CSS classes
    - `OurStorySection.tsx`: Removed 5 inline style overrides — "Our Story" heading, "Wedding Party" heading, "Bride's Side" and "Groom's Side" subheadings, and member initial placeholders. Replaced with `.theme-primary`, `.theme-secondary`, `.theme-accent` classes
    - `app/[slug]/page.tsx`: Added `dark:` variants to all loading, error, verification, and "not found" states — backgrounds (`dark:from-slate-900 dark:to-slate-800`), text colors, cards, spinners, shadows. Applied to both the main component and `<Suspense>` fallback
  - **Impact**: All text on the wedding slug page is now readable in both light and dark mode, with theme colors automatically lightened for dark backgrounds

### Changed

- **OTP Verification API Optimization** (`app/services/otp_service.py`, `app/api/otp.py`, `app/components/RSVPModal.tsx`, `app/otp/verify/page.tsx`):

  - **Problem**: After OTP verification, frontend made a redundant API call to `/weddings/guest-access/{slug}/{token}` to fetch guest data that was already available
  - **Root cause**: `/otp/verify` endpoint only returned `{"message": "OTP verified"}` with no guest data, forcing frontend to re-fetch
  - **Solution**: Refactored `verify_otp_by_guest_id()` to return full guest data and auth method
  - **Backend changes**:
    - `generate_otp()` now stores `contact_type` in OTP record for accurate auth method tracking
    - `send_otp()` passes contact_type to generate_otp() and updates record on email fallback
    - `verify_otp_by_guest_id()` now returns `{success, guest, auth_method}` instead of `bool`
    - `/otp/verify` endpoint returns guest data and auth_method on success
  - **Frontend changes**:
    - RSVPModal and OTP verify page now use guest data directly from verify response
    - Eliminated redundant API call after OTP verification
  - **Impact**: Faster RSVP flow, reduced server load, accurate auth method tracking (phone_otp vs email_otp)
- **Platform Branding Update** (`app/layout.tsx`, `app/admin/components/Sidebar.tsx`, `public/favicon.svg`):

  - **Browser Favicon**: Added SVG favicon with interlinked rings icon in pink/rose gradient colors
  - **Root Layout Metadata**: Added Next.js metadata export with favicon (`/favicon.svg`) and apple touch icon (`/logo_all.png`)
  - **Admin Sidebar Logo**: Replaced Heart icon with "The Special Wedding" logo image
    - Expanded sidebar: Shows full logo with text (160x40)
    - Collapsed sidebar: Shows cropped logo icon (40x40)
  - **Files**:
    - Created `public/favicon.svg` - SVG rings icon for browser tab
    - Modified `app/layout.tsx` - Added metadata with icons configuration
    - Modified `app/admin/components/Sidebar.tsx` - Replaced Heart icon with NextImage component
  - **Impact**: Consistent branding across browser tabs and admin/planner dashboards

### Fixed

- **Onboarding Modal Not Staying Closed** (`app/admin/planner/page.tsx`):

  - **Problem**: The onboarding modal kept reappearing after planners dismissed it, making it impossible to close
  - **Root cause**: Race condition between the API call to mark onboarding complete and the profile refetch. If the profile returned before MongoDB reflected the update, the useEffect would reopen the modal with stale `onboarding_completed: false` data
  - **Solution**: Added `hasUserDismissedOnboarding` local state flag that tracks when the user has dismissed the modal in the current session, preventing the useEffect from reopening it even if profile data is momentarily stale
  - **Impact**: Planners can now dismiss the onboarding tour and it stays closed
- **Critical: Knowledge Base Model MRO Conflict** (`app/models/knowledge_base.py`):

  - **Problem**: App failed to import due to `TypeError: Cannot create a consistent method resolution order (MRO) for bases MongoModel, UserRelatedModel`
  - **Root cause**: `KnowledgeBaseArticleModel` inherited from both `MongoModel` and `UserRelatedModel`, but `UserRelatedModel` already inherits from `MongoModel` (diamond inheritance)
  - **Solution**: Changed inheritance to only `UserRelatedModel` since it already includes `MongoModel`
  - **Impact**: Knowledge base feature now loads correctly
- **Critical: Migration 006 Index Conflict Causing 502 Bad Gateway** (`app/utils/migrations.py`):

  - **Problem**: Production backend failed to start due to MongoDB `IndexOptionsConflict` error in migration 006
  - **Root cause**: Migration 006 created indexes without explicit names, while `database_indexes.py` created the same indexes with names (e.g., `idx_admin_activity_created`). MongoDB rejects duplicate indexes with different names.
  - **Solution**: Refactored migration 006 to only create TTL indexes (its unique purpose). Non-TTL indexes are now solely managed by `create_all_indexes()` in `database_indexes.py`.
  - **Changes**:
    - Removed duplicate non-TTL index creation for `admin_activity_log`, `activity_logs`, `audit_logs`, and `security_audit_logs`
    - Added `safe_create_ttl_index()` helper function with graceful error handling for "already exists" scenarios
    - Removed unused `down_func_name` variable (fixed linter warning)
  - **Impact**: Production backend starts successfully; planners can log in again

### Added

- **Seating Chart PDF Export Feature** (`app/services/seating_export_service.py`, `app/api/tables.py`, `app/admin/seating/page.tsx`):

  - **Purpose**: Allow planners to export seating charts as printable PDFs for large venue display posters
  - **New service** (`app/services/seating_export_service.py`):
    - `SeatingExportService` class with `generate_seating_chart_pdf()` method
    - Two layout styles: `visual` (floor plan with positioned tables) and `list` (table-by-table guest list)
    - Two paper sizes: `poster` (24×18 inches for venue display) and `tabloid` (11×17 inches for print shops)
    - Elegant styling with gold accents (#d4af37), wedding name header, and guest counts
    - HTML escaping via `_escape_html()` to prevent XSS in guest/table names
    - Supports round and rectangle table shapes with proper CSS styling
  - **New API endpoint** (`app/api/tables.py`):
    - `GET /admin/tables/{wedding_id}/export/pdf` - Export seating chart as PDF
    - Query parameters: `layout` (visual/list), `size` (poster/tabloid)
    - Returns PDF with `Content-Disposition: attachment` for download
    - Handles both string and ObjectId wedding formats for compatibility
  - **Frontend UI** (`app/admin/seating/page.tsx`):
    - New "Export PDF ▾" dropdown button in PageHeader actions
    - Poster and Tabloid size options with descriptions
    - Loading state during PDF generation
    - Dark mode support for dropdown menu
  - **Dependencies**:
    - Added `weasyprint>=62.0` to `requirements.txt`
    - Added system libraries to `Dockerfile.coolify`: libcairo2, libpango, libgdk-pixbuf2.0, libffi
  - **Impact**: Planners can print professional seating charts for venue escort tables
- **Comprehensive Activity Logging System for Planner Dashboard** (`app/services/activity_log_service.py`, `app/services/rsvp_service.py`, `app/api/guest.py`, `app/api/reminder_twilio.py`):

  - **Problem**: Planner activity dashboard (`/admin/planner/activity-log`) only showed support ticket logs - no RSVP, guest, or SMS activity
  - **New service** (`app/services/activity_log_service.py`):
    - Standardized `ActivityLogService` for logging to `activity_logs` collection
    - Activity type constants: `RSVP_RECEIVED`, `RSVP_UPDATED`, `GUEST_ADDED`, `GUEST_UPDATED`, `GUEST_DELETED`, `GUEST_IMPORTED`, `SMS_SENT`, `EMAIL_SENT`, `REMINDER_SENT`
    - Convenience methods: `log_rsvp_received()`, `log_guest_added()`, `log_guest_updated()`, `log_guest_deleted()`, `log_guests_imported()`, `log_sms_sent()`, `log_reminder_sent()`, `log_email_sent()`
  - **RSVP logging** (`app/services/rsvp_service.py`):
    - Added `log_rsvp_received()` call in `_notify_planner_rsvp()` method
    - Logs guest name, response status, plus-one count, and couple names
  - **Guest logging** (`app/api/guest.py`):
    - Added activity logging to `create_guest`, `update_guest`, and `delete_guest` endpoints
    - Logs guest name, changes made, and who performed the action
  - **SMS reminder logging** (`app/api/reminder_twilio.py`):
    - Added activity logging to `send_individual_reminders` endpoint
    - Groups SMS sends by wedding for cleaner activity feed
    - Logs recipient count, reminder type, and channel
  - **Impact**: Planner dashboard now shows comprehensive activity feed with RSVP submissions, guest management, and SMS sends
- **Activity/Audit Log Cleanup & Export Endpoints** (`app/api/admin_activity.py`, `app/api/admin_platform_metrics.py`):

  - **Problem**: No mechanism to prune old logs or export for audit compliance
  - **Admin activity log endpoints** (`app/api/admin_activity.py`):
    - `DELETE /admin/activity-log/cleanup` - Remove activities older than N days (default 90, range 7-365)
    - `GET /admin/activity-log/export` - Export activities as JSON or CSV with filters (action_type, entity_type, date range)
  - **Platform metrics endpoints** (`app/api/admin_platform_metrics.py`):
    - `DELETE /admin/platform/audit-logs/cleanup` - Cleanup audit logs (default 30 days)
    - `DELETE /admin/platform/security-logs/cleanup` - Cleanup security audit logs (default 180 days)
    - `GET /admin/platform/errors/export` - Export error logs as JSON or CSV
    - `POST /admin/platform/errors/{error_id}/acknowledge-and-delete` - Acknowledge single error with export
    - `POST /admin/platform/errors/acknowledge-and-delete-bulk` - Bulk acknowledge errors with export
  - **Export format**: JSON returns array of records; CSV returns downloadable format with headers
  - **Impact**: ROOT_ADMIN can now manage log retention and export for compliance auditing
- **TTL Indexes for Automatic Log Cleanup** (`app/core/database_indexes.py`, `app/utils/migrations.py`):

  - **Problem**: Activity and audit log collections grow indefinitely without cleanup
  - **New indexes** (`app/core/database_indexes.py`):

    - `create_admin_activity_log_indexes()` - Query indexes + 90-day TTL on `created_at`
    - `create_activity_logs_indexes()` - Query indexes + 90-day TTL on `timestamp`
    - `create_audit_logs_indexes()` - Query indexes + 30-day TTL on `timestamp`
    - `create_security_audit_logs_indexes()` - Query indexes + 180-day TTL on `timestamp`
    - `create_errors_indexes()` - Query indexes + 30-day TTL on `acknowledged_at`
  - **Migration 006** (`app/utils/migrations.py`):

    - Creates all TTL indexes on first deploy
    - Handles `IndexKeySpecsConflict` for existing indexes
  - **Retention policy**:

    | Collection              | TTL      | Reason                   |
    | ----------------------- | -------- | ------------------------ |
    | `admin_activity_log`  | 90 days  | Admin action history     |
    | `activity_logs`       | 90 days  | Planner activity         |
    | `audit_logs`          | 30 days  | High-volume HTTP logging |
    | `security_audit_logs` | 180 days | Security compliance      |
    | `errors`              | 30 days  | After acknowledgment     |
  - **Impact**: Database automatically prunes old logs, preventing storage bloat
- **Support Ticket Response Notifications for Planners** (`app/services/support_service.py`, `app/services/planner_notification_service.py`, `app/models/planner_notification.py`, `app/admin/notifications/page.tsx`):

  - **Problem**: When ROOT_ADMIN responded to a planner's support ticket, the planner received no notification
  - **New notification type**: Added `support_ticket_response` to `PlannerNotificationTypes` and `NotificationType` Literal
  - **New helper method**: `notify_support_ticket_response()` in `PlannerNotificationService` creates in-app notification with ticket details
  - **Modified `add_comment()` method**: Now triggers notification when ROOT_ADMIN responds (excludes internal comments and self-responses)
  - **Email notification**: New `_send_ticket_response_email()` method sends formatted HTML email to planner with ticket details and response content
  - **Activity logging**: Comments are now logged to `activity_logs` collection for audit trail
  - **Frontend**: Added `support_ticket_response` to TypeScript interface with teal color indicator and legend entry
  - **Flow**: ROOT_ADMIN adds comment → In-app notification + Email + Web Push (automatic via existing service) → Planner sees response in bell icon and receives email
  - **Guards**: Only non-internal comments trigger notifications; planner's own follow-up comments don't trigger self-notification
- **Request RSVP Link Feature** (`app/components/RequestRSVPLinkModal.tsx`, `app/components/landing-page/ThemedHeroSection.tsx`, `app/components/landing-page/LandingLayout.tsx`, `app/api/guest_verification.py`, `app/services/guest_verification_service.py`):

  - **Purpose**: Allow guests who lost their invitation link to request it via phone or email
  - **User flow**: Guest visits `/{slug}` landing page → clicks "Celebrate with us" button → enters phone/email → receives RSVP link via SMS or email
  - **New modal component** (`app/components/RequestRSVPLinkModal.tsx`):
    - Luxury/modern glassmorphism design with wedding theme colors
    - Phone/email toggle with auto-detection based on input
    - Loading spinner, success state, error handling
    - Dark mode support with gradient decorative border
  - **ThemedHeroSection update** (`app/components/landing-page/ThemedHeroSection.tsx`):
    - Added `onCelebrateClick?: () => void` prop to interface
    - Changed decorative div to interactive button with click handler
  - **LandingLayout integration** (`app/components/landing-page/LandingLayout.tsx`):
    - Added `showRSVPLinkModal` state management
    - Wired modal to ThemedHeroSection's `onCelebrateClick` callback
  - **New API endpoint** (`app/api/guest_verification.py`):
    - `POST /guests/request-rsvp-link` - Request RSVP link via phone or email
    - Pydantic model: `RequestRSVPLinkRequest` with `slug`, `contact`, `contact_type` fields
    - Always returns generic success message to prevent guest enumeration
  - **New service method** (`app/services/guest_verification_service.py`):
    - `request_and_send_rsvp_link()` - Core logic for guest lookup and link delivery
    - **Phone lookup**: Tries multiple stored formats (original, digits-only, E.164 with +1)
    - **Email lookup**: Case-insensitive MongoDB regex query
    - **SMS delivery**: Uses `TwilioReminderService._send_sms()`
    - **Email delivery**: Uses `ResendEmailService.send_email()` with HTML template
    - `_generate_rsvp_link_email_html()` - Professional email template with RSVP button
  - **Security features**:
    - Rate limiting: 3 requests per contact per 10 minutes (hashed contact)
    - Generic success messages prevent guest enumeration attacks
    - No cross-channel leakage (only sends to provided contact type)
    - Security event logging for audit trail
  - **Impact**: Guests can now recover their RSVP link without contacting the couple directly

### Changed

- **Defensive Field Access in Admin Activity Service** (`app/services/admin_activity_service.py`):

  - **Problem**: Direct dictionary access (`doc["field"]`) on MongoDB documents caused `KeyError` when documents had missing fields, resulting in 500 errors on activity log endpoints
  - **Fix**: Changed all field access in `get_activity_log()` and `get_recent_activities()` to use `.get()` with sensible defaults
  - **Example**: `doc["action_type"]` → `doc.get("action_type", "unknown")`
  - **Fields protected**: `admin_id`, `action_type`, `title`, `message`, `entity_type`, `entity_id`, `metadata`, `is_read`, `created_at`
  - **Impact**: Activity log endpoints now gracefully handle malformed or legacy documents
- **Enhanced Activity Type Color Mapping in Planner Dashboard** (`app/admin/planner/activity-log/page.tsx`):

  - **Problem**: Frontend only had colors for 4 activity types; new activity types showed default purple
  - **Added color mapping** for all activity types:
    - RSVP events: `rsvp_received` (green-500), `rsvp_updated` (green-400)
    - Guest events: `guest_added` (blue-500), `guest_updated` (blue-400), `guest_deleted` (blue-300), `guest_imported` (blue-600)
    - Communication: `email_sent` (yellow-500), `sms_sent` (orange-500), `reminder_sent` (amber-500)
    - Support: `support_ticket_created` (red-500), `support_ticket_comment` (red-400)
    - Wedding: `wedding_created` (indigo-500), `wedding_updated` (indigo-400)
  - **Impact**: Activity feed now shows visually distinct colors for each activity type
- **Platform Metrics Response Time Unit Standardization** (`app/api/admin_platform_metrics.py`, `app/admin/platform/page.tsx`):

  - **Eliminated redundant unit conversions**: Backend stored ms → API converted to seconds → Frontend converted back to ms
  - **New flow**: Backend stores ms → API returns ms directly → Frontend displays ms
  - **Field name changes** for clarity (explicit `_ms` suffix):

    | Old Name                      | New Name                           |
    | ----------------------------- | ---------------------------------- |
    | `avg_response_time`         | `avg_response_time_ms`           |
    | `min_response_time`         | `min_response_time_ms`           |
    | `max_response_time`         | `max_response_time_ms`           |
    | `p50`, `p95`, `p99`     | `p50_ms`, `p95_ms`, `p99_ms` |
    | `overall_avg_response_time` | `overall_avg_response_time_ms`   |
  - **Backend changes** (`app/api/admin_platform_metrics.py`):

    - Removed `/1000` divisions when returning response times
    - Updated field names in `_calculate_performance_metrics()` and `_calculate_endpoint_performance()`
  - **Frontend changes** (`app/admin/platform/page.tsx`):

    - Updated TypeScript interfaces (`PerformanceSummary`, `EndpointPerformance`) with new field names
    - Removed `* 1000` multiplications when displaying values
  - **Why**: Reduces cognitive overhead, prevents floating-point precision issues, and follows the principle of keeping data in its natural unit until display
- **AI Chat Service Availability & Health Monitoring** (`app/api/ai.py`):

  - **503 Service Unavailable**: When Google Gemini API is unavailable (network errors, API key issues, quota exceeded), the endpoint now returns proper 503 status instead of 500
  - **Why**: Frontend can detect 503 and show "AI temporarily unavailable" message instead of generic error; follows same pattern as Stripe, Telnyx, and email services in the codebase
  - **New endpoint**: `GET /admin/ai/health` - Health check for AI service monitoring
    - Returns: `{ status: "healthy"|"degraded"|"unhealthy", model, configured, api_key_set, error? }`
    - Tests actual API connectivity by making a minimal request to Gemini
    - Used by platform metrics dashboard for service status monitoring
  - **Enhanced error handling**:
    - `google.api_core.exceptions.GoogleAPIError` for API-level failures (quota, permissions)
    - `requests.exceptions.RequestException` for network connectivity issues
    - Both return 503 with `detail: "AI service temporarily unavailable"`
  - **Platform metrics integration**: AI health status now available alongside other service health checks (Stripe, Twilio, Web Push, Email)
- **Web Push Notifications (Replaces Ntfy)** (`app/services/web_push_service.py`, `app/api/web_push.py`, `app/admin/components/AccountSettingsModal.tsx`, `public/sw.js`):

  - **Complete replacement**: Removed self-hosted Ntfy server dependency in favor of standard Web Push API with VAPID authentication
  - **Why**: Ntfy required users to download a separate app, copy/paste subscription URLs, and perform manual setup - poor UX. Web Push is the industry standard (used by Gmail, YouTube, etc.) where users just click "Allow" and notifications work automatically
  - **New service** (`app/services/web_push_service.py`):
    - VAPID-based authentication using `pywebpush` library
    - Subscriptions stored in MongoDB `push_subscriptions` collection (per user, per device)
    - Methods: `save_subscription()`, `remove_subscription()`, `send_notification()`, `health_check()`
    - Handles expired subscriptions (404/410 responses) with automatic cleanup
  - **New API endpoints** (`app/api/web_push.py`):
    - `GET /admin/web-push/vapid-public-key` - Get VAPID public key for browser subscription
    - `POST /admin/web-push/subscribe` - Save browser push subscription
    - `DELETE /admin/web-push/unsubscribe` - Remove subscription by endpoint
    - `GET /admin/web-push/health` - Health check for monitoring
  - **Service worker** (`public/sw.js`):
    - Handles `push` events with JSON payload parsing
    - Handles `notificationclick` to focus/open app window
    - Handles `pushsubscriptionchange` for subscription renewal
  - **Frontend toggle fix** (`app/admin/components/AccountSettingsModal.tsx`):
    - Toggle now checks actual browser subscription state when modal opens
    - Previously showed DB preference which could be stale on different devices
    - Uses `navigator.serviceWorker.getRegistration()` and `pushManager.getSubscription()`
  - **Platform metrics updated** (`app/admin/platform/page.tsx`, `app/api/admin_platform_metrics.py`):
    - Changed `NtfyHealth` interface to `WebPushHealth`
    - Shows: configured, enabled, has_public_key, has_private_key, vapid_email, total_subscriptions
  - **Config validator updated** (`app/services/config_validator.py`, `app/api/config_errors.py`):
    - Replaced Ntfy alert sending with Web Push
    - Fixed type error: changed `False` sentinel to separate `_web_push_checked` flag
  - **Environment variables**:
    - Removed: `SERVICE_URL_NTFY`
    - Added: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_EMAIL`
  - **Dependencies**: Added `pywebpush>=1.14.0` to `requirements.txt`
  - **Files removed**: `app/services/ntfy_service.py` (deleted)
  - **Generate VAPID keys**: `python -c "from pywebpush import generate_vapid_keys; k=generate_vapid_keys(); print(f'VAPID_PRIVATE_KEY={k[\"private_key\"]}\\nVAPID_PUBLIC_KEY={k[\"public_key\"]}')"`
- **RSVP Form Glassmorphism Redesign** (`app/components/RSVPForm.tsx`, `app/otp/verify/page.tsx`):

  - **Glass design system**: Complete redesign to match SaaS landing page aesthetic
  - **Dark theme**: `bg-slate-950` background with radial gradient overlays and subtle grid pattern
  - **Glass cards**: `backdrop-blur-xl`, `bg-white/5`, `border-white/10`, `rounded-3xl` styling
  - **FormCard component**: Glass card wrapper with wedding-rose uppercase tracking labels
  - **Events section**: Glass checkboxes with hover states (`hover:border-wedding-rose/40 hover:bg-wedding-rose/10`)
  - **Form inputs**: Dark glass inputs (`bg-white/5 text-white placeholder-slate-500`)
  - **Notifications section**: Glass opt-in cards with proper dark theme contrast
  - **Plus-ones section**: Glass guest cards with matching input styling
  - **Submit button**: `rounded-full` with `shadow-wedding-rose/40` glow effect
  - **Success state**: Glass card with wedding-rose accent checkmark and gradient bar
  - **OTP verify page**: Full glass design with matching background effects and animations
- **Plus-One Events Auto-Inherit** (`app/components/RSVPForm.tsx`):

  - Plus-ones now automatically inherit the main guest's selected events on RSVP submission
  - Previously: Plus-ones were submitted with empty `attending: []` array
  - Now: `filledPlusOnes.map(p => ({ ...p, attending: data.attending || [] }))`
  - Fixes "Attending: None" display issue in admin dashboard for plus-ones

### Fixed

- **Wedding ID Lookup Consistency** (`app/api/tables.py`, `app/api/guest_export.py`):

  - **Problem**: PDF export endpoints only queried weddings by string `_id`, failing for ObjectId-based weddings
  - **Solution**: Added dual-format lookup pattern: `ObjectId(wedding_id) if ObjectId.is_valid(wedding_id) else wedding_id`
  - **Files updated**: Seating chart PDF export endpoint, Guest list PDF export endpoint
  - **Impact**: PDF exports now work regardless of whether wedding IDs are stored as strings or ObjectIds
- **Type Annotation Fixes in Twilio Reminder API** (`app/api/reminder_twilio.py`):

  - **Problem**: Pylance/mypy reported type errors for optional service instances and untyped dictionary
  - **Fix 1**: Added `Optional[TwilioReminderService]` and `Optional[TwilioRSVPReminderHelper]` type annotations for conditionally-initialized service variables
  - **Fix 2**: Added `dict[str, int]` type annotation to `wedding_sent_counts` dictionary
  - **Fix 3**: Removed unused `wedding_ids_logged` variable (dead code from previous implementation)
  - **Impact**: Clean type checking with no Pylance/mypy/Flake8 warnings
- **500 Errors on Activity Log Endpoints** (`app/services/admin_activity_service.py`, `app/api/admin_activity.py`):

  - **Root cause**: Direct dictionary access (`doc["field"]`) on MongoDB documents with missing fields raised `KeyError`, causing 500 responses on `/admin/activity-log` endpoints
  - **Fix** (`app/services/admin_activity_service.py`): Changed to defensive `.get()` access with defaults in `get_activity_log()` and `get_recent_activities()`
  - **Fix** (`app/api/admin_activity.py`): Added try-catch error handling to return graceful errors instead of 500
  - **Affected endpoints**: `GET /admin/activity-log`, `GET /admin/activity-log/recent`
  - **Impact**: Activity log endpoints now handle malformed documents gracefully and return empty results instead of crashing
- **RSVP Link SMS Status Check Bug** (`app/services/guest_verification_service.py`):

  - **Root cause**: Twilio `_send_sms()` returns `"status": "failed: {error}"` on failure, but code checked `!= "failed"` which always evaluated to `True`
  - **Fix**: Changed status check from `result.get("status") != "failed"` to `result.get("status") == "success"`
  - **Impact**: SMS send failures are now correctly detected and logged
- **RSVP Link SMS Phone Format Bug** (`app/services/guest_verification_service.py`):

  - **Root cause**: Service passed raw user input (e.g., `(319) 529-6088`) to Twilio, which added `+1` prefix creating invalid `+1(319) 529-6088`
  - **Fix**: Changed to pass `digits_only` (extracted digits) to Twilio, which then correctly formats as `+13195296088`
  - **Impact**: SMS delivery now works regardless of how user formats their phone number input
- **Gallery S3 Operations Failing on Cloudflare R2** (`app/services/gallery_upload_service.py`, `app/services/vendor_service.py`):

  - **Root cause**: Cloudflare R2 requires S3 Signature Version 4 (`s3v4`) for all operations, but boto3 defaults to v2
  - **Symptom**: `AccessDenied` errors on upload, list, and delete operations despite correct credentials
  - **Fix**: Added `config=Config(signature_version='s3v4')` to boto3 client initialization in both services
  - **Fix**: Added error code logging for better diagnostics on S3 operation failures
  - **Impact**: Gallery uploads, listing, and deletion now work correctly with Cloudflare R2
- **Gallery Image Delete Returning 405 Method Not Allowed** (`app/admin/gallery/upload/page.tsx`):

  - **Root cause**: Frontend called `DELETE /gallery` but the admin endpoint is registered at `DELETE /admin/gallery`
  - **Fix**: Changed delete endpoint from `/gallery` to `/admin/gallery` (line 313)
  - **Impact**: Planners can now delete gallery images from the upload management page
- **Private Wedding Gallery Page Returning 403 for Verified Guests** (`app/[slug]/gallery/page.tsx`):

  - **Root cause**: Gallery page was server-side rendered (SSR) and only called `GET /gallery` without guest verification
  - **Symptom**: Guest verifies on landing page → clicks "View Full Gallery" → 403 error because verification state wasn't persisted
  - **Fix**: Converted gallery page to client-side rendering (`'use client'`)
  - **Fix**: Added same verification flow as landing page using `WeddingContext` and `GuestVerificationModal`
  - **Fix**: Public weddings use `GET /gallery?wedding_slug={slug}`
  - **Fix**: Private weddings show verification modal, then use `POST /gallery/verified` with guest token/name/phone
  - **Alignment verified**:
    - `GuestVerificationModal` props: `slug`, `onVerified(wedding, guest?)` ✅
    - `WeddingContext` provides `privacy_mode` field ✅
    - `GalleryGrid` expects `images: {key, url}[]` ✅
    - Backend returns `[{key, url}]` from `gallery/{slug}/` prefix ✅
  - **Impact**: Guests on private weddings can now access the full gallery page after verification
- **Root Admin In-App Notifications Not Displaying** (`app/services/notification_service.py`, `app/services/support_service.py`, `app/utils/secure_error_handler.py`):

  - **Root cause**: Schema mismatch between notification creation and retrieval
    - Notifications created with `target_audience: "root_admin"` but fetched using `user_id` field
    - Root admin has no `user_id` in notifications collection - they use audience-based targeting
  - **Fix** (`app/services/notification_service.py`):
    - Added `get_root_admin_notifications()` method that queries by `target_audience: "root_admin"`
    - Updated `get_notifications()` to handle root admin case with proper audience query
    - Updated `mark_as_read()` and `mark_all_as_read()` to use audience-based queries for root admin
    - Added `delete_notification()` method with proper root admin support
  - **Fix** (`app/services/support_service.py`):
    - Changed notification `target_audience` from `"admin"` to `"root_admin"` for consistency
    - Root admin notifications now use correct audience identifier throughout
  - **Fix** (`app/utils/secure_error_handler.py`):
    - Changed notification `target_audience` from `"admin"` to `"root_admin"` for config error alerts
  - **Impact**: Root admin can now see notification bell count and all in-app notifications for:
    - Support ticket submissions from planners
    - Contact form submissions from public users
    - Configuration error alerts from the system
- **Notification System Schema Alignment** (Multiple files):

  - **API Validation** (`app/api/notification_management.py`):
    - Added `root_admin` to valid `target_audience` values in both `NotificationCreateModel` and `NotificationUpdateModel` validators
    - Previously API would reject notifications with `target_audience: "root_admin"` even though backend services created them
  - **TypeScript Interface** (`app/admin/notifications/page.tsx`):
    - Added `support_ticket`, `system_config`, and `sales_contact` to `PlannerNotification.type` union
    - These types are used by root admin notifications but were missing from the TypeScript interface
  - **Priority Value Standardization** (`app/models/support_ticket.py`, `app/api/reminder.py`, `app/api/twilio_webhooks.py`):
    - Changed default priority from `"normal"` to `"medium"` to match notification system
    - Standardized priority enum to `["low", "medium", "high", "urgent"]` across all systems
    - Previously support tickets used `"normal"` while notifications used `"medium"`
  - **ROOT_ADMIN_EMAIL Fallback** (`app/services/support_service.py`):
    - Updated fallback email domain from `.com` to `.io` to match SAAS platform domain
    - Changed from `thedeveloper@thespecialwedding.com` to `admin@thespecialwedding.io`
  - **Impact**: Full schema alignment between database models, API validation, and frontend TypeScript interfaces
- **Notification Recipient Dropdown Misaligned with Schema** (`app/admin/notifications/page.tsx`):

  - **Root cause**: Dropdown showed `"Trial Users"` and `"Premium Users"` options that don't exist in subscription schema
  - **Subscription status enum**: `PENDING_PAYMENT`, `TRIAL`, `ACTIVE`, `CANCELLED`, `EXPIRED`, `SUSPENDED` - no "premium"
  - **Fix**: Simplified dropdown to match backend `target_audience` values exactly:
    - `all` → All Users
    - `wedding_planners` → Wedding Planners
    - `vendors` → Vendors
  - **Fix**: Removed stale mapping logic - `recipientFilter` now passes directly to `target_audience`
  - **Fix**: Updated default state from `'all_users'` to `'all'`
  - **Impact**: Frontend dropdown now matches backend API validation and subscription schema
- **Root Admin Receiving Own Platform Notifications** (`app/services/notification_service.py`):

  - **Root cause**: Notification retrieval logic included `target_audience: "all"` for root admin
  - **Problem**: When root admin sends notification to "all users", they would also see it in their bell
  - **Fix**: Separated audience logic by role:
    - **Root admin** only sees: `target_audience: "root_admin"` (system alerts) + direct `user_id` targeting
    - **Planners/Vendors** see: `target_audience: "all"` + their role + direct targeting
  - **Fix**: Applied to both `get_user_notifications()` and `get_user_notification_count()` methods
  - **Impact**: Root admin notification bell only shows system alerts (support tickets, config errors, contact forms), not their own platform announcements
- **QR Code Preview Not Displaying in Guest Management** (`app/admin/guests/page.tsx`):

  - **Root cause**: The QR code modal used `<img src>` pointing directly to the authenticated API endpoint, but browsers don't send Authorization headers with image requests
  - **Fix**: Added state variables `qrImageUrl` and `qrImageLoading` to track fetched QR image
  - **Fix**: Added `useEffect` that fetches QR code with proper `Authorization: Bearer ${token}` header when modal opens
  - **Fix**: Converts response blob to object URL for display in the modal
  - **Fix**: Shows loading spinner while fetching, error state if fetch fails
  - **Fix**: Properly cleans up blob URL when modal closes to prevent memory leaks
- **Calendar Invite Download Not Working** (`app/components/RSVPForm.tsx`):

  - **Root cause 1**: Backend `EventDetailsModel.time` uses 12-hour format (`"3:00 PM"`) but frontend expected 24-hour (`"15:00"`)
  - **Root cause 2**: Backend model has no `endTime` field but frontend was trying to use it
  - **Root cause 3**: Invalid Date created when `eventDate` was undefined (`new Date("undefinedT15:00:00Z")`)
  - **Fix**: Added `parseTimeToISO()` helper that handles both 12-hour and 24-hour time formats
  - **Fix**: Use local time parsing instead of UTC to prevent timezone issues
  - **Fix**: Fallback to first event if no `white_wedding` event found, then to `wedding.date`
  - **Fix**: Default 3-hour event duration since backend doesn't have `endTime`
  - **Fix**: Proper ICS format with `\r\n` line endings and required headers (PRODID, CALSCALE, METHOD)
  - **Fix**: Added error handling and URL cleanup with `URL.revokeObjectURL()`
- **Calendar ICS Generates Only One Event with Wrong Time** (`app/components/RSVPForm.tsx`):

  - **Root cause 1**: `generateICS()` only picked one event (white_wedding or first) instead of all configured events
  - **Root cause 2**: `parseTimeToISO()` regex required colon - formats like "6PM" failed, defaulting to 12:00
  - **Symptom**: Planner configured Traditional (05/29 6PM), White Wedding (05/30 5PM), Reception - calendar showed only one event at 12:00PM
  - **Fix**: Enhanced `parseTimeToISO()` to handle hour-only formats: "6PM", "5pm", "6 PM" via new regex `/^(\d{1,2})\s*(am|pm)$/i`
  - **Fix**: Refactored `generateICS()` to loop through ALL `wedding.events` and create multiple VEVENT blocks
  - **Fix**: Each calendar event now has unique UID (`timestamp-index@wedding-rsvp`), event-specific title (e.g., "Traditional Ceremony - Peace & Emmanuel"), and correct time/location/attire
  - **Result**: Downloaded ICS now contains all wedding events with correct dates and times
- **Calendar ICS Missing Timezone Information** (`app/components/RSVPForm.tsx`, `app/models/wedding.py`, `app/types/wedding.ts`):

  - **Root cause**: ICS dates like `20260529T180000` had no timezone indicator - calendar apps interpreted in user's local timezone
  - **Impact**: Guests in different timezones would see wrong event times (e.g., 6 PM Chicago showing as 6 PM Lagos)
  - **Fix**: Added `timezone` field to `WeddingModel` (defaults to `America/Chicago`) and `EventDetailsModel` for per-event override
  - **Fix**: Added `timezone` field to TypeScript `Wedding` and `EventDetails` interfaces
  - **Fix**: ICS now includes `DTSTART;TZID=America/Chicago:20260529T180000` format with explicit timezone
  - **Fix**: Added `X-WR-TIMEZONE` header for calendar app compatibility (Google Calendar, Apple Calendar, Outlook)
  - **Result**: Calendar events now display in the correct wedding venue timezone regardless of guest's location

### Added

- **Wedding Timezone Configuration** (`app/models/wedding.py`, `app/types/wedding.ts`):

  - **New field**: `timezone` on `WeddingModel` - IANA timezone string (e.g., `America/Chicago`, `Africa/Lagos`)
  - **Default value**: `America/Chicago` (US Central Time) for backward compatibility
  - **Per-event override**: `EventDetailsModel.timezone` allows different timezones for events at different venues
  - **Frontend types**: Updated `Wedding` and `EventDetails` TypeScript interfaces
  - **Use case**: Planners can configure the correct timezone for their wedding venue, ensuring calendar downloads show accurate local times
- **Planner Timezone Preference** (`app/models/user_extended.py`, `app/admin/users/page.tsx`, `app/admin/saas/page.tsx`):

  - **New field**: `timezone` on `UserModel` - IANA timezone for display preferences (default: `America/Chicago`)
  - **Frontend types**: Added `timezone` to `Planner` and `WeddingPlanner` TypeScript interfaces
  - **Use case**: Planners see timestamps in their preferred timezone across the dashboard
- **Admin Dashboard Timestamp Consistency** (`app/utils/dateFormat.ts`, 20+ admin pages):

  - **Problem**: ~27 instances of browser-local `.toLocaleString()` caused different users to see different times for the same record
  - **Root cause**: Mix of UTC formatting (centralized utility) and browser-local formatting (direct `.toLocaleString()`)
  - **Enhanced utility** (`app/utils/dateFormat.ts`):
    - Added `getTimezoneAbbreviation()` - Gets timezone abbreviation (CST, EST, WAT) for display
    - Added `formatDateTimeWithTz()` - Format with timezone suffix (e.g., "Jan 30, 2026, 3:00 PM CST")
    - Added `formatAdminTimestamp()` - Primary function for admin dashboard timestamps with timezone indicator
    - Added `formatAdminDate()` - Date-only formatting for admin displays
    - Added `formatListTimestamp()` - Shorter format for tables/lists
    - All functions accept optional timezone parameter (defaults to `America/Chicago`)
  - **Pages updated**:
    - Root admin: `app/admin/page.tsx`, `app/admin/dashboard/page.tsx`
    - Weddings: `app/admin/weddings/page.tsx`, `app/admin/weddings/[id]/page.tsx`
    - Billing: `app/admin/billing/page.tsx`, `app/admin/money/page.tsx`, `app/admin/planner/billing/page.tsx`
    - Vendors: `app/admin/vendors/contracts/[id]/page.tsx`, `app/admin/vendors/contracts/new/page.tsx`, `app/admin/vendors/components/PaymentMilestones.tsx`, `app/admin/vendors/components/VendorPaymentModal.tsx`
    - Users: `app/admin/users/page.tsx`
    - Planner: `app/admin/planner/calendar/page.tsx`, `app/admin/planner/calendar/components/GoogleCalendarConnect.tsx`
    - Forms: `app/admin/forms/[id]/edit/page.tsx`
    - Notifications: `app/admin/notifications/page.tsx`
    - Packages: `app/admin/packages/[id]/send/page.tsx`
  - **Result**: All admin timestamps now show consistent timezone-aware formatting with abbreviation suffix (e.g., "Jan 30, 2026, 3:00 PM CST")
- **Already RSVPed Detection** (`app/components/AlreadyRSVPedScreen.tsx`, `app/otp/verify/page.tsx`, `app/services/guest_verification_service.py`):

  - **Problem solved**: Guests re-visiting RSVP link after submission would go through OTP verification again (Twilio SMS cost ~$0.0079 each)
  - **Backend enhancement**: `get_rsvp_access_by_token()` now checks for existing RSVP in `rsvps` collection
    - Returns `rsvp: { has_rsvp, submitted_at, attending, dietary, plus_ones }` in response
    - Fetches associated plus-ones from `plus_ones` collection
  - **New component**: `AlreadyRSVPedScreen` shows existing RSVP status with glass design
    - Displays guest name, submission date, events attending, dietary restrictions
    - "Edit My RSVP" button to switch to edit mode
  - **Edit mode flow**: `editMode` state allows guests to modify their existing RSVP
  - **Cost savings**: Prevents unnecessary OTP SMS costs for return visitors
- **Twilio SMS Delivery Tracking** (`app/api/twilio_webhooks.py`, `app/services/reminder_service_twilio.py`, `app/core/database_indexes.py`):

  - **StatusCallback webhooks**: Track SMS delivery status (delivered/failed/undelivered) via Twilio webhooks
    - `POST /webhook/twilio/status` - Receives delivery status updates from Twilio
    - Updates `reminders_sent` collection with `delivery_status`, `delivery_events`, and `error_code`
  - **MessageSid tracking**: `_send_sms()` now returns dict with `message_sid` for delivery correlation
    - Log records include `message_sid`, `delivery_status`, `delivery_status_updated_at`, `delivery_events` fields
  - **Database indexes**: Added sparse unique index on `message_sid` field in `reminders_sent` collection
  - **Incoming SMS webhook**: `POST /webhook/twilio/incoming` handles STOP/HELP/START and support messages
    - Routes messages to assigned wedding planner or logs to errors collection for root admin
- **Twilio Platform Monitoring** (`app/api/admin_platform_metrics.py`, `app/admin/platform/page.tsx`):

  - **Backend health check**: `_check_twilio_health()` function checks:
    - Environment variables: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_MESSAGING_SERVICE_SID`, `TWILIO_STATUS_CALLBACK_URL`
    - 24h delivery stats from `reminders_sent` collection: total sent, delivered, failed, pending, delivery rate
    - Status: healthy (>=95%), degraded (>=80%), unhealthy (<80%)
  - **Frontend dashboard card**: New "SMS Service (Twilio)" card in External Services section
    - Shows configuration status, status callback status, delivery stats, and delivery rate percentage
    - Color-coded status indicators and warnings for missing configuration
- **Settings URL Helper** (`app/core/config.py`):

  - Added `get_required_url(url_name)` method to Settings class
  - Returns configured URL or raises ValueError if not set
  - Supports `FRONTEND_URL`, `NEXT_PUBLIC_API_BASE_URL`, `MEDIA_DOMAIN`

### Fixed

- **OTP Rate Limiting Now Uses Settings** (`app/services/otp_service.py`):

  - Fixed hardcoded `timedelta(minutes=4)` rate limit logic to use `settings.rate_limit_auth_period`
  - Rate limiting now uses `created_at` timestamp instead of confusing `expires_at` calculation
  - Both `send_otp()` (line 93) and `send_otp_by_contact()` (line 253) now use configurable rate limit
  - Default: 60 seconds from `RATE_LIMIT_AUTH_PERIOD` env variable
  - Clearer logging: shows seconds since last OTP was sent
- **Admin RSVP Service Async Bug** (`app/services/admin_rsvp_service.py`):

  - Fixed `get_all_rsvps()` using synchronous `list()` with async Motor driver
  - Changed `list(self.guest_collection.find(query))` to `await self.guest_collection.find(query).to_list(length=None)`
  - This bug caused the planner dashboard to fail silently when fetching RSVPs
- **OTP Service Dict Handling** (`app/services/otp_service.py`):

  - Fixed `send_otp()` and `send_otp_by_contact()` to handle dict return from `_send_sms()`
  - Extracts status with `result.get("status") if isinstance(result, dict) else result`
  - Prevents 500 errors when sending OTP via Twilio
- **Removed Slack Integration** (`app/api/twilio_webhooks.py`, `app/api/reminder.py`):

  - Replaced Slack webhook notifications with errors collection logging
  - Unassigned support tickets now appear in platform monitoring Errors tab
  - Root admin gets email notification for unassigned tickets
- **Seating Orchestration Enhancements** (`app/api/tables.py`, `app/admin/weddings/[id]/seating/page.tsx`, `app/admin/components/seating/*`, `app/core/database_indexes.py`):

  - **Server-side capacity validation**: API now rejects guest assignments that would exceed table capacity
    - Returns clear error message: "Cannot assign guests: table capacity is X, would have Y guests after assignment"
    - Prevents over-seating at the API level, not just frontend warnings
  - **Database indexes for seating performance**:
    - `idx_table_wedding_id` on `tables` collection for fast table listing
    - `idx_table_id` on `guests` collection for finding guests at a table
    - `idx_wedding_table` compound index for seating page queries
  - **Batch AI suggestion applications**: Changed from sequential to parallel API calls using `Promise.all()`
    - Significantly faster when applying AI seating suggestions across many tables
  - **Reduced motion accessibility**: LiquidBackground now uses `useReducedMotion` from framer-motion
    - Users with `prefers-reduced-motion: reduce` see a static gradient instead of 3D animation
  - **Capacity warning on drag-over**: Visual indicator when dragging guest to a full table
    - Orange highlight with warning icon and seat count when table is at capacity
  - **Full dark mode support for seating components**:
    - SeatingCanvas, TableNode, Sidebar, and all seating UI elements now support dark mode
    - Header bar, error banner, and modal all have proper `dark:` variants
  - **Frontend error handling**: `useTables` hook now parses API error details
    - Shows actual capacity error messages instead of generic "Failed to assign guests"
  - Validated against Tailwind CSS, dnd-kit, and framer-motion documentation via context7 MCP
- **Guest Export Features** (`app/api/guest_export.py`, `app/services/guest_export_service.py`, `app/admin/guests/page.tsx`):

  - **Individual QR Preview**: View/download QR code for single guest (for physical RSVP cards)
    - `GET /admin/guests/{guest_id}/qr` - Returns QR PNG inline with caching
    - `GET /admin/guests/{guest_id}/qr/download` - Returns QR PNG as attachment for download
    - QR codes link to: `{FRONTEND_URL}/{slug}/invite/{token}` (RSVP page)
  - **Guest List PDF Export**: Printable PDF of guest table
    - `GET /admin/guests/export/pdf` - Returns styled PDF with guest details
    - Columns: Name, Phone, Email, Group, RSVP Status, Dietary
    - Footer shows summary stats (Total, Attending, Pending, Declined)
    - Uses WeasyPrint with lazy import pattern (matches contract_pdf_service.py)
  - **Bulk QR ZIP Download**: Download QR codes as PNG files in a ZIP archive
    - `POST /admin/guests/export/qr-zip` - Returns ZIP of QR PNGs
    - Supports all guests or selected guests via `guest_ids` parameter
    - Files named: `GuestName_token.png` for uniqueness
  - **Frontend Integration** (`app/admin/guests/page.tsx`):
    - [QR] button on guest row actions opens modal with preview + download
    - Export dropdown with PDF, CSV, and ZIP options
    - "Download QR Codes" button in bulk actions bar for selected guests
    - QR Preview Modal with instant display and download button
  - **New Service**: `GuestExportService` with methods:
    - `generate_qr_code(url)` - Generate QR code PNG bytes using qrcode library
    - `build_rsvp_url(slug, token)` - Build RSVP URL for guest
    - `generate_guest_list_pdf(wedding_id, wedding_name)` - Generate styled PDF
    - `generate_guests_qr_zip(guests, slug)` - Generate ZIP archive
    - `get_single_guest_qr(guest_id, wedding_id)` - Get single guest QR with filename
  - **Security**: All endpoints require `require_wedding_planner_only` + `check_wedding_access()`
  - Validated against qrcode, weasyprint, and FastAPI documentation via context7 MCP
- **Bulk Error Acknowledgement Endpoint** (`app/api/admin_platform_metrics.py`):

  - New `POST /admin/platform/errors/acknowledge-bulk` endpoint for acknowledging multiple errors in a single API call
  - Accepts `BulkAcknowledgeRequest` with list of `error_ids`
  - Uses MongoDB `update_many` with `$or` operator to match both `error_id` and `_id` fields
  - Returns `acknowledged_count` and `requested_count` for accurate feedback
  - Replaces 200+ individual API calls with a single operation
  - Validated against PyMongo official documentation via context7 MCP
- **Cursor-Based Pagination for Error Dashboard** (`app/api/admin_platform_metrics.py`, `app/admin/platform/page.tsx`):

  - Replaced `skip()`-based pagination with cursor-based pagination using `_id` range queries
  - **Backend changes:**
    - New `cursor` parameter (error_id from last item of previous page)
    - New `direction` parameter (`'next'` for older, `'prev'` for newer errors)
    - Uses `$lt`/`$gt` operators on indexed `_id` field for O(1) performance
    - Returns `next_cursor` and `prev_cursor` for navigation
  - **Frontend changes:**
    - Replaced page state with `cursorHistory` array for backward navigation
    - New handlers: `handleNextPage()`, `handlePrevPage()`, `handleFirstPage()`
    - Updated pagination controls to use cursor-based navigation
  - **Performance improvement:**
    - `skip()`: O(n) - degrades linearly with offset (page 1000 scans 1000*limit documents)
    - Cursor: O(1) - constant time regardless of how deep into dataset
  - Validated against MongoDB and React official documentation via context7 MCP
- **Error Table Endpoint Column Tooltip** (`app/admin/platform/page.tsx`):

  - Added `title` attribute and `cursor-help` class to truncated endpoint column
  - Full endpoint path now visible on hover for better UX
- **Plus-One Email and Opt-In Fields** (`app/models/plus_one.py`, `app/models/rsvp.py`, `app/services/rsvp_service.py`, `app/services/email_service_resend.py`, `app/components/RSVPForm.tsx`, `app/admin/guests/page.tsx`):

  - Added `email` field to plus-ones so planners can contact them directly
  - Added `sms_opt_in` and `email_opt_in` fields with consent tracking timestamps
  - New fields in `PlusOneModel`: `email`, `sms_opt_in`, `sms_opt_in_date`, `sms_opt_out_date`, `email_opt_in`, `email_opt_in_date`, `email_opt_out_date`
  - Frontend RSVP form now collects plus-one email and shows opt-in checkboxes with compliant consent language
  - Email reminder service (`send_reminders`) now supports `target_group: "plus-ones"` and `"all"` to send reminders to opted-in plus-ones
  - Admin guests page displays plus-one contact info (phone, email) and opt-in status badges (SMS, Email)
  - SMS reminder service already had partial plus-one support; now properly tracks opt-in status
- **Account Setup Name Collection** (`app/api/user_management.py`, `app/setup-account/page.tsx`):

  - Added `first_name` and `last_name` fields to `AccountSetupModel` with validation
  - Frontend form now collects planner's name during account setup
  - Backend passes name fields to `complete_account_setup()` service method
  - Planners no longer show as "Unnamed Planner" after completing account setup
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
- **Push Notifications Toggle** (`app/admin/components/AccountSettingsModal.tsx`, `app/api/user_management.py`, `app/models/user.py`, `app/services/planner_notification_service.py`):

  - Added toggle switch in Account Settings modal for planners to enable/disable push notifications
  - New `push_notifications_enabled` field in `ProfileInfoModel` (defaults to `True` - opt-out model)
  - New `_check_push_enabled()` method in planner notification service checks user preference
  - Ntfy push notifications are skipped if planner has disabled them
  - Gives planners control over mobile/desktop push alerts while keeping in-app notifications active
- **Ntfy Push Notification Diagnostics & Error Logging** (`app/services/ntfy_service.py`, `app/api/admin_platform_metrics.py`, `app/admin/platform/page.tsx`):

  - **Health check endpoint integration**: Ntfy service status now visible in Platform Monitoring dashboard
  - New `health_check()` method in `NtfyNotificationService`:
    - Tests DNS resolution for ntfy server hostname
    - Tests HTTP connectivity with 5-second timeout
    - Reports status: `healthy`, `disabled`, `timeout`, `unreachable`, `auth_required`, or `error`
    - Returns diagnostic info: `configured`, `enabled`, `dns_resolved`, `connection_successful`, `server_url`, `error`
  - **Error logging to database**: Failed push notifications now logged to `errors` collection
    - New `_log_notification_failure()` method logs failures with topic, title, HTTP status, and server URL
    - Errors appear in Platform Monitoring → Errors tab for admin visibility
    - Severity set to `warning` with `source: "ntfy_service"`
  - **Backend integration** (`admin_platform_metrics.py`):
    - `GET /admin/platform/metrics` now includes `services.ntfy` health status
    - Metrics snapshot includes ntfy status for historical tracking
  - **Frontend integration** (`platform/page.tsx`):
    - New "External Services" card in Health tab showing ntfy status
    - Displays: status badge (healthy/disabled/error), configured, DNS resolved, connected, server URL
    - Shows error message with warning icon when ntfy is unhealthy
  - **Root cause identified**: Coolify domain misconfigured as `https://...:80` (HTTPS uses port 443, not 80)
    - Fix: Update Coolify environment variable to `SERVICE_URL_NTFY=http://notify.thespecialwedding.io`
  - Verified ntfy API format against official ntfy documentation via context7 MCP

### Fixed

- **Coolify Deployment — Missing Environment Variables** (`Dockerfile.coolify`, `.github/workflows/deploy.yml`):

  - **Dockerfile.coolify**: Added `BACKUP_SECRET`, `FRONTEND_URL`, `CRON_SECRET` as ARG/ENV declarations for Coolify injection
  - **deploy.yml**: Added `BACKUP_SECRET` and `FRONTEND_URL` to VPS deployment .env file
  - **deploy.yml**: Restricted workflow to only trigger on `feature-twilio-otp-improvements-final-submitted` branch (excluded `main`)
  - **deploy.yml**: Added comment clarifying `DEPLOYMENT_TARGET='coolify'` skips VPS SSH deployment
  - **Impact**: Backup cron authentication and guest export QR code URL generation now work correctly in Coolify deployments
  - Verified against GitHub Actions and Docker official documentation via context7 MCP
- **Cloudflare Workers — Documentation Comment Mismatch** (`cloudflare-workers/metrics-snapshot-cron.js`):

  - Documentation comment referenced `API_URL` but code correctly used `NEXT_PUBLIC_API_BASE_URL`
  - Fix: Updated comment to match actual environment variable name
- **Security: Delete table wedding scope** (`app/api/tables.py`):

  - Fixed guest unassignment query to include `wedding_id` filter when deleting tables
  - Prevents theoretical cross-wedding data leak
  - Query now: `{"table_id": table_id, "wedding_id": table["wedding_id"]}`
- **CRITICAL: Complete RSVP Invite Flow Broken — 7 Bugs** (`app/api/wedding.py`, `app/[slug]/invite/[token]/page.tsx`, `app/components/OTPFlow.tsx`, `app/otp/verify/page.tsx`, `app/admin/guests/page.tsx`, `app/admin/reminders/page.tsx`):

  - **Root cause**: `/weddings/slug/{slug}` endpoint was rewritten for security but stripped the response from `get_wedding_privacy_info()`, removing `id` and `events` that the invite page depends on
  - **Impact**: Guests clicking RSVP links saw 404 pages; SMS templates were missing the domain URL
  - **Bug 1 — Invite page 404** (`app/api/wedding.py:228`): Endpoint returned `{couple_names, slug, privacy_mode}` instead of full `privacy_info` response. Frontend sent `wedding_id=undefined` to guest endpoint → 404
    - Fix: Return `privacy_info` directly (already security-filtered by `get_wedding_privacy_info()`)
  - **Bug 1b — Frontend ID mismatch** (`app/[slug]/invite/[token]/page.tsx:27`): Used `wedding._id` but `get_wedding_privacy_info` returns `id` (no underscore)
    - Fix: `wedding._id` → `wedding.id`
  - **Bug 2 — OTPFlow wrong guest ID** (`app/components/OTPFlow.tsx:21,30`): Used `guest._id` but backend returns `guest.id`
    - Fix: `guest._id` → `guest.id`
  - **Bug 3 — OTP client API paths don't exist** (`app/components/OTPFlow.tsx:18`, `app/otp/verify/page.tsx:36,48,68`): Client-side fetches to `/api/otp/request`, `/api/otp/verify`, `/api/guest/invite/{token}` — no Next.js route handlers exist for these paths
    - Fix: Use `process.env.NEXT_PUBLIC_API_BASE_URL` as base URL for all client-side backend calls
  - **Bug 4 — Missing wedding_id in guest fetch** (`app/otp/verify/page.tsx:48`): Called `/api/guest/invite/{token}` without required `wedding_id` query param → 422
    - Fix: Use `/weddings/guest-access/{slug}/{token}` endpoint which returns both wedding and guest
  - **Bug 5 — RSVPForm missing WeddingContext** (`app/otp/verify/page.tsx:86`): `/otp/verify` page is NOT under `[slug]/` layout, so no WeddingContext provider exists → runtime error
    - Fix: Wrap RSVPForm in `<WeddingContext.Provider>` with wedding data fetched via guest-access endpoint
  - **Bug 6 — SMS template missing domain** (`app/admin/guests/page.tsx:610,2209`): `process.env.FRONTEND_URL` used in `'use client'` component — undefined in browser (no `NEXT_PUBLIC_` prefix)
    - Fix: `process.env.FRONTEND_URL || ''` → `window.location.origin`
  - **Bug 7 — SMS preview missing domain** (`app/admin/reminders/page.tsx:755`): Same env var issue as Bug 6
    - Fix: `process.env.FRONTEND_URL || ''` → `window.location.origin`
  - **OTPFlow slug param**: Added `slug` prop to OTPFlow component, passed through redirect URL to OTP verify page
  - Verified field names against database schemas: `WeddingModel._id` (string), `GuestModel.wedding_id` (string), `get_wedding_privacy_info()` returns `id: str(wedding._id)`
- **Guest Export QR Code — Wrong MongoDB Query Field** (`app/services/guest_export_service.py:420`):

  - `get_single_guest_qr()` queried weddings collection with `{"wedding_id": wedding_id}` but wedding documents use `_id` as primary key, not `wedding_id`
  - Query never matched any wedding → always returned `None` → QR code generation silently failed
  - Fix: `{"wedding_id": wedding_id}` → `{"_id": wedding_id}`
- **Guest Export API — Same Wrong Query Field Bug** (`app/api/guest_export.py:110,163`):

  - PDF export endpoint (`GET /guests/export/pdf`) queried `{"wedding_id": wedding_id}` → always returned `None` → PDF header showed "Wedding" instead of couple names
  - ZIP export endpoint (`POST /guests/export/qr-zip`) queried `{"wedding_id": request.wedding_id}` → always returned `None` → endpoint returned 404 "Wedding not found" for every request
  - Both fixes: `{"wedding_id": ...}` → `{"_id": ...}`
  - Note: Same bug pattern as `guest_export_service.py:420` fix above, but in the API layer
- **Guest Export URL Fallback Logic** (`app/services/guest_export_service.py:84-87`):

  - `build_rsvp_url()` had broken fallback logic for `FRONTEND_URL` environment variable
  - Code called `os.getenv("FRONTEND_URL", "")` then checked if empty and called it again with different default - the second call would still return empty string
  - Fix: Simplified to `os.getenv("FRONTEND_URL") or "https://thespecialwedding.io"`
  - **URL format**: Generates full RSVP URL as `{FRONTEND_URL}/{slug}/invite/{token}` (e.g., `https://thespecialwedding.io/emmanuel-peace/invite/abc123xyz`)
  - **Note**: Ensure `FRONTEND_URL` environment variable is set in Coolify to match your production domain
- **Cloudflare Workers — Multiple Configuration Issues** (`.github/workflows/deploy-workers.yml`, `cloudflare-workers/*.js`, `cloudflare-workers/*.wrangler.toml`):

  - **Issue 1 — Workflow branch condition**: Workflow only triggered on `main` or `development/saas-features`, not current branch `feature-twilio-otp-improvements-final-submitted`
    - Fix: Added current branch to trigger list and simplified condition using `startsWith()`
  - **Issue 2 — Metrics snapshot missing secrets**: `metrics-snapshot.wrangler.toml` deployment had no `wrangler secret put` commands
    - Fix: Added `NEXT_PUBLIC_API_BASE_URL`, `ADMIN_TOKEN`, `RESEND_API_KEY`, `ALERT_EMAIL`, `ROOT_ADMIN_EMAIL` secrets
  - **Issue 3 — Inconsistent API URL variable**: `trial-cron.js` and `metrics-snapshot-cron.js` used `env.API_URL` (hardcoded in wrangler.toml), other workers used `env.NEXT_PUBLIC_API_BASE_URL` (set via GitHub secrets)
    - Fix: Changed all workers to use `NEXT_PUBLIC_API_BASE_URL` for consistency
  - **Issue 4 — Hardcoded API URLs in wrangler.toml**: `trial.wrangler.toml` and `metrics-snapshot.wrangler.toml` had `API_URL = "https://api.thespecialwedding.io"` hardcoded
    - Fix: Removed hardcoded URLs, now all workers get API URL from GitHub secrets
  - **Issue 5 — Wrong admin dashboard URLs**: All workers had `https://admin.thespecialwedding.io/admin/*` (non-existent subdomain)
    - Fix: Changed to `https://thespecialwedding.io/admin/*` (path-based routing)
  - **Issue 6 — KV namespace replacement fragile**: sed command used `-i` with simple pattern that might not match
    - Fix: Added multiple pattern handling and better error logging
  - **Issue 7 — Typo in ALERT_EMAIL**: `trial.wrangler.toml` had `alertsd@thespecialwedding.io` (extra 'd')
    - Fix: Removed hardcoded email, now set via GitHub secrets
  - **Files modified**:
    - `.github/workflows/deploy-workers.yml`
    - `cloudflare-workers/autopilot-cron.js`
    - `cloudflare-workers/backup-cron.js`
    - `cloudflare-workers/uptime-cron.js`
    - `cloudflare-workers/trial-cron.js`
    - `cloudflare-workers/metrics-snapshot-cron.js`
    - `cloudflare-workers/trial.wrangler.toml`
    - `cloudflare-workers/metrics-snapshot.wrangler.toml`
- **Planner Notifications — Wrong Wedding Query Field** (`app/services/rsvp_service.py:150`, `app/services/stripe_service.py:1519`, `app/services/form_service.py:997`):

  - Same bug pattern as guest export: queried weddings collection with `{"wedding_id": wedding_id}` instead of `{"_id": wedding_id}`
  - **Impact**: Planner notifications silently failed — planners never received push/in-app notifications for:
    - RSVP updates (guest confirmed/declined attendance)
    - Payment received (Stripe payment success)
    - Form submissions (contact forms, vendor inquiries)
  - All three queries returned `None` → code exited early without sending notification
  - Fix: `{"wedding_id": wedding_id}` → `{"_id": wedding_id}` in all three services
  - Validated against `WeddingModel` schema: `id: str = Field(..., alias="_id")`
- **SMS/Email Opt-In Default Values** (`app/services/guest_service.py`, `app/services/import_service.py`):

  - Fixed new guests being created as "opted out" before receiving any message
  - **Root cause**: `sms_opt_in: False` and `email_opt_in: False` hardcoded on guest creation
  - **Impact**: Reminder service blocked messages for guests who hadn't opted out
  - **Fix**: Changed defaults to `True` (opted-in) - guests can opt-out later via RSVP form
  - `guest_service.py` line 242: `"sms_opt_in": False` → `"sms_opt_in": True`
  - `guest_service.py` line 243: `"email_opt_in": False` → `"email_opt_in": True`
  - `import_service.py`: Added explicit `"sms_opt_in": True, "email_opt_in": True` for imported guests
- **CSRF Middleware Blocking Guest RSVP Flow** (`app/main.py`, `app/core/settings.py`):

  - **Root cause**: CSRF middleware required `X-CSRF-Token` header + `csrf_token` cookie for all POST requests, but guest-facing pages don't have CSRF tokens
  - **Impact**: Guests clicking "Verify My Identity" on RSVP page saw "CSRF token missing in request header or cookie" error
  - **Analysis**: CSRF protection is redundant for this application because:
    1. Admin pages use JWT Bearer tokens (CSRF-immune by design - browsers don't auto-attach Authorization headers cross-origin)
    2. Guest pages use URL token-based auth (not vulnerable to CSRF - attacker would need to know the token)
    3. No session cookies are used that could be exploited
  - **Verified against OWASP guidelines**:
    - [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html): Custom request headers trigger CORS preflight, preventing cross-origin requests
    - [OWASP CSRF Attack](https://owasp.org/www-community/attacks/csrf): "all cookies will be submitted with every request" — JWT in Authorization header is not auto-attached
  - **Fix**: Removed CSRF middleware entirely
    - `app/main.py`: Removed `CSRFProtectionMiddleware` import and registration
    - `app/core/settings.py`: Changed `csrf_enabled` default from `True` to `False`
  - **Note**: CSRF middleware file (`app/middleware/csrf_protection.py`) retained with expanded `exclude_paths` documenting which endpoints would need exemption if CSRF is re-enabled:
    - `/otp/` - OTP endpoints (phone verification)
    - `/forgot-password` - Password recovery (email-based)
    - `/reset-password` - Password reset (uses reset token)
    - `/setup/` - Account setup (uses invitation token)
    - `/signup` - User registration
    - `/contact` - Contact forms (public)
- **OTP Request Returns Generic Error Message** (`app/services/otp_service.py`, `app/api/otp.py`):

  - **Root cause**: `send_otp()` returned `True/False` with no error details; API returned generic "Failed to send OTP" for all failure cases
  - **Impact**: Guests saw unhelpful error message when OTP failed (e.g., missing phone number displayed as "Failed to send OTP")
  - **Fix**: Modified `send_otp()` to return dict with specific error messages:
    - `{"success": False, "error": "Invalid guest ID format"}` — invalid ObjectId
    - `{"success": False, "error": "Please wait before requesting another code"}` — rate limited
    - `{"success": False, "error": "Guest not found"}` — guest doesn't exist
    - `{"success": False, "error": "No phone number on file. Please contact the wedding planner."}` — missing phone
    - `{"success": False, "error": "Failed to send SMS. Please try again later."}` — Twilio error
  - **Also fixed**: `/otp/verify` endpoint was calling wrong method (`verify_otp` instead of `verify_otp_by_guest_id`) and missing `async/await`
- **OTP Rate Limiting Math Error + Double-Submit Race Condition** (`app/services/otp_service.py`, `app/otp/verify/page.tsx`):

  - **Bug 1 — Rate limit blocks ALL resends for 5 minutes** (lines 73, 205):
    - **Root cause**: Condition `expires_at > datetime.utcnow() - timedelta(minutes=4)` should be `+ timedelta(minutes=4)`
    - **Why**: OTP expires in 5 minutes. To rate-limit for 1 minute: `expires_at > now + 4min` (sent < 1 min ago)
    - **Impact**: Current logic is ALWAYS true for valid OTPs, blocking ALL resends until OTP expires
    - **Fix**: Changed `- timedelta(minutes=4)` → `+ timedelta(minutes=4)` in both `send_otp()` and `send_otp_by_contact()`
  - **Bug 2 — Double-click causes "Invalid or expired OTP"** (`app/otp/verify/page.tsx`):
    - **Root cause**: No double-submit protection; OTP deleted on first successful verify, second request fails
    - **Impact**: Network shows success but UI shows error (first click succeeded, second failed)
    - **Fix**: Added `isSubmittingRef` guard to prevent concurrent verify requests
  - **Bug 3 — Frontend/backend timer mismatch** (`app/otp/verify/page.tsx`):
    - **Root cause**: Frontend hardcoded 60s cooldown but server blocked for 5 minutes (due to Bug 1)
    - **Fix**: Changed cooldown from 60 to 65 seconds (5 seconds buffer over server's 1-minute limit)
  - **Bug 4 — datetime.utcnow() deprecated** (`app/services/otp_service.py`):
    - **Root cause**: `datetime.utcnow()` returns naive datetime, deprecated in Python 3.12+
    - **Impact**: Potential timezone issues with MongoDB TTL index and comparison operations
    - **Fix**: Replaced all 7 occurrences with `datetime.now(timezone.utc)` (timezone-aware)
  - **Bug 5 — OTP verify success but RSVP form doesn't appear** (`app/otp/verify/page.tsx`):
    - **Root cause**: After OTP verify succeeds, `/weddings/guest-access/{slug}/{token}` fetch may fail; error thrown before `setIsVerified(true)`
    - **Impact**: OTP is consumed (deleted) but guest is stuck on verify screen with no way to proceed
    - **Fix**: Added `otpVerified` state to track OTP success separately; added retry UI when wedding data fetch fails after successful OTP verification
- **Forms API 404 Error** (`app/services/formsApi.ts`):

  - Fixed "Not Found" error when accessing Forms page in planner dashboard
  - **Root cause**: Frontend called `/admin/forms` but backend registers routes at `/forms` (no `/admin` prefix)
  - **Fix**: Removed `/admin` prefix from all form API paths in frontend service
  - Affected methods: `fetchForms`, `fetchTemplates`, `createBlankForm`, `createFromTemplate`, `duplicateForm`, `markScopeViewed`
  - Path changes:
    - `/admin/forms` → `/forms`
    - `/admin/form-templates` → `/form-templates`
    - `/admin/forms/from-template/{id}` → `/forms/from-template/{id}`
    - `/admin/forms/{id}/duplicate` → `/forms/{id}/duplicate`
    - `/admin/forms/{id}/views` → `/forms/{id}/views`
- **False Positive Error Acknowledgement** (`app/admin/platform/page.tsx`):

  - Fixed "Acknowledged 200 errors" toast showing success when all acknowledgements actually failed
  - Root cause: `Promise.allSettled()` marks promises as "fulfilled" even when HTTP response is 4xx/5xx
  - The code only checked `r.status === 'fulfilled'` without verifying `response.ok`
  - **Before:** 200 errors "acknowledged" but unacknowledged count remained 200
  - **After:** Uses bulk endpoint for single API call, properly reports actual success/failure count
  - Validated against MDN Fetch API documentation via context7 MCP
- **Duplicate `/admin/admin/` API Route Prefix** (`app/api/admin_activity.py`):

  - Fixed 404 errors on activity log endpoints due to double `/admin` prefix
  - Root cause: Router defined `prefix="/admin"` AND was mounted with `prefix="/admin"` in `main.py`
  - Changed `router = APIRouter(prefix="/admin", tags=["ROOT_ADMIN"])` to `router = APIRouter(tags=["ROOT_ADMIN"])`
  - Affected endpoints now work correctly:
    - `/admin/admin/activity-log` → `/admin/activity-log`
    - `/admin/admin/activity-log/recent` → `/admin/activity-log/recent`
  - Validated against FastAPI APIRouter documentation via context7 MCP
- **Notification Polling Performance & Resource Waste** (`app/admin/components/TopHeader.tsx`):

  - Fixed aggressive polling that continued even after authentication failures (401 errors)
  - **Issues fixed:**
    - Polling continued indefinitely despite 401 unauthorized responses
    - No exponential backoff on errors - same rate even during failures
    - Polling continued when browser tab was hidden (wasted resources)
    - No debouncing on window focus events - caused rapid duplicate requests
  - **Improvements:**
    - Added `stopPolling()` on 401 authentication errors - stops wasting server resources
    - Added Page Visibility API - pauses polling when tab is hidden, resumes when visible
    - Added exponential backoff: 60s → 120s → 240s → 300s (max) on consecutive errors
    - Added 2-second debounce on focus events to prevent rapid duplicate calls
    - Properly cleans up intervals on unmount and visibility changes
- **Double `/admin/admin/` Prefix in API Paths** (`app/admin/users/page.tsx`, `app/admin/page.tsx`):

  - Fixed 404 errors caused by duplicate `/admin` prefix in invitation and activity log API calls
  - Affected endpoints (all returning 404):
    - `/admin/admin/invitations` → fixed to `/admin/invitations`
    - `/admin/admin/invitations/stats` → fixed to `/admin/invitations/stats`
    - `/admin/admin/invitations/{id}/resend` → fixed to `/admin/invitations/{id}/resend`
    - `/admin/admin/invitations/{id}/cancel` → fixed to `/admin/invitations/{id}/cancel`
    - `/admin/admin/activity-log/recent` → fixed to `/admin/activity-log/recent`
  - Root cause: Frontend code incorrectly included `/admin` twice in URL paths
- **Profile Page API Path Mismatches** (`app/admin/profile/page.tsx`):

  - Fixed 404 errors on profile update operations (password, email, info, image)
  - Root cause: `user_management.py` profile endpoints are mounted WITHOUT `/admin` prefix, but frontend used `/admin/profile/...`
  - Fixed API paths:
    - `/admin/profile/password` → `/profile/password` (PUT)
    - `/admin/profile/email` → `/profile/email` (PUT)
    - `/admin/profile/info` → `/profile/info` (PUT)
    - `/admin/profile/image` → `/profile/image` (POST upload, DELETE remove)
  - Note: `GET /admin/profile` remains correct (served by `admin_auth.py` with `/admin` prefix)
  - This affects both root admin and planner profile pages
- **Account Settings Modal Issues** (`app/admin/components/AccountSettingsModal.tsx`, `app/api/admin_auth.py`):

  - Fixed "Not Found" error when clicking "Save Changes"
    - Root cause: Frontend was calling `/admin/profile/info` but endpoint is at `/profile/info` (no `/admin` prefix)
    - Fixed all API paths (password, email, info, image) to use correct endpoints
  - Fixed modal positioning (was appearing off-center/inside header dropdown)
    - Root cause: Modal was rendered inside `<header>` element, interfering with `fixed` positioning
    - Solution: Used React Portal (`createPortal`) to render modal at document.body level
    - Added `z-[9999]` to ensure modal appears above all other elements
  - Improved modal UI design:
    - Added gradient header background with subtitle
    - Redesigned tab navigation with pill-style selector
    - Improved Save button styling with shadow and better spacing
    - Added smooth animations (fade-in, zoom-in)
    - Better dark mode support
  - Added `push_notifications_enabled` field to `GET /admin/profile` response (defaults to `true`)
- **CRITICAL: User Management Operations Failing (Delete/Suspend/Activate)** (`app/services/user_management_service.py`):

  - Fixed "Failed to delete user" error when attempting to delete a planner from Planner Management page
  - Root cause: User ID passed as string but MongoDB stores `_id` as ObjectId - query never matched
  - Added `from bson import ObjectId` conversion to all user-by-ID queries:
    - `get_user()`: Now converts string to ObjectId before querying
    - `update_user()`: Now converts string to ObjectId before updating
    - `delete_user()`: Now converts string to ObjectId before find and delete
    - `suspend_user()`: Now converts string to ObjectId, also sets `is_suspended: True`
    - `activate_user()`: Now converts string to ObjectId, also sets `is_suspended: False`
    - `assign_wedding_to_planner()`: Now converts user_id string to ObjectId
  - Pattern now matches all other services in codebase (subscription_service, stripe_service, autopilot_service, etc.)
  - Also added `is_suspended` field to user document for frontend status display
- **Code Quality & Type Safety Fixes** (Multiple files):

  - **subscription_service.py**: Added missing `subscription_service = SubscriptionService()` singleton instance at end of file
    - Fixes `"subscription_service" is unknown import symbol` error when importing from other modules
  - **subscription_service.py**: Removed unused Pydantic model imports (`SubscriptionPlanModel`, `UserSubscriptionModel`, `UsageTrackingModel`, `SubscriptionStatus`, `BillingInterval`)
    - Service uses raw MongoDB dictionaries instead of these models
  - **user_management_service.py**: Removed unused `stripe_service` import (line 118)
    - The `stripe` module is imported directly elsewhere in the file
  - **user_management_service.py**: Fixed type error for `trial_end_date` timestamp conversion
    - Changed `datetime.fromtimestamp(subscription.trial_end)` to `datetime.fromtimestamp(subscription.trial_end) if subscription.trial_end else None`
    - Handles case where `subscription.trial_end` is `None` (no trial period)
- **Root Admin Notification Badge Never Clears** (`app/services/notification_service.py`):

  - Fixed notification badge showing count that never clears for root admin
  - Root cause: Root admin was receiving their own notifications (via `target_audience: "all"`)
  - Added `{"created_by": {"$ne": user_email}}` filter to exclude notifications created by the current user
  - Modified `get_user_notifications()` at line 293 and `get_user_notification_count()` at line 481
  - Logical behavior: Creators should not receive their own announcements
  - Planners unaffected (they don't create notifications)
- **Platform Errors Tab Data Mismatch** (`app/api/admin_platform_metrics.py`):

  - Fixed Errors tab showing 0 errors while Dashboard showed 236 errors
  - Root cause: `audit_logs` collection (where HTTP 4xx/5xx errors are stored) was only queried when `acknowledged=None`
  - When "Unacknowledged" filter was selected (`acknowledged=False`), `audit_logs` were skipped entirely
  - Changed line 720 from `acknowledged is None` to `acknowledged is not True`
  - Now includes `audit_logs` for both "All" and "Unacknowledged" views, excludes only for "Acknowledged" view
  - `audit_logs` entries don't have an `acknowledged` field, so they're inherently unacknowledged
- **PlannerNotificationTypes Type Errors** (`app/models/planner_notification.py`):

  - Fixed 8 type errors in `planner_notification_service.py` where notification type constants were incompatible with `NotificationType` Literal
  - Root cause: Type checker saw `PlannerNotificationTypes.FORM_SUBMISSION` as `str`, not `Literal["form_submission"]`
  - Solution: Added `Final[Literal["..."]]` type annotations to all class constants
  - Changed from `FORM_SUBMISSION: Literal["form_submission"]` to `FORM_SUBMISSION: Final[Literal["form_submission"]]`
  - `Final` tells type checker the value is immutable and should preserve its literal type
  - Affected constants: `FORM_SUBMISSION`, `RSVP_UPDATE`, `GUEST_MESSAGE`, `PAYMENT_RECEIVED`, `PAYMENT_FAILED`, `CONTRACT_SIGNED`, `VENDOR_RESPONSE`, `REMINDER`, `SYSTEM`
- **Undefined Function in Metrics Snapshot** (`app/api/admin_platform_metrics.py:578`):

  - Fixed `NameError: name 'get_platform_metrics' is not defined` in `save_metrics_snapshot` endpoint
  - Changed `await get_platform_metrics(current_user)` to `await get_platform_health(current_user)`
  - The function was renamed but this call site was not updated
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

- **Multi-Tenant Data Isolation** (Multiple files):

  - **Guest Search Endpoint** (`app/api/guest.py`):
    - `/invite/search` now requires authentication via `require_wedding_planner_only`
    - Added mandatory `wedding_id` parameter to prevent cross-wedding guest enumeration
    - Added ownership verification via `check_wedding_access()` before returning results
  - **Guest Service** (`app/services/guest_service.py`):
    - `get_guest_by_phone_or_name()` now accepts and filters by `wedding_id`
    - Prevents planners from accessing guests outside their assigned weddings
  - **Gallery Admin Endpoints** (`app/api/gallery_admin.py`):
    - Added `verify_wedding_access_by_slug()` helper for ownership validation
    - All endpoints now validate wedding ownership via `assigned_planner_email` field
    - `/gallery/upload-url`: Validates planner access before generating presigned URL
    - `/gallery/file-url`: Extracts wedding_slug from key path and validates ownership
    - `DELETE /gallery`: Validates ownership before allowing file deletion
    - `/gallery/list`: Filters results by wedding access, returns empty for unauthorized
    - `/gallery/upload`: Validates wedding access before accepting uploads
  - **OTP Rate Limiting** (`app/services/otp_service.py`):
    - Added rate limiting to `send_otp_by_contact()` method (1 OTP per minute per guest)
    - Prevents OTP spam attacks while keeping endpoint public for guest verification
    - Uses existing OTP expiry (5 min) minus 4 min buffer to calculate rate limit window
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

### Pre-Launch QA Fixes (formerly 1.7.0-rc.1 - 2026-03-01)

Comprehensive QA review identified 66 frontend-backend alignment issues (21 CRITICAL, 24 HIGH, 16 MEDIUM, 5 LOW). All CRITICAL and HIGH severity issues fixed below. MEDIUM/LOW items also completed.

### Fixed

- **Budget: 9 CRITICAL endpoint path mismatches** (`app/services/budgetApi.ts`):

  - B1/B2: Vendor quotes GET/POST path (`vendor-quotes` → `quotes`)
  - B3: Quote status PUT path (`vendor-quotes` → `quotes`)
  - B4: Delete category path (`categories` → `category`, singular)
  - B5: Get quotes response unwrapping (backend returns `{quotes: [...]}`)
  - B7: Compare quotes path — query param → path param (`/quotes/compare/{category}`)
  - B8: Budget alerts GET path structure
- **AI: CRON_SECRET security vulnerability** (`app/api/autopilot.py`):

  - A2: Added fail-closed guard — if `CRON_SECRET` is not set, all cron requests are rejected instead of silently bypassed
- **AI: Seating and forecast mismatches** (`app/api/ai.py`, `app/admin/money/page.tsx`):

  - A1: Fixed seating optimization parameter mismatch — added all required guest fields
  - A3: Added AI client initialization check to seating endpoint
  - A4: Fixed forecast response shape — frontend reads flat response instead of nested `data.forecast`
- **Seating: ID format and data integrity** (`app/api/tables.py`, `app/api/guest.py`, `app/services/guest_service.py`):

  - T1: Invalid guest IDs now return validation error instead of being silently skipped
  - T8: Added atomic update with version check for concurrent table assignments
  - T4: Added server-side capacity validation with specific error when table is full
  - T7: Fixed constraint endpoint string vs ObjectId conversion
  - T2/T6: Guest deletion now cleans up orphan `must_sit_with`/`must_sit_apart` references
- **Stripe: Auth and billing page failures** (`app/admin/billing/success/page.tsx`, `app/admin/planner/billing/page.tsx`, `app/dependencies/feature_gates.py`):

  - S2: Fixed auth token name (`authToken` → `admin_token`)
  - S3: Subscription fetch uses actual `user_id` from auth context instead of email
  - S8: Feature gate checks both `user_id` and `user_email` for subscription lookup
- **Stripe: Webhook idempotency** (`app/services/stripe_service.py`):

  - S7: Added idempotency tracking via Stripe event ID to prevent duplicate processing
- **Contracts: 9 missing backend endpoints** (`app/api/contracts.py`):

  - C3: `POST /contracts` — full contract creation with vendor lookup, auto-generated number, secure token
  - C2: `POST /milestones/{milestone_id}/pay` — record vendor payment (pending → partial → paid)
  - C4: `PUT /contracts/{contract_id}/sections` — update sections with status validation
  - Added: `PUT /contracts/{contract_id}`, `POST /contracts/{contract_id}/send`, `POST /contracts/{contract_id}/milestones`, `GET /contracts/{contract_id}/form-data`, `POST /contracts/{contract_id}/apply-form-data`, `GET /milestones`
- **Contracts: Service-layer fixes** (`app/services/contract_service.py`):

  - C5: Auto-generates contract numbers in `CON-YYYYMMDD-XXXX` format
  - C11: Added 30-day token expiration; cancelled/completed contracts expire immediately
  - C13: Status transition validation — only draft/pending_review can be updated or sent
- **Contracts: Frontend alignment** (`app/admin/vendors/contracts/[id]/page.tsx`, `app/services/contract_email_service.py`):

  - C9: Wired up "View & Apply Form Data" button onClick handler
  - Fixed `GET /contracts/{contract_id}` response format (was `{contract: ...}`, frontend expects direct object)
  - Added `send_contract_email()` — HTML email with "View & Sign Contract" CTA
- **Contracts: Route ordering bug** (`app/api/contracts.py`):

  - Moved `/contracts/followup-drafts` routes before `/contracts/{contract_id}` to prevent FastAPI route shadowing

### Security

- B9-SEC: Added wedding access control to `update_budget_category()` and `delete_budget_category()` — closes cross-tenant data modification vulnerability
- A2: CRON_SECRET fail-closed guard prevents unauthenticated cron execution
- S7: Webhook idempotency prevents duplicate payment/subscription processing
- C11: Contract token expiration prevents indefinite public access to contract data

### Files Modified

**Backend (11 files):**
`app/api/budget.py`, `app/api/contracts.py`, `app/api/autopilot.py`, `app/api/ai.py`, `app/api/tables.py`, `app/api/guest.py`, `app/services/contract_service.py`, `app/services/contract_email_service.py`, `app/services/guest_service.py`, `app/services/stripe_service.py`, `app/dependencies/feature_gates.py`

**Frontend (5 files):**
`app/services/budgetApi.ts`, `app/admin/money/page.tsx`, `app/admin/billing/success/page.tsx`, `app/admin/planner/billing/page.tsx`, `app/admin/vendors/contracts/[id]/page.tsx`

### MEDIUM/LOW Issues (Completed 2026-03-02)

Remaining 24 MEDIUM/LOW severity issues addressed:

**AI (A6-A10):**

- A6: Added `Field` validation with `max_length` constraints to all AI request models (`ChatMessageRequest`, `DraftCommunicationRequest`, `ContractSectionRequest`, `GenerateMessageRequest`, `GenerateFormQuestionsRequest`)
- A7: Enhanced `/ai/health` endpoint — added API response time measurement and 24-hour error rate metrics from `ai_usage_log`
- A8: Added pre-flight AI credit check in `generate-contract-section` endpoint before expensive generation
- A9/A10: Already handled — `AIRateLimitError` and `AIServiceUnavailableError` provide rate limiting and fallback at the service layer

**Seating (T3, T5, T9):**

- T3: Verified `list_guests_by_wedding` already converts `_id` → `id` consistently (no change needed)
- T5: Added clarifying comments in `seating_export_service.py` confirming ObjectId → string normalization for guest-to-table lookup
- T9: Made `PrintableSeatingChart` branding dynamic — added `SeatingChartTheme` interface with configurable `accentColor`, `headerColor`, `headingFont`, `bodyFont` (defaults to gold/navy/Playfair Display)

**Stripe (S1, S4, S5, S6):**

- S1: Verified no fix needed — backend `PublicCreateCheckoutSessionRequest` ignores `user_id` and derives it from email lookup
- S4/S5: Verified no fix needed — card fields are already optional in `UserSubscription` interface with null guards in JSX
- S6: Added AI credits fetch from `/ai/credits` endpoint in billing page to populate `ai_credits_used` and `ai_credits_remaining`

**Contracts (C7, C8, C12, C14, C15, C16, C17):**

- C7: Added Stripe `PaymentMethod.retrieve` validation in sign endpoint — verifies payment method belongs to customer
- C8: Verified already handled — `_serialize_contract` converts `wedding_date` via `.isoformat()`
- C12: Improved email recipient resolution in `send_signed_confirmation` — falls back to `vendor_email` → `couple.email` → `signer_email`
- C14: Added HTML fallback in `contract_pdf_service.generate_pdf` — when WeasyPrint is unavailable, stores signed HTML document in R2 instead
- C15: Already addressed by A8 credit pre-check
- C16: Added `document_url` and `deposit_processed` to sign contract response
- C17: Added documented status constants (`CONTRACT_STATUS_DRAFT`, `EDITABLE_STATUSES`, `TERMINAL_STATUSES`, etc.) to `contract_service.py`

**Additional files modified:**
`app/services/seating_export_service.py`, `app/admin/components/seating/PrintableSeatingChart.tsx`, `app/services/contract_pdf_service.py`

### Code Review Fixes (2026-03-02)

Engineering alignment review across frontend, backend, database models, and endpoint parameters. Found and fixed 5 issues:

**Critical:**

- **C-1: Public vendor contract URLs returning 404** (`app/vendor-contract/[id]/page.tsx`, `app/services/vendorManagementApi.ts`):
  - Frontend was calling `/admin/public/contracts/{id}` — but the `vendor_management_router` is registered at prefix `/vendor-contract` (not `/admin`)
  - Fixed both the page component and `getPublicContract()`/`signPublicContract()` API helpers to use `/vendor-contract/public/contracts/{id}`
  - The separate new contract system (`app/contracts/[token]/page.tsx`) was already correctly aligned

**Medium:**

- **M-2: Budget alerts fully implemented** (`app/api/budget.py`, `app/services/budget_service.py`):
  - `GET /admin/budget/alerts/{wedding_id}` was returning a hardcoded empty array despite `_check_budget_alerts()` already creating real alerts in MongoDB
  - Added `get_budget_alerts()`, `mark_alert_as_read()`, `resolve_alert()` methods to `BudgetService`
  - Wired endpoint to service; added `PUT /admin/budget/alerts/{alert_id}/read` and `PUT /admin/budget/alerts/{alert_id}/resolve` endpoints matching `budgetApi.ts` frontend calls
- **M-1: Documented route dependency** (`app/admin/money/page.tsx`):
  - Money page calls contract/payment endpoints at root paths (`/contracts`, `/payments`) because `contracts_router` is registered without a prefix
  - Added documentation comment explaining the dependency

**Observations fixed:**

- **O-1: ContractStatus type synced** (`app/services/vendorManagementApi.ts`):
  - Added missing `'active'` status to `ContractStatus` type union and `getContractStatusColor()` map (`bg-teal-100 text-teal-800`)
- **O-2: Consistent `id`/`_id` across both contract systems** (`app/services/vendor_service.py`, `app/services/vendorManagementApi.ts`):
  - `vendor_service.py` only returned `_id` while `contract_service.py` returned both `id` and `_id` — inconsistent API shape
  - Added `_serialize_doc()` helper to `VendorService`; applied to all contract CRUD methods (create, list, get, get_by_token, create PDF)
  - Added `id?: string` to `VendorContract` and `PublicContract` TypeScript interfaces

**Files modified:**
`app/api/budget.py`, `app/services/budget_service.py`, `app/services/vendor_service.py`, `app/services/vendorManagementApi.ts`, `app/vendor-contract/[id]/page.tsx`, `app/admin/money/page.tsx`

---

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

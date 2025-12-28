# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

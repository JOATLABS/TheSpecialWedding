# Vendor Advertising Feature — Changelog

## Phase 7: Platform Hardening — Billing Cron, Webhooks, Fraud Detection, FTC Compliance, Data Retention & UX Copy
**Date:** 2026-03-22
**Version:** 6.0.0

### Overview

Platform hardening phase that wires up all remaining operational infrastructure: monthly billing cron, Stripe webhook handlers for ad invoices, real-time + batch fraud detection, FTC native advertising compliance disclosures, MongoDB TTL-based data retention, and a UX copy audit aligning all microcopy to the original mockup.

### 1. Monthly Invoice Cron

**Modified: `app/main.py`**
- Added `_monthly_billing_scheduler()` background task registered in FastAPI lifespan
- Runs on the 1st of each month at 6:00 AM UTC
- Calls `AdBillingService.finalize_monthly_invoices()` to finalize all pending Stripe invoices for the prior month
- Registered alongside existing `rollup_task` with proper shutdown cancellation

### 2. Stripe Webhook Handlers for Ad Billing

**Modified: `app/services/stripe_service.py`**
- `_handle_invoice_paid()` — now routes ad invoices (`metadata.platform == "thespecialwedding_ads"`) to `_handle_ad_invoice_paid()`: updates `vendor_ad_billing` to `payment_status: "paid"`, updates `ad_lead_charges` from `"charged"` to `"paid"`
- `_handle_invoice_payment_failed()` — routes ad invoices to `_handle_ad_invoice_payment_failed()`: updates billing to `"payment_failed"`, creates root admin notification
- New `_handle_invoice_finalized()` — updates ad billing records to `"invoiced"` status
- Added `invoice.finalized` to webhook dispatch chain

**Modified: `app/api/stripe_payment.py`**
- Added `invoice.finalized` to webhook endpoint docstring

### 3. Fraud Detection

**New file: `app/services/ad_fraud_detection_service.py`**
- `AdFraudDetectionService` class with configurable thresholds matching mockup Platform Config:
  - `MAX_CLICKS_PER_PLANNER_PER_CAMPAIGN_PER_HOUR = 5`
  - `CLICK_VELOCITY_WINDOW_MINUTES = 5` / `MAX_CLICKS_IN_VELOCITY_WINDOW = 4`
  - `DUPLICATE_CLICK_WINDOW_SECONDS = 60`
  - `HIGH_HIDE_RATE_THRESHOLD = 0.03` (3%)
  - `MAX_EVENTS_PER_SESSION_PER_HOUR = 50`
- Real-time `check_click_event()` — 3 sub-checks: click velocity, duplicate click, session anomaly
- Batch `run_batch_detection()` — 2 aggregate checks: high hide rates (7-day window), hourly click abuse (24-hour window)
- Creates `ad_fraud_signals` documents with `signal_type`, `details`, `status: "pending"`

**Modified: `app/services/planner_ad_interaction_service.py`**
- Constructor accepts `fraud_detection_service` parameter
- `add_to_directory()` and `request_quote()` call fraud detection after event recording (non-blocking, wrapped in try/except)

**Modified: `app/api/planner_ad_interactions.py`**
- DI function instantiates `AdFraudDetectionService` and passes to service

**Modified: `app/main.py`**
- Nightly rollup scheduler now runs batch fraud detection after campaign rollup and auto-complete

### 4. FTC Native Advertising Compliance

**Modified: `app/services/planner_ad_interaction_service.py`**
- New `_build_targeting_reason()` static method — builds dynamic disclosure text based on planner location + campaign category match
- `get_sponsored_cards()` now includes `targeting_reason` field on each sponsored card

**Modified: `app/services/campaignAdvertisingApi.ts`**
- Added `targeting_reason?: string` to `SponsoredCard` interface

**Modified: `app/admin/vendors/components/CampaignSponsoredCard.tsx`**
- Added FTC disclosure paragraph displaying `card.targeting_reason` below the offer tag

**Modified: `app/admin/vendors/components/CampaignSponsoredRail.tsx`**
- Updated tooltip disclosure text: "These vendors are paid sponsors. They appear here because they match your wedding location and vendor needs. Ads are labeled 'Sponsored.'"

### 5. Data Retention (TTL Indexes)

**Modified: `app/core/database_indexes.py`**
- 90-day TTL index on `ad_events.created_at` (`expireAfterSeconds = 7,776,000`)
- 7-day TTL on `ad_fraud_signals` via existing index lifecycle
- Fraud detection compound index: `(planner_id, campaign_id, event_type, created_at DESC)`
- Session anomaly index: `(session_id, created_at DESC)` (sparse)
- Total ad_events indexes increased from 2 to 5

### 6. UX Copy Audit (Mockup Alignment)

Systematic comparison of all implemented pages against `docs/plans/vendor_ads/MOCKUP/full-advertising-platform.html`. Changes made:

**`app/portal/ads/billing/page.tsx`**
- Page title: "Billing" → "Billing & Spend" (matches mockup vendor billing section header)
- Total Spend subtitle: "Lifetime total" → conditionally shows "Free tier" when `is_free_tier` is active

**`app/admin/vendors/components/CampaignSponsoredCard.tsx`**
- Added-to-directory button text: "Added" → "✓ In Directory" (matches mockup + P12 decision)
- Updated aria-label for added state to "is in your directory"

**`app/admin/vendors/components/CampaignSponsoredRail.tsx`**
- Mobile rail title: "Recommended for you" → "Sponsored Vendors" (FTC requires clear "Sponsored" labeling, matches mockup)
- Added helper text to both desktop and mobile footers: "You can hide any vendor you're not interested in" (matches mockup rail footer)

**`app/admin/vendors/components/QuoteRequestModal.tsx`**
- Modal subtitle: now includes vendor category and service area (matches mockup "Bloom & Petal Florals · Florist · Austin, TX")
- Wedding selector label: "Wedding" → "Link to a wedding? (optional)" (matches mockup)
- Wedding default option: "Select a wedding (optional)" → "General inquiry (no specific wedding)" (matches mockup)
- Send button: "Send Request" → "Send Quote Request" (matches mockup)
- Toast: generic success → "Quote request sent to [vendor name]" (matches P11 decision)

### Notes for Future Phases

- **Platform Config tab**: Mockup includes a "Platform Config" admin tab with sub-tabs for Settings, Data Export, and Data Pipeline. Not yet implemented as a UI — thresholds are currently code-level constants.
- **"Show fewer sponsored vendors" toggle**: Mockup includes a bottom-of-rail link for planners to reduce ad frequency. Not yet implemented (requires `planner_ad_preferences.reduced_frequency` field per P10 decision).
- **AI-suggested draft in quote modal**: Mockup shows an "AI-suggested draft" label with wedding-context-aware email pre-population. Current implementation has a static template — AI drafting is a future enhancement.

---

## Phase 6: CPL Billing & Stripe Integration
**Date:** 2026-03-22
**Version:** 5.0.0

### Overview

Implemented Cost Per Lead (CPL) billing for the advertising platform with full Stripe integration. Vendors are charged per lead event (quote request or directory add) via Stripe invoice items. Root admin has exclusive control to grant free tier status at both the vendor level (all campaigns free) and individual campaign level.

### Billing Model: CPL (Cost Per Lead)

Two billable lead types with configurable per-campaign pricing:
- **Quote Request** — Default $10.00/lead. Planner sends quote to vendor.
- **Directory Add** — Default $3.00/lead. Planner adds vendor to directory.

Free tier campaigns still create all billing records (charge_amount=$0, charge_status="free") so the data pipeline works identically — only actual Stripe charges are skipped.

### Root Admin Free Tier Security

Only the root admin can grant free tier status. Two levels of control:
- **Per-vendor**: `vendor_free_tier` collection. All campaigns from that vendor are free. Optional expiry date.
- **Per-campaign**: `is_free_tier` field on `ad_campaigns`. Individual campaign override.

Check priority: campaign-level `is_free_tier` → vendor-level `vendor_free_tier` → paid.

### Backend Changes

**New file: `app/services/ad_billing_service.py`**
- `AdBillingService` class with CPL charge logic
- `charge_for_lead()` — creates AdLeadCharge, updates budget_consumed, creates Stripe invoice item
- `is_campaign_free()` — checks campaign + vendor free tier status
- `_check_budget_enforcement()` — auto-pauses campaigns at budget cap
- `_create_stripe_invoice_item()` — creates Stripe invoice items for paid leads
- `_update_period_billing()` — upserts monthly vendor_ad_billing aggregates
- `set_vendor_free_tier()` / `set_campaign_free_tier()` — admin free tier toggles
- `finalize_monthly_invoices()` — monthly cron for Stripe invoice finalization

**Modified: `app/services/planner_ad_interaction_service.py`**
- Constructor now accepts `billing_service` parameter
- `add_to_directory()` — calls `billing_service.charge_for_lead(lead_type="add_to_directory")` after lead creation
- `request_quote()` — calls `billing_service.charge_for_lead(lead_type="quote_request")` after lead creation
- Both return `billing` result in response

**Modified: `app/api/planner_ad_interactions.py`**
- `get_planner_ad_interaction_service()` now instantiates AdBillingService + StripeService and passes to PlannerAdInteractionService

**Modified: `app/api/admin_campaigns.py`** — 8 new endpoints:
- `PUT /{campaign_id}/free-tier` — Toggle campaign free tier
- `PUT /vendors/{vendor_id}/free-tier` — Toggle vendor free tier
- `GET /vendors/{vendor_id}/free-tier` — Check vendor free tier status
- `GET /free-tier-vendors` — List all free tier vendors
- `PUT /{campaign_id}/cpl-pricing` — Update CPL rates per campaign
- `GET /{campaign_id}/billing` — Campaign billing summary
- `GET /{campaign_id}/lead-charges` — Individual charge history

**Modified: `app/api/vendor_campaigns.py`** — Replaced placeholder billing endpoint:
- `GET /billing` — Full billing summary with CPL data, free tier status, period history
- `GET /billing/charges` — Individual charge history for vendor

**Modified: `app/models/advertising_campaign.py`**:
- New enums: `BillingModel`, `LeadChargeType`
- AdCampaign: added `billing_model`, `is_free_tier`, `cpl_quote_request`, `cpl_directory_add`
- New models: `AdLeadCharge`, `VendorFreeTierConfig`, `SetFreeTierRequest`, `UpdateCPLPricingRequest`
- VendorAdBilling: added `quote_request_leads`, `directory_add_leads`, `is_free_tier`, `stripe_customer_id`

**Modified: `app/core/database_indexes.py`**:
- New function: `create_billing_indexes()` — 7 indexes across 3 collections
- `ad_lead_charges`: campaign+date, vendor+date, lead_id (unique), stripe_invoice_item (sparse)
- `vendor_free_tier`: vendor_id (unique), is_free+expires_at
- `vendor_ad_billing`: payment_status

### Frontend Changes

**Modified: `app/services/campaignAdvertisingApi.ts`** — 10 new functions + 6 new types:
- Types: `LeadCharge`, `BillingPeriod`, `VendorBillingSummary`, `CampaignBillingSummary`, `FreeTierStatus`
- Admin: `setCampaignFreeTier`, `setVendorFreeTier`, `getVendorFreeTierStatus`, `listFreeTierVendors`, `updateCampaignCPLPricing`, `getCampaignBilling`, `getCampaignLeadCharges`
- Vendor: `getVendorBillingSummary`, `getVendorBillingCharges`

**Modified: `app/admin/ads/page.tsx`** — Admin console billing features:
- Campaign Monitor tab: "Free"/"Make Free" toggle button per campaign row
- Vendor Accounts tab: free tier toggle per vendor
- Revenue Dashboard: "Free Tier Vendors" list section

**Modified: `app/portal/ads/billing/page.tsx`** — Full billing dashboard:
- Summary cards: Total Spend, Total Leads, Quote Requests, Directory Adds
- Free tier badge with reason
- Billing history table by period
- Recent charges list with type, amount, and status badges

### Budget Enforcement

Campaigns auto-pause when `budget_consumed >= total_budget`:
- Status set to "paused" with `metadata.paused_reason = "budget_exhausted"`
- Warning at 80% budget consumed
- `total_budget = 0` means unlimited (no cap)

### Collections Added

- `ad_lead_charges` — Individual CPL charge per lead event
- `vendor_free_tier` — Vendor-level free tier overrides

---

## Phase 5.3: Documentation & Phase 5.1: E2E Flow Verification
**Date:** 2026-03-20
**Version:** 4.1.0

### Phase 5.1: End-to-End Flow Verification

Code-level trace of all 9 user journey steps from the roadmap. Every chain from frontend → API call → backend route → service method → MongoDB collection was verified intact.

1. Vendor signup → campaign creation → creative upload → submit for review ✅
2. Admin reviews → approves campaign and creative ✅
3. Planner loads homepage → sees vendor in right rail ✅
4. Planner clicks 'Request Quote' → modal → AI-drafted email → send ✅
5. Vendor receives email + lead appears in portal ✅
6. Planner clicks 'Add to Directory' → vendor in directory ✅
7. Planner assigns vendor to wedding (existing flow) ✅
8. Admin revenue dashboard shows engagement metrics ✅
9. Nightly rollup computes campaign_day_stats + placement_day_stats ✅

Phase 5 Final Test Checkpoint — all items pass:
- All Python files compile (0 errors)
- All TypeScript compiles (0 errors in app/)
- No references to vendor_profile_id in new campaign code (only docstring clarifications)
- No dead imports of deprecated components
- Rollup service compiles and is wired to nightly cron
- click_id chain present in service, API client, and models
- No hardcoded hex colors in new frontend pages

### Phase 5.3: Documentation

Three documentation files created in `docs/plans/vendor_ads/`:

- **API_DOCUMENTATION.md** (34KB) — Complete API reference for all 3 routers (Vendor Portal, Admin Campaigns, Planner Interactions). Includes 30+ endpoints with request/response examples, authentication details, data models, status lifecycle, and error codes.
- **VENDOR_PORTAL_GUIDE.md** (6KB) — User guide for independent vendor advertisers. Covers account creation, 6-step campaign wizard, campaign lifecycle, creative management, lead viewing, billing, and tips for success.
- **ADMIN_RUNBOOK.md** (10KB) — Operational runbook for root administrators. Covers daily operations across all 5 admin console tabs, vendor management workflows, system configuration, fraud monitoring, and troubleshooting guides.

---

## Phase 5.2: Legacy System Deprecation & Full Cleanup
**Date:** 2026-03-20
**Version:** 4.0.0

### Overview

Completed the Phase 5.2 deprecation checklist from the Advertising Development Roadmap. All legacy `sponsored_vendors`-based code has been removed from the codebase. The platform now runs exclusively on the campaign-centric architecture (`ad_campaigns` + `ad_creatives` collections).

### Frontend Removals

- **Deleted `SponsoredMilestoneModule.tsx`** — Legacy milestone-based vendor suggestions removed from wedding detail page (`/admin/weddings/[id]/page.tsx`). Four `<SponsoredMilestoneModule>` instances (venue, photographer, catering, florist) removed.
- **Deleted `BoostedVendorCard.tsx`** — Legacy "boosted" vendor cards removed from vendor directory page (`/admin/vendors/page.tsx`). All related state (`boostedVendors`), fetch logic (`getSponsoredVendors`), event handlers (`handleBoostedRecordEvent`, `handleBoostedHide`), and UI (boosted count indicator, boosted grid section) removed.
- **Deleted `/admin/advertising/` directory** — Legacy 2-tab admin page (vendors + analytics) removed. Replaced by the 5-tab admin console at `/admin/ads/`.
- **Deleted `/admin/vendor/ads/` directory** — Legacy vendor portal pages (6 files) removed. Replaced by the independent vendor portal at `/portal/ads/`.
- **Updated admin sidebar** — Removed "Ads (Legacy)" link to `/admin/advertising`. Single "Ad Platform" link to `/admin/ads/` remains.
- **Updated `AdminHeader.tsx`** — Vendor advertising link changed from `/admin/vendor/ads` to `/portal/ads` (the new independent portal).
- **Removed `Target` icon import** from `Sidebar.tsx` (no longer needed).

### Backend Removals

- **Removed `advertising_router`** from `main.py` — Legacy `/admin/ads/sponsored-vendors/*` endpoints no longer registered. The new campaign routers (`admin_campaigns_router`, `vendor_campaigns_router`, `planner_ad_interactions_router`) are the sole ad platform API.
- **Deleted `app/api/advertising.py`** — Legacy router with 28+ endpoints for sponsored vendor CRUD, review workflow, rollup triggers. All functionality replaced by `admin_campaigns.py`, `vendor_campaigns.py`, and `planner_ad_interactions.py`.
- **Deleted `app/services/advertising_service.py`** — Legacy service for sponsored vendor management. Replaced by `vendor_campaign_service.py`, `admin_campaign_service.py`, and `planner_ad_interaction_service.py`.
- **Deleted `app/models/advertising.py`** — Legacy `SponsoredVendor`, `AdEvent`, `AdLead` Pydantic models. Replaced by `advertising_campaign.py` with `AdCampaign`, `AdCreative`, and updated event/lead models.
- **Deleted `app/services/ad_rollup_service.py`** — Legacy rollup that aggregated by `sponsored_vendor_id` into `ad_stats_daily`. Replaced by `campaign_rollup_service.py` which rolls up into `campaign_day_stats` and `placement_day_stats`.
- **Removed legacy rollup from nightly cron** — `main.py` startup task now only runs the campaign-centric `CampaignRollupService`, not the old `AdRollupService`.

### Files Deleted (11 total)

1. `app/admin/vendors/components/SponsoredMilestoneModule.tsx`
2. `app/admin/vendors/components/BoostedVendorCard.tsx`
3. `app/admin/advertising/page.tsx`
4. `app/admin/advertising/layout.tsx`
5. `app/admin/vendor/ads/page.tsx` + `layout.tsx` + `billing/page.tsx` + `campaigns/page.tsx` + `campaigns/new/page.tsx` + `leads/page.tsx`
6. `app/api/advertising.py`
7. `app/models/advertising.py`
8. `app/services/advertising_service.py`
9. `app/services/ad_rollup_service.py`

### Files Modified (5 total)

1. `app/admin/weddings/[id]/page.tsx` — Removed SponsoredMilestoneModule import + 4 JSX instances
2. `app/admin/vendors/page.tsx` — Removed BoostedVendorCard import, advertisingApi imports, all boosted vendor state/logic/UI
3. `app/admin/components/Sidebar.tsx` — Removed "Ads (Legacy)" nav item and Target icon import
4. `app/admin/components/AdminHeader.tsx` — Updated vendor ad link to new portal path
5. `app/main.py` — Removed advertising_router import/registration, removed legacy rollup from cron

### Deprecated Collections (data preserved, no new writes)

- `sponsored_vendors` — Legacy admin-managed vendor ads. Data retained for historical reference.
- `ad_stats_daily` — Legacy rollup by sponsored_vendor_id. Data retained; no longer computed.

### Active Campaign Platform Architecture

The platform now consists of:

- **3 API routers**: `admin_campaigns.py`, `vendor_campaigns.py`, `planner_ad_interactions.py`
- **3 services**: `admin_campaign_service.py`, `vendor_campaign_service.py`, `planner_ad_interaction_service.py`
- **1 rollup service**: `campaign_rollup_service.py` (campaign_day_stats + placement_day_stats)
- **1 model file**: `advertising_campaign.py` (AdCampaign, AdCreative, all request/response models)
- **1 frontend API client**: `campaignAdvertisingApi.ts` (36+ typed fetch functions)
- **Admin console**: `/admin/ads/` (5-tab: Creative Review, Campaign Monitor, Revenue, Vendors, Feedback)
- **Vendor portal**: `/portal/ads/` (Overview, Campaigns, Creatives, Leads, Billing + auth)
- **Planner surface**: `CampaignSponsoredRail` on 4 pages (dashboard, budget, vendors, wedding detail)

---

## Phase 4.1: Legacy Rail Removal, UX Copy Audit & P0/P1 Bug Fixes
**Date:** 2026-03-20
**Version:** 3.1.0

### Overview

Removed the legacy `SponsoredVendorsRail` from all four planner-facing pages and replaced it with the Phase 4 `CampaignSponsoredRail`. Completed a comprehensive UX copy audit of the vendor portal. Fixed critical P0 bugs (IntersectionObserver timer leak, double event recording) and P1 issues (N+All profile fetch, missing drawer logo) in the legacy rail components.

### Legacy Rail → Campaign Rail Migration

All four planner-facing pages now import `CampaignSponsoredRail` (campaign-based, fetches from `/planner/ads/sponsored-cards`) instead of the legacy `SponsoredVendorsRail` (admin-managed, fetches from `/admin/ads/sponsored-vendors`). The rail renders nothing when no approved campaigns exist, which is the correct behavior for the current state of the system.

- **`app/admin/planner/page.tsx`** — `SponsoredVendorsRail placement="dashboard_rail"` → `CampaignSponsoredRail`
- **`app/admin/budget/page.tsx`** — `SponsoredVendorsRail placement="vendor_rail"` → `CampaignSponsoredRail`
- **`app/admin/vendors/page.tsx`** — `SponsoredVendorsRail placement="vendor_rail"` → `CampaignSponsoredRail`
- **`app/admin/weddings/[id]/page.tsx`** — `SponsoredVendorsRail placement="milestone_module"` → `CampaignSponsoredRail`

No pages import `SponsoredVendorsRail` anymore. The legacy rail component files (`SponsoredVendorsRail.tsx`, `SponsoredVendorCard.tsx`, `SponsoredVendorDetailsDrawer.tsx`) remain in the codebase but are unused — candidates for cleanup.

### P0 Bug Fixes (Legacy Rail — retained for reference)

- **`dashboard_rail` placement mismatch** — `SponsoredVendorsRail` queried the backend with `placement="dashboard_rail"` but admin creates entries with `vendor_rail`, returning 0 results. Added `queryPlacement` mapping so `dashboard_rail` queries as `vendor_rail` while preserving the original placement for event recording.
- **IntersectionObserver timer leak** (`SponsoredVendorCard.tsx:74-122`) — `setTimeout` inside the observer callback returned a cleanup function from `forEach`, which the observer ignores. Replaced with a `viewableTimerRef` + `observedElementRef` pattern: timer stored in ref, cleared on both out-of-view scroll and effect cleanup. Also fixed stale `cardRef.current` in cleanup by capturing the element reference.

### P1 Bug Fixes (Legacy Rail — retained for reference)

- **Double `vendor_profile_view` event** (`SponsoredVendorDetailsDrawer.tsx:42-51`) — Drawer's `useEffect` recorded a duplicate `vendor_profile_view` on open, but the card's `handleViewDetails()` already fires this before opening the drawer. Removed the drawer's `useEffect` and added a comment explaining the single-recording design.
- **N+All vendor profile fetch** (`SponsoredVendorsRail.tsx:129`) — Rail fetched `getVendorDirectory(token, { limit: 100 })` to display 3 cards. Reduced to `Math.max(neededIds.size * 3, 20)` and filters results to only the `vendor_profile_id`s from sponsored vendors.
- **Missing vendor logo in drawer** (`SponsoredVendorDetailsDrawer.tsx:167-183`) — Drawer always showed a letter-initial placeholder. Now renders `vendorProfile.logo_url` as an `<img>` when available, falling back to the placeholder only when no logo exists.

### UX Copy Audit Fixes (Vendor Portal)

- **`app/portal/ads/campaigns/new/page.tsx`** — Replaced snake_case dropdown values with `{value, label}` objects for categories, wedding stages, and goals. Budget copy reframed from "$0" to free tier language. Schedule copy clarified approval flow. Review section shows "Free Tier" / "After approval" / "Until paused" instead of raw values.
- **`app/portal/ads/campaigns/page.tsx`** — Added `window.confirm()` dialogs for delete and pause actions. "Re-submit" → "Edit & Re-submit" for rejected campaigns. Added contextual empty state with filter awareness.
- **`app/portal/ads/page.tsx`** — CTA consistency: "Create New Campaign" → "Create Campaign".
- **`app/portal/ads/creatives/page.tsx`** — Added `<label>` for campaign selector, character counters for headline (100) and description (300), "CTA Button" → "Button Text", empty state explaining what creatives are, tooltip on "Set Primary" button.
- **`app/portal/ads/leads/page.tsx`** — Added `getTypeLabel()` function for human-readable lead types, planner emails as `mailto:` links, descriptive empty state.
- **`app/portal/ads/billing/page.tsx`** — `$0.00` → "Free", subtitle "No charges on the free tier".

### Console Error Fixes

- **`app/services/advertisingApi.ts`** — `recordAdEvent` wrapped in try-catch, silently returns on network error (endpoint may not exist yet).
- **`app/services/vendorManagementApi.ts`** — 4 functions (`getVendorDirectory`, `getContracts`, `getPaymentMilestones`, `getVendorDashboard`) wrapped fetch in try-catch with descriptive error messages.
- **`app/admin/vendors/page.tsx`** — Changed `Promise.all` → `Promise.allSettled` for 4 parallel API calls with independent fallbacks per result.

### Files Modified
- `app/admin/planner/page.tsx`
- `app/admin/budget/page.tsx`
- `app/admin/vendors/page.tsx`
- `app/admin/weddings/[id]/page.tsx`
- `app/admin/vendors/components/SponsoredVendorsRail.tsx`
- `app/admin/vendors/components/SponsoredVendorCard.tsx`
- `app/admin/vendors/components/SponsoredVendorDetailsDrawer.tsx`
- `app/services/advertisingApi.ts`
- `app/services/vendorManagementApi.ts`
- `app/portal/ads/campaigns/new/page.tsx`
- `app/portal/ads/campaigns/page.tsx`
- `app/portal/ads/page.tsx`
- `app/portal/ads/creatives/page.tsx`
- `app/portal/ads/leads/page.tsx`
- `app/portal/ads/billing/page.tsx`

---

## Phase 4: Campaign-Based Frontend — Three Portal Architecture
**Date:** 2026-03-19
**Version:** 3.0.0

### Overview

Complete frontend rebuild for the new campaign-based advertising platform. Replaces the old `vendor_profile_id`-keyed system with an `ad_campaigns`-centric architecture across three portals: Root Admin, Vendor Portal, and Planner-facing sponsored rail. All new frontend code talks to the Phase 1–3 backend endpoints (`/admin/ads/*`, `/portal/ads/*`, `/planner/ads/*`).

### New API Client

- **`app/services/campaignAdvertisingApi.ts`** — New API client with 36 fetch functions for all three portals, full TypeScript types matching Phase 1 Pydantic models, and utility functions (`formatNumber`, `formatCurrency`, `formatPercent`, status label/color helpers). Null guards added to all format functions to prevent runtime crashes on undefined data.

### Root Admin Portal (`/admin/ads`)

- **5-tab layout** (down from 6 — Platform Config moved to SaaS Management):
  - **Creative Review** — Review queue with approve/reject/request-changes actions, counts by status, creative review queue
  - **Campaign Monitor** — Campaign list with status filters, pause/deactivate actions, fraud signal monitoring
  - **Revenue Dashboard** — 8 KPI stat cards (revenue, impressions, clicks, leads, conversions, active campaigns, active vendors, avg CTR), daily trend table, free tier notice
  - **Vendor Accounts** — Vendor account list with status filters
  - **Planner Feedback** — Feedback entries from planners with type badges and timestamps
- **Defensive data handling** — All list-state setters use `Array.isArray()` guards to handle both array and paginated object (`{ items: [...] }`) API responses
- **`app/admin/ads/layout.tsx`** — Simple passthrough layout

### SaaS Management Integration

- **Platform Config moved to `/admin/saas`** — Ad platform configuration (display settings, review settings) relocated to the SaaS Management page as a new "Ad Platform" tab. This includes max sponsored per page, sponsored badge toggle, tracking toggle, require review, auto-approve returning vendors, and review SLA settings.
- **Sidebar updated** — "Ad Platform" nav item points to `/admin/ads` (operational dashboard), "Ads (Legacy)" points to old `/admin/advertising`

### Vendor Portal (`/portal/ads`)

- **`app/portal/ads/layout.tsx`** — Self-contained auth system with `VendorAuthContext`, login page, sidebar navigation (Overview, Campaigns, Creatives, Leads, Billing), mobile-responsive layout
- **`app/portal/ads/page.tsx`** — Overview dashboard with welcome hero, 5 KPI cards (active campaigns, impressions, clicks, leads, avg CTR), recent campaigns list, lead funnel visualization
- **`app/portal/ads/campaigns/page.tsx`** — Campaign list with search and status filter, action menus (submit for review, pause, delete, re-submit), review notes display for rejected campaigns
- **`app/portal/ads/campaigns/new/page.tsx`** — 6-step campaign creation wizard (Basics → Targeting → Creative → Budget → Schedule → Review) with campaign goal selector, multi-select targeting pills, creative form, budget pacing, save-as-draft and submit-for-review actions
- **`app/portal/ads/creatives/page.tsx`** — Creative management with campaign selector, create/edit form, grid view with status badges and set-primary action
- **`app/portal/ads/leads/page.tsx`** — Filterable leads table with status/type filters, planner info, messages
- **`app/portal/ads/billing/page.tsx`** — Free tier banner, 3 summary cards, billing history table

### Planner-Facing Components

- **`app/admin/vendors/components/CampaignSponsoredRail.tsx`** — New campaign-based sponsored rail fetching from `/planner/ads/sponsored-cards`, same visual pattern as old rail (vertical desktop, horizontal mobile carousel)
- **`app/admin/vendors/components/CampaignSponsoredCard.tsx`** — "Add to Directory" and "Request Quote" buttons, impression tracking, click ID generation, hide functionality
- **`app/admin/vendors/components/QuoteRequestModal.tsx`** — Modal with wedding selector, collapsible context fields, message textarea with 2000 char limit, auto-add-to-directory checkbox

### Bug Fixes (Post-Deploy)

- **`formatNumber` crash** — Added null/NaN guards to `formatNumber`, `formatCurrency`, and `formatPercent` in `campaignAdvertisingApi.ts` to prevent `TypeError: Cannot read properties of undefined` when backend returns partial data
- **`feedback.map` crash** — API returning paginated objects instead of arrays; added `Array.isArray()` guards to all 6 data-fetching points in the admin ads page

### Files Created
- `app/services/campaignAdvertisingApi.ts`
- `app/admin/ads/layout.tsx`
- `app/admin/ads/page.tsx`
- `app/portal/ads/layout.tsx`
- `app/portal/ads/page.tsx`
- `app/portal/ads/campaigns/page.tsx`
- `app/portal/ads/campaigns/new/page.tsx`
- `app/portal/ads/creatives/page.tsx`
- `app/portal/ads/leads/page.tsx`
- `app/portal/ads/billing/page.tsx`
- `app/admin/vendors/components/CampaignSponsoredRail.tsx`
- `app/admin/vendors/components/CampaignSponsoredCard.tsx`
- `app/admin/vendors/components/QuoteRequestModal.tsx`

### Files Modified
- `app/admin/components/Sidebar.tsx` — Added "Ad Platform" and "Ads (Legacy)" nav items replacing single "Advertising" item
- `app/admin/saas/page.tsx` — Added "Ad Platform" tab with platform config (moved from ads page)

---

## Senior QA: ObjectId Serialization & Attribution Tracking
**Date:** 2026-03-17
**Version:** 2.3.0

### CRITICAL: ObjectId Serialization (15+ locations)

Every service method that returns MongoDB documents now converts `_id` from ObjectId to string. Added `_serialize_doc()` helper that wraps all return points.

**insert_one returns fixed:**
- `create_sponsored_vendor()` -- `str(result.inserted_id)`
- `record_ad_event()` -- `str(result.inserted_id)`
- `create_lead()` -- `str(result.inserted_id)`
- `get_feature_flag()` default creation -- `str(result.inserted_id)`
- `get_planner_preferences()` default creation -- `str(result.inserted_id)`

**find_one_and_update returns fixed (wrapped with `_serialize_doc()`):**
- `toggle_feature_flag()`
- `update_sponsored_vendor()`
- `delete_sponsored_vendor()`
- `review_sponsored_vendor()`
- `update_lead_status()`
- `hide_vendor()`, `unhide_vendor()`, `hide_category()`, `toggle_reduced_frequency()` (all 4 preference methods)

**find/cursor returns fixed:**
- `get_sponsored_vendors()` -- both instances
- `get_sponsored_vendors_filtered()`
- `get_review_queue()`
- `get_leads()`
- `get_lead()`

### HIGH: Wedding ID Attribution Tracking

- **SponsoredVendorsRail** -- `handleRecordEvent` now passes `wedding_id: selectedWeddingId || weddings?.[0]?.id` to every `recordAdEvent` call
- **SponsoredMilestoneModule** -- Added `weddingId?: string` prop, passed to `recordAdEvent` calls
- **Wedding Detail page** -- All 4 `SponsoredMilestoneModule` instances now receive `weddingId={weddingId}` from route params

### Files Modified
- `app/services/advertising_service.py` -- `_serialize_doc()` helper, all ObjectId conversions, all return points wrapped
- `app/admin/vendors/components/SponsoredVendorsRail.tsx` -- wedding_id in handleRecordEvent
- `app/admin/vendors/components/SponsoredMilestoneModule.tsx` -- weddingId prop, passed to events
- `app/admin/weddings/[id]/page.tsx` -- weddingId prop passed to all 4 milestone modules

---

## Frontend-Backend Alignment Audit & Fixes
**Date:** 2026-03-17
**Version:** 2.2.0

### Audit Results
- **26 API endpoints audited**: All frontend fetch calls match backend routes, HTTP methods, query params, request bodies, and auth headers. Zero mismatches.
- **12 model pairs compared**: Field-by-field alignment between TypeScript interfaces and Python Pydantic models.
- **MongoDB query patterns**: Cross-referenced against model fields and index definitions.

### Fixes Applied

**CRITICAL: RecordAdEventRequest missing fields**
- Frontend `RecordAdEventRequest` was missing `wedding_id`, `planner_id`, `session_id`, `click_id` and had a nonexistent `user_id` field. All attribution tracking context was lost on the frontend side. Fixed by aligning the TS interface to match the backend Pydantic model exactly.

**HIGH: planner_id not enforced in create_lead()**
- `create_lead()` used `data.get("planner_id")` for a required field, allowing null values to be written to MongoDB. Added explicit validation that raises 400 if `planner_id` is missing.

**HIGH: Date range null comparison**
- `get_sponsored_vendors()` and `get_sponsored_vendors_filtered()` used `{"start_date": None}` to match null dates. While PyMongo handles this correctly, replaced with `{"$in": [None]}` + `{"$exists": False}` for explicit coverage of both null and missing field cases.

**MEDIUM: Timestamp fields missing from 4 models**
- `AdEvent`, `AdLead`, `PlannerAdPreference`, and `AdvertisingFeatureFlag` models were missing `created_at` and `updated_at` fields despite the service layer writing them. Added `Optional[datetime]` fields to all four models so the schema matches reality.

**MEDIUM: Missing review_status index**
- `get_review_queue()` and `get_review_queue_counts()` query on `review_status` without a supporting index. Added compound index `(review_status ASC, created_at DESC)` in `database_indexes.py`.

### Files Modified
- `app/services/advertisingApi.ts` -- RecordAdEventRequest aligned with backend (removed user_id, added wedding_id/planner_id/session_id/click_id)
- `app/services/advertising_service.py` -- planner_id validation in create_lead(), date range null comparison fix
- `app/models/advertising.py` -- Added created_at/updated_at to AdEvent, AdLead, PlannerAdPreference, AdvertisingFeatureFlag
- `app/core/database_indexes.py` -- Added idx_sponsored_review_status_created index

---

## Ad Placement Layout Fix — Consistent Right-Rail Across All Pages
**Date:** 2026-03-17
**Version:** 2.1.0

### Layout Standardization

All four planner-facing pages now use the same grid layout for the sponsored vendors rail: `grid-cols-1 lg:grid-cols-4` with main content in `lg:col-span-3` and the `SponsoredVendorsRail` in `lg:col-span-1` with `sticky top-6`. This matches the agreed design: horizontal scroll on mobile, vertical right rail on desktop (1024px+).

| Page | Before | After |
|------|--------|-------|
| Dashboard (`/admin/planner`) | Already correct | No change |
| Vendors (`/admin/vendors`) | Rail stacked inline between stats and quick actions | Moved to right sidebar column |
| Wedding Detail (`/admin/weddings/[id]`) | Already correct | No change |
| Budget (`/admin/budget`) | No ad surface at all | Added rail in right sidebar column |

### Bug Fix: SponsoredVendorDetailsDrawer

- **`useToast` import error** -- Drawer imported from `@/hooks/useToast` which doesn't exist. Replaced with `toast` from `sonner` (the project's actual toast library).

### Files Modified
- `app/admin/vendors/page.tsx` -- Wrapped content in `lg:grid-cols-4` grid, moved rail from inline to `lg:col-span-1` sidebar
- `app/admin/budget/page.tsx` -- Added `SponsoredVendorsRail` import, wrapped content in `lg:grid-cols-4` grid with rail in sidebar
- `app/admin/vendors/components/SponsoredVendorDetailsDrawer.tsx` -- Replaced `useToast` with `sonner` toast

---

## View 2 Drawer Wiring & View Status Reconciliation
**Date:** 2026-03-17
**Version:** 2.0.0

### SponsoredVendorDetailsDrawer Wired Up (View 2)

- **Drawer now opens on card click** -- When a planner clicks a sponsored vendor card in the `SponsoredVendorsRail`, the `SponsoredVendorDetailsDrawer` opens instead of navigating to a new page. Shows vendor photo/placeholder, business info, pricing, contact details, portfolio links, "Why am I seeing this?" disclosure, ratings, stats, and 4 action buttons (Add to Wedding, Request Quote, Message Vendor, View Portfolio).
- **Event tracking on open** -- Records `vendor_profile_view` event when drawer opens.
- **Request Quote from drawer** -- Opens `mailto:` with pre-filled subject line and body including wedding name.
- **Hide from drawer** -- Dismiss event recorded, vendor hidden, drawer auto-closes.

### View Status Reconciliation

Updated the gap analysis to reflect current reality. The code review report from March 16 was stale.

| View | Status | Notes |
|------|--------|-------|
| View 1: Planner Dashboard Rail | Built | Layout uses `lg:grid-cols-4` right sidebar. **Known issue:** rail not visible when feature flag is disabled |
| View 2: Vendor Details Drawer | **Now wired up** | Was built but not connected to any click handler. Now opens from SponsoredVendorsRail card clicks |
| View 3: Directory Boosts | Built | BoostedVendorCard integrated in `/admin/vendors` grid with count indicator |
| View 4: Milestone Module | Built | SponsoredMilestoneModule on `/admin/weddings/[id]` for venue, photographer, catering, florist |
| View 5: Vendor Ad Manager | Built | `/admin/vendor/ads/page.tsx` with metrics, weekly chart, funnel, campaigns table |
| View 6: Campaign Wizard | Built | 6-step wizard at `/admin/vendor/ads/campaigns/new` with image upload + review workflow |
| View 7: Admin Console | Built | 4-tab root admin page at `/admin/ads/console` |
| View 8: System Flows | Built | Rollup pipeline, event tracking, attribution, nightly scheduler |

### Known Open Items
- ~~Ad placement layout fix~~ -- **RESOLVED in v2.1.0** -- All four pages now use consistent `lg:grid-cols-4` right-rail layout
- Dashboard rail only visible on `lg` breakpoint (1024px+) and only when feature flag is enabled (by design)
- Fraud detection not built (View 8, Flow 5) -- rate limiter, session anomaly detection, auto-void clicks, quality score penalty system

### Files Modified
- `app/admin/vendors/components/SponsoredVendorsRail.tsx` -- Imported drawer, added `drawerVendor` state, wired click handler to open drawer with event tracking and action callbacks

---

## Views 3-5 QA Audit, Tech Debt Fixes & Refinements
**Date:** 2026-03-17
**Version:** 1.9.0

### Tech Debt Audit & Fixes

**Backend fixes:**
- **Feature flag config back-fill** — `get_feature_flag()` now auto-migrates existing MongoDB documents by adding missing config keys (`require_review`, `auto_approve_returning_vendors`, `review_sla_hours`). Prevents frontend crashes when the FeatureFlag document was created before the review workflow was added.
- **`_id` serialization** — `get_feature_flag()` now converts ObjectId to string before returning, preventing JSON serialization errors in endpoints that return raw documents.
- **Category filter clobber fix** — `get_sponsored_vendors_filtered()` previously overwrote `target_categories` when both `category_filter` and `hidden_categories` were set. Now uses `$and` to combine both conditions.
- **ObjectId validation** — Hidden vendor IDs in `get_sponsored_vendors_filtered()` are now validated with try/except before converting to ObjectId, preventing crashes on malformed strings.
- **Review queue enrichment logging** — Silent `except: pass` in review queue vendor profile enrichment now logs warnings.
- **Dashboard stats cursor limit** — `get_dashboard_stats()` now caps results at 5000 documents to prevent unbounded memory usage.

**Frontend fixes:**
- **`SponsoredVendor` interface** — Added `review_status`, `reviewed_by`, `reviewed_at`, `review_notes` fields. Removed unsafe `as any` casts in campaigns page.
- **`FeatureFlagConfig` interface** — Moved to top of `advertisingApi.ts` and merged with `FeatureFlag` interface, eliminating duplicate definitions.
- **Duplicate `getFeatureFlag` export** — Removed duplicate function that caused build error.

### View 3 (Directory Boosts) — Verification

- **Status: Already integrated** — `BoostedVendorCard` is rendered at the top of the vendor directory grid in `/admin/vendors/page.tsx`
- Boosted vendors fetched via `getSponsoredVendors(token, { placement: 'directory_boost' })` with category/preference filtering
- Count indicator shows "N boosted results" in search results header

### View 4 (Milestone Module) — Verification

- **Status: Already integrated** — `SponsoredMilestoneModule` is rendered on `/admin/weddings/[id]/page.tsx` for venue, photographer, catering, and florist categories
- Wedding context (city, state, guest count, budget) passed as props for contextual why-tags

### View 5 (Vendor Ad Manager) — Refinements

- **Budget column added** — Campaigns table now shows daily_budget or lifetime_budget from campaign metadata, with "Free tier" fallback
- **CPL column added** — Shows $0.00 during free tier (will compute from billing when Stripe integration is built)
- **Review-aware status badges** — Campaign status now shows pending_review (purple), rejected (red), changes_requested (amber) in addition to Active (green) and Paused (yellow)

### Previously Flagged Issues Verified as Already Fixed
- `dashboard_rail` was already in backend `AdPlacement` enum
- `hidden_vendor_ids` field names already matched on both frontend and backend
- CTR calculation was already using `impression_served` only (not double-counting)

### Files Modified
- `app/services/advertising_service.py` — Feature flag back-fill, ObjectId validation, category query fix, enrichment logging
- `app/services/ad_rollup_service.py` — Dashboard stats cursor limit
- `app/services/advertisingApi.ts` — FeatureFlagConfig dedup, SponsoredVendor review fields, duplicate function removal
- `app/admin/vendor/ads/page.tsx` — Budget column, CPL column, review-aware status badges
- `app/admin/vendor/ads/campaigns/page.tsx` — Removed unsafe `as any` cast

---

## View 7 — Admin Moderation Console & Review Workflow
**Date:** 2026-03-17
**Version:** 1.8.0

### Creative Review Workflow (Backend)

- **`AdReviewStatus` enum** — `pending_review`, `approved`, `rejected`, `changes_requested` added to `advertising.py` models.
- **`SponsoredVendor` review fields** — `review_status`, `reviewed_by`, `reviewed_at`, `review_notes` fields added to the model for full review audit trail.
- **`ReviewCampaignRequest` model** — New request model for the review endpoint with `review_status` and `review_notes`.
- **`review_sponsored_vendor()` service method** — Approves (activates), rejects (deactivates), or requests changes. Stores reviewer email and timestamp.
- **`get_review_queue()` service method** — Fetches campaigns by review status with vendor profile enrichment for review UI cards.
- **`get_review_queue_counts()` service method** — Aggregation pipeline returning counts per review status for the queue stats bar.
- **`PUT /admin/ads/sponsored-vendors/{id}/review`** — New endpoint for admin creative review. Root admin only.
- **`GET /admin/ads/review-queue`** — New endpoint returning enriched review queue with vendor profile data.
- **`GET /admin/ads/review-queue/counts`** — New endpoint returning status counts for queue stats.
- **`PUT /admin/ads/feature-flag/config`** — New endpoint to update individual config keys (allowlisted) without toggling the entire feature.
- **Review workflow config** — Added `require_review`, `auto_approve_returning_vendors`, `review_sla_hours` to `AdvertisingFeatureFlag.config` defaults.
- **Campaign Wizard submission** — Now submits with `is_active: false` and `review_status: "pending_review"` so campaigns enter the review queue.

### Frontend API Functions (advertisingApi.ts)

- `ReviewStatus` type and `ReviewQueueItem`, `ReviewQueueCounts`, `FeatureFlagConfig` interfaces
- `getReviewQueue()`, `getReviewQueueCounts()`, `reviewCampaign()` — Review queue operations
- `getFeatureFlag()`, `toggleFeatureFlag()`, `updateFeatureFlagConfig()` — Feature flag management

### View 7 Admin Console Page (`/admin/ads/console`)

- **4-tab root admin console** — Creative Review, Performance Dashboard, System Config, Revenue & Billing
- **Creative Review tab** — Queue stats bar (pending/approved/rejected/changes requested counts), review cards with vendor profile enrichment, creative preview, approve/reject/request changes actions with inline notes modal, placement and status filters
- **Performance Dashboard tab** — Top-level metrics (impressions, clicks, CTR, leads, revenue placeholder), daily impressions trend bar chart, platform health grid, vendor leaderboard table with rank/impressions/clicks/CTR/leads, configurable lookback period (7/14/30/90 days)
- **System Config tab** — Feature flag toggles (ads enabled, show badge, enable tracking), serving limits (max per page, impressions per session, min priority) with inline editing, review workflow config (require review, auto-approve returning, SLA hours), data pipeline controls (manual rollup, 90-day backfill)
- **Revenue & Billing tab** — All $0 values, no fake data. Shows what data is already captured (pricing_model, bids, budgets, events, rollups) vs. what needs to be built (Stripe integration, usage metering, budget enforcement, invoices, webhooks)
- **RootAdminGuard** — Page is protected and only accessible to root admins

### Vendor Placeholder Pages

- **`/admin/vendor/ads/campaigns`** — Campaign list page showing all vendor campaigns with status badges (pending/approved/rejected/active/inactive), impression/click counts, and "New Campaign" button
- **`/admin/vendor/ads/leads`** — Leads list page showing planner interactions from sponsored ads with status filter, lead type labels, quote amounts, and response timestamps
- **`/admin/vendor/ads/billing`** — Billing placeholder with free-tier notice, zeroed metrics (no fake data), tracked usage data list, and "coming soon" feature roadmap

### Files Created
- `app/admin/ads/console/page.tsx` — View 7 Admin Console (4-tab root admin page)
- `app/admin/vendor/ads/campaigns/page.tsx` — Campaign list placeholder
- `app/admin/vendor/ads/leads/page.tsx` — Leads list placeholder
- `app/admin/vendor/ads/billing/page.tsx` — Billing placeholder

### Files Modified
- `app/models/advertising.py` — AdReviewStatus enum, SponsoredVendor review fields, ReviewCampaignRequest model, FeatureFlag config defaults
- `app/services/advertising_service.py` — review_sponsored_vendor(), get_review_queue(), get_review_queue_counts(), create_sponsored_vendor() review fields
- `app/api/advertising.py` — Review queue endpoints, review endpoint, feature flag config endpoint
- `app/services/advertisingApi.ts` — ReviewStatus type, review/flag API functions, CreateSponsoredVendorRequest updated
- `app/admin/vendor/ads/campaigns/new/page.tsx` — Submits with is_active: false, review_status: pending_review

---

## Ad Image Upload & Separate S3 Bucket
**Date:** 2026-03-17
**Version:** 1.7.0

### Separate S3/R2 Bucket for Ad Assets

- **New `vendor-ad-assets` bucket** — Vendor ad creative images are now stored in a dedicated Cloudflare R2 bucket, fully isolated from the `wedding-gallery` bucket. Enables independent access controls, cost tracking, lifecycle rules, and future billing metering.
- **New env variables** — `S3_AD_BUCKET_NAME` and `AD_MEDIA_DOMAIN` added to `.env` and `.env.example`. Same R2 credentials (same Cloudflare account), different bucket.
- **`AdUploadService` class** — New service in `gallery_upload_service.py` alongside existing `GalleryUploadService`. Handles presigned URL generation, file deletion, and vendor file listing for the ad bucket. Only allows JPEG/PNG/WebP, max 5 MB. Key format: `ads/{vendor_id}/{timestamp}_{filename}`.

### Campaign Wizard Image Uploader (Step 5)

- **Drag-and-drop image uploader** — Replaced the plain text "Image URL" field with a proper file upload zone. Supports drag-and-drop, click-to-browse, upload progress states (spinner + status text), file type validation, size validation, and error display.
- **Image preview with remove** — After upload, shows the image preview with an X button to remove and re-upload.
- **3-step upload flow** — (1) Get presigned PUT URL from `/admin/ads/upload-url`, (2) PUT file directly to R2, (3) Persist CDN URL on vendor profile via `/admin/ads/update-logo`.
- **Auto-saves to `logo_url`** — The uploaded CDN URL is automatically saved as the vendor's `logo_url` on their VendorProfile, which is the same field the ad cards (SponsoredVendorCard, BoostedVendorCard) render.

### Backend Endpoints

- **`GET /admin/ads/upload-url`** — Returns presigned PUT URL for the ad bucket. Accepts `filename` and `content_type` query params. Restricted to vendors and root admins.
- **`POST /admin/ads/update-logo`** — Persists CDN URL on vendor_profiles.logo_url. Restricted to vendors and root admins.

### Frontend API Functions

- `getAdImageUploadUrl()` — Gets presigned URL from our API
- `uploadFileToPresignedUrl()` — PUTs file directly to R2 (no round-trip through our server)
- `updateVendorLogo()` — Saves CDN URL on vendor profile

### Config

- **`next.config.js`** — Added `AD_MEDIA_DOMAIN` to `remotePatterns` for Next.js image optimization
- **`.env.example`** — Rebuilt from scratch with all current env variables (placeholder values, no secrets)

### Files Modified
- `.env` — Added S3_AD_BUCKET_NAME, AD_MEDIA_DOMAIN
- `.env.example` — Full rebuild with all env vars
- `app/services/gallery_upload_service.py` — Added AdUploadService class
- `app/api/advertising.py` — Added upload-url and update-logo endpoints
- `app/services/advertisingApi.ts` — Added 3 upload functions
- `app/admin/vendor/ads/campaigns/new/page.tsx` — Replaced URL input with drag-and-drop uploader
- `next.config.js` — Added AD_MEDIA_DOMAIN to remotePatterns

---

## Planner Action Wiring — Add to Wedding, Request Quote (mailto), Vendor Images
**Date:** 2026-03-16
**Version:** 1.6.0

### Planner-to-Vendor Action Flow (4 gaps closed)

- **"Request Quote" opens native email client** — Both SponsoredVendorCard (rail) and BoostedVendorCard (directory) now generate a `mailto:` link with the vendor's email pre-filled in the To field, a contextual subject line ("Quote Request – {vendor} for {wedding}"), and a pre-drafted body. Creates an AdLead (lead_type: quote_request) for attribution tracking.
- **"Add to Wedding" creates VendorAssignment** — Both card types now call `assignVendorToWedding()` to create a real VendorAssignment record in the database. Button transitions to "✓ Added" (green) on success, handles duplicate-assignment gracefully, and falls back to vendor profile if no wedding context is available. Creates an AdLead (lead_type: add_to_wedding) for attribution.
- **Vendor images render from logo_url** — Both card types now check `vendorProfile.logo_url` and render the actual vendor image. Falls back to category emoji only when no image is available.
- **VendorProfile TypeScript interface updated** — Added `logo_url`, `service_radius`, `country`, `postal_code` fields to match backend model.
- **Removed fake toast callbacks** — Vendor directory page no longer passes `onAddToWedding`/`onRequestQuote` callbacks that showed misleading success toasts. Cards now handle real API calls internally.

## UX Copy Audit — Cross-Component Terminology & Microcopy Review
**Date:** 2026-03-16
**Version:** 1.5.0

### UX Copy Fixes (12 issues audited, all resolved)

- **Placement label alignment** — Campaign wizard PLACEMENT_OPTIONS now matches `getAdPlacementLabel()`: "Vendor Rail", "Vendor Detail", "Milestone Module", "Directory Boost"
- **Category value mapping** — CATEGORY_OPTIONS changed from bare strings to `{value, label}` objects mapping human labels (e.g., "Photography") to backend snake_case (e.g., "photographer")
- **Vendor-facing annotation** — View 5 data annotation rewritten from developer language ("ad_stats_daily + ad_events collections", "recharts") to vendor-friendly copy explaining how tracking works
- **Pricing label in Review step** — Shows human label ("Cost per Click (CPC)") instead of raw value ("cpc")
- **Goal descriptions de-jargoned** — Removed unexplained CPC/CPL/CPA acronyms from goal option descriptions
- **Price format consistency** — BoostedVendorCard now uses `vendorProfile.currency` instead of hardcoded `$`, matching SponsoredVendorCard
- **Why-tag tone** — Changed "You may need a {category}" to neutral "Offers {category} services" in SponsoredVendorsRail
- **Footer copy consistency** — Mobile and desktop footer both say "See more vendors ›" instead of different phrasing
- **Funnel labels clarified** — "Added" → "Added to Wedding", "Contracts" → "Bookings", rate labels more specific
- **Chart empty state** — Improved contrast (gray-400 → gray-500), more helpful copy ("Data will appear here once your campaigns start running")
- **Mobile tooltip** — Now mentions hide ability ("You can hide any vendor you're not interested in")
- **Ads layout nav** — Differentiated placeholder hrefs so sub-nav active state can work (/campaigns, /leads, /billing)

## View 5: Vendor Ad Manager + View 6: Campaign Wizard
**Date:** 2026-03-16
**Version:** 1.4.0

### View 5 — Vendor Ad Manager Dashboard (`vendor/ads/page.tsx`)

Major refactor of the vendor advertising overview page to match mockup View 5 spec:

- **5 performance metric cards** — Impressions, Clicks, Click Rate, Leads, Cost/Lead with period-over-period change indicators (↑/↓/→ Stable). Compares 30-day vs 60-day stats.
- **Performance by Week bar chart** — Recharts `BarChart` with dual bars (sage for impressions, gold for clicks). Daily series aggregated into weekly chunks via `aggregateWeekly()`.
- **Conversion Funnel visualization** — 5-step funnel (Impressions → Clicks → Leads → Added → Contracts) with decreasing width bars, conversion rate labels between steps, and wedding color palette.
- **Active Campaigns table** — 7-column table (Campaign, Status, Placement, Impressions, Clicks, Leads, CTR). Status badges (green/yellow). Lead counts computed by filtering `getAdLeads` results per vendor.
- **Parallel data fetching** — `Promise.all` for dashboard stats (30-day + 60-day), sponsored vendors, and leads.
- **Cost/Lead "Free Tier"** — Displays $0.00 with "Free Tier" label during pre-billing period.
- **Data source annotation** — Footer note documenting data source (ad_stats_daily + ad_events) and full-funnel attribution.
- **Accessibility** — 44px min-h "New Campaign" button, gray-600 annotation text (4.5:1 contrast), responsive grid (2-col mobile → 5-col desktop).

### View 6 — Campaign Creation Wizard (`vendor/ads/campaigns/new/page.tsx`)

Major refactor from 5-step to 6-step wizard matching mockup View 6 spec:

- **6-step wizard** — Goal → Targeting → Budget & Schedule → Pricing → Creative → Review
- **Step indicator** — Numbered circles with completed (sage + checkmark), active (navy), future (gray) states. Connector lines between steps.
- **Step 1: Goal** — 3 goal cards with emoji icons (👁 Profile Visits, 💌 Quote Requests, 📅 Bookings)
- **Step 2: Targeting** — 4 placement cards in 2-col grid (now includes `directory_boost`), location targeting (region + city), category chips as toggleable buttons
- **Step 3: Budget & Schedule** — Budget type toggle cards (Daily/Lifetime), large-font budget input ($20px), estimated impressions/clicks/total spend calculations, date range with duration calculator, pacing strategy cards (Standard/Accelerated), budget recommendation box
- **Step 4: Pricing (NEW)** — CPC/CPL/Fixed pricing model selection. Conditional bid inputs per model. Fixed slot shows premium badge.
- **Step 5: Creative** — Image URL, headline (60 char), description (150 char), special offer, CTA select. Live preview with "✦ Sponsored" badge matching production card style.
- **Step 6: Review** — Summary with pill-style tags for placements/categories, budget/pricing/pacing grid, creative preview.
- **Navigation** — "← Back" / "Continue to {NextStep} →" / "Submit for Review" with 44px min-h buttons
- **Metadata capture** — Comprehensive metadata including goal, budget_type, daily_budget, pacing, pricing_model, cpc_bid, cpl_bid, region, city
- **Accessibility** — `aria-label` and `aria-pressed` on all toggle buttons (goal, placement, category, budget type, pacing), `aria-current="step"` on active step, date range validation (endDate >= startDate)

### QA Verification
- View 5: 67/72 checks passed. 1 fix applied (annotation contrast gray-400→gray-600)
- View 6: 26.5/27 checks passed. Fixes applied (aria-labels on all interactive buttons, date validation)

### Files Modified
- `app/admin/vendor/ads/page.tsx` — Full rewrite (5 perf cards, recharts bar chart, funnel, campaigns table)
- `app/admin/vendor/ads/campaigns/new/page.tsx` — Full rewrite (6-step wizard with pricing step)

---

## View 3: Directory Boosts + View 4: Milestone Module
**Date:** 2026-03-16
**Version:** 1.3.0

### View 3 — Directory Boost Cards (`BoostedVendorCard.tsx`)

New `BoostedVendorCard` component for the `directory_boost` placement, matching mockup View 3 spec:

- **120px image header** with category emoji placeholder and "⚡ Boosted" gold gradient badge (`bg-gradient-to-r from-wedding-gold to-amber-600`) positioned absolute top-left
- **Dual badge system** — "⚡ Boosted" on image header + "✦ Sponsored" text badge on card body
- **Full card layout** — Vendor name (14px bold), category (11px sage), location with pin emoji, star rating (filled/empty Lucide Stars), price range ($X,XXX – $X,XXX format)
- **Dual CTA row** — "+ Add to Wedding" (sage bg) + "Request Quote" (outlined) with 44px min-h touch targets
- **Complete event tracking** — `impression_served` (on mount), `impression_viewable` (IntersectionObserver, 50% visible for 1s), `vendor_profile_view`, `vendor_added_to_wedding`, `contact_click`, `dismiss`
- **Click attribution** — UUID `click_id` generated per card, consistent across all events
- **Hide on hover** — X button appears on group-hover, records dismiss event, removes card from DOM
- **Accessibility** — `<article>` with `role="article"`, `<a>` link with focus ring, `aria-label` on all interactive elements, `focus-within:ring-2` on card, `w-11 h-11` (44px) hide button, focus rings on CTA buttons

**Integration into vendor directory page (`vendors/page.tsx`):**
- Fetches max 2 boosted vendors via `getSponsoredVendors(token, { placement: 'directory_boost', limit: 2 })`
- Client-side filtering by `hidden_vendor_ids` and `hidden_categories` from planner preferences
- Boosted cards render at top of vendor grid before organic cards
- Count indicator: "Showing X results · 2 boosted results"
- Empty state checks both `vendors.length === 0 AND boostedVendors.length === 0`

### View 4 — Sponsored Milestone Module (`SponsoredMilestoneModule.tsx`)

New `SponsoredMilestoneModule` component for the `milestone_module` placement, matching mockup View 4 spec:

- **"✦ Sponsored {Category} Options" header** with "Hide this section" link
- **2-column card grid** (`grid-cols-1 sm:grid-cols-2`) rendering max 2 `SponsoredVendorCard` components
- **Contextual why-tags** generated from `weddingContext` prop:
  - Distance: "📍 {radius}mi from {city}" or "📍 Near {city}"
  - Guest capacity: "👥 Fits {count}+ guests"
  - Budget match: "Budget range match" (when `price_min <= budget && price_max >= budget * 0.5`)
- **Auto-suppression** — Module returns null when `isBooked=true`, section hidden, loading, or no vendors
- **Footer** — "Why am I seeing this?" toggle + "See more {category} ›" link
- **Why tooltip** — Contextual explanation of matching criteria with `role="tooltip"` and `aria-expanded`
- **Section** — `role="region"` with `aria-label`, subtle gradient background

**Integration into wedding detail page (`weddings/[id]/page.tsx`):**
- 4 milestone modules rendered in main content column (`lg:col-span-3`):
  - `venue` (isBooked checks `venue_name` on events)
  - `photographer`
  - `catering`
  - `florist`
- Each module receives `weddingContext` with city, state, guestCount, and category-specific budget
- Wrapped in `space-y-4` with `mt-8` top margin
- Conditionally rendered only when `wedding` object exists

### QA Verification
- View 3: 25/29 checks passed, 3 medium issues fixed (hide button 32px→44px, focus rings on link and buttons)
- View 4: 29/29 checks passed, 0 issues

### Files Created
- `app/admin/vendors/components/BoostedVendorCard.tsx`
- `app/admin/vendors/components/SponsoredMilestoneModule.tsx`

### Files Modified
- `app/admin/vendors/page.tsx` — Boosted vendor integration (fetch, filter, render, event handlers)
- `app/admin/weddings/[id]/page.tsx` — Milestone module integration (4 categories with context)

---

## Responsive Rail Refactor, Accessibility & Multi-Agent QA Pass
**Date:** 2026-03-16
**Version:** 1.2.0

### Responsive Layout Refactor

Implemented dual-layout responsive design for the sponsored vendors rail, aligning with the Vendor_Ad_Mockups.html source of truth:

**Desktop (lg: 1024px+):** Vertical stacked rail (right sidebar, max 3 cards) matching mockup View 1 spec — 320px width column inside `lg:grid-cols-4` planner dashboard grid. Includes "Sponsored Vendors" header, "⚙ Preferences" button, wedding context badge, "Why am I seeing this?" expandable tooltip, and "See more vendors ›" footer link.

**Mobile (<1024px):** Horizontal snap-scroll carousel with left/right navigation arrows. Includes "Recommended for you" header with Sparkles icon, HelpCircle tooltip, "See all sponsored vendors →" centered footer link.

### Accessibility Fixes (WCAG 2.1 AA Compliance)

1. **Keyboard accessibility** — Card changed from `<div onClick>` to semantic `<article>` with `<a>` link for the main clickable area. CTA buttons placed outside the link to avoid nested interactive elements. Cards are now fully navigable via Tab/Enter/Space.

2. **Touch target sizes** — All interactive elements meet WCAG 44px minimum:
   - Hide button: `w-11 h-11` (44px)
   - Scroll arrows: `w-11 h-11` (44px)
   - Mobile info button: `w-11 h-11` (44px)
   - CTA buttons: `min-h-[44px]`

3. **Contrast ratios** — All gray text upgraded from `gray-300`/`gray-400`/`gray-500` to `gray-600` (5.7:1 ratio on white, exceeding AA 4.5:1 requirement). Applies to meta text, preferences, footer links, and tooltip content.

4. **ARIA carousel** — Mobile carousel has `role="region"`, `aria-roledescription="carousel"`, `aria-label`. Scroll container has `role="list"` with `role="listitem"` on each card. Desktop layout also has `role="region"` with `aria-label`.

5. **Tooltip ARIA** — Both mobile and desktop tooltips have `role="tooltip"` with matching `id`/`aria-controls`. Trigger buttons have `aria-expanded` state.

6. **Live region for dismissals** — `<div aria-live="polite" aria-atomic="true">` announces vendor name when card is hidden, providing screen reader feedback.

7. **Semantic HTML** — Cards use `<article>` with `role="article"` and descriptive `aria-label`. Image placeholders have `aria-hidden="true"`. Card has `focus-within:ring-2` for keyboard focus visibility.

8. **Preferences control** — Changed from non-focusable `<span>` to `<button>` element.

### Why-Tag Passthrough Fix

The `whyTag` prop existed on `SponsoredVendorCard` but was never passed from `SponsoredVendorsRail`. Added `getWhyTag()` function (memoized via `useCallback`) that generates context-aware why-tags from vendor profile data (e.g., "Serves Austin · You may need a photographer"). Both desktop and mobile renders now pass `whyTag={getWhyTag(vendor)}`. Also fixed why-tag padding from `py-1` to `py-1.5` per mockup spec.

### Frontend Type Alignment

1. **Legacy event types removed** — `AdEventType` cleaned from 15 values to 12, removing `impression`, `viewable_impression`, `detail_view`, `assignment` that existed in the frontend but not the backend enum. `getEventTypeLabel` updated to match.

2. **`wedding_overrides` added** — `AdPreferences` interface now includes `wedding_overrides: Record<string, { hidden_vendor_ids?: string[]; hidden_categories?: string[] }>` matching the backend `PlannerAdPreference` model.

### Backend Feature Flag Guard

Added feature flag check to `record_ad_event` endpoint — now calls `service.get_feature_flag()` before recording events and returns `{"status": "skipped", "reason": "advertising_disabled"}` when the advertising feature is toggled off. Prevents phantom event accumulation when ads are disabled.

### Files Changed
- `app/admin/vendors/components/SponsoredVendorCard.tsx` — Semantic article, keyboard-accessible `<a>`, 44px touch targets, contrast fixes, focus ring, ARIA labels, why-tag py-1.5
- `app/admin/vendors/components/SponsoredVendorsRail.tsx` — Dual responsive layout, whyTag passthrough, ARIA carousel, live region, tooltip ARIA, 44px targets, contrast fixes, dismissAnnouncement state, getWhyTag useCallback
- `app/services/advertisingApi.ts` — AdEventType cleaned (15→12), wedding_overrides added to AdPreferences, getEventTypeLabel aligned
- `app/api/advertising.py` — Feature flag guard on record_ad_event

### QA Verification
- Multi-agent review (Senior QA + Senior UX + Accessibility) — 42/42 checks passed
- Responsive breakpoints consistent (all `lg:` at 1024px)
- Desktop limited to 3 cards as specified in mockup
- Event tracking intact through refactor
- 95% pixel fidelity to mockup

---

## Code Review Bugfix Pass
**Date:** 2026-03-16
**Version:** 1.1.0

### Critical Fixes

1. **`$or` query construction bug** (`advertising_service.py`) — Date range filtering in `get_sponsored_vendors()` and `get_sponsored_vendors_filtered()` was malformed. The `$or` appended end_date conditions to the start_date `$or`, creating an overly permissive query that could serve expired vendors. **Fixed:** Replaced with proper `$and` + nested `$or` structure for both start_date and end_date filtering.

2. **Field name mismatch** (`advertisingApi.ts`) — `AdPreferences.hidden_vendors` didn't match the backend model's `hidden_vendor_ids`. The `SponsoredVendorsRail.tsx` component was already using the correct `hidden_vendor_ids` field, so this was a type interface error. **Fixed:** Renamed to `hidden_vendor_ids`.

3. **CTR double-counting** (`ad_rollup_service.py`, `advertising.py`) — `total_impressions` summed `impression_served + impression_viewable`, but viewable is a subset of served (not additive). This deflated CTR across the daily rollup, dashboard stats, and vendor leaderboard. **Fixed:** All three locations now use only `impression_served` as denominator.

4. **Missing `dashboard_rail` placement** (`advertising.py`) — Frontend defined `AdPlacement` with 5 values including `dashboard_rail`, but the backend `AdPlacement` enum only had 4. Events with `placement: dashboard_rail` would fail Pydantic validation. **Fixed:** Added `DASHBOARD_RAIL = "dashboard_rail"` to backend enum.

5. **Lead endpoint vendor-role scoping** (`advertising.py`) — Lead endpoints used `require_admin_or_planner` which blocked vendor users entirely. Updated to `get_current_user_extended` with inline role checks: admins see all leads, vendors see leads for their vendor profiles (via email lookup on `vendor_profiles` collection with ObjectId conversion), planners see only their own leads.

### Files Changed
- `app/services/advertising_service.py` — 2 query fixes (lines 204–224, 848–868)
- `app/services/advertisingApi.ts` — 1 field rename (line 171)
- `app/services/ad_rollup_service.py` — 2 CTR fixes (line 229, line 519)
- `app/models/advertising.py` — 1 enum addition (line 53)
- `app/api/advertising.py` — Import added (bson.ObjectId, get_current_user_extended), dashboard stats CTR fix (line 808), 3 lead endpoints updated with vendor-role scoping

---

## Stage 1–3 Expansion: Full Advertising Platform Build-out
**Date:** 2026-03-15
**Version:** 1.0.0

### Overview
Major expansion of the advertising feature from basic sponsored rail to a full-platform advertising system with lead tracking, planner preferences, vendor self-serve dashboard, campaign wizard, and detailed analytics. Includes comprehensive QA review and bugfix pass across all layers.

### New Data Models (`app/models/advertising.py`)

**AdEventType expanded** — 7 → 12 event types:
| Event | Description | Stage |
|-------|-------------|-------|
| `impression_served` | Ad rendered in DOM | 1 |
| `impression_viewable` | 50%+ visible for 1+ sec (IntersectionObserver) | 1 |
| `click` | Card or CTA clicked | 1 |
| `vendor_profile_view` | Details drawer opened | 1 |
| `vendor_added_to_wedding` | "Add to wedding" CTA used | 2 |
| `lead_created` | Quote request, message, or invite sent | 2 |
| `vendor_invited` | Vendor invited via ad | 2 |
| `lead_accepted` | Vendor accepted lead | 2 |
| `vendor_responded` | Vendor responded to lead | 2 |
| `dismiss` | Planner dismissed/hid ad | 1 |
| `hover` | Card hovered 500ms+ | 1 |
| `contact_click` | Contact button clicked | 1 |

**New: AdLead model** — Tracks planner→vendor interactions from sponsored ads:
- `sponsored_vendor_id`, `vendor_profile_id`, `planner_id` (email)
- `lead_type`: `quote_request` | `message` | `add_to_wedding` | `vendor_invite`
- `status`: `pending` | `contacted` | `responded` | `converted` | `closed`
- `click_id` (UUID) for full click→lead→conversion attribution
- `placement`, `message`, `quote_amount`, `responded_at`, `converted_at`

**New: PlannerAdPreference model** — Per-planner ad controls:
- `hidden_vendor_ids[]`, `hidden_categories[]`
- `reduced_frequency` (boolean — shows ~50% fewer ads)
- `wedding_overrides` (per-wedding preference dict)

### New Backend Endpoints (`app/api/advertising.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /admin/ads/leads | Admin/Planner | Create a lead from ad interaction |
| GET | /admin/ads/leads | Admin/Planner | List leads (filtered by vendor_id, planner_id, status, lead_type) |
| GET | /admin/ads/leads/{id} | Admin/Planner | Get single lead detail |
| PUT | /admin/ads/leads/{id}/status | Admin/Planner | Update lead status (with responded_at, converted_at timestamps) |
| GET | /admin/ads/preferences | Planner | Get planner's ad preferences |
| PUT | /admin/ads/preferences/hide-vendor?vendor_id= | Planner | Hide a vendor from ads |
| DELETE | /admin/ads/preferences/unhide-vendor/{vendor_id} | Planner | Unhide a previously hidden vendor |
| PUT | /admin/ads/preferences/hide-category?category= | Planner | Hide an entire vendor category |
| PUT | /admin/ads/preferences/reduce-frequency?reduce= | Planner | Toggle reduced ad frequency |

### New Frontend Pages

**Vendor Ads Dashboard** (`app/admin/vendor/ads/page.tsx` — 573 lines):
- 4-tab self-serve dashboard: Overview, Campaigns, Leads, Billing
- Key metrics cards: impressions, clicks, CTR, active campaigns, total leads
- Campaign table with status, budget, performance metrics
- Lead table with planner info, type, status, response time
- Billing section with spend tracking (mock data, awaiting Stripe integration)

**Campaign Creation Wizard** (`app/admin/vendor/ads/campaigns/new/page.tsx` — 727 lines):
- 5-step wizard flow:
  1. **Goal** — visits, quote requests, or bookings
  2. **Placement & Targeting** — multi-select placements, location targeting, category targeting
  3. **Budget** — daily budget ($5 min), optional lifetime budget, date range, pacing strategy
  4. **Creative** — image URL, headline (60 chars), description (150 chars), special offer, CTA text, live preview
  5. **Review & Submit** — full campaign summary before creation

**Public Vendor Profile** (`app/vendors/[id]/page.tsx` — 467 lines):
- No-auth public page at `/vendors/{id}`
- Backend: `GET /api/v1/vendors/{vendor_id}/public` (excludes internal_notes, tax_id, total_revenue)
- Hero section, contact card, portfolio gallery, service areas

### Enhanced Frontend Components

**SponsoredVendorCard.tsx** — Major upgrade:
- IntersectionObserver for viewable impression tracking (50% visible, 1+ second)
- Per-card `click_id` UUID generation for full attribution chain
- "Hide this vendor" dismiss button (X icon)
- Fixed event types: `impression_viewable`, `vendor_profile_view`, `vendor_added_to_wedding`

**SponsoredVendorsRail.tsx** — Major upgrade:
- Wedding context selector dropdown for multi-wedding planners
- "Why am I seeing this?" tooltip (HelpCircle icon)
- "See all sponsored vendors" footer link
- Preference-based filtering (fetches planner preferences, filters hidden vendors/categories)
- `handleVendorHide` wired to `hideAdVendor` backend API
- Fixed: `useEffect` moved before conditional returns (React rules-of-hooks compliance)

**SponsoredVendorDetailsDrawer.tsx** — Major upgrade:
- "Add to wedding" primary CTA (Heart icon, rose styling)
- "Request quote" secondary CTA (FileText icon)
- "Message vendor" secondary CTA (MessageSquare icon)
- "View portfolio" conditional link
- Fixed event types and added missing FileText import

**SponsoredVendorsRail placements:**
- `app/admin/planner/page.tsx` — Dashboard rail sidebar (`placement="dashboard_rail"`)
- `app/admin/weddings/[id]/page.tsx` — Wedding detail sidebar (`placement="milestone_module"`)
- `app/admin/components/AdminHeader.tsx` — "Advertising" nav link for vendor role

### Frontend-Backend Alignment Fixes

**advertisingApi.ts** — 10 fixes:
1. `toggleFeatureFlag`: JSON body → query param `?is_enabled=`
2. FeatureFlag config fields: `enable_click_tracking` → `enable_tracking`, etc.
3. AdStats: `recent_events` → `recent_events_count`
4. `hideAdVendor`: POST body → PUT query param
5. `unhideAdVendor`: POST body → DELETE path param
6. `hideAdCategory`: POST body → PUT query param
7. `toggleReducedFrequency`: fixed URL path and param name
8. `updateAdLeadStatus`: URL `/leads/{id}` → `/leads/{id}/status`
9. `getAdLeads`: `offset` param → `skip` (matching backend)
10. `CreateAdLeadRequest`: added required `lead_type` field

**LeadStatus enum aligned**: `new/contacted/engaged/accepted/rejected/archived` → `pending/contacted/responded/converted/closed`

### Backward Compatibility

**Legacy event type mapping** (`advertising_service.py`):
```python
LEGACY_EVENT_TYPE_MAP = {
    "impression": "impression_served",
    "viewable_impression": "impression_viewable",
    "detail_view": "vendor_profile_view",
    "assignment": "vendor_added_to_wedding",
}
```
Old event names are silently mapped to new names in `record_ad_event()`.

### Critical Bugfixes (Non-Advertising)

- **AdminContext.tsx crash** — Provider referenced non-existent `auth.X` objects; fixed to direct variables
- **403 logout too aggressive** — Only logout on 401 (expired token), not 403 (permission denied)
- **AI credit check key mismatch** — `has_credits` → `allowed`
- **InsufficientCreditsError missing `message` param** — Added required constructor arg
- **Vendor recommendation cache pollution** — Unique tenant_id for no-wedding context
- **Undefined `model` in AI error handler** — `locals().get("model", "unknown")`
- **AIInvalidResponseError takes no args** — Fixed to `raise AIInvalidResponseError()`

### New MongoDB Collections

| Collection | Description |
|------------|-------------|
| `ad_leads` | Planner→vendor interactions with click_id attribution, status workflow |
| `planner_ad_preferences` | Per-planner hidden vendors/categories, frequency settings |

### QA Verification Results

**Python** — All 7 modified files pass `py_compile`:
`advertising.py`, `advertising_service.py`, `models/advertising.py`, `ai.py`, `ai_service.py`, `vendor_public.py`, `main.py`

**TypeScript** — 0 compilation errors (excluding pre-existing docs/ file)

**Event type alignment** — All 6 frontend event types match backend AdEventType enum values exactly

**API endpoint alignment** — All 13 advertising endpoints verified: HTTP methods, URL paths, query/path params, and request body shapes match between frontend and backend

---

## Phase 1: Foundation (Data Models, Feature Flag, Backend API)
**Date:** 2026-03-11
**Files Added:**
- `app/models/advertising.py` — Pydantic v2 models for sponsored vendors, ad events, feature flags
- `app/services/advertising_service.py` — Async service layer with MongoDB operations
- `app/api/advertising.py` — FastAPI router with 8 endpoints

**What Changed:**
- Added AdCampaignStatus, AdEventType, AdPlacement enums
- Added SponsoredVendor model with priority-based manual placement
- Added AdEvent model for impression/click tracking
- Added AdvertisingFeatureFlag model with configurable defaults
- Created CRUD endpoints for sponsored vendors
- Created feature flag toggle endpoint
- Created ad event recording endpoint
- Created stats endpoint with CTR calculation

**New MongoDB Collections:**
- `sponsored_vendors` — Sponsored vendor entries with placement, priority, and metadata
- `ad_events` — Event log capturing impressions, clicks, dismisses, hovers, detail views, contact clicks, and assignments
- `ad_feature_flags` — Feature toggle state with configuration (max_sponsored_per_page, show_sponsored_badge, tracking settings, etc.)

**API Endpoints Added:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /admin/ads/feature-flag | Admin/Planner | Get feature flag status and configuration |
| PUT | /admin/ads/feature-flag | Admin | Toggle feature flag on/off |
| GET | /admin/ads/sponsored-vendors | Any | List all sponsored vendors, filterable by placement, category, wedding_stage |
| POST | /admin/ads/sponsored-vendors | Admin | Create new sponsored vendor entry |
| PUT | /admin/ads/sponsored-vendors/{id} | Admin | Update sponsored vendor (priority, status, placement, etc.) |
| DELETE | /admin/ads/sponsored-vendors/{id} | Admin | Soft delete sponsored vendor (marks as inactive) |
| POST | /admin/ads/events | Any | Record ad event (impression, click, dismiss, etc.) |
| GET | /admin/ads/sponsored-vendors/{id}/stats | Admin | Get performance stats for a vendor (impressions, clicks, CTR) with optional date range |

**Key Implementation Details:**
- Priority field uses integer sorting (lower number = higher priority)
- AdEvent timestamps are stored as UTC ISO strings
- CTR (Click-Through Rate) calculated as clicks / impressions
- Feature flag has per-placement limits and tracking toggles
- SponsoredVendor soft-deletes preserve historical data for analytics
- Stats endpoint supports optional `days` query param (default: last 30 days)

---

## Phase 2: Frontend Display (Sponsored Rail Components)
**Date:** 2026-03-11
**Files Added:**
- `app/services/advertisingApi.ts` — TypeScript API client with full type safety
- `app/admin/vendors/components/SponsoredVendorCard.tsx` — Reusable sponsored vendor card component
- `app/admin/vendors/components/SponsoredVendorsRail.tsx` — Horizontal scrolling rail with lazy loading
- `app/admin/vendors/components/SponsoredVendorDetailsDrawer.tsx` — Slide-out detail view with full vendor info

**What Changed:**
- Created TypeScript types matching backend models (SponsoredVendor, FeatureFlag, AdStats, AdPlacement, AdEventType)
- Created comprehensive API client functions for all 8 endpoints with proper error handling
- Built SponsoredVendorCard with:
  - Platform color palette (navy #1D3557, sage #457B9D, rose #D4A5A5, gold #E9C46A)
  - Automatic impression tracking on mount
  - Click tracking on vendor card interaction
  - Hover state animations
  - Sponsored badge display when enabled
  - Responsive image handling
- Built SponsoredVendorsRail with:
  - Horizontal scroll with keyboard navigation
  - Loading skeleton states while fetching data
  - Graceful empty state
  - Feature flag integration (doesn't render if disabled)
  - Error boundary with toast notifications
  - Smooth transitions and animations
- Built SponsoredVendorDetailsDrawer with:
  - Slide-out animation from right
  - Full vendor profile display
  - Performance metrics (impressions, clicks, CTR)
  - Action buttons (contact, view profile, etc.)
  - Event tracking for detail views and contact clicks
  - Close on backdrop click
- All components integrate with Tailwind CSS and sonner toasts
- Components gracefully degrade — no error shown if feature disabled or API fails
- Each impression and click event includes metadata (user_id, placement, timestamp)

**Event Tracking Implemented:**
- `impression` — Fired when SponsoredVendorCard mounts and is visible in viewport
- `click` — Fired when user interacts with card or calls-to-action
- `detail_view` — Fired when user opens SponsoredVendorDetailsDrawer
- `contact_click` — Fired when user clicks contact/message buttons
- All events include `placement` (vendor_rail, vendor_detail, etc.) and optional `metadata` for extensibility

---

## Phase 3: Event Tracking & Admin Controls
**Date:** 2026-03-11
**Files Added:**
- `app/admin/advertising/page.tsx` — Comprehensive admin advertising management console
- `app/admin/advertising/layout.tsx` — Layout wrapper for advertising admin section

**What Changed:**
- Created three-tab admin interface:

  **Tab 1: Feature Settings**
  - Large, prominent toggle switch for enabling/disabling sponsored vendors feature
  - Real-time status display (Active/Inactive) with color-coded badges
  - Configuration display showing:
    - Max sponsored vendors per page
    - Sponsored badge visibility setting
    - Click tracking enabled/disabled
    - Impression tracking enabled/disabled
    - Minimum impression threshold
  - Metadata display: "Last toggled by" user and "Last toggled at" timestamp
  - All settings read from FeatureFlag model, no inline editing needed at this phase

  **Tab 2: Sponsored Vendors**
  - Table view of all active sponsored vendors
  - Columns: Vendor Name, Placement, Priority, Status (active badge), Impressions, Clicks, CTR, Actions
  - "Add Sponsored Vendor" button opens form with fields:
    - Vendor selection dropdown (populated from vendor directory)
    - Placement selector (vendor_rail, vendor_detail, milestone_module, directory_boost)
    - Priority input (numeric)
    - Headline text field (optional)
    - Description text field (optional)
  - Inline priority editing with input field
  - Toggle active/inactive status with eye/eye-off icon buttons
  - Delete button with confirmation dialog
  - Empty state when no vendors (icon + helpful message)
  - Disable states for loading actions
  - Real-time stats fetching for impressions/clicks/CTR calculation

  **Tab 3: Analytics**
  - Date range filter buttons: 7d, 30d, 90d (changes all metrics)
  - Summary cards at top (grid layout):
    - Total Impressions (Users icon, blue gradient)
    - Total Clicks (Mouse icon, green gradient)
    - Average CTR (Activity icon, purple gradient)
    - Active Campaigns (Trending Up icon, orange gradient)
  - Vendor performance table sorted by impressions descending:
    - Columns: Vendor, Impressions, Clicks, CTR %, Status
    - Same vendor data as Vendors tab but read-only and sorted by performance
  - Empty state when no vendors
  - Metrics auto-update when date range changes

**Component Features:**
- Consistent styling with existing admin pages (Tailwind CSS, platform colors)
- Dark mode support throughout
- Loading spinner on initial page load
- Tab navigation with rose underline indicator
- Success/error toast notifications for all actions
- Responsive grid layouts (1 col mobile, 2+ cols tablet/desktop)
- Gradient backgrounds for metric cards
- Icon buttons with hover states
- Form validation (vendor required for add)
- Confirmation dialogs for destructive actions (delete)

**Data Flow:**
1. Page loads → fetch feature flag, all sponsored vendors, all vendors directory
2. Fetch stats for each sponsored vendor (parallel requests)
3. User actions (add/update/delete) trigger API calls and update local state
4. Stats refresh when date range changes in analytics tab
5. All errors caught and displayed as toast notifications
6. Loading states disable form fields and buttons during operations

**API Integration:**
- Uses all 8 endpoints from Phase 1 backend
- Feature flag toggle (`PUT /admin/ads/feature-flag`)
- Sponsored vendor CRUD (`GET/POST/PUT/DELETE /admin/ads/sponsored-vendors`)
- Stats fetching (`GET /admin/ads/sponsored-vendors/{id}/stats?days=X`)
- Proper Authorization header with Bearer token
- Error handling with detailed messages

**Styling & Design:**
- Uses platform color palette: navy #1D3557, sage #457B9D, rose #D4A5A5, gold #E9C46A
- Rose color for primary actions (toggle, add, edit buttons)
- Gradient backgrounds for metric cards
- Status badges (green for active, gray for inactive)
- Badge colors: green for success, red for delete, purple/blue/orange for metrics
- Responsive breakpoints: md (768px), lg (1024px)
- Dark mode support with dark: prefixes throughout
- Border and shadow styling consistent with wedding app design system

---

## Wiring & Integration (Post-Phase 3)
**Date:** 2026-03-11
**Files Modified:**
- `app/main.py` — Registered advertising router import and `include_router()` call
- `app/admin/components/Sidebar.tsx` — Added "Advertising" nav item with Megaphone icon to admin nav
- `app/admin/vendors/page.tsx` — Imported and embedded `SponsoredVendorsRail` in overview tab
- `app/api/advertising.py` — Fixed `is_admin` → `is_root_admin` (5 occurrences) to match auth dependency
- `app/services/advertisingApi.ts` — Fixed API URL prefix from `/admin/ads/` → `/api/v1/ads/` to match backend router; fixed `toggleFeatureFlag` to use query param instead of JSON body

**What Changed:**
- Advertising router now registered in FastAPI app (no `/admin` prefix since router has own `/api/v1/ads`)
- Admin sidebar shows "Advertising" link for root admins between Billing and Notifications
- Vendor management overview tab now renders SponsoredVendorsRail (gracefully hidden if feature disabled)
- All admin-only endpoint checks use `is_root_admin` matching `ExtendedAuthUser` class
- Frontend API client URLs match backend FastAPI router prefix exactly

---

## Integration Points with Existing Features

**Vendor Management:**
- Pulls vendor list from `getVendorDirectory()` for dropdown population
- Displays vendor names alongside IDs in tables
- Links to vendor profiles (extensible for future Phase 4)

**Feature Flag System:**
- Uses platform's admin authentication via AdminContext
- Respects token-based authorization
- Feature flag gates display of sponsored vendors across all frontend components

**Admin Dashboard:**
- Admin page follows same tab pattern as vendor management page
- Uses PageHeader component for consistent navigation
- Integrates with existing admin layout and sidebar navigation
- Toast notifications via sonner package
- Icons via lucide-react

---

## Technical Specifications

**Frontend Stack:**
- Next.js 16 with App Router
- React 19
- TypeScript for full type safety
- Tailwind CSS for styling
- sonner for toast notifications
- lucide-react for icon library

**Backend Stack:**
- FastAPI with Python 3.11+
- Pydantic v2 for validation
- MongoDB with async pymongo
- UTC timestamps for all events

**Error Handling:**
- Toast notifications for all user-facing errors
- Console logging for debugging
- Graceful fallbacks for API failures
- Form validation before submission
- Confirmation dialogs for destructive actions

**Performance Considerations:**
- Parallel data fetching on page load (Promise.all)
- Vendor stats fetched in loop (could be batched in Phase 4)
- Table sorting done client-side (sponsoredVendors.sort())
- Pagination deferred to Phase 4 for large vendor lists

---

## Deferred to Stage 4+
- [ ] Self-serve vendor campaign portal (vendorfacingUI, bid management)
- [ ] Auction engine (AdRank = Bid × EstimatedActionRate × QualityScore)
- [ ] Bulk vendor operations (add multiple vendors at once)
- [ ] Advanced filtering in vendor table (by category, placement, date range)
- [ ] CSV export of vendor performance data
- [ ] AI-powered contextual targeting and recommendation integration
- [ ] Full attribution pipeline (click_id → vendor_assignment → contract → payment)
- [ ] Stripe billing engine for ad spend and automated invoicing
- [ ] Advanced fraud detection and click validation
- [ ] A/B testing framework for ad placements
- [ ] Programmatic ad buying (REST API for external vendors)
- [ ] Real-time analytics dashboard with WebSocket updates
- [ ] Ad performance forecasting and optimization recommendations
- [ ] Vendor self-serve dashboard with earnings and campaign performance
- [ ] Custom reporting and scheduled email reports
- [ ] Banner ads and rich media (video, carousel) support

---

## Version History

| Version | Date | Status | Notes |
|---------|------|--------|-------|
| 1.2.0 | 2026-03-16 | Release | Responsive rail refactor, WCAG 2.1 AA accessibility, why-tag passthrough, type alignment, feature flag guard |
| 1.1.0 | 2026-03-16 | Release | Code review bugfix pass: 5 critical fixes ($or query, field name, CTR double-count, enum, vendor-role scoping) |
| 1.0.0 | 2026-03-15 | Release | Stages 1-3 complete: Full platform with leads, preferences, vendor self-serve, campaign wizard, analytics |
| 0.3.0 | 2026-03-11 | Beta | Phase 3 complete: Admin controls and analytics |
| 0.2.0 | 2026-03-11 | Beta | Phase 2 complete: Frontend display components |
| 0.1.0 | 2026-03-11 | Beta | Phase 1 complete: Backend models and API endpoints |

---

## Testing Checklist

### Phase 1 (Backend)
- [x] Feature flag GET endpoint returns correct config
- [x] Feature flag PUT endpoint toggles state
- [x] Create sponsored vendor saves to MongoDB
- [x] Update sponsored vendor modifies fields
- [x] Delete sponsored vendor soft-deletes (marks inactive)
- [x] Record ad event saves event to MongoDB
- [x] Get vendor stats calculates CTR correctly
- [x] Impressions and clicks increment properly

### Phase 2 (Frontend Display)
- [x] SponsoredVendorCard renders with image and metadata
- [x] SponsoredVendorCard fires impression event on mount
- [x] SponsoredVendorCard fires click events on interaction
- [x] SponsoredVendorsRail scrolls horizontally
- [x] SponsoredVendorsRail shows loading skeleton
- [x] SponsoredVendorsRail gracefully handles errors
- [x] SponsoredVendorDetailsDrawer opens on card click
- [x] SponsoredVendorDetailsDrawer displays full vendor info
- [x] All components hide if feature flag is disabled

### Phase 3 (Admin Controls)
- [x] Feature Settings tab displays feature flag status
- [x] Feature toggle button enables/disables feature
- [x] Sponsored Vendors tab displays all vendors
- [x] Add vendor form validates and submits
- [x] Priority inline editing updates vendor
- [x] Status toggle button activates/deactivates vendor
- [x] Delete button removes vendor with confirmation
- [x] Analytics tab shows summary cards
- [x] Analytics date range filter updates metrics
- [x] Vendor performance table sorts by impressions
- [x] All actions show proper loading and error states

---

## Database Schema Reference

### sponsored_vendors collection
```javascript
{
  _id: ObjectId,
  vendor_profile_id: String,      // FK to vendor profile
  placement: String,               // vendor_rail, vendor_detail, etc.
  priority: Number,                // lower = higher priority
  headline: String,                // optional display text
  description: String,             // optional display text
  is_active: Boolean,              // soft delete flag
  start_date: ISODate,             // optional campaign start
  end_date: ISODate,               // optional campaign end
  target_categories: Array,        // filter by vendor category
  target_wedding_stages: Array,    // filter by wedding stage
  created_by: String,              // admin user who created
  click_count: Number,             // denormalized from ad_events
  impression_count: Number,        // denormalized from ad_events
  metadata: Object,                // flexible extension point
  created_at: ISODate,
  updated_at: ISODate
}
```

### ad_events collection
```javascript
{
  _id: ObjectId,
  sponsored_vendor_id: ObjectId,   // FK to sponsored_vendors
  vendor_profile_id: String,       // denormalized for queries
  event_type: String,              // impression, click, dismiss, hover, detail_view, contact_click, assignment
  placement: String,               // where event occurred
  user_id: String,                 // optional, for attribution
  metadata: Object,                // flexible event context
  created_at: ISODate,
  timestamp: Number                // milliseconds since epoch
}
```

### ad_feature_flags collection
```javascript
{
  _id: ObjectId,
  feature_key: String,             // "advertising_enabled"
  is_enabled: Boolean,
  enabled_by: String,              // admin user who toggled
  enabled_at: ISODate,
  config: {
    max_sponsored_per_page: Number,
    show_sponsored_badge: Boolean,
    enable_click_tracking: Boolean,
    enable_impression_tracking: Boolean,
    minimum_impression_threshold: Number
  }
}
```

---

## API Request/Response Examples

### Get Feature Flag
```bash
GET /admin/ads/feature-flag
Authorization: Bearer <token>

Response:
{
  "_id": "...",
  "feature_key": "advertising_enabled",
  "is_enabled": true,
  "enabled_by": "admin@example.com",
  "enabled_at": "2026-03-11T10:30:00Z",
  "config": {
    "max_sponsored_per_page": 5,
    "show_sponsored_badge": true,
    "enable_click_tracking": true,
    "enable_impression_tracking": true,
    "minimum_impression_threshold": 10
  }
}
```

### Create Sponsored Vendor
```bash
POST /admin/ads/sponsored-vendors
Authorization: Bearer <token>
Content-Type: application/json

{
  "vendor_profile_id": "vendor_123",
  "placement": "vendor_rail",
  "priority": 1,
  "headline": "Featured Photographer",
  "is_active": true,
  "target_categories": ["photographer"],
  "target_wedding_stages": ["planning"]
}

Response: [SponsoredVendor object with _id, timestamps, etc.]
```

### Record Ad Event
```bash
POST /admin/ads/events
Authorization: Bearer <token>
Content-Type: application/json

{
  "sponsored_vendor_id": "...",
  "vendor_profile_id": "vendor_123",
  "event_type": "impression",
  "placement": "vendor_rail",
  "user_id": "user_456",
  "metadata": { "session_id": "...", "viewport_height": 1080 }
}

Response: 200 OK
```

### Get Vendor Stats
```bash
GET /admin/ads/sponsored-vendors/<id>/stats?days=7
Authorization: Bearer <token>

Response:
{
  "sponsored_vendor_id": "...",
  "total_impressions": 150,
  "total_clicks": 12,
  "ctr": 0.08,
  "recent_events": 162,
  "period_days": 7
}
```

---

## Notes for Future Phases

- Phase 4 should add vendor self-serve portal with campaign creation/bidding
- Consider caching feature flag at application level to reduce DB queries
- Stats calculation could be optimized with aggregation pipeline
- Event deduplication strategy needed if same user-vendor pair creates multiple impressions
- Plan for event retention policy (archive old events after N months)
- Consider Elasticsearch for event querying if scale increases

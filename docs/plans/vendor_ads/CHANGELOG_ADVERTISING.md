# Vendor Advertising Feature — Changelog

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

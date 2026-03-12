# Vendor Advertising Feature — Changelog

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

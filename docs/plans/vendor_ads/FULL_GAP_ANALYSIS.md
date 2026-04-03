# Vendor Advertising Monetization Platform — FULL GAP ANALYSIS

**Prepared:** March 18, 2026
**Scope:** Complete gap analysis comparing PRD requirements vs. actual implementation
**Methodology:** Reviewed PRD (Section 14.3 solo-dev revised architecture), backend code (models, services, API), frontend code (admin pages, vendor pages, components), and database indexes.

---

## EXECUTIVE SUMMARY

The vendor advertising system has **foundational infrastructure in place** but is **extremely incomplete relative to the PRD specification**. The implementation correctly implements the **Phase 1 foundation** (data models, basic API, feature flag, event tracking) but is **entirely missing**:

- Root admin dashboard with 4-tab design
- Vendor campaign creation wizard (6-step flow)
- Vendor ad manager portal (Campaigns, Creatives, Leads, Billing pages)
- Billing and monetization engine
- Analytics rollup pipeline for platform-level dashboards
- Fraud detection and quality scoring
- Frontend planner-facing UI components (missing some displays)
- Styling inconsistencies (light theme vs. dark glassmorphic platform standard)

**Critical Architectural Issue:** The system **conflates two different systems**:
1. **Planner-facing sponsored vendors** (what the admin manually populates via /admin/advertising)
2. **Vendor-created campaigns** (what vendors should create self-serve)

The current implementation maps everything through `vendor_profile_id`, but the PRD clearly specifies that **sponsored vendors are NOT vendor profiles**—they are **ad campaign records** managed by the admin for **external vendor outreach**.

---

## 1. CRITICAL ARCHITECTURAL GAP: Fundamentally Wrong Model

### The Problem

**The PRD (Section 2.1, 6.4)** states:

> "Vendors will pay to promote their services to planners through contextual, workflow-integrated sponsored recommendations... The Vendor Ad Campaign Manager adds a new section to the existing vendor workspace (vendor portal) where vendors can create, manage, and monitor advertising campaigns."

**Key points from PRD:**
- Section 2.1: Platform "reaches out to EXTERNAL vendors to advertise"
- Section 6.4: "Vendor Campaign Manager" is a **vendor portal feature** where vendors self-serve create campaigns
- Section 6.7: Stripe integration charges vendors for ad spend
- Section 8: `ad_campaigns` collection stores **vendor-created campaigns**, separate from vendor profiles

**The Implementation:**

The code conflates two separate systems:

1. **`SponsoredVendor` collection** (what exists):
   - Has `vendor_profile_id` pointing to existing planner-created vendor profiles
   - Admin manually populates via `/admin/advertising` page
   - Used to display ads to planners
   - This is correct for **Phase 1 foundation** (manual admin-managed ads)

2. **Missing `ad_campaigns` collection** (what should exist):
   - Should store vendor-created, self-serve campaigns
   - Should track bidding, budgets, goals (visits/quotes/bookings)
   - Should support auction mechanics, pacing, scheduling
   - Should integrate with vendor portal for self-serve management

**Why This Matters:**

The form at `/admin/advertising` (if it exists) asks an admin to "Select a vendor from the planner directory," but this is **backwards**. The PRD specifies:

- **Phase 1 (current):** Admin manually adds vendors to a sponsored list without requiring vendor opt-in
- **Phase 3+:** Vendors self-serve create campaigns, set budgets, choose bidding models

The current schema supports Phase 1 (admin-managed `SponsoredVendor` entries) but **is architecturally incompatible** with Phase 3+ (vendor self-serve campaigns with auctions and budget enforcement).

### Verdict

**CRITICAL GAP.** The data model works for Phase 1 but **cannot evolve** to support Phase 3+ auction mechanics, vendor self-serve, and billing.

---

## 2. SCHEMA DESIGN GAPS

### 2.1 Missing Collections

**Required by PRD (Section 8):**
- `ad_campaigns` — Vendor-created campaigns with bids, budgets, goals, schedules
- `placement_day_stats` — Platform-level daily rollups by placement type
- `ad_fraud_signals` — TTL-indexed anomaly detection records
- `ad_creative_assets` — Image/video/text asset library per vendor

**Status:** Only `SponsoredVendor`, `AdEvent`, `AdLead`, `AdStatsDaily` (partial) exist.

### 2.2 Missing Fields on Existing Collections

**`SponsoredVendor` missing:**
- `vendor_id` — Reference to actual vendor creating campaign (not `vendor_profile_id`)
- `goal` — (visits/quotes/bookings)
- `budget` fields: `daily_budget`, `lifetime_budget`, `remaining_budget`, `spent_to_date`
- `pricing_model` — (cpc, cpl, fixed)
- `bid` fields: `cpc_bid`, `cpl_bid`, `max_daily_spend_cap`
- `pacing` — (standard/accelerated)
- `quality_score` — For auction ranking
- `estimated_action_rate` — For auction ranking
- `target_regions` — Geographic targeting (city/metro/state)

**`AdEvent` missing:**
- `ip_address` — For fraud detection
- `user_agent` — For fraud detection

### 2.3 Missing Indexes

**From PRD Section 8.1, missing:**
- `ad_campaigns`: (vendor_id, status)
- `ad_campaigns`: (target_regions, status, target_categories)
- `ad_events`: unique on `click_id`
- `ad_fraud_signals`: (planner_id, campaign_id, detection_timestamp) with TTL

### 2.4 Verdict

**HIGH SEVERITY GAPS:**
- Missing `ad_campaigns` collection entirely (vendor self-serve feature)
- Missing `placement_day_stats` (platform-level reporting)
- Missing `ad_fraud_signals` (fraud detection)
- Missing critical fields for auction (quality_score, bid, goal, budget)

---

## 3. ROOT ADMIN DASHBOARD GAPS

### What PRD Specifies (Section 6.8)

Four-tab dashboard:
1. **Creative Review** — Approve/reject vendor creatives
2. **Campaign Monitor** — Track active campaigns, spend, performance
3. **System Config** — Frequency caps, minimum bids, policies
4. **Revenue Dashboard** — Aggregate monetization metrics
5. **Planner Feedback Monitor** — Aggregated hide/report actions (implied in 6.8)

### What Actually Exists

**Files found:**
- `/admin/ads/creative-review/page.tsx` ✓ Implemented
- `/admin/ads/performance/page.tsx` ✓ Implemented (but basic)
- `/admin/ads/revenue/page.tsx` ✓ Placeholder (honest)
- `/admin/ads/console/page.tsx` — Multi-tab console (58KB)

**Missing:**
- `/admin/ads/config/page.tsx` — System configuration
- `/admin/ads/feedback/page.tsx` — Planner feedback monitor

### 3.1 Creative Review

**Status:** ✓ Well-implemented

**What's there:**
- Queue stats (pending, approved, rejected, changes requested)
- Review queue with filters
- Approve/Reject/Request Changes with notes
- Vendor profile enrichment

**What's missing:**
- A/B testing preview
- Copy analysis
- Competitor comparison

### 3.2 Performance Dashboard

**Status:** ✓ Basic implementation

**What's there:**
- 5 metric cards
- Daily trends chart
- Platform health metrics
- Vendor leaderboard

**What's missing:**
- Lead funnel breakdown
- Engagement heatmap
- Placement performance breakdown
- Fraud alerts
- Cohort analysis

### 3.3 Revenue Dashboard

**Status:** Placeholder (honest)

The page explicitly states: "Billing is not active... Revenue tracking will be enabled once Stripe billing integration is built."

**Missing:**
- Stripe integration
- Usage records
- Invoice tracking
- Revenue by region/category/vendor
- CPC/CPL calculations

### 3.4 Verdict

**CRITICAL GAPS:**
- Config page missing
- Planner feedback monitor missing
- Revenue dashboard is non-functional placeholder
- Performance dashboard lacks advanced analytics

---

## 4. VENDOR AD MANAGER GAPS

### What Mockup/PRD Specifies

Vendor portal should have:
- Overview dashboard (impressions, clicks, CTR, leads, cost/lead)
- Campaigns page (list, edit, pause, delete, create new)
- Creatives library
- Leads inbox
- Billing history

### What Actually Exists

**Files found:**
- `/admin/vendor/ads/page.tsx` ✓ Overview dashboard
- `/admin/vendor/ads/campaigns/page.tsx` ✓ Campaign list (view-only)
- `/admin/vendor/ads/campaigns/new/page.tsx` ✓ Campaign wizard
- `/admin/vendor/ads/leads/page.tsx` ✓ Listed
- `/admin/vendor/ads/billing/page.tsx` ✓ Listed

### 4.1 Campaign Wizard (6-step flow)

**Status:** ✓ Mostly complete

**Steps implemented:**
1. Goal (visits/quotes/bookings) ✓
2. Targeting (placements + categories) ✓ But missing region targeting
3. Budget & Schedule (daily/lifetime, dates, pacing) ✓ But missing recommendations
4. Pricing (CPC, CPL, fixed) ✓
5. Creative (headline, description, offer, CTA, image) ✓ But missing placement preview
6. Review & Submit ✓ But missing reach/cost estimates

**Missing:**
- Region targeting (city/metro/state)
- Default budget recommendations
- Placement-specific ad preview
- Estimated daily reach

### 4.2 Campaign List

**Status:** View-only

**What's there:**
- Campaign list with headline, status, placement, priority, impressions, clicks

**What's missing:**
- Edit / pause / delete actions
- Bulk actions
- Sorting/filtering
- Quick stats (CTR, leads, CPA)
- Performance sparklines

### 4.3 Verdict

**HIGH SEVERITY GAPS:**
- Campaign wizard missing region targeting
- Campaign list view-only (no management actions)
- Missing placement preview
- Missing budget recommendations
- Missing reach estimates

---

## 5. BILLING & MONETIZATION GAPS

### What PRD Specifies (Section 6.7)

**Stage 1 (Fixed Pricing):**
- Weekly sponsored slots charged upfront via Stripe Checkout

**Stage 2+ (Performance Pricing):**
- CPC and CPL with second-price auction
- Budget controls (daily cap, lifetime cap, 80% alert)

**Stripe Integration:**
- Metered subscriptions for usage-based billing
- Invoicing and payment history
- Webhook handlers

### What Actually Exists

**Code review:**
- `SponsoredVendor` has metadata but no explicit budget fields
- No `ad_billing_records` collection
- No Stripe integration methods in `AdvertisingService`
- No `/api/billing/*` endpoints

**Revenue dashboard explicitly states:** "All monetary values shown below are $0 — this section is a placeholder"

### Verdict

**CRITICAL GAPS:**
- Stripe integration not started
- No usage metering
- No budget enforcement (campaigns don't pause)
- No invoice generation
- Billing impossible

---

## 6. ANALYTICS PIPELINE GAPS

### What PRD Specifies (Section 6.6)

**Collections:**
- `ad_events` — Raw events (✓ exists with TTL)
- `campaign_day_stats` — Daily rollups (✓ mapped to `ad_stats_daily`)
- `placement_day_stats` — Platform-level rollups (✗ missing)
- `ad_fraud_signals` — Anomaly detection (✗ missing)

**Computation:**
- Quality score (vendor rating, profile completeness, hide rate)
- Estimated action rate (ML model by region/category)
- Fraud detection (rate limiting, IP fingerprinting, session anomalies)

### What Actually Exists

**`ad_rollup_service.py` implements:**
- ✓ Event aggregation by vendor/placement/day
- ✓ Lead aggregation by vendor/placement
- ✓ CTR computation
- ✗ No quality score
- ✗ No estimated action rate
- ✗ No fraud detection
- ✗ No `placement_day_stats` rollup

### Verdict

**HIGH SEVERITY GAPS:**
- Missing `placement_day_stats` (platform reporting impossible)
- No fraud detection logic
- No quality score computation
- No automated pause rules

---

## 7. PLANNER-FACING UI GAPS

### Components Implemented

**Files found:**
- `SponsoredVendorsRail.tsx` ✓
- `SponsoredVendorCard.tsx` ✓
- `SponsoredVendorDetailsDrawer.tsx` ✓
- `SponsoredMilestoneModule.tsx` ✓
- `BoostedVendorCard.tsx` ✓

### Missing Features

**Transparency (PRD 6.2.1, 6.3):**
- No "Why am I seeing this?" tooltip
- No "See more" link
- No hide control
- No feedback mechanism (too many similar, not interested, etc.)

**Interactions:**
- Missing "Message vendor" CTA
- Missing review/rating display
- Missing price tier indicator

### Verdict

**MEDIUM SEVERITY GAPS:**
- Missing transparency features (why-tag, hide control)
- Missing interaction options (message, reviews, price tier)

---

## 8. STYLING GAPS

### The Problem

**Platform standard:** Dark glassmorphic theme with Tailwind `dark:` classes

**Admin pages:** Mixed light/dark, inline styles, inconsistent

**Examples:**
- Console page uses custom color variables (`NAVY`, `SAGE`, `ROSE`, `GOLD`)
- Vendor campaigns assume light background (`style={{ background: '#fff' }}`)
- Some pages use `dark:` classes, others don't

### Verdict

**MEDIUM SEVERITY.** Not functional but creates UX inconsistency.

---

## 9. API ENDPOINT GAPS

### Missing Endpoints

**Campaign management:**
- `PUT /vendor/ads/campaigns/:id` — Update campaign ✗
- `DELETE /vendor/ads/campaigns/:id` — Cancel campaign ✗
- `PATCH /vendor/ads/campaigns/:id/pause` — Pause campaign ✗

**Admin:**
- `GET /admin/ads/config` — System settings ✗
- `POST /admin/ads/config` — Update settings ✗
- `GET /admin/ads/feedback` — Planner feedback ✗

**Billing:**
- `GET /vendor/ads/billing` — Invoice history ✗
- Revenue metrics API ✗

### Verdict

**MEDIUM SEVERITY GAPS:**
- Campaign CRUD incomplete
- Admin config API missing
- Billing API missing

---

## 10. COMPREHENSIVE GAP SUMMARY TABLE

| **Gap** | **Severity** | **Impact** | **PRD Ref** |
|---|---|---|---|
| Missing `ad_campaigns` collection | CRITICAL | Vendor self-serve impossible | 6.4, 8 |
| Missing auction fields (quality_score, bid, budget) | CRITICAL | Cannot rank ads fairly | 6.5 |
| Missing Stripe billing integration | CRITICAL | No revenue possible | 6.7 |
| Missing budget enforcement | CRITICAL | Vendors can overdraft | 6.7 |
| Missing `placement_day_stats` collection | HIGH | Platform metrics invisible | 6.6.3 |
| Missing `ad_fraud_signals` collection | HIGH | Vulnerable to click fraud | 6.6.4 |
| Missing fraud detection logic | HIGH | No click rate limiting, IP checks | 6.6.4 |
| Missing quality score computation | HIGH | Auction cannot weight quality | 6.5 |
| Admin config page missing | MEDIUM | No central control of policies | 6.8 |
| Planner feedback monitor missing | MEDIUM | Cannot monitor quality degradation | 6.8 |
| Revenue dashboard is placeholder | CRITICAL | Cannot demonstrate monetization | 6.8 |
| Campaign wizard missing region targeting | HIGH | Geographic relevance incomplete | 6.4 |
| Campaign wizard missing budget recommendations | MEDIUM | Vendors unsure of spend | 6.4 |
| Campaign wizard missing placement preview | MEDIUM | Vendors blind to framing | 6.4 |
| Campaign list view-only (no edit/pause/delete) | HIGH | Poor UX; vendor churn risk | 6.4 |
| Missing "Why am I seeing this?" tooltip | MEDIUM | Low transparency; trust risk | 6.2.1 |
| Missing hide/feedback controls | MEDIUM | Preference capture inefficient | 6.2.1, 6.3 |
| Missing campaign update/delete API endpoints | HIGH | Cannot manage campaigns via API | 6.4 |
| Inconsistent dark mode styling | MEDIUM | UX inconsistency; readability issues | Design |

---

## 11. ROOT CAUSES

1. **Solo-dev simplification:** PRD assumes multi-team. Solo dev deferred Phase 3+ features. But Phase 1 architecture should be compatible with Phase 3.

2. **Fundamental design confusion:** Using `vendor_profile_id` on `SponsoredVendor` conflates **ad placements** with **vendor contacts**. They are separate concepts. This will require refactoring for Phase 3.

3. **Incremental delivery without forward compatibility:** Billing system not even stubbed. Should have placeholder that flows through entire stack (Stripe Checkout → usage record → invoice) even if amounts are $0.

4. **Honest placeholders vs missing work:** Revenue dashboard is honest. But honest alone is not enough—system should work end-to-end with $0 charges, ready for monetization.

---

## 12. RECOMMENDATIONS

### To Unlock Monetization (Next 40-60 hours):

1. **Implement Stripe integration:**
   - Usage metering for clicks/leads
   - Budget enforcement (pause at cap)
   - Monthly invoicing

2. **Complete admin dashboards:**
   - Config page (frequency caps, bid floors, policies)
   - Planner feedback monitor
   - Real revenue calculations

3. **Add campaign management:**
   - Edit/pause/delete endpoints and UI
   - Vendor admin screens for actions

### To Enable Vendor Self-Serve (Phase 3):

4. **Refactor schema:**
   - Separate `ad_campaigns` from `SponsoredVendor`
   - Add auction fields (quality_score, bid, budget)

5. **Implement auction engine:**
   - Quality score computation
   - Second-price auction logic
   - Real-time ranking

6. **Fraud detection:**
   - Rate limiting
   - Automated pause rules
   - Anomaly detection

---

## 13. CONCLUSION

The advertising system has a **solid Phase 1 foundation** but is **not monetization-ready**. Top blockers:

1. **No Stripe integration** → Can't charge vendors
2. **No budget enforcement** → Can't limit spending
3. **No campaign CRUD** → Vendors can't manage campaigns
4. **No admin dashboards** → Can't monitor system health

**To validate demand and generate revenue:** Implement billing, admin dashboards, and campaign management. Estimated: 40-60 hours.

**To support vendor self-serve:** Refactor schema and implement auction engine. Estimated: 8-12 weeks after Phase 1 completion.

---

## Appendix: Files Reviewed

**Backend:**
- `/app/models/advertising.py` (678 lines)
- `/app/services/advertising_service.py` (1121 lines)
- `/app/services/ad_rollup_service.py` (574 lines)
- `/app/api/advertising.py` (51KB)
- `/app/core/database_indexes.py` (grep results)

**Admin Pages:**
- `/admin/ads/creative-review/page.tsx` ✓
- `/admin/ads/revenue/page.tsx` ✓
- `/admin/ads/performance/page.tsx` ✓
- `/admin/ads/console/page.tsx` (58KB)

**Vendor Pages:**
- `/admin/vendor/ads/page.tsx` ✓
- `/admin/vendor/ads/campaigns/page.tsx` ✓
- `/admin/vendor/ads/campaigns/new/page.tsx` ✓

**Frontend Components:**
- `SponsoredVendorsRail.tsx` ✓
- `SponsoredVendorCard.tsx` ✓
- `SponsoredVendorDetailsDrawer.tsx` (exists)
- `SponsoredMilestoneModule.tsx` (exists)
- `BoostedVendorCard.tsx` (exists)


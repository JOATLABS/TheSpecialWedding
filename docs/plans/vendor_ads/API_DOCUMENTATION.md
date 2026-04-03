# Vendor Advertising Monetization Platform - API Documentation

## Overview

The Vendor Advertising Monetization Platform provides a comprehensive suite of APIs for managing advertising campaigns, creatives, and interactions. The platform is designed to help vendors reach wedding planners through targeted advertising while maintaining quality standards through an approval workflow.

**Base URL:** `https://api.weddingapp.com`

**API Version:** 1.0

---

## Table of Contents

1. [Authentication](#authentication)
2. [Vendor Portal API](#vendor-portal-api)
3. [Admin Campaign API](#admin-campaign-api)
4. [Planner Ad Interactions API](#planner-ad-interactions-api)
5. [Data Models](#data-models)
6. [Status Lifecycles](#status-lifecycles)
7. [Error Codes](#error-codes)
8. [Common Patterns](#common-patterns)

---

## Authentication

All API endpoints require Bearer token authentication in the `Authorization` header.

### Authorization Header Format

```
Authorization: Bearer {token}
```

### Token Types and Permissions

| Token Type | Access Level | Available Endpoints |
|-----------|--------------|-------------------|
| `vendor` | Vendor-level access | Vendor Portal API (`/portal/ads`) |
| `wedding_planner` | Planner-level access | Planner Ad Interactions API (`/planner/ads`) |
| `root_admin` | Full administrative access | All endpoints |

### Authentication Example

```bash
curl -X GET https://api.weddingapp.com/portal/ads/campaigns \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Vendor Portal API

**Prefix:** `/portal/ads`

**Auth Required:** Bearer token (vendor or root_admin)

The Vendor Portal API allows vendors to manage their advertising campaigns, creatives, and view performance metrics.

### Campaigns

#### Create Campaign

Creates a new draft campaign.

```
POST /portal/ads/campaigns
```

**Request Body:**

```json
{
  "campaign_name": "Summer Wedding Season 2026",
  "goal": "clicks",
  "target_categories": ["photography", "catering", "venues"],
  "target_regions": ["California", "Nevada"],
  "target_placements": ["sidebar", "featured"],
  "daily_budget": 50.00,
  "total_budget": 1500.00,
  "start_date": "2026-04-01",
  "end_date": "2026-08-31"
}
```

**Response:** `201 Created`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "vendor_id": "vend_2c4e8b3a1f5d9c2e",
  "campaign_name": "Summer Wedding Season 2026",
  "goal": "clicks",
  "status": "draft",
  "target_categories": ["photography", "catering", "venues"],
  "target_regions": ["California", "Nevada"],
  "target_placements": ["sidebar", "featured"],
  "daily_budget": 50.00,
  "total_budget": 1500.00,
  "start_date": "2026-04-01",
  "end_date": "2026-08-31",
  "quality_score": null,
  "created_at": "2026-03-20T10:30:00Z",
  "updated_at": "2026-03-20T10:30:00Z"
}
```

#### List Campaigns

Retrieves all campaigns for the authenticated vendor.

```
GET /portal/ads/campaigns
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (draft, pending_review, active, paused, completed, rejected) |
| `limit` | integer | Number of results (default: 20, max: 100) |
| `skip` | integer | Number of results to skip for pagination (default: 0) |

**Response:** `200 OK`

```json
{
  "campaigns": [
    {
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "vendor_id": "vend_2c4e8b3a1f5d9c2e",
      "campaign_name": "Summer Wedding Season 2026",
      "goal": "clicks",
      "status": "active",
      "daily_budget": 50.00,
      "total_budget": 1500.00,
      "quality_score": 8.5,
      "created_at": "2026-03-20T10:30:00Z",
      "updated_at": "2026-03-21T14:15:00Z"
    }
  ],
  "total": 5,
  "limit": 20,
  "skip": 0
}
```

#### Get Campaign Details

Retrieves detailed information about a specific campaign.

```
GET /portal/ads/campaigns/{campaign_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `campaign_id` | string | Unique campaign identifier |

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "vendor_id": "vend_2c4e8b3a1f5d9c2e",
  "campaign_name": "Summer Wedding Season 2026",
  "goal": "clicks",
  "status": "active",
  "target_categories": ["photography", "catering"],
  "target_regions": ["California"],
  "target_placements": ["sidebar"],
  "daily_budget": 50.00,
  "total_budget": 1500.00,
  "start_date": "2026-04-01",
  "end_date": "2026-08-31",
  "quality_score": 8.5,
  "created_at": "2026-03-20T10:30:00Z",
  "updated_at": "2026-03-21T14:15:00Z",
  "creatives": [
    {
      "creative_id": "crea_7b2c4e8a1f5d9c3e",
      "creative_type": "image",
      "image_url": "https://cdn.weddingapp.com/creative_7b2c4e8a.jpg",
      "headline": "Beautiful Wedding Photography",
      "description": "Capture your special moments with our award-winning photography team",
      "offer": "20% off for bookings before May 1st",
      "call_to_action": "Book Now",
      "review_status": "approved",
      "is_primary": true
    }
  ]
}
```

#### Update Campaign

Updates a draft campaign. Only campaigns with `status: "draft"` can be updated.

```
PUT /portal/ads/campaigns/{campaign_id}
```

**Request Body:**

```json
{
  "campaign_name": "Summer Wedding Season 2026 - Updated",
  "daily_budget": 75.00,
  "target_categories": ["photography", "catering", "venues", "florals"]
}
```

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "campaign_name": "Summer Wedding Season 2026 - Updated",
  "status": "draft",
  "daily_budget": 75.00,
  "updated_at": "2026-03-21T09:45:00Z"
}
```

#### Delete Campaign

Deletes a draft campaign. Only campaigns with `status: "draft"` can be deleted.

```
DELETE /portal/ads/campaigns/{campaign_id}
```

**Response:** `204 No Content`

#### Submit Campaign for Review

Submits a draft campaign for administrative review. Changes status from `draft` to `pending_review`.

```
POST /portal/ads/campaigns/{campaign_id}/submit
```

**Request Body:** Empty

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "status": "pending_review",
  "submitted_at": "2026-03-21T11:20:00Z",
  "message": "Campaign submitted for review"
}
```

#### Pause Campaign

Vendor pauses an active campaign.

```
POST /portal/ads/campaigns/{campaign_id}/pause
```

**Request Body:** Empty

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "status": "paused",
  "paused_at": "2026-03-21T12:00:00Z"
}
```

#### Get Campaign Stats

Retrieves performance statistics for a campaign.

```
GET /portal/ads/campaigns/{campaign_id}/stats
```

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "impressions": 15420,
  "clicks": 1245,
  "ctr": 0.0808,
  "leads": 87,
  "conversion_rate": 0.0699,
  "spent": 1234.50,
  "remaining_budget": 265.50,
  "start_date": "2026-04-01",
  "end_date": "2026-08-31",
  "last_updated": "2026-03-21T14:30:00Z"
}
```

### Creatives

#### Create Creative

Creates a new creative asset for a campaign.

```
POST /portal/ads/campaigns/{campaign_id}/creatives
```

**Request Body:**

```json
{
  "creative_type": "image",
  "image_url": "https://cdn.weddingapp.com/creative_example.jpg",
  "headline": "Professional Wedding Photography Services",
  "description": "Capture your special moments with our experienced photography team. We specialize in candid and traditional shots.",
  "offer": "20% off for bookings made before May 1st",
  "call_to_action": "Book Now"
}
```

**Response:** `201 Created`

```json
{
  "creative_id": "crea_7b2c4e8a1f5d9c3e",
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "creative_type": "image",
  "image_url": "https://cdn.weddingapp.com/creative_7b2c4e8a.jpg",
  "headline": "Professional Wedding Photography Services",
  "description": "Capture your special moments with our experienced photography team. We specialize in candid and traditional shots.",
  "offer": "20% off for bookings made before May 1st",
  "call_to_action": "Book Now",
  "review_status": "pending",
  "is_primary": false,
  "created_at": "2026-03-21T10:15:00Z"
}
```

#### List Campaign Creatives

Retrieves all creatives for a specific campaign.

```
GET /portal/ads/campaigns/{campaign_id}/creatives
```

**Response:** `200 OK`

```json
{
  "creatives": [
    {
      "creative_id": "crea_7b2c4e8a1f5d9c3e",
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "creative_type": "image",
      "headline": "Professional Wedding Photography Services",
      "review_status": "approved",
      "is_primary": true,
      "created_at": "2026-03-21T10:15:00Z"
    },
    {
      "creative_id": "crea_9d3f2b4e8a1c5d7f",
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "creative_type": "image",
      "headline": "Elegant Portrait Sessions",
      "review_status": "pending",
      "is_primary": false,
      "created_at": "2026-03-21T11:30:00Z"
    }
  ],
  "total": 2
}
```

#### Update Creative

Updates an existing creative.

```
PUT /portal/ads/creatives/{creative_id}
```

**Request Body:**

```json
{
  "headline": "Premium Wedding Photography Services",
  "description": "Capture your special moments with our award-winning photography team.",
  "offer": "25% off for bookings made before May 15th"
}
```

**Response:** `200 OK`

```json
{
  "creative_id": "crea_7b2c4e8a1f5d9c3e",
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "headline": "Premium Wedding Photography Services",
  "description": "Capture your special moments with our award-winning photography team.",
  "offer": "25% off for bookings made before May 15th",
  "updated_at": "2026-03-21T15:45:00Z"
}
```

#### Set Primary Creative

Designates a creative as the primary creative for its campaign.

```
POST /portal/ads/campaigns/{campaign_id}/creatives/{creative_id}/set-primary
```

**Request Body:** Empty

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "creative_id": "crea_7b2c4e8a1f5d9c3e",
  "is_primary": true,
  "message": "Creative set as primary"
}
```

### Leads & Billing

#### List Leads

Retrieves leads generated from advertising campaigns.

```
GET /portal/ads/leads
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `campaign_id` | string | Filter by specific campaign |
| `lead_type` | string | Filter by type (add_to_directory, quote_request) |
| `status` | string | Filter by status (new, contacted, converted) |
| `limit` | integer | Number of results (default: 20, max: 100) |
| `skip` | integer | Number of results to skip (default: 0) |

**Response:** `200 OK`

```json
{
  "leads": [
    {
      "lead_id": "lead_3c5e7a1b2d4f8a9c",
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "planner_id": "plan_1a3b5c7d9e2f4g6h",
      "lead_type": "quote_request",
      "status": "new",
      "message": "Interested in your photography services for June wedding",
      "wedding_id": "wed_2f4g6h8i1a3b5c7d",
      "created_at": "2026-03-21T13:20:00Z"
    },
    {
      "lead_id": "lead_4d6f8b2c3e5g9a1d",
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "planner_id": "plan_2b4c6d8e0f1g3h5i",
      "lead_type": "add_to_directory",
      "status": "converted",
      "created_at": "2026-03-20T09:15:00Z"
    }
  ],
  "total": 42,
  "limit": 20,
  "skip": 0
}
```

#### Get Billing Summary

Retrieves billing and cost information for the vendor.

```
GET /portal/ads/billing
```

**Response:** `200 OK`

```json
{
  "vendor_id": "vend_2c4e8b3a1f5d9c2e",
  "total_spent": 3450.75,
  "total_leads": 156,
  "cost_per_lead": 22.11,
  "current_month_spent": 1234.50,
  "current_month_leads": 45,
  "active_campaigns": 2,
  "payment_method": "credit_card",
  "account_balance": 500.00,
  "last_updated": "2026-03-21T14:30:00Z"
}
```

---

## Admin Campaign API

**Prefix:** `/admin/ads/campaigns`

**Auth Required:** Bearer token (root_admin only)

The Admin Campaign API provides administrative functions for reviewing campaigns, managing creatives, and monitoring system health.

### Review Queue

#### Get Review Queue

Retrieves all campaigns pending administrative review.

```
GET /admin/ads/campaigns/review
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Number of results (default: 20, max: 100) |
| `skip` | integer | Number of results to skip (default: 0) |

**Response:** `200 OK`

```json
{
  "campaigns": [
    {
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "vendor_id": "vend_2c4e8b3a1f5d9c2e",
      "vendor_name": "Premier Photography Co.",
      "campaign_name": "Summer Wedding Season 2026",
      "status": "pending_review",
      "daily_budget": 50.00,
      "submitted_at": "2026-03-21T11:20:00Z",
      "quality_score": 7.8,
      "flagged": false
    }
  ],
  "total": 3,
  "limit": 20,
  "skip": 0
}
```

#### Get Review Status Counts

Retrieves count of campaigns in each review status.

```
GET /admin/ads/campaigns/review/counts
```

**Response:** `200 OK`

```json
{
  "pending_review": 3,
  "approved": 18,
  "rejected": 2,
  "request_changes": 1
}
```

#### Approve Campaign

Approves a campaign pending review. Changes status from `pending_review` to `active`.

```
PUT /admin/ads/campaigns/{campaign_id}/approve
```

**Request Body:** Empty

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "status": "active",
  "approved_at": "2026-03-21T14:30:00Z",
  "approved_by": "admin_1c3e5a7b9d2f4g6h"
}
```

#### Reject Campaign

Rejects a campaign pending review. Changes status to `rejected`.

```
PUT /admin/ads/campaigns/{campaign_id}/reject
```

**Request Body:**

```json
{
  "reason": "Content violates advertising guidelines. Images must not contain faces without consent."
}
```

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "status": "rejected",
  "reason": "Content violates advertising guidelines. Images must not contain faces without consent.",
  "rejected_at": "2026-03-21T14:35:00Z",
  "rejected_by": "admin_1c3e5a7b9d2f4g6h"
}
```

#### Request Changes

Returns a campaign to the vendor with requested modifications.

```
PUT /admin/ads/campaigns/{campaign_id}/request-changes
```

**Request Body:**

```json
{
  "notes": "Please update the headline to be more descriptive. Current headline is too generic."
}
```

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "status": "draft",
  "notes": "Please update the headline to be more descriptive. Current headline is too generic.",
  "returned_at": "2026-03-21T14:40:00Z",
  "returned_by": "admin_1c3e5a7b9d2f4g6h"
}
```

### Creative Review

#### Get Creative Review Queue

Retrieves all creatives pending approval.

```
GET /admin/ads/campaigns/review/creatives
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Number of results (default: 20, max: 100) |
| `skip` | integer | Number of results to skip (default: 0) |

**Response:** `200 OK`

```json
{
  "creatives": [
    {
      "creative_id": "crea_7b2c4e8a1f5d9c3e",
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "vendor_id": "vend_2c4e8b3a1f5d9c2e",
      "creative_type": "image",
      "headline": "Professional Wedding Photography Services",
      "review_status": "pending",
      "submitted_at": "2026-03-21T10:15:00Z"
    }
  ],
  "total": 5,
  "limit": 20,
  "skip": 0
}
```

#### Approve Creative

Approves a creative pending review.

```
PUT /admin/ads/campaigns/review/creatives/{creative_id}/approve
```

**Request Body:** Empty

**Response:** `200 OK`

```json
{
  "creative_id": "crea_7b2c4e8a1f5d9c3e",
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "review_status": "approved",
  "approved_at": "2026-03-21T15:00:00Z",
  "approved_by": "admin_1c3e5a7b9d2f4g6h"
}
```

#### Reject Creative

Rejects a creative pending review.

```
PUT /admin/ads/campaigns/review/creatives/{creative_id}/reject
```

**Request Body:**

```json
{
  "reason": "Image quality is too low. Please provide a higher resolution image (minimum 1200x800px)."
}
```

**Response:** `200 OK`

```json
{
  "creative_id": "crea_7b2c4e8a1f5d9c3e",
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "review_status": "rejected",
  "reason": "Image quality is too low. Please provide a higher resolution image (minimum 1200x800px).",
  "rejected_at": "2026-03-21T15:05:00Z",
  "rejected_by": "admin_1c3e5a7b9d2f4g6h"
}
```

### Monitoring

#### List All Campaigns

Retrieves all campaigns with optional filtering.

```
GET /admin/ads/campaigns/
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status |
| `vendor_id` | string | Filter by vendor |
| `limit` | integer | Number of results (default: 20, max: 100) |
| `skip` | integer | Number of results to skip (default: 0) |

**Response:** `200 OK`

```json
{
  "campaigns": [
    {
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "vendor_id": "vend_2c4e8b3a1f5d9c2e",
      "vendor_name": "Premier Photography Co.",
      "campaign_name": "Summer Wedding Season 2026",
      "status": "active",
      "quality_score": 8.5,
      "daily_budget": 50.00,
      "created_at": "2026-03-20T10:30:00Z"
    }
  ],
  "total": 42,
  "limit": 20,
  "skip": 0
}
```

#### Pause Campaign (Admin)

Administrator pauses an active campaign.

```
PUT /admin/ads/campaigns/{campaign_id}/pause
```

**Request Body:** Empty

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "status": "paused",
  "paused_at": "2026-03-21T16:00:00Z",
  "paused_by": "admin_1c3e5a7b9d2f4g6h"
}
```

#### Deactivate Campaign

Permanently deactivates a campaign, preventing any future resumption.

```
PUT /admin/ads/campaigns/{campaign_id}/deactivate
```

**Request Body:** Empty

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "status": "completed",
  "deactivated_at": "2026-03-21T16:05:00Z",
  "deactivated_by": "admin_1c3e5a7b9d2f4g6h"
}
```

### Dashboard

#### Revenue Summary

Retrieves revenue metrics for a specified period.

```
GET /admin/ads/campaigns/revenue
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `period` | string | Time period (today, week, month, year) |

**Response:** `200 OK`

```json
{
  "period": "month",
  "total_revenue": 12500.00,
  "total_leads": 450,
  "average_cost_per_lead": 27.78,
  "active_campaigns": 15,
  "top_categories": [
    {
      "category": "photography",
      "revenue": 4200.00,
      "leads": 150
    },
    {
      "category": "catering",
      "revenue": 3800.00,
      "leads": 140
    }
  ],
  "last_updated": "2026-03-21T14:30:00Z"
}
```

#### Planner Feedback

Retrieves feedback and ratings from wedding planners on vendor ads.

```
GET /admin/ads/campaigns/feedback
```

**Response:** `200 OK`

```json
{
  "feedback": [
    {
      "feedback_id": "feed_1a3b5c7d9e2f4g6h",
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "vendor_id": "vend_2c4e8b3a1f5d9c2e",
      "planner_id": "plan_2b4c6d8e0f1g3h5i",
      "rating": 4.5,
      "comment": "Good quality ads, relevant to my planning needs",
      "submitted_at": "2026-03-20T11:15:00Z"
    }
  ],
  "average_rating": 4.2,
  "total_feedback": 87
}
```

#### Fraud Signals

Retrieves detected fraud signals and suspicious activities.

```
GET /admin/ads/campaigns/fraud-signals
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (pending, investigated, resolved, dismissed) |

**Response:** `200 OK`

```json
{
  "fraud_signals": [
    {
      "signal_id": "fraud_5c7d9e1f3a5b7c2d",
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "vendor_id": "vend_2c4e8b3a1f5d9c2e",
      "signal_type": "unusual_click_pattern",
      "severity": "medium",
      "status": "pending",
      "detected_at": "2026-03-21T12:30:00Z",
      "details": "Click rate 3x higher than average for category"
    }
  ],
  "total": 2
}
```

#### Update Fraud Signal Status

Updates the investigation status of a fraud signal.

```
PUT /admin/ads/campaigns/fraud-signals/{signal_id}
```

**Request Body:**

```json
{
  "status": "investigated",
  "notes": "Click pattern verified as legitimate. Vendor ran targeted social media campaign."
}
```

**Response:** `200 OK`

```json
{
  "signal_id": "fraud_5c7d9e1f3a5b7c2d",
  "status": "investigated",
  "notes": "Click pattern verified as legitimate. Vendor ran targeted social media campaign.",
  "updated_at": "2026-03-21T16:45:00Z",
  "updated_by": "admin_1c3e5a7b9d2f4g6h"
}
```

#### Vendor Accounts List

Retrieves all vendor accounts with summary information.

```
GET /admin/ads/campaigns/vendors
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Number of results (default: 20, max: 100) |
| `skip` | integer | Number of results to skip (default: 0) |

**Response:** `200 OK`

```json
{
  "vendors": [
    {
      "vendor_id": "vend_2c4e8b3a1f5d9c2e",
      "vendor_name": "Premier Photography Co.",
      "contact_email": "contact@premierphotography.com",
      "active_campaigns": 2,
      "total_spent": 3450.75,
      "total_leads": 156,
      "account_status": "active",
      "created_at": "2026-01-15T08:00:00Z"
    }
  ],
  "total": 28,
  "limit": 20,
  "skip": 0
}
```

#### Get System Configuration

Retrieves current system configuration settings.

```
GET /admin/ads/campaigns/config
```

**Response:** `200 OK`

```json
{
  "platform_settings": {
    "max_daily_budget": 500.00,
    "min_daily_budget": 5.00,
    "max_total_budget": 10000.00,
    "min_quality_score_for_approval": 7.0,
    "headline_max_length": 100,
    "description_max_length": 300,
    "offer_max_length": 200,
    "cta_max_length": 50
  },
  "campaign_settings": {
    "auto_expire_days": 90,
    "quality_score_recalculation_interval": "daily"
  },
  "last_updated": "2026-03-15T10:00:00Z"
}
```

#### Update System Configuration

Updates system configuration settings.

```
PUT /admin/ads/campaigns/config
```

**Request Body:**

```json
{
  "platform_settings": {
    "max_daily_budget": 750.00,
    "min_quality_score_for_approval": 7.5
  }
}
```

**Response:** `200 OK`

```json
{
  "platform_settings": {
    "max_daily_budget": 750.00,
    "min_daily_budget": 5.00,
    "max_total_budget": 10000.00,
    "min_quality_score_for_approval": 7.5,
    "headline_max_length": 100,
    "description_max_length": 300,
    "offer_max_length": 200,
    "cta_max_length": 50
  },
  "updated_at": "2026-03-21T17:00:00Z",
  "updated_by": "admin_1c3e5a7b9d2f4g6h"
}
```

---

## Planner Ad Interactions API

**Prefix:** `/planner/ads`

**Auth Required:** Bearer token (wedding_planner or root_admin)

The Planner Ad Interactions API enables wedding planners to interact with vendor advertisements and manage vendor relationships.

### Get Sponsored Cards

Retrieves sponsored vendor cards for display in the planner interface.

```
GET /planner/ads/sponsored-cards
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `placement` | string | Display location (sidebar, featured, rail) |
| `category` | string | Filter by vendor category (optional) |
| `limit` | integer | Number of cards (default: 5, max: 20) |

**Response:** `200 OK`

```json
{
  "sponsored_cards": [
    {
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "creative_id": "crea_7b2c4e8a1f5d9c3e",
      "click_id": "click_8c3f5d7a2e4g6b9c",
      "vendor_name": "Premier Photography Co.",
      "vendor_id": "vend_2c4e8b3a1f5d9c2e",
      "category": "photography",
      "headline": "Professional Wedding Photography Services",
      "description": "Capture your special moments with our award-winning photography team",
      "image_url": "https://cdn.weddingapp.com/creative_7b2c4e8a.jpg",
      "offer": "20% off for bookings before May 1st",
      "call_to_action": "Book Now"
    }
  ],
  "total": 1
}
```

### Add Vendor to Directory

Adds a sponsored vendor to the planner's directory.

```
POST /planner/ads/add-to-directory
```

**Request Body:**

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "creative_id": "crea_7b2c4e8a1f5d9c3e",
  "click_id": "click_8c3f5d7a2e4g6b9c"
}
```

**Response:** `201 Created`

```json
{
  "directory_entry_id": "dent_9d4g6e8b3f5h7c1d",
  "planner_id": "plan_1a3b5c7d9e2f4g6h",
  "vendor_id": "vend_2c4e8b3a1f5d9c2e",
  "vendor_name": "Premier Photography Co.",
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "added_at": "2026-03-21T13:45:00Z",
  "message": "Vendor added to your directory"
}
```

### Send Quote Request

Sends a quote request to a vendor through their campaign.

```
POST /planner/ads/request-quote
```

**Request Body:**

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "creative_id": "crea_7b2c4e8a1f5d9c3e",
  "click_id": "click_8c3f5d7a2e4g6b9c",
  "wedding_id": "wed_2f4g6h8i1a3b5c7d",
  "message": "Interested in your photography services for our June 15th wedding. We have approximately 100 guests."
}
```

**Response:** `201 Created`

```json
{
  "lead_id": "lead_3c5e7a1b2d4f8a9c",
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "vendor_id": "vend_2c4e8b3a1f5d9c2e",
  "planner_id": "plan_1a3b5c7d9e2f4g6h",
  "lead_type": "quote_request",
  "status": "new",
  "wedding_id": "wed_2f4g6h8i1a3b5c7d",
  "message": "Interested in your photography services for our June 15th wedding. We have approximately 100 guests.",
  "created_at": "2026-03-21T14:10:00Z"
}
```

### Check Directory Status

Checks if a vendor is already in the planner's directory.

```
GET /planner/ads/directory-status
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `campaign_id` | string | Campaign to check |

**Response:** `200 OK`

```json
{
  "campaign_id": "camp_5a8f2b1c9d3e7f2a",
  "vendor_id": "vend_2c4e8b3a1f5d9c2e",
  "in_directory": true,
  "added_at": "2026-03-21T13:45:00Z"
}
```

---

## Data Models

### AdCampaign

Represents an advertising campaign created by a vendor.

| Field | Type | Description |
|-------|------|-------------|
| `campaign_id` | string | Unique campaign identifier |
| `vendor_id` | string | ID of the vendor who created the campaign |
| `campaign_name` | string | Name of the campaign |
| `goal` | string | Campaign goal (clicks, leads, conversions) |
| `status` | string | Campaign status (draft, pending_review, active, paused, completed, rejected) |
| `target_categories` | array | Array of targeted vendor categories |
| `target_regions` | array | Array of targeted geographic regions |
| `target_placements` | array | Array of placement locations (sidebar, featured, rail) |
| `daily_budget` | number | Daily budget allocation in USD |
| `total_budget` | number | Total campaign budget in USD |
| `start_date` | string | Campaign start date (ISO 8601) |
| `end_date` | string | Campaign end date (ISO 8601) |
| `quality_score` | number | Quality score (0-10, null if not yet calculated) |
| `created_at` | string | Timestamp of campaign creation (ISO 8601) |
| `updated_at` | string | Timestamp of last update (ISO 8601) |

### AdCreative

Represents a creative asset for a campaign.

| Field | Type | Description |
|-------|------|-------------|
| `creative_id` | string | Unique creative identifier |
| `campaign_id` | string | ID of the parent campaign |
| `vendor_id` | string | ID of the vendor |
| `creative_type` | string | Type of creative (image, video, carousel) |
| `image_url` | string | URL to the creative image |
| `headline` | string | Headline text (max 100 characters) |
| `description` | string | Description text (max 300 characters) |
| `offer` | string | Promotional offer text (max 200 characters) |
| `call_to_action` | string | CTA button text (max 50 characters) |
| `review_status` | string | Review status (pending, approved, rejected) |
| `is_primary` | boolean | Whether this is the primary creative for the campaign |
| `created_at` | string | Timestamp of creation (ISO 8601) |
| `updated_at` | string | Timestamp of last update (ISO 8601) |

---

## Status Lifecycles

### Campaign Status Lifecycle

```
draft
  ↓
  ├─→ pending_review (via /submit)
  │     ├─→ active (admin approval)
  │     ├─→ rejected (admin rejection)
  │     └─→ draft (admin request changes)
  │
  └─→ deleted (via DELETE)

active
  ├─→ paused (vendor or admin pause)
  └─→ completed (end date reached or admin deactivate)

paused
  └─→ active (vendor resume)
```

### Creative Status Lifecycle

```
pending
  ├─→ approved (admin approval)
  └─→ rejected (admin rejection)

approved
  └─→ available for campaigns
```

---

## Error Codes

All API errors follow a standard error response format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "details": {}
  },
  "status": 400
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource successfully created |
| 204 | No Content - Successful deletion |
| 400 | Bad Request - Invalid request parameters |
| 401 | Unauthorized - Missing or invalid authentication token |
| 403 | Forbidden - Insufficient permissions for this action |
| 404 | Not Found - Resource does not exist |
| 409 | Conflict - Request conflicts with current state |
| 422 | Unprocessable Entity - Request validation failed |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error occurred |

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_TOKEN` | 401 | Authentication token is missing, invalid, or expired |
| `INSUFFICIENT_PERMISSIONS` | 403 | User lacks required permissions for this action |
| `RESOURCE_NOT_FOUND` | 404 | Requested resource does not exist |
| `INVALID_REQUEST_BODY` | 400 | Request body contains invalid or missing fields |
| `INVALID_QUERY_PARAMS` | 400 | Query parameters are invalid |
| `CAMPAIGN_NOT_DRAFT` | 409 | Cannot update campaign - only draft campaigns can be modified |
| `CAMPAIGN_NOT_PENDING_REVIEW` | 409 | Cannot approve/reject campaign - campaign is not pending review |
| `INVALID_CAMPAIGN_STATUS_TRANSITION` | 409 | Requested status transition is not allowed |
| `CREATIVE_ALREADY_APPROVED` | 409 | Creative has already been approved |
| `NO_PRIMARY_CREATIVE` | 422 | Campaign must have a primary creative before activation |
| `BUDGET_EXCEEDED` | 422 | Daily budget exceeds maximum allowed amount |
| `INVALID_DATE_RANGE` | 422 | Start date must be before end date |
| `VENDOR_NOT_FOUND` | 404 | Vendor account does not exist |
| `CAMPAIGN_NOT_FOUND` | 404 | Campaign does not exist |
| `CREATIVE_NOT_FOUND` | 404 | Creative asset does not exist |
| `LEAD_NOT_FOUND` | 404 | Lead does not exist |
| `FRAUD_SIGNAL_NOT_FOUND` | 404 | Fraud signal does not exist |
| `DUPLICATE_DIRECTORY_ENTRY` | 409 | Vendor is already in planner's directory |
| `VENDOR_NOT_IN_DIRECTORY` | 404 | Vendor is not in planner's directory |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests. Please retry after some time |
| `INTERNAL_SERVER_ERROR` | 500 | An unexpected server error occurred |

### Error Response Examples

**Invalid Token:**

```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Authentication token is invalid or expired"
  },
  "status": 401
}
```

**Insufficient Permissions:**

```json
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "You do not have permission to access this resource"
  },
  "status": 403
}
```

**Validation Error:**

```json
{
  "error": {
    "code": "INVALID_REQUEST_BODY",
    "message": "Request validation failed",
    "details": {
      "daily_budget": "Must be a positive number",
      "campaign_name": "Cannot be empty"
    }
  },
  "status": 422
}
```

**Status Transition Error:**

```json
{
  "error": {
    "code": "CAMPAIGN_NOT_DRAFT",
    "message": "Cannot update campaign - only draft campaigns can be modified",
    "details": {
      "campaign_id": "camp_5a8f2b1c9d3e7f2a",
      "current_status": "pending_review"
    }
  },
  "status": 409
}
```

---

## Common Patterns

### Pagination

List endpoints support cursor-based pagination using `limit` and `skip` parameters.

**Example Request:**

```bash
GET /portal/ads/campaigns?limit=20&skip=0
```

**Example Response Structure:**

```json
{
  "campaigns": [...],
  "total": 150,
  "limit": 20,
  "skip": 0
}
```

To get the next page, use `skip=20`. To calculate the next skip value: `skip_next = skip + limit`.

### Campaign Creation Workflow

1. Create campaign in draft status
2. Create one or more creatives
3. Designate one creative as primary (required)
4. Submit campaign for review
5. Admin reviews and approves/rejects
6. If approved, campaign becomes active
7. Monitor campaign performance via stats endpoints

### Lead Generation Workflow

1. Planner views sponsored cards via `/planner/ads/sponsored-cards`
2. Planner either adds vendor to directory or sends quote request
3. Vendor receives lead notification
4. Vendor contacts planner (external communication)
5. Lead status can be updated to "contacted" or "converted"

### Admin Review Workflow

1. Vendor submits campaign (status: pending_review)
2. Admin retrieves review queue via `/admin/ads/campaigns/review`
3. Admin approves, rejects, or requests changes
4. If approved, campaign becomes active
5. If changes requested, campaign reverts to draft for vendor revision
6. Vendor resubmits when ready
7. Admin reviews again and provides final decision

---

## Rate Limiting

API endpoints are rate-limited to prevent abuse. Clients should implement exponential backoff when receiving 429 responses.

**Rate Limits:**

- 100 requests per minute per API token
- 1000 requests per hour per API token

**Rate Limit Headers:**

Responses include the following headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1626873600
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-20 | Initial API documentation |

---

## Support

For API support and issues, contact: api-support@weddingapp.com

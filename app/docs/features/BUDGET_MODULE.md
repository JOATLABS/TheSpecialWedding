# Budget Management Module

## Overview

The Budget Management Module is a comprehensive financial tracking system for wedding planning. It gives planners an at-a-glance view of category performance, real-time payment activity, and vendor quote management with tooling designed around a translucent “glass” aesthetic to match the broader SaaS design language.

## Module Components (February 2025 status)

### 1. Budget Categories – **Implemented**
- Create and manage spending categories (Flowers, Photography, Venue, etc.)
- Set budgeted amounts and priorities
- Track actual spending vs. budget with animated progress bars
- Filter by payment status, search by keyword, and sort by priority, spend, or allocation

### 2. Payment Tracking – **Implemented**
- Record payments directly from each category card via the glassmorphic modal
- Capture vendor, amount, payment method, date, receipts, and internal notes
- Automatically update category actual spend, payment status, and dashboard analytics
- Review all payments in the right-rail history panel with live filters and refresh controls

### 3. Vendor Quotes – **Implemented**
- Create professional quotes for clients
- Manage vendor information
- Track quote status (draft, sent, accepted, rejected)
- Generate downloadable quotes (PDF tooling still pending)

### 4. Budget Templates – **Implemented**
- Pre-built templates can be listed, filtered by wedding style, and applied to weddings with a single action
- Planners can craft glass-styled custom templates, define guest ranges, budget targets, and percentage allocations with inline validation, then decide whether to share them globally
- Category authoring enforces unique names, priority levels, and 100% allocation before persisting to the API-backed `POST /admin/budget/templates` endpoint

## File Structure

```
/app/admin/budget/
├── page.tsx                    # Main budget dashboard with categories + payment timeline
├── quotes/
│   └── page.tsx               # Quote management page
├── templates/
│   └── page.tsx               # Budget template management
└── /components/budget/
    ├── BudgetSummaryCard.tsx  # Overall budget summary
    ├── BudgetCategoryCard.tsx # Individual category cards
    ├── PaymentHistoryPanel.tsx # Payment history and analytics rail
    ├── RecordPaymentModal.tsx  # Payment recording modal
    ├── QuoteModal.tsx         # Quote creation/editing
    └── CreateTemplateModal.tsx # Custom template creation modal
```

## Features

### Budget Dashboard

**URL**: `/admin/budget`

**Highlights**:
- Wedding selection dropdown with planner-access guard rails
- Budget summary card showing total budget, spent, remaining, and variance
- Category grid with search, status filtering, and priority/budget sorting
- Category actions: edit, delete, and **Record Payment** (opens the modal)
- Export buttons for PDF and Excel financial reports
- Right-rail payment history panel featuring quick stats, filtering, and receipt links

### Payment System

**Payment Recording Modal**
- Triggered from any category card’s **Record Payment** button
- Previews the category’s budgeted, spent, and remaining amounts in a frosted glass info bar
- Required fields: Amount, Payment Method, Date
- Optional fields: Vendor name, status (completed/pending/failed), receipt URL, description, internal notes
- Prevents zero/negative amounts and surfaces inline validation errors
- Persists payments through `POST /admin/budget/category/{category_id}/payment` and refreshes the dashboard on success

**Payment History Panel**
- Resides on the right of the dashboard to provide continuous visibility into transactions
- Displays aggregate totals (recorded, cleared, pending) and the most recent payment metadata
- Supports search plus category, method, and status filters
- Refresh button re-fetches data from `GET /admin/weddings/{wedding_id}/payments`
- Each list item surfaces vendor context, notes, and a receipt link when available

### Quote Management

**URL**: `/admin/budget/quotes`

**Features**:
- Create professional quotes for clients
- Vendor database with contact information
- Quote line items with quantities and prices
- Status tracking (Draft, Sent, Accepted, Rejected)
- PDF generation (planned)

### Budget Templates

**URL**: `/admin/budget/templates`

**Current Features**:
- Pre-configured budget templates that can be applied to a wedding with guided total budget entry
- Accessible "Create Custom Template" modal with Apple glass styling, inline validation, and dynamic category management
- API-backed persistence through `POST /admin/budget/templates` with optional team-wide sharing controls

**Outstanding Work**:
- Template duplication and in-place editing workflows for existing templates
- Percentage presets that auto-balance categories as allocations shift
- Migration tooling to promote private templates into organisation-wide defaults with approval steps

## User Guide

### Setting Up a Budget

1. **Create Budget Categories**
   - Navigate to the Budget page
   - Select a wedding
   - Click **Add Category**
   - Enter name, description, and budgeted amount
   - Set priority level (1–5)

2. **Use a Template** (Optional)
   - Go to Budget Templates
   - Select a template
   - Apply to wedding
   - Adjust amounts as needed

### Recording Payments

1. Click **Record Payment** on the relevant category card
2. Review the pre-filled budget metrics at the top of the modal
3. Enter the payment amount, method, and date (required) plus any vendor details, receipts, or notes
4. Submit to persist the payment; the modal closes on success and the dashboard refreshes automatically
5. Re-open the modal if you need to log additional instalments for the same category

### Viewing Payment History

1. Select a wedding to load the dashboard and payment rail
2. Use the search box or dropdown filters (category, method, status) to focus the list
3. Review totals in the metrics panel and scroll the history for detailed context
4. Click **Refresh** after back-office adjustments to fetch the latest payments

### Creating Quotes

1. Navigate to Quotes
   - Go to Budget → Quotes
   - Click **Create Quote**

2. Fill Quote Details
   - Select or add vendor
   - Add line items
   - Set terms and conditions
   - Save as draft or send

## API Endpoints

### Budget Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/weddings/{wedding_id}/budget` | Get budget summary and categories |
| POST | `/admin/weddings/{wedding_id}/budget/category` | Create new category |
| PUT | `/admin/budget/category/{id}` | Update category |
| DELETE | `/admin/budget/categories/{id}` | Delete category |

### Payments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin/budget/category/{id}/payment` | Record payment |
| GET | `/admin/weddings/{wedding_id}/payments` | Get payment history |

### Quotes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/weddings/{wedding_id}/vendor-quotes` | Get quotes |
| POST | `/admin/weddings/{wedding_id}/vendor-quotes` | Create quote |
| PUT | `/admin/vendor-quotes/{id}/status` | Update quote status |
| DELETE | `/admin/vendor-quotes/{id}` | Delete quote |

### Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/budget/templates` | Get all templates |
| POST | `/admin/budget/templates` | Create a new custom template |
| POST | `/admin/weddings/{wedding_id}/budget/apply-template` | Apply template |
| PUT | `/admin/budget/templates/{id}` | Update template (roadmap) |
| DELETE | `/admin/budget/templates/{id}` | Delete template (roadmap) |

## Data Models

### BudgetCategory

```typescript
interface BudgetCategory {
  _id: string;
  wedding_id: string;
  name: string;
  description?: string;
  budgeted_amount: number;
  actual_spent: number;
  remaining_amount: number;
  percentage_of_total: number;
  priority: number;
  payments?: PaymentRecord[];
  created_at: string;
  updated_at: string;
}
```

### PaymentRecord

```typescript
interface PaymentRecord {
  id: string;
  category_id: string;
  vendor_name?: string;
  amount: number;
  payment_method: 'cash' | 'check' | 'card' | 'transfer';
  payment_date: string;
  description?: string;
  receipt_url?: string;
  status: 'pending' | 'completed' | 'failed';
  notes?: string;
  created_at: string;
  category_name?: string;
}
```

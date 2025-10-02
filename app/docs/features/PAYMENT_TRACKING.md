# Payment Tracking System Documentation

## Implementation Status: ✅ Implemented (February 2025)

The payment tracking system is live across the admin budget experience. Planners can log payments from any budget category, capture detailed vendor context, and review a searchable transaction history without leaving the dashboard. The workflow follows the Apple glass design fundamentals in use throughout the SaaS product, delivering a frosted, layered interface with clear hierarchy and accessible controls.

## Quick Start Guide

### For Wedding Planners (current behaviour)

1. **Access the Budget Module**
   - Log into the admin dashboard
   - Navigate to **Budget** from the sidebar menu
   - Select the wedding you want to manage

2. **Record a Payment**
   - Click **Record Payment** on the relevant category card
   - Enter the amount, method, and date (all required)
   - Optionally add vendor name, receipt URL, description, or internal notes
   - Save the form to update totals and payment status instantly

3. **Review Payment History**
   - Use the right-rail history panel to browse recorded payments
   - Filter by category, payment method, or status, or search by vendor/notes
   - Click receipt links to view supporting documentation in a new tab

### For Developers

1. **Key Files**
   - Frontend:
     - `/app/admin/budget/page.tsx` – orchestrates category management, payment modal, and history panel
     - `/app/components/budget/RecordPaymentModal.tsx` – handles payment form UX, validation, and submission
     - `/app/components/budget/PaymentHistoryPanel.tsx` – renders metrics, filters, and the scrollable payment list
     - `/app/services/budgetApi.ts` – exposes `recordPayment` and `getPaymentHistory`
   - Backend:
     - `/app/api/budget.py` – provides the payment endpoints
     - `/app/services/budget_service.py` – persists payments and updates category spend summaries

2. **Running Locally**
   ```bash
   # Start backend (FastAPI + MongoDB)
   docker-compose up -d

   # Start frontend (Next.js)
   npm run dev

   # Access at http://localhost:3000/admin/budget
   ```

## Features Overview (planned vs current)

### Delivered Functionality
- **Payment Recording**: Record vendor payments with amount, method, date, status, receipt link, and internal notes.
- **Validation & Accessibility**: Inline validation guards against invalid amounts/dates and provides focus-visible controls that meet accessibility guidelines.
- **Real-time Updates**: Successful payments immediately refresh the category grid, budget summary, and payment rail so totals stay consistent.
- **Payment History**: Filterable, searchable list with aggregate metrics (recorded, cleared, pending) and quick receipt access.
- **Multi-tenant Security**: Endpoints enforce planner access via existing authentication middleware.

### Remaining Enhancements
- **CSV Export**: Dedicated payment CSV export is still a roadmap item; financial exports currently cover the overall budget report.
- **Inline Editing**: Editing or deleting individual payments is not yet supported and should be scoped separately.
- **Automated Alerts**: Payment-triggered notifications are tracked under the alerting/notifications roadmap and not part of this delivery.

## System Architecture

### Data Flow

```
Planner Action → RecordPaymentModal → budgetApi.recordPayment → POST /admin/budget/category/{id}/payment → MongoDB payment_records
                                                             ↓
                                                Budget service updates category actual_spent & status
                                                             ↓
                             Budget page re-fetches summary, categories, and GET /admin/weddings/{id}/payments
```

### Backend Implementation

- `POST /admin/budget/category/{category_id}/payment`
  - Validates request body against `RecordPaymentRequest`
  - Inserts a `PaymentRecord` into `payment_records`
  - Updates the category’s `actual_spent` and payment status

- `GET /admin/weddings/{wedding_id}/payments`
  - Returns all payments for the selected wedding with category name enrichment
  - Used by the payment history rail and refresh control

### Frontend Implementation

```
/app/admin/budget/
├── page.tsx
└── components/budget/
    ├── RecordPaymentModal.tsx
    ├── PaymentHistoryPanel.tsx
    └── BudgetCategoryCard.tsx
```

- `RecordPaymentModal` renders the glassmorphic form, manages validation, and submits ISO-formatted dates.
- `PaymentHistoryPanel` memoises totals, exposes filters, and renders a scrollable list with animations.
- `budgetApi.recordPayment` and `budgetApi.getPaymentHistory` abstract fetch requests, headers, and response parsing.

## Database Schema (proposed)

### payment_records

```javascript
{
  "_id": ObjectId("..."),
  "category_id": "budget_category_id",
  "vendor_name": "Flowers by Jane",
  "amount": 2500.00,
  "payment_method": "card",
  "payment_date": ISODate("2025-02-14"),
  "description": "50% deposit",
  "receipt_url": "https://drive.example.com/receipt.pdf",
  "status": "completed",
  "notes": "Balance due 30 days prior to event",
  "created_at": ISODate("2025-02-14T10:30:00Z")
}
```

### budget_categories (updated fields)

```javascript
{
  "_id": ObjectId("..."),
  "name": "Flowers",
  "budgeted_amount": 5000.00,
  "actual_spent": 2500.00,
  "payment_status": "partial",
  "payments": [
    {
      "id": "...",
      "category_id": "...",
      "amount": 2500.00,
      "payment_method": "card",
      "payment_date": ISODate("2025-02-14"),
      "status": "completed",
      "created_at": ISODate("2025-02-14T10:30:00Z")
    }
  ]
}
```

## Security Features

- Planner authentication is required for all payment endpoints; tokens are supplied through the `Authorization` header.
- The payment modal prevents injection by trimming user-supplied strings and deferring sanitisation to the backend service layer.
- Receipt links open in a new tab with `rel="noreferrer"` to avoid leaking admin context to external domains.

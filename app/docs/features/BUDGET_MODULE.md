# Budget Management Module

## Overview

The Budget Management Module is a comprehensive financial tracking system for wedding planning. It provides wedding planners with tools to manage budgets, track payments, generate quotes, and monitor spending across multiple weddings.

## Module Components (January 2025 status)

### 1. Budget Categories – **Implemented**
- Create and manage spending categories (Flowers, Photography, Venue, etc.)
- Set budgeted amounts and priorities
- Track actual spending vs. budget
- Visual progress indicators

### 2. Payment Tracking – **Not yet delivered**
- The UI currently surfaces a "Payment tracking feature coming soon" toast when planners click the button.
- `PaymentModal` and `PaymentHistory` components referenced in earlier designs are not present in the codebase.
- No API endpoints exist for recording or listing payments, so CSV export is limited to overall budget reports.

### 3. Vendor Quotes – **Implemented**
- Create professional quotes for clients
- Manage vendor information
- Track quote status (draft, sent, accepted, rejected)
- Generate downloadable quotes (PDF tooling still pending)

### 4. Budget Templates – **Partially implemented**
- Pre-built budget templates for different wedding types can be listed and applied.
- The "Create Custom Template" button has no handler and there is no template authoring API yet.
- Customisable category lists remain a roadmap item until template creation is wired up.

## File Structure

```
/app/admin/budget/
├── page.tsx                    # Main budget dashboard with tabs
├── quotes/
│   └── page.tsx               # Quote management page
├── templates/
│   └── page.tsx               # Budget template management
└── /components/budget/
    ├── BudgetSummaryCard.tsx  # Overall budget summary
    ├── BudgetCategoryCard.tsx # Individual category cards
    ├── PaymentModal.tsx       # (Planned) Payment recording form – not yet created
    ├── PaymentHistory.tsx     # (Planned) Payment history table – not yet created
    ├── QuoteModal.tsx         # Quote creation/editing
    └── TemplateModal.tsx      # Template creation/editing
```

## Features

### Budget Dashboard

**URL**: `/admin/budget`

**Features**:
- Wedding selection dropdown
- Budget summary card showing total budget, spent, and remaining
- Tabbed interface:
  - **Budget Categories**: Manage spending categories
  - **Payment History**: (Planned) Tab reserved for future payment tracking UI
- Category management with add, edit, delete
- Payment recording for each category

### Payment System (roadmap)

The payment tracking flow described in earlier drafts has not been implemented. Clicking "Record Payment" triggers an informational toast, and there is no modal or backend persistence for payments. The section below is retained to capture the intended scope once development resumes.

**Planned Features**:
- Quick payment recording from category cards
- Comprehensive payment history view
- Advanced search and filtering
- CSV export for accounting
- Real-time budget updates

**Planned Payment Fields**:
- Amount (required)
- Payment Method (required): Cash, Check, Card, Transfer
- Payment Date (required)
- Vendor Name (optional)
- Description (optional)
- Notes (optional)

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
- Pre-configured budget templates that can be applied to a wedding
- Quick setup for new weddings

**Outstanding Work**:
- Custom template creation UI and API
- Editing the category lists inside a template
- Percentage-based or fixed-amount allocation tools

## User Guide

### Setting Up a Budget

1. **Create Budget Categories**
   - Navigate to Budget page
   - Select wedding
   - Click "Add Category"
   - Enter name, description, and budgeted amount
   - Set priority level (1-5)

2. **Use a Template** (Optional)
   - Go to Budget Templates
   - Select a template
   - Apply to wedding
   - Adjust amounts as needed

### Recording Payments (future flow)

1. **From Category Card**
   - Planned: click "Record Payment" to open the payment modal
   - Planned: enter payment details and save

2. **View History**
   - Planned: a dedicated "Payment History" tab with filtering and CSV export

### Creating Quotes

1. **Navigate to Quotes**
   - Go to Budget → Quotes
   - Click "Create Quote"

2. **Fill Quote Details**
   - Select or add vendor
   - Add line items
   - Set terms and conditions
   - Save as draft or send

## API Endpoints

### Budget Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/budget/wedding/{wedding_id}` | Get budget summary and categories |
| POST | `/api/budget/category` | Create new category |
| PUT | `/api/budget/category/{id}` | Update category |
| DELETE | `/api/budget/category/{id}` | Delete category |

### Payments (planned)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/budget/category/{id}/payment` | Record payment |
| GET | `/api/weddings/{wedding_id}/payments` | Get payment history |

### Quotes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/budget/quotes/wedding/{wedding_id}` | Get quotes |
| POST | `/api/budget/quotes` | Create quote |
| PUT | `/api/budget/quotes/{id}` | Update quote |
| DELETE | `/api/budget/quotes/{id}` | Delete quote |

### Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/budget/templates` | Get all templates |
| POST | `/api/budget/templates` | Create template |
| PUT | `/api/budget/templates/{id}` | Update template |
| DELETE | `/api/budget/templates/{id}` | Delete template |

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

### PaymentRecord (planned)

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
  }
```

### Quote

```typescript
interface Quote {
  _id: string;
  wedding_id: string;
  vendor: VendorInfo;
  items: QuoteItem[];
  subtotal: number;
  tax_rate: number;
  tax_amount: number;
  discount_amount: number;
  total_amount: number;
  terms?: string;
  notes?: string;
  status: 'draft' | 'sent' | 'accepted' | 'rejected';
  valid_until?: string;
  created_at: string;
  updated_at: string;
}
```

## Security

### Access Control
- Authentication required for all endpoints
- Wedding-scoped data isolation
- Role-based permissions (Admin, Planner)

### Data Validation
- Input sanitization on all forms
- Amount validation (positive numbers only)
- Date validation (no future dates for payments)
- Wedding ownership verification

### Multi-Tenancy
- Complete data isolation between weddings
- Query filtering by wedding_id
- Cross-wedding access prevention

## Best Practices

### Budget Management
1. Set realistic budget amounts
2. Use priority levels to focus on important categories
3. Record payments immediately after making them
4. Review budget summary regularly
5. Export payment data monthly for accounting

### Payment Recording
1. Always include vendor name for tracking
2. Add descriptions for clarity
3. Keep receipts and attach when possible
4. Use consistent payment method labels
5. Verify amounts before saving

### Quote Creation
1. Include all costs upfront
2. Set reasonable validity periods
3. Clearly state terms and conditions
4. Follow up on sent quotes
5. Update status promptly

## Troubleshooting

### Common Issues

**Categories Not Saving**
- Check all required fields are filled
- Verify budget amount is positive
- Ensure wedding is selected

**Payments Not Appearing**
- Refresh the page
- Check payment date is correct
- Verify payment was saved successfully

**Export Not Working**
- Check browser download settings
- Ensure payments exist to export
- Try a different browser

### Support

For technical issues:
1. Check browser console for errors
2. Review network tab for API failures
3. Verify backend services are running
4. Contact technical support

## Future Enhancements

### Planned Features
- Receipt upload and storage
- Payment edit/delete functionality
- Bulk payment import via CSV
- Advanced budget analytics
- Client portal for budget viewing
- Integration with accounting software
- Automated payment reminders
- Budget forecasting tools

### Integration Opportunities
- QuickBooks sync
- Stripe payment processing
- Email notifications for budget alerts
- Mobile app for on-the-go tracking

---

**Module Version**: 1.0.0
**Last Updated**: January 2025
**Status**: Production Ready
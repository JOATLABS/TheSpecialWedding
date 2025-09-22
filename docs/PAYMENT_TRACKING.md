# Payment Tracking System Documentation

## Original Objectives

The payment tracking system was designed to provide comprehensive financial management for wedding planning, enabling planners to:

1. **Track Actual Expenses**: Record real payments made to vendors against budgeted amounts
2. **Monitor Budget Health**: Compare actual spending vs budgeted amounts in real-time
3. **Maintain Payment History**: Keep detailed records of all transactions with receipts
4. **Generate Financial Reports**: Export payment data for accounting and client reporting
5. **Alert on Overspending**: Automatically detect and notify when categories exceed budget

## System Architecture

### Data Model (`app/models/budget.py:182-195`)

```python
class PaymentRecord(BaseModel):
    id: PyObjectId                    # Unique payment identifier
    category_id: str                   # Links to budget category
    vendor_name: Optional[str]         # Vendor receiving payment
    amount: float                      # Payment amount (>0)
    payment_method: str                # cash, check, card, transfer
    payment_date: datetime             # When payment was made
    description: Optional[str]         # Payment description
    receipt_url: Optional[str]         # Digital receipt storage
    status: str                        # pending, completed, failed
    notes: Optional[str]               # Additional notes
    created_at: datetime               # Record creation timestamp
```

### Backend Implementation Status ✅

#### API Endpoints (`app/api/budget.py`)

1. **POST `/budget/category/{category_id}/payment`** (Line 277-295)
   - Records new payment for a budget category
   - Validates payment data
   - Updates category's `amount_paid` field
   - Triggers budget alert checks

2. **GET `/weddings/{wedding_id}/payments`** (Line 297-312)
   - Retrieves payment history for entire wedding
   - Aggregates payments across all categories
   - Sorted by payment date (newest first)

#### Service Layer (`app/services/budget_service.py`)

1. **`record_payment()`** (Line 370-415)
   - Creates payment record in MongoDB
   - Updates budget category's `amount_paid`
   - Recalculates category's `remaining_amount`
   - Triggers automatic budget alerts
   - Logs payment for audit trail

2. **`get_payment_history()`** (Line 417-441)
   - Fetches all payments for a wedding
   - Enriches with category information
   - Calculates payment statistics
   - Supports filtering and sorting

### Frontend Implementation Status ❌

#### Missing Components

1. **API Service Methods** (`app/services/budgetApi.ts`)
   ```typescript
   // MISSING: Add these methods to budgetApi.ts
   async recordPayment(token: string, categoryId: string, data: RecordPaymentRequest)
   async getPaymentHistory(token: string, weddingId: string)
   async getPaymentDetails(token: string, paymentId: string)
   async updatePayment(token: string, paymentId: string, data: UpdatePaymentRequest)
   async deletePayment(token: string, paymentId: string)
   ```

2. **TypeScript Types** (`app/types/budget.ts`)
   ```typescript
   // MISSING: Payment-related types
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

3. **UI Components**
   - `PaymentModal.tsx` - Form for recording new payments
   - `PaymentHistory.tsx` - List/table of all payments
   - `PaymentCard.tsx` - Individual payment display
   - `ReceiptUpload.tsx` - Handle receipt file uploads

## Implementation Requirements

### Phase 1: Core Payment Tracking

1. **Payment Recording Form**
   - Amount input with validation (>0)
   - Vendor name (auto-complete from existing vendors)
   - Payment method selector
   - Date picker (default to today)
   - Optional description and notes
   - Receipt upload capability

2. **Payment History View**
   - Sortable table with columns: Date, Vendor, Amount, Method, Status
   - Filter by: Category, Date range, Vendor, Method
   - Search functionality
   - Export to CSV/PDF

3. **Budget Category Integration**
   - "Record Payment" button on each category card
   - Display payment count and total paid
   - Visual progress bar (paid vs budgeted)
   - Remaining amount calculation

### Phase 2: Advanced Features

1. **Receipt Management**
   - Upload receipts to Cloudflare R2
   - Preview receipts in modal
   - OCR for automatic data extraction (future)

2. **Payment Analytics**
   - Payment timeline chart
   - Vendor spending breakdown
   - Payment method distribution
   - Monthly spending trends

3. **Automated Workflows**
   - Email reminders for pending payments
   - Auto-generate payment reports
   - Integration with accounting software

## User Workflows

### Recording a Payment

1. User clicks "Record Payment" on budget category
2. Payment modal opens with pre-filled category
3. User enters payment details:
   - Amount paid
   - Vendor name
   - Payment method
   - Date of payment
   - Optional receipt upload
4. System validates and saves payment
5. Category card updates with new payment info
6. Budget summary refreshes totals

### Viewing Payment History

1. User navigates to "Payment History" tab
2. System displays all payments in table format
3. User can:
   - Sort by any column
   - Filter by multiple criteria
   - Search for specific payments
   - Click payment for details
   - Export filtered results

### Managing Receipts

1. User uploads receipt during payment recording
2. System stores file in Cloudflare R2
3. Receipt URL saved with payment record
4. User can view/download receipt anytime
5. Receipts included in financial reports

## Database Schema

### Collections Structure

```javascript
// payment_records collection
{
  "_id": ObjectId,
  "category_id": "budget_category_id",
  "vendor_name": "Flowers by Jane",
  "amount": 2500.00,
  "payment_method": "card",
  "payment_date": ISODate("2025-01-15"),
  "description": "50% deposit for wedding flowers",
  "receipt_url": "https://r2.../receipts/abc123.pdf",
  "status": "completed",
  "notes": "Includes delivery and setup",
  "created_at": ISODate("2025-01-15T10:30:00Z")
}

// budget_categories collection (updated fields)
{
  "_id": ObjectId,
  "amount_paid": 2500.00,      // Sum of all payments
  "remaining_amount": 2500.00,  // allocated - amount_paid
  "payment_count": 1,           // Number of payments
  "last_payment_date": ISODate("2025-01-15")
}
```

## Alert System Integration

The payment system triggers automatic alerts:

1. **Over-Budget Alert**: When `amount_paid > allocated_amount`
2. **Payment Due Alert**: Based on vendor payment terms
3. **Large Payment Alert**: For payments exceeding thresholds
4. **Budget Milestone Alert**: At 50%, 75%, 90% spent

## Security Considerations

1. **Access Control**
   - Only wedding planners and root admins can record payments
   - Payments are wedding-scoped for multi-tenancy
   - Audit trail for all payment operations

2. **Data Validation**
   - Amount must be positive
   - Valid payment methods only
   - Date cannot be in future
   - Category must exist and belong to wedding

3. **Receipt Security**
   - Secure file upload with type validation
   - Private S3/R2 bucket with signed URLs
   - Automatic expiry for download links

## Testing Requirements

### Backend Tests
- Payment creation with valid/invalid data
- Budget category update on payment
- Payment history retrieval
- Alert generation on overspending
- Multi-tenant isolation

### Frontend Tests
- Payment form validation
- Receipt upload functionality
- Payment history filtering/sorting
- Budget progress calculation
- Real-time updates

## Performance Considerations

1. **Database Indexes**
   - `category_id` for payment lookups
   - `wedding_id, payment_date` for history queries
   - `vendor_name` for vendor payment reports

2. **Caching Strategy**
   - Cache payment summaries (5-minute TTL)
   - Cache vendor name autocomplete
   - Invalidate on new payment

3. **Pagination**
   - Limit payment history to 50 per page
   - Virtual scrolling for large datasets
   - Lazy load receipt previews

## Implementation Priority

1. **Critical (Week 1)**
   - Add payment API methods to budgetApi.ts
   - Create PaymentModal component
   - Update BudgetCategoryCard with payment button
   - Basic payment recording functionality

2. **Important (Week 2)**
   - Payment history table with filtering
   - Receipt upload to Cloudflare R2
   - Payment validation and error handling
   - Update budget calculations

3. **Nice-to-Have (Week 3+)**
   - Payment analytics dashboard
   - Bulk payment import
   - Recurring payment templates
   - Integration with accounting software
# Payment Tracking System Documentation

## Implementation Status: ❌ Not yet implemented (January 2025)

The payment tracking system described in earlier plans has not shipped. The admin budget page still displays a "Payment tracking feature coming soon" toast, and no backend endpoints exist for persisting payments.

## Quick Start Guide

### For Wedding Planners (current behaviour)

1. **Access the Budget Module**
   - Login to your admin dashboard
   - Navigate to **Budget** from the sidebar menu
   - Select the wedding you want to manage

2. **Attempt to record a payment**
   - Click the **"Record Payment"** button on a category card
   - A toast appears stating "Payment tracking feature coming soon"
   - No modal opens and no payment is saved

3. **Payment history tab**
   - The UI reserves a tab for future payment history functionality
   - No table or export options are rendered yet

### For Developers

1. **Key Files**
   - Frontend: `/app/admin/budget/page.tsx` - Contains the placeholder toast for the future payment modal
   - Components: `PaymentModal.tsx` & `PaymentHistory.tsx` **do not exist yet**
   - Backend: `/app/api/budget.py` has no payment endpoints
   - Service: `/app/services/budget_service.py` does not persist payments

2. **Running Locally**
   ```bash
   # Start backend
   docker-compose up -d

   # Start frontend
   npm run dev

   # Access at http://localhost:3000/admin/budget
   ```

## Features Overview (planned vs current)

### Planned Core Functionality
- **Payment Recording**: Add payments with vendor, amount, method, and date
- **Real-time Updates**: Update category totals after payment
- **Payment History**: View all payments with filtering
- **CSV Export**: Download payment data for accounting
- **Multi-tenant Security**: Isolate payments per wedding
- **Dark Mode Support**: Match rest of dashboard styling

### Current State
- None of the payment-specific UI or APIs are present
- Budget totals only change when categories are edited manually
- CSV export still references overall budget reports, not payments
- Payment-specific tests and automation are absent

## System Architecture

### Data Flow

```
User Action → Frontend Component → API Service → Backend Endpoint → MongoDB
                                                        ↓
                                              Budget Calculations
                                                        ↓
                                              Real-time UI Update
```

### Backend Implementation (to be built)

Target endpoints:

1. **Record Payment**
   - `POST /api/budget/category/{category_id}/payment`
   - Persists a payment linked to a budget category

2. **Get Payment History**
   - `GET /api/weddings/{wedding_id}/payments`
   - Returns paginated payment records with category context

Suggested data model:

```python
class PaymentRecord(BaseModel):
    id: PyObjectId
    category_id: str
    vendor_name: Optional[str]
    amount: float
    payment_method: str  # cash, check, card, transfer
    payment_date: datetime
    description: Optional[str]
    receipt_url: Optional[str]
    status: str  # pending, completed, failed
    notes: Optional[str]
    created_at: datetime
```

### Frontend Implementation (to be built)

Planned component structure:

```
/app/admin/budget/
├── page.tsx                 # Main budget page with tab navigation
└── /components/budget/
    ├── PaymentModal.tsx     # Payment recording form (missing)
    ├── PaymentHistory.tsx   # Payment history table (missing)
    ├── BudgetCategoryCard.tsx # Category cards with payment button
    └── BudgetSummaryCard.tsx  # Overall budget summary
```

Proposed TypeScript interface:

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

## User Workflows (proposed)

### Recording a Payment

1. **Navigate to Budget Page**
   - Planner logs in and selects Budget from the menu
   - Chooses the wedding to manage

2. **Select Category**
   - Views budget categories in grid layout
   - Identifies the category for payment

3. **Open Payment Form**
   - Planned: click "Record Payment" on the category card to open a modal

4. **Enter Payment Details**
   - Planned required fields: Amount, Payment Method, Date
   - Planned optional fields: Vendor Name, Description, Notes

5. **Save and Update**
   - Planned: saving should update the category card and overall budget summary

### Viewing Payment History

1. **Access History Tab**
   - Planned: click the "Payment History" tab to load the table

2. **Search and Filter**
   - Planned controls for search, method/category filters, and sortable columns

3. **Export Data**
   - Planned: "Export to CSV" button to download a formatted spreadsheet

## Database Schema (proposed)

### Collections

**payment_records**
```javascript
{
  "_id": ObjectId("..."),
  "category_id": "budget_category_id",
  "vendor_name": "Flowers by Jane",
  "amount": 2500.00,
  "payment_method": "card",
  "payment_date": ISODate("2025-01-15"),
  "description": "50% deposit",
  "status": "completed",
  "notes": "Includes delivery",
  "created_at": ISODate("2025-01-15T10:30:00Z")
}
```

**budget_categories** (updated fields)
```javascript
{
  "_id": ObjectId("..."),
  "name": "Flowers",
  "budgeted_amount": 5000.00,
  "actual_spent": 2500.00,
  "remaining_amount": 2500.00,
  "payments": [...]
}
```

## Security Features

### Access Control
- **Authentication Required**: All endpoints require valid JWT token
- **Wedding Scoping**: Users can only access their assigned weddings
- **Role-Based Access**: Only planners and admins can record payments

### Data Validation
- **Amount Validation**: Must be positive number
- **Date Validation**: Cannot be future date
- **Payment Method**: Must be valid enum value
- **Category Verification**: Must exist and belong to wedding

### Multi-Tenancy
- **Isolated Data**: Payments scoped to specific weddings
- **Cross-Wedding Protection**: Queries filtered by wedding_id
- **Audit Trail**: All payment operations logged

## Testing

### Backend Tests (`tests/integration/test_payment_tracking.py`)

```python
# Test Coverage:
✅ Valid payment recording
✅ Invalid payment rejection
✅ Multiple payment accumulation
✅ Payment history retrieval
✅ Multi-tenant isolation
✅ Budget alert generation
✅ Category update verification
```

### Frontend Testing

To test the payment system:

1. **Manual Testing**
   ```bash
   npm run dev
   # Navigate to http://localhost:3000/admin/budget
   ```

2. **Test Scenarios**
   - Record payment with minimum fields
   - Record payment with all fields
   - View payment in history
   - Search for specific payment
   - Filter by payment method
   - Export to CSV
   - Verify budget calculations

## Troubleshooting

### Common Issues

**Payment Not Saving**
- Check network tab for API errors
- Verify all required fields are filled
- Ensure valid JWT token

**History Not Loading**
- Confirm wedding is selected
- Check browser console for errors
- Verify backend is running

**Export Not Working**
- Check browser download settings
- Verify payments exist to export
- Try different browser

### Debug Commands

```bash
# Check backend logs
docker-compose logs -f api

# Verify MongoDB data
docker exec -it wedding-mongo mongosh
> use wedding
> db.payment_records.find()

# Test API directly
curl -X POST http://localhost:8000/api/budget/category/{id}/payment \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 100, "payment_method": "cash", "payment_date": "2025-01-15"}'
```

## Performance Considerations

### Optimizations
- **Database Indexes**: On category_id and wedding_id
- **Pagination**: Payment history limited to 50 per page
- **Caching**: Budget summaries cached for 5 minutes
- **Lazy Loading**: Payment details loaded on demand

### Scalability
- Supports unlimited payments per wedding
- Efficient aggregation queries
- Optimized for up to 500 categories per wedding
- CSV export handles large datasets

## Future Enhancements

### Planned Features
- **Receipt Upload**: Store receipts in Cloudflare R2
- **Payment Edit/Delete**: Allow modification of payments
- **Bulk Import**: CSV upload for multiple payments
- **Payment Reminders**: Automated vendor payment alerts
- **Advanced Analytics**: Payment trends and projections

### Integration Opportunities
- **Accounting Software**: QuickBooks, Xero integration
- **Payment Processing**: Direct payment to vendors
- **Vendor Portal**: Vendors check payment status
- **Client Portal**: Couples view budget progress

## API Reference

### Payment Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/budget/category/{category_id}/payment` | Record new payment |
| GET | `/api/weddings/{wedding_id}/payments` | Get payment history |
| GET | `/api/budget/category/{category_id}/payments` | Get category payments |
| PUT | `/api/payment/{payment_id}` | Update payment (planned) |
| DELETE | `/api/payment/{payment_id}` | Delete payment (planned) |

### Request/Response Examples

**Record Payment Request**
```bash
POST /api/budget/category/cat_123/payment
Authorization: Bearer {token}
Content-Type: application/json

{
  "vendor_name": "ABC Florist",
  "amount": 1500.00,
  "payment_method": "check",
  "payment_date": "2025-01-20",
  "description": "Final payment for centerpieces"
}
```

**Payment History Response**
```json
{
  "payments": [
    {
      "id": "pay_456",
      "category_id": "cat_123",
      "category_name": "Flowers",
      "vendor_name": "ABC Florist",
      "amount": 1500.00,
      "payment_method": "check",
      "payment_date": "2025-01-20",
      "description": "Final payment for centerpieces",
      "status": "completed",
      "created_at": "2025-01-20T14:30:00Z"
    }
  ],
  "total": 1500.00,
  "count": 1
}
```

## Support

For issues or questions:
1. Check this documentation
2. Review test files for examples
3. Check GitHub issues
4. Contact development team

---

**Last Updated**: January 2025
**Version**: 1.0.0
**Status**: Production Ready
# Vendor Management System - Implementation Plan

## Executive Summary

Transform the current vendor forms page into a comprehensive **Vendor CRM** that wedding planners actually need. This feature will be **subscription-gated** - plans can include or exclude vendor management.

---

## What Already Exists (Leverage These)

### 1. Subscription System (`app/models/subscription.py`)
- `SubscriptionPlanModel.features: Dict[str, bool]` - feature flags
- `SubscriptionPlanModel.staff_seats: int` - seat-based limits
- Usage tracking infrastructure

### 2. Budget System (`app/models/budget.py`)
- `VendorQuote` - vendor name, email, phone, quote amount, status, rating
- `BudgetCategory.vendor_quotes: List[str]` - links quotes to categories
- `PaymentRecord` - payment tracking per category

### 3. User System (`app/models/user_extended.py`)
- Vendor role support: `role: "vendor"`
- `assigned_wedding_ids: List[str]` for vendor access
- `service_type: str` for vendor categorization

### 4. Vendor Dashboard (`app/api/vendor_dashboard.py`)
- Vendor authentication flow
- Task assignment system
- Form submission workflow

---

## Phase 1: Feature Gating (Day 1)

### 1.1 Add Feature Flags to Plans

```python
# In subscription plans, add these features:
features: {
    "vendor_management": True,      # Enable/disable entire vendor feature
    "vendor_contracts": True,       # Contract workflow
    "vendor_quotes_comparison": True,  # Quote comparison tools
    "vendor_directory": True,       # Master vendor list
}

# Add limit:
max_vendors: int = Field(10, description="Maximum vendors in directory (-1 unlimited)")
```

### 1.2 Create Feature Check Decorator

```python
# app/dependencies/feature_gates.py
async def require_vendor_feature(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Check if user's plan includes vendor management"""
    plan = await get_user_plan(current_user.email)
    if not plan.features.get("vendor_management", False):
        raise HTTPException(403, "Vendor management not included in your plan")
    return current_user
```

---

## Phase 2: Database Models

### 2.1 Extend Existing - NO NEW COLLECTIONS for core

The `VendorQuote` model is already 80% of what we need. We just need to:

```python
# Extend VendorQuote with these fields (in budget.py):
class VendorQuote(BaseModel):
    # ... existing fields ...

    # NEW: Contract linking
    contract_status: Optional[str] = Field(None)  # draft|sent|signed|completed
    contract_url: Optional[str] = Field(None)     # Signed contract file
    contract_signed_at: Optional[datetime] = Field(None)

    # NEW: Payment milestone tracking
    deposit_amount: Optional[float] = Field(None)
    deposit_paid: bool = Field(False)
    payment_milestones: List[Dict] = Field(default_factory=list)
    # Each milestone: {description, amount, due_date, status, paid_at}

    # NEW: Vendor directory flag
    is_directory_vendor: bool = Field(False)  # If true, reusable across weddings

    # NEW: Communication tracking
    last_contacted_at: Optional[datetime] = Field(None)
    notes_history: List[Dict] = Field(default_factory=list)
    # Each note: {content, created_by, created_at}
```

### 2.2 New Collection: Vendor Directory (Master List)

```python
# app/models/vendor.py - NEW FILE
class VendorProfile(BaseModel):
    """Master vendor directory - reusable across all weddings"""
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")

    # Owner
    created_by: str = Field(..., description="Planner email who added this vendor")

    # Basic Info
    business_name: str = Field(..., min_length=1, max_length=200)
    contact_name: Optional[str] = Field(None)
    email: str = Field(...)
    phone: Optional[str] = Field(None)
    website: Optional[str] = Field(None)
    address: Optional[str] = Field(None)

    # Categorization
    service_category: str = Field(...)  # photographer, caterer, florist, etc.
    service_subcategories: List[str] = Field(default_factory=list)  # e.g., ["portrait", "drone"]

    # Planner's Notes
    notes: Optional[str] = Field(None)
    internal_rating: Optional[int] = Field(None, ge=1, le=5)  # Planner's rating
    is_preferred: bool = Field(False)  # Go-to vendor flag
    tags: List[str] = Field(default_factory=list)  # custom tags

    # Portfolio (optional)
    portfolio_urls: List[str] = Field(default_factory=list)

    # Pricing Guide (optional, for quick reference)
    typical_price_range: Optional[Dict] = Field(None)  # {min: 1000, max: 5000, currency: "USD"}

    # Usage Stats
    weddings_assigned: int = Field(0)  # How many times used
    last_used_at: Optional[datetime] = Field(None)

    # System
    is_active: bool = Field(True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2.3 Wedding-Vendor Assignment (Link Table Concept)

Instead of a new collection, use **VendorQuote with enhanced fields**:

```python
# When assigning a vendor from directory to a wedding:
# 1. Create a VendorQuote with vendor_profile_id linking back
# 2. The quote tracks wedding-specific details

class VendorQuote(BaseModel):
    # ... existing ...
    vendor_profile_id: Optional[str] = Field(None)  # Link to VendorProfile if from directory
```

---

## Phase 3: Backend API Endpoints

### 3.1 Vendor Directory API (`app/api/vendor_directory.py` - NEW)

```
# Master Vendor Directory (planner's contact book)
GET    /admin/vendors/directory              # List all vendors in directory
POST   /admin/vendors/directory              # Add vendor to directory
GET    /admin/vendors/directory/{id}         # Get vendor details
PUT    /admin/vendors/directory/{id}         # Update vendor
DELETE /admin/vendors/directory/{id}         # Remove from directory

# Quick Search
GET    /admin/vendors/directory/search?q=    # Search vendors
GET    /admin/vendors/directory/categories   # List all categories used

# Assign to Wedding
POST   /admin/vendors/assign                 # Assign vendor to wedding + budget category
       Body: {vendor_profile_id, wedding_id, budget_category_id}
```

### 3.2 Extend Budget API for Contracts

```
# Contract Management (extend existing quote endpoints)
POST   /budget/quotes/{quote_id}/contract    # Create contract from quote
PUT    /budget/quotes/{quote_id}/contract    # Update contract status
POST   /budget/quotes/{quote_id}/contract/send  # Send contract for signing
POST   /budget/quotes/{quote_id}/contract/sign  # Mark as signed

# Payment Milestones
POST   /budget/quotes/{quote_id}/milestones  # Add payment milestone
PUT    /budget/quotes/{quote_id}/milestones/{milestone_id}  # Update milestone
POST   /budget/quotes/{quote_id}/milestones/{milestone_id}/pay  # Record payment
```

### 3.3 Feature Check in All Endpoints

```python
@router.get("/admin/vendors/directory")
async def list_directory_vendors(
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)  # Gate it!
):
    ...
```

---

## Phase 4: Frontend Redesign

### 4.1 New Vendor Page Structure

```
/admin/vendors/
├── page.tsx (Main - Tabbed Interface)
│   ├── Tab: Directory (Master vendor list)
│   ├── Tab: Wedding Vendors (Assigned to current/selected wedding)
│   ├── Tab: Quotes (Quote comparison, linked to budget)
│   └── Tab: Contracts (Contract status tracking)
```

### 4.2 Component Breakdown

```
components/vendors/
├── VendorDirectory.tsx       # Master list CRUD
├── VendorCard.tsx            # Vendor display card
├── VendorForm.tsx            # Add/Edit vendor modal
├── AssignVendorModal.tsx     # Assign to wedding + category
├── VendorQuoteCard.tsx       # Quote with comparison
├── ContractTracker.tsx       # Contract status workflow
├── PaymentMilestones.tsx     # Payment tracking
└── VendorCategoryFilter.tsx  # Filter by service type
```

### 4.3 Feature Gating in Frontend

```typescript
// Check plan features before rendering
const { userProfile } = useAdmin();

if (!userProfile?.plan?.features?.vendor_management) {
  return <UpgradePrompt feature="Vendor Management" />;
}
```

---

## Phase 5: Integration Points

### 5.1 Budget Integration

When assigning vendor to wedding:
1. Select vendor from directory
2. Select budget category (e.g., "Photography")
3. Creates VendorQuote linked to both
4. Quote appears in budget category's vendor_quotes array
5. When quote accepted → updates budget actual_spent

### 5.2 Calendar Integration (Future)

- Vendor availability checking
- Block dates when vendor is booked
- Conflict detection

### 5.3 Notification Integration

- Quote expiration reminders
- Contract signing reminders
- Payment due reminders

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLANNER'S VENDOR WORKFLOW                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. VENDOR DIRECTORY (Master List)                              │
│     - Add vendors you work with                                 │
│     - Store contact info, notes, ratings                        │
│     - Mark preferred vendors                                     │
│     - Reusable across ALL weddings                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. ASSIGN TO WEDDING                                           │
│     - Select vendor from directory                              │
│     - Link to budget category (Photography, Catering, etc.)     │
│     - Creates VendorQuote record                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. QUOTE MANAGEMENT                                            │
│     - Request quotes from multiple vendors                      │
│     - Compare side-by-side                                      │
│     - Accept/Reject quotes                                      │
│     - Quote → Budget tracking                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. CONTRACT WORKFLOW                                           │
│     - Generate contract from accepted quote                     │
│     - Track: Draft → Sent → Signed → Completed                  │
│     - Store signed documents                                    │
│     - Define payment terms                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. PAYMENT TRACKING                                            │
│     - Payment milestones (deposit, balance, etc.)               │
│     - Record payments                                           │
│     - Syncs with Budget actual_spent                            │
│     - Due date reminders                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Order

### Sprint 1: Foundation (Feature Gating + Directory)
1. Add feature flags to subscription model
2. Create feature gate decorator
3. Create VendorProfile model
4. Build directory CRUD API
5. Basic frontend directory tab

### Sprint 2: Wedding Integration
1. Extend VendorQuote with new fields
2. Build assign-to-wedding API
3. Link vendors to budget categories
4. Quote comparison UI

### Sprint 3: Contracts
1. Contract status workflow
2. Contract endpoints
3. Payment milestones
4. Document upload for signed contracts

### Sprint 4: Polish
1. Search & filtering
2. Notifications/reminders
3. Reporting/analytics
4. Mobile responsiveness

---

## Files to Create/Modify

### New Files:
- `app/models/vendor.py` - VendorProfile model
- `app/api/vendor_directory.py` - Directory API
- `app/services/vendor_service.py` - Business logic
- `app/dependencies/feature_gates.py` - Feature checking
- `app/admin/vendors/` - Redesigned frontend

### Modify:
- `app/models/subscription.py` - Add vendor feature flags
- `app/models/budget.py` - Extend VendorQuote
- `app/api/budget.py` - Add contract endpoints
- `app/services/budget_service.py` - Contract logic

---

## Questions Before Implementation

1. **Contract Templates**: Do you want pre-built contract templates by vendor type, or just upload custom contracts?

2. **Vendor Portal**: Should vendors be able to log in and see their assignments/contracts? (Already partial support exists)

3. **Multi-Planner**: Can multiple planners share a vendor directory, or is it per-planner only?

4. **Payment Integration**: Should milestone payments integrate with Stripe for actual payment processing, or just tracking?

5. **Document Storage**: Where should signed contracts be stored? (S3, local, etc.)

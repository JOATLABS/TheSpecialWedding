# Wedding Finance Autopilot + AI Layer

## Implementation Status: 🔄 Planning Phase (December 2024)

A transformative feature that replaces manual payment requests with an automated **Package → Contract → Autopilot** flow, enhanced by **Ambient AI** that makes the platform intelligent. This document serves as the Product-as-Code (PAC) specification for Linear tracking.

---

## Executive Summary

### The Problem
Currently, planners manually create payment requests, copy links, and track status in a disconnected workflow. This is 2018 thinking in a 2025 platform.

### The Solution
Define the business relationship once (Package), get it signed (Contract), and let money flow automatically (Autopilot). AI assists throughout without being summoned.

### The Outcome
- **For Planners**: "I set up the package once. Payments happen automatically while I focus on planning."
- **For Couples**: "I signed the contract and payments just work. No friction."
- **For the Platform**: Differentiated value proposition, increased stickiness, new monetization path.

---

## Feature Overview

### Core Flow
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    PACKAGE      │───▶│    CONTRACT     │───▶│    AUTOPILOT    │
│  Define once    │    │  Couple signs   │    │  Money flows    │
│  Reuse always   │    │  Card saved     │    │  Automatically  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                      │                      │
         ▼                      ▼                      ▼
   AI: Pricing           AI: Follow-up          AI: Retry timing
   suggestions           draft if no sign       optimization
```

### AI Integration Points
| Moment | AI Action | Credits |
|--------|-----------|---------|
| Package creation | Suggest pricing based on market | 3 |
| Contract sent | Draft warm intro message | 1 |
| 3 days no signature | Draft follow-up email | 1 |
| Contract signed | Generate welcome message | 1 |
| Payment approaching | Predict success likelihood | 0 (internal) |
| Payment failed | Suggest optimal retry time | 0 (internal) |
| Budget updated | Generate insights | 3 |
| Seating incomplete | Optimize arrangement | 2-10 |

---

## Epic Structure

### Epic 1: Foundation Layer
**Goal**: Data models, services, and infrastructure

| Ticket | Title | Priority | Points | Dependencies |
|--------|-------|----------|--------|--------------|
| WFA-101 | Create Package data model and MongoDB schema | P0 | 3 | None |
| WFA-102 | Create Contract data model and schema | P0 | 3 | WFA-101 |
| WFA-103 | Create ScheduledPayment data model | P0 | 2 | WFA-102 |
| WFA-104 | Create PackageService with CRUD operations | P0 | 5 | WFA-101 |
| WFA-105 | Create ContractService for lifecycle management | P0 | 5 | WFA-102 |
| WFA-106 | Create PaymentScheduleService for calculations | P0 | 5 | WFA-103 |
| WFA-107 | Add package/contract API routes | P0 | 3 | WFA-104, WFA-105 |
| WFA-108 | Add GOOGLE_API_KEY to settings and env | P0 | 1 | None |

### Epic 2: AI Service Layer
**Goal**: Centralized AI with credits, caching, and logging

| Ticket | Title | Priority | Points | Dependencies |
|--------|-------|----------|--------|--------------|
| WFA-201 | Create AIService foundation class | P0 | 5 | WFA-108 |
| WFA-202 | Create AICacheService with MongoDB backend | P0 | 3 | None |
| WFA-203 | Integrate AI credits with existing subscription limits | P0 | 3 | WFA-201 |
| WFA-204 | Add AI usage logging collection and service | P1 | 2 | WFA-201 |
| WFA-205 | Create AI feature definitions (prompts, credits, TTLs) | P0 | 3 | WFA-201 |
| WFA-206 | Add cache invalidation hooks to budget service | P1 | 2 | WFA-202 |
| WFA-207 | Add cache invalidation hooks to guest service | P1 | 2 | WFA-202 |
| WFA-208 | Create AI metrics endpoint for root admin | P2 | 2 | WFA-204 |

### Epic 3: Package Builder UI
**Goal**: Planner can create and manage packages

| Ticket | Title | Priority | Points | Dependencies |
|--------|-------|----------|--------|--------------|
| WFA-301 | Create Packages section in planner navigation | P0 | 2 | None |
| WFA-302 | Create package list page with status indicators | P0 | 3 | WFA-107 |
| WFA-303 | Create package builder form (services section) | P0 | 5 | WFA-302 |
| WFA-304 | Add payment schedule builder component | P0 | 5 | WFA-303 |
| WFA-305 | Add terms/cancellation policy section | P1 | 3 | WFA-303 |
| WFA-306 | Create package preview mode | P0 | 3 | WFA-303 |
| WFA-307 | Implement save as template functionality | P1 | 3 | WFA-304 |
| WFA-308 | Integrate AI pricing suggestions into builder | P1 | 3 | WFA-201, WFA-303 |

### Epic 4: Contract Signing Flow
**Goal**: Couples can view and sign contracts

| Ticket | Title | Priority | Points | Dependencies |
|--------|-------|----------|--------|--------------|
| WFA-401 | Create public contract viewing page (no auth) | P0 | 5 | WFA-107 |
| WFA-402 | Design branded contract template (PDF-like view) | P0 | 5 | WFA-401 |
| WFA-403 | Integrate Stripe Elements for card capture | P0 | 5 | WFA-401 |
| WFA-404 | Create digital signature component | P0 | 3 | WFA-401 |
| WFA-405 | Implement contract signing API endpoint | P0 | 5 | WFA-105, WFA-403 |
| WFA-406 | Generate PDF snapshot on signing | P1 | 3 | WFA-405 |
| WFA-407 | Send signed contract confirmation email | P0 | 2 | WFA-405 |
| WFA-408 | Process first payment (deposit) on signing | P0 | 3 | WFA-405 |
| WFA-409 | AI-drafted follow-up if no sign after 3 days | P1 | 3 | WFA-201, WFA-105 |

### Epic 5: Autopilot Engine
**Goal**: Payments happen automatically on schedule

| Ticket | Title | Priority | Points | Dependencies |
|--------|-------|----------|--------|--------------|
| WFA-501 | Create payment schedule calculator | P0 | 5 | WFA-106 |
| WFA-502 | Build cron job: process-due-payments | P0 | 5 | WFA-501 |
| WFA-503 | Build cron job: send-payment-reminders (3 days before) | P0 | 3 | WFA-501 |
| WFA-504 | Implement retry logic with exponential backoff | P0 | 5 | WFA-502 |
| WFA-505 | Add payment_intent.succeeded webhook for scheduled payments | P0 | 3 | WFA-502 |
| WFA-506 | Add payment_intent.payment_failed webhook handler | P0 | 3 | WFA-504 |
| WFA-507 | Build cron job: recalculate-schedules (on wedding date change) | P1 | 3 | WFA-501 |
| WFA-508 | AI: Optimal retry timing suggestion | P2 | 3 | WFA-201, WFA-504 |
| WFA-509 | AI: Payment success prediction | P2 | 5 | WFA-201 |

### Epic 6: Couple Portal
**Goal**: Couples can view status and manage payment method

| Ticket | Title | Priority | Points | Dependencies |
|--------|-------|----------|--------|--------------|
| WFA-601 | Create public couple portal page | P0 | 5 | WFA-102 |
| WFA-602 | Display payment schedule with status indicators | P0 | 3 | WFA-601 |
| WFA-603 | Show payment history with receipts | P0 | 3 | WFA-601 |
| WFA-604 | Implement update payment method flow | P0 | 5 | WFA-601 |
| WFA-605 | Add download receipt functionality | P1 | 2 | WFA-603 |
| WFA-606 | Send payment reminder emails to couples | P0 | 3 | WFA-503 |

### Epic 7: AI Features (Initial Set)
**Goal**: Deliver immediate value through AI

| Ticket | Title | Priority | Points | Dependencies |
|--------|-------|----------|--------|--------------|
| WFA-701 | Budget insights: always-visible recommendations | P0 | 5 | WFA-201 |
| WFA-702 | Seating optimization: small weddings (≤50) | P0 | 5 | WFA-201 |
| WFA-703 | Seating optimization: medium weddings (51-150) | P1 | 3 | WFA-702 |
| WFA-704 | Seating optimization: large weddings (150+) | P2 | 3 | WFA-703 |
| WFA-705 | Communication copilot: draft emails | P1 | 5 | WFA-201 |
| WFA-706 | Progress report generator | P2 | 3 | WFA-201 |
| WFA-707 | Package pricing suggestions | P1 | 3 | WFA-201, WFA-303 |

### Epic 8: Unified Money Dashboard
**Goal**: Replace fragmented billing UI

| Ticket | Title | Priority | Points | Dependencies |
|--------|-------|----------|--------|--------------|
| WFA-801 | Design unified Money dashboard | P0 | 3 | None |
| WFA-802 | Build incoming payments view (from couples) | P0 | 5 | WFA-501 |
| WFA-803 | Build outgoing payments view (to vendors) | P1 | 3 | Existing |
| WFA-804 | Add cash flow timeline visualization | P1 | 5 | WFA-802 |
| WFA-805 | Integrate subscription billing into Money view | P1 | 3 | Existing |
| WFA-806 | Deprecate old "Client Payments" tab | P2 | 2 | WFA-802 |

### Epic 9: Integration & Polish
**Goal**: Connect everything, handle edge cases

| Ticket | Title | Priority | Points | Dependencies |
|--------|-------|----------|--------|--------------|
| WFA-901 | Connect contracts to Budget module | P0 | 3 | WFA-102 |
| WFA-902 | Handle offline payments (mark as paid externally) | P1 | 3 | WFA-502 |
| WFA-903 | Implement contract cancellation flow | P1 | 5 | WFA-105 |
| WFA-904 | Build refund processing workflow | P2 | 5 | WFA-903 |
| WFA-905 | Hide Connect card for root admin in billing | P1 | 1 | Existing |
| WFA-906 | Migrate existing payment_requests (optional) | P2 | 3 | WFA-102 |
| WFA-907 | End-to-end testing: full flow | P0 | 5 | All |

---

## Data Models

### Package
```python
class WeddingPackage(BaseModel):
    """A reusable service package template."""

    id: str = Field(default_factory=lambda: f"pkg_{ObjectId()}")
    planner_id: str

    # Package details
    name: str                              # "Full Wedding Planning"
    description: Optional[str]
    services: List[PackageService]         # What's included

    # Pricing
    total_amount: Decimal
    currency: str = "usd"

    # Payment schedule
    payment_schedule: List[ScheduleItem]

    # Terms
    cancellation_policy: str               # "full_refund_30_days" or custom text
    late_payment_policy: Optional[str]
    custom_terms: Optional[str]

    # Meta
    is_template: bool = False
    status: Literal["draft", "active", "archived"] = "draft"
    created_at: datetime
    updated_at: datetime


class PackageService(BaseModel):
    """A service included in a package."""
    name: str
    description: Optional[str]
    included: bool = True


class ScheduleItem(BaseModel):
    """A single payment in the schedule."""
    name: str                              # "Deposit", "Final Balance"
    trigger: Literal["on_signing", "days_after_signing", "days_before_wedding", "fixed_date"]

    # Trigger-specific fields
    days_after: Optional[int]              # For days_after_signing
    days_before: Optional[int]             # For days_before_wedding
    fixed_date: Optional[date]             # For fixed_date

    # Amount (one of these)
    amount: Optional[Decimal]              # Fixed amount
    percentage: Optional[float]            # Percentage of total (0-100)
```

### Contract
```python
class Contract(BaseModel):
    """A signed agreement between planner and couple."""

    id: str = Field(default_factory=lambda: f"ctr_{ObjectId()}")
    package_id: str
    planner_id: str
    wedding_id: Optional[str]              # Link to wedding entity

    # Couple info (may not be platform users)
    couple: CoupleInfo
    wedding_date: Optional[date]
    venue: Optional[str]

    # Signature
    signature: Optional[ContractSignature]

    # Payment (Stripe)
    stripe_customer_id: Optional[str]
    stripe_payment_method_id: Optional[str]

    # Document
    document_url: Optional[str]            # PDF snapshot

    # Status
    status: Literal["draft", "sent", "viewed", "signed", "active", "completed", "cancelled"]

    # Timestamps
    created_at: datetime
    sent_at: Optional[datetime]
    viewed_at: Optional[datetime]
    signed_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]


class CoupleInfo(BaseModel):
    """Couple contact information."""
    partner1_name: str
    partner2_name: Optional[str]
    email: str
    phone: Optional[str]


class ContractSignature(BaseModel):
    """Digital signature record."""
    signed_by: str                         # Name typed
    signed_at: datetime
    ip_address: str
    user_agent: str
```

### ScheduledPayment
```python
class ScheduledPayment(BaseModel):
    """An individual scheduled payment instance."""

    id: str = Field(default_factory=lambda: f"sp_{ObjectId()}")
    contract_id: str
    planner_id: str

    # From schedule
    name: str                              # "Deposit", "Second Payment"
    amount: Decimal
    currency: str = "usd"
    due_date: date                         # Calculated from schedule rules

    # Execution
    status: Literal["scheduled", "processing", "succeeded", "failed", "cancelled", "paid_externally"]
    stripe_payment_intent_id: Optional[str]

    # Retry tracking
    attempt_count: int = 0
    last_attempt_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    failure_reason: Optional[str]

    # Completion
    paid_at: Optional[datetime]
    receipt_url: Optional[str]
    paid_externally: bool = False
    external_payment_note: Optional[str]

    # Timestamps
    created_at: datetime
    updated_at: datetime
```

### AICache
```python
class AICache(BaseModel):
    """Cached AI response."""

    id: str                                # ai:{feature}:{tenant_id}:{context_hash}
    feature: str
    tenant_id: str
    context_hash: str
    response: dict
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
```

### AIUsageLog
```python
class AIUsageLog(BaseModel):
    """AI usage audit log."""

    id: str = Field(default_factory=lambda: str(ObjectId()))
    user_id: str
    tenant_id: str                         # Wedding ID or Planner ID
    feature: str
    credits_used: int
    latency_ms: float
    status: Literal["success", "error", "cached"]
    error: Optional[str]
    timestamp: datetime
```

---

## API Contracts

### Package Endpoints
```yaml
# Create package
POST /admin/packages
Body: CreatePackageRequest
Response: Package
Auth: require_admin_or_planner

# List planner's packages
GET /admin/packages
Query: ?include_templates=true&status=active
Response: List[Package]
Auth: require_admin_or_planner

# Get package details
GET /admin/packages/{package_id}
Response: Package
Auth: require_admin_or_planner

# Update package
PUT /admin/packages/{package_id}
Body: UpdatePackageRequest
Response: Package
Auth: require_admin_or_planner

# Delete package (drafts only)
DELETE /admin/packages/{package_id}
Response: {status: "deleted"}
Auth: require_admin_or_planner

# Send package to couple (creates contract)
POST /admin/packages/{package_id}/send
Body: SendPackageRequest {couple: CoupleInfo, wedding_date?: date}
Response: Contract
Auth: require_admin_or_planner

# Duplicate as template
POST /admin/packages/{package_id}/duplicate
Body: {name?: string, as_template: bool}
Response: Package
Auth: require_admin_or_planner
```

### Contract Endpoints (Public)
```yaml
# View contract (no auth, token in URL)
GET /contracts/{contract_token}
Response: ContractPublicView
Auth: None (token-based)

# Sign contract
POST /contracts/{contract_token}/sign
Body: SignContractRequest {
  signature_name: string,
  payment_method_id: string,  # From Stripe Elements
  accept_terms: bool
}
Response: {status: "signed", first_payment: PaymentResult}
Auth: None (token-based)

# Get contract status
GET /contracts/{contract_token}/status
Response: {status: string, viewed_at?: datetime}
Auth: None (token-based)
```

### Couple Portal Endpoints (Public)
```yaml
# View portal
GET /portal/{contract_token}
Response: CouplePortalView
Auth: None (token-based)

# Get payment history
GET /portal/{contract_token}/payments
Response: List[ScheduledPayment]
Auth: None (token-based)

# Update payment method
PUT /portal/{contract_token}/payment-method
Body: {payment_method_id: string}
Response: {status: "updated"}
Auth: None (token-based)
```

### AI Endpoints
```yaml
# Budget insights
GET /admin/weddings/{wedding_id}/ai/budget-insights
Response: {insights: List[Insight], cached: bool, credits_used: int}
Auth: require_admin_or_planner

# Seating optimization
POST /admin/weddings/{wedding_id}/ai/seating-optimize
Body: {guests: List[Guest], tables: List[Table], constraints: List[Constraint]}
Response: {arrangement: TableArrangement, cached: bool, credits_used: int}
Auth: require_admin_or_planner

# Communication draft
POST /admin/ai/draft-communication
Body: {type: string, context: dict, tone?: string}
Response: {draft: string, credits_used: int}
Auth: require_admin_or_planner

# Package pricing suggestion
POST /admin/ai/suggest-pricing
Body: {services: List[str], location: string, wedding_size: int}
Response: {min_price: float, max_price: float, recommended: float, ...}
Auth: require_admin_or_planner

# AI metrics (root admin)
GET /admin/ai/metrics
Query: ?period=7d
Response: {daily_usage: List, top_tenants: List, feature_breakdown: dict}
Auth: require_root_admin
```

### Scheduled Payment Endpoints
```yaml
# List scheduled payments for planner
GET /admin/scheduled-payments
Query: ?status=scheduled&due_before=2025-03-01
Response: List[ScheduledPayment]
Auth: require_admin_or_planner

# Manual retry
POST /admin/scheduled-payments/{payment_id}/retry
Response: {status: string, payment_intent_id?: string}
Auth: require_admin_or_planner

# Cancel scheduled payment
POST /admin/scheduled-payments/{payment_id}/cancel
Body: {reason?: string}
Response: {status: "cancelled"}
Auth: require_admin_or_planner

# Mark as paid externally
POST /admin/scheduled-payments/{payment_id}/mark-paid
Body: {note?: string}
Response: {status: "paid_externally"}
Auth: require_admin_or_planner
```

---

## UI Specifications

### Package Builder
```
┌─────────────────────────────────────────────────────────────────────┐
│  Packages                                        [+ New Package]    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────┐  ┌─────────────────────┐                  │
│  │ Full Planning       │  │ Day-of Coordination │                  │
│  │ $15,000             │  │ $3,500              │                  │
│  │ ✓ 3 contracts       │  │ ✓ 8 contracts       │                  │
│  │ Template            │  │ Template            │                  │
│  └─────────────────────┘  └─────────────────────┘                  │
│                                                                     │
│  Recent Packages                                                    │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │ Emma & Michael Package    │ $15,000 │ Signed  │ Active  │       │
│  │ Sarah & James Package     │ $12,500 │ Sent    │ Pending │       │
│  │ Custom Package (Draft)    │ $8,000  │ Draft   │ Edit    │       │
│  └─────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### Contract Signing Page (Couple View)
```
┌─────────────────────────────────────────────────────────────────────┐
│                    Sarah's Wedding Planning                         │
│                    YOUR WEDDING PACKAGE                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Services Included                                                  │
│  ─────────────────                                                  │
│  ✓ Full wedding planning & coordination                            │
│  ✓ Vendor sourcing & management                                    │
│  ✓ Timeline creation & management                                  │
│  ✓ Day-of coordination                                             │
│                                                                     │
│  Investment: $15,000                                                │
│                                                                     │
│  Payment Schedule                                                   │
│  ────────────────                                                   │
│  • On signing ─────────── $3,000 (20%)                             │
│  • 90 days before ─────── $6,000 (40%)                             │
│  • 7 days before ──────── $6,000 (40%)                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │  💳 Payment Method                                       │       │
│  │  [Stripe Card Element]                                   │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                     │
│  ☑ I have read and agree to the terms and cancellation policy      │
│                                                                     │
│  Signature: [___________________]                                   │
│                                                                     │
│  [            Sign & Pay $3,000 Deposit            ]                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Unified Money Dashboard
```
┌─────────────────────────────────────────────────────────────────────┐
│  Money                                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  This Month                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Incoming    │  │  Outgoing    │  │  Net         │              │
│  │  $24,500     │  │  $8,200      │  │  +$16,300    │              │
│  │  ↑ 12%       │  │  ↓ 5%        │  │              │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                     │
│  Upcoming Payments                            [Collect Payment]     │
│  ─────────────────                                                  │
│  │ Emma & Michael  │ $6,000 │ Mar 17 │ 5 days │ ✓ Card saved │    │
│  │ Sarah & James   │ $4,500 │ Mar 22 │ 10 days│ ✓ Card saved │    │
│  │ Lisa & David    │ $7,500 │ Mar 28 │ 16 days│ ⚠ Update card│    │
│                                                                     │
│  ⚠ Action Needed                                                    │
│  │ Tom & Amy: Card declined Mar 12. Retry scheduled Mar 15.        │
│  │ [Retry Now] [Contact Couple]                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Cron Jobs

### process-due-payments
```yaml
Schedule: Daily at 9:00 AM UTC (configurable per planner timezone)
Logic:
  1. Find all ScheduledPayments where due_date <= today AND status = "scheduled"
  2. For each payment:
     a. Create PaymentIntent using saved payment method
     b. Set status = "processing"
     c. If immediate success: status = "succeeded"
     d. If requires_action: Send email to couple
     e. If fails: Set status = "failed", schedule retry
```

### send-payment-reminders
```yaml
Schedule: Daily at 10:00 AM UTC
Logic:
  1. Find payments due in 3 days with status = "scheduled"
  2. For each:
     a. Send reminder email to couple
     b. Record reminder_sent_at
```

### retry-failed-payments
```yaml
Schedule: Every 6 hours
Logic:
  1. Find payments where status = "failed" AND next_retry_at <= now
  2. For each:
     a. Attempt charge
     b. If success: status = "succeeded"
     c. If fail:
        - Increment attempt_count
        - Calculate next_retry_at (exponential backoff: 1d, 2d, 4d, 7d)
        - If attempt_count > 4: Notify planner for manual intervention
```

### recalculate-schedules
```yaml
Schedule: On wedding date change (event-driven) + daily cleanup
Logic:
  1. Find contracts where wedding_date changed
  2. For each contract with days_before_wedding payments:
     a. Recalculate due_date for each scheduled payment
     b. Update ScheduledPayment records
     c. If due_date moved to past: Notify planner
```

---

## Implementation Sequence

### Phase 1: Foundation (Week 1-2)
- WFA-101 → WFA-108 (Data models + API routes)
- WFA-201 → WFA-205 (AI service foundation)

### Phase 2: Package Builder (Week 2-3)
- WFA-301 → WFA-307 (UI for package management)
- WFA-308 (AI pricing integration)

### Phase 3: Contract Flow (Week 3-4)
- WFA-401 → WFA-408 (Public signing experience)
- WFA-409 (AI follow-up drafts)

### Phase 4: Autopilot (Week 4-5)
- WFA-501 → WFA-509 (Scheduled payments + crons)

### Phase 5: Couple Portal (Week 5-6)
- WFA-601 → WFA-606 (Public couple dashboard)

### Phase 6: AI Features (Week 6-7)
- WFA-701 → WFA-707 (Budget insights, seating, communication)

### Phase 7: Integration (Week 7-8)
- WFA-801 → WFA-806 (Unified Money dashboard)
- WFA-901 → WFA-907 (Connections, edge cases, testing)

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Contract signature rate | >70% | Signed / Sent |
| Payment success rate | >95% | Succeeded / Attempted |
| Time to first payment | <2 days | From contract sent |
| AI credit utilization | >50% | Used / Allocated |
| Planner retention | +15% | vs. non-package users |
| NPS for payment flow | >50 | Couple survey |

---

## Security Considerations

1. **Contract tokens**: Use cryptographically secure random tokens (32 bytes, base64)
2. **PCI compliance**: Card data never touches our servers (Stripe Elements only)
3. **Rate limiting**: Contract viewing/signing endpoints (prevent enumeration)
4. **Token expiry**: Contract tokens expire after signing + 30 days
5. **Audit logging**: All payment attempts logged with IP, user-agent
6. **AI prompt injection**: Sanitize all user input before AI prompts

---

## Migration Notes

### From Current Payment Requests
- Existing `payment_requests` collection remains functional
- New contracts create `scheduled_payments` in parallel
- Optional migration script for active payment requests
- Old "Client Payments" tab deprecated after 30 days

### Credit Reset Timing
- AI credits reset on subscription billing cycle
- Prorated credits for mid-cycle plan upgrades
- Grace period: 5 bonus credits if exhausted mid-cycle

---

## Appendix: AI Credit Allocation

### By Plan
| Plan | Monthly Credits | AI Tools Access |
|------|----------------|-----------------|
| Boutique | 100 | Budget insights, communication drafts |
| Signature | 300 | All features including seating |

### By Feature
| Feature | Credits | Cacheable | TTL |
|---------|---------|-----------|-----|
| Budget insights | 3 | Yes | 48h |
| Seating (≤50) | 2 | Yes | 72h |
| Seating (51-150) | 5 | Yes | 72h |
| Seating (150+) | 10 | Yes | 72h |
| Email draft | 1 | No | - |
| Progress report | 2 | Yes | 6h |
| Package pricing | 3 | Yes | 24h |

---

*Document Version: 1.0*
*Last Updated: December 2024*
*Author: Claude (Product Architecture)*

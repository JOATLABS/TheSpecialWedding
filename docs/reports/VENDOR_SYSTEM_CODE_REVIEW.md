# Engineering Code Review: Vendor Management System
## The Special Wedding SaaS Platform

**Review Date:** 2026-03-22
**Scope:** Vendor directory, contracts, payments, and token-based vendor portal
**Focus:** Preparation for new vendor portal feature with inline contract notes & AI quote comparison

---

## Executive Summary

The vendor management system demonstrates **solid fundamentals** with good separation of concerns and thoughtful design patterns. However, there are **critical security gaps** in token handling and authorization that must be addressed before building the vendor portal feature. Several **performance optimizations** and **data consistency issues** warrant attention.

**Overall Assessment:**
- **Security:** CRITICAL - Token validation gaps, insufficient input sanitization
- **Performance:** ACCEPTABLE - Good use of aggregation, some N+1 risks remain
- **Correctness:** NEEDS IMPROVEMENT - Data consistency issues, missing transaction support
- **Maintainability:** GOOD - Clear structure, but token handling duplicated

---

## 1. SECURITY REVIEW

### 1.1 CRITICAL: Token Access Control Gaps

**Issue:** The `get_contract_by_token()` method has weak token validation.

**Location:** `/app/services/vendor_service.py:919-955`

**Problem:**
```python
async def get_contract_by_token(self, contract_id: str, token: str) -> dict:
    contract = await self.vendor_contracts.find_one({
        "_id": ObjectId(contract_id),
        "access_token": token
    })
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found or invalid token")

    # Check expiration
    if contract.get("token_expires_at") and contract["token_expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Contract link has expired")
```

**Risks:**
1. **No rate limiting** on token attempts - attackers can brute force tokens
2. **Same error message** for "not found" and "invalid token" suggests valid contract IDs may be enumerable
3. **Token format too simple** - 32 random alphanumeric characters (line 110) is good, but no token rotation/revocation mechanism
4. **No token usage tracking** - vendors could forward links; no audit trail
5. **Token stored in plaintext** in MongoDB - if DB is compromised, all active tokens are exposed

**Recommendations:**
```python
# 1. Implement rate limiting per IP/contract
# 2. Hash tokens in database (bcrypt/argon2)
# 3. Add token revocation mechanism
# 4. Log all token access attempts
# 5. Generic error: "Access denied"
# 6. Implement token rotation on first use
```

**For New Feature:** Token-based vendor portal MUST implement:
- Secure token storage (hashed)
- Per-vendor token with scope limitations
- Token expiry with auto-rotation
- Rate limiting per IP/vendor
- Comprehensive audit logging

---

### 1.2 HIGH: Authorization Bypass in `get_wedding_vendors()`

**Location:** `/app/services/vendor_service.py:549-562`

**Problem:**
```python
async def get_wedding_vendors(self, wedding_id: str, created_by: str) -> List[dict]:
    """Get all vendors assigned to a wedding"""
    try:
        cursor = self.vendor_assignments.find({"wedding_id": wedding_id})
        assignments = await cursor.to_list(length=100)
        # NO VERIFICATION that created_by owns this wedding!
```

The `created_by` parameter is accepted but **never validated** against the wedding. A planner could theoretically query any wedding's vendors.

**Impact:** Moderate - depends on how `wedding_id` is obtained (if from user input without validation)

**Fix:**
```python
async def get_wedding_vendors(self, wedding_id: str, created_by: str) -> List[dict]:
    # Verify ownership
    wedding = await self._get_wedding(wedding_id)
    if not wedding or wedding.get("created_by") != created_by:
        raise HTTPException(status_code=403, detail="Access denied")

    cursor = self.vendor_assignments.find({"wedding_id": wedding_id})
    # ...
```

---

### 1.3 HIGH: No Input Validation for Email Fields

**Location:** Multiple endpoints in `/app/api/vendor_management.py`

**Problem:** Email fields in requests are not validated:
```python
# vendor_management.py:738
payer_email: str  # No EmailStr type
payer_name: str   # Could contain HTML/JS for XSS

# Contrast with vendor.py model which uses EmailStr
email: str = Field(..., description="Vendor email address")
```

**Risk:** Cross-site scripting (XSS) if vendor names/notes are rendered without escaping in frontend.

**Fix:**
```python
from pydantic import EmailStr, Field

class CreatePaymentLinkRequest(BaseModel):
    payer_type: PayerType
    payer_email: EmailStr  # Validates email format
    payer_name: str = Field(..., max_length=200)  # Add constraints
    # ...
```

---

### 1.4 MEDIUM: Payment Link Access Not Properly Scoped

**Location:** `/app/api/vendor_management.py:637-656`

**Problem:**
```python
@router.get("/payment-links/{payment_link_id}")
async def get_payment_link(
    payment_link_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    from bson import ObjectId

    link = await vendor_service.payment_links.find_one({
        "_id": ObjectId(payment_link_id),
        "created_by": current_user.email  # ✓ Good
    })
```

This correctly checks `created_by`, but there's **no public endpoint** for payment link viewing without auth. This means:
- Payers receive email links but can't access without login
- Payment links aren't truly "linkable" to external parties (couples, vendors)
- Security via obscurity (long IDs) instead of proper token handling

**Recommendation:** Implement public payment link access similar to contract links.

---

### 1.5 MEDIUM: MongoDB Regex Injection Risk

**Location:** `/app/services/vendor_service.py:271-276`

**Problem:**
```python
if search:
    query["$or"] = [
        {"business_name": {"$regex": search, "$options": "i"}},
        {"contact_name": {"$regex": search, "$options": "i"}},
        {"email": {"$regex": search, "$options": "i"}},
        {"service_description": {"$regex": search, "$options": "i"}}
    ]
```

The `search` parameter is passed directly to `$regex` without escaping. A user could craft a regex injection:
```
search=".*"  # Returns all vendors
search="^admin"  # Pattern matching
```

**Fix:**
```python
import re

if search:
    # Escape regex special characters
    escaped_search = re.escape(search)
    query["$or"] = [
        {"business_name": {"$regex": escaped_search, "$options": "i"}},
        # ...
    ]
```

---

### 1.6 MEDIUM: Planner Settings Update Not Validated

**Location:** `/app/api/vendor_management.py:689-768`

**Problem:** While there's validation on the values (ranges), the settings endpoint doesn't verify the settings structure before processing:

```python
settings: dict  # Untyped dict!

# Then it validates field-by-field, but no schema validation
```

**Improvement:**
```python
from pydantic import BaseModel

class UpdateContractSettingsRequest(BaseModel):
    token_expiry_days: Optional[int] = Field(None, ge=7, le=90)
    deposit_due_days: Optional[int] = Field(None, ge=1, le=60)
    # ...

@router.put("/settings/contract")
async def update_contract_settings(
    settings: UpdateContractSettingsRequest,  # Typed!
    # ...
):
    # Type system validates for you
```

---

## 2. PERFORMANCE REVIEW

### 2.1 GOOD: Efficient Dashboard Counts

**Location:** `/app/services/vendor_service.py:393-481`

**Assessment:** ✓ EXCELLENT

The dashboard uses aggregation pipelines and count_documents instead of loading all data:
```python
vendor_total = await self.vendor_profiles.count_documents({...})
payment_totals = await self.payment_milestones.aggregate(payment_pipeline).to_list(1)
```

This prevents N+1 and large memory loads. **Best practice exemplified.**

---

### 2.2 ACCEPTABLE: Vendor Profile Queries

**Location:** `/app/services/vendor_service.py:250-298`

**Assessment:** ✓ GOOD with notes

```python
cursor = self.vendor_profiles.find(query).skip(skip).limit(limit).sort("business_name", 1)
vendors = await cursor.to_list(length=limit)
```

**Strengths:**
- Uses skip/limit for pagination (good)
- Sorts by business_name (probably indexed)
- Reasonable limit cap (50 default, max 100)

**Concerns:**
- No index hints for searches; MongoDB may use wrong index
- `$or` queries without proper indexing can be slow
- No cardinality analysis in aggregation pipeline

**Recommendation:** Create compound indexes:
```javascript
db.vendor_profiles.createIndex({
  "created_by": 1,
  "is_active": 1,
  "service_category": 1
})
db.vendor_profiles.createIndex({
  "created_by": 1,
  "is_preferred": 1
})
```

---

### 2.3 MEDIUM: N+1 Risk in Contract List + Related Data

**Location:** `/app/api/vendor_management.py:473-514` (Dashboard)

**Problem:**
```python
recent_contracts = await vendor_service.get_contracts(...)  # Loads contracts

upcoming_milestones = await vendor_service.get_payment_milestones(...)  # Separate query
```

If you later add code to fetch vendor details for each contract, you'll hit N+1:
```python
for contract in recent_contracts:
    vendor = await vendor_service.get_vendor_profile(contract.vendor_id)  # BAD!
```

**Current Status:** No N+1 in current code, but future-proof with:
```python
# Use MongoDB $lookup instead
contracts_with_vendors = await self.vendor_contracts.aggregate([
    {"$match": {"created_by": created_by}},
    {"$lookup": {
        "from": "vendor_profiles",
        "localField": "vendor_profile_id",
        "foreignField": "_id",
        "as": "vendor"
    }},
    {"$limit": 5}
]).to_list(5)
```

---

### 2.4 ACCEPTABLE: Payment Milestone Status Updates

**Location:** `/app/services/vendor_service.py:1515-1543`

**Assessment:** ✓ GOOD design

Milestones are loaded, checked for overdue status in-memory, then bulk-updated:
```python
if overdue_milestone_ids:
    await self.payment_milestones.update_many(
        {"_id": {"$in": overdue_milestone_ids}},
        {"$set": {"status": PaymentMilestoneStatus.OVERDUE.value, ...}}
    )
```

This is more efficient than individual updates, though could be further optimized with MongoDB's calculated fields.

---

## 3. CORRECTNESS REVIEW

### 3.1 CRITICAL: No Transaction Support for Multi-Collection Updates

**Location:** `/app/services/vendor_service.py:1549-1636` (record_payment)

**Problem:**
```python
async def record_payment(self, milestone_id: str, amount: float, ...):
    # Updates 4 different collections without transactions!
    await self.payment_milestones.update_one(...)  # Could succeed
    await self.vendor_assignments.update_one(...)   # Could fail
    await self.vendor_profiles.update_one(...)      # Could fail
    await self.budget_categories.update_one(...)    # Could fail
```

**Impact:** CRITICAL for financial consistency

If step 2 fails after step 1 succeeds:
- Milestone shows paid
- But vendor assignment not updated
- Budget category shows wrong amount
- **Audit trail is broken**

**Comment in code acknowledges this:**
```python
"""
Note: This method updates multiple collections without using MongoDB transactions.
In rare cases of partial failure, manual reconciliation may be needed.
"""
```

**Fix:** Use MongoDB transactions (requires replica set):
```python
async with await self.client.start_session() as session:
    async with session.start_transaction():
        await self.payment_milestones.update_one(..., session=session)
        await self.vendor_assignments.update_one(..., session=session)
        await self.vendor_profiles.update_one(..., session=session)
        await self.budget_categories.update_one(..., session=session)
```

---

### 3.2 CRITICAL: No Transaction in `sign_contract()`

**Location:** `/app/services/vendor_service.py:1077-1173`

**Problem:**
```python
async def sign_contract(self, contract_id: str, token: str, ...):
    # Updates vendor_contracts
    await self.vendor_contracts.update_one(...)

    # Updates vendor_assignments
    await self.vendor_assignments.update_one(...)

    # Sends email (external side effect!)
    await self.email_service.send_email(...)

    # If email fails, contract is marked signed but notification never sent
```

**Additional Issue:** No idempotency key. If request retries:
- Contract gets signed multiple times (status check prevents this but is fragile)
- Email sent twice
- Planner notification sent twice

**Recommendation:**
```python
# 1. Use transactions
# 2. Add idempotency check at start
# 3. Move email outside transaction or make it pre-transaction
# 4. Log errors separately

async with session.start_transaction():
    # Mark as signed
    # Update assignments

# Only AFTER transaction succeeds
await self.email_service.send_email(...)
```

---

### 3.3 HIGH: Race Condition in Vendor Assignment

**Location:** `/app/services/vendor_service.py:502-508`

**Problem:**
```python
# Check if already assigned
existing = await self.vendor_assignments.find_one({
    "vendor_profile_id": vendor_profile_id,
    "wedding_id": wedding_id
})
if existing:
    raise HTTPException(...)

# Two requests can both pass the check, then both insert!
assignment = await self.vendor_assignments.insert_one(assignment)
```

**Fix:** Use unique indexes + upsert:
```python
db.vendor_assignments.createIndex({
    "vendor_profile_id": 1,
    "wedding_id": 1
}, { unique: true })

# Then use replace_one with upsert:
await self.vendor_assignments.replace_one(
    {"vendor_profile_id": vendor_profile_id, "wedding_id": wedding_id},
    assignment,
    upsert=True
)
```

---

### 3.4 MEDIUM: Contract Token Not Regenerated on Resend

**Location:** `/app/services/vendor_service.py:957-1075` (send_contract)

**Issue:** If a contract is sent twice, the vendor gets the same link. If the first recipient shares it before closing, the second recipient could access it.

**Current:** No token refresh on resend

**Recommendation:**
```python
# Option 1: Regenerate token on each send
contract["access_token"] = self._generate_token()

# Option 2: Track token usage
# Add "token_used_at" field, invalidate after viewing
```

---

### 3.5 MEDIUM: No Handling of Concurrent Updates

**Location:** All update operations

**Issue:** When updating vendor profile stats (weddings_count, total_revenue), concurrent requests could lose updates:

```python
# Thread 1: reads weddings_count = 5
# Thread 2: reads weddings_count = 5
# Thread 1: sets weddings_count = 6
# Thread 2: sets weddings_count = 6
# Result: Should be 7, but is 6

# Current code uses $inc which is atomic, so this is actually GOOD:
await self.vendor_profiles.update_one(
    {"_id": ObjectId(vendor_profile_id)},
    {"$inc": {"weddings_count": 1}}  # ✓ Atomic
)
```

**Assessment:** ✓ This is handled correctly with `$inc` operator.

---

## 4. MAINTAINABILITY REVIEW

### 4.1 Code Organization: GOOD

**Strengths:**
- Clear separation: Models → Service → API routes
- Logical grouping by feature (directory, contracts, payments)
- Good use of helper methods (`_serialize_doc`, `_populate_placeholders`, `_log_communication`)
- Comprehensive docstrings

**Observations:**
- VendorService is large (2134 lines) - consider breaking into smaller services
- Payment logic could be extracted: `PaymentService`
- Template logic could be extracted: `ContractTemplateService`

---

### 4.2 Naming and Clarity: GOOD

**Strengths:**
```python
get_contract_by_token()  # Clear it's for public access
_serialize_doc()         # Private utility well-named
payment_milestones       # Collection name is clear
```

**Minor Issues:**
```python
created_by: str  # Used inconsistently:
# - For planner email in vendor_profiles
# - For planner email in contracts
# - For user who logged communication

# Better: planner_email throughout
```

---

### 4.3 Duplication: MEDIUM

**Issue:** Token validation duplicated across endpoints:

**Location 1:** `/app/services/vendor_service.py:919-932` (get_contract_by_token)
**Location 2:** `/app/services/vendor_service.py:1093-1105` (sign_contract)

Both check:
```python
# Same pattern repeated
contract = await self.vendor_contracts.find_one({
    "_id": ObjectId(contract_id),
    "access_token": token
})

if not contract:
    raise HTTPException(...)

if contract.get("token_expires_at") and contract["token_expires_at"] < datetime.now(...):
    raise HTTPException(...)
```

**Recommendation:** Extract helper:
```python
async def _validate_contract_token(self, contract_id: str, token: str) -> dict:
    """Validate token and return contract or raise exception"""
    contract = await self.vendor_contracts.find_one({
        "_id": ObjectId(contract_id),
        "access_token": token
    })

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found or invalid token")

    if contract.get("token_expires_at") and contract["token_expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Contract link has expired")

    return contract
```

---

### 4.4 Error Handling: ACCEPTABLE

**Strengths:**
- Consistent error responses with HTTPException
- Logging at INFO and ERROR levels
- Clear error messages

**Concerns:**
```python
except Exception as e:
    logger.error(f"Error creating contract: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Failed to create contract: {str(e)}")
    # ✗ Leaks internal error to client
```

**Better:**
```python
except ValueError as e:
    logger.warning(f"Invalid input: {str(e)}")
    raise HTTPException(status_code=400, detail="Invalid input")
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    raise HTTPException(status_code=500, detail="An error occurred")
```

---

## 5. SPECIFIC FOCUS: Token-Based Vendor Portal Readiness

### 5.1 Access Control Pattern Assessment

**Current Pattern:**
```python
# Public endpoint with token
@router.get("/public/contracts/{contract_id}")
async def get_contract_for_vendor(contract_id: str, token: str = Query(...)):
    return await vendor_service.get_contract_by_token(contract_id, token)
```

**Assessment:** ✓ Pattern is sound but needs hardening for production portal

**For Vendor Portal Feature:**

```python
# Should support:
# 1. Single-vendor access (vendor can see only their contracts/quotes)
# 2. Role-based access (vendor can submit forms, not modify)
# 3. Audit trail (every action logged)

# Recommended implementation:
class VendorPortalToken(BaseModel):
    token: str  # Secure token
    vendor_id: str  # Which vendor
    scope: List[str]  # ["view_contract", "submit_form", "view_quote"]
    expires_at: datetime
    rate_limit: dict  # {"requests_per_minute": 10}
```

---

### 5.2 Quote Lifecycle and Contracts Integration

**Current State:**
- Quotes are managed in budget models
- Contracts can be created from quotes (`quote_id` field)
- But no explicit quote→contract conversion flow

**For New Feature (AI Quote Comparison):**

```python
# Current quote model is minimal:
class VendorQuote(BaseModel):
    id: PyObjectId
    quote_amount: float
    quote_details: Dict
    includes: List[str]
    excludes: List[str]
    status: str  # pending, accepted, rejected, expired

# Should add for comparison:
class VendorQuote(BaseModel):
    # ... existing fields ...

    # For AI comparison
    breakdown: Dict  # Line items for comparison
    value_score: Optional[float]  # AI assessment
    comparison_notes: Optional[str]

    # For contract conversion
    terms_conditions: Optional[str]
    payment_structure: Optional[List[Dict]]

    # Source tracking
    source: str  # "manual", "form_submission", "email"
    vendor_profile_id: Optional[str]
```

---

### 5.3 Contract Notes and Inline Comments

**Current State:** Contracts support:
- Section editing
- Custom clauses
- But NO inline comments/annotations

**For New Feature:**

```python
class ContractNote(BaseModel):
    id: PyObjectId
    contract_id: str
    section_id: str  # Which section
    position: int  # Character position
    content: str  # The note
    author_role: str  # "planner", "vendor"
    created_at: datetime
    resolved: bool

class VendorContract(BaseModel):
    # ... existing ...
    notes: List[ContractNote]  # Inline notes
    negotiation_status: str  # "pending_review", "commented", "agreed"
```

---

## 6. POSITIVE OBSERVATIONS

### 6.1 Thoughtful Design Patterns

**✓ Denormalization strategy:** Vendor info duplicated in contracts for historical accuracy
```python
vendor_name: str
vendor_email: str
vendor_phone: Optional[str]
# These are copied from profile, so if vendor changes name, old contracts preserve original
```

**✓ Soft deletes:** Vendors marked inactive rather than hard deleted
```python
is_active: bool  # Preserves audit trail
```

**✓ Comprehensive audit fields:**
```python
created_at: datetime
updated_at: datetime
created_by: str  # Always track who
```

---

### 6.2 Good Error Prevention

**✓ ObjectId validation:**
```python
def validate_object_id(id_str: str, field_name: str = "ID") -> ObjectId:
    if not id_str:
        raise HTTPException(...)
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(...)
```

**✓ Status state machine:** Only allows valid transitions
```python
if contract["status"] not in [ContractStatus.DRAFT.value, ContractStatus.PENDING_REVIEW.value]:
    raise HTTPException(status_code=400, detail="Contract cannot be modified after sent")
```

---

### 6.3 Security-Conscious Features

**✓ Internal notes removed from public response:**
```python
# Remove sensitive fields for vendor view
contract.pop("access_token", None)
contract.pop("internal_notes", None)
```

**✓ IP address logging for signatures:**
```python
signature_ip = request.client.host  # Could be used for verification
```

---

## 7. RECOMMENDATIONS SUMMARY

### Critical (Fix Before Production):
1. **Hash tokens in database** - Current plaintext storage unacceptable
2. **Implement transactions** - Payment updates need atomicity
3. **Add rate limiting** - Token endpoint vulnerable to brute force
4. **Fix authorization checks** - Verify wedding ownership before returning vendors
5. **Escape regex inputs** - MongoDB injection risk in search

### High Priority:
6. Add idempotency to state-changing operations (sign, pay)
7. Implement token revocation mechanism
8. Add comprehensive audit logging for vendor portal
9. Validate email fields with EmailStr type
10. Create database indexes for vendor queries

### Medium Priority:
11. Extract payment logic into separate service
12. Remove duplicate token validation code
13. Use $lookup for related data loads
14. Add contract notes/annotations structure
15. Improve error messages (remove internal details)

### Performance:
16. Create compound indexes on filtered queries
17. Consider caching for contract templates
18. Monitor slow logs for payment milestone queries

---

## 8. FILES REVIEWED

- `/app/models/vendor.py` - Models ✓
- `/app/api/vendor_management.py` - Routes ✓
- `/app/services/vendor_service.py` - Core logic ✓
- `/app/api/vendor_contract_public.py` - Public endpoints ✓
- `/app/services/vendorManagementApi.ts` - Frontend API client ✓
- `/app/admin/vendors/page.tsx` - Vendor management UI ✓
- `/app/admin/budget/page.tsx` - Budget integration ✓
- `/app/admin/budget/quotes/page.tsx` - Quote management ✓
- `/app/models/budget.py` - Budget models ✓

---

## 9. NEXT STEPS FOR VENDOR PORTAL FEATURE

1. **Week 1:** Implement token security hardening (hash, rate limit, rotation)
2. **Week 2:** Add transaction support for payment operations
3. **Week 3:** Implement vendor portal base with token validation
4. **Week 4:** Add inline contract notes structure
5. **Week 5:** Integrate AI quote comparison UI
6. **Week 6:** Testing and security audit

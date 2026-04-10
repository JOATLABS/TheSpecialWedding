# Technical Findings: Vendor Management System
## Code Examples and Detailed Analysis

---

## Section A: Security Vulnerabilities - Code Examples

### A.1 Token Security Issue: Plaintext Storage

**Current Implementation (VULNERABLE):**
```python
# vendor_service.py:817-820
contract = {
    # ...
    "access_token": self._generate_token(),  # Generated securely
    "token_expires_at": datetime.now(timezone.utc) + timedelta(
        days=planner_settings["token_expiry_days"]
    ),
    # ...
}

# Stored in MongoDB without hashing
result = await self.vendor_contracts.insert_one(contract)
```

**Attack Vector:**
1. DB breach exposes all active tokens
2. Attacker can sign contracts on behalf of vendors
3. No way to revoke tokens server-side

**Recommended Fix:**
```python
import hashlib
import hmac

class VendorService:
    def __init__(self):
        self.token_secret = os.getenv("TOKEN_SECRET", "")
        # ...

    def _generate_token(self, length: int = 32) -> str:
        """Generate a secure random token"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

    def _hash_token(self, token: str) -> str:
        """Hash token for database storage"""
        return hashlib.sha256(token.encode()).hexdigest()

    async def create_contract(self, ...):
        plain_token = self._generate_token()
        hashed_token = self._hash_token(plain_token)

        contract = {
            # ... fields ...
            "access_token_hash": hashed_token,  # Store hash only
            "token_expires_at": datetime.now(timezone.utc) + timedelta(days=30),
            "token_created_at": datetime.now(timezone.utc),
            # NEW: Track token usage
            "token_used_at": None,
            "token_rotation_secret": self._generate_token(),  # For rotation
        }

        await self.vendor_contracts.insert_one(contract)
        return plain_token  # Return to send in email

    async def get_contract_by_token(self, contract_id: str, token: str) -> dict:
        """Validate token and return contract"""
        hashed_token = self._hash_token(token)

        contract = await self.vendor_contracts.find_one({
            "_id": ObjectId(contract_id),
            "access_token_hash": hashed_token
        })

        if not contract:
            # Log failed attempt
            await self._log_token_failure(contract_id, token)
            raise HTTPException(status_code=403, detail="Access denied")

        # Check expiration
        if contract.get("token_expires_at") and contract["token_expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(status_code=403, detail="Link has expired")

        # Token rotation on first view (prevents sharing)
        if not contract.get("token_used_at"):
            new_token = self._generate_token()
            new_hash = self._hash_token(new_token)

            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {
                    "$set": {
                        "access_token_hash": new_hash,
                        "token_used_at": datetime.now(timezone.utc),
                        "token_rotation_secret": self._generate_token()
                    }
                }
            )

            # Log this for audit
            await self._log_communication(
                vendor_profile_id=contract.get("vendor_profile_id"),
                comm_type="contract_viewed",
                content=f"Contract accessed via token",
                created_by="vendor",  # Mark as vendor action
                contract_id=contract_id
            )

        self._serialize_doc(contract)
        contract.pop("access_token_hash", None)  # Never send hash to client
        return contract
```

**Database Schema Addition:**
```javascript
// Create unique index on token hash to prevent duplicates
db.vendor_contracts.createIndex({
    "access_token_hash": 1
}, { sparse: true })

// Track token attempts
db.token_failures.createIndex({
    "contract_id": 1,
    "timestamp": 1
})
```

---

### A.2 Authorization Bypass: Wedding Ownership Not Verified

**Current Code (VULNERABLE):**
```python
# vendor_service.py:549-558
async def get_wedding_vendors(self, wedding_id: str, created_by: str) -> List[dict]:
    """Get all vendors assigned to a wedding"""
    try:
        cursor = self.vendor_assignments.find({"wedding_id": wedding_id})
        # BUG: created_by parameter is never used!
        # A planner could query any wedding if they know the ID
        assignments = await cursor.to_list(length=100)
        # ...
```

**Attack Scenario:**
```
1. Planner A obtains wedding_id of Planner B (via URL enumeration)
2. Calls: GET /weddings/{wedding_b_id}/vendors
3. Returns all of Planner B's vendor assignments
4. Planner A now sees all vendor contact info, contracts, etc.
```

**Fix:**
```python
async def get_wedding_vendors(self, wedding_id: str, created_by: str) -> List[dict]:
    """Get all vendors assigned to a wedding (with authorization)"""
    try:
        # CRITICAL: Verify created_by owns this wedding
        wedding = await self._get_wedding(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        # Check ownership
        if wedding.get("created_by") != created_by:
            raise HTTPException(status_code=403, detail="You do not have access to this wedding")

        # Now safe to fetch
        cursor = self.vendor_assignments.find({
            "wedding_id": wedding_id,
            # Additional safety: require created_by match here too
            "created_by": created_by
        })
        assignments = await cursor.to_list(length=100)

        for a in assignments:
            a["_id"] = str(a["_id"])

        return assignments

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching wedding vendors: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch wedding vendors")
```

**API Route Protection:**
```python
# vendor_management.py:151-157
@router.get("/weddings/{wedding_id}/vendors")
async def get_wedding_vendors(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get all vendors assigned to a wedding"""
    # Verify access via the service (ownership check)
    return await vendor_service.get_wedding_vendors(
        wedding_id,
        current_user.email  # This must be checked against wedding owner
    )
```

---

### A.3 MongoDB Regex Injection

**Current Code (VULNERABLE):**
```python
# vendor_service.py:271-276
if search:
    query["$or"] = [
        {"business_name": {"$regex": search, "$options": "i"}},
        {"contact_name": {"$regex": search, "$options": "i"}},
        {"email": {"$regex": search, "$options": "i"}},
        {"service_description": {"$regex": search, "$options": "i"}}
    ]
```

**Attack Example:**
```python
# Attacker supplies:
search = ".*"  # Matches ANY vendor name (DoS)
search = "^admin"  # Pattern matching attack
search = "(.*)"  # Capturing groups (performance)
```

**Impact:** Information disclosure, DoS through expensive regex

**Fix:**
```python
import re

async def get_vendor_profiles(
    self,
    created_by: str,
    category: Optional[str] = None,
    is_preferred: Optional[bool] = None,
    search: Optional[str] = None,
    tags: Optional[List[str]] = None,
    skip: int = 0,
    limit: int = 50
) -> List[dict]:
    """Get vendor profiles for a planner with filtering"""
    try:
        query = {"created_by": created_by, "is_active": True}

        if category:
            query["service_category"] = category
        if is_preferred is not None:
            query["is_preferred"] = is_preferred
        if tags:
            query["tags"] = {"$all": tags}

        if search:
            # FIXED: Escape regex special characters
            if len(search) > 100:  # Prevent DoS
                raise HTTPException(status_code=400, detail="Search term too long")

            escaped_search = re.escape(search)

            query["$or"] = [
                {"business_name": {"$regex": escaped_search, "$options": "i"}},
                {"contact_name": {"$regex": escaped_search, "$options": "i"}},
                {"email": {"$regex": escaped_search, "$options": "i"}},
                {"service_description": {"$regex": escaped_search, "$options": "i"}}
            ]

        cursor = self.vendor_profiles.find(query).skip(skip).limit(limit).sort("business_name", 1)
        vendors = await cursor.to_list(length=limit)

        for v in vendors:
            v["_id"] = str(v["_id"])
            if isinstance(v.get("created_at"), datetime):
                v["created_at"] = v["created_at"].isoformat()
            if isinstance(v.get("updated_at"), datetime):
                v["updated_at"] = v["updated_at"].isoformat()

        return vendors

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid filter parameters: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch vendor profiles: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch vendors")
```

---

## Section B: Data Consistency Issues - Transaction Examples

### B.1 Payment Recording Without Transactions

**Current Code (NOT TRANSACTIONAL):**
```python
# vendor_service.py:1549-1636
async def record_payment(
    self,
    milestone_id: str,
    amount: float,
    payment_method: str,
    created_by: str,
    payment_date: Optional[datetime] = None,
    notes: Optional[str] = None,
    receipt_url: Optional[str] = None,
    stripe_payment_intent_id: Optional[str] = None
) -> dict:
    """
    Record a payment against a milestone.

    Note: This method updates multiple collections without using MongoDB transactions.
    In rare cases of partial failure, manual reconciliation may be needed.
    """
    try:
        milestone = await self.payment_milestones.find_one({"_id": ObjectId(milestone_id)})
        if not milestone:
            raise HTTPException(status_code=404, detail="Milestone not found")

        new_paid_amount = milestone.get("paid_amount", 0) + amount

        # Determine new status
        if new_paid_amount >= milestone["amount"]:
            new_status = PaymentMilestoneStatus.PAID.value
        elif new_paid_amount > 0:
            new_status = PaymentMilestoneStatus.PARTIAL.value
        else:
            new_status = milestone["status"]

        # UPDATE 1: Payment Milestone
        await self.payment_milestones.update_one(
            {"_id": ObjectId(milestone_id)},
            {"$set": {
                "paid_amount": new_paid_amount,
                "status": new_status,
                "payment_method": payment_method,
                "paid_at": payment_date or datetime.now(timezone.utc),
                "notes": notes,
                "receipt_url": receipt_url,
                "updated_at": datetime.now(timezone.utc)
            }}
        )  # SUCCESS - milestone recorded

        # UPDATE 2: Vendor Assignment (could FAIL)
        await self.vendor_assignments.update_one(
            {
                "vendor_profile_id": milestone["vendor_profile_id"],
                "wedding_id": milestone["wedding_id"]
            },
            {"$inc": {"paid_amount": amount}}
        )  # Problem: If this fails, milestone is paid but assignment is not

        # UPDATE 3: Vendor Profile (could FAIL)
        await self.vendor_profiles.update_one(
            {"_id": ObjectId(milestone["vendor_profile_id"])},
            {"$inc": {"total_revenue": amount}}
        )  # Problem: If this fails, payment is recorded but vendor stats are wrong

        # UPDATE 4: Budget Category (could FAIL)
        await self.budget_categories.update_one(
            {"_id": ObjectId(milestone["budget_category_id"])},
            {"$inc": {"actual_spent": amount}}
        )  # Problem: If this fails, everything above is wrong

        updated = await self.payment_milestones.find_one({"_id": ObjectId(milestone_id)})
        if not updated:
            raise HTTPException(status_code=404, detail="Milestone not found after update")
        updated["_id"] = str(updated["_id"])

        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record payment")
```

**Problem Scenario:**
```
Time:  Event:
T1:    Payment of $5000 recorded against milestone
T2:    Milestone status = PAID (database)
T3:    vendor_assignments updated (+$5000)
T4:    vendor_profiles updated (+$5000)
T5:    Network timeout when updating budget_categories!
Result:
  - Milestone: Shows paid ✓
  - Assignment: Shows $5000 paid ✓
  - Vendor: Shows $5000 revenue ✓
  - Budget: Still shows OLD amount (MISMATCH!)

  Reconciliation needed manually. Audit trail broken.
```

**Transactional Fix:**
```python
async def record_payment(
    self,
    milestone_id: str,
    amount: float,
    payment_method: str,
    created_by: str,
    payment_date: Optional[datetime] = None,
    notes: Optional[str] = None,
    receipt_url: Optional[str] = None,
    stripe_payment_intent_id: Optional[str] = None
) -> dict:
    """Record a payment against a milestone with full consistency."""

    try:
        # Get the milestone first (outside transaction for read)
        milestone = await self.payment_milestones.find_one({"_id": ObjectId(milestone_id)})
        if not milestone:
            raise HTTPException(status_code=404, detail="Milestone not found")

        # Validate related records exist
        vendor = await self.vendor_profiles.find_one({"_id": ObjectId(milestone.get("vendor_profile_id"))})
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        budget = await self.budget_categories.find_one({"_id": ObjectId(milestone.get("budget_category_id"))})
        if not budget:
            raise HTTPException(status_code=404, detail="Budget category not found")

        # Calculate new status
        new_paid_amount = milestone.get("paid_amount", 0) + amount
        if new_paid_amount >= milestone["amount"]:
            new_status = PaymentMilestoneStatus.PAID.value
        elif new_paid_amount > 0:
            new_status = PaymentMilestoneStatus.PARTIAL.value
        else:
            new_status = milestone["status"]

        # TRANSACTIONAL: All or nothing
        async with await self.client.start_session() as session:
            async with session.start_transaction():
                # UPDATE 1: Payment Milestone
                await self.payment_milestones.update_one(
                    {"_id": ObjectId(milestone_id)},
                    {
                        "$set": {
                            "paid_amount": new_paid_amount,
                            "status": new_status,
                            "payment_method": payment_method,
                            "paid_at": payment_date or datetime.now(timezone.utc),
                            "notes": notes,
                            "receipt_url": receipt_url,
                            "stripe_payment_intent_id": stripe_payment_intent_id,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    },
                    session=session
                )

                # UPDATE 2: Vendor Assignment
                await self.vendor_assignments.update_one(
                    {
                        "vendor_profile_id": milestone["vendor_profile_id"],
                        "wedding_id": milestone["wedding_id"]
                    },
                    {"$inc": {"paid_amount": amount}},
                    session=session
                )

                # UPDATE 3: Vendor Profile
                await self.vendor_profiles.update_one(
                    {"_id": ObjectId(milestone["vendor_profile_id"])},
                    {"$inc": {"total_revenue": amount}},
                    session=session
                )

                # UPDATE 4: Budget Category
                await self.budget_categories.update_one(
                    {"_id": ObjectId(milestone["budget_category_id"])},
                    {"$inc": {"actual_spent": amount}},
                    session=session
                )

                # Log the transaction (inside transaction for consistency)
                await self.vendor_communications.insert_one(
                    {
                        "vendor_profile_id": milestone["vendor_profile_id"],
                        "wedding_id": milestone["wedding_id"],
                        "type": "payment_recorded",
                        "content": f"Payment of ${amount} recorded",
                        "direction": "system",
                        "created_by": created_by,
                        "created_at": datetime.now(timezone.utc)
                    },
                    session=session
                )

        # Read updated record (outside transaction)
        updated = await self.payment_milestones.find_one({"_id": ObjectId(milestone_id)})
        if not updated:
            raise HTTPException(status_code=404, detail="Milestone not found after update")

        updated["_id"] = str(updated["_id"])
        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording payment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record payment")
```

---

### B.2 Contract Signing Without Transaction

**Current Code (PROBLEMATIC):**
```python
# vendor_service.py:1077-1173
async def sign_contract(self, contract_id: str, token: str, ...):
    # ... validation ...

    # UPDATE 1: Mark contract as signed
    await self.vendor_contracts.update_one(
        {"_id": ObjectId(contract_id)},
        {"$set": {
            "status": ContractStatus.SIGNED.value,
            "signed_at": datetime.now(timezone.utc),
            "signed_by_name": signer_name,
            "signed_by_email": signer_email,
            "signature_ip": signature_ip,
            "updated_at": datetime.now(timezone.utc)
        }}
    )  # SUCCESS but...

    # UPDATE 2: Update assignment
    if contract.get("vendor_profile_id"):
        await self.vendor_assignments.update_one(
            {
                "vendor_profile_id": contract["vendor_profile_id"],
                "wedding_id": contract["wedding_id"]
            },
            {
                "$set": {
                    "status": "contracted",
                    "contract_id": contract_id,
                    "contracted_amount": contract["total_amount"],
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )  # Could fail

    # EXTERNAL SIDE EFFECT: Send email (irreversible!)
    planner_email = contract["created_by"]
    # ... email HTML ...
    await self.email_service.send_email(
        to_email=planner_email,
        subject=f"Contract Signed: {contract['vendor_name']}",
        html_content=html_content,
        from_name="Wedding Platform"
    )  # If this fails, contract shows signed but planner not notified
```

**Problems:**
1. Contract may be signed but assignment not updated
2. Email sent after state changes (no atomicity)
3. If email fails, vendor sees no notification
4. No idempotency - retry will send email twice

**Better Implementation:**
```python
async def sign_contract(
    self,
    contract_id: str,
    token: str,
    signer_name: str,
    signer_email: str,
    signature_ip: Optional[str] = None
) -> dict:
    """Sign a contract with proper transaction handling."""

    try:
        # Validate and get contract
        contract = await self.vendor_contracts.find_one({
            "_id": ObjectId(contract_id),
            "access_token_hash": self._hash_token(token)  # Use hashed token
        })

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found or invalid token")

        if contract["status"] == ContractStatus.SIGNED.value:
            raise HTTPException(status_code=400, detail="Contract has already been signed")

        if contract["status"] not in [ContractStatus.SENT.value, ContractStatus.VIEWED.value]:
            raise HTTPException(status_code=400, detail="Contract cannot be signed in current state")

        # Create idempotency key
        idempotency_key = f"{contract_id}:{signer_email}:{datetime.now(timezone.utc).date()}"

        # Check if already signed today (idempotency)
        existing_signature = await self.vendor_communications.find_one({
            "contract_id": contract_id,
            "type": "contract_signed",
            "created_by": signer_email,
            "created_at": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)}
        })

        if existing_signature:
            logger.warning(f"Duplicate signing attempt for contract {contract_id}")
            return {
                "message": "Contract signed successfully",
                "signed_at": existing_signature["created_at"].isoformat()
            }

        # TRANSACTIONAL: Sign contract and update assignment
        now = datetime.now(timezone.utc)

        async with await self.client.start_session() as session:
            async with session.start_transaction():
                # Update contract
                await self.vendor_contracts.update_one(
                    {"_id": ObjectId(contract_id)},
                    {
                        "$set": {
                            "status": ContractStatus.SIGNED.value,
                            "signed_at": now,
                            "signed_by_name": signer_name,
                            "signed_by_email": signer_email,
                            "signature_ip": signature_ip,
                            "updated_at": now
                        }
                    },
                    session=session
                )

                # Update assignment if applicable
                if contract.get("vendor_profile_id"):
                    await self.vendor_assignments.update_one(
                        {
                            "vendor_profile_id": contract["vendor_profile_id"],
                            "wedding_id": contract["wedding_id"]
                        },
                        {
                            "$set": {
                                "status": "contracted",
                                "contract_id": contract_id,
                                "contracted_amount": contract["total_amount"],
                                "updated_at": now
                            }
                        },
                        session=session
                    )

                # Log the signing (inside transaction)
                await self.vendor_communications.insert_one(
                    {
                        "vendor_profile_id": contract.get("vendor_profile_id"),
                        "wedding_id": contract["wedding_id"],
                        "contract_id": contract_id,
                        "type": "contract_signed",
                        "subject": f"Contract Signed by {signer_name}",
                        "content": f"Contract signed by {signer_name} ({signer_email}) at {now.isoformat()}",
                        "direction": "incoming",
                        "received_from": signer_email,
                        "created_by": signer_email,
                        "created_at": now
                    },
                    session=session
                )

        # AFTER transaction succeeds: Send notification (not part of transaction)
        planner_email = contract["created_by"]

        try:
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Contract Signed!</h2>
                <p>Great news! {contract['vendor_name']} has signed the contract.</p>
                <div style="background: #f3f4f6; padding: 15px; border-radius: 6px;">
                    <p><strong>Contract:</strong> {contract['contract_title']}</p>
                    <p><strong>Signed by:</strong> {signer_name}</p>
                    <p><strong>Email:</strong> {signer_email}</p>
                    <p><strong>Signed at:</strong> {now.strftime('%B %d, %Y at %H:%M UTC')}</p>
                </div>
                <p>Log in to your dashboard to view the signed contract and next steps.</p>
            </body>
            </html>
            """

            email_result = await self.email_service.send_email(
                to_email=planner_email,
                subject=f"Contract Signed: {contract['vendor_name']}",
                html_content=html_content,
                from_name="Wedding Platform"
            )

            if not email_result.get("success"):
                logger.error(f"Failed to send signing notification to {planner_email}")
                # Don't raise - contract is already signed
                # Email failure shouldn't break the flow

        except Exception as e:
            logger.error(f"Error sending contract signing email: {str(e)}")
            # Log but don't raise - contract is already signed

        return {
            "message": "Contract signed successfully",
            "signed_at": now.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error signing contract: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to sign contract")
```

---

## Section C: Database Optimization

### C.1 Missing Indexes

**Create These Indexes:**
```javascript
// Vendor profiles - common queries
db.vendor_profiles.createIndex({
    "created_by": 1,
    "is_active": 1,
    "service_category": 1
})

db.vendor_profiles.createIndex({
    "created_by": 1,
    "is_preferred": 1
})

db.vendor_profiles.createIndex({
    "business_name": 1,
    "created_by": 1
})

// Vendor contracts - filtering and sorting
db.vendor_contracts.createIndex({
    "created_by": 1,
    "wedding_id": 1,
    "status": 1
})

db.vendor_contracts.createIndex({
    "wedding_id": 1,
    "vendor_profile_id": 1
})

db.vendor_contracts.createIndex({
    "status": 1,
    "created_at": -1
})

// Payment milestones - tracking overdue
db.vendor_payment_milestones.createIndex({
    "wedding_id": 1,
    "status": 1,
    "due_date": 1
})

db.vendor_payment_milestones.createIndex({
    "contract_id": 1,
    "status": 1
})

// Vendor assignments - quick lookups
db.vendor_assignments.createIndex({
    "vendor_profile_id": 1,
    "wedding_id": 1
}, { unique: true })  // Prevent duplicates!

db.vendor_assignments.createIndex({
    "wedding_id": 1,
    "status": 1
})

// Communication history
db.vendor_communications.createIndex({
    "vendor_profile_id": 1,
    "created_at": -1
})

db.vendor_communications.createIndex({
    "contract_id": 1,
    "created_at": -1
})
```

---

## Section D: Query Performance Analysis

### D.1 Good: Dashboard Count Queries

**Query Pattern (EFFICIENT):**
```python
vendor_total = await self.vendor_profiles.count_documents({
    "created_by": created_by,
    "is_active": True
})
```

**Execution:** O(1) with index on (created_by, is_active)
**Recommended Index:** Already covered above ✓

---

### D.2 Potential Issue: Vendor Search with Regex

**Current Query:**
```python
cursor = self.vendor_profiles.find(query).skip(skip).limit(limit).sort("business_name", 1)
```

**When search contains $or with regex:**
```python
query = {
    "created_by": "planner@example.com",
    "is_active": True,
    "$or": [
        {"business_name": {"$regex": "photo", "$options": "i"}},
        {"service_description": {"$regex": "photo", "$options": "i"}},
        # ... more
    ]
}
```

**Issue:** MongoDB must scan all matching documents before skip/limit

**Recommendation:** Use text indexes for better performance
```javascript
// Create text index
db.vendor_profiles.createIndex({
    "business_name": "text",
    "service_description": "text",
    "contact_name": "text"
})

// Then use text search (more efficient)
db.vendor_profiles.find({
    "created_by": "planner@example.com",
    "is_active": true,
    "$text": {"$search": "photo"}
})
```

---

## Section E: Frontend Integration Observations

### E.1 Frontend API Error Handling (GOOD)

**Location:** `/app/services/vendorManagementApi.ts:18-27`

```typescript
function extractErrorMessage(errBody: any, fallback: string): string {
  const detail = errBody?.detail;
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (typeof detail === 'object' && !Array.isArray(detail) && detail.message) return detail.message;
  if (Array.isArray(detail) && detail.length > 0 && detail[0].msg) {
    return detail.map((d: any) => d.msg).join('; ');
  }
  return fallback;
}
```

**Strength:** Handles multiple error response formats from FastAPI

---

### E.2 Token Passing Pattern (NEEDS HARDENING)

**Location:** `/app/services/vendorManagementApi.ts:1035-1053`

```typescript
export async function getPublicContract(
  contractId: string,
  accessToken: string
): Promise<PublicContract> {
  const response = await fetch(
    `${API_BASE}/vendor-contract/public/contracts/${contractId}?token=${accessToken}`
  );
  // ...
}
```

**Issue:** Token in URL query parameter
- Visible in browser history
- Logged by servers/proxies
- Can appear in referrer headers

**Better:**
```typescript
export async function getPublicContract(
  contractId: string,
  accessToken: string
): Promise<PublicContract> {
  const response = await fetch(
    `${API_BASE}/vendor-contract/public/contracts/${contractId}`,
    {
      headers: {
        'X-Contract-Token': accessToken  // Use custom header
      }
    }
  );

  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Access denied - link may have expired');
    }
    // ...
  }

  return response.json();
}
```

**Backend:**
```python
@router.get("/public/contracts/{contract_id}")
async def get_contract_for_vendor(
    contract_id: str,
    request: Request  # Get headers
):
    token = request.headers.get("X-Contract-Token") or request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=400, detail="Missing token")

    return await vendor_service.get_contract_by_token(contract_id, token)
```

---

## Summary of Code Examples Provided

| Issue | File | Line | Severity | Status |
|-------|------|------|----------|--------|
| Token plaintext storage | vendor_service.py | 817-820 | CRITICAL | Code examples provided above |
| Authorization bypass | vendor_service.py | 549-558 | HIGH | Fix provided above |
| MongoDB injection | vendor_service.py | 271-276 | MEDIUM | Fix provided above |
| Missing transactions | vendor_service.py | 1549-1636 | CRITICAL | Implementation provided above |
| Contract signing issues | vendor_service.py | 1077-1173 | CRITICAL | Refactored code provided above |
| Token in URL | vendorManagementApi.ts | 1040 | MEDIUM | Alternative provided above |

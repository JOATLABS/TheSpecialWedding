# QA Findings - Fix Implementation Guide

This guide provides code snippets and step-by-step instructions to fix critical AI feature issues.

---

## FIX #1: CRITICAL - Seating Optimization Parameter Mismatch

**Severity:** CRITICAL | **Time:** 1-2 hours | **Files:** 2

### Root Cause
Frontend sends incomplete guest data to seating optimization endpoint. Backend expects fields for accessibility, dietary restrictions, language preferences, and relationship constraints.

### File 1: Backend - Update SeatingOptimizeRequest Model
**File:** `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py`
**Location:** Around line 317

**Current Code:**
```python
class SeatingOptimizeRequest(BaseModel):
    guests: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    constraints: Optional[Dict[str, Any]] = None
    force_refresh: bool = False
```

**This is actually CORRECT** - it accepts any Dict[str, Any], so the issue is frontend not sending all data.

### File 2: Frontend - Update Seating Request
**File:** `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/admin/weddings/[id]/seating/page.tsx`
**Location:** Around line 144-162

**Current Code:**
```typescript
body: JSON.stringify({
  guests: guests.map(g => ({
    id: g.id,
    name: g.name,
    group_id: g.group_id,
    role: g.role,
    current_table_id: g.table_id
  })),
  tables: tables.map(t => ({
    id: t.id,
    name: t.name,
    capacity: t.capacity,
    shape: t.shape
  })),
  constraints: {
    keep_groups_together: true,
    respect_roles: true
  }
})
```

**Fixed Code:**
```typescript
body: JSON.stringify({
  guests: guests.map(g => ({
    id: g.id,
    name: g.name,
    group_id: g.group_id,
    role: g.role,
    plus_one_allowed: g.plus_one_allowed,
    number_of_plus_ones_allowed: g.number_of_plus_ones_allowed || 0,
    accessibility_needs: g.accessibility_needs || null,
    age_group: g.age_group || null,
    language_preference: g.language_preference || null,
    seating_preference: g.seating_preference || null,
    must_sit_with: g.must_sit_with || [],
    must_sit_apart: g.must_sit_apart || []
  })),
  tables: tables.map(t => ({
    id: t.id,
    name: t.name,
    capacity: t.capacity,
    shape: t.shape
  })),
  constraints: {
    keep_groups_together: true,
    respect_roles: true
  }
})
```

**Changes Made:**
- Added all fields expected by backend seating optimization logic (lines 865-882 in ai.py)
- Include plus_one fields for party size calculation
- Include accessibility_needs for special placement logic
- Include language_preference for multilingual weddings
- Include seating_preference for guest preferences
- Include must_sit_with and must_sit_apart arrays for relationship constraints

**Verification:**
After fix, the backend will receive complete guest data and:
1. Properly calculate party sizes (1 + plus_ones)
2. Place guests with accessibility needs near exits
3. Keep relationship constraints (must sit together/apart)
4. Group by language for multilingual events

---

## FIX #2: HIGH - Missing AI Client Check on Seating Endpoint

**Severity:** HIGH | **Time:** 15 minutes | **Files:** 1

**File:** `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py`
**Location:** Around line 796-810

**Current Code:**
```python
@router.post("/weddings/{wedding_id}/seating-optimize")
async def optimize_seating(
    wedding_id: str,
    request: SeatingOptimizeRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    AI-powered seating optimization.

    Cost varies by guest count:
    - ≤50 guests: 2 credits
    - 51-150 guests: 5 credits
    - 150+ guests: 10 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
```

**Fixed Code:**
```python
@router.post("/weddings/{wedding_id}/seating-optimize")
async def optimize_seating(
    wedding_id: str,
    request: SeatingOptimizeRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    AI-powered seating optimization.

    Cost varies by guest count:
    - ≤50 guests: 2 credits
    - 51-150 guests: 5 credits
    - 150+ guests: 10 credits
    """
    try:
        # Check if AI service is properly initialized
        if not ai_service._client:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "ai_not_configured",
                    "message": "AI service is not configured. Please contact the administrator.",
                    "hint": "GEMINI_API_KEY environment variable may be missing."
                }
            )

        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
```

**Changes Made:**
- Added AI client check immediately after authentication
- Uses same pattern as budget_insights endpoint (line 519-527)
- Provides clear error message if AI not configured
- Matches behavior of other AI endpoints

---

## FIX #3: HIGH - CRON_SECRET Security Issue

**Severity:** HIGH | **Time:** 30 minutes | **Files:** 1

**File:** `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/autopilot.py`
**Location:** Around line 23-43

**Current Code:**
```python
# Cron secret for securing internal endpoints
CRON_SECRET = os.getenv("CRON_SECRET", "")


def verify_cron_auth(authorization: Optional[str] = Header(None)):
    """Verify cron job authorization."""
    if not CRON_SECRET:
        # If no secret configured, allow (for development)
        logger.warning("CRON_SECRET not configured - cron endpoints are unprotected")
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")

    # Check Bearer token
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        if token == CRON_SECRET:
            return True

    raise HTTPException(status_code=401, detail="Invalid cron authorization")
```

**Fixed Code:**
```python
import sys

# Cron secret for securing internal endpoints - REQUIRED in production
CRON_SECRET = os.getenv("CRON_SECRET", "")

# Validate on startup
if not CRON_SECRET:
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production" or env == "coolify":
        logger.error("CRON_SECRET must be configured for production deployment")
        logger.error("Set the CRON_SECRET environment variable in your deployment configuration")
        sys.exit(1)
    else:
        logger.warning("CRON_SECRET not configured - cron endpoints are unprotected in development")


def verify_cron_auth(authorization: Optional[str] = Header(None)):
    """Verify cron job authorization."""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )

    # Check Bearer token
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        if token == CRON_SECRET and CRON_SECRET:  # Must have configured secret
            logger.info(f"Cron job authorized")
            return True

    logger.warning(f"Failed cron authorization attempt")
    raise HTTPException(
        status_code=401,
        detail="Invalid cron authorization"
    )
```

**Changes Made:**
- CRON_SECRET now required in production (checked at startup)
- Development mode still allows unprotected access
- Better error messages during startup (not just logs)
- Always requires Bearer token (no silent fallback)
- Added audit logging for authorization attempts

**Configuration:**
In Coolify environment variables, set:
```
ENVIRONMENT=coolify
CRON_SECRET=<your-secure-random-string>
```

Generate a secure secret:
```bash
openssl rand -hex 32
# Output: 8f2a9c4b5e1d7f3a2c9e4b1a5d8f2c4e8a1b5d9e2f4a8c1e5b9d2f6a0c4e8
```

---

## FIX #4: HIGH - Payment Forecast Response Format Mismatch

**Severity:** HIGH | **Time:** 30 minutes | **Files:** 2

### Option A: Backend - Wrap Response (RECOMMENDED)

**File:** `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py`
**Location:** Around line 1800-1821

**Current Code:**
```python
        return {
            "forecast_periods": result["response"].get("forecast_periods", []),
            "cash_flow_warning": result["response"].get("cash_flow_warning"),
            "peak_payment_dates": result["response"].get("peak_payment_dates", []),
            "recommendations": result["response"].get("recommendations", []),
            "summary": result["response"].get("summary", {}),
            "cached": result["cached"],
            "credits_used": result["credits_used"]
        }
```

**Fixed Code:**
```python
        return {
            "forecast": {
                "forecast_periods": result["response"].get("forecast_periods", []),
                "cash_flow_warning": result["response"].get("cash_flow_warning"),
                "peak_payment_dates": result["response"].get("peak_payment_dates", []),
                "recommendations": result["response"].get("recommendations", []),
                "summary": result["response"].get("summary", {})
            },
            "cached": result["cached"],
            "credits_used": result["credits_used"]
        }
```

**Changes Made:**
- Wrapped forecast data in "forecast" key
- Maintains consistent structure with other endpoints
- Frontend code stays unchanged

### Option B: Frontend - Adjust Data Access (Alternative)

**File:** `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/admin/money/page.tsx`
**Location:** Around line 195-210

**Current Code:**
```typescript
      const data = await response.json();
      setAiForecast(data.forecast);
```

**Fixed Code (if choosing Option B):**
```typescript
      const data = await response.json();
      setAiForecast(data);  // Use entire response directly
      // Update TypeScript types to match flat structure
```

**RECOMMENDATION:** Use Option A (backend) for consistency with other endpoints.

---

## FIX #5: MEDIUM - Payment AI Features Not Integrated

**Severity:** MEDIUM | **Time:** 2 hours | **Files:** 2+

This is a feature integration, not a quick fix. The backend endpoints exist but frontend never calls them.

### What's Missing:
1. Frontend doesn't call `/admin/autopilot/ai/retry-timing/{payment_id}`
2. Frontend doesn't call `/admin/autopilot/ai/success-prediction/{payment_id}`
3. Money dashboard doesn't display AI payment risk assessment

### Implementation Steps:

1. **Add Risk Assessment UI to Money Dashboard**
   File: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/admin/money/page.tsx`

   Add new component after payment forecast:
   ```typescript
   // Fetch risk assessment for each scheduled payment
   async function fetchPaymentRiskAssessment(paymentId: string) {
     const response = await fetch(
       `${baseUrl}/admin/autopilot/ai/success-prediction/${paymentId}`,
       { headers: { 'Authorization': `Bearer ${adminToken}` } }
     );
     return response.json();
   }

   // Display as part of payment list
   ```

2. **Integrate Retry Timing Suggestions**
   Add to payment retry logic:
   ```typescript
   // Before retrying failed payment
   const timing = await fetch(
     `${baseUrl}/admin/autopilot/ai/retry-timing/${paymentId}`,
     { headers: { 'Authorization': `Bearer ${adminToken}` } }
   );
   const suggestion = await timing.json();
   // Use suggestion.suggested_retry_date and suggested_retry_time
   ```

### Recommendation:
Consider this a Phase 2 improvement. For RSVP launch, focus on critical fixes first.

---

## Verification Checklist

After implementing fixes:

```
[ ] FIX #1: Seating requests include all guest fields
    - Verify with browser DevTools Network tab
    - Check request body includes: plus_one_allowed, accessibility_needs, etc.

[ ] FIX #2: Seating endpoint returns 503 if AI not configured
    - Disable GEMINI_API_KEY env var
    - Attempt seating optimization
    - Should get "ai_not_configured" error

[ ] FIX #3: CRON_SECRET required in production
    - Start app with ENVIRONMENT=coolify but no CRON_SECRET
    - Should fail on startup with clear error message
    - Start with CRON_SECRET set
    - Should succeed

[ ] FIX #4: Payment forecast displays correctly
    - Generate forecast for wedding with scheduled payments
    - Should show forecast_periods, recommendations, etc.
    - UI should not show empty state

[ ] All endpoints return proper error codes
    - 402: Insufficient credits
    - 403: No wedding access
    - 404: Wedding not found
    - 503: AI not configured
    - 500: Unexpected error
```

---

## Testing Commands

### Test Seating with cURL
```bash
curl -X POST \
  'http://localhost:8000/admin/ai/weddings/WEDDING_ID/seating-optimize' \
  -H 'Authorization: Bearer TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "guests": [
      {
        "id": "guest1",
        "name": "John Doe",
        "group_id": "family",
        "role": "friend",
        "plus_one_allowed": true,
        "accessibility_needs": null,
        "age_group": "adult",
        "language_preference": "en"
      }
    ],
    "tables": [
      {
        "id": "table1",
        "name": "Table 1",
        "capacity": 8
      }
    ]
  }'
```

### Test CRON Auth
```bash
# Should fail - no CRON_SECRET
curl -X POST 'http://localhost:8000/admin/autopilot/process-due-payments'
# Response: 401 Unauthorized

# Should succeed - with valid CRON_SECRET
curl -X POST 'http://localhost:8000/admin/autopilot/process-due-payments' \
  -H 'Authorization: Bearer YOUR_CRON_SECRET'
```

### Test Payment Forecast
```bash
curl -X GET \
  'http://localhost:8000/admin/ai/weddings/WEDDING_ID/payment-forecast' \
  -H 'Authorization: Bearer TOKEN'

# Should return forecast key with periods, recommendations, etc.
```

---

## Rollback Plan

If issues occur after fixes:

1. **Revert seating request change** - Comment out new fields, backend still accepts
2. **Revert CRON_SECRET check** - Restore original code (less secure but functional)
3. **Revert payment forecast** - Use Option B (frontend adjustment) instead
4. **Disable AI features** - Set GEMINI_API_KEY="" to gracefully disable

---

## Timeline

| Fix | Time | Priority | Impact |
|-----|------|----------|--------|
| #1: Seating params | 1-2h | CRITICAL | Wedding guest seating |
| #2: AI client check | 15m | HIGH | Error consistency |
| #4: Payment forecast | 30m | HIGH | Financial dashboard |
| #3: CRON security | 30m | HIGH | Payment processing |
| #5: Payment AI | 2h | MEDIUM | Enhancement, not blocking |

**Total estimated time:** 4-5 hours for all critical fixes

---

## Questions?

Refer to the detailed findings report:
`/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/QA_REVIEW_AI_FEATURES.md`

Each issue includes detailed explanation of root cause, impact, and recommendations.

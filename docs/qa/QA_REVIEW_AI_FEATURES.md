# QA/Dev Review: AI Features Architecture Alignment

**Review Date:** 2026-03-01
**Reviewer:** AI QA Agent
**Codebase:** WeddingWebApp (feature-twilio-otp-improvement-final-submitted branch)
**Status:** CRITICAL ISSUES FOUND - Wedding launch at risk

---

## Executive Summary

This comprehensive review of the AI features in the wedding SaaS platform reveals **10 critical to medium severity issues** that could impact the wedding RSVP launch. The primary concern is a **parameter mismatch in the seating optimization endpoint** that will cause failures when planners attempt to use AI seating suggestions. Additionally, there are gaps in error handling, feature gating consistency, and missing endpoint integrations for payment-related AI features.

**Risk Level:** **CRITICAL** - The planned RSVP launch (2 weeks) depends on stable AI features.

---

## Issues Found

### ISSUE #1: CRITICAL - Seating Optimization Parameter Mismatch

**SEVERITY:** CRITICAL
**CATEGORY:** Parameter Mismatch
**LOCATION:** Frontend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/admin/weddings/[id]/seating/page.tsx` → Backend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py`

**DESCRIPTION:**

The frontend sends a `current_table_id` field that the backend does not expect. The backend's `SeatingOptimizeRequest` model only accepts `guests` and `tables` arrays, but the frontend is sending additional guest fields:

**Frontend sends (line 144-162):**
```typescript
body: JSON.stringify({
  guests: guests.map(g => ({
    id: g.id,
    name: g.name,
    group_id: g.group_id,
    role: g.role,
    current_table_id: g.table_id  // ← NOT EXPECTED BY BACKEND
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

**Backend expects (ai.py line 317-321):**
```python
class SeatingOptimizeRequest(BaseModel):
    guests: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    constraints: Optional[Dict[str, Any]] = None
    force_refresh: bool = False
```

**Backend processes (ai.py line 865-882):**
```python
for g in request.guests:
    guest_id: str = g.get("id") or g.get("_id") or ""
    guest_data = {
        "id": guest_id,
        "name": g.get("name"),
        "group": g.get("group_id"),
        "role": g.get("role"),
        "plus_one": g.get("plus_one_allowed"),  # NOT SENT BY FRONTEND
        "party_size": ...,
        "dietary": ...,
        "accessibility": ...,
        "age_group": ...,
        "language": ...,
        "seating_pref": ...
    }
```

**IMPACT:**
- Planners clicking "AI Suggest" for seating will experience unexpected response parsing
- The backend gracefully accepts extra fields via `Dict[str, Any]`, but frontend sends incomplete data
- Backend expects and uses fields NOT sent by frontend (plus_one_allowed, accessibility_needs, age_group, language_preference, seating_preference)
- AI seating optimization will lack critical information for quality suggestions
- Guests with accessibility needs will not be properly placed
- Plus-one logic will be ignored

**AFFECTED ENDPOINTS:**
- POST `/admin/ai/weddings/{wedding_id}/seating-optimize`

**REMEDIATION:**
1. Update frontend to send all fields expected by backend:
   - `plus_one_allowed`
   - `number_of_plus_ones_allowed`
   - `accessibility_needs`
   - `age_group`
   - `language_preference`
   - `seating_preference`
   - `must_sit_with[]` (relationships)
   - `must_sit_apart[]` (conflicts)

2. OR: Update backend SeatingOptimizeRequest model to document required vs optional fields

3. Update frontend type definitions to match backend expectations

---

### ISSUE #2: HIGH - Missing AI Feature Gating on Seating Endpoint

**SEVERITY:** HIGH
**CATEGORY:** Missing Error Handling / Security
**LOCATION:** Backend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py` (line 796-945)

**DESCRIPTION:**

The seating optimization endpoint (`POST /admin/ai/weddings/{wedding_id}/seating-optimize`) does NOT check if the user has access to the AI feature. It only checks:
1. Wedding access (line 814)
2. Wedding existence (line 821)
3. Valid guests/tables (line 825)

But does NOT call `require_feature("ai_tools")` or check subscription AI credits availability.

**COMPARISON - Budget Insights endpoint (line 506-628) properly checks:**
```python
async def get_budget_insights(
    wedding_id: str,
    force_refresh: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    # ✓ Checks AI client initialization (line 519)
    # ✓ Will fail with credit check in ai_service.generate() (line 606)
```

**Seating endpoint MISSING:**
```python
async def optimize_seating(
    wedding_id: str,
    request: SeatingOptimizeRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)  # ← Only basic auth
):
    # ✗ NO AI client check
    # ✗ NO feature gate check
    # ✗ Will fail at ai_service.generate() but not gracefully
```

**IMPACT:**
- Planners without AI features enabled could trigger expensive API calls
- No early feedback before attempting to process guests/tables
- Inconsistent user experience across AI endpoints
- Potential for unauthorized feature access if credit checks are bypassed

**REMEDIATION:**
Add to seating endpoint before line 810:
```python
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
```

---

### ISSUE #3: MEDIUM - Payment AI Endpoints Not Exposed to Frontend

**SEVERITY:** MEDIUM
**CATEGORY:** Missing Endpoint Integration
**LOCATION:** Backend only: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/autopilot.py` (lines 292-409)

**DESCRIPTION:**

The autopilot service defines 2 AI-powered endpoints that are NOT integrated into any frontend:
- `GET /autopilot/ai/retry-timing/{payment_id}` (line 292)
- `GET /autopilot/ai/success-prediction/{payment_id}` (line 338)
- `POST /autopilot/ai/assess-all-payments` (line 370)

These endpoints use AI to:
1. Suggest optimal retry timing for failed payments
2. Predict payment success likelihood
3. Assess all scheduled payments for risk

**But:**
- No frontend integration exists to display these predictions
- No UI to show AI-powered payment risk assessment
- No mechanism to use AI recommendations in payment strategy
- These are powerful internal features with 0 credits cost but NOT leveraged

**IMPACT:**
- Planners cannot see AI-powered payment health insights
- Autopilot doesn't benefit from AI analysis for decision-making
- Money dashboard (admin/money/page.tsx) uses payment-forecast AI but NOT payment-risk AI
- Missed opportunity: Risk assessment data stored but never displayed

**AFFECTED ENDPOINTS:**
- GET `/admin/autopilot/ai/retry-timing/{payment_id}`
- GET `/admin/autopilot/ai/success-prediction/{payment_id}`
- POST `/admin/autopilot/ai/assess-all-payments`

**REMEDIATION:**
1. Add AI Risk Assessment widget to Money dashboard
2. Display success probability for each scheduled payment
3. Show risk factors and recommendations from AI
4. Integrate retry-timing suggestions into automatic retry logic

---

### ISSUE #4: HIGH - Autopilot Endpoint Uses Wrong Auth Check

**SEVERITY:** HIGH
**CATEGORY:** Security / Authentication Issue
**LOCATION:** Backend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/autopilot.py` (lines 27-43)

**DESCRIPTION:**

Autopilot cron endpoints use custom `verify_cron_auth()` function that checks for `CRON_SECRET` environment variable. However:

**Line 27-43:**
```python
def verify_cron_auth(authorization: Optional[str] = Header(None)):
    """Verify cron job authorization."""
    if not CRON_SECRET:
        # If no secret configured, allow (for development)
        logger.warning("CRON_SECRET not configured - cron endpoints are unprotected")
        return True  # ← DANGEROUS: Any request passes if env var missing
```

**PROBLEMS:**
1. **Insecure Default:** If `CRON_SECRET` environment variable is missing, ANY request to cron endpoints succeeds
2. **No User Context:** Cron endpoints (like payment processing) have NO user context, so they bypass user auth entirely
3. **Missing Logging:** No audit trail of who triggered payment processing
4. **Vulnerable in Production:** If env var is not properly set in coolify deployment, cron endpoints are open

**IMPACT:**
- Unauthorized users could trigger payment processing, payment reminders, schedule recalculations
- No audit trail for financial operations
- Potential for payment fraud or manipulation
- Money/autopilot endpoints completely unprotected if CRON_SECRET not configured

**AFFECTED ENDPOINTS:**
- POST `/admin/autopilot/process-due-payments`
- POST `/admin/autopilot/send-payment-reminders`
- POST `/admin/autopilot/retry-failed-payments`
- POST `/admin/autopilot/recalculate-schedules/{contract_id}`
- GET `/admin/autopilot/ai/retry-timing/{payment_id}`
- GET `/admin/autopilot/ai/success-prediction/{payment_id}`
- POST `/admin/autopilot/ai/assess-all-payments`

**REMEDIATION:**
1. Make CRON_SECRET mandatory in production (not optional)
2. Add user_id context to cron endpoints where possible
3. Log all cron operation executions
4. Verify CRON_SECRET is set during startup
5. Add fallback to IP-based verification for internal services

---

### ISSUE #5: HIGH - Payment Forecast Response Data Mismatch

**SEVERITY:** HIGH
**CATEGORY:** Parameter Mismatch / Type Mismatch
**LOCATION:** Frontend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/admin/money/page.tsx` → Backend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py` (line 1675-1821)

**DESCRIPTION:**

Frontend expects `data.forecast` but backend returns the entire result dict with response at top level.

**Frontend expects (money/page.tsx):**
```typescript
const data = await response.json();
setAiForecast(data.forecast);  // ← Expects "forecast" key
```

**Backend returns (ai.py line 1675-1821):**
```python
result = await ai_service.generate(...)
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

**The endpoint returns:**
- Top-level keys: `forecast_periods`, `cash_flow_warning`, `peak_payment_dates`, `recommendations`, `summary`, `cached`, `credits_used`
- NO `forecast` wrapper key

**IMPACT:**
- Frontend sets `aiForecast` to `undefined` (trying to access data.forecast which doesn't exist)
- Payment forecast widget displays empty state even though data was returned
- Planning tool loses critical AI-powered insights
- User sees "No forecast available" instead of cash flow predictions

**AFFECTED ENDPOINTS:**
- GET `/admin/ai/weddings/{wedding_id}/payment-forecast`

**REMEDIATION:**
Option A (Backend): Wrap response:
```python
return {
    "forecast": {
        "forecast_periods": ...,
        ...
    },
    "cached": result["cached"],
    "credits_used": result["credits_used"]
}
```

Option B (Frontend): Update data access:
```typescript
setAiForecast(data);  // Use entire response instead
```

**RECOMMENDATION:** Option A (wrap in backend) maintains consistency with other endpoints.

---

### ISSUE #6: MEDIUM - Seating Response Format Inconsistency

**SEVERITY:** MEDIUM
**CATEGORY:** Parameter Mismatch
**LOCATION:** Backend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py` (line 796-989)

**DESCRIPTION:**

Seating optimization endpoint returns validated table data with extra fields (`seats_used`, `capacity`) that frontend doesn't expect or use.

**Backend returns (ai.py line 961-989):**
```python
return {
    "tables": validated_tables,  # Each table has: id, guests[], capacity, seats_used
    "warnings": warnings,        # Validation warnings
    "credits_used": result["credits_used"],
    "cached": result["cached"]
}
```

**validated_tables contains:**
```python
{
    "id": ...,
    "table_id": ...,
    "table_name": ...,
    "guests": [...],    # Each guest: {id, name, reason, ...}
    "capacity": ...,    # Added by backend
    "seats_used": ...   # Added by backend - NOT EXPECTED BY FRONTEND
}
```

**Frontend expects (seating/page.tsx line 48-56):**
```typescript
interface AISuggestion {
  tables: Array<{
    table_id: string;
    table_name: string;
    guests: Array<{ guest_id: string; guest_name: string; reason: string }>;
  }>;
  credits_used: number;
  cached: boolean;
}
// ← No warnings field
// ← Doesn't expect capacity, seats_used
```

**MINOR IMPACT:**
- Extra fields in response (harmless but indicate spec mismatch)
- Frontend type definition incomplete (missing `warnings` field)
- No validation feedback shown to user
- API response is more complete than frontend utilizes

**AFFECTED ENDPOINTS:**
- POST `/admin/ai/weddings/{wedding_id}/seating-optimize`

**REMEDIATION:**
1. Update frontend type definition to include warnings
2. Display validation warnings to user (over capacity, invalid guests, etc.)
3. Document full response schema

---

### ISSUE #7: MEDIUM - AI Health Check Not Called by Frontend

**SEVERITY:** MEDIUM
**CATEGORY:** Dead Code / Missing Integration
**LOCATION:** Backend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py` (line 2288-2301)

**DESCRIPTION:**

Backend provides a health check endpoint for the AI service:

```python
@router.get("/health")
async def ai_health_check() -> Dict[str, Any]:
    """Check if AI service is initialized and available."""
    return {
        "status": "healthy" if ai_service._client else "unavailable",
        "ai_enabled": settings.ai_enabled,
        "service": "gemini",
        "models": {
            "primary": MODEL_PRIMARY,
            "economy": MODEL_ECONOMY
        }
    }
```

**But:**
- Frontend NEVER calls this endpoint
- No UI component checks AI availability before showing AI features
- Planners see AI buttons even when service is down
- Failed clicks provide no feedback about service status

**IMPACT:**
- Poor UX: Users attempt to use AI features that aren't available
- No early warning that AI is misconfigured
- Debugging is harder (no clear status indication)

**AFFECTED ENDPOINTS:**
- GET `/admin/ai/health`

**REMEDIATION:**
1. Call `/admin/ai/health` on admin dashboard load
2. Display AI service status indicator
3. Disable AI feature buttons if service is unavailable
4. Show tooltip explaining why features are disabled

---

### ISSUE #8: LOW - AI Features Not Gated by Subscription Plan in Frontend

**SEVERITY:** LOW
**CATEGORY:** Missing Error Handling / UX Issue
**LOCATION:** Frontend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/components/ai/AIChatWidget.tsx` and scattered endpoints

**DESCRIPTION:**

Frontend AI components show buttons for AI features without checking if the planner's subscription plan includes AI credits. The backend enforces this (returns 402 Insufficient Credits), but frontend provides no upfront indication.

**Backend checks credits (ai_service.py line 822-846):**
```python
async def check_credits(self, user_id: str, feature: str) -> Dict[str, Any]:
    """Check if user has enough AI credits for a feature."""
    ...
    result = await self.subscription_service.check_usage_limits(...)
    return {
        "allowed": result.get("allowed", False),
        "credits_needed": credits_needed,
        "credits_remaining": result.get("remaining", 0),
        "message": result.get("message", "")
    }
```

**Frontend doesn't check upfront:**
```typescript
// AIChatWidget.tsx shows chat button without checking credits
const handleSendMessage = async (message: string) => {
  try {
    const response = await fetch(`${baseUrl}/admin/ai/chat`, { ... });
    if (response.ok) { /* success */ }
    else if (response.status === 402) { /* insufficient credits */ }
  }
}
```

**IMPACT:**
- UX: Users click AI buttons and get error "Insufficient credits" after loading
- Better UX: Show "Upgrade to use AI" badge on buttons or disable for free plans
- No guidance on how many credits are needed
- Could frustrate planners, especially during critical RSVP planning

**REMEDIATION:**
1. Fetch user's remaining credits on page load
2. Disable/gray out AI buttons if credits unavailable
3. Show credit cost next to each AI feature button
4. Link "Upgrade" buttons to pricing page

---

### ISSUE #9: MEDIUM - Missing Error Handling in Payment Forecast

**SEVERITY:** MEDIUM
**CATEGORY:** Missing Error Handling
**LOCATION:** Backend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py` (line 1675-1821)

**DESCRIPTION:**

The payment forecast endpoint doesn't handle cases where payment schedule data is invalid or missing:

```python
async def get_payment_forecast(
    wedding_id: str,
    force_refresh: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Fetches scheduled payments and venues (line 1695-1724)
        # But NO validation that data exists or is well-formed

        result = await ai_service.generate(...)

        # If payment data is malformed, AI might return incomplete forecast
        return { ... }
    except ...:
        raise HTTPException(...)
```

**Specific gaps:**
1. No check if scheduled_payments is empty → AI generates generic forecast with no real data
2. No validation of payment dates → AI might get invalid date formats
3. No check if wedding has no payment schedule → Frontend displays empty forecast as if calculated

**IMPACT:**
- Misleading forecast for weddings with no payments scheduled
- AI generates generic advice rather than wedding-specific insights
- Planner sees "All good!" when maybe no data was available

**REMEDIATION:**
Add early returns:
```python
if not scheduled_payments:
    return {
        "forecast_periods": [],
        "cash_flow_warning": "No scheduled payments found. Add vendor contracts to enable forecasting.",
        "peak_payment_dates": [],
        "recommendations": [],
        "summary": { "total_remaining": 0, "total_paid": 0, ... },
        "cached": False,
        "credits_used": 0
    }
```

---

### ISSUE #10: LOW - Inconsistent Feature Cost Documentation

**SEVERITY:** LOW
**CATEGORY:** Documentation Issue
**LOCATION:** Backend: `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/services/ai_service.py` (lines 34-605)

**DESCRIPTION:**

AI_FEATURES dict defines credit costs, but some have cost 0 (internal) while frontend doesn't indicate cost:

```python
AI_FEATURES = {
    "budget_insights": { "credits": 3, ... },      # 3 credits
    "chat": { "credits": 1, ... },                 # 1 credit
    "seating_small": { "credits": 2, ... },        # 2 credits
    "seating_medium": { "credits": 5, ... },       # 5 credits
    "seating_large": { "credits": 10, ... },       # 10 credits (expensive!)
    "payment_retry_timing": { "credits": 0, ... },  # Free (internal)
    "payment_success_prediction": { "credits": 0, ... },  # Free (internal)
}
```

**Frontend shows buttons without credit indication:**
- No tooltip showing "Uses 3 credits"
- No warning that seating_large costs 10x more than chat
- Users might be surprised by credit deduction

**IMPACT:**
- Planners don't understand credit economics
- Might avoid expensive features thinking they're free
- Or burn through credits on expensive operations without realizing

**REMEDIATION:**
1. Document credit costs in frontend button tooltips
2. Show cost before execution: "This will use 10 credits"
3. Warn for expensive operations (>5 credits)

---

## Summary by Severity

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 1 | Issue #1: Seating parameter mismatch |
| HIGH | 3 | Issues #2, #4, #5: Feature gating, auth, response format |
| MEDIUM | 4 | Issues #3, #6, #9, #10: Missing integration, inconsistencies |
| LOW | 2 | Issues #7, #8: Dead code, UX improvements |

---

## Recommendations for Launch

### Before RSVP Launch (CRITICAL)
1. **Fix Issue #1** - Seating parameter mismatch (will break AI feature)
2. **Fix Issue #4** - CRON_SECRET security issue (payment processing vulnerable)
3. **Fix Issue #5** - Payment forecast response format (currently broken)

### Before Launch (HIGH)
4. **Fix Issue #2** - Add AI client check to seating endpoint

### Post-Launch Improvements (MEDIUM)
5. Integrate payment risk assessment into Money dashboard
6. Call health check endpoint on dashboard load
7. Add credit check UI to prevent user frustration
8. Update seating response types and documentation

---

## File Locations for Changes

### Backend Files to Update
- `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/ai.py`
- `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/api/autopilot.py`
- `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/services/ai_service.py`

### Frontend Files to Update
- `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/admin/weddings/[id]/seating/page.tsx`
- `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/admin/seating/page.tsx`
- `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/admin/money/page.tsx`
- `/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/app/components/ai/AIChatWidget.tsx`

---

## Testing Recommendations

### Manual Testing Required
1. **Seating:** Request AI suggestions with 50, 150, and 300+ guests
2. **Payment Forecast:** Generate forecast for wedding with and without payments
3. **Auth:** Verify CRON_SECRET blocks unauthorized requests (or allows with valid secret)
4. **Credits:** Confirm insufficient credits error displays properly
5. **Health Check:** Verify AI service status indicated correctly

### Automated Testing
- Add integration tests for all AI endpoints
- Test parameter validation for request/response models
- Verify credit deduction accuracy
- Test caching behavior (same context should be cached)

---

## Risk Assessment

**Overall Platform Risk:** MEDIUM-HIGH
**Wedding Launch Risk:** HIGH
**Payment Processing Risk:** CRITICAL

The platform has solid AI architecture with proper credit management and error handling, but the identified issues (especially seating parameter mismatch and payment forecast format) will break core features during RSVP launch. The security issue with CRON_SECRET is also concerning for production payment processing.

**Recommendation:** Address all CRITICAL and HIGH severity issues before launching RSVP feature. The platform is otherwise well-designed for a SaaS wedding planning solution.


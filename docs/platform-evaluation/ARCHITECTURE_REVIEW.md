# Architecture and Code Quality Review
## WeddingWebApp Recent Changes (Commit d793b5c)

**Review Date:** 2026-03-07
**Reviewed By:** Senior Architecture Review
**Scope:** Recent changes from commit d793b5c to HEAD

---

## Executive Summary

This review identified **4 CRITICAL**, **3 HIGH**, and **2 MEDIUM** severity issues across systemic areas including SSE architecture, datetime serialization patterns, import hygiene, and API error handling consistency. While individual issues are mostly contained, there are patterns suggesting code review processes may need strengthening.

**Key Concern:** The SSE implementation uses in-process pub/sub that will NOT scale horizontally, and the frontend has several edge cases not handled. The datetime serialization uses inconsistent patterns across the codebase.

---

## FINDINGS

---

### 1. CRITICAL: SSE Architecture Not Production-Ready for Horizontal Scaling

**Category:** Architecture / Infrastructure
**Severity:** CRITICAL
**Files:**
- `app/services/sse_manager.py` (singleton in-memory)
- `app/api/notification_stream.py` (single-instance pub/sub)
- `app/admin/components/TopHeader.tsx` (relies on single-instance backend)

**Description:**

The SSE implementation uses an in-process `asyncio.Queue`-based pub/sub system with a singleton `sse_manager` instance. This approach has fundamental limitations:

1. **Not Distributed:** When running multiple server instances behind a load balancer, connections to Instance A won't receive events published by Instance B. Events from services (NotificationService, PlannerNotificationService) only reach connected clients on the same instance.

2. **Stateful Singleton:** `sse_manager` in `app/services/sse_manager.py` (line 75) is a module-level singleton. If the server restarts, all connections are lost with no graceful reconnect strategy on the backend side.

3. **Memory Leak Risk:** Connections stored in `_connections: Dict[str, Set[asyncio.Queue]]` are tied to a single process. Under high load with many connections, memory could accumulate without a Redis/message-queue backend.

**Current Code Pattern:**
```python
# app/services/sse_manager.py:75
sse_manager = SSEManager()  # Singleton - in-process only

# app/services/notification_service.py:270
asyncio.create_task(
    sse_manager.broadcast_to_user(
        recipient_email,
        "notification-new",
        notification_data
    )
)
```

**Recommended Action:**

- **IMMEDIATE:** Add documentation to `sse_manager.py` clearly stating "Single-instance only. Do not use behind load balancer." Include a GitHub issue for future migration to Redis Streams or AWS EventBridge.
- **BEFORE PROD SCALING:** Replace in-process pub/sub with Redis Streams or similar distributed message queue:
  - Use Redis XADD/XREAD for pub/sub
  - Move `SSEManager` to a thin wrapper around Redis streams
  - Add connection pooling and automatic reconnect logic
- **FRONTEND SAFETY:** The frontend already has exponential backoff (good), but consider adding a "sync" button in the UI when SSE has been down > 60 seconds.

---

### 2. CRITICAL: JWT Token in Query Parameter Vulnerable to Logging/History

**Category:** Security
**Severity:** CRITICAL
**Files:**
- `app/api/notification_stream.py` (line 132: `token: str = Query(...)`)
- `app/admin/components/TopHeader.tsx` (line 83: `?token=${encodeURIComponent(token)}`)

**Description:**

The SSE endpoint passes JWT tokens as query parameters because EventSource doesn't support custom headers. However, this creates security risks:

1. **Logged in Server Logs:** HTTP request logs (nginx, Uvicorn, CloudFlare) will record the full URL including the JWT token.
2. **Browser History:** If users manually navigate to SSE stream URLs, tokens appear in browser history.
3. **Proxy/Firewall Logs:** Intermediate proxies may log query parameters.
4. **Shorter Token Lifespan Not Sufficient:** Even with short-lived tokens, the attack window is real.

**Example Exposure:**
```
# nginx access log
GET /admin/notifications/stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... HTTP/1.1
```

**Recommended Action:**

- **MANDATORY:** Implement One-Time Auth Tokens (OAT):
  1. Frontend calls POST `/admin/notifications/session` → Backend returns single-use session ID (short-lived, e.g., 5 min)
  2. Frontend opens EventSource with `?session=<session_id>`
  3. Backend validates session ID (not JWT), then returns events
  4. Session IDs are cheaper to revoke/rotate than JWTs

- **ALTERNATE:** Use WebSocket instead of EventSource (supports custom headers natively), but requires WebSocket library and proxy support.

- **AUDIT:** Check CloudFlare logs and nginx access logs for token exposure in production. Rotate all tokens if found.

---

### 3. CRITICAL: API Error Handling Breaking Change in vendorManagementApi.ts

**Category:** API Design / Breaking Change
**Severity:** CRITICAL
**Files:**
- `app/services/vendorManagementApi.ts` (lines 437, 563, 794)
- `app/admin/vendors/page.tsx` (lines 200-214)

**Description:**

The API service was updated to throw errors from methods that previously returned empty arrays on 404/5xx:

**Changed Behavior:**
```typescript
// OLD (implicit behavior in getContracts):
if (!response.ok) return [];

// Now appears to throw in some paths, but NOT ALL:
export async function getContracts(...): Promise<VendorContract[]> {
  if (!response.ok) return [];  // Still returns []!
  return response.json();
}

export async function getPaymentMilestones(...): Promise<PaymentMilestone[]> {
  if (!response.ok) return [];  // Still returns []!
  return response.json();
}

export async function getFormDataForContract(...) {
  if (!response.ok) {
    return { submissions: [], available_fields: {}, suggested_mappings: {} };
  }
  return response.json();
}
```

**Issue:** The patterns are **inconsistent**. Some methods return empty arrays (graceful fallback), others throw. Callers in `app/admin/vendors/page.tsx` use `Promise.all()` at line 200, which means if ANY call throws, the entire page fails to load.

```typescript
// Line 200-209: vendors/page.tsx
const [dashboardData, vendorsData, contractsData, milestonesData] = await Promise.all([
  getVendorDashboard(token),                      // Throws on error
  getVendorDirectory(token, {...}),               // Throws on error
  getContracts(token),                            // Returns [] on error (graceful)
  getPaymentMilestones(token),                    // Returns [] on error (graceful)
]);
```

**Current Callers:** The try/catch at line 216 catches errors, but the UX is:
- If `getVendorDashboard` fails → whole page shows error, users can't access vendor directory
- If `getContracts` fails → silently shows empty contracts list (confusing for users)

**Recommended Action:**

1. **STANDARDIZE ERROR HANDLING:** Choose one pattern across ALL API methods:
   - **Option A (Recommended):** Throw errors, let callers handle gracefully per endpoint
     ```typescript
     export async function getContracts(...): Promise<VendorContract[]> {
       const response = await fetch(...);
       if (!response.ok) {
         const error = await response.json().catch(() => ({}));
         throw new Error(error.detail || 'Failed to fetch contracts');
       }
       return response.json();
     }
     ```
   - **Option B:** Return fallback values, add a status field for errors
     ```typescript
     export async function getContracts(...): Promise<{ data: VendorContract[], error?: string }> {
       // Return { data: [], error: null } on success
       // Return { data: [], error: "reason" } on failure
     }
     ```

2. **UPDATE CALLERS:** If Option A, update vendors/page.tsx to handle partial failures:
   ```typescript
   const results = await Promise.allSettled([...]);
   const [dashboardData, vendorsData, contractsData, milestonesData] = results.map(
     (result, i) => result.status === 'fulfilled' ? result.value : defaultValues[i]
   );
   ```

3. **UPDATE TESTS:** Add tests for error scenarios in vendorManagementApi.ts to prevent regression.

---

### 4. CRITICAL: No Token Refresh Handling in SSE / Multiple Tabs Issue

**Category:** Authentication / Frontend Resilience
**Severity:** CRITICAL
**Files:**
- `app/admin/components/TopHeader.tsx` (SSE implementation)
- `app/api/notification_stream.py` (no token validation refresh)

**Description:**

The SSE implementation in TopHeader.tsx does not handle token expiration during an active connection:

1. **Token Expires While SSE Connected:** If a user's JWT expires (typically 1 hour), the SSE connection keeps trying to use the expired token. The backend's `_authenticate_from_query()` will reject it, but the frontend doesn't automatically refresh the token before reconnecting.

2. **Multiple Tabs Issue:** If the user opens multiple tabs of the admin dashboard:
   - Each tab opens its own SSE connection with its own token
   - If the user logs out on one tab, tokens on other tabs are invalid
   - No shared state means each tab reconnects independently, creating duplicate connections

3. **Logout Not Propagated:** Closing one tab doesn't close SSE connections in other tabs. No cross-tab communication mechanism.

**Current Logic (TopHeader.tsx lines 43-161):**
```typescript
useEffect(() => {
  if (!token) return;

  const connect = () => {
    const url = `${getApiBaseUrl()}/admin/notifications/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    // ...
    es.onerror = () => {
      // Reconnect with backoff (uses SAME expired token!)
      reconnectTimeoutRef.current = setTimeout(connect, delay);
    };
  };

  connect();
  // ...
}, [token]);  // Dependency on token is good, but token refresh not handled
```

**Missing:** When the token changes (user logs in, token refreshed), the component remounts and reconnects, but there's no automatic token refresh before expiration.

**Recommended Action:**

1. **Token Refresh Before Expiration:**
   - Decode the JWT in the frontend to check expiration time
   - Schedule a token refresh 5 minutes before expiration
   - Update the SSE URL with the new token and reconnect gracefully

   ```typescript
   const getTokenExpiry = (token: string) => {
     const decoded = JSON.parse(atob(token.split('.')[1]));
     return decoded.exp * 1000; // Convert to milliseconds
   };

   useEffect(() => {
     if (!token) return;
     const expiry = getTokenExpiry(token);
     const timeout = expiry - Date.now() - 5 * 60 * 1000; // 5 min before expiry
     if (timeout > 0) {
       const refreshTimer = setTimeout(() => {
         // Call refreshToken() and update context
       }, timeout);
       return () => clearTimeout(refreshTimer);
     }
   }, [token]);
   ```

2. **Multiple Tabs Synchronization:**
   - Use `localStorage` events to communicate token changes across tabs
   - Add a listener for logout events and close SSE on other tabs

   ```typescript
   useEffect(() => {
     const handleStorageChange = (e: StorageEvent) => {
       if (e.key === 'logout' && e.newValue === 'true') {
         closeConnection();
       }
     };
     window.addEventListener('storage', handleStorageChange);
     return () => window.removeEventListener('storage', handleStorageChange);
   }, []);
   ```

3. **Explicit 401 Handling:**
   - On `es.onerror`, check if the backend returned 401
   - If so, trigger logout rather than infinite reconnect loop

---

## 5. HIGH: Inconsistent DateTime Serialization Patterns

**Category:** Consistency / Code Maintenance
**Severity:** HIGH
**Files:**
- `app/models/guest.py` (lines 51-58: `@field_serializer`)
- `app/models/wedding.py` (lines 116-118: `@field_serializer`)
- `app/services/vendor_service.py` (manual `isoformat()` calls)
- `app/services/budget_service.py` (manual dict inspection)
- `app/services/contract_service.py` (manual `isoformat()` with `hasattr` checks)
- `app/services/checkin_service.py` (manual `isoformat()` with `hasattr` checks)
- `app/utils/serializers.py` (centralized serialization utility)

**Description:**

The codebase uses **three different approaches** to serialize datetime objects:

**Pattern 1: Pydantic Field Serializers (Modern, Recommended)**
```python
# app/models/guest.py:51-58
@field_serializer(
    'sms_opt_in_date', 'sms_opt_out_date', ...,
    when_used='json'
)
def serialize_datetimes(self, value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None
```

**Pattern 2: Manual Dict Transformation in Services (Fragile)**
```python
# app/services/vendor_service.py
if isinstance(vendor.get("created_at"), datetime):
    vendor["created_at"] = vendor["created_at"].isoformat()
if isinstance(vendor.get("updated_at"), datetime):
    vendor["updated_at"] = vendor["updated_at"].isoformat()
```

**Pattern 3: Hasattr Checks (Defensive, Verbose)**
```python
# app/services/contract_service.py:_serialize_contract
for date_field in ["wedding_date", "sent_at", "viewed_at", ...]:
    if date_field in serialized and serialized[date_field]:
        if hasattr(serialized[date_field], "isoformat"):
            serialized[date_field] = serialized[date_field].isoformat()
```

**Pattern 4: Centralized Utility (Exists but Not Used)**
```python
# app/utils/serializers.py:9-38 (EXISTS but underutilized)
def serialize_mongo_doc(doc: Any) -> Any:
    if isinstance(doc, datetime):
        return doc.isoformat()
    # ...
```

**Issues:**
1. **Code Duplication:** Datetime serialization logic is repeated in 5+ places
2. **Inconsistent Handling:** Some check for `None`, others check `hasattr`, others rely on Pydantic
3. **Maintenance Risk:** If you need to change timestamp format (e.g., to include timezone), you must update multiple files
4. **Nested Objects:** Only `contract_service.py` handles nested datetime fields in sections/payments; others don't

**Recommended Action:**

1. **Audit All Services:** List all places datetime serialization happens:
   - `vendor_service.py`: 4 places (create, list, get, update)
   - `budget_service.py`: Custom serialization in templates and summaries
   - `contract_service.py`: Nested serialization (good!)
   - `checkin_service.py`: Single place (minimal)

2. **Migrate to Pydantic Field Serializers:**
   - Define Pydantic models for all database documents (vendors, contracts, budgets, etc.)
   - Use `@field_serializer` decorators like in `guest.py` and `wedding.py`
   - Remove manual serialization from service methods

   ```python
   # Better approach:
   class VendorProfileModel(BaseModel):
       created_at: Optional[datetime] = None
       updated_at: Optional[datetime] = None

       @field_serializer('created_at', 'updated_at', when_used='json')
       def serialize_datetimes(self, value: Optional[datetime]) -> Optional[str]:
           return value.isoformat() if value else None
   ```

3. **Use Centralized Serializer for Fallback:**
   - For raw MongoDB dicts that can't use Pydantic, use `serialize_mongo_doc()` from utils:

   ```python
   # app/services/contract_service.py
   from app.utils.serializers import serialize_mongo_doc

   def _serialize_contract(self, contract: Optional[Dict]) -> Optional[Dict]:
       if not contract:
           return None
       return serialize_mongo_doc(contract)  # Handles all datetime fields recursively
   ```

4. **Add Tests:**
   ```python
   def test_datetime_serialization():
       # Test that all datetime fields are properly serialized to ISO format strings
       doc = {
           "created_at": datetime(2026, 3, 7, 12, 0, 0),
           "nested": {
               "updated_at": datetime(2026, 3, 7, 13, 0, 0)
           }
       }
       serialized = serialize_mongo_doc(doc)
       assert isinstance(serialized["created_at"], str)
       assert isinstance(serialized["nested"]["updated_at"], str)
   ```

---

### 6. HIGH: Lazy Imports of SSE Manager Create Hidden Coupling

**Category:** Import Hygiene / Code Clarity
**Severity:** HIGH
**Files:**
- `app/services/notification_service.py` (lines 270, 419, 456)
- `app/services/planner_notification_service.py` (lines 143, 271, 301)

**Description:**

Both notification services import `sse_manager` inside method bodies instead of at module level:

```python
# app/services/notification_service.py:270
def some_method(self):
    # ...
    from app.services.sse_manager import sse_manager  # Inside method!
    asyncio.create_task(
        sse_manager.broadcast_to_user(...)
    )
```

**Why This Pattern Was Used:** Likely to avoid circular imports, but there's no actual circular dependency:
- `sse_manager.py` imports: `asyncio`, `logging`, standard types
- `notification_service.py` imports: `motor`, `pymongo`, `pydantic`, no SSE imports
- No circular dependency exists

**Issues:**
1. **Hidden Coupling:** Readers of the method signature don't see the SSE dependency
2. **Performance:** Import lookup happens every method call (though Python caches it)
3. **Testability:** Hard to mock SSE manager when it's imported inside methods
4. **Code Standards:** Violates PEP 8 (imports should be at module level)

**Recommended Action:**

1. **Move Imports to Module Level:**
   ```python
   # app/services/notification_service.py (top of file)
   from app.services.sse_manager import sse_manager

   class NotificationService:
       async def send_notification(...):
           # Use sse_manager directly
           asyncio.create_task(
               sse_manager.broadcast_to_user(...)
           )
   ```

2. **Verify No Circular Imports:**
   ```bash
   python -c "import app.services.notification_service"
   # Should import without error
   ```

3. **Update Type Hints:**
   ```python
   from app.services.sse_manager import SSEManager

   class NotificationService:
       def __init__(self, sse: Optional[SSEManager] = None):
           self.sse = sse or sse_manager
   ```
   This makes the dependency explicit and testable.

4. **Add Comment Explaining SSE Dependency:**
   ```python
   # File: app/services/notification_service.py
   """
   Notification service with real-time SSE broadcasting.

   Dependencies:
   - MongoDB (for notification persistence)
   - SSE Manager (for real-time updates to connected clients)

   When a notification is created, it's broadcast to all connected
   clients of the affected user(s) via the SSE manager.
   """
   ```

---

### 7. HIGH: Missing Fallback When SSE Fails for Extended Period

**Category:** Frontend Resilience / UX
**Severity:** HIGH
**Files:**
- `app/admin/components/TopHeader.tsx` (SSE implementation)

**Description:**

The TopHeader component connects to SSE and displays notification counts, but if SSE fails completely:

1. **Silent Failure:** If SSE stays disconnected after max reconnect attempts (20), the notification count stays stale
2. **No User Feedback:** Users don't know if the count is current or outdated
3. **No Fallback:** There's no degradation to polling-based notification checking
4. **Max Attempts Reached:** After 20 failed reconnections with exponential backoff up to 30s, it gives up entirely

**Current Code (TopHeader.tsx lines 107-112):**
```typescript
es.onerror = () => {
  isConnecting.current = false;
  es.close();
  eventSourceRef.current = null;

  // Reconnect with exponential backoff
  if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {  // 20 attempts
    const delay = Math.min(
      INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current),
      MAX_RECONNECT_DELAY  // 30 seconds
    );
    reconnectAttempts.current += 1;
    reconnectTimeoutRef.current = setTimeout(connect, delay);
  }
  // AFTER 20 ATTEMPTS, connection is abandoned. No fallback.
};
```

**Timeline:**
- Attempts 1-20: Exponential backoff, final wait is ~30 seconds
- After 20th failure: Give up entirely
- User sees stale notification count for rest of session

**Recommended Action:**

1. **Add Fallback to Polling:**
   ```typescript
   const MAX_RECONNECT_ATTEMPTS = 20;
   let pollIntervalRef: NodeJS.Timeout | null = null;

   es.onerror = () => {
     // ... existing code ...
     if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
       // SSE exhausted, fall back to polling every 60 seconds
       console.warn('SSE connection exhausted, falling back to polling');
       if (!pollIntervalRef) {
         pollIntervalRef = setInterval(async () => {
           try {
             const [platformRes, activityRes] = await Promise.allSettled([...]);
             // Update count
           } catch {
             // Polling will retry
           }
         }, 60000);
       }
     }
   };
   ```

2. **Visual Indicator:**
   ```typescript
   const [sseStatus, setSseStatus] = useState<'connected' | 'reconnecting' | 'polling' | 'offline'>(
     'connected'
   );

   // Show indicator in UI
   {sseStatus === 'polling' && (
     <span title="Real-time updates unavailable, using polling">
       <AlertCircle size={16} className="text-yellow-500 animate-pulse" />
     </span>
   )}
   ```

3. **Reset Fallback on Success:**
   ```typescript
   es.onopen = () => {
     isConnecting.current = false;
     reconnectAttempts.current = 0;
     setSseStatus('connected');

     // Clear polling fallback if it was active
     if (pollIntervalRef) {
       clearInterval(pollIntervalRef);
       pollIntervalRef = null;
     }
   };
   ```

---

### 8. MEDIUM: No Documentation of Route Prefix Changes

**Category:** API / Breaking Changes
**Severity:** MEDIUM
**Files:**
- `app/main.py` (lines 300-361)
- `app/services/vendorManagementApi.ts`

**Description:**

The codebase has two different API prefixes for contracts:
- `/admin/contracts` — Admin-only contract management
- `/vendor-contract/public/contracts` — Public contract viewing/signing (no auth)

This is intentional and correct, but there's no documentation explaining:
1. Why two separate routers exist
2. When to use each endpoint
3. What happens if you mix them up

**Current Code (app/main.py:300-301):**
```python
app.include_router(vendor_management_router, prefix="/admin", tags=["Vendor Contracts"])
app.include_router(vendor_contract_public_router, prefix="/vendor-contract", tags=["Public Contract Access"])
```

**Concern:** If a future developer adds a new endpoint and puts it in the wrong router, or if external integrations (mobile apps, webhooks) hardcoded URLs, they might break.

**Recommended Action:**

1. **Add Comments to main.py:**
   ```python
   # Vendor contract endpoints: TWO separate routers for different access patterns
   app.include_router(
       vendor_management_router,
       prefix="/admin",
       tags=["Vendor Contracts"]
   )
   # ↑ Admin-only endpoints: create, edit, list, delete contracts
   # Used by: Admin dashboard, vendor management page
   # Auth: Required (Bearer token)

   app.include_router(
       vendor_contract_public_router,
       prefix="/vendor-contract",
       tags=["Public Contract Access"]
   )
   # ↑ Public endpoints: view and sign contracts
   # Used by: External vendors, public contract links
   # Auth: None (uses public access tokens instead)
   ```

2. **Document in README or API.md:**
   ```markdown
   ## Contract Endpoints

   | Endpoint | Router | Auth | Purpose |
   |----------|--------|------|---------|
   | `/admin/contracts` | vendor_management_router | JWT | Admin contract management |
   | `/vendor-contract/public/contracts` | vendor_contract_public_router | None | Public contract signing |

   **Important:** Do not mix these endpoints. Admin endpoints are for internal use only.
   ```

3. **Add Type Comments in vendorManagementApi.ts:**
   ```typescript
   /**
    * Fetch contracts for admin dashboard.
    *
    * Endpoint: GET /admin/contracts
    * Auth: Required (JWT token)
    *
    * Note: This is for admin management only. For public contract access,
    * use getPublicContract() instead.
    */
   export async function getContracts(...) {
     // ...
   }
   ```

---

### 9. MEDIUM: Unused useCallback Removed Without Explanation

**Category:** Code Cleanup / Refactoring
**Severity:** MEDIUM
**Files:**
- `app/admin/components/TopHeader.tsx` (line 3: removed `useCallback`)

**Description:**

The TopHeader component had `useCallback` removed in the SSE refactor:

**Before:**
```typescript
import React, { useState, useEffect, useCallback, useRef } from 'react';
```

**After:**
```typescript
import React, { useState, useEffect, useRef } from 'react';
```

This is actually **correct** — the old polling pattern used `useCallback` to memoize the `fetchNotificationCount` function, but the SSE pattern doesn't need it. However, there's no code comment explaining why.

**Why This Matters:** Future developers might wonder if this was intentional or an accidental removal.

**Recommended Action:**

1. **Add Comment Above useEffect:**
   ```typescript
   // SSE connection management
   // No useCallback needed: connection setup runs once on mount/token change
   // (Unlike the old polling pattern where fetchNotificationCount was memoized)
   useEffect(() => {
     if (!token) return;
     // ...
   }, [token]);
   ```

2. **Or** commit message should explicitly note:
   ```
   Refactored notification polling → SSE streaming:
   - Removed useCallback (no longer needed for SSE setup)
   - Replaced polling interval with EventSource subscription
   - Added exponential backoff for reconnection
   ```

---

## SUMMARY TABLE

| # | Category | Severity | Title | File(s) | Action |
|---|----------|----------|-------|---------|--------|
| 1 | Architecture | CRITICAL | SSE not horizontally scalable | sse_manager.py, notification_stream.py | Migrate to Redis Streams before multi-instance deployment |
| 2 | Security | CRITICAL | JWT in query parameter exposed to logs | notification_stream.py, TopHeader.tsx | Implement one-time auth tokens or use WebSocket |
| 3 | API Design | CRITICAL | API error handling breaking changes | vendorManagementApi.ts, vendors/page.tsx | Standardize error handling pattern across all API methods |
| 4 | Authentication | CRITICAL | No token refresh/multi-tab handling in SSE | TopHeader.tsx, notification_stream.py | Add token refresh logic and cross-tab logout sync |
| 5 | Consistency | HIGH | Inconsistent datetime serialization | models/, services/ | Migrate to Pydantic field serializers or centralized utility |
| 6 | Code Quality | HIGH | Lazy imports hide SSE coupling | notification_service.py, planner_notification_service.py | Move imports to module level, add type hints |
| 7 | Resilience | HIGH | No fallback when SSE exhausted | TopHeader.tsx | Add polling fallback after max reconnect attempts |
| 8 | Documentation | MEDIUM | No docs on route prefix separation | main.py, README | Add inline comments and API documentation |
| 9 | Code Clarity | MEDIUM | Unused import removal unexplained | TopHeader.tsx | Add code comment explaining removal of useCallback |

---

## RISK ASSESSMENT

**Immediate Risk (Next 30 days):**
- **CRITICAL-1 & 2:** If SSE is deployed to production without Redis backend, it will fail catastrophically with multiple server instances
- **CRITICAL-3:** If vendors page is used heavily, inconsistent error handling could cause unpredictable crashes
- **CRITICAL-4:** Users with expired tokens will have stale notification counts; multi-tab scenarios cause connection duplicates

**Medium-term Risk (Next 90 days):**
- **HIGH-5:** Datetime serialization inconsistency makes migrations and schema changes error-prone
- **HIGH-6:** Tests and mocking become difficult with lazy imports; circular import refactoring becomes riskier
- **HIGH-7:** User experience degrades silently after 10-20 minutes of SSE failures

**Long-term Risk (Next 6+ months):**
- **MEDIUM-8 & 9:** Code clarity issues accumulate, onboarding new developers becomes harder, refactoring risk increases

---

## RECOMMENDATIONS BY PRIORITY

### Phase 1: Critical Fixes (Must do before production)
1. Implement one-time auth tokens for SSE
2. Add token refresh logic to SSE connection
3. Standardize API error handling (Promise.allSettled pattern)
4. Document SSE single-instance limitation

### Phase 2: High Priority (Before scaling)
1. Audit and migrate datetime serialization to centralized approach
2. Move SSE manager imports to module level
3. Add polling fallback for SSE exhaustion
4. Add Redis Streams backend for SSE (in-progress or planned)

### Phase 3: Code Quality
1. Add comprehensive test suite for SSE, token refresh, error handling
2. Document API route separation (admin vs public)
3. Add inline comments to explain non-obvious design decisions
4. Create ARCHITECTURE.md with SSE scaling strategy

---

## Conclusion

The recent changes introduce powerful real-time notification capability via SSE, but several systemic issues need resolution before production use:

1. **Architecture must support horizontal scaling** — Currently in-process only
2. **Security must prevent token exposure** — Currently tokens in query params and logs
3. **API contracts must be consistent** — Currently mixing throw/return patterns
4. **Frontend must be resilient** — Currently no token refresh or fallback
5. **Code must follow established patterns** — Currently mixing serialization/import approaches

**Recommended Timeline:**
- Week 1: CRITICAL-1,2,4 (SSE, token, refresh)
- Week 2-3: CRITICAL-3 (API errors), HIGH-5,6,7
- Week 4+: MEDIUM-8,9 and tests

The good news: The SSE architecture is fundamentally sound and well-implemented for a single-instance system. With the recommended changes, it will scale to production.

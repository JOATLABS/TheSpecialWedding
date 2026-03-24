# P0 Architectural Refactors — Research-Backed Specifications

> **Methodology**: Every recommendation below is grounded in 2025–2026 industry best practices,
> sourced from official documentation, production case studies, and expert guides.
> Citations appear inline as numbered references; full URLs are listed at the bottom.

These items require coordinated backend + frontend changes and should be tackled as individual sprint tasks, not quick fixes.

---

## Cross-Cutting: Automated Type Synchronization (NEW — must be done first)

**Research Finding**: The `pydantic-to-typescript` CLI tool [4] enables a single source of truth
for type definitions across Python and TypeScript. It converts Pydantic v2 models into
TypeScript interfaces automatically and can run as a GitHub Action in CI/CD pipelines.

**Why This Matters**: Our audit found 62 frontend/backend type misalignments. Manual type
maintenance is the root cause. The 2026 Production-Ready FastAPI Guide [1] explicitly
separates `schemas/` (Pydantic) from `models/` (DB), making auto-generation straightforward.

**Implementation**:

```bash
# Install (Pydantic v2 compatible)
pip install 'pydantic-to-typescript>=2'

# Generate all TypeScript interfaces from our Pydantic schemas
pydantic2ts --module app.models --output app/types/generated/api-types.ts

# Or target specific modules
pydantic2ts --module app.models.guest --output app/types/generated/guest.ts
pydantic2ts --module app.models.subscription --output app/types/generated/subscription.ts
```

**CI/CD Integration**: Add a pre-commit hook or GitHub Action that regenerates types and
fails the build if the generated output differs from committed types. This catches drift
at PR time, not in production.

**Files to Create**: `scripts/generate-types.sh`, `.github/workflows/type-sync.yml`
**Files to Modify**: `package.json` (add `generate:types` script), `tsconfig.json` (include generated dir)
**Risk**: Low — additive, doesn't change runtime behavior
**Estimated Effort**: 0.25 sprint days

---

## P0-9: Consolidate Contract APIs

**Current State**: Contracts are served from 3 separate files:
- `vendor_management.py` — Admin CRUD for vendor contracts (milestones, payment links)
- `contracts.py` — Standalone contract CRUD with sections, public viewing/signing
- `vendor_contract_public.py` — Public contract access by token

**Problem**: Overlapping responsibility, inconsistent contract models, no shared service layer.

**Research-Backed Approach**:

Per the 2026 Production-Ready FastAPI Guide [1] and the Service Layer Best Practices [2],
the correct pattern is:

1. **Routes own no business logic** — endpoint functions should "receive an HTTP request,
   delegate to the corresponding service, and return the response" [2].
2. **Service Layer as the brain** — a single `ContractService` encapsulates all contract
   business rules, testable without HTTP context [1].
3. **Hierarchical Router aggregation** [1] — keep 2 route entry points (admin + public)
   that both delegate to the same service via different auth guards.
4. **Dependency Injection chain** [3] — inject `ContractService` via `Depends()` with
   the DB session flowing through the DI tree.

**Implementation**:

```python
# app/services/contract_service.py (single service)
class ContractService:
    def __init__(self, db):
        self.db = db

    async def get_contract(self, contract_id: str, *, include_sections: bool = False):
        """Unified contract retrieval — used by both admin and public routes."""
        ...

    async def create_contract(self, data: ContractCreate, created_by: str):
        """Business rule: validate milestone dates, compute totals."""
        ...

# app/api/contracts_admin.py (auth-required routes)
@router.get("/{contract_id}")
async def get_contract(
    contract_id: str,
    service: ContractService = Depends(get_contract_service),
    user: ExtendedAuthUser = Depends(require_admin),
):
    return await service.get_contract(contract_id, include_sections=True)

# app/api/contracts_public.py (token-based routes)
@router.get("/view/{token}")
async def view_contract_public(
    token: str,
    service: ContractService = Depends(get_contract_service),
):
    return await service.get_contract_by_token(token)
```

**Files to Change**: `contracts.py`, `vendor_management.py`, `vendor_contract_public.py`, new `contract_service.py`
**Risk**: Medium — need to verify all frontend contract pages reference correct endpoints
**Estimated Effort**: 1 sprint day

---

## P0-10: Consolidate Form APIs

**Current State**: Forms are served from 3 files:
- `forms.py` — Core form CRUD + public submission
- `vendor_forms.py` — Vendor-specific form endpoints
- Various components reference forms differently

**Problem**: Two separate form models and services for what is essentially the same entity.

**Research-Backed Approach**:

Per the MongoDB Polymorphic Pattern Guide [5] (January 2026), the correct approach for
related-but-different document types in a single collection is:

1. **Discriminator field** — add `form_type` as the type identifier (`"vendor_intake"`,
   `"rsvp_custom"`, `"general"`) [5].
2. **Conditional validation** — use MongoDB's `$jsonSchema` with `oneOf` for
   type-specific field requirements [5].
3. **Compound indexes including discriminator** — `{ form_type: 1, created_by: 1, created_at: -1 }` [5].
4. **Single service + route aliases** — merge routes into `forms.py` with type filtering,
   keep `vendor_forms.py` as thin aliases for backward compat (1 sprint deprecation window).

**Implementation**:

```python
# app/models/form.py
class FormModel(BaseModel):
    form_type: str = Field("general", description="Discriminator: vendor_intake | rsvp_custom | general")
    # ... shared fields ...

# MongoDB index
db.forms.create_index([("form_type", 1), ("created_by", 1), ("created_at", -1)])
```

**Files to Change**: `forms.py`, `vendor_forms.py`, `form_service.py`, `models/form.py`
**Risk**: Low — forms are relatively isolated
**Estimated Effort**: 0.5 sprint days

---

## P0-11: Fix Subscription Dual-State

**Current State**: Subscription state lives in TWO places:
- `users` collection: `subscription_status`, `trial_end_date`, embedded fields
- `user_subscriptions` collection: Full subscription lifecycle documents

**Problem**: On updates (webhook, admin action), both must be synchronized. If one is
updated and the other isn't, the user sees inconsistent state.

**Research-Backed Approach**:

The Sequin "Stripe as Source of Truth" guide [6] makes the critical point that **Stripe
itself should be the authoritative source**, not your local database. Your local DB is a
**synchronized cache** of Stripe state. The SaaSBase series [7] reinforces: "wait for
Stripe to confirm that a particular plan has been successfully assigned to a customer and
then update the database accordingly."

The idempotent webhook pattern from the NestJS Stripe guide [8] provides the implementation
model:

1. **Stripe is the authority** — never write subscription state from your app first.
   Always wait for webhook confirmation [6][7].
2. **Single local collection** — `user_subscriptions` is the sole synchronized cache.
   The `users` collection gets a computed `subscription_summary` read at query time.
3. **Webhook event deduplication** [8] — store processed event IDs in a `webhook_events`
   collection with a unique index on `stripe_event_id`. On receipt, check if already
   processed → return 200 early.
4. **Optimistic locking** [8] — add a `version` field to `user_subscriptions`. On
   update, include `version` in the query filter. If it doesn't match (concurrent
   modification), retry.
5. **Event status tracking** [8] — each webhook event goes through
   `processing → processed | failed`, enabling debugging and manual retry.

**Implementation**:

```python
# app/models/webhook_event.py (NEW — event deduplication)
class WebhookEvent(BaseModel):
    stripe_event_id: str        # unique index
    event_type: str
    status: str = "processing"  # processing | processed | failed
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Indexes
db.webhook_events.create_index("stripe_event_id", unique=True)
db.webhook_events.create_index([("status", 1), ("created_at", 1)])

# app/services/stripe_webhook_service.py
async def handle_webhook(self, event_id: str, event_type: str, data: dict):
    # Step 1: Deduplication check
    existing = await self.db.webhook_events.find_one({"stripe_event_id": event_id})
    if existing and existing["status"] == "processed":
        return {"success": True, "deduplicated": True}

    # Step 2: Log event
    await self.db.webhook_events.insert_one({
        "stripe_event_id": event_id,
        "event_type": event_type,
        "status": "processing",
        "created_at": datetime.utcnow(),
    })

    try:
        # Step 3: Process with optimistic locking
        await self._process_event(event_type, data)

        # Step 4: Mark processed
        await self.db.webhook_events.update_one(
            {"stripe_event_id": event_id},
            {"$set": {"status": "processed", "processed_at": datetime.utcnow()}},
        )
    except Exception as e:
        await self.db.webhook_events.update_one(
            {"stripe_event_id": event_id},
            {"$set": {"status": "failed", "error_message": str(e)}},
        )
        raise

# Computed subscription summary for user profile
async def get_user_with_subscription(self, user_id: str):
    pipeline = [
        {"$match": {"_id": ObjectId(user_id)}},
        {"$lookup": {
            "from": "user_subscriptions",
            "localField": "_id",
            "foreignField": "user_id",
            "as": "subscription",
        }},
        {"$addFields": {
            "subscription_summary": {"$arrayElemAt": ["$subscription", 0]},
        }},
        {"$project": {"subscription": 0}},  # drop raw lookup
    ]
    return await self.db.users.aggregate(pipeline).to_list(1)
```

**Cleanup Cron**: Schedule a weekly job to delete processed webhook events older than 30
days [8], preventing collection bloat while maintaining audit trail.

**Files to Change**: `subscription_service.py`, `user_management.py`, `admin_auth.py`,
`models/subscription.py`, new `models/webhook_event.py`, new `stripe_webhook_service.py`
**Risk**: High — Stripe webhooks must be updated atomically
**Estimated Effort**: 2 sprint days

---

## P0-12: Subscription State Machine

**Current State**: No explicit state machine. Trial management, subscription management,
and Stripe webhooks each implement their own logic for state transitions.

**Research-Backed Approach**:

The idempotent webhook pattern [8] establishes that state transitions must be validated
before execution. Combined with the "Stripe as source of truth" principle [6], the state
machine enforces that:

1. **Only valid transitions execute** — a `CANCELLED` subscription cannot go to `PAST_DUE`.
2. **Each transition is idempotent** — processing the same event twice is a no-op [8].
3. **Stripe event ordering cannot be guaranteed** [8] — the state machine must handle
   out-of-order events gracefully by checking current state, not assumed sequence.

```python
# app/services/subscription_state_machine.py
from enum import Enum
from typing import Dict, Set

class SubState(str, Enum):
    PENDING_SETUP = "pending_setup"
    TRIAL = "trial"
    TRIAL_EXPIRING = "trial_expiring"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

# Valid transitions: {current_state: {allowed_target_states}}
TRANSITIONS: Dict[SubState, Set[SubState]] = {
    SubState.PENDING_SETUP: {SubState.TRIAL},
    SubState.TRIAL: {SubState.TRIAL_EXPIRING, SubState.ACTIVE},
    SubState.TRIAL_EXPIRING: {SubState.ACTIVE, SubState.EXPIRED},
    SubState.ACTIVE: {SubState.PAST_DUE, SubState.CANCELLED},
    SubState.PAST_DUE: {SubState.ACTIVE, SubState.CANCELLED},
    SubState.CANCELLED: {SubState.ACTIVE},  # re-subscribe
    SubState.EXPIRED: {SubState.ACTIVE},     # re-subscribe
}

class SubscriptionStateMachine:
    def __init__(self, db):
        self.db = db

    async def transition(self, user_id: str, target: SubState, *, trigger: str, metadata: dict = None):
        """
        Attempt a state transition with optimistic locking.

        Uses findOneAndUpdate with the current state in the filter to prevent
        race conditions — if another webhook already changed the state, the
        update will match zero docs and we retry or skip.
        """
        sub = await self.db.user_subscriptions.find_one({"user_id": user_id})
        if not sub:
            raise ValueError(f"No subscription found for user {user_id}")

        current = SubState(sub["status"])
        if target not in TRANSITIONS.get(current, set()):
            # Out-of-order event — log but don't crash
            logger.warning(
                f"Invalid transition {current} → {target} for user {user_id} "
                f"(trigger: {trigger}). Skipping."
            )
            return None

        # Optimistic lock: only update if status hasn't changed since we read it
        result = await self.db.user_subscriptions.find_one_and_update(
            {"user_id": user_id, "status": current.value, "version": sub["version"]},
            {
                "$set": {"status": target.value, "updated_at": datetime.utcnow()},
                "$inc": {"version": 1},
                "$push": {"history": {
                    "from": current.value,
                    "to": target.value,
                    "trigger": trigger,
                    "metadata": metadata,
                    "at": datetime.utcnow(),
                }},
            },
            return_document=True,
        )

        if not result:
            logger.warning(f"Optimistic lock failed for user {user_id}; state may have changed concurrently")
            return None

        # Emit notification event (consumed by P0-15 unified notification system)
        await self._emit_event(user_id, current, target, trigger)
        return result
```

**Files to Change**: New `subscription_state_machine.py`, update `stripe_service.py`,
`subscription_service.py`, `trial_expiration_service.py`
**Risk**: Medium — must be tested against real Stripe webhook sequences
**Estimated Effort**: 1.5 sprint days
**Dependency**: P0-11 (single source of truth must exist first)

---

## P0-13: Link Stripe Payment Requests to Budget

**Current State**:
- `payment_requests` in vendor management track Stripe payment intents for vendor invoices
- `budget.payments` track manual payment records entered by planners
- No link between them

**Research-Backed Approach**:

The Sequin guide [6] establishes that "having order and subscription data in your own
database" is essential for efficient queries, but Stripe remains authoritative. Apply the
same principle to payments:

1. **Stripe payment_intent as foreign key** — add `stripe_payment_intent_id` to `PaymentRecord`.
2. **Webhook-driven sync** — on `payment_intent.succeeded`, auto-create budget entry [6][7].
3. **Idempotent creation** — use the same deduplication pattern from P0-11 to prevent
   duplicate budget entries on webhook retries [8].

**Implementation**:

```python
# app/models/budget.py
class PaymentRecord(BaseModel):
    # ... existing fields ...
    stripe_payment_intent_id: Optional[str] = None  # NEW
    stripe_sync_status: Optional[str] = None         # NEW: "synced" | "manual"

# In webhook handler
async def handle_payment_succeeded(self, payment_intent: dict):
    """Auto-create budget payment record when Stripe payment succeeds."""
    # Check if already synced (idempotent)
    existing = await self.db.budget_payments.find_one({
        "stripe_payment_intent_id": payment_intent["id"]
    })
    if existing:
        return  # Already synced

    # Look up vendor assignment to find wedding + budget category
    vendor_payment = await self.db.payment_requests.find_one({
        "stripe_payment_intent_id": payment_intent["id"]
    })
    if not vendor_payment:
        return  # Not a vendor payment

    # Create budget entry
    await self.db.budget_payments.insert_one({
        "wedding_id": vendor_payment["wedding_id"],
        "category_id": vendor_payment.get("budget_category_id"),
        "amount": payment_intent["amount"] / 100,
        "description": f"Stripe payment to {vendor_payment.get('vendor_name', 'vendor')}",
        "stripe_payment_intent_id": payment_intent["id"],
        "stripe_sync_status": "synced",
        "created_at": datetime.utcnow(),
    })
```

**Files to Change**: `models/budget.py`, `budget_service.py`, `stripe_service.py`, `vendor_management.py`
**Risk**: Low — additive change, doesn't break existing manual entries
**Estimated Effort**: 1 sprint day

---

## P0-15: Unify Notification System

**Current State**: Three independent notification systems:
1. **Platform notifications** (`notification_management.py`) — stored in `notifications`
2. **Planner activity notifications** (`planner_notifications.py`) — stored in `planner_activity_notifications`
3. **SSE stream** (`notification_stream.py`) — reads from both above

**Problem**: Each has its own model, service, and API. No unified query. Bell icon counts
combine both but the APIs are separate.

**Research-Backed Approach**:

The MongoDB Polymorphic Pattern [5] is the exact solution for this. From the January 2026
guide: "The polymorphic pattern enables storing heterogeneous documents in a single
collection using a discriminator field to identify document types."

The FastAPI SSE documentation [9] (official, 2025) shows the modern pattern using
`EventSourceResponse` with async generators, built-in keep-alive pings, and
`Last-Event-ID` header support for connection resumption.

**Implementation**:

```python
# 1. Unified notification model with discriminator [5]
class NotificationBase(BaseModel):
    notification_type: str  # "platform" | "activity" | "reminder"
    user_id: str
    title: str
    message: str
    read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Type-specific fields are optional — only populated for their type
    # Platform-specific
    severity: Optional[str] = None  # "info" | "warning" | "error"
    # Activity-specific
    source_type: Optional[str] = None   # "guest" | "vendor" | "contract"
    source_id: Optional[str] = None
    wedding_id: Optional[str] = None
    action: Optional[str] = None        # "rsvp_received" | "contract_signed" etc.

# 2. Indexes following polymorphic best practices [5]
db.notifications.create_index([
    ("notification_type", 1), ("user_id", 1), ("created_at", -1)
])
db.notifications.create_index(
    {"user_id": 1, "created_at": -1},
    partialFilterExpression={"read": False}  # fast unread count
)

# 3. Single NotificationService [1][2]
class NotificationService:
    def __init__(self, db):
        self.db = db

    async def create(self, notification: NotificationBase) -> str:
        result = await self.db.notifications.insert_one(notification.dict())
        return str(result.inserted_id)

    async def get_all(self, user_id: str, *, types: list[str] = None, unread_only: bool = False):
        query = {"user_id": user_id}
        if types:
            query["notification_type"] = {"$in": types}
        if unread_only:
            query["read"] = False
        cursor = self.db.notifications.find(query).sort("created_at", -1).limit(50)
        return await cursor.to_list(50)

    async def get_unread_count(self, user_id: str) -> dict:
        """Faceted count by type [5]."""
        pipeline = [
            {"$match": {"user_id": user_id, "read": False}},
            {"$facet": {
                "platform": [{"$match": {"notification_type": "platform"}}, {"$count": "n"}],
                "activity": [{"$match": {"notification_type": "activity"}}, {"$count": "n"}],
                "total": [{"$count": "n"}],
            }},
        ]
        result = await self.db.notifications.aggregate(pipeline).to_list(1)
        return result[0] if result else {"platform": [], "activity": [], "total": []}

# 4. SSE endpoint using FastAPI's built-in EventSourceResponse [9]
from fastapi.sse import EventSourceResponse, ServerSentEvent

@router.get("/stream", response_class=EventSourceResponse)
async def notification_stream(
    last_event_id: Annotated[int | None, Header()] = None,
    user: ExtendedAuthUser = Depends(require_auth),
) -> AsyncIterable[ServerSentEvent]:
    """
    SSE stream with automatic keep-alive pings (15s) and
    Last-Event-ID support for connection resumption [9].
    """
    service = NotificationService(mongo.db)
    user_id = str(user.user_data["_id"])
    last_check = datetime.utcnow()

    while True:
        new_notifications = await service.get_since(user_id, since=last_check)
        for notif in new_notifications:
            yield ServerSentEvent(
                data=notif,
                event=notif["notification_type"],
                id=str(notif["_id"]),
            )
        last_check = datetime.utcnow()
        await asyncio.sleep(2)  # poll interval
```

**Migration Strategy**:
1. Create the unified `notifications` collection with the polymorphic schema.
2. Write a one-time migration script that copies docs from `planner_activity_notifications`
   into `notifications` with `notification_type: "activity"`, and from old `notifications`
   with `notification_type: "platform"`.
3. Update services to write to the new collection.
4. Keep old API routes as thin wrappers for 1 sprint (backward compat).
5. Remove old routes + collections after frontend migration.

**Files to Change**: `models/planner_notification.py` (merge into unified),
`notification_service.py`, `planner_notification_service.py`, `notification_stream.py`
**Risk**: High — must migrate existing data; SSE format must remain backward compatible
**Estimated Effort**: 2 sprint days

---

## NEW: Next.js 16 Proxy Migration

**Research Finding**: Next.js 16 introduced `proxy.ts` [10], which replaces static
`next.config.js` rewrites with programmable, type-safe request forwarding. Our current
`next.config.js` uses static rewrites to proxy API requests to the FastAPI backend.

**Why Migrate**: Per the Next.js 16 Proxy Architecture guide [10]:
- `proxy.ts` supports hot reload (instant vs 5-10s restart for config changes)
- Enables runtime logic (dynamic routing, header injection, auth token forwarding)
- Supports the Backend-for-Frontend (BFF) pattern — keeps API keys server-side
- Built-in duplex streaming and connection pooling

**Implementation** (when upgrading to Next.js 16):

```typescript
// src/proxy.ts
import { type ProxyRequest, NextResponse } from 'next/server';

export const config = {
  matcher: '/api/proxy/:path*',
};

export default async function proxy(req: ProxyRequest) {
  const backendUrl = process.env.BACKEND_SERVICE_URL || 'http://localhost:8000';
  const path = req.nextUrl.pathname.replace('/api/proxy', '');
  const destination = new URL(path + req.nextUrl.search, backendUrl);

  const headers = new Headers(req.headers);
  // Forward auth headers, strip internal-only ones
  headers.delete('x-internal-only');

  try {
    const response = await fetch(destination, {
      method: req.method,
      headers,
      body: req.body,
    });

    if (response.status === 401) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    return response;
  } catch (err) {
    console.error('Proxy failure:', err);
    return new Response('Bad Gateway', { status: 502 });
  }
}
```

**Note**: This is a future migration — our current Next.js version uses `next.config.js`
rewrites which work fine. Capture this as a tech-debt item for the Next.js 16 upgrade.

**Risk**: Low (when done during version upgrade)
**Estimated Effort**: 0.5 sprint days (during Next.js upgrade sprint)

---

## Priority Order (Updated with Research)

| Item | Risk | Effort | Dependencies | Recommended Sprint |
|------|------|--------|-------------|-------------------|
| Type Sync (pydantic-to-typescript) | Low | 0.25d | None | Sprint N (do first) |
| P0-10 (Forms — polymorphic discriminator) | Low | 0.5d | None | Sprint N |
| P0-9 (Contracts — service layer) | Med | 1d | None | Sprint N |
| P0-13 (Budget-Stripe — idempotent sync) | Low | 1d | None | Sprint N |
| P0-11 (Subscription — Stripe as SoT) | High | 2d | None | Sprint N+1 |
| P0-12 (State Machine — optimistic lock) | Med | 1.5d | P0-11 | Sprint N+1 |
| P0-15 (Notifications — polymorphic + SSE) | High | 2d | None | Sprint N+1 |
| Next.js 16 Proxy Migration | Low | 0.5d | Next.js upgrade | Future sprint |

**Total estimated effort: ~8.75 sprint days across 2-3 sprints**

---

## References

1. [Production-Ready FastAPI Project Structure (2026 Guide)](https://dev.to/thesius_code_7a136ae718b7/production-ready-fastapi-project-structure-2026-guide-b1g) — DEV Community, 2026. Covers layered architecture, service layer, DI patterns, and route aggregation.

2. [FastAPI Services Layer Best Practices](https://medium.com/@hadiyolworld007/fastapi-services-layer-best-practices-49b89368982d) — Medium, 2025. "The endpoint function should be very simple: receive an HTTP request, delegate to the corresponding service, and return the response."

3. [Combining FastAPI Dependency Injection with Service and Repository Layers](https://blog.dotcs.me/posts/fastapi-dependency-injection-x-layers) — blog.dotcs.me, 2025. Multi-layer DI chain pattern.

4. [pydantic-to-typescript](https://github.com/phillipdupuis/pydantic-to-typescript) — GitHub. CLI tool + GitHub Action for automated Pydantic → TypeScript interface generation.

5. [How to Implement MongoDB Polymorphic Patterns](https://oneuptime.com/blog/post/2026-01-30-mongodb-polymorphic-patterns/view) — OneUptime, January 2026. Covers discriminator fields, conditional validation, indexing strategies, and notification system example.

6. [Managing Stripe as a Source of Truth](https://blog.sequin.io/stripe-source-of-truth/) — Sequin. "Having order and subscription data in your own database" while keeping Stripe authoritative. Covers webhook vs API-response sync trade-offs.

7. [Building a Subscription System using Stripe, Node.js, and MongoDB](https://medium.com/saasbase/adding-managing-and-keeping-track-of-subscription-payments-using-stripe-and-mongo-for-your-saas-3046439f9ed6) — SaaSBase/Medium. 5-part series on webhook-driven subscription state management.

8. [Building Reliable Stripe Subscriptions: Webhook Idempotency and Optimistic Locking](https://dev.to/aniefon_umanah_ac5f21311c/building-reliable-stripe-subscriptions-in-nestjs-webhook-idempotency-and-optimistic-locking-3o91) — DEV Community, 2025. webhook_events table schema, deduplication, version column, and retry patterns.

9. [Server-Sent Events (SSE) — FastAPI Official Documentation](https://fastapi.tiangolo.com/tutorial/server-sent-events/) — FastAPI docs, 2025. EventSourceResponse, async generators, Last-Event-ID resumption, keep-alive pings.

10. [Next.js 16 Proxy Architecture: API Gateway Patterns](https://learnwebcraft.com/learn/nextjs/nextjs-16-proxy-ts-changes-everything) — LearnWebCraft, 2026. proxy.ts replaces next.config.js rewrites with programmable, type-safe proxying.

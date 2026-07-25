import asyncio
import logging
import os
import time
from datetime import UTC, datetime
from typing import Optional

from bson import ObjectId
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing_extensions import TypedDict

from app.core.cache import cache
from app.core.database import mongo
from app.models.subscription import (
    PLANNER_BLOCKED_SUBSCRIPTION_STATUSES,
    SubscriptionStatus,
    normalize_subscription_status,
)
from app.models.team_member import resolve_team_permissions
from app.utils import team_subscription_gate
from app.utils.auth_utils import verify_token
from app.utils.communication_access import (
    CommunicationCapability,
    enforce_communication_capability,
)
from app.utils.planner_ownership import (
    normalize_planner_email,
    normalize_planner_id,
    normalize_wedding_query_id,
    wedding_belongs_to_owner,
)

logger = logging.getLogger(__name__)

# ── Subscription block reasons (shared between planner and team-member paths) ──
_SUB_BLOCK_REASONS = {
    "pending": "Please complete your subscription checkout to access the platform.",
    "pending_checkout": "Please complete your Stripe checkout to activate your subscription.",
    "pending_payment": "Please complete your subscription payment to access the platform.",
    "inactive": "Please choose a plan and complete checkout to access the platform.",
    "cancelled": "Your subscription has been cancelled. Please resubscribe to continue.",
    "past_due": "Your latest subscription payment failed. Please update your payment method to continue.",
    "suspended": "Your subscription is suspended due to a payment issue. Please update your payment method.",
    "expired": "Free trial has expired. Please upgrade your subscription to continue using the platform.",
}
_DEFAULT_SUB_BLOCK_REASON = "Subscription issue. Please contact support."


def _build_team_member_block_reason(
    owner_sub_status: str | None, owner_email: str | None
) -> str:
    """Compatibility wrapper around the shared team-member billing helper.

    Keep the leading-underscore local name so existing call sites and tests in
    this module do not churn, while delegating the actual phrasing to the
    shared helper module.
    """
    return team_subscription_gate.build_team_member_block_reason(
        owner_sub_status, owner_email
    )


# ── Team member data cache (bounded, thread-safe, with invalidation) ──
_TEAM_CACHE_TTL = 60  # seconds
_TEAM_CACHE_MAX_SIZE = 500
_team_cache: dict = {}
_team_cache_lock = asyncio.Lock()


async def _get_cached_team_data(user_id: str) -> dict | None:
    """Get cached team data if not expired (thread-safe)"""
    async with _team_cache_lock:
        entry = _team_cache.get(user_id)
        if entry and time.time() - entry["ts"] < _TEAM_CACHE_TTL:
            return entry["data"]
        # Remove expired entry if it exists
        if entry:
            del _team_cache[user_id]
        return None


async def _set_team_cache(user_id: str, data: dict) -> None:
    """Set cached team data with timestamp (thread-safe, bounded)"""
    async with _team_cache_lock:
        _team_cache[user_id] = {"data": data, "ts": time.time()}
        # Evict oldest entries if over capacity
        if len(_team_cache) > _TEAM_CACHE_MAX_SIZE:
            sorted_keys = sorted(_team_cache.keys(), key=lambda k: _team_cache[k]["ts"])
            # Remove oldest 20% to avoid frequent evictions
            evict_count = max(1, len(sorted_keys) // 5)
            for k in sorted_keys[:evict_count]:
                del _team_cache[k]


def invalidate_team_cache(user_id: str) -> None:
    """Invalidate cache for a specific team member (called on permission changes).
    Synchronous because it's called from non-async contexts too."""
    _team_cache.pop(user_id, None)


def invalidate_team_cache_by_owner(owner_id: str) -> None:
    """Invalidate all cached entries for a given owner (e.g., on bulk changes).
    Synchronous for simplicity."""
    keys_to_remove = [
        k
        for k, v in _team_cache.items()
        if v.get("data", {}).get("owner_id") == owner_id
    ]
    for k in keys_to_remove:
        _team_cache.pop(k, None)


# ── Auth user cache (Redis-backed, short TTL) ────────────────────────────
# Caches the assembled ``ExtendedAuthUser`` shape so that successive
# requests within the cache window do not pay 2-4 Mongo reads each.
#
# Design notes:
#   * Key shape: ``auth:user:{email}``.  Email is the primary lookup key
#     used by ``get_current_user_extended`` and is already normalized by
#     the JWT signing flow.
#   * 10-second TTL.  Short enough that subscription state mutations
#     (Stripe webhooks, trial expiry) propagate to live sessions within
#     a single visible blink, without needing invalidation at every
#     mutation site.  Long enough that a single user click (which fires
#     5-10 XHRs in ~1 s) hits cache for everything past the first.
#   * What is cached: the assembled ``ExtendedAuthUser`` snapshot, not
#     the raw Mongo docs.  This means a cache hit also avoids the
#     ``compute_owner_subscription_block`` work for team members.
#   * What is NOT cached: ROOT_ADMIN (low frequency, sensitive enough
#     to read fresh every time), the per-request 402 subscription gate
#     (depends on ``request.url.path`` — re-evaluated each request),
#     the ``last_active_at`` write for team members (already throttled).
#   * Failure mode: if Redis is disabled or unreachable, ``CacheManager``
#     returns ``None`` from ``get`` and ``False`` from ``set``.  The
#     dependency falls through to the existing Mongo path.  No regression.
#
# Explicit invalidation is only required at the highest-impact mutation
# sites: Stripe webhook handlers that flip subscription status, and the
# inline trial-auto-expire branch in ``get_current_user_extended``.
# Other mutations are tolerated as "eventually consistent within 10 s."

_AUTH_USER_CACHE_TTL_SECONDS = 10


def _auth_user_cache_key(email: str) -> str:
    return f"auth:user:{email.lower()}"


def _serialize_auth_user(auth_user: "ExtendedAuthUser") -> dict:
    """Convert ``ExtendedAuthUser`` to a JSON-serializable snapshot.

    ``user_data`` is already JSON-safe at this point: ``_id`` has been
    converted to ``str`` (see line ~247) and datetimes are handled by
    the cache layer's ``_json_default`` hook.
    """
    return {
        "email": auth_user.email,
        "role": auth_user.role,
        "user_data": auth_user.user_data,
        "team_permissions": auth_user.team_permissions,
        "team_role": auth_user.team_role,
        "team_wedding_access": auth_user.team_wedding_access,
        "team_assigned_wedding_ids": list(auth_user.team_assigned_wedding_ids or []),
        "team_owner_email": auth_user.team_owner_email,
        "parent_planner_id": auth_user.parent_planner_id,
    }


def _deserialize_auth_user(snapshot: dict) -> "ExtendedAuthUser":
    """Rehydrate a cached snapshot back into ``ExtendedAuthUser``."""
    auth_user = ExtendedAuthUser(
        email=snapshot["email"],
        role=snapshot["role"],
        user_data=snapshot.get("user_data") or {},
    )
    auth_user.team_permissions = snapshot.get("team_permissions")
    auth_user.team_role = snapshot.get("team_role")
    auth_user.team_wedding_access = snapshot.get("team_wedding_access")
    auth_user.team_assigned_wedding_ids = (
        snapshot.get("team_assigned_wedding_ids") or []
    )
    auth_user.team_owner_email = snapshot.get("team_owner_email")
    auth_user.parent_planner_id = snapshot.get("parent_planner_id")
    return auth_user


async def _get_cached_auth_user(email: str) -> Optional["ExtendedAuthUser"]:
    """Return the cached auth user for ``email``, or ``None`` on miss.

    Fail-open: any cache exception (Redis down, deserialize failure)
    returns ``None`` so the caller falls through to the Mongo path.
    """
    if not email:
        return None
    try:
        snapshot = await cache.get(_auth_user_cache_key(email))
        if not snapshot or not isinstance(snapshot, dict):
            return None
        return _deserialize_auth_user(snapshot)
    except Exception as e:
        logger.debug(f"Auth cache get failed for {email}: {e}")
        return None


async def _set_cached_auth_user(auth_user: "ExtendedAuthUser") -> None:
    """Cache the assembled auth user. Best-effort, fail-open."""
    if not auth_user or not auth_user.email:
        return
    try:
        snapshot = _serialize_auth_user(auth_user)
        await cache.set(
            _auth_user_cache_key(auth_user.email),
            snapshot,
            expire=_AUTH_USER_CACHE_TTL_SECONDS,
        )
    except Exception as e:
        logger.debug(f"Auth cache set failed for {auth_user.email}: {e}")


async def invalidate_auth_cache(email: str) -> None:
    """Bust the cached auth user for ``email``.

    Call this from any mutation site that changes a field the cache
    depends on: ``users.subscription_status``, ``users.is_active``,
    ``users.role``, ``users.email_verified``, ``users.team_member_id``,
    ``user_subscriptions.status``, or ``team_members.{role,
    custom_permissions, status, wedding_access, assigned_wedding_ids}``
    for a known team member's email.
    """
    if not email:
        return
    try:
        await cache.delete(_auth_user_cache_key(email))
    except Exception as e:
        logger.debug(f"Auth cache invalidate failed for {email}: {e}")


async def invalidate_auth_cache_by_user_id(user_id: str | None) -> None:
    """Bust the auth cache for a user identified by Mongo ``_id``.

    Useful for callers that have ``user_id`` but not email — most
    notably Stripe webhook handlers that key off
    ``subscription.metadata.user_id``.  Performs a single email lookup
    and delegates to :func:`invalidate_auth_cache`.

    Fail-open: any error during lookup or invalidation is logged at
    debug level and swallowed; the cache will expire naturally within
    the TTL window.
    """
    if not user_id:
        return
    try:
        user_doc = await mongo.get_users_collection().find_one(
            {"_id": ObjectId(user_id)}, {"email": 1}
        )
        if user_doc and user_doc.get("email"):
            await invalidate_auth_cache(user_doc["email"])
    except Exception as e:
        logger.debug(f"Auth cache invalidate-by-user-id failed for {user_id}: {e}")


def _apply_subscription_gate(
    auth_user: "ExtendedAuthUser", request: Request | None
) -> None:
    """Re-evaluate the 402 subscription gate against ``request.url.path``.

    Runs on every request — must NOT be cached, because the whitelist
    decision depends on the request path.  Raises HTTPException(402) if
    the user is blocked and the path is not whitelisted.
    """
    if not auth_user.user_data.get("_subscription_blocked") or request is None:
        return
    path = request.url.path
    _SUB_WHITELIST = (
        "/admin/profile",
        "/admin/token",
        "/admin/logout",  # blocked team members must be able to sign out
        "/admin/team/permissions",  # blocked-page UX reads its own permission metadata
        "/stripe/",
        "/api/stripe/",
        "/public/",
        "/users/",  # subscription management self-view
        "/subscription-plans",  # view available plans
    )
    if any(path.startswith(p) or f"/{p.lstrip('/')}" in path for p in _SUB_WHITELIST):
        return
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=auth_user.user_data.get(
            "_subscription_block_reason",
            "Subscription issue. Please upgrade your plan.",
        ),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def compute_owner_subscription_block(
    owner_id: str | None, owner_email: str | None
) -> tuple[bool, str | None]:
    """Compatibility wrapper around the shared helper.

    auth_extended tests patch this module's ``mongo`` handle directly. Route
    the shared helper through that same handle so the refactor to
    ``app.utils.team_subscription_gate`` does not bypass the patched
    dependency during tests or future scoped-call sites.
    """
    return await team_subscription_gate.compute_owner_subscription_block(
        owner_id=owner_id,
        owner_email=owner_email,
        mongo_client=mongo,
    )


# Security scheme
security = HTTPBearer(auto_error=False)

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


def should_backfill_vendor_email_verification(user_data: dict, role: str) -> bool:
    """Allow legacy approved vendor self-signups to self-heal missing verification."""
    return (
        role == "advertising_vendor"
        and user_data.get("registration_source") == "vendor_self_signup"
        and user_data.get("vendor_account_status") == "active"
    )


class ExtendedAuthUser:
    """Extended auth user supporting multiple roles including team members"""

    def __init__(self, email: str, role: str, user_data: dict | None = None):
        self.email = email
        self.role = role
        self.user_data = user_data or {}
        self.subscription_status: str | None = (
            self.user_data.get("subscription_status") if self.user_data else None
        )
        # Role-specific properties
        root_admin_email = os.getenv(
            "ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"
        )
        self.is_root_admin = role == "ROOT_ADMIN" and email == root_admin_email
        self.is_wedding_planner = role == "wedding_planner"
        self.is_vendor = role == "vendor"
        self.is_team_member = role == "team_member"
        self.is_advertising_vendor = role == "advertising_vendor"

        # Team member properties (populated by get_current_user_extended for team members)
        self.parent_planner_id: str | None = (
            user_data.get("parent_planner_id") if user_data else None
        )
        self.team_member_id: str | None = (
            user_data.get("team_member_id") if user_data else None
        )
        self.team_role: str | None = user_data.get("team_role") if user_data else None
        self.team_permissions: dict | None = None
        self.team_wedding_access: str | None = None  # "all" or "assigned"
        self.team_assigned_wedding_ids: list[str] = []
        self.team_owner_email: str | None = None


class CalendarOwnerScope(TypedDict):
    owner_id: str | None
    owner_email: str | None
    accessible_wedding_ids: list[str] | None
    is_owner: bool
    is_team_member: bool


async def get_current_user_extended(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    request: Request = None,  # type: ignore[assignment]
) -> ExtendedAuthUser:
    """Get current authenticated user supporting both legacy and new auth systems"""
    token = credentials.credentials if credentials else None
    if not token and request is not None:
        token = request.cookies.get("admin_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = verify_token(token)
        email = payload.get("sub")
        role = payload.get("role")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_data = {}

        # ── Auth user cache check ────────────────────────────────────
        # Skip the cache for ROOT_ADMIN (low frequency, sensitive).
        # For all other identities, try Redis first; on hit, re-run the
        # request-scoped 402 gate against the current path and return.
        # On miss, fall through to the full Mongo path below and write
        # the assembled snapshot before returning.
        root_admin_email = os.getenv(
            "ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"
        )
        if email != root_admin_email:
            cached_auth_user = await _get_cached_auth_user(email)
            if cached_auth_user is not None:
                _apply_subscription_gate(cached_auth_user, request)
                return cached_auth_user

        # Check if this is the ROOT_ADMIN
        if email == root_admin_email:
            # ROOT_ADMIN must exist in the users collection
            user = await mongo.get_users_collection().find_one({"email": email})
            if user:
                # ROOT_ADMIN always has full access
                role = "ROOT_ADMIN"
                user_data = user.copy()
                # Convert ObjectId to string for consistent data types
                if "_id" in user_data and isinstance(user_data["_id"], ObjectId):
                    user_data["_id"] = str(user_data["_id"])
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Root admin user not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # For other users, check the new users collection first, then legacy
            user = await mongo.get_users_collection().find_one({"email": email})
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user_data = user.copy()  # Make a copy to avoid modifying the original
            # Convert ObjectId to string for consistent data types
            if "_id" in user_data and isinstance(user_data["_id"], ObjectId):
                user_data["_id"] = str(user_data["_id"])
            role = user.get("role", "wedding_planner")
            # Check if account is active (early check, before team data hydration)
            if not user_data.get("is_active", True):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account has been deactivated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # Check email verification for new accounts
            if not user_data.get("email_verified"):
                if should_backfill_vendor_email_verification(user_data, role):
                    verified_at = user_data.get("approved_at") or datetime.now(UTC)
                    await mongo.get_users_collection().update_one(
                        {"email": email},
                        {
                            "$set": {
                                "email_verified": True,
                                "email_verified_at": verified_at,
                            }
                        },
                    )
                    user_data["email_verified"] = True
                    user_data["email_verified_at"] = verified_at
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Email address not verified. Please check your email and verify your account.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            # Tag users with subscription issues — don't block here so they can
            # still access profile and billing endpoints to upgrade/reactivate.
            sub_status = normalize_subscription_status(
                user_data.get("subscription_status")
            )
            if sub_status:
                user_data["subscription_status"] = sub_status

            # ── RACE CONDITION FIX (Prong 1): Cross-check user_subscriptions ──
            # If webhook hasn't updated users collection yet but has updated
            # user_subscriptions, trust the more recent subscription status.
            user_id_str = str(user_data.get("_id", ""))
            if user_id_str and role == "wedding_planner":
                try:
                    subscription_record = await mongo.db["user_subscriptions"].find_one(
                        {"user_id": user_id_str}, {"status": 1, "updated_at": 1}
                    )
                    if subscription_record:
                        sub_record_status = subscription_record.get("status")
                        # If subscription says "cancelled" but users says "active",
                        # trust the subscription record (it's more recent)
                        if (
                            sub_record_status in PLANNER_BLOCKED_SUBSCRIPTION_STATUSES
                            and sub_status not in PLANNER_BLOCKED_SUBSCRIPTION_STATUSES
                        ):
                            logger.info(
                                f"Webhook race detected: user_subscriptions has '{sub_record_status}' "
                                f"but users has '{sub_status}' for user {email}. "
                                f"Trusting user_subscriptions."
                            )
                            sub_status = sub_record_status
                            user_data["subscription_status"] = sub_status
                except Exception as e:
                    logger.warning(
                        f"Failed to cross-check user_subscriptions for {email}: {e}"
                    )
                    # Non-fatal: proceed with user_data subscription status

            if (
                role == "wedding_planner"
                and sub_status in PLANNER_BLOCKED_SUBSCRIPTION_STATUSES
            ):
                user_data["_subscription_blocked"] = True
                user_data["_subscription_block_reason"] = _SUB_BLOCK_REASONS.get(
                    sub_status, _DEFAULT_SUB_BLOCK_REASON
                )
            # Check trial expiration for wedding planners
            if role == "wedding_planner" and sub_status in {
                SubscriptionStatus.TRIAL.value,
                SubscriptionStatus.TRIAL_EXPIRING.value,
            }:
                trial_end_date = user_data.get("trial_end_date")
                if trial_end_date:
                    # Handle both datetime objects and ISO strings, ensuring timezone-aware
                    if isinstance(trial_end_date, str):
                        try:
                            trial_end_date = datetime.fromisoformat(
                                trial_end_date.replace("Z", "+00:00")
                            )
                        except ValueError:
                            # Parse and assume UTC if no timezone info
                            trial_end_date = datetime.fromisoformat(
                                trial_end_date
                            ).replace(tzinfo=UTC)
                    elif (
                        isinstance(trial_end_date, datetime)
                        and trial_end_date.tzinfo is None
                    ):
                        # Handle naive datetime objects from MongoDB
                        trial_end_date = trial_end_date.replace(tzinfo=UTC)
                    if datetime.now(UTC) > trial_end_date:
                        # Auto-expire the trial — update BOTH users and user_subscriptions
                        expire_time = datetime.now(UTC)
                        await mongo.get_users_collection().update_one(
                            {"email": email},
                            {
                                "$set": {
                                    "subscription_status": "expired",
                                    "trial_expired_at": expire_time,
                                }
                            },
                        )
                        # Keep user_subscriptions in sync (user_id is stored as string)
                        user_id_str = str(user_data.get("_id", ""))
                        if user_id_str:
                            await mongo.db["user_subscriptions"].update_one(
                                {
                                    "user_id": user_id_str,
                                    "status": {"$in": ["trial", "active"]},
                                },
                                {
                                    "$set": {
                                        "status": "expired",
                                        "updated_at": expire_time,
                                        "trial_expired_at": expire_time,
                                    }
                                },
                            )
                        # Tag as blocked — don't raise so user can access billing
                        user_data["subscription_status"] = "expired"
                        user_data["_subscription_blocked"] = True
                        user_data["_subscription_block_reason"] = (
                            "Free trial has expired. Please upgrade your subscription to continue using the platform."
                        )

        auth_user = ExtendedAuthUser(email=email, role=role, user_data=user_data)

        # ── Team member: hydrate permissions from team_members collection (with cache) ──
        if role == "team_member" and user_data.get("team_member_id"):
            try:
                team_member_id = user_data["team_member_id"]
                # Try to get from cache first
                cached_data = await _get_cached_team_data(team_member_id)
                if cached_data:
                    team_doc = cached_data
                else:
                    # Cache miss: query database
                    team_doc = await mongo.db["team_members"].find_one(
                        {
                            "_id": ObjectId(team_member_id),
                            "status": "active",
                        }
                    )
                    if team_doc:
                        # Store in cache for future requests
                        await _set_team_cache(team_member_id, team_doc)

                if team_doc:
                    auth_user.team_permissions = resolve_team_permissions(
                        team_doc.get("role", "viewer"),
                        team_doc.get("custom_permissions", {}),
                    )
                    auth_user.team_role = team_doc.get("role", "viewer")
                    auth_user.team_wedding_access = team_doc.get(
                        "wedding_access", "all"
                    )
                    auth_user.team_assigned_wedding_ids = team_doc.get(
                        "assigned_wedding_ids", []
                    )
                    auth_user.team_owner_email = normalize_planner_email(
                        team_doc.get("owner_email")
                    )
                    auth_user.parent_planner_id = normalize_planner_id(
                        team_doc.get("owner_id")
                    )

                    # ── Team-member billing gate ──────────────────────
                    # Inherit the subscription block from the owning planner.
                    # If the planner's subscription is past_due/suspended/expired/etc.,
                    # the whole team (including this member) is blocked from feature
                    # routes, mirroring the planner-side 402 behavior. Team members
                    # cannot pay on the planner's behalf, so the error message directs
                    # them to contact their planner.
                    (
                        owner_is_blocked,
                        owner_sub_status,
                    ) = await compute_owner_subscription_block(
                        owner_id=auth_user.parent_planner_id,
                        owner_email=auth_user.team_owner_email,
                    )
                    if owner_is_blocked:
                        user_data["_subscription_blocked"] = True
                        user_data["_subscription_block_reason"] = (
                            _build_team_member_block_reason(
                                owner_sub_status, auth_user.team_owner_email
                            )
                        )
                        user_data["_blocked_reason_source"] = "owner_subscription"
                        user_data["_owner_email"] = auth_user.team_owner_email
                        user_data["_owner_subscription_status"] = owner_sub_status

                    # Update last_active_at with throttle (only if > 5 minutes old)
                    last_active = team_doc.get("last_active_at")
                    should_update = not last_active
                    if last_active:
                        if (
                            isinstance(last_active, datetime)
                            and last_active.tzinfo is None
                        ):
                            last_active = last_active.replace(tzinfo=UTC)
                        should_update = (
                            datetime.now(UTC) - last_active
                        ).total_seconds() > 300
                    if should_update:
                        try:
                            asyncio.create_task(
                                mongo.db["team_members"].update_one(
                                    {"_id": ObjectId(team_member_id)},
                                    {"$set": {"last_active_at": datetime.now(UTC)}},
                                )
                            )
                        except Exception as e:
                            logger.debug(
                                f"Failed to update team member last_active_at: {e}"
                            )
                            # Non-critical
                else:
                    # Team membership revoked or deactivated
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Team membership is no longer active",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error loading team member data for {email}: {e}")
                # Non-fatal: allow login but without team permissions

        # ── Cache the assembled auth user ────────────────────────────
        # ROOT_ADMIN is never cached (low frequency, sensitive).  For
        # everyone else, write the assembled snapshot to Redis so the
        # next request within the TTL window short-circuits at the top
        # of this function.  Writing AFTER the team-member hydration
        # and the subscription/trial computation captures all derived
        # state (``_subscription_blocked``, team_permissions, etc.).
        if email != root_admin_email:
            await _set_cached_auth_user(auth_user)

        # ── Subscription gate ─────────────────────────────────────
        # Block expired/cancelled/suspended planners on feature endpoints.
        # Root admins are never tagged so they always pass through.
        # Whitelisted paths (profile, billing, stripe, public) are allowed
        # so expired planners can still log in and upgrade.  This gate
        # is shared with the cache-hit path via ``_apply_subscription_gate``
        # so the whitelist policy lives in exactly one place.
        _apply_subscription_gate(auth_user, request)

        return auth_user

    except HTTPException:
        # Re-raise HTTP exceptions (including trial expiration 402) as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in require_auth_extended: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Role-based dependency factories
async def require_root_admin(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """Require ROOT_ADMIN access (only thedeveloper@thespecialwedding.io)"""
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Root admin access required"
        )
    return current_user


async def require_wedding_planner(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """Require wedding planner access"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wedding planner access required",
        )
    return current_user


async def require_vendor(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """Require vendor access"""
    if not (
        current_user.is_vendor
        or current_user.is_wedding_planner
        or current_user.is_root_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Vendor access required"
        )
    return current_user


async def require_admin_or_planner(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """Require root admin, wedding planner, team member, or advertising vendor access"""
    if current_user.is_root_admin or current_user.is_wedding_planner:
        return current_user
    if current_user.is_team_member and current_user.team_permissions is not None:
        return current_user
    if current_user.is_advertising_vendor:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin or wedding planner access required",
    )


async def require_any_admin(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """Require root admin access"""
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


async def require_wedding_planner_only(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """
    Legacy dependency name retained for planner-scoped admin routes.

    ROOT_ADMIN already has full wedding access elsewhere in this module, so this
    gate must stay aligned and allow root-admin support workflows too.
    """
    if current_user.is_root_admin or current_user.is_wedding_planner:
        return current_user
    if current_user.is_team_member and current_user.team_permissions is not None:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Wedding planner access required"
    )


async def check_wedding_access(user: ExtendedAuthUser, wedding_id: str) -> bool:
    """Check if user has access to a specific wedding"""
    # ROOT_ADMIN has full access to all weddings for platform management
    if user.is_root_admin:
        return True

    if user.is_wedding_planner:
        # Check if this wedding is assigned to this planner
        # Validate and sanitize wedding_id
        if not wedding_id or not isinstance(wedding_id, str):
            return False

        # Prevent NoSQL injection by validating input
        if len(wedding_id) > 100:  # Reasonable limit
            return False

        try:
            wedding = await mongo.get_weddings_collection().find_one(
                {"_id": normalize_wedding_query_id(wedding_id)}
            )
            return wedding_belongs_to_owner(
                wedding,
                planner_id=user.user_data.get("_id"),
                planner_email=user.email,
            )
        except Exception as e:
            logger.warning(f"Error checking wedding access for user {user.email}: {e}")
            return False

    # ── Team member wedding access ──
    if user.is_team_member:
        if user.team_wedding_access == "all":
            # Team member with "all" access: check if the wedding belongs to their owner planner
            if (
                not wedding_id
                or not isinstance(wedding_id, str)
                or len(wedding_id) > 100
            ):
                return False
            try:
                wedding = await mongo.get_weddings_collection().find_one(
                    {"_id": normalize_wedding_query_id(wedding_id)}
                )
                return wedding_belongs_to_owner(
                    wedding,
                    planner_id=user.parent_planner_id,
                    planner_email=user.team_owner_email,
                )
            except Exception as e:
                logger.warning(
                    f"Error checking team wedding access for user {user.email}: {e}"
                )
                return False
        elif user.team_wedding_access == "assigned":
            # Team member with "assigned" access: must be in their list
            return wedding_id in (user.team_assigned_wedding_ids or [])
        return False

    if user.is_vendor:
        # Check if vendor has access to this wedding
        vendor = await mongo.get_vendors_collection().find_one(
            {"email": user.email, "wedding_id": wedding_id}
        )
        return vendor is not None
    return False


async def require_wedding_access(wedding_id: str):
    """Factory function to require access to a specific wedding"""

    async def wedding_access_checker(
        current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    ) -> ExtendedAuthUser:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this wedding denied",
            )
        return current_user

    return wedding_access_checker


# ─── Team-Aware Dependencies ─────────────────────────────────────────────


async def require_team_or_planner(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """
    Allow access for planner-owners, their team members, and ROOT_ADMIN.
    This replaces require_wedding_planner on endpoints that team members
    should also be able to access.
    """
    if current_user.is_root_admin:
        return current_user
    if current_user.is_wedding_planner:
        return current_user
    if current_user.is_team_member and current_user.team_permissions is not None:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Planner or team member access required",
    )


def require_communication_capability(capability: CommunicationCapability):
    """Build a dependency that enforces one canonical communication domain."""

    async def _check_communication_capability(
        current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    ) -> ExtendedAuthUser:
        enforce_communication_capability(current_user, capability)
        return current_user

    return _check_communication_capability


def require_team_permission(permission_name: str):
    """
    Factory: create a dependency that checks for a specific team permission.
    Planner-owners and ROOT_ADMIN always pass; team members need the permission.

    Usage:
        @router.post("/guests")
        async def create_guest(
            current_user = Depends(require_team_permission("manage_guests"))
        ):
            ...
    """

    async def _check_permission(
        current_user: ExtendedAuthUser = Depends(require_team_or_planner),
    ) -> ExtendedAuthUser:
        # Owners and root admin have all permissions
        if current_user.is_root_admin or current_user.is_wedding_planner:
            return current_user

        # Team member — check specific permission
        if current_user.team_permissions and current_user.team_permissions.get(
            permission_name, False
        ):
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have the '{permission_name.replace('_', ' ')}' permission.",
        )

    return _check_permission


def get_accessible_wedding_ids(user: ExtendedAuthUser) -> list[str] | None:
    """
    Utility: determine which wedding IDs a user can access.

    Returns:
        None — means "all weddings" (planner owner or team member with access=all)
        List[str] — specific wedding IDs (team member with access=assigned)
    """
    if user.is_root_admin or user.is_wedding_planner:
        return None  # No filter needed — access all
    if user.is_team_member:
        if user.team_wedding_access == "all":
            return None  # Access all of their owner's weddings
        return user.team_assigned_wedding_ids or []
    return []  # No access


def get_owner_identity(user: ExtendedAuthUser) -> tuple[str | None, str | None]:
    """Return the planner owner identity behind a planner or team-member session."""
    if user.is_wedding_planner:
        return (
            normalize_planner_id(user.user_data.get("_id")),
            normalize_planner_email(user.email),
        )
    if user.is_team_member:
        return (
            normalize_planner_id(user.parent_planner_id),
            normalize_planner_email(user.team_owner_email),
        )
    return None, None


def get_calendar_owner_identity(user: ExtendedAuthUser) -> dict[str, str | None]:
    """Return owner identity payload for calendar-scoped routes."""
    owner_id, owner_email = get_owner_identity(user)
    return {
        "owner_id": owner_id,
        "owner_email": owner_email,
        "user_id": normalize_planner_id(user.user_data.get("_id")),
        "user_email": normalize_planner_email(user.email),
    }


async def resolve_owner_scoped_user_assignments(
    owner_id: str | None,
    owner_email: str | None,
    user_ids: list[str],
) -> tuple[list[str], list[str]]:
    """Resolve assignee ids/emails and reject users outside the planner-owner scope."""
    if not user_ids:
        return [], []

    normalized_owner_id = normalize_planner_id(owner_id)
    normalized_owner_email = normalize_planner_email(owner_email)
    users_collection = mongo.get_users_collection()

    resolved_ids: list[str] = []
    resolved_emails: list[str] = []
    invalid_user_ids: list[str] = []

    for user_id in user_ids:
        try:
            lookup_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
            user_doc = await users_collection.find_one(
                {"_id": lookup_id},
                {
                    "email": 1,
                    "role": 1,
                    "parent_planner_id": 1,
                    "is_active": 1,
                },
            )
        except Exception:
            user_doc = None

        if not user_doc or user_doc.get("is_active") is False:
            invalid_user_ids.append(user_id)
            continue

        resolved_user_id = normalize_planner_id(user_doc.get("_id"))
        resolved_user_email = normalize_planner_email(user_doc.get("email"))
        user_role = user_doc.get("role")
        belongs_to_owner_scope = False

        if (
            normalized_owner_id
            and resolved_user_id == normalized_owner_id
            or normalized_owner_email
            and resolved_user_email == normalized_owner_email
            or (
                user_role == "team_member"
                and normalized_owner_id
                and normalize_planner_id(user_doc.get("parent_planner_id"))
                == normalized_owner_id
            )
        ):
            belongs_to_owner_scope = True

        if not (belongs_to_owner_scope and resolved_user_id and resolved_user_email):
            invalid_user_ids.append(user_id)
            continue

        if resolved_user_id not in resolved_ids:
            resolved_ids.append(resolved_user_id)
            resolved_emails.append(resolved_user_email)

    if invalid_user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned staff must belong to the planner business owner scope.",
        )

    return resolved_ids, resolved_emails


def get_accessible_calendar_scope(user: ExtendedAuthUser) -> CalendarOwnerScope:
    """Return owner and wedding visibility scope for shared calendar queries."""
    owner_id, owner_email = get_owner_identity(user)
    return {
        "owner_id": owner_id,
        "owner_email": owner_email,
        "accessible_wedding_ids": get_accessible_wedding_ids(user),
        "is_owner": user.is_root_admin or user.is_wedding_planner,
        "is_team_member": user.is_team_member,
    }


def can_view_calendar_details(user: ExtendedAuthUser) -> bool:
    """Whether the current user may see full shared-calendar details by default."""
    if user.is_root_admin or user.is_wedding_planner:
        return True
    if user.is_team_member:
        return bool(
            user.team_permissions
            and user.team_permissions.get("view_calendar_details", False)
        )
    return False


def enforce_team_permission(user: ExtendedAuthUser, permission: str) -> None:
    """
    Inline permission check for team members.
    Planners and ROOT_ADMIN always pass. Team members need the specific permission.
    Raises HTTPException if denied.

    Usage in endpoint:
        enforce_team_permission(current_user, "manage_guests")
    """
    # Validate permission key to catch typos at development time
    from app.models.team_member import ALL_PERMISSION_KEYS

    if permission not in ALL_PERMISSION_KEYS:
        raise ValueError(
            f"Invalid permission key: '{permission}'. Valid keys: {ALL_PERMISSION_KEYS}"
        )

    if user.is_root_admin or user.is_wedding_planner:
        return
    if user.is_team_member:
        if user.team_permissions and user.team_permissions.get(permission, False):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have the '{permission.replace('_', ' ')}' permission.",
        )
    # Non-team, non-planner, non-admin — shouldn't reach here but deny anyway
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied",
    )


async def require_calendar_access(
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
) -> ExtendedAuthUser:
    """Allow access to shared calendar surfaces for planners and permitted team members."""
    if current_user.is_root_admin or current_user.is_wedding_planner:
        return current_user
    if current_user.is_team_member and current_user.team_permissions:
        if current_user.team_permissions.get("view_shared_calendar", False):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have the 'view shared calendar' permission.",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Calendar access denied",
    )


def require_calendar_permission(permission_name: str):
    """Dependency factory for calendar-specific permissions."""

    async def _check_permission(
        current_user: ExtendedAuthUser = Depends(require_calendar_access),
    ) -> ExtendedAuthUser:
        if current_user.is_root_admin or current_user.is_wedding_planner:
            return current_user
        if current_user.team_permissions and current_user.team_permissions.get(
            permission_name, False
        ):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have the '{permission_name.replace('_', ' ')}' permission.",
        )

    return _check_permission

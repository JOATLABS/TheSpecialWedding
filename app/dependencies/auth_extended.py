from typing import Optional, List
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.auth_utils import verify_token
import os
import logging
import time
import asyncio
from datetime import datetime, timezone
from app.core.database import mongo
from app.models.subscription import (
    PLANNER_BLOCKED_SUBSCRIPTION_STATUSES,
    normalize_subscription_status,
)
from app.models.team_member import resolve_team_permissions
from app.utils.planner_ownership import (
    normalize_planner_email,
    normalize_planner_id,
    normalize_wedding_query_id,
    wedding_belongs_to_owner,
)
from bson import ObjectId

logger = logging.getLogger(__name__)

# ── Team member data cache (bounded, thread-safe, with invalidation) ──
_TEAM_CACHE_TTL = 60  # seconds
_TEAM_CACHE_MAX_SIZE = 500
_team_cache: dict = {}
_team_cache_lock = asyncio.Lock()


async def _get_cached_team_data(user_id: str) -> Optional[dict]:
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


# Security scheme
security = HTTPBearer(auto_error=False)

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


class ExtendedAuthUser:
    """Extended auth user supporting multiple roles including team members"""

    def __init__(self, email: str, role: str, user_data: Optional[dict] = None):
        self.email = email
        self.role = role
        self.user_data = user_data or {}
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
        self.parent_planner_id: Optional[str] = (
            user_data.get("parent_planner_id") if user_data else None
        )
        self.team_member_id: Optional[str] = (
            user_data.get("team_member_id") if user_data else None
        )
        self.team_permissions: Optional[dict] = None
        self.team_wedding_access: Optional[str] = None  # "all" or "assigned"
        self.team_assigned_wedding_ids: List[str] = []
        self.team_owner_email: Optional[str] = None


async def get_current_user_extended(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    request: Request = None,
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

        # Check if this is the ROOT_ADMIN
        root_admin_email = os.getenv(
            "ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"
        )
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
                user_data["_subscription_block_reason"] = {
                    "pending": "Please complete your subscription checkout to access the platform.",
                    "pending_checkout": "Please complete your Stripe checkout to activate your subscription.",
                    "pending_payment": "Please complete your subscription payment to access the platform.",
                    "inactive": "Please choose a plan and complete checkout to access the platform.",
                    "cancelled": "Your subscription has been cancelled. Please resubscribe to continue.",
                    "past_due": "Your latest subscription payment failed. Please update your payment method to continue.",
                    "suspended": "Your subscription is suspended due to a payment issue. Please update your payment method.",
                    "expired": "Free trial has expired. Please upgrade your subscription to continue using the platform.",
                }.get(sub_status, "Subscription issue. Please contact support.")
            # Check trial expiration for wedding planners
            if (
                role == "wedding_planner"
                and user_data.get("subscription_status") == "trial"
            ):
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
                            ).replace(tzinfo=timezone.utc)
                    elif (
                        isinstance(trial_end_date, datetime)
                        and trial_end_date.tzinfo is None
                    ):
                        # Handle naive datetime objects from MongoDB
                        trial_end_date = trial_end_date.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > trial_end_date:
                        # Auto-expire the trial — update BOTH users and user_subscriptions
                        expire_time = datetime.now(timezone.utc)
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

                    # Update last_active_at with throttle (only if > 5 minutes old)
                    last_active = team_doc.get("last_active_at")
                    should_update = not last_active
                    if last_active:
                        if (
                            isinstance(last_active, datetime)
                            and last_active.tzinfo is None
                        ):
                            last_active = last_active.replace(tzinfo=timezone.utc)
                        should_update = (
                            datetime.now(timezone.utc) - last_active
                        ).total_seconds() > 300
                    if should_update:
                        try:
                            asyncio.create_task(
                                mongo.db["team_members"].update_one(
                                    {"_id": ObjectId(team_member_id)},
                                    {
                                        "$set": {
                                            "last_active_at": datetime.now(timezone.utc)
                                        }
                                    },
                                )
                            )
                        except Exception as e:
                            logger.debug(
                                f"Failed to update team member last_active_at: {e}"
                            )
                            pass  # Non-critical
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
                pass

        # ── Subscription gate ─────────────────────────────────────
        # Block expired/cancelled/suspended planners on feature endpoints.
        # Root admins are never tagged so they always pass through.
        # Whitelisted paths (profile, billing, stripe, public) are allowed
        # so expired planners can still log in and upgrade.
        if auth_user.user_data.get("_subscription_blocked") and request:
            path = request.url.path
            _SUB_WHITELIST = (
                "/admin/profile",
                "/admin/token",
                "/stripe/",
                "/api/stripe/",
                "/public/",
                "/users/",  # subscription management self-view
                "/subscription-plans",  # view available plans
            )
            if not any(
                path.startswith(p) or f"/{p.lstrip('/')}" in path
                for p in _SUB_WHITELIST
            ):
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=auth_user.user_data.get(
                        "_subscription_block_reason",
                        "Subscription issue. Please upgrade your plan.",
                    ),
                    headers={"WWW-Authenticate": "Bearer"},
                )

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


def get_accessible_wedding_ids(user: ExtendedAuthUser) -> Optional[List[str]]:
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


def get_owner_identity(user: ExtendedAuthUser) -> tuple[Optional[str], Optional[str]]:
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


def get_calendar_owner_identity(user: ExtendedAuthUser) -> dict[str, Optional[str]]:
    """Return owner identity payload for calendar-scoped routes."""
    owner_id, owner_email = get_owner_identity(user)
    return {
        "owner_id": owner_id,
        "owner_email": owner_email,
        "user_id": normalize_planner_id(user.user_data.get("_id")),
        "user_email": normalize_planner_email(user.email),
    }


def get_accessible_calendar_scope(user: ExtendedAuthUser) -> dict[str, Optional[object]]:
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

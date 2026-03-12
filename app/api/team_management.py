"""
Team Management API Router

Endpoints for managing planner team members: invite, accept, list,
update, deactivate, reactivate, remove, and permission queries.

Prefix: /admin/team (registered in main.py)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Optional, List
from bson import ObjectId
from bson.errors import InvalidId
import time
from collections import defaultdict

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    get_current_user_extended,
    require_wedding_planner,
)
from app.dependencies.feature_gates import require_team_management
from app.models.team_member import (
    InviteTeamMemberRequest,
    UpdateTeamMemberRequest,
    AcceptInviteRequest,
    TeamMemberResponse,
    TeamSeatsResponse,
    TeamPermissionsResponse,
    InviteInfoResponse,
)
from app.services.team_management_service import TeamManagementService
from app.utils.response import dict_response

router = APIRouter()
team_service = TeamManagementService()


# ─── H7: ObjectId Validation Helper ────────────────────────────────────────

def validate_object_id(id_str: str, field_name: str = "ID") -> str:
    """Validate that a string is a valid MongoDB ObjectId."""
    try:
        ObjectId(id_str)
        return id_str
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format: {id_str}")


# ─── H8: Simple In-Memory Rate Limiter ────────────────────────────────────

class SimpleRateLimiter:
    """In-memory rate limiter with automatic stale entry cleanup."""
    def __init__(self, max_requests: int = 10, window_seconds: int = 60, max_keys: int = 10000):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._requests: dict = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Full cleanup every 5 minutes

    def check(self, key: str) -> bool:
        """Check if a request is within the rate limit."""
        now = time.time()

        # Periodic full cleanup of stale keys
        if now - self._last_cleanup > self._cleanup_interval:
            self._full_cleanup(now)

        # Clean this key's old timestamps
        self._requests[key] = [t for t in self._requests[key] if now - t < self.window_seconds]

        if len(self._requests[key]) >= self.max_requests:
            return False
        self._requests[key].append(now)
        return True

    def _full_cleanup(self, now: float) -> None:
        """Remove all stale entries and enforce max_keys limit."""
        self._last_cleanup = now
        cutoff = now - self.window_seconds
        # Remove keys with no recent requests
        stale_keys = [k for k, timestamps in self._requests.items()
                      if not timestamps or timestamps[-1] < cutoff]
        for k in stale_keys:
            del self._requests[k]
        # If still over limit, remove oldest entries
        if len(self._requests) > self.max_keys:
            sorted_keys = sorted(
                self._requests.keys(),
                key=lambda k: self._requests[k][-1] if self._requests[k] else 0
            )
            for k in sorted_keys[:len(self._requests) - self.max_keys]:
                del self._requests[k]


_invite_limiter = SimpleRateLimiter(max_requests=10, window_seconds=60)
_accept_limiter = SimpleRateLimiter(max_requests=5, window_seconds=60)


# ─── Helper: resolve owner_id from the current user ──────────────────────

def _get_owner_id(user: ExtendedAuthUser) -> str:
    """Extract the planner's user _id as a string"""
    return user.user_data.get("_id", "")


# ─── Planner-Only Endpoints (require_wedding_planner) ────────────────────

@router.post("/team/invite", tags=["Team Management"])
async def invite_team_member(
    body: InviteTeamMemberRequest,
    current_user: ExtendedAuthUser = Depends(require_team_management),
):
    """
    Invite a new team member. Sends an invitation email with a setup link.
    Requires an available seat on the planner's plan.
    """
    owner_id = _get_owner_id(current_user)
    result = await team_service.invite_team_member(
        owner_id=owner_id,
        owner_email=current_user.email,
        email=body.email,
        role=body.role.value,
        custom_permissions=body.custom_permissions,
        wedding_access=body.wedding_access.value,
        assigned_wedding_ids=body.assigned_wedding_ids,
    )
    return result


@router.get("/team/members", tags=["Team Management"])
async def list_team_members(
    current_user: ExtendedAuthUser = Depends(require_team_management),
    skip: int = Query(0, ge=0, le=10000),
    limit: int = Query(50, ge=1, le=100),
):
    """List team members for the authenticated planner (paginated)"""
    owner_id = _get_owner_id(current_user)
    return await team_service.list_team_members(owner_id, skip=skip, limit=limit)


@router.get("/team/members/{team_member_id}", tags=["Team Management"])
async def get_team_member(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_management),
):
    """Get details of a single team member"""
    validate_object_id(team_member_id, "team_member_id")
    owner_id = _get_owner_id(current_user)
    return await team_service.get_team_member(owner_id, team_member_id)


@router.patch("/team/members/{team_member_id}", tags=["Team Management"])
async def update_team_member(
    team_member_id: str,
    body: UpdateTeamMemberRequest,
    current_user: ExtendedAuthUser = Depends(require_team_management),
):
    """Update a team member's role, permissions, or wedding access"""
    validate_object_id(team_member_id, "team_member_id")
    owner_id = _get_owner_id(current_user)
    updates = body.model_dump(exclude_none=True)
    # Convert enums to strings
    if "role" in updates:
        updates["role"] = updates["role"].value if hasattr(updates["role"], "value") else updates["role"]
    if "wedding_access" in updates:
        updates["wedding_access"] = (
            updates["wedding_access"].value
            if hasattr(updates["wedding_access"], "value")
            else updates["wedding_access"]
        )
    return await team_service.update_team_member(owner_id, current_user.email, team_member_id, updates)


@router.post("/team/members/{team_member_id}/resend-invite", tags=["Team Management"])
async def resend_invite(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_management),
):
    """Resend an invitation email (regenerates the token)"""
    validate_object_id(team_member_id, "team_member_id")
    owner_id = _get_owner_id(current_user)
    return await team_service.resend_invite(owner_id, team_member_id)


@router.post("/team/members/{team_member_id}/deactivate", tags=["Team Management"])
async def deactivate_team_member(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_management),
):
    """Deactivate a team member (soft-delete; blocks login)"""
    validate_object_id(team_member_id, "team_member_id")
    owner_id = _get_owner_id(current_user)
    return await team_service.deactivate_team_member(owner_id, team_member_id)


@router.post("/team/members/{team_member_id}/reactivate", tags=["Team Management"])
async def reactivate_team_member(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_management),
):
    """Reactivate a previously deactivated team member"""
    validate_object_id(team_member_id, "team_member_id")
    owner_id = _get_owner_id(current_user)
    return await team_service.reactivate_team_member(
        owner_id, current_user.email, team_member_id
    )


@router.delete("/team/members/{team_member_id}", tags=["Team Management"])
async def remove_team_member(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_management),
):
    """Permanently remove a team member (frees up a seat)"""
    validate_object_id(team_member_id, "team_member_id")
    owner_id = _get_owner_id(current_user)
    return await team_service.remove_team_member(owner_id, team_member_id)


@router.get("/team/seats", tags=["Team Management"])
async def get_seat_usage(
    current_user: ExtendedAuthUser = Depends(require_team_management),
):
    """Get current seat usage vs. plan limit"""
    owner_id = _get_owner_id(current_user)
    return await team_service.get_seats_info(owner_id, current_user.email)


# ─── Public Endpoints (no auth) ──────────────────────────────────────────

@router.get("/team/invite-info/{token}", tags=["Team Management"])
async def get_invite_info(token: str, request: Request):
    """
    Public: get invite details for the accept page.
    Shows company name, role, and permissions without requiring login.
    """
    client_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
    if not _invite_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    return await team_service.get_invite_info(token)


@router.post("/team/accept-invite", tags=["Team Management"])
async def accept_invite(body: AcceptInviteRequest, request: Request):
    """
    Public: accept an invitation — creates a user account and activates the member.
    """
    client_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
    if not _accept_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    return await team_service.accept_invite(
        token=body.token,
        first_name=body.first_name,
        last_name=body.last_name,
        password=body.password,
    )


# ─── Team Member Self-Service ────────────────────────────────────────────

@router.get("/team/permissions", tags=["Team Management"])
async def get_my_permissions(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
):
    """
    Get the current user's effective permissions.
    Works for both planner-owners (returns full access) and team members.
    """
    if current_user.is_root_admin or current_user.is_wedding_planner:
        return dict_response(
            data={
                "is_team_member": False,
                "is_owner": True,
                "role": current_user.role,
                "permissions": {k: True for k in [
                    "manage_guests", "manage_budget", "manage_gallery",
                    "manage_seating", "manage_vendors", "send_rsvp",
                    "send_reminders", "manage_forms", "view_analytics",
                    "manage_wedding_settings", "manage_contracts", "manage_packages",
                ]},
                "wedding_access": "all",
                "assigned_wedding_ids": [],
            }
        )

    # Team member — load from team_members collection
    user_id = current_user.user_data.get("_id", "")
    member_data = await team_service.get_member_permissions(user_id)

    if not member_data:
        raise HTTPException(status_code=403, detail="No team membership found")

    return dict_response(
        data={
            "is_team_member": True,
            "is_owner": False,
            "role": member_data["role"],
            "permissions": member_data["permissions"],
            "wedding_access": member_data["wedding_access"],
            "assigned_wedding_ids": member_data["assigned_wedding_ids"],
        }
    )

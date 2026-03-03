"""
Team Management API Router

Endpoints for managing planner team members: invite, accept, list,
update, deactivate, reactivate, remove, and permission queries.

Prefix: /admin/team (registered in main.py)
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from bson import ObjectId

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    get_current_user_extended,
    require_wedding_planner,
)
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

router = APIRouter()
team_service = TeamManagementService()


# ─── Helper: resolve owner_id from the current user ──────────────────────

def _get_owner_id(user: ExtendedAuthUser) -> str:
    """Extract the planner's user _id as a string"""
    return user.user_data.get("_id", "")


# ─── Planner-Only Endpoints (require_wedding_planner) ────────────────────

@router.post("/team/invite", tags=["Team Management"])
async def invite_team_member(
    body: InviteTeamMemberRequest,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
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
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
):
    """List all team members for the authenticated planner"""
    owner_id = _get_owner_id(current_user)
    return await team_service.list_team_members(owner_id)


@router.get("/team/members/{team_member_id}", tags=["Team Management"])
async def get_team_member(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
):
    """Get details of a single team member"""
    owner_id = _get_owner_id(current_user)
    return await team_service.get_team_member(owner_id, team_member_id)


@router.patch("/team/members/{team_member_id}", tags=["Team Management"])
async def update_team_member(
    team_member_id: str,
    body: UpdateTeamMemberRequest,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
):
    """Update a team member's role, permissions, or wedding access"""
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
    return await team_service.update_team_member(owner_id, team_member_id, updates)


@router.post("/team/members/{team_member_id}/resend-invite", tags=["Team Management"])
async def resend_invite(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
):
    """Resend an invitation email (regenerates the token)"""
    owner_id = _get_owner_id(current_user)
    return await team_service.resend_invite(owner_id, team_member_id)


@router.post("/team/members/{team_member_id}/deactivate", tags=["Team Management"])
async def deactivate_team_member(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
):
    """Deactivate a team member (soft-delete; blocks login)"""
    owner_id = _get_owner_id(current_user)
    return await team_service.deactivate_team_member(owner_id, team_member_id)


@router.post("/team/members/{team_member_id}/reactivate", tags=["Team Management"])
async def reactivate_team_member(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
):
    """Reactivate a previously deactivated team member"""
    owner_id = _get_owner_id(current_user)
    return await team_service.reactivate_team_member(
        owner_id, current_user.email, team_member_id
    )


@router.delete("/team/members/{team_member_id}", tags=["Team Management"])
async def remove_team_member(
    team_member_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
):
    """Permanently remove a team member (frees up a seat)"""
    owner_id = _get_owner_id(current_user)
    return await team_service.remove_team_member(owner_id, team_member_id)


@router.get("/team/seats", tags=["Team Management"])
async def get_seat_usage(
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
):
    """Get current seat usage vs. plan limit"""
    owner_id = _get_owner_id(current_user)
    return await team_service.get_seats_info(owner_id, current_user.email)


# ─── Public Endpoints (no auth) ──────────────────────────────────────────

@router.get("/team/invite-info/{token}", tags=["Team Management"])
async def get_invite_info(token: str):
    """
    Public: get invite details for the accept page.
    Shows company name, role, and permissions without requiring login.
    """
    return await team_service.get_invite_info(token)


@router.post("/team/accept-invite", tags=["Team Management"])
async def accept_invite(body: AcceptInviteRequest):
    """
    Public: accept an invitation — creates a user account and activates the member.
    """
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
        return {
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

    # Team member — load from team_members collection
    user_id = current_user.user_data.get("_id", "")
    member_data = await team_service.get_member_permissions(user_id)

    if not member_data:
        raise HTTPException(status_code=403, detail="No team membership found")

    return {
        "is_team_member": True,
        "is_owner": False,
        "role": member_data["role"],
        "permissions": member_data["permissions"],
        "wedding_access": member_data["wedding_access"],
        "assigned_wedding_ids": member_data["assigned_wedding_ids"],
    }

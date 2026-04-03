"""
Team Member Models

Pydantic models for the team management feature.
Supports planner → team member relationships with role-based permissions
and wedding-scoped access control.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from enum import Enum


class TeamMemberRole(str, Enum):
    """Team member role presets"""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class TeamMemberStatus(str, Enum):
    """Team member lifecycle status"""
    PENDING = "pending"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class WeddingAccessType(str, Enum):
    """Wedding access scope"""
    ALL = "all"
    ASSIGNED = "assigned"


# ─── Role Preset Definitions ──────────────────────────────────────────────────
# Defined in code, not in DB. Used as defaults when a role is selected;
# planners can override individual permissions via custom_permissions.

ROLE_PRESETS: Dict[str, Dict[str, bool]] = {
    "admin": {
        "manage_guests": True,
        "manage_budget": True,
        "manage_gallery": True,
        "manage_seating": True,
        "manage_vendors": True,
        "send_rsvp": True,
        "send_reminders": True,
        "manage_forms": True,
        "view_analytics": True,
        "manage_wedding_settings": True,
        "manage_contracts": True,
        "manage_packages": True,
    },
    "editor": {
        "manage_guests": True,
        "manage_budget": True,
        "manage_gallery": True,
        "manage_seating": True,
        "manage_vendors": False,
        "send_rsvp": False,
        "send_reminders": False,
        "manage_forms": True,
        "view_analytics": True,
        "manage_wedding_settings": False,
        "manage_contracts": False,
        "manage_packages": False,
    },
    "viewer": {
        "manage_guests": False,
        "manage_budget": False,
        "manage_gallery": False,
        "manage_seating": False,
        "manage_vendors": False,
        "send_rsvp": False,
        "send_reminders": False,
        "manage_forms": False,
        "view_analytics": True,
        "manage_wedding_settings": False,
        "manage_contracts": False,
        "manage_packages": False,
    },
}

# All valid permission keys (used for validation)
ALL_PERMISSION_KEYS = list(ROLE_PRESETS["admin"].keys())


class TeamPermissions(BaseModel):
    """Granular permission toggles for team members"""
    manage_guests: bool = False
    manage_budget: bool = False
    manage_gallery: bool = False
    manage_seating: bool = False
    manage_vendors: bool = False
    send_rsvp: bool = False
    send_reminders: bool = False
    manage_forms: bool = False
    view_analytics: bool = False
    manage_wedding_settings: bool = False
    manage_contracts: bool = False
    manage_packages: bool = False

    def to_dict(self) -> Dict[str, bool]:
        """Convert to plain dict for MongoDB storage"""
        return self.model_dump()

    @classmethod
    def from_role(cls, role: str) -> "TeamPermissions":
        """Create permissions from a role preset"""
        preset = ROLE_PRESETS.get(role, ROLE_PRESETS["viewer"])
        return cls(**preset)

    def has_permission(self, permission_name: str) -> bool:
        """Check if a specific permission is enabled"""
        return getattr(self, permission_name, False)

    def has_any_permission(self) -> bool:
        """Check if the member has at least one permission"""
        return any(self.model_dump().values())


# ─── Request Models ───────────────────────────────────────────────────────────

class InviteTeamMemberRequest(BaseModel):
    """Request body for inviting a new team member"""
    email: str = Field(
        ...,
        min_length=5,
        max_length=254,
        description="Email address of the team member to invite"
    )
    role: TeamMemberRole = Field(
        TeamMemberRole.VIEWER,
        description="Role preset (admin, editor, viewer)"
    )
    custom_permissions: Optional[Dict[str, bool]] = Field(
        None,
        description="Override individual permissions from the role preset"
    )
    wedding_access: WeddingAccessType = Field(
        WeddingAccessType.ALL,
        description="Wedding access scope: 'all' or 'assigned'"
    )
    assigned_wedding_ids: Optional[List[str]] = Field(
        None,
        description="Wedding IDs to grant access to (only when wedding_access='assigned')"
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v

    @field_validator("custom_permissions")
    @classmethod
    def validate_permission_keys(cls, v):
        if v is not None:
            invalid = set(v.keys()) - set(ALL_PERMISSION_KEYS)
            if invalid:
                raise ValueError(f"Invalid permission keys: {invalid}")
        return v

    @model_validator(mode="after")
    def validate_wedding_access(self):
        if self.wedding_access == WeddingAccessType.ASSIGNED:
            if not self.assigned_wedding_ids or len(self.assigned_wedding_ids) == 0:
                raise ValueError(
                    "assigned_wedding_ids is required when wedding_access is 'assigned'"
                )
        return self


class UpdateTeamMemberRequest(BaseModel):
    """Request body for updating an existing team member"""
    role: Optional[TeamMemberRole] = Field(
        None,
        description="New role preset (resets permissions to preset defaults)"
    )
    custom_permissions: Optional[Dict[str, bool]] = Field(
        None,
        description="Override individual permissions"
    )
    wedding_access: Optional[WeddingAccessType] = Field(
        None,
        description="Wedding access scope"
    )
    assigned_wedding_ids: Optional[List[str]] = Field(
        None,
        description="Wedding IDs to grant access to"
    )

    @field_validator("custom_permissions")
    @classmethod
    def validate_permission_keys(cls, v):
        if v is not None:
            invalid = set(v.keys()) - set(ALL_PERMISSION_KEYS)
            if invalid:
                raise ValueError(f"Invalid permission keys: {invalid}")
        return v

    @model_validator(mode="after")
    def validate_wedding_access(self):
        if self.wedding_access == WeddingAccessType.ASSIGNED:
            if not self.assigned_wedding_ids or len(self.assigned_wedding_ids) == 0:
                raise ValueError(
                    "assigned_wedding_ids is required when wedding_access is 'assigned'"
                )
        return self


class AcceptInviteRequest(BaseModel):
    """Request body for accepting a team invitation"""
    token: str = Field(..., min_length=1, description="Invitation token from email")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    password: str = Field(..., min_length=8, max_length=128, description="Account password")

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, v: str) -> str:
        return v.strip()


# ─── Response Models ──────────────────────────────────────────────────────────

class TeamMemberResponse(BaseModel):
    """Response model for a team member"""
    id: str = Field(..., description="Team member document ID")
    owner_id: str = Field(..., description="Planner (account owner) user ID")
    email: str = Field(..., description="Team member email")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: TeamMemberStatus = Field(..., description="pending, active, or deactivated")
    role: TeamMemberRole = Field(..., description="admin, editor, or viewer")
    permissions: Dict[str, bool] = Field(default_factory=dict)
    wedding_access: WeddingAccessType = Field(..., description="all or assigned")
    assigned_wedding_ids: List[str] = Field(default_factory=list)
    invited_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user_id: Optional[str] = Field(None, description="Linked user account ID")
    owner_email: str = Field(..., description="Planner's email address")
    invite_token_expires_at: Optional[datetime] = Field(None, description="When the invite token expires")

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )


class TeamSeatsResponse(BaseModel):
    """Response model for seat usage"""
    total_seats: int = Field(..., description="Total seats in the plan")
    used_seats: int = Field(..., description="Currently used seats")
    available_seats: int = Field(..., description="Remaining available seats")
    members_by_status: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of members by status"
    )


class TeamPermissionsResponse(BaseModel):
    """Response model for current user's effective permissions"""
    is_team_member: bool = False
    is_owner: bool = False
    role: Optional[str] = None
    permissions: Dict[str, bool] = Field(default_factory=dict)
    wedding_access: Optional[str] = None
    assigned_wedding_ids: List[str] = Field(default_factory=list)


class InviteInfoResponse(BaseModel):
    """Response model for public invite info (shown on accept page)"""
    email: str
    role: str
    permissions: Dict[str, bool] = Field(default_factory=dict)
    company_name: Optional[str] = None
    planner_name: Optional[str] = None
    is_expired: bool = False

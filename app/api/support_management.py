from fastapi import APIRouter, HTTPException, Depends, Query, File, UploadFile
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner, ExtendedAuthUser
from app.services.support_service import SupportService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
support_service = SupportService()

class TicketCreateModel(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200, description="Ticket subject")
    description: str = Field(..., min_length=1, max_length=2000, description="Ticket description")
    priority: str = Field(default="medium", description="Ticket priority")
    category: str = Field(default="general", description="Ticket category")
    wedding_id: Optional[str] = Field(None, description="Related wedding ID")
    attachments: List[str] = Field(default_factory=list, description="Attachment file URLs")

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high', 'urgent']:
            raise ValueError('Priority must be one of: low, medium, high, urgent')
        return v

    @validator('category')
    def validate_category(cls, v):
        if v not in ['technical', 'billing', 'feature_request', 'bug_report', 'general']:
            raise ValueError('Category must be one of: technical, billing, feature_request, bug_report, general')
        return v

class TicketUpdateModel(BaseModel):
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    priority: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None

    @validator('priority')
    def validate_priority(cls, v):
        if v is not None and v not in ['low', 'medium', 'high', 'urgent']:
            raise ValueError('Priority must be one of: low, medium, high, urgent')
        return v

    @validator('category')
    def validate_category(cls, v):
        if v is not None and v not in ['technical', 'billing', 'feature_request', 'bug_report', 'general']:
            raise ValueError('Category must be one of: technical, billing, feature_request, bug_report, general')
        return v

    @validator('status')
    def validate_status(cls, v):
        if v is not None and v not in ['open', 'in_progress', 'resolved', 'closed']:
            raise ValueError('Status must be one of: open, in_progress, resolved, closed')
        return v

class CommentCreateModel(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="Comment message")
    is_internal: bool = Field(default=False, description="Whether this is an internal admin comment")

# ==================== ADMIN SUPPORT MANAGEMENT ====================

@router.post("/tickets", tags=["Support"])
async def create_ticket(ticket_data: TicketCreateModel, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Create a new support ticket - Authenticated users only"""
    return await support_service.create_ticket(
        ticket_data.dict(),
        created_by=current_user.email
    )

@router.get("/tickets", tags=["Support"])
async def get_tickets(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned admin"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get support tickets with filtering - Authenticated users can see their own tickets, ROOT_ADMIN sees all"""
    filters = {}
    if status:
        filters['status'] = status
    if priority:
        filters['priority'] = priority
    if category:
        filters['category'] = category
    if assigned_to:
        filters['assigned_to'] = assigned_to
    if created_by:
        filters['created_by'] = created_by
    if wedding_id:
        filters['wedding_id'] = wedding_id

    # Non-admin users can only see their own tickets
    if current_user.role != "ROOT_ADMIN":
        filters['created_by'] = current_user.email

    return await support_service.get_tickets(
        page=page,
        limit=limit,
        filters=filters
    )

@router.get("/tickets/{ticket_id}", tags=["Support"])
async def get_ticket(ticket_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get specific ticket details with comments"""
    return await support_service.get_ticket(ticket_id, current_user)

@router.put("/tickets/{ticket_id}", tags=["Support"])
async def update_ticket(
    ticket_id: str,
    ticket_data: TicketUpdateModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Update ticket - Users can update their own tickets, ROOT_ADMIN can update any"""
    return await support_service.update_ticket(
        ticket_id,
        ticket_data.dict(exclude_unset=True),
        current_user
    )

@router.post("/tickets/{ticket_id}/comments", tags=["Support"])
async def add_comment(
    ticket_id: str,
    comment_data: CommentCreateModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Add comment to ticket"""
    return await support_service.add_comment(
        ticket_id,
        comment_data.dict(),
        current_user
    )

@router.get("/tickets/{ticket_id}/comments", tags=["Support"])
async def get_comments(
    ticket_id: str,
    include_internal: bool = Query(False, description="Include internal comments"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get ticket comments"""
    return await support_service.get_comments(
        ticket_id,
        current_user,
        include_internal=include_internal
    )

# ==================== ADMIN-ONLY ENDPOINTS ====================

@router.get("/analytics", tags=["Support Admin"])
async def get_support_analytics(
    period: str = Query("30d", description="Time period: 7d, 30d, 90d, 1y"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Get support analytics and metrics - ROOT_ADMIN only"""
    return await support_service.get_analytics(period)

@router.get("/agents", tags=["Support Admin"])
async def get_support_agents(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get list of support agents - ROOT_ADMIN only"""
    return await support_service.get_support_agents()

@router.put("/tickets/{ticket_id}/assign", tags=["Support Admin"])
async def assign_ticket(
    ticket_id: str,
    agent_email: str = Query(..., description="Email of agent to assign"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Assign ticket to support agent - ROOT_ADMIN only"""
    return await support_service.assign_ticket(ticket_id, agent_email, current_user.email)

@router.put("/tickets/{ticket_id}/priority", tags=["Support Admin"])
async def update_ticket_priority(
    ticket_id: str,
    priority: str = Query(..., description="New priority level"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Update ticket priority - ROOT_ADMIN only"""
    if priority not in ['low', 'medium', 'high', 'urgent']:
        raise HTTPException(status_code=400, detail="Invalid priority level")

    return await support_service.update_ticket(
        ticket_id,
        {"priority": priority},
        current_user
    )

@router.get("/metrics/dashboard", tags=["Support Admin"])
async def get_support_dashboard(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get support dashboard metrics - ROOT_ADMIN only"""
    return await support_service.get_dashboard_metrics()

# ==================== FILE UPLOAD ====================

@router.post("/tickets/{ticket_id}/attachments", tags=["Support"])
async def upload_attachment(
    ticket_id: str,
    file: UploadFile = File(...),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Upload attachment to ticket"""
    return await support_service.upload_attachment(ticket_id, file, current_user)

# ==================== USER ENDPOINTS ====================

@router.get("/my-tickets", tags=["User Support"])
async def get_my_tickets(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get current user's tickets"""
    filters = {"created_by": current_user.email}
    if status:
        filters['status'] = status

    return await support_service.get_tickets(
        page=page,
        limit=limit,
        filters=filters
    )

@router.get("/categories", tags=["Support"])
async def get_ticket_categories(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get available ticket categories"""
    return {
        "categories": [
            {"value": "technical", "label": "Technical Issue", "description": "Technical problems with the platform"},
            {"value": "billing", "label": "Billing", "description": "Payment and subscription issues"},
            {"value": "feature_request", "label": "Feature Request", "description": "Request for new features"},
            {"value": "bug_report", "label": "Bug Report", "description": "Report software bugs"},
            {"value": "general", "label": "General", "description": "General inquiries and support"}
        ],
        "priorities": [
            {"value": "low", "label": "Low", "description": "Minor issues, no urgency"},
            {"value": "medium", "label": "Medium", "description": "Standard issues"},
            {"value": "high", "label": "High", "description": "Important issues affecting operations"},
            {"value": "urgent", "label": "Urgent", "description": "Critical issues requiring immediate attention"}
        ]
    }
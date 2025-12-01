from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner, ExtendedAuthUser
from app.services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
notification_service = NotificationService()

class NotificationCreateModel(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Notification title")
    message: str = Field(..., min_length=1, max_length=1000, description="Notification message")
    type: str = Field(default="info", description="Notification type")
    target_audience: str = Field(default="all", description="Target audience")
    wedding_id: Optional[str] = Field(None, description="Wedding ID for targeted notifications")
    user_id: Optional[str] = Field(None, description="User ID for targeted notifications")
    expiry_date: Optional[datetime] = Field(None, description="Notification expiry date")
    is_dismissible: bool = Field(default=True, description="Whether notification can be dismissed")
    priority: str = Field(default="medium", description="Notification priority")

    @validator('type')
    def validate_type(cls, v):
        if v not in ['info', 'warning', 'error', 'success']:
            raise ValueError('Type must be one of: info, warning, error, success')
        return v

    @validator('target_audience')
    def validate_target_audience(cls, v):
        if v not in ['all', 'wedding_planners', 'vendors']:
            raise ValueError('Target audience must be one of: all, wedding_planners, vendors')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high', 'urgent']:
            raise ValueError('Priority must be one of: low, medium, high, urgent')
        return v

class NotificationUpdateModel(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    message: Optional[str] = Field(None, min_length=1, max_length=1000)
    type: Optional[str] = None
    target_audience: Optional[str] = None
    expiry_date: Optional[datetime] = None
    is_dismissible: Optional[bool] = None
    priority: Optional[str] = None

    @validator('type')
    def validate_type(cls, v):
        if v is not None and v not in ['info', 'warning', 'error', 'success']:
            raise ValueError('Type must be one of: info, warning, error, success')
        return v

    @validator('target_audience')
    def validate_target_audience(cls, v):
        if v is not None and v not in ['all', 'wedding_planners', 'vendors']:
            raise ValueError('Target audience must be one of: all, wedding_planners, vendors')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v is not None and v not in ['low', 'medium', 'high', 'urgent']:
            raise ValueError('Priority must be one of: low, medium, high, urgent')
        return v

# ==================== ADMIN NOTIFICATION MANAGEMENT ====================

@router.post("/notifications", tags=["Notifications"])
async def create_notification(notification_data: NotificationCreateModel, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Create a new notification - ROOT_ADMIN only"""
    return await notification_service.create_notification(
        notification_data.dict(),
        created_by=current_user.email
    )

@router.get("/notifications", tags=["Notifications"])
async def get_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    type: Optional[str] = Query(None, description="Filter by notification type"),
    target_audience: Optional[str] = Query(None, description="Filter by target audience"),
    status: Optional[str] = Query(None, description="Filter by status"),
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Get notifications with filtering and pagination - ROOT_ADMIN only"""
    filters = {}
    if type:
        filters['type'] = type
    if target_audience:
        filters['target_audience'] = target_audience
    if status:
        filters['status'] = status
    if wedding_id:
        filters['wedding_id'] = wedding_id

    return await notification_service.get_notifications(
        page=page,
        limit=limit,
        filters=filters
    )

@router.get("/notifications/{notification_id}", tags=["Notifications"])
async def get_notification(notification_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get specific notification details - ROOT_ADMIN only"""
    return await notification_service.get_notification(notification_id)

@router.put("/notifications/{notification_id}", tags=["Notifications"])
async def update_notification(
    notification_id: str,
    notification_data: NotificationUpdateModel,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Update a notification - ROOT_ADMIN only"""
    return await notification_service.update_notification(
        notification_id,
        notification_data.dict(exclude_unset=True),
        updated_by=current_user.email
    )

@router.delete("/notifications/{notification_id}", tags=["Notifications"])
async def delete_notification(notification_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Delete a notification - ROOT_ADMIN only"""
    return await notification_service.delete_notification(notification_id)

@router.post("/notifications/{notification_id}/send", tags=["Notifications"])
async def send_notification(notification_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Send notification to target audience - ROOT_ADMIN only"""
    return await notification_service.send_notification(notification_id)

# ==================== USER NOTIFICATION ACCESS ====================

@router.get("/user/notifications", tags=["User Notifications"])
async def get_user_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get notifications for the current authenticated user"""
    return await notification_service.get_user_notifications(
        user_email=current_user.email,
        user_role=current_user.role,
        page=page,
        limit=limit,
        unread_only=unread_only
    )

@router.put("/user/notifications/{notification_id}/read", tags=["User Notifications"])
async def mark_notification_read(notification_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Mark notification as read by current user"""
    return await notification_service.mark_notification_read(
        notification_id,
        user_id=current_user.email
    )

@router.put("/user/notifications/{notification_id}/dismiss", tags=["User Notifications"])
async def dismiss_notification(notification_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Dismiss a notification for current user"""
    return await notification_service.dismiss_notification(
        notification_id,
        user_id=current_user.email
    )

@router.get("/user/notifications/count", tags=["User Notifications"])
async def get_notification_count(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get notification count for current user"""
    return await notification_service.get_user_notification_count(
        user_email=current_user.email,
        user_role=current_user.role
    )

# ==================== NOTIFICATION TEMPLATES ====================

class NotificationTemplateModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Template name")
    subject: str = Field(..., min_length=1, max_length=200, description="Email subject / SMS preview")
    content: str = Field(..., min_length=1, description="Template content (supports variables like {guest_name})")
    type: str = Field(..., description="Template type: email or sms")
    category: str = Field(default="general", description="Template category")
    variables: List[str] = Field(default_factory=list, description="List of available variables")
    is_active: bool = Field(default=True, description="Whether template is active")

    @validator('type')
    def validate_type(cls, v):
        if v not in ['email', 'sms']:
            raise ValueError('Type must be either email or sms')
        return v

class NotificationTemplateUpdateModel(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    category: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None

@router.post("/notification-templates", tags=["Notification Templates"])
async def create_notification_template(
    template_data: NotificationTemplateModel,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Create a new notification template - ROOT_ADMIN only"""
    return await notification_service.create_template(
        template_data.dict(),
        created_by=current_user.email
    )

@router.get("/notification-templates", tags=["Notification Templates"])
async def get_notification_templates(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    type: Optional[str] = Query(None, description="Filter by template type (email/sms)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Get notification templates with filtering and pagination - ROOT_ADMIN only"""
    filters = {}
    if type:
        filters['type'] = type
    if category:
        filters['category'] = category

    return await notification_service.get_templates(
        page=page,
        limit=limit,
        filters=filters
    )

@router.get("/notification-templates/{template_id}", tags=["Notification Templates"])
async def get_notification_template(
    template_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Get specific notification template - ROOT_ADMIN only"""
    return await notification_service.get_template(template_id)

@router.put("/notification-templates/{template_id}", tags=["Notification Templates"])
async def update_notification_template(
    template_id: str,
    template_data: NotificationTemplateUpdateModel,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Update a notification template - ROOT_ADMIN only"""
    return await notification_service.update_template(
        template_id,
        template_data.dict(exclude_unset=True),
        updated_by=current_user.email
    )

@router.delete("/notification-templates/{template_id}", tags=["Notification Templates"])
async def delete_notification_template(
    template_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Delete a notification template - ROOT_ADMIN only"""
    return await notification_service.delete_template(template_id)
from fastapi import APIRouter, HTTPException, Depends, Query, File, UploadFile
from pydantic import BaseModel, Field, validator
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner, ExtendedAuthUser
from app.services.support_service import SupportService
from app.utils.serializers import serialize_mongo_doc
from app.utils.query_validation import (
    validated_page,
    validated_limit,
    validated_string_filter,
    validated_status_filter
)
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
    logger.info(f"Creating support ticket for user: {current_user.email}, subject: {ticket_data.subject}")
    result = await support_service.create_ticket(
        ticket_data.dict(),
        created_by=current_user.email
    )
    logger.info(f"Support ticket created successfully: {result.get('ticket_number', 'unknown')}")
    return result


@router.get("/tickets", tags=["Support"])
async def get_tickets(
    page: int = Query(1, ge=1, le=10000, description="Page number"),
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
    # Validate filter parameters
    status = validated_status_filter(status, ['open', 'in_progress', 'resolved', 'closed'])
    priority = validated_status_filter(priority, ['low', 'medium', 'high', 'urgent'])
    category = validated_status_filter(category, ['technical', 'billing', 'feature_request', 'bug_report', 'general'])
    assigned_to = validated_string_filter(assigned_to, max_length=100)
    created_by = validated_string_filter(created_by, max_length=100)
    wedding_id = validated_string_filter(wedding_id, max_length=100)

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

# ==================== SMS SUPPORT TICKETS (NEW) ====================


class SMSResponseModel(BaseModel):
    message: str = Field(..., min_length=1, max_length=1600, description="SMS response message (max 1600 chars)")
    mark_resolved: bool = Field(default=True, description="Mark ticket as resolved after sending")


@router.get("/sms-tickets", tags=["SMS Support"])
async def get_sms_tickets(
    status: Optional[str] = Query(None, description="Filter by status: new, in_progress, resolved"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get SMS support tickets
    - Wedding planners see only tickets for their assigned weddings
    - ROOT_ADMIN sees all tickets
    """
    from app.core.database import mongo

    # Build query
    query = {"source": "sms"}

    if status:
        query["status"] = status

    # Filter by assigned planner (multi-tenant security)
    if not current_user.is_root_admin:
        query["assigned_to"] = current_user.email

    # Pagination
    skip = (page - 1) * limit

    cursor = (
        mongo.db["support_tickets"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    tickets = await cursor.to_list(length=limit)

    # Convert ObjectId to string
    for ticket in tickets:
        ticket["_id"] = str(ticket["_id"])
        if "guest_id" in ticket and ticket["guest_id"]:
            ticket["guest_id"] = str(ticket["guest_id"])
        if "wedding_id" in ticket and ticket["wedding_id"]:
            ticket["wedding_id"] = str(ticket["wedding_id"])

    total = await mongo.db["support_tickets"].count_documents(query)

    return serialize_mongo_doc({
        "tickets": tickets,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
        "limit": limit
    })


@router.get("/sms-tickets/{ticket_id}", tags=["SMS Support"])
async def get_sms_ticket(
    ticket_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get specific SMS ticket with full details and response history"""
    from app.core.database import mongo
    from bson import ObjectId
    try:
        obj_id = ObjectId(ticket_id)
    except Exception as e:
        logger.error(f"Invalid ObjectId provided for ticket: {ticket_id}, error: {e}")
        raise HTTPException(status_code=400, detail="Invalid ticket ID format")

    # Multi-tenant security: combine access check into query for non-root-admin users
    if current_user.is_root_admin:
        query = {"_id": obj_id}
    else:
        query = {"_id": obj_id, "assigned_to": current_user.email}

    ticket = await mongo.db["support_tickets"].find_one(query)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Convert ObjectId to string
    ticket["_id"] = str(ticket["_id"])
    if "guest_id" in ticket and ticket["guest_id"]:
        ticket["guest_id"] = str(ticket["guest_id"])
    if "wedding_id" in ticket and ticket["wedding_id"]:
        ticket["wedding_id"] = str(ticket["wedding_id"])

    return serialize_mongo_doc({"ticket": ticket})


@router.post("/sms-tickets/{ticket_id}/respond", tags=["SMS Support"])
async def respond_to_sms_ticket(
    ticket_id: str,
    response_data: SMSResponseModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Send SMS response to guest
    - Sends SMS via configured provider (Twilio/Telnyx)
    - Logs response in ticket history
    - Updates ticket status
    - Calculates response time metrics
    """
    from app.core.database import mongo
    from bson import ObjectId
    from app.services.sms_service import SMSService
    # Get ticket
    try:
        obj_id = ObjectId(ticket_id)
    except Exception as e:
        logger.error(f"Invalid ObjectId provided for ticket: {ticket_id}, error: {e}")
        raise HTTPException(status_code=400, detail="Invalid ticket ID format")

    # Multi-tenant security: combine access check into query for non-root-admin users
    if current_user.is_root_admin:
        query = {"_id": obj_id}
    else:
        query = {"_id": obj_id, "assigned_to": current_user.email}

    ticket = await mongo.db["support_tickets"].find_one(query)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Validate ticket has phone number
    if not ticket.get("phone"):
        raise HTTPException(status_code=400, detail="Ticket has no phone number")

    # Send SMS
    sms_service = SMSService()
    result = sms_service.send_sms(ticket["phone"], response_data.message)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send SMS: {result.get('error', 'Unknown error')}"
        )

    # Calculate response time
    now = datetime.now(timezone.utc)
    response_time_minutes = None
    if ticket.get("created_at"):
        delta = now - ticket["created_at"]
        response_time_minutes = int(delta.total_seconds() / 60)

    # Build update
    update: Dict[str, Any] = {
        "$push": {
            "responses": {
                "message": response_data.message,
                "sent_by": current_user.email,
                "sent_by_name": current_user.user_data.get("company_name") or current_user.email,
                "sent_at": now,
                "sms_provider": result.get("provider"),
                "message_id": result.get("message_id")
            }
        },
        "$set": {
            "updated_at": now,
            "is_read": True
        }
    }

    # Set first response time if this is the first response
    if not ticket.get("first_response_at"):
        update["$set"]["first_response_at"] = now
        if response_time_minutes:
            update["$set"]["first_response_time_minutes"] = response_time_minutes

    # Mark as resolved if requested
    if response_data.mark_resolved:
        update["$set"]["status"] = "resolved"
        update["$set"]["resolved_at"] = now
        if response_time_minutes:
            update["$set"]["resolution_time_minutes"] = response_time_minutes

    # Update ticket
    await mongo.db["support_tickets"].update_one(
        {"_id": ObjectId(ticket_id)},
        update
    )

    logger.info(f"SMS response sent for ticket {ticket_id} by {current_user.email}")

    return {
        "success": True,
        "message": "SMS response sent successfully",
        "sms_result": result,
        "ticket_status": "resolved" if response_data.mark_resolved else ticket.get("status"),
        "response_time_minutes": response_time_minutes
    }


@router.put("/sms-tickets/{ticket_id}/status", tags=["SMS Support"])
async def update_sms_ticket_status(
    ticket_id: str,
    status: str = Query(..., description="New status: new, in_progress, resolved, closed"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Update SMS ticket status without sending a response"""
    from app.core.database import mongo
    from bson import ObjectId
    from datetime import datetime, timezone

    if status not in ["new", "in_progress", "resolved", "closed"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Get ticket
    try:
        obj_id = ObjectId(ticket_id)
    except Exception as e:
        logger.error(f"Invalid ObjectId provided for ticket: {ticket_id}, error: {e}")
        raise HTTPException(status_code=400, detail="Invalid ticket ID format")

    # Multi-tenant security: combine access check into query for non-root-admin users
    if current_user.is_root_admin:
        query = {"_id": obj_id}
    else:
        query = {"_id": obj_id, "assigned_to": current_user.email}

    ticket = await mongo.db["support_tickets"].find_one(query)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update status
    update = {
        "status": status,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": current_user.email
    }

    if status == "resolved" and not ticket.get("resolved_at"):
        update["resolved_at"] = datetime.now(timezone.utc)

    await mongo.db["support_tickets"].update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": update}
    )

    logger.info(f"Ticket {ticket_id} status updated to {status} by {current_user.email}")

    return {
        "success": True,
        "message": f"Ticket status updated to {status}",
        "ticket_id": ticket_id,
        "new_status": status
    }


@router.get("/sms-tickets/stats/summary", tags=["SMS Support"])
async def get_sms_ticket_stats(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get summary statistics for SMS support tickets"""
    from app.core.database import mongo

    # Build base query for user's tickets
    base_query = {"source": "sms"}
    if not current_user.is_root_admin:
        base_query["assigned_to"] = current_user.email

    # Get counts by status
    new_count = await mongo.db["support_tickets"].count_documents({**base_query, "status": "new"})
    in_progress_count = await mongo.db["support_tickets"].count_documents({**base_query, "status": "in_progress"})
    resolved_count = await mongo.db["support_tickets"].count_documents({**base_query, "status": "resolved"})
    total_count = await mongo.db["support_tickets"].count_documents(base_query)

    # Calculate average response time for resolved tickets
    pipeline = [
        {"$match": {**base_query, "status": "resolved", "first_response_time_minutes": {"$exists": True}}},
        {"$group": {
            "_id": None,
            "avg_response_time": {"$avg": "$first_response_time_minutes"},
            "min_response_time": {"$min": "$first_response_time_minutes"},
            "max_response_time": {"$max": "$first_response_time_minutes"}
        }}
    ]

    cursor = mongo.db["support_tickets"].aggregate(pipeline)
    response_stats = await cursor.to_list(length=None)
    avg_response = response_stats[0] if response_stats else {}

    unread_count = await mongo.db["support_tickets"].count_documents({**base_query, "is_read": False})

    return {
        "total": total_count,
        "by_status": {
            "new": new_count,
            "in_progress": in_progress_count,
            "resolved": resolved_count
        },
        "response_time": {
            "average_minutes": round(avg_response.get("avg_response_time", 0), 1),
            "min_minutes": avg_response.get("min_response_time", 0),
            "max_minutes": avg_response.get("max_response_time", 0)
        },
        "unread_count": unread_count
    }

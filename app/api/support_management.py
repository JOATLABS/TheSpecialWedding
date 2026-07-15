import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, validator

from app.core.database import mongo
from app.constants.support_conversations import (
    guest_sms_ticket_scope,
    support_ticket_owner_scope,
)
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    require_admin_or_planner,
    require_communication_capability,
    require_root_admin,
)
from app.services.support_service import SupportService
from app.utils.communication_access import CommunicationCapability
from app.utils.contact_sanitizer import sanitize_phone
from app.utils.query_validation import validated_status_filter, validated_string_filter
from app.utils.serializers import serialize_mongo_doc

logger = logging.getLogger(__name__)

router = APIRouter()
support_service = SupportService()


class TicketCreateModel(BaseModel):
    subject: str = Field(
        ..., min_length=1, max_length=200, description="Ticket subject"
    )
    description: str = Field(
        ..., min_length=1, max_length=2000, description="Ticket description"
    )
    priority: str = Field(default="medium", description="Ticket priority")
    category: str = Field(default="general", description="Ticket category")
    wedding_id: Optional[str] = Field(None, description="Related wedding ID")
    attachments: List[str] = Field(
        default_factory=list, description="Attachment file URLs"
    )

    @validator("priority")
    def validate_priority(cls, v):
        if v not in ["low", "medium", "high", "urgent"]:
            raise ValueError("Priority must be one of: low, medium, high, urgent")
        return v

    @validator("category")
    def validate_category(cls, v):
        if v not in [
            "technical",
            "billing",
            "feature_request",
            "bug_report",
            "general",
        ]:
            raise ValueError(
                "Category must be one of: technical, billing, feature_request, bug_report, general"
            )
        return v


class TicketUpdateModel(BaseModel):
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    priority: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None

    @validator("priority")
    def validate_priority(cls, v):
        if v is not None and v not in ["low", "medium", "high", "urgent"]:
            raise ValueError("Priority must be one of: low, medium, high, urgent")
        return v

    @validator("category")
    def validate_category(cls, v):
        if v is not None and v not in [
            "technical",
            "billing",
            "feature_request",
            "bug_report",
            "general",
        ]:
            raise ValueError(
                "Category must be one of: technical, billing, feature_request, bug_report, general"
            )
        return v

    @validator("status")
    def validate_status(cls, v):
        if v is not None and v not in ["open", "in_progress", "resolved", "closed"]:
            raise ValueError(
                "Status must be one of: open, in_progress, resolved, closed"
            )
        return v


class CommentCreateModel(BaseModel):
    message: str = Field(
        ..., min_length=1, max_length=1000, description="Comment message"
    )
    is_internal: bool = Field(
        default=False, description="Whether this is an internal admin comment"
    )


# ==================== ADMIN SUPPORT MANAGEMENT ====================


@router.post("/tickets", tags=["Support"])
async def create_ticket(
    ticket_data: TicketCreateModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Create a new support ticket - Authenticated users only"""
    logger.info(
        f"Creating support ticket for user: {current_user.email}, subject: {ticket_data.subject}"
    )
    if ticket_data.wedding_id and not await check_wedding_access(
        current_user, ticket_data.wedding_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Access to this wedding denied",
        )

    result = await support_service.create_ticket(
        ticket_data.dict(), current_user=current_user
    )
    logger.info(
        f"Support ticket created successfully: {result.get('ticket_number', 'unknown')}"
    )
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
    active_only: bool = Query(
        False, description="Show only active ticket statuses for inbox surfaces"
    ),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get support tickets with filtering - Authenticated users can see their own tickets, ROOT_ADMIN sees all"""
    if active_only and status:
        raise HTTPException(
            status_code=400,
            detail="status cannot be combined with active_only",
        )

    # Validate filter parameters
    status = validated_status_filter(
        status, ["open", "in_progress", "resolved", "closed"]
    )
    priority = validated_status_filter(priority, ["low", "medium", "high", "urgent"])
    category = validated_status_filter(
        category, ["technical", "billing", "feature_request", "bug_report", "general"]
    )
    assigned_to = validated_string_filter(assigned_to, max_length=100)
    created_by = validated_string_filter(created_by, max_length=100)
    wedding_id = validated_string_filter(wedding_id, max_length=100)

    filters = {}
    if status:
        filters["status"] = status
    if priority:
        filters["priority"] = priority
    if category:
        filters["category"] = category
    if assigned_to:
        filters["assigned_to"] = assigned_to
    if created_by:
        filters["created_by"] = created_by
    if wedding_id:
        filters["wedding_id"] = wedding_id

    # Non-admin users can only see their own tickets
    is_root_admin = bool(current_user.is_root_admin)
    if not is_root_admin:
        filters.update(support_ticket_owner_scope(current_user))

    return await support_service.get_tickets(
        page=page,
        limit=limit,
        filters=filters,
        platform_support_only=True,
        active_statuses=["open", "in_progress"] if active_only else None,
        current_user=current_user,
        include_internal_comments=is_root_admin,
    )


@router.get("/tickets/{ticket_id}", tags=["Support"])
async def get_ticket(
    ticket_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get specific ticket details with comments"""
    return await support_service.get_ticket(ticket_id, current_user)


@router.put("/tickets/{ticket_id}", tags=["Support"])
async def update_ticket(
    ticket_id: str,
    ticket_data: TicketUpdateModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Update ticket - Users can update their own tickets, ROOT_ADMIN can update any"""
    return await support_service.update_ticket(
        ticket_id, ticket_data.dict(exclude_unset=True), current_user
    )


@router.post("/tickets/{ticket_id}/comments", tags=["Support"])
async def add_comment(
    ticket_id: str,
    comment_data: CommentCreateModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Add comment to ticket"""
    return await support_service.add_comment(
        ticket_id, comment_data.dict(), current_user
    )


@router.get("/tickets/{ticket_id}/comments", tags=["Support"])
async def get_comments(
    ticket_id: str,
    include_internal: bool = Query(False, description="Include internal comments"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get ticket comments"""
    return await support_service.get_comments(
        ticket_id, current_user, include_internal=include_internal
    )


# ==================== ADMIN-ONLY ENDPOINTS ====================


@router.get("/analytics", tags=["Support Admin"])
async def get_support_analytics(
    period: str = Query("30d", description="Time period: 7d, 30d, 90d, 1y"),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get support analytics and metrics - ROOT_ADMIN only"""
    return await support_service.get_analytics(period)


@router.get("/agents", tags=["Support Admin"])
async def get_support_agents(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get list of support agents - ROOT_ADMIN only"""
    return await support_service.get_support_agents()


@router.put("/tickets/{ticket_id}/assign", tags=["Support Admin"])
async def assign_ticket(
    ticket_id: str,
    agent_email: str = Query(..., description="Email of agent to assign"),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Assign ticket to support agent - ROOT_ADMIN only"""
    return await support_service.assign_ticket(
        ticket_id, agent_email, current_user.email
    )


@router.put("/tickets/{ticket_id}/priority", tags=["Support Admin"])
async def update_ticket_priority(
    ticket_id: str,
    priority: str = Query(..., description="New priority level"),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Update ticket priority - ROOT_ADMIN only"""
    if priority not in ["low", "medium", "high", "urgent"]:
        raise HTTPException(status_code=400, detail="Invalid priority level")

    return await support_service.update_ticket(
        ticket_id, {"priority": priority}, current_user
    )


@router.get("/metrics/dashboard", tags=["Support Admin"])
async def get_support_dashboard(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get support dashboard metrics - ROOT_ADMIN only"""
    return await support_service.get_dashboard_metrics()


# ==================== FILE UPLOAD ====================


@router.post("/tickets/{ticket_id}/attachments", tags=["Support"])
async def upload_attachment(
    ticket_id: str,
    file: UploadFile = File(...),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Upload attachment to ticket"""
    return await support_service.upload_attachment(ticket_id, file, current_user)


# ==================== USER ENDPOINTS ====================


@router.get("/my-tickets", tags=["User Support"])
async def get_my_tickets(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    active_only: bool = Query(
        False, description="Show only active ticket statuses for inbox surfaces"
    ),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get current user's tickets"""
    if active_only and status:
        raise HTTPException(
            status_code=400,
            detail="status cannot be combined with active_only",
        )

    filters = support_ticket_owner_scope(current_user)
    if status:
        filters["status"] = status

    return await support_service.get_tickets(
        page=page,
        limit=limit,
        filters=filters,
        platform_support_only=True,
        active_statuses=["open", "in_progress"] if active_only else None,
        current_user=current_user,
        include_internal_comments=False,
    )


@router.get("/categories", tags=["Support"])
async def get_ticket_categories(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get available ticket categories"""
    return {
        "categories": [
            {
                "value": "technical",
                "label": "Technical Issue",
                "description": "Technical problems with the platform",
            },
            {
                "value": "billing",
                "label": "Billing",
                "description": "Payment and subscription issues",
            },
            {
                "value": "feature_request",
                "label": "Feature Request",
                "description": "Request for new features",
            },
            {
                "value": "bug_report",
                "label": "Bug Report",
                "description": "Report software bugs",
            },
            {
                "value": "general",
                "label": "General",
                "description": "General inquiries and support",
            },
        ],
        "priorities": [
            {"value": "low", "label": "Low", "description": "Minor issues, no urgency"},
            {"value": "medium", "label": "Medium", "description": "Standard issues"},
            {
                "value": "high",
                "label": "High",
                "description": "Important issues affecting operations",
            },
            {
                "value": "urgent",
                "label": "Urgent",
                "description": "Critical issues requiring immediate attention",
            },
        ],
    }


# ==================== SMS SUPPORT TICKETS (NEW) ====================


class SMSResponseModel(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=1600,
        description="SMS response message (max 1600 chars)",
    )
    mark_resolved: bool = Field(
        default=False, description="Mark ticket as resolved after sending"
    )


def _phone_lookup_variants(phone: Optional[str]) -> list[str]:
    sanitized = sanitize_phone(phone)
    if not sanitized:
        return []

    digits_only = "".join(ch for ch in sanitized if ch.isdigit())
    variants = {sanitized}

    if digits_only:
        variants.add(digits_only)
        variants.add(f"+{digits_only}")

        if len(digits_only) == 11 and digits_only.startswith("1"):
            local_number = digits_only[1:]
            variants.update({local_number, f"1{local_number}", f"+1{local_number}"})
        elif len(digits_only) == 10:
            variants.update({digits_only, f"1{digits_only}", f"+1{digits_only}"})

    return [variant for variant in variants if variant]


async def _resolve_guest_for_sms_ticket(
    ticket: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    from bson import ObjectId

    guest_collection = mongo.get_guest_collection()
    projection = {"_id": 1, "name": 1}

    guest_id = ticket.get("guest_id")
    if guest_id:
        guest_id_str = str(guest_id)
        if ObjectId.is_valid(guest_id_str):
            guest = await guest_collection.find_one(
                {"_id": ObjectId(guest_id_str)},
                projection,
            )
            if guest:
                return guest

    phone_variants = _phone_lookup_variants(ticket.get("phone"))
    if not phone_variants:
        return None

    phone_query = {"$or": [{"phone": variant} for variant in phone_variants]}
    wedding_id = ticket.get("wedding_id")

    if wedding_id:
        wedding_id_str = str(wedding_id)
        guest = await guest_collection.find_one(
            {**phone_query, "wedding_id": wedding_id_str},
            projection,
        )
        if guest:
            return guest

        if ObjectId.is_valid(wedding_id_str):
            guest = await guest_collection.find_one(
                {**phone_query, "wedding_id": ObjectId(wedding_id_str)},
                projection,
            )
            if guest:
                return guest

        return None

    # An SMS ticket without wedding scope cannot safely select among guests
    # who may share a phone number across separate planner tenants.
    return None


async def _enrich_sms_ticket_guest_context(ticket: Dict[str, Any]) -> Dict[str, Any]:
    has_guest_name = bool((ticket.get("guest_name") or "").strip())
    has_guest_id = bool(ticket.get("guest_id"))
    if has_guest_name and has_guest_id:
        return ticket

    guest = await _resolve_guest_for_sms_ticket(ticket)
    if not guest:
        return ticket

    updates: Dict[str, Any] = {}

    if guest.get("name") and not has_guest_name:
        ticket["guest_name"] = guest["name"]
        updates["guest_name"] = guest["name"]

    guest_id_str = str(guest["_id"]) if guest.get("_id") else None
    if guest_id_str and not has_guest_id:
        ticket["guest_id"] = guest_id_str
        updates["guest_id"] = guest_id_str

    if updates and ticket.get("_id"):
        await mongo.db["support_tickets"].update_one(
            guest_sms_ticket_scope({"_id": ticket["_id"]}),
            {"$set": updates},
        )

    return ticket


@router.get("/sms-tickets", tags=["SMS Support"])
async def get_sms_tickets(
    status: Optional[str] = Query(
        None, description="Filter by status: new, in_progress, resolved"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    active_only: bool = Query(
        False, description="Show only active ticket statuses for inbox surfaces"
    ),
    current_user: ExtendedAuthUser = Depends(
        require_communication_capability(CommunicationCapability.GUEST_SMS)
    ),
):
    """
    Get SMS support tickets
    - Wedding planners see only tickets for their assigned weddings
    - Root administrators are denied by the guest-SMS capability gate
    """
    if active_only and status:
        raise HTTPException(
            status_code=400,
            detail="status cannot be combined with active_only",
        )

    # Build query
    query: Dict[str, Any] = guest_sms_ticket_scope()

    if status:
        query["status"] = status
    elif active_only:
        query["status"] = {"$in": ["new", "in_progress"]}

    # The capability gate excludes root; every remaining actor is owner-scoped.
    query["assigned_to"] = current_user.email

    # Pagination
    skip = (page - 1) * limit

    cursor = (
        mongo.db["support_tickets"]
        .find(query)
        .sort([("updated_at", -1), ("created_at", -1)])
        .skip(skip)
        .limit(limit)
    )
    tickets = await cursor.to_list(length=limit)

    # Convert ObjectId to string
    for ticket in tickets:
        await _enrich_sms_ticket_guest_context(ticket)
        ticket["_id"] = str(ticket["_id"])
        if "guest_id" in ticket and ticket["guest_id"]:
            ticket["guest_id"] = str(ticket["guest_id"])
        if "wedding_id" in ticket and ticket["wedding_id"]:
            ticket["wedding_id"] = str(ticket["wedding_id"])

    total = await mongo.db["support_tickets"].count_documents(query)

    return serialize_mongo_doc(
        {
            "tickets": tickets,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
            "limit": limit,
        }
    )


@router.get("/sms-tickets/{ticket_id}", tags=["SMS Support"])
async def get_sms_ticket(
    ticket_id: str,
    current_user: ExtendedAuthUser = Depends(
        require_communication_capability(CommunicationCapability.GUEST_SMS)
    ),
):
    """Get specific SMS ticket with full details and response history"""
    from bson import ObjectId

    try:
        obj_id = ObjectId(ticket_id)
    except Exception as e:
        logger.error(f"Invalid ObjectId provided for ticket: {ticket_id}, error: {e}")
        raise HTTPException(status_code=400, detail="Invalid ticket ID format")

    query = guest_sms_ticket_scope({"_id": obj_id, "assigned_to": current_user.email})

    ticket = await mongo.db["support_tickets"].find_one(query)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if not ticket.get("is_read"):
        await mongo.db["support_tickets"].update_one(
            query,
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.now(timezone.utc),
                }
            },
        )
        ticket["is_read"] = True

    await _enrich_sms_ticket_guest_context(ticket)

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
    current_user: ExtendedAuthUser = Depends(
        require_communication_capability(CommunicationCapability.GUEST_SMS)
    ),
):
    """
    Send SMS response to guest
    - Sends SMS via configured provider (Twilio/Telnyx)
    - Logs response in ticket history
    - Updates ticket status
    - Calculates response time metrics
    """
    from bson import ObjectId

    from app.core.database import mongo
    from app.services.sms_service import SMSService

    # Get ticket
    try:
        obj_id = ObjectId(ticket_id)
    except Exception as e:
        logger.error(f"Invalid ObjectId provided for ticket: {ticket_id}, error: {e}")
        raise HTTPException(status_code=400, detail="Invalid ticket ID format")

    query = guest_sms_ticket_scope({"_id": obj_id, "assigned_to": current_user.email})

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
            detail=f"Failed to send SMS: {result.get('error', 'Unknown error')}",
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
                "sent_by_name": current_user.user_data.get("company_name")
                or current_user.email,
                "sent_at": now,
                "sms_provider": result.get("provider"),
                "message_id": result.get("message_id"),
            }
        },
        "$set": {
            "updated_at": now,
            "is_read": True,
            "last_response_at": now,
            "last_message_preview": response_data.message[:160],
            "last_message_direction": "outbound",
        },
    }

    # Set first response time if this is the first response
    if not ticket.get("first_response_at"):
        update["$set"]["first_response_at"] = now
        if response_time_minutes is not None:
            update["$set"]["first_response_time_minutes"] = response_time_minutes

    # Mark as resolved if requested
    if response_data.mark_resolved:
        update["$set"]["status"] = "resolved"
        update["$set"]["resolved_at"] = now
        if response_time_minutes is not None:
            update["$set"]["resolution_time_minutes"] = response_time_minutes
    elif ticket.get("status") == "new":
        update["$set"]["status"] = "in_progress"

    # Update ticket
    await mongo.db["support_tickets"].update_one(query, update)

    next_status = update["$set"].get("status", ticket.get("status"))

    logger.info(f"SMS response sent for ticket {ticket_id} by {current_user.email}")

    return {
        "success": True,
        "message": "SMS response sent successfully",
        "sms_result": result,
        "ticket_status": next_status,
        "response_time_minutes": response_time_minutes,
    }


@router.put("/sms-tickets/{ticket_id}/status", tags=["SMS Support"])
async def update_sms_ticket_status(
    ticket_id: str,
    status: str = Query(
        ..., description="New status: new, in_progress, resolved, closed"
    ),
    current_user: ExtendedAuthUser = Depends(
        require_communication_capability(CommunicationCapability.GUEST_SMS)
    ),
):
    """Update SMS ticket status without sending a response"""
    from datetime import datetime, timezone

    from bson import ObjectId

    from app.core.database import mongo

    if status not in ["new", "in_progress", "resolved", "closed"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Get ticket
    try:
        obj_id = ObjectId(ticket_id)
    except Exception as e:
        logger.error(f"Invalid ObjectId provided for ticket: {ticket_id}, error: {e}")
        raise HTTPException(status_code=400, detail="Invalid ticket ID format")

    query = guest_sms_ticket_scope({"_id": obj_id, "assigned_to": current_user.email})

    ticket = await mongo.db["support_tickets"].find_one(query)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update status
    update = {
        "status": status,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": current_user.email,
    }

    if status == "resolved" and not ticket.get("resolved_at"):
        update["resolved_at"] = datetime.now(timezone.utc)

    await mongo.db["support_tickets"].update_one(query, {"$set": update})

    logger.info(
        f"Ticket {ticket_id} status updated to {status} by {current_user.email}"
    )

    return {
        "success": True,
        "message": f"Ticket status updated to {status}",
        "ticket_id": ticket_id,
        "new_status": status,
    }


@router.get("/sms-tickets/stats/summary", tags=["SMS Support"])
async def get_sms_ticket_stats(
    current_user: ExtendedAuthUser = Depends(
        require_communication_capability(CommunicationCapability.GUEST_SMS)
    ),
):
    """Get summary statistics for SMS support tickets"""
    from app.core.database import mongo

    # Build base query for user's tickets
    base_query = guest_sms_ticket_scope({"assigned_to": current_user.email})

    # Get counts by status
    new_count = await mongo.db["support_tickets"].count_documents(
        {**base_query, "status": "new"}
    )
    in_progress_count = await mongo.db["support_tickets"].count_documents(
        {**base_query, "status": "in_progress"}
    )
    resolved_count = await mongo.db["support_tickets"].count_documents(
        {**base_query, "status": "resolved"}
    )
    total_count = await mongo.db["support_tickets"].count_documents(base_query)

    # Calculate average response time for resolved tickets
    pipeline = [
        {
            "$match": {
                **base_query,
                "status": "resolved",
                "first_response_time_minutes": {"$exists": True},
            }
        },
        {
            "$group": {
                "_id": None,
                "avg_response_time": {"$avg": "$first_response_time_minutes"},
                "min_response_time": {"$min": "$first_response_time_minutes"},
                "max_response_time": {"$max": "$first_response_time_minutes"},
            }
        },
    ]

    cursor = mongo.db["support_tickets"].aggregate(pipeline)
    response_stats = await cursor.to_list(length=None)
    avg_response = response_stats[0] if response_stats else {}

    unread_count = await mongo.db["support_tickets"].count_documents(
        {**base_query, "is_read": False}
    )
    urgent_count = await mongo.db["support_tickets"].count_documents(
        {
            **base_query,
            "priority": "urgent",
            "status": {"$in": ["new", "in_progress"]},
        }
    )

    return {
        "total": total_count,
        "by_status": {
            "new": new_count,
            "in_progress": in_progress_count,
            "resolved": resolved_count,
        },
        "response_time": {
            "average_minutes": round(avg_response.get("avg_response_time", 0), 1),
            "min_minutes": avg_response.get("min_response_time", 0),
            "max_minutes": avg_response.get("max_response_time", 0),
        },
        "unread_count": unread_count,
        "urgent_count": urgent_count,
    }

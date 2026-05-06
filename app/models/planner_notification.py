"""
Planner Activity Notifications Model

This handles wedding-specific notifications for planners:
- Form submissions from guests/vendors
- RSVP updates
- Guest messages
- Payment events
- System reminders

These are SEPARATE from platform notifications (root admin announcements).
"""

from datetime import datetime, timezone
from typing import Final, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class PlannerNotificationTypes:
    """Notification type constants with Final type annotations for proper Literal inference"""

    FORM_SUBMISSION: Final[Literal["form_submission"]] = "form_submission"
    RSVP_UPDATE: Final[Literal["rsvp_update"]] = "rsvp_update"
    GUEST_MESSAGE: Final[Literal["guest_message"]] = "guest_message"
    PAYMENT_RECEIVED: Final[Literal["payment_received"]] = "payment_received"
    PAYMENT_FAILED: Final[Literal["payment_failed"]] = "payment_failed"
    CONTRACT_SIGNED: Final[Literal["contract_signed"]] = "contract_signed"
    VENDOR_RESPONSE: Final[Literal["vendor_response"]] = "vendor_response"
    REMINDER: Final[Literal["reminder"]] = "reminder"
    SYSTEM: Final[Literal["system"]] = "system"
    SUPPORT_TICKET_RESPONSE: Final[Literal["support_ticket_response"]] = (
        "support_ticket_response"
    )
    DELIVERY_FAILURE: Final[Literal["delivery_failure"]] = "delivery_failure"
    BULK_SEND_SUMMARY: Final[Literal["bulk_send_summary"]] = "bulk_send_summary"
    # Sprint 3: Couple portal notification types
    COUPLE_MESSAGE: Final[Literal["couple_message"]] = "couple_message"
    COUPLE_NOTE: Final[Literal["couple_note"]] = "couple_note"
    MEETING_BOOKING_REQUEST: Final[Literal["meeting_booking_request"]] = (
        "meeting_booking_request"
    )


NotificationType = Literal[
    "form_submission",
    "rsvp_update",
    "guest_message",
    "payment_received",
    "payment_failed",
    "contract_signed",
    "vendor_response",
    "reminder",
    "system",
    "support_ticket_response",
    "delivery_failure",
    "bulk_send_summary",
    "couple_message",
    "couple_note",
    "meeting_booking_request",
]


class PlannerNotificationCreate(BaseModel):
    """Model for creating a planner activity notification"""

    planner_id: str = Field(..., description="The planner's user ID or email")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    metadata: Optional[dict] = Field(
        default_factory=lambda: {},
        description="Additional context (guest name, form type, amount, etc.)",
    )
    priority: Literal["low", "medium", "high"] = Field(default="medium")
    action_url: Optional[str] = Field(None, description="Deep link to relevant page")


class PlannerNotificationResponse(BaseModel):
    """Response model for planner notification"""

    id: str
    planner_id: str
    wedding_id: Optional[str]
    wedding_name: Optional[str]
    type: NotificationType
    title: str
    message: str
    metadata: dict
    priority: str
    action_url: Optional[str]
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime]

    class Config:
        from_attributes = True


def create_notification_document(
    planner_id: str,
    notification_type: NotificationType,
    title: str,
    message: str,
    wedding_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    priority: str = "medium",
    action_url: Optional[str] = None,
) -> dict:
    """
    Create a notification document for MongoDB insertion.

    Usage:
        doc = create_notification_document(
            planner_id="planner@example.com",
            notification_type="rsvp_update",
            title="New RSVP Response",
            message="John Doe has confirmed attendance for 2 guests",
            wedding_id="wedding_123",
            metadata={"guest_name": "John Doe", "guests": 2, "status": "confirmed"}
        )
    """
    return {
        "_id": ObjectId(),
        "planner_id": planner_id,
        "wedding_id": wedding_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "metadata": metadata or {},
        "priority": priority,
        "action_url": action_url,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
        "read_at": None,
    }

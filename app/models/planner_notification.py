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

from datetime import UTC, datetime
from typing import Final, Literal

from bson import ObjectId
from pydantic import BaseModel, Field


class PlannerNotificationTypes:
    """Notification type constants with Final type annotations for proper Literal inference"""

    FORM_SUBMISSION: Final = "form_submission"
    RSVP_UPDATE: Final = "rsvp_update"
    GUEST_MESSAGE: Final = "guest_message"
    PAYMENT_RECEIVED: Final = "payment_received"
    PAYMENT_FAILED: Final = "payment_failed"
    CONTRACT_SIGNED: Final = "contract_signed"
    VENDOR_RESPONSE: Final = "vendor_response"
    REMINDER: Final = "reminder"
    SYSTEM: Final = "system"
    SUPPORT_TICKET_RESPONSE: Final = "support_ticket_response"
    DELIVERY_FAILURE: Final = "delivery_failure"
    BULK_SEND_SUMMARY: Final = "bulk_send_summary"
    # Sprint 3: Couple portal notification types
    COUPLE_MESSAGE: Final = "couple_message"
    COUPLE_NOTE: Final = "couple_note"
    # Two-stage wedding-checklist nudge:
    #   Stage 1 fires when a wedding is created — prompts the planner
    #   to invite the couple to their portal.
    #   Stage 2 fires when the couple finishes setup-password (i.e.
    #   accepts the portal invite) — surfaces an action-button toast
    #   that one-click sends the seeded couple_intake template.
    WEDDING_CREATED: Final = "wedding_created"
    COUPLE_PORTAL_ACCEPTED: Final = "couple_portal_accepted"
    # Couple has submitted a new booking request that needs the planner's approval
    MEETING_BOOKING_REQUEST: Final = "meeting_booking_request"


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
    "wedding_created",
    "couple_portal_accepted",
    "meeting_booking_request",
]


class PlannerNotificationCreate(BaseModel):
    """Model for creating a planner activity notification"""

    planner_id: str = Field(..., description="The planner's user ID or email")
    wedding_id: str | None = Field(None, description="Associated wedding ID")
    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    metadata: dict | None = Field(
        default_factory=dict,
        description="Additional context (guest name, form type, amount, etc.)",
    )
    priority: Literal["low", "medium", "high"] = Field(default="medium")
    action_url: str | None = Field(None, description="Deep link to relevant page")


class PlannerNotificationResponse(BaseModel):
    """Response model for planner notification"""

    id: str
    planner_id: str
    wedding_id: str | None
    wedding_name: str | None
    type: NotificationType
    title: str
    message: str
    metadata: dict
    priority: str
    action_url: str | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None

    class Config:
        from_attributes = True


def create_notification_document(
    planner_id: str,
    notification_type: NotificationType,
    title: str,
    message: str,
    wedding_id: str | None = None,
    metadata: dict | None = None,
    priority: str = "medium",
    action_url: str | None = None,
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
        "created_at": datetime.now(UTC),
        "read_at": None,
    }

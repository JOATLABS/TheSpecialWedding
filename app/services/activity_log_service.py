"""
Planner Activity Logging Service

Standardized service for logging planner activities to the activity_logs collection.
This populates the planner dashboard activity feed with events like:
- RSVP submissions
- Guest additions/updates/deletions
- SMS/reminder sends
- Email sends
- Support tickets (handled by support_service.py)

Usage:
    from app.services.activity_log_service import activity_log_service

    # Log an RSVP submission
    await activity_log_service.log_rsvp_received(
        wedding_id="...",
        guest_name="John Doe",
        response="confirmed",
        planner_email="planner@example.com"
    )
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.database import mongo

logger = logging.getLogger(__name__)


class ActivityTypes:
    """Activity type constants for planner activities"""

    # RSVP events
    RSVP_RECEIVED = "rsvp_received"
    RSVP_UPDATED = "rsvp_updated"

    # Guest events
    GUEST_ADDED = "guest_added"
    GUEST_UPDATED = "guest_updated"
    GUEST_DELETED = "guest_deleted"
    GUEST_IMPORTED = "guest_imported"

    # Communication events
    SMS_SENT = "sms_sent"
    EMAIL_SENT = "email_sent"
    REMINDER_SENT = "reminder_sent"

    # Support events (for reference, handled by support_service.py)
    SUPPORT_TICKET_CREATED = "support_ticket_created"
    SUPPORT_TICKET_COMMENT = "support_ticket_comment"

    # Wedding events
    WEDDING_CREATED = "wedding_created"
    WEDDING_UPDATED = "wedding_updated"

    # Team management events
    TEAM_MEMBER_INVITED = "team_member_invited"
    TEAM_MEMBER_ACCEPTED = "team_member_accepted"
    TEAM_MEMBER_UPDATED = "team_member_updated"
    TEAM_MEMBER_DEACTIVATED = "team_member_deactivated"
    TEAM_MEMBER_REACTIVATED = "team_member_reactivated"
    TEAM_MEMBER_REMOVED = "team_member_removed"


class ActivityLogService:
    """
    Service for logging planner activities to the activity_logs collection.

    This is separate from AdminActivityService which logs ROOT_ADMIN actions
    to the admin_activity_log collection.
    """

    def __init__(self):
        self.collection_name = "activity_logs"

    @property
    def collection(self):
        return mongo.db[self.collection_name]

    async def log_activity(
        self,
        activity_type: str,
        message: str,
        wedding_id: str | None = None,
        planner_email: str | None = None,
        actor_email: str | None = None,
        actor_name: str | None = None,
        actor_role: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new activity log entry.

        Args:
            activity_type: Type of activity (use ActivityTypes constants)
            message: Human-readable description of the activity
            wedding_id: ID of the wedding this activity relates to
            planner_email: Email of the planner who owns the wedding
            actor_email: Email of who performed the action (may be guest, planner, or system)
            actor_name: Display name of the actor (e.g. "John Smith")
            actor_role: Role of the actor (e.g. "Editor", "Admin", "Planner")
            metadata: Additional context data
        """
        try:
            now = datetime.now(UTC)
            doc = {
                "type": activity_type,
                "message": message,
                "timestamp": now,
                "created_at": now,
                "wedding_id": wedding_id,
                "planner_email": planner_email,
                "actor_email": actor_email or planner_email,
                "actor_name": actor_name,
                "actor_role": actor_role,
                "metadata": metadata or {},
            }

            result = await self.collection.insert_one(doc)

            if not result.inserted_id:
                logger.warning(
                    "[ActivityLog] Failed to insert activity log: %s", activity_type
                )
                return {"id": None, "success": False}

            logger.debug(
                f"Logged planner activity: {activity_type} for wedding {wedding_id}"
            )

            return {"id": str(result.inserted_id), "success": True}

        except Exception as e:
            # Activity logging should not block main operations
            logger.error("[ActivityLog] Error logging activity: %s", str(e))
            return {"id": None, "success": False, "error": str(e)}

    # ==================== RSVP CONVENIENCE METHODS ====================

    async def log_rsvp_received(
        self,
        wedding_id: str,
        guest_name: str,
        response: str,
        planner_email: str | None = None,
        guest_email: str | None = None,
        plus_ones: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log when an RSVP is submitted by a guest"""
        response_text = {
            "confirmed": "accepted",
            "declined": "declined",
            "pending": "is pending",
        }.get(response.lower(), response)

        message = f"{guest_name} {response_text} the invitation"
        if plus_ones > 0:
            message += f" (+{plus_ones} guest{'s' if plus_ones > 1 else ''})"

        return await self.log_activity(
            activity_type=ActivityTypes.RSVP_RECEIVED,
            message=message,
            wedding_id=wedding_id,
            planner_email=planner_email,
            actor_email=guest_email or "guest",
            metadata={
                "guest_name": guest_name,
                "guest_email": guest_email,
                "response": response,
                "plus_ones": plus_ones,
                **(metadata or {}),
            },
        )

    async def log_rsvp_updated(
        self,
        wedding_id: str,
        guest_name: str,
        old_response: str,
        new_response: str,
        planner_email: str | None = None,
        guest_email: str | None = None,
        guest_id: str | None = None,
    ) -> dict[str, Any]:
        """Log when an RSVP is updated"""
        message = f"{guest_name} changed RSVP from {old_response} to {new_response}"

        meta: dict[str, Any] = {
            "guest_name": guest_name,
            "old_response": old_response,
            "new_response": new_response,
        }
        if guest_id:
            meta["guest_id"] = guest_id
        return await self.log_activity(
            activity_type=ActivityTypes.RSVP_UPDATED,
            message=message,
            wedding_id=wedding_id,
            planner_email=planner_email,
            actor_email=guest_email or "guest",
            metadata=meta,
        )

    # ==================== GUEST CONVENIENCE METHODS ====================

    async def log_guest_added(
        self,
        wedding_id: str,
        guest_name: str,
        planner_email: str,
        guest_id: str | None = None,
        guest_email: str | None = None,
        added_by: str | None = None,
    ) -> dict[str, Any]:
        """Log when a guest is added to the guest list"""
        meta: dict[str, Any] = {"guest_name": guest_name, "guest_email": guest_email}
        if guest_id:
            meta["guest_id"] = guest_id
        return await self.log_activity(
            activity_type=ActivityTypes.GUEST_ADDED,
            message=f"Added guest: {guest_name}",
            wedding_id=wedding_id,
            planner_email=planner_email,
            actor_email=added_by or planner_email,
            metadata=meta,
        )

    async def log_guest_updated(
        self,
        wedding_id: str,
        guest_name: str,
        planner_email: str,
        guest_id: str | None = None,
        changes: dict[str, Any] | None = None,
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        """Log when a guest's information is updated"""
        meta: dict[str, Any] = {"guest_name": guest_name, "changes": changes or {}}
        if guest_id:
            meta["guest_id"] = guest_id
        return await self.log_activity(
            activity_type=ActivityTypes.GUEST_UPDATED,
            message=f"Updated guest: {guest_name}",
            wedding_id=wedding_id,
            planner_email=planner_email,
            actor_email=updated_by or planner_email,
            metadata=meta,
        )

    async def log_guest_deleted(
        self,
        wedding_id: str,
        guest_name: str,
        planner_email: str,
        guest_id: str | None = None,
        deleted_by: str | None = None,
    ) -> dict[str, Any]:
        """Log when a guest is removed from the guest list"""
        meta: dict[str, Any] = {"guest_name": guest_name}
        if guest_id:
            meta["guest_id"] = guest_id
        return await self.log_activity(
            activity_type=ActivityTypes.GUEST_DELETED,
            message=f"Removed guest: {guest_name}",
            wedding_id=wedding_id,
            planner_email=planner_email,
            actor_email=deleted_by or planner_email,
            metadata=meta,
        )

    async def log_guests_imported(
        self, wedding_id: str, count: int, planner_email: str, source: str = "csv"
    ) -> dict[str, Any]:
        """Log when guests are bulk imported"""
        return await self.log_activity(
            activity_type=ActivityTypes.GUEST_IMPORTED,
            message=f"Imported {count} guest{'s' if count != 1 else ''} from {source}",
            wedding_id=wedding_id,
            planner_email=planner_email,
            actor_email=planner_email,
            metadata={"count": count, "source": source},
        )

    # ==================== COMMUNICATION CONVENIENCE METHODS ====================

    async def log_sms_sent(
        self,
        wedding_id: str,
        recipient_name: str,
        recipient_phone: str,
        message_type: str,
        planner_email: str,
        status: str = "sent",
        guest_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log when an SMS is sent"""
        status_text = "sent" if status == "sent" else f"failed ({status})"
        message = f"SMS {status_text} to {recipient_name}: {message_type}"

        meta: dict[str, Any] = {
            "recipient_name": recipient_name,
            "recipient_phone": (
                recipient_phone[-4:] if recipient_phone else None
            ),  # Last 4 digits only
            "message_type": message_type,
            "status": status,
            **(metadata or {}),
        }
        if guest_id:
            meta["guest_id"] = guest_id
        return await self.log_activity(
            activity_type=ActivityTypes.SMS_SENT,
            message=message,
            wedding_id=wedding_id,
            planner_email=planner_email,
            actor_email="system",
            metadata=meta,
        )

    async def log_reminder_sent(
        self,
        wedding_id: str,
        recipient_count: int,
        reminder_type: str,
        planner_email: str,
        channel: str = "sms",
    ) -> dict[str, Any]:
        """Log when reminders are sent to guests"""
        message = f"Sent {reminder_type} reminder to {recipient_count} guest{'s' if recipient_count != 1 else ''} via {channel}"

        return await self.log_activity(
            activity_type=ActivityTypes.REMINDER_SENT,
            message=message,
            wedding_id=wedding_id,
            planner_email=planner_email,
            actor_email=planner_email,
            metadata={
                "recipient_count": recipient_count,
                "reminder_type": reminder_type,
                "channel": channel,
            },
        )

    async def log_email_sent(
        self,
        wedding_id: str,
        recipient_name: str,
        email_type: str,
        planner_email: str,
        recipient_email: str | None = None,
        guest_id: str | None = None,
        status: str = "sent",
    ) -> dict[str, Any]:
        """Log when an email is sent"""
        status_text = "sent" if status == "sent" else f"failed ({status})"
        message = f"Email {status_text} to {recipient_name}: {email_type}"

        meta: dict[str, Any] = {
            "recipient_name": recipient_name,
            "recipient_email": recipient_email,
            "email_type": email_type,
            "status": status,
        }
        if guest_id:
            meta["guest_id"] = guest_id
        return await self.log_activity(
            activity_type=ActivityTypes.EMAIL_SENT,
            message=message,
            wedding_id=wedding_id,
            planner_email=planner_email,
            actor_email="system",
            metadata=meta,
        )

    # ── Team management activity helpers ─────────────────────────────────

    async def log_team_member_invited(
        self,
        planner_email: str,
        member_email: str,
        role: str,
        invited_by: str,
        member_name: str | None = None,
    ):
        display = member_name or member_email
        return await self.log_activity(
            activity_type=ActivityTypes.TEAM_MEMBER_INVITED,
            message=f"Invited {display} as {role}",
            planner_email=planner_email,
            actor_email=invited_by,
            actor_role="Planner",
            metadata={
                "member_email": member_email,
                "member_name": member_name,
                "role": role,
            },
        )

    async def log_team_member_accepted(
        self,
        planner_email: str,
        member_email: str,
        member_name: str,
        role: str | None = None,
    ):
        role_label = f" ({role})" if role else ""
        return await self.log_activity(
            activity_type=ActivityTypes.TEAM_MEMBER_ACCEPTED,
            message=f"{member_name}{role_label} accepted their team invitation",
            planner_email=planner_email,
            actor_email=member_email,
            actor_name=member_name,
            actor_role=role,
            metadata={
                "member_email": member_email,
                "member_name": member_name,
                "role": role,
            },
        )

    async def log_team_member_updated(
        self,
        planner_email: str,
        member_email: str,
        changes: dict,
        updated_by: str,
        member_name: str | None = None,
        member_role: str | None = None,
    ):
        display = member_name or member_email
        role_label = f" ({member_role})" if member_role else ""
        return await self.log_activity(
            activity_type=ActivityTypes.TEAM_MEMBER_UPDATED,
            message=f"Updated team member {display}{role_label}",
            planner_email=planner_email,
            actor_email=updated_by,
            actor_name=member_name,
            actor_role=member_role,
            metadata={
                "member_email": member_email,
                "member_name": member_name,
                "role": member_role,
                "changes": changes,
            },
        )

    async def log_team_member_deactivated(
        self,
        planner_email: str,
        member_email: str,
        deactivated_by: str,
        member_name: str | None = None,
        member_role: str | None = None,
    ):
        display = member_name or member_email
        role_label = f" ({member_role})" if member_role else ""
        return await self.log_activity(
            activity_type=ActivityTypes.TEAM_MEMBER_DEACTIVATED,
            message=f"Deactivated {display}{role_label}",
            planner_email=planner_email,
            actor_email=deactivated_by,
            metadata={
                "member_email": member_email,
                "member_name": member_name,
                "role": member_role,
            },
        )

    async def log_team_member_reactivated(
        self,
        planner_email: str,
        member_email: str,
        reactivated_by: str,
        member_name: str | None = None,
        member_role: str | None = None,
    ):
        display = member_name or member_email
        role_label = f" ({member_role})" if member_role else ""
        return await self.log_activity(
            activity_type=ActivityTypes.TEAM_MEMBER_REACTIVATED,
            message=f"Reactivated {display}{role_label}",
            planner_email=planner_email,
            actor_email=reactivated_by,
            metadata={
                "member_email": member_email,
                "member_name": member_name,
                "role": member_role,
            },
        )

    async def log_team_member_removed(
        self,
        planner_email: str,
        member_email: str,
        removed_by: str,
        member_name: str | None = None,
        member_role: str | None = None,
    ):
        display = member_name or member_email
        role_label = f" ({member_role})" if member_role else ""
        return await self.log_activity(
            activity_type=ActivityTypes.TEAM_MEMBER_REMOVED,
            message=f"Removed {display}{role_label}",
            planner_email=planner_email,
            actor_email=removed_by,
            metadata={
                "member_email": member_email,
                "member_name": member_name,
                "role": member_role,
            },
        )


# Singleton instance
activity_log_service = ActivityLogService()

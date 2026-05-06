"""
Planner Activity Notifications Service

Handles CRUD operations and triggers for planner-specific notifications.
These are wedding activity notifications (RSVPs, forms, payments), NOT platform announcements.

Includes Web Push notification support for instant browser notifications.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

from bson import ObjectId
from fastapi import HTTPException

from app.core.database import mongo
from app.models.planner_notification import (
    NotificationType,
    PlannerNotificationTypes,
    create_notification_document,
)
from app.utils.support_inbox_links import build_support_inbox_path

logger = logging.getLogger(__name__)


class PlannerNotificationService:
    """Service for managing planner activity notifications"""

    def __init__(self):
        self.collection = mongo.db["planner_notifications"]
        self.weddings_collection = mongo.db["weddings"]

    # ==================== CRUD OPERATIONS ====================

    async def _get_wedding_name(self, wedding_id: Optional[str]) -> Optional[str]:
        """Get wedding name for push notification context"""
        if not wedding_id:
            return None
        try:
            wedding = await self.weddings_collection.find_one(
                {"wedding_id": wedding_id}, {"couple_names": 1}
            )
            return wedding.get("couple_names") if wedding else None
        except Exception:
            return None

    async def _check_push_enabled(self, planner_id: str) -> bool:
        """Check if user has push notifications enabled (defaults to True if not set)"""
        try:
            users_collection = mongo.db["users"]
            user = await users_collection.find_one(
                {"email": planner_id}, {"push_notifications_enabled": 1}
            )
            if user:
                # Default to True if field doesn't exist (opt-out model)
                return user.get("push_notifications_enabled", True)
            return True
        except Exception:
            # On error, default to sending notification
            return True

    async def _send_push_notification(
        self,
        planner_id: str,
        notification_type: str,
        title: str,
        message: str,
        wedding_name: Optional[str] = None,
        action_url: Optional[str] = None,
    ):
        """Send push notification via Web Push API (non-blocking)"""
        try:
            # Check if user has push notifications enabled
            if not await self._check_push_enabled(planner_id):
                logger.debug(f"Push notifications disabled for user {planner_id}")
                return

            # Late import to avoid circular dependencies
            from app.services.web_push_service import web_push_service

            if web_push_service.enabled:
                # Build full message with wedding name if provided
                full_message = (
                    f"[{wedding_name}] {message}" if wedding_name else message
                )

                await web_push_service.send_notification(
                    user_id=planner_id,
                    title=title,
                    body=full_message,
                    url=action_url,
                    tag=notification_type,
                )
        except Exception as e:
            # Don't fail the main notification if push fails
            logger.warning(f"Failed to send push notification: {str(e)}")

    async def create_notification(
        self,
        planner_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        wedding_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        priority: str = "medium",
        action_url: Optional[str] = None,
    ) -> dict:
        """Create a new activity notification for a planner"""
        try:
            doc = create_notification_document(
                planner_id=planner_id,
                notification_type=notification_type,
                title=title,
                message=message,
                wedding_id=wedding_id,
                metadata=metadata,
                priority=priority,
                action_url=action_url,
            )

            result = await self.collection.insert_one(doc)

            if not result.inserted_id:
                raise HTTPException(
                    status_code=500, detail="Failed to create notification"
                )

            logger.info(
                f"Created {notification_type} notification for planner {planner_id}"
            )

            # Send push notification (non-blocking)
            wedding_name = await self._get_wedding_name(wedding_id)
            push_task = asyncio.create_task(
                self._send_push_notification(
                    planner_id=planner_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    wedding_name=wedding_name,
                    action_url=action_url,
                )
            )
            push_task.add_done_callback(
                lambda t: t.exception() if not t.cancelled() and t.exception() else None
            )

            # Broadcast via SSE (non-blocking)
            from app.services.sse_manager import sse_manager

            sse_task = asyncio.create_task(
                sse_manager.broadcast_to_user(
                    planner_id,
                    "notification-new",
                    {
                        "title": title,
                        "message": message,
                        "type": notification_type,
                        "wedding_id": wedding_id,
                        "priority": priority,
                    },
                )
            )
            sse_task.add_done_callback(
                lambda t: t.exception() if not t.cancelled() and t.exception() else None
            )

            return {
                "id": str(result.inserted_id),
                "message": "Notification created successfully",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating planner notification: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating notification: {str(e)}"
            )

    async def get_notifications(
        self,
        planner_id: str,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False,
        wedding_id: Optional[str] = None,
        notification_type: Optional[str] = None,
    ) -> dict:
        """Get activity notifications for a planner"""
        try:
            query: Dict[str, Any] = {"planner_id": planner_id}

            if unread_only:
                query["is_read"] = False

            if wedding_id:
                query["wedding_id"] = wedding_id

            if notification_type:
                query["type"] = notification_type

            total = await self.collection.count_documents(query)
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit if total > 0 else 0

            cursor = (
                self.collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            notifications = []

            async for doc in cursor:
                # Enrich with wedding name if available
                wedding_name = None
                if doc.get("wedding_id"):
                    wedding = await self.weddings_collection.find_one(
                        {"wedding_id": doc["wedding_id"]}, {"title": 1}
                    )
                    if wedding:
                        wedding_name = wedding.get("title")

                notifications.append(
                    {
                        "_id": str(doc["_id"]),
                        "id": str(doc["_id"]),
                        "planner_id": doc["planner_id"],
                        "wedding_id": doc.get("wedding_id"),
                        "wedding_name": wedding_name,
                        "type": doc["type"],
                        "title": doc["title"],
                        "message": doc["message"],
                        "metadata": doc.get("metadata", {}),
                        "priority": doc.get("priority", "medium"),
                        "action_url": doc.get("action_url"),
                        "is_read": doc.get("is_read", False),
                        "created_at": (
                            doc["created_at"].isoformat()
                            if doc.get("created_at")
                            else None
                        ),
                        "read_at": (
                            doc["read_at"].isoformat() if doc.get("read_at") else None
                        ),
                    }
                )

            return {
                "notifications": notifications,
                "total": total,
                "page": page,
                "pages": pages,
                "unread_count": await self.collection.count_documents(
                    {"planner_id": planner_id, "is_read": False}
                ),
            }

        except Exception as e:
            logger.error(f"Error getting planner notifications: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving notifications: {str(e)}"
            )

    async def get_notification_count(self, planner_id: str) -> dict:
        """Get notification counts for a planner"""
        try:
            total = await self.collection.count_documents({"planner_id": planner_id})
            unread = await self.collection.count_documents(
                {"planner_id": planner_id, "is_read": False}
            )

            return {"total": total, "unread": unread, "read": total - unread}

        except Exception as e:
            logger.error(f"Error getting notification count: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting count: {str(e)}"
            )

    async def mark_as_read(self, notification_id: str, planner_id: str) -> dict:
        """Mark a notification as read"""
        try:
            obj_id = ObjectId(notification_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid notification ID")

        try:
            result = await self.collection.update_one(
                {"_id": obj_id, "planner_id": planner_id},
                {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc)}},
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Notification not found")

            # Broadcast updated count via SSE
            from app.services.sse_manager import sse_manager

            try:
                counts = await self.get_notification_count(planner_id)
                task = asyncio.create_task(
                    sse_manager.broadcast_to_user(
                        planner_id, "notification-count", counts
                    )
                )
                task.add_done_callback(
                    lambda t: (
                        t.exception() if not t.cancelled() and t.exception() else None
                    )
                )
            except Exception:
                pass

            return {"message": "Notification marked as read"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error updating notification: {str(e)}"
            )

    async def mark_action_completed(
        self, notification_id: str, planner_id: str
    ) -> dict:
        """Mark a notification as actioned via its action button.

        Distinct from `is_read`: a notification can be read but its
        action ("Send checklist", "Invite couple") still pending. This
        endpoint is invoked by toast handlers after their network call
        succeeds so the bell entry stops re-prompting and the next
        toast that re-opens it can fall back to a read-only state.

        Idempotent: a second call on an already-actioned notification
        is a no-op (still returns 200 to keep the client UX stable).
        """
        try:
            obj_id = ObjectId(notification_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid notification ID")

        try:
            now = datetime.now(timezone.utc)
            result = await self.collection.update_one(
                {"_id": obj_id, "planner_id": planner_id},
                {
                    "$set": {
                        "actioned_at": now,
                        "actioned_via_action_button": True,
                        "is_read": True,
                        "read_at": now,
                    }
                },
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Notification not found")

            from app.services.sse_manager import sse_manager

            try:
                counts = await self.get_notification_count(planner_id)
                task = asyncio.create_task(
                    sse_manager.broadcast_to_user(
                        planner_id, "notification-count", counts
                    )
                )
                task.add_done_callback(
                    lambda t: (
                        t.exception() if not t.cancelled() and t.exception() else None
                    )
                )
            except Exception:
                pass

            return {"message": "Notification marked as actioned"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error marking notification actioned: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error updating notification: {str(e)}"
            )

    async def mark_all_as_read(
        self, planner_id: str, wedding_id: Optional[str] = None
    ) -> dict:
        """Mark all notifications as read for a planner"""
        try:
            query = {"planner_id": planner_id, "is_read": False}
            if wedding_id:
                query["wedding_id"] = wedding_id

            result = await self.collection.update_many(
                query,
                {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc)}},
            )

            # Broadcast updated count via SSE
            from app.services.sse_manager import sse_manager

            try:
                counts = await self.get_notification_count(planner_id)
                task = asyncio.create_task(
                    sse_manager.broadcast_to_user(
                        planner_id, "notification-count", counts
                    )
                )
                task.add_done_callback(
                    lambda t: (
                        t.exception() if not t.cancelled() and t.exception() else None
                    )
                )
            except Exception:
                pass

            return {
                "message": f"Marked {result.modified_count} notifications as read",
                "count": result.modified_count,
            }

        except Exception as e:
            logger.error(f"Error marking all as read: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error updating notifications: {str(e)}"
            )

    async def delete_notification(self, notification_id: str, planner_id: str) -> dict:
        """Delete a notification"""
        try:
            obj_id = ObjectId(notification_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid notification ID")

        try:
            result = await self.collection.delete_one(
                {"_id": obj_id, "planner_id": planner_id}
            )

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Notification not found")

            return {"message": "Notification deleted"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting notification: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error deleting notification: {str(e)}"
            )

    # ==================== TRIGGER HELPERS ====================
    # These methods are called by other services when events occur

    async def notify_form_submission(
        self,
        planner_id: str,
        wedding_id: str,
        form_type: str,
        submitter_name: str,
        form_id: Optional[str] = None,
    ):
        """Trigger notification when a form is submitted"""
        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.FORM_SUBMISSION,
            title="New Form Submission",
            message=f"{submitter_name} submitted a {form_type} form",
            wedding_id=wedding_id,
            metadata={
                "form_type": form_type,
                "submitter_name": submitter_name,
                "form_id": form_id,
            },
            action_url=f"/admin/planner/weddings/{wedding_id}/forms",
        )

    # =========================================================================
    # Two-stage wedding-checklist nudge
    # =========================================================================
    #
    # Stage 1 (notify_wedding_created) fires the moment a wedding row is
    # created. The toast prompts the planner to invite the couple to
    # their portal next.
    #
    # Stage 2 (notify_couple_portal_accepted) fires when the couple
    # completes setup-password — i.e. they accepted the portal invite.
    # The toast carries the seeded couple_intake form id so the planner
    # can one-click "Send checklist" without navigating anywhere.
    #
    # Both helpers wrap create_notification, which already handles SSE
    # broadcast + web-push delivery in addition to Mongo persistence.

    async def notify_wedding_created(
        self,
        planner_id: str,
        wedding_id: str,
        couple_names: Optional[str] = None,
    ):
        """Stage 1: a wedding has just been created."""
        couple_label = (couple_names or "the couple").strip() or "the couple"
        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.WEDDING_CREATED,
            title="New wedding created",
            message=(
                f"Invite {couple_label} to their portal next — "
                f"they'll be ready for the wedding checklist once they accept."
            ),
            wedding_id=wedding_id,
            metadata={"couple_names": couple_names},
            action_url=f"/admin/planner/weddings/{wedding_id}?tab=couple",
        )

    async def notify_couple_portal_accepted(
        self,
        planner_id: str,
        wedding_id: Optional[str],
        couple_email: str,
        couple_names: Optional[str],
        seeded_form_id: Optional[str],
    ):
        """Stage 2: the couple has accepted the portal invite.

        Carries ``seeded_form_id`` (the planner's catalog-seeded
        ``couple_intake`` form) and the couple's email in metadata so
        the frontend toast can render an action button that one-click
        dispatches the form via ``POST /admin/forms/{form_id}/send``.
        """
        couple_label = (couple_names or "the couple").strip() or "The couple"
        action_url = (
            f"/admin/planner/forms/{seeded_form_id}/send"
            f"?prefill_email={quote(couple_email or '')}"
            if seeded_form_id
            else f"/admin/planner/weddings/{wedding_id or ''}"
        )
        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.COUPLE_PORTAL_ACCEPTED,
            title=f"{couple_label} accepted the portal invite",
            message="Send them the wedding checklist now.",
            wedding_id=wedding_id,
            metadata={
                "couple_email": couple_email,
                "couple_names": couple_names,
                "form_id": seeded_form_id,
            },
            action_url=action_url,
        )

    async def notify_rsvp_update(
        self,
        planner_id: str,
        wedding_id: str,
        guest_name: str,
        status: str,
        guest_count: int = 1,
        guest_id: Optional[str] = None,
    ):
        """Trigger notification when RSVP status changes"""
        status_text = (
            "confirmed attendance" if status == "confirmed" else f"responded: {status}"
        )
        guest_text = f" for {guest_count} guests" if guest_count > 1 else ""

        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.RSVP_UPDATE,
            title="RSVP Update",
            message=f"{guest_name} {status_text}{guest_text}",
            wedding_id=wedding_id,
            metadata={
                "guest_name": guest_name,
                "status": status,
                "guest_count": guest_count,
                "guest_id": guest_id,
            },
            action_url=f"/admin/planner/weddings/{wedding_id}/guests",
        )

    async def notify_guest_message(
        self,
        planner_id: str,
        wedding_id: str,
        guest_name: str,
        message_preview: str,
        guest_id: Optional[str] = None,
    ):
        """Trigger notification when a guest sends a message"""
        preview = (
            message_preview[:100] + "..."
            if len(message_preview) > 100
            else message_preview
        )

        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.GUEST_MESSAGE,
            title="New Guest Message",
            message=f"{guest_name}: {preview}",
            wedding_id=wedding_id,
            metadata={"guest_name": guest_name, "guest_id": guest_id},
            priority="high",
            action_url=f"/admin/planner/weddings/{wedding_id}/messages",
        )

    async def notify_payment_received(
        self,
        planner_id: str,
        wedding_id: str,
        amount: float,
        payer_name: str,
        payment_id: Optional[str] = None,
    ):
        """Trigger notification when a payment is received"""
        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.PAYMENT_RECEIVED,
            title="Payment Received",
            message=f"${amount:,.2f} received from {payer_name}",
            wedding_id=wedding_id,
            metadata={
                "amount": amount,
                "payer_name": payer_name,
                "payment_id": payment_id,
            },
            priority="high",
            action_url="/admin/planner/money",
        )

    async def notify_payment_failed(
        self,
        planner_id: str,
        wedding_id: str,
        amount: float,
        payer_name: str,
        reason: Optional[str] = None,
        payment_id: Optional[str] = None,
    ):
        """Trigger notification when a payment fails"""
        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.PAYMENT_FAILED,
            title="Payment Failed",
            message=f"${amount:,.2f} payment from {payer_name} failed"
            + (f": {reason}" if reason else ""),
            wedding_id=wedding_id,
            metadata={
                "amount": amount,
                "payer_name": payer_name,
                "reason": reason,
                "payment_id": payment_id,
            },
            priority="high",
            action_url="/admin/planner/money",
        )

    async def notify_contract_signed(
        self,
        planner_id: str,
        wedding_id: str,
        signer_name: str,
        contract_id: Optional[str] = None,
    ):
        """Trigger notification when a contract is signed"""
        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.CONTRACT_SIGNED,
            title="Contract Signed",
            message=f"{signer_name} signed the contract",
            wedding_id=wedding_id,
            metadata={"signer_name": signer_name, "contract_id": contract_id},
            priority="high",
            action_url=f"/admin/planner/weddings/{wedding_id}/contracts",
        )

    async def notify_vendor_response(
        self,
        planner_id: str,
        wedding_id: str,
        vendor_name: str,
        response_type: str,
        vendor_id: Optional[str] = None,
    ):
        """Trigger notification when a vendor responds"""
        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.VENDOR_RESPONSE,
            title="Vendor Response",
            message=f"{vendor_name} {response_type}",
            wedding_id=wedding_id,
            metadata={
                "vendor_name": vendor_name,
                "response_type": response_type,
                "vendor_id": vendor_id,
            },
            action_url="/admin/planner/vendors",
        )

    async def notify_task_reminder(
        self,
        planner_id: str,
        task_title: str,
        due_date: str,
        wedding_id: Optional[str] = None,
        task_id: Optional[str] = None,
        reminder_minutes: Optional[int] = None,
    ):
        """Trigger notification for a task reminder (calendar task due soon)"""
        if reminder_minutes:
            if reminder_minutes >= 1440:  # 24 hours or more
                days = reminder_minutes // 1440
                time_str = f"{days} day{'s' if days > 1 else ''}"
            elif reminder_minutes >= 60:
                hours = reminder_minutes // 60
                time_str = f"{hours} hour{'s' if hours > 1 else ''}"
            else:
                time_str = (
                    f"{reminder_minutes} minute{'s' if reminder_minutes > 1 else ''}"
                )
            message = f"Task '{task_title}' is due in {time_str}"
        else:
            message = f"Task '{task_title}' is due soon"

        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.REMINDER,
            title="Task Reminder",
            message=message,
            wedding_id=wedding_id,
            metadata={
                "task_title": task_title,
                "task_id": task_id,
                "due_date": due_date,
                "reminder_minutes": reminder_minutes,
            },
            priority="high",
            action_url="/admin/planner/calendar",
        )

    async def notify_delivery_failure(
        self,
        planner_id: str,
        wedding_id: str,
        channel: str,
        to_address: str,
        error_message: Optional[str] = None,
        guest_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """Trigger notification when an SMS or email delivery fails"""
        recipient = guest_name or to_address
        channel_label = "SMS" if channel == "sms" else "Email"
        reason = f": {error_message}" if error_message else ""

        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.DELIVERY_FAILURE,
            title=f"{channel_label} Delivery Failed",
            message=f"{channel_label} to {recipient} failed{reason}",
            wedding_id=wedding_id,
            metadata={
                "channel": channel,
                "to_address": to_address,
                "guest_name": guest_name,
                "error_message": error_message,
                **(metadata or {}),
            },
            priority="high",
            action_url="/admin/communications/history",
        )

    async def notify_bulk_delivery_summary(
        self,
        planner_id: str,
        wedding_id: str,
        channel: str,
        sent: int,
        failed: int,
        skipped: int = 0,
        metadata: Optional[dict] = None,
    ):
        """Trigger notification summarizing a bulk send operation"""
        channel_label = "SMS" if channel == "sms" else "Email"
        parts = [f"{sent} sent"]
        if failed > 0:
            parts.append(f"{failed} failed")
        if skipped > 0:
            parts.append(f"{skipped} skipped")

        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.BULK_SEND_SUMMARY,
            title=f"{channel_label} Send: {', '.join(parts)}",
            message=f"Bulk {channel_label} send completed. {', '.join(parts)}.",
            wedding_id=wedding_id,
            metadata={
                "channel": channel,
                "sent": sent,
                "failed": failed,
                "skipped": skipped,
                **(metadata or {}),
            },
            priority="high" if failed > 0 else "low",
            action_url="/admin/communications/history",
        )

    async def notify_support_ticket_response(
        self,
        planner_id: str,
        ticket_number: str,
        ticket_subject: str,
        responder_name: str,
        ticket_id: str,
        message_preview: Optional[str] = None,
    ):
        """Notify planner when root admin responds to their support ticket"""
        preview = ""
        if message_preview:
            preview = (
                f": {message_preview[:80]}..."
                if len(message_preview) > 80
                else f": {message_preview}"
            )

        return await self.create_notification(
            planner_id=planner_id,
            notification_type=PlannerNotificationTypes.SUPPORT_TICKET_RESPONSE,
            title=f"Support Response: {ticket_subject[:50]}",
            message=f"{responder_name} responded to ticket #{ticket_number}{preview}",
            wedding_id=None,
            metadata={
                "ticket_number": ticket_number,
                "ticket_id": ticket_id,
                "responder_name": responder_name,
                "ticket_subject": ticket_subject,
            },
            priority="high",
            action_url=build_support_inbox_path(
                "support_ticket",
                ticket_id=ticket_id,
            ),
        )


# Singleton instance
planner_notification_service = PlannerNotificationService()

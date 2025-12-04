from fastapi import HTTPException
from app.core.database import mongo
from app.services.email_service_resend import ResendEmailService
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.notifications_collection = mongo.db["notifications"]
        self.templates_collection = mongo.db["notification_templates"]
        self.users_collection = mongo.db["users"]  # Fixed: use admin_users collection
        self.email_service = ResendEmailService()

    async def create_notification(self, notification_data: dict, created_by: str) -> dict:
        """Create a new notification"""
        try:
            # Prepare notification document
            notification = {
                "_id": ObjectId(),
                "title": notification_data["title"],
                "message": notification_data["message"],
                "type": notification_data["type"],
                "target_audience": notification_data["target_audience"],
                "wedding_id": notification_data.get("wedding_id"),
                "user_id": notification_data.get("user_id"),
                "created_by": created_by,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "expiry_date": notification_data.get("expiry_date"),
                "is_dismissible": notification_data["is_dismissible"],
                "priority": notification_data["priority"],
                "status": "active",
                "read_by": [],
                "dismissed_by": []
            }

            # Insert notification
            result = await self.notifications_collection.insert_one(notification)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create notification")

            return {
                "id": str(result.inserted_id),
                "message": "Notification created successfully",
                "created_at": notification["created_at"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating notification: {str(e)}")

    async def get_notifications(self, page: int = 1, limit: int = 20, filters: dict = None) -> dict:
        """Get notifications with filtering and pagination"""
        try:
            # Build query
            query = {}
            if filters:
                if filters.get("type"):
                    query["type"] = filters["type"]
                if filters.get("target_audience"):
                    query["target_audience"] = filters["target_audience"]
                if filters.get("status"):
                    query["status"] = filters["status"]
                if filters.get("wedding_id"):
                    query["wedding_id"] = filters["wedding_id"]

            # Count total documents
            total = await self.notifications_collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit

            # Get notifications
            cursor = self.notifications_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            notifications = []

            async for notification in cursor:
                notification["id"] = str(notification["_id"])
                notification["_id"] = str(notification["_id"])
                notification["read_count"] = len(notification.get("read_by", []))
                notification["total_recipients"] = await self._count_target_audience(notification)
                notifications.append(notification)

            return {
                "notifications": notifications,
                "total": total,
                "page": page,
                "pages": pages
            }

        except Exception as e:
            logger.error(f"Error getting notifications: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving notifications: {str(e)}")

    async def get_notification(self, notification_id: str) -> dict:
        """Get specific notification by ID"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(notification_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid notification ID")

            notification = await self.notifications_collection.find_one({"_id": obj_id})
            if not notification:
                raise HTTPException(status_code=404, detail="Notification not found")

            notification["id"] = str(notification["_id"])
            notification["_id"] = str(notification["_id"])
            notification["read_count"] = len(notification.get("read_by", []))
            notification["total_recipients"] = await self._count_target_audience(notification)

            return notification

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving notification: {str(e)}")

    async def update_notification(self, notification_id: str, update_data: dict, updated_by: str) -> dict:
        """Update a notification"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(notification_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid notification ID")

            # Check if notification exists
            existing = await self.notifications_collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Notification not found")

            # Prepare update data
            update_data["updated_at"] = datetime.utcnow()
            update_data["updated_by"] = updated_by

            # Update notification
            result = await self.notifications_collection.update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Notification update failed")

            return {
                "message": "Notification updated successfully",
                "updated_fields": list(update_data.keys())
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating notification: {str(e)}")

    async def delete_notification(self, notification_id: str) -> dict:
        """Delete a notification"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(notification_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid notification ID")

            # Delete notification
            result = await self.notifications_collection.delete_one({"_id": obj_id})

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Notification not found")

            return {"message": "Notification deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error deleting notification: {str(e)}")

    async def send_notification(self, notification_id: str) -> dict:
        """Send notification to target audience"""
        try:
            notification = await self.get_notification(notification_id)

            if not getattr(self.email_service, "configured", False):
                raise HTTPException(status_code=503, detail="Email service not configured")

            recipients = await self._resolve_recipients(notification)
            if not recipients:
                raise HTTPException(status_code=400, detail="No active recipients found for this notification")

            dispatch_started = datetime.utcnow()
            sent = []
            failed = []

            for recipient in recipients:
                try:
                    html_content = self._render_notification_email(notification, recipient)
                    result = await self.email_service.send_email(
                        to_email=recipient["email"],
                        subject=notification["title"],
                        html_content=html_content,
                        email_type="admin_notification",
                    )

                    if result.get("success"):
                        sent.append(recipient["email"])
                    else:
                        failed.append({
                            "email": recipient["email"],
                            "error": result.get("error", "Unknown error"),
                        })
                except Exception as email_error:  # noqa: BLE001 - capture and record delivery issues
                    logger.error(
                        "Error sending notification email to %s: %s",
                        recipient.get("email"),
                        str(email_error),
                    )
                    failed.append({
                        "email": recipient.get("email"),
                        "error": str(email_error),
                    })

            delivery_summary = {
                "attempted": len(recipients),
                "sent": len(sent),
                "failed": len(failed),
                "last_attempt_at": dispatch_started,
            }
            if failed:
                delivery_summary["last_error"] = failed[-1].get("error")

            obj_id = ObjectId(notification_id)
            log_entry = {
                "attempted": len(recipients),
                "sent": len(sent),
                "failed": len(failed),
                "timestamp": dispatch_started,
            }
            if failed:
                # Store a trimmed view of failures to keep document size manageable
                log_entry["failed_recipients"] = failed[:10]

            await self.notifications_collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "status": "sent",
                        "sent_at": dispatch_started,
                        "updated_at": datetime.utcnow(),
                        "delivery_summary": delivery_summary,
                        "total_recipients": len(recipients),
                    },
                    "$push": {"delivery_logs": log_entry},
                },
            )

            message = "Notification sent successfully" if not failed else "Notification sent with partial failures"

            return {
                "message": message,
                "attempted": len(recipients),
                "sent": len(sent),
                "failed": len(failed),
                "failed_recipients": failed,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error sending notification: {str(e)}")

    async def get_user_notifications(self, user_email: str, user_role: str, page: int = 1, limit: int = 20, unread_only: bool = False) -> dict:
        """Get notifications for a specific user"""
        try:
            # Build query for user-specific notifications
            query = {
                "$and": [
                    # Check if notification is active/sent and not expired
                    {"status": {"$in": ["active", "sent"]}},
                    {
                        "$or": [
                            {"expiry_date": {"$exists": False}},
                            {"expiry_date": None},
                            {"expiry_date": {"$gt": datetime.utcnow()}}
                        ]
                    },
                    # Check target audience
                    {
                        "$or": [
                            {"target_audience": "all"},
                            {"target_audience": user_role + "s"},  # wedding_planner -> wedding_planners
                            {"user_id": user_email}  # Direct user targeting
                        ]
                    }
                ]
            }

            # Filter for unread notifications
            if unread_only:
                query["$and"].append({"read_by.user_id": {"$ne": user_email}})

            # Filter out dismissed notifications
            query["$and"].append({"dismissed_by.user_id": {"$ne": user_email}})

            # Count total documents
            total = await self.notifications_collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit

            # Get notifications
            cursor = self.notifications_collection.find(query).sort("priority_order", -1).sort("created_at", -1).skip(skip).limit(limit)
            notifications = []

            priority_order = {"urgent": 4, "high": 3, "medium": 2, "low": 1}

            async for notification in cursor:
                notification["id"] = str(notification["_id"])
                notification["_id"] = str(notification["_id"])

                # Check if user has read this notification
                notification["is_read"] = any(read["user_id"] == user_email for read in notification.get("read_by", []))

                # Add priority ordering
                notification["priority_order"] = priority_order.get(notification.get("priority", "medium"), 2)

                notifications.append(notification)

            return {
                "notifications": notifications,
                "total": total,
                "page": page,
                "pages": pages
            }

        except Exception as e:
            logger.error(f"Error getting user notifications: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving user notifications: {str(e)}")

    async def mark_notification_read(self, notification_id: str, user_id: str) -> dict:
        """Mark notification as read by user"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(notification_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid notification ID")

            # Check if already read by this user
            existing_read = await self.notifications_collection.find_one({
                "_id": obj_id,
                "read_by.user_id": user_id
            })

            if existing_read:
                return {"message": "Notification already marked as read"}

            # Mark as read
            result = await self.notifications_collection.update_one(
                {"_id": obj_id},
                {
                    "$push": {
                        "read_by": {
                            "user_id": user_id,
                            "read_at": datetime.utcnow()
                        }
                    }
                }
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Notification not found")

            return {"message": "Notification marked as read"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error marking notification as read: {str(e)}")

    async def dismiss_notification(self, notification_id: str, user_id: str) -> dict:
        """Dismiss notification for user"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(notification_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid notification ID")

            # Check if notification is dismissible
            notification = await self.notifications_collection.find_one({"_id": obj_id})
            if not notification:
                raise HTTPException(status_code=404, detail="Notification not found")

            if not notification.get("is_dismissible", True):
                raise HTTPException(status_code=400, detail="Notification cannot be dismissed")

            # Check if already dismissed by this user
            existing_dismissed = await self.notifications_collection.find_one({
                "_id": obj_id,
                "dismissed_by.user_id": user_id
            })

            if existing_dismissed:
                return {"message": "Notification already dismissed"}

            # Mark as dismissed
            result = await self.notifications_collection.update_one(
                {"_id": obj_id},
                {
                    "$push": {
                        "dismissed_by": {
                            "user_id": user_id,
                            "dismissed_at": datetime.utcnow()
                        }
                    }
                }
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Notification not found")

            return {"message": "Notification dismissed"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error dismissing notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error dismissing notification: {str(e)}")

    async def get_user_notification_count(self, user_email: str, user_role: str) -> dict:
        """Get notification count for user"""
        try:
            # Query for user notifications
            query = {
                "$and": [
                    {"status": {"$in": ["active", "sent"]}},
                    {
                        "$or": [
                            {"expiry_date": {"$exists": False}},
                            {"expiry_date": None},
                            {"expiry_date": {"$gt": datetime.utcnow()}}
                        ]
                    },
                    {
                        "$or": [
                            {"target_audience": "all"},
                            {"target_audience": user_role + "s"},
                            {"user_id": user_email}
                        ]
                    },
                    {"dismissed_by.user_id": {"$ne": user_email}}
                ]
            }

            # Count total notifications
            total = await self.notifications_collection.count_documents(query)

            # Count unread notifications
            unread_query = query.copy()
            unread_query["$and"].append({"read_by.user_id": {"$ne": user_email}})
            unread = await self.notifications_collection.count_documents(unread_query)

            return {
                "total": total,
                "unread": unread,
                "read": total - unread
            }

        except Exception as e:
            logger.error(f"Error getting notification count: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting notification count: {str(e)}")

    async def _resolve_recipients(self, notification: dict) -> List[Dict[str, Optional[str]]]:
        """Resolve the actual recipient list for the notification."""
        target = notification.get("target_audience", "all")
        recipients: List[Dict[str, Optional[str]]] = []
        seen_emails = set()

        targeted_user_id = notification.get("user_id")
        if targeted_user_id:
            user = await self._find_user_by_identifier(targeted_user_id)
            if user and user.get("email"):
                formatted = self._format_user_contact(user)
                recipients.append(formatted)
                return recipients

        base_query = {
            "is_active": True,
            "email": {"$exists": True, "$ne": None, "$ne": ""},
        }

        if target == "all":
            cursor = self.users_collection.find(base_query)
        elif target == "wedding_planners":
            cursor = self.users_collection.find({**base_query, "role": "wedding_planner"})
        elif target == "vendors":
            cursor = self.users_collection.find({**base_query, "role": "vendor"})
        else:
            cursor = []

        async for user in cursor:
            email = user.get("email")
            if not email or email in seen_emails:
                continue

            formatted = self._format_user_contact(user)
            recipients.append(formatted)
            seen_emails.add(email)

        return recipients

    async def _find_user_by_identifier(self, identifier: str) -> Optional[Dict]:
        """Locate a user by ObjectId or email address."""
        if not identifier:
            return None

        try:
            if ObjectId.is_valid(identifier):
                user = await self.users_collection.find_one({"_id": ObjectId(identifier)})
                if user:
                    return user
        except Exception as exc:  # noqa: BLE001 - capture lookup issues without aborting send
            logger.debug("Failed ObjectId lookup for user identifier %s: %s", identifier, str(exc))

        return await self.users_collection.find_one({"email": identifier})

    @staticmethod
    def _format_user_contact(user: Dict) -> Dict[str, Optional[str]]:
        """Prepare a consistent contact payload for recipients."""
        name_parts = [user.get("first_name"), user.get("last_name")]
        full_name = " ".join(part for part in name_parts if part).strip()
        if not full_name:
            full_name = user.get("full_name") or user.get("name") or user.get("company_name")
        if not full_name and user.get("email"):
            full_name = user["email"].split("@")[0]

        return {
            "email": user.get("email"),
            "name": full_name,
            "role": user.get("role"),
            "user_id": str(user.get("_id")) if user.get("_id") is not None else None,
        }

    @staticmethod
    def _render_notification_email(notification: dict, recipient: Dict[str, Optional[str]]) -> str:
        """Generate a glass-inspired HTML email for the notification."""
        headline = notification.get("title", "Platform Update")
        body = notification.get("message", "")
        recipient_name = recipient.get("name") or "there"

        return f"""
        <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background-color:#f4f5f7;padding:32px 0;\">
          <tr>
            <td align=\"center\" style=\"padding:0 16px;\">
              <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:640px;background:linear-gradient(135deg,rgba(255,255,255,0.72),rgba(255,255,255,0.45));backdrop-filter:blur(18px);border-radius:28px;border:1px solid rgba(255,255,255,0.6);box-shadow:0 30px 60px rgba(15,23,42,0.12);overflow:hidden;\">
                <tr>
                  <td style=\"padding:32px 40px 16px;font-family:'SF Pro Display','Helvetica Neue',Helvetica,Arial,sans-serif;color:#0f172a;\">
                    <p style=\"margin:0;font-size:14px;letter-spacing:0.08em;text-transform:uppercase;color:rgba(15,23,42,0.56);\">Special Wedding Platform</p>
                    <h1 style=\"margin:12px 0 16px;font-size:28px;font-weight:600;line-height:1.25;\">{headline}</h1>
                    <p style=\"margin:0 0 24px;font-size:16px;line-height:1.6;color:rgba(15,23,42,0.72);\">Hi {recipient_name},</p>
                    <div style=\"font-size:16px;line-height:1.7;color:rgba(15,23,42,0.78);white-space:pre-wrap;\">{body}</div>
                  </td>
                </tr>
                <tr>
                  <td style=\"padding:0 40px 32px;font-family:'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;font-size:14px;line-height:1.6;color:rgba(15,23,42,0.56);\">
                    <hr style=\"border:none;height:1px;background:linear-gradient(90deg,rgba(255,255,255,0),rgba(255,255,255,0.8),rgba(255,255,255,0));margin:0 0 20px;\" />
                    <p style=\"margin:0 0 12px;\">You are receiving this message because your account has access to platform announcements.</p>
                    <p style=\"margin:0;color:rgba(15,23,42,0.45);\">© {datetime.utcnow().year} The Special Wedding. All rights reserved.</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
        """

    async def _count_target_audience(self, notification: dict) -> int:
        """Count the number of users in the target audience"""
        try:
            target = notification["target_audience"]

            if target == "all":
                return await self.users_collection.count_documents({"is_active": True})
            elif target == "wedding_planners":
                return await self.users_collection.count_documents({"role": "wedding_planner", "is_active": True})
            elif target == "vendors":
                return await self.users_collection.count_documents({"role": "vendor", "is_active": True})
            elif notification.get("user_id"):
                return 1  # Targeted to specific user
            else:
                return 0

        except Exception as e:
            logger.error(f"Error counting target audience: {str(e)}")
            return 0

    # ==================== NOTIFICATION TEMPLATE METHODS ====================

    async def create_template(self, template_data: dict, created_by: str) -> dict:
        """Create a new notification template"""
        try:
            template = {
                "_id": ObjectId(),
                "name": template_data["name"],
                "subject": template_data["subject"],
                "content": template_data["content"],
                "type": template_data["type"],
                "category": template_data.get("category", "general"),
                "variables": template_data.get("variables", []),
                "is_active": template_data.get("is_active", True),
                "created_by": created_by,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            result = await self.templates_collection.insert_one(template)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create template")

            return {
                "id": str(result.inserted_id),
                "message": "Template created successfully",
                "created_at": template["created_at"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")

    async def get_templates(self, page: int = 1, limit: int = 50, filters: dict = None) -> dict:
        """Get notification templates with filtering and pagination"""
        try:
            query = {}
            if filters:
                if filters.get("type"):
                    query["type"] = filters["type"]
                if filters.get("category"):
                    query["category"] = filters["category"]

            total = await self.templates_collection.count_documents(query)
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit

            cursor = self.templates_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            templates = []

            async for template in cursor:
                template["id"] = str(template["_id"])
                template["_id"] = str(template["_id"])
                templates.append(template)

            return {
                "templates": templates,
                "total": total,
                "page": page,
                "pages": pages
            }

        except Exception as e:
            logger.error(f"Error getting templates: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")

    async def get_template(self, template_id: str) -> dict:
        """Get specific template by ID"""
        try:
            try:
                obj_id = ObjectId(template_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid template ID")

            template = await self.templates_collection.find_one({"_id": obj_id})
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            template["id"] = str(template["_id"])
            template["_id"] = str(template["_id"])

            return template

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving template: {str(e)}")

    async def update_template(self, template_id: str, update_data: dict, updated_by: str) -> dict:
        """Update a notification template"""
        try:
            try:
                obj_id = ObjectId(template_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid template ID")

            existing = await self.templates_collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Template not found")

            update_data["updated_at"] = datetime.utcnow()
            update_data["updated_by"] = updated_by

            result = await self.templates_collection.update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Template update failed")

            return {
                "message": "Template updated successfully",
                "updated_fields": list(update_data.keys())
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating template: {str(e)}")

    async def delete_template(self, template_id: str) -> dict:
        """Delete a notification template"""
        try:
            try:
                obj_id = ObjectId(template_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid template ID")

            result = await self.templates_collection.delete_one({"_id": obj_id})

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Template not found")

            return {"message": "Template deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error deleting template: {str(e)}")
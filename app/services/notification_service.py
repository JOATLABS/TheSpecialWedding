from fastapi import HTTPException
from app.core.database import mongo
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.notifications_collection = mongo.db["notifications"]
        self.users_collection = mongo.db["users"]

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
            result = self.notifications_collection.insert_one(notification)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create notification")

            # If this is a root admin notification, queue email
            if notification_data["target_audience"] == "root_admin":
                await self._queue_admin_email(notification_data)

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
            total = self.notifications_collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit

            # Get notifications
            cursor = self.notifications_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            notifications = []

            for notification in cursor:
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

            notification = self.notifications_collection.find_one({"_id": obj_id})
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
            existing = self.notifications_collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Notification not found")

            # Prepare update data
            update_data["updated_at"] = datetime.utcnow()
            update_data["updated_by"] = updated_by

            # Update notification
            result = self.notifications_collection.update_one(
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
            result = self.notifications_collection.delete_one({"_id": obj_id})

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Notification not found")

            return {"message": "Notification deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error deleting notification: {str(e)}")

    async def send_notification(self, notification_id: str) -> dict:
        """Send notification to target audience via email"""
        try:
            # Get notification
            notification = await self.get_notification(notification_id)

            # Get target audience
            target_audience = notification["target_audience"]
            sent_count = 0
            failed_count = 0

            # Get recipients based on target audience
            recipients = []
            if target_audience == "all":
                # Get all active users
                users_cursor = self.users_collection.find({"is_active": True, "email": {"$exists": True}})
                recipients = [{"email": user["email"], "role": user.get("role", "user")} for user in users_cursor]
            elif target_audience == "wedding_planners":
                # Get wedding planners only
                users_cursor = self.users_collection.find({"role": "wedding_planner", "is_active": True, "email": {"$exists": True}})
                recipients = [{"email": user["email"], "role": "wedding_planner"} for user in users_cursor]
            elif target_audience == "vendors":
                # Get vendors only
                users_cursor = self.users_collection.find({"role": "vendor", "is_active": True, "email": {"$exists": True}})
                recipients = [{"email": user["email"], "role": "vendor"} for user in users_cursor]
            elif target_audience == "root_admin":
                # Send to root admin only - this was already handled in create_notification
                pass
            elif notification.get("user_id"):
                # Send to specific user
                user = self.users_collection.find_one({"email": notification["user_id"], "is_active": True})
                if user:
                    recipients = [{"email": user["email"], "role": user.get("role", "user")}]

            # Send emails to recipients using Celery task queue
            if recipients:
                from app.tasks.email_tasks import send_email_notification
                from app.services.email_template_service import EmailTemplateService
                from app.models.email_template import TemplateType

                # Try to get appropriate email template
                template_service = EmailTemplateService()
                notification_type = notification.get("type", "info")

                # Map notification type to template type
                if notification_type == "success":
                    template_type = TemplateType.GENERAL
                elif notification_type == "warning":
                    template_type = TemplateType.SYSTEM_ALERT
                elif notification_type == "error":
                    template_type = TemplateType.SYSTEM_ALERT
                else:
                    template_type = TemplateType.GENERAL

                # Try to get template
                try:
                    template = await template_service.get_template_by_type(template_type)
                except:
                    template = None

                # Prepare template data
                template_data = {
                    "title": notification["title"],
                    "message": notification["message"],
                    "type": notification_type,
                    "priority": notification.get("priority", "medium"),
                    "admin_link": "https://www.thespecialwedding.com/admin"
                }

                for recipient in recipients:
                    try:
                        if template:
                            # Use database template
                            html_content = template_service._render_template(template["html_content"], template_data)
                            subject = template_service._render_template(template["subject"], template_data)
                        else:
                            # Generate simple fallback HTML
                            subject = f"🔔 {notification['title']}"
                            html_content = self._generate_simple_notification_email(
                                notification["title"],
                                notification["message"],
                                notification_type,
                                notification.get("priority", "medium")
                            )

                        # Queue email via Celery
                        send_email_notification.apply_async(
                            args=[
                                recipient["email"],
                                subject,
                                html_content,
                                f"notification_{notification_type}",
                                "noreply@thespecialwedding.com",
                                "TheSpecialWedding Platform"
                            ],
                            kwargs={
                                "metadata": {
                                    "notification_id": notification_id,
                                    "recipient_role": recipient["role"],
                                    "priority": notification.get("priority", "medium")
                                },
                                "template_id": template["id"] if template else None
                            }
                        )
                        sent_count += 1

                    except Exception as e:
                        logger.error(f"Failed to queue email for {recipient['email']}: {str(e)}")
                        failed_count += 1

            # Mark notification as sent
            obj_id = ObjectId(notification_id)
            self.notifications_collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "status": "sent",
                        "sent_at": datetime.utcnow(),
                        "email_sent_count": sent_count,
                        "email_failed_count": failed_count
                    }
                }
            )

            logger.info(f"Notification {notification_id} sent to {sent_count} recipients, {failed_count} failed")

            return {
                "message": "Notification sent successfully",
                "recipients": len(recipients),
                "emails_queued": sent_count,
                "emails_failed": failed_count
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error sending notification: {str(e)}")

    def _generate_simple_notification_email(self, title: str, message: str, notification_type: str, priority: str) -> str:
        """Generate simple fallback notification email HTML"""
        # Choose color based on notification type
        type_colors = {
            "info": "#3b82f6",
            "success": "#10b981",
            "warning": "#f59e0b",
            "error": "#ef4444"
        }
        color = type_colors.get(notification_type, "#3b82f6")

        # Choose icon based on type
        type_icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌"
        }
        icon = type_icons.get(notification_type, "🔔")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .header {{ background: {color}; color: white; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
                .content {{ padding: 30px; }}
                .message {{ background: #f9fafb; border-left: 4px solid {color}; padding: 20px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
                .priority {{ display: inline-block; padding: 4px 8px; background: {color}; color: white; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; background: #f9fafb; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{icon} {title}</h1>
                    <p>TheSpecialWedding Platform</p>
                </div>
                <div class="content">
                    <div class="message">
                        <p>{message}</p>
                    </div>
                    <p><span class="priority">Priority: {priority}</span></p>
                    <p><a href="https://www.thespecialwedding.com/admin" style="color: {color};">Go to Admin Panel</a></p>
                </div>
                <div class="footer">
                    <p>© JOAT Labs - TheSpecialWedding Platform</p>
                </div>
            </div>
        </body>
        </html>
        """

    async def get_user_notifications(self, user_email: str, user_role: str, page: int = 1, limit: int = 20, unread_only: bool = False) -> dict:
        """Get notifications for a specific user"""
        try:
            # Build query for user-specific notifications
            query = {
                "$and": [
                    # Check if notification is active and not expired
                    {"status": "active"},
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
            total = self.notifications_collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit

            # Get notifications
            cursor = self.notifications_collection.find(query).sort("priority_order", -1).sort("created_at", -1).skip(skip).limit(limit)
            notifications = []

            priority_order = {"urgent": 4, "high": 3, "medium": 2, "low": 1}

            for notification in cursor:
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
            existing_read = self.notifications_collection.find_one({
                "_id": obj_id,
                "read_by.user_id": user_id
            })

            if existing_read:
                return {"message": "Notification already marked as read"}

            # Mark as read
            result = self.notifications_collection.update_one(
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
            notification = self.notifications_collection.find_one({"_id": obj_id})
            if not notification:
                raise HTTPException(status_code=404, detail="Notification not found")

            if not notification.get("is_dismissible", True):
                raise HTTPException(status_code=400, detail="Notification cannot be dismissed")

            # Check if already dismissed by this user
            existing_dismissed = self.notifications_collection.find_one({
                "_id": obj_id,
                "dismissed_by.user_id": user_id
            })

            if existing_dismissed:
                return {"message": "Notification already dismissed"}

            # Mark as dismissed
            result = self.notifications_collection.update_one(
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
                    {"status": "active"},
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
            total = self.notifications_collection.count_documents(query)

            # Count unread notifications
            unread_query = query.copy()
            unread_query["$and"].append({"read_by.user_id": {"$ne": user_email}})
            unread = self.notifications_collection.count_documents(unread_query)

            return {
                "total": total,
                "unread": unread,
                "read": total - unread
            }

        except Exception as e:
            logger.error(f"Error getting notification count: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting notification count: {str(e)}")

    async def _count_target_audience(self, notification: dict) -> int:
        """Count the number of users in the target audience"""
        try:
            target = notification["target_audience"]

            if target == "all":
                return self.users_collection.count_documents({"is_active": True})
            elif target == "wedding_planners":
                return self.users_collection.count_documents({"role": "wedding_planner", "is_active": True})
            elif target == "vendors":
                return self.users_collection.count_documents({"role": "vendor", "is_active": True})
            elif notification.get("user_id"):
                return 1  # Targeted to specific user
            else:
                return 0

        except Exception as e:
            logger.error(f"Error counting target audience: {str(e)}")
            return 0

    async def _queue_admin_email(self, notification_data: dict):
        """Queue admin email notification"""
        try:
            from app.services.email_service_resend import ResendEmailService

            email_service = ResendEmailService()

            # Determine notification type for email template
            notification_type = notification_data.get("source", "general")
            if notification_type == "contact_form":
                notification_type = "contact_form"
            elif notification_type == "new_user":
                notification_type = "new_user"
            elif notification_type == "payment":
                notification_type = "payment"
            elif notification_data.get("type") == "error":
                notification_type = "system_alert"
            else:
                notification_type = "general"

            # Extract metadata from notification
            metadata = {}
            if 'submission_id' in notification_data:
                metadata["submission_id"] = notification_data.get("submission_id")
            if 'email' in notification_data:
                metadata["email"] = notification_data.get("email")
            if 'name' in notification_data:
                metadata["name"] = notification_data.get("name")
            if 'company' in notification_data:
                metadata["company"] = notification_data.get("company")
            if 'phone' in notification_data:
                metadata["phone"] = notification_data.get("phone")
            if 'message' in notification_data:
                metadata["message"] = notification_data.get("message")

            # Queue the admin notification email
            result = email_service.send_admin_notification(
                notification_type=notification_type,
                subject=notification_data["title"],
                content=notification_data["message"],
                metadata=metadata
            )

            if result.get("success"):
                logger.info(f"Admin email queued successfully for notification type: {notification_type}")
            else:
                logger.error(f"Failed to queue admin email: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error queuing admin email: {str(e)}")
            # Don't raise exception - notification should still be created even if email fails
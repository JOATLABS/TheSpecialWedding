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

    async def notify_form_response(self, form_id: str, response_id: str, response_data: dict, form_data: dict) -> dict:
        """Create notification for new form response"""
        try:
            from app.core.database import get_database

            db = get_database()
            forms_collection = db["forms"]
            form_responses_collection = db["form_responses"]
            users_collection = db["users"]

            # Get form details
            form = forms_collection.find_one({"_id": form_id})
            if not form:
                logger.error(f"Form {form_id} not found for notification")
                return {"success": False, "error": "Form not found"}

            # Get form owner (wedding planner)
            form_owner_email = form.get("created_by")
            if not form_owner_email:
                logger.error(f"Form {form_id} has no owner for notification")
                return {"success": False, "error": "Form owner not found"}

            # Check notification preferences for this user
            preferences = await self.get_notification_preferences(form_owner_email)
            if not preferences.get("email_enabled", True):
                logger.info(f"Email notifications disabled for {form_owner_email}")
                return {"success": True, "message": "Notifications disabled"}

            # Check if instant notifications or if this form is in their list
            if preferences.get("digest_frequency") != "instant":
                if form_id not in preferences.get("forms", []):
                    logger.info(f"Form {form_id} not in notification list for {form_owner_email}")
                    return {"success": True, "message": "Form not in notification list"}

            # Get response details
            submitted_by_name = response_data.get("submitted_by_name", "Anonymous")
            submitted_by_email = response_data.get("submitted_by_email", "Not provided")

            # Get total response count for this form
            total_responses = form_responses_collection.count_documents({"form_id": form_id})

            # Create in-app notification
            notification_data = {
                "title": f"New Response: {form['settings']['title']}",
                "message": f"{submitted_by_name} has submitted a response to your form '{form['settings']['title']}'",
                "type": "form_response",
                "target_audience": "specific_user",
                "user_id": form_owner_email,
                "is_dismissible": True,
                "priority": "medium",
                "form_id": form_id,
                "response_id": response_id,
                "metadata": {
                    "form_name": form["settings"]["title"],
                    "submitted_by_name": submitted_by_name,
                    "submitted_by_email": submitted_by_email,
                    "total_responses": total_responses,
                    "response_url": f"/admin/forms/{form_id}/responses"
                }
            }

            # Create the in-app notification
            await self.create_notification(notification_data, "system")

            # Send email notification
            await self._send_form_response_email(
                form_owner_email=form_owner_email,
                form_data=form,
                response_data=response_data,
                total_responses=total_responses,
                response_id=response_id
            )

            # Mark response as notification sent
            form_responses_collection.update_one(
                {"_id": response_id},
                {
                    "$set": {
                        "notification_sent": True,
                        "notification_sent_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Form response notification sent for form {form_id} to {form_owner_email}")

            return {
                "success": True,
                "message": "Notification sent successfully",
                "email_sent": True
            }

        except Exception as e:
            logger.error(f"Error sending form response notification: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _send_form_response_email(self, form_owner_email: str, form_data: dict, response_data: dict, total_responses: int, response_id: str):
        """Send email notification for form response"""
        try:
            from app.services.email_service_resend import ResendEmailService

            email_service = ResendEmailService()

            # Generate email content
            form_title = form_data["settings"]["title"]
            submitted_by_name = response_data.get("submitted_by_name", "Anonymous")
            submitted_by_email = response_data.get("submitted_by_email", "Not provided")
            submitted_at = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p")

            # Get first few response fields for preview
            response_preview = self._generate_response_preview(form_data.get("fields", []), response_data.get("responses", {}))

            subject = f"📝 New Response: {form_title}"

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>New Form Response</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f8fafc; }}
                    .container {{ max-width: 600px; margin: 20px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                    .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
                    .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
                    .content {{ padding: 30px; }}
                    .form-info {{ background: #f1f5f9; border-left: 4px solid #667eea; padding: 20px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
                    .response-meta {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
                    .meta-item {{ text-align: center; padding: 15px; background: #f8fafc; border-radius: 8px; }}
                    .meta-item strong {{ display: block; font-size: 18px; color: #667eea; margin-bottom: 5px; }}
                    .response-preview {{ background: #fafbfc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin: 20px 0; }}
                    .response-preview h3 {{ margin-top: 0; color: #334155; }}
                    .field-preview {{ margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #e2e8f0; }}
                    .field-preview:last-child {{ border-bottom: none; margin-bottom: 0; }}
                    .field-label {{ font-weight: 600; color: #475569; margin-bottom: 5px; }}
                    .field-value {{ color: #64748b; }}
                    .action-button {{ display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
                    .action-button:hover {{ background: #5a67d8; }}
                    .footer {{ text-align: center; padding: 20px; color: #64748b; font-size: 14px; background: #f8fafc; }}
                    .footer a {{ color: #667eea; text-decoration: none; }}

                    @media (max-width: 600px) {{
                        .container {{ margin: 10px; border-radius: 8px; }}
                        .header {{ padding: 20px; }}
                        .content {{ padding: 20px; }}
                        .response-meta {{ grid-template-columns: 1fr; gap: 10px; }}
                        .action-button {{ display: block; text-align: center; }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📝 New Form Response</h1>
                        <p>You've received a new response!</p>
                    </div>

                    <div class="content">
                        <div class="form-info">
                            <h3 style="margin-top: 0; color: #334155;">Form: {form_title}</h3>
                            <p style="margin-bottom: 0; color: #64748b;">A new response has been submitted and is ready for your review.</p>
                        </div>

                        <div class="response-meta">
                            <div class="meta-item">
                                <strong>{submitted_by_name}</strong>
                                <span>{submitted_by_email}</span>
                            </div>
                            <div class="meta-item">
                                <strong>{total_responses}</strong>
                                <span>Total Responses</span>
                            </div>
                        </div>

                        <div class="response-preview">
                            <h3>Response Preview</h3>
                            {response_preview}
                        </div>

                        <div style="text-align: center;">
                            <a href="https://app.thespecialwedding.com/admin/forms/{form_data['_id']}/responses"
                               class="action-button">View Full Response</a>
                        </div>

                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 14px; color: #64748b;">
                            <p><strong>Submitted:</strong> {submitted_at}</p>
                            <p><strong>Response ID:</strong> {response_id}</p>
                        </div>
                    </div>

                    <div class="footer">
                        <p>© TheSpecialWedding Platform - Wedding Planning Made Simple</p>
                        <p>
                            <a href="https://app.thespecialwedding.com/admin/settings/notifications">
                                Manage notification preferences
                            </a>
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Send the email
            result = email_service.send_email(
                to_email=form_owner_email,
                subject=subject,
                html_content=html_content
            )

            if result.get("success"):
                logger.info(f"Form response email sent to {form_owner_email}")
            else:
                logger.error(f"Failed to send form response email: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error sending form response email: {str(e)}")

    def _generate_response_preview(self, fields: list, responses: dict) -> str:
        """Generate HTML preview of form responses"""
        try:
            preview_html = ""

            # Show first 3 fields only for preview
            preview_fields = fields[:3] if len(fields) > 3 else fields

            for field in preview_fields:
                field_id = field.get("id", "")
                field_label = field.get("label", "Unknown Field")
                field_value = responses.get(field_id, "No response")

                # Format different field types
                if field.get("type") == "rating" and isinstance(field_value, (int, float)):
                    stars = "★" * int(field_value) + "☆" * (5 - int(field_value))
                    field_value = f"{stars} ({field_value}/5)"
                elif field.get("type") == "scale" and isinstance(field_value, (int, float)):
                    field_value = f"{field_value}/10"
                elif isinstance(field_value, list):
                    field_value = ", ".join(str(v) for v in field_value)
                elif len(str(field_value)) > 100:
                    field_value = str(field_value)[:100] + "..."

                preview_html += f"""
                <div class="field-preview">
                    <div class="field-label">{field_label}</div>
                    <div class="field-value">{field_value}</div>
                </div>
                """

            if len(fields) > 3:
                preview_html += f"""
                <div style="text-align: center; color: #64748b; font-style: italic; margin-top: 15px;">
                    ... and {len(fields) - 3} more fields
                </div>
                """

            return preview_html if preview_html else "<p>No response data available</p>"

        except Exception as e:
            logger.error(f"Error generating response preview: {str(e)}")
            return "<p>Error loading response preview</p>"

    async def get_notification_preferences(self, user_email: str) -> dict:
        """Get user's notification preferences"""
        try:
            from app.core.database import get_database

            db = get_database()
            preferences_collection = db["notification_preferences"]

            preferences = preferences_collection.find_one({"user_email": user_email})

            if not preferences:
                # Return default preferences
                return {
                    "email_enabled": True,
                    "instant_notifications": True,
                    "digest_frequency": "instant",
                    "forms": []
                }

            return {
                "email_enabled": preferences.get("email_enabled", True),
                "instant_notifications": preferences.get("instant_notifications", True),
                "digest_frequency": preferences.get("digest_frequency", "instant"),
                "forms": preferences.get("forms", [])
            }

        except Exception as e:
            logger.error(f"Error getting notification preferences: {str(e)}")
            return {
                "email_enabled": True,
                "instant_notifications": True,
                "digest_frequency": "instant",
                "forms": []
            }

    async def update_notification_preferences(self, user_email: str, preferences: dict) -> dict:
        """Update user's notification preferences"""
        try:
            from app.core.database import get_database

            db = get_database()
            preferences_collection = db["notification_preferences"]

            # Prepare preferences document
            preference_doc = {
                "user_email": user_email,
                "email_enabled": preferences.get("email_enabled", True),
                "instant_notifications": preferences.get("instant_notifications", True),
                "digest_frequency": preferences.get("digest_frequency", "instant"),
                "forms": preferences.get("forms", []),
                "updated_at": datetime.utcnow()
            }

            # Upsert preferences
            result = preferences_collection.update_one(
                {"user_email": user_email},
                {
                    "$set": preference_doc,
                    "$setOnInsert": {"created_at": datetime.utcnow()}
                },
                upsert=True
            )

            logger.info(f"Notification preferences updated for {user_email}")

            return {
                "success": True,
                "message": "Preferences updated successfully"
            }

        except Exception as e:
            logger.error(f"Error updating notification preferences: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating preferences: {str(e)}")

    async def get_unread_form_response_count(self, user_email: str) -> int:
        """Get count of unread form responses for user"""
        try:
            from app.core.database import get_database

            db = get_database()
            form_responses_collection = db["form_responses"]
            forms_collection = db["forms"]

            # Get forms owned by this user
            user_forms = forms_collection.find({"created_by": user_email}, {"_id": 1})
            form_ids = [form["_id"] for form in user_forms]

            if not form_ids:
                return 0

            # Count unreviewed responses for user's forms
            unread_count = form_responses_collection.count_documents({
                "form_id": {"$in": form_ids},
                "is_reviewed": {"$ne": True}
            })

            return unread_count

        except Exception as e:
            logger.error(f"Error getting unread form response count: {str(e)}")
            return 0
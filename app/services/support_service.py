from fastapi import HTTPException, UploadFile
from app.core.database import mongo
from typing import Dict, Optional, Any
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from app.utils.serializers import serialize_mongo_doc
import secrets
import string
import logging
import os
import asyncio

logger = logging.getLogger(__name__)

# Root admin email for support notifications
# Default fallback uses .io domain (SAAS platform) - should be configured via env var
ROOT_ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "admin@thespecialwedding.io")


class SupportService:
    def __init__(self):
        self.tickets_collection = mongo.db["support_tickets"]
        self.users_collection = mongo.get_users_collection()

    def generate_ticket_number(self) -> str:
        """Generate a unique ticket number"""
        prefix = "TKT"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
        return f"{prefix}-{timestamp}-{random_suffix}"

    async def create_ticket(self, ticket_data: dict, created_by: str) -> dict:
        """Create a new support ticket"""
        try:
            # Generate unique ticket number
            ticket_number = self.generate_ticket_number()

            # Ensure unique ticket number
            while await self.tickets_collection.find_one({"ticket_number": ticket_number}):
                ticket_number = self.generate_ticket_number()

            # Prepare ticket document
            ticket = {
                "_id": ObjectId(),
                "ticket_number": ticket_number,
                "subject": ticket_data["subject"],
                "description": ticket_data["description"],
                "priority": ticket_data["priority"],
                "category": ticket_data["category"],
                "status": "open",
                "created_by": created_by,
                "assigned_to": None,
                "wedding_id": ticket_data.get("wedding_id"),
                "attachments": ticket_data.get("attachments", []),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "resolved_at": None,
                "comments": [],
                "tags": [],
                "satisfaction_rating": None
            }

            # Insert ticket
            result = await self.tickets_collection.insert_one(ticket)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create ticket")

            logger.info(f"Support ticket {ticket_number} created successfully by {created_by}")

            # Log activity for planner dashboard (activity_logs collection)
            try:
                activity_logs_collection = mongo.db["activity_logs"]
                await activity_logs_collection.insert_one({
                    "type": "support_ticket_created",
                    "message": f"Support ticket created: {ticket['subject'][:50]}",
                    "timestamp": datetime.now(timezone.utc),
                    "created_at": datetime.now(timezone.utc),
                    "planner_email": created_by,
                    "actor_email": created_by,
                    "metadata": {
                        "ticket_number": ticket_number,
                        "ticket_id": str(result.inserted_id),
                        "priority": ticket['priority'],
                        "category": ticket['category']
                    }
                })
                logger.info(f"Activity logged for support ticket {ticket_number}")
            except Exception as activity_error:
                logger.error(f"Failed to log activity for ticket {ticket_number}: {str(activity_error)}")
                # Don't fail ticket creation if activity logging fails

            # Create in-app notification for ROOT_ADMIN
            try:
                from app.services.notification_service import NotificationService
                notification_service = NotificationService()
                await notification_service.create_notification(
                    notification_data={
                        "title": f"New Support Ticket: {ticket['subject'][:50]}",
                        "message": f"Ticket #{ticket_number} from {created_by} - Priority: {ticket['priority'].upper()}",
                        "type": "support_ticket",
                        "target_audience": "root_admin",
                        "is_dismissible": True,
                        "priority": "high" if ticket['priority'] in ['urgent', 'high'] else "medium"
                    },
                    created_by="system"
                )
                logger.info(f"In-app notification created for support ticket {ticket_number}")
            except Exception as notif_error:
                logger.error(f"Failed to create notification for ticket {ticket_number}: {str(notif_error)}")
                # Don't fail ticket creation if notification fails

            # Send email notification to root admin
            try:
                await self._send_new_ticket_notification(ticket, created_by)
            except Exception as email_error:
                logger.error(f"Failed to send email notification for ticket {ticket_number}: {str(email_error)}")
                # Don't fail the ticket creation if email fails

            return {
                "id": str(result.inserted_id),
                "ticket_number": ticket_number,
                "message": "Support ticket created successfully",
                "created_at": ticket["created_at"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating ticket: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating ticket: {str(e)}")

    async def get_tickets(self, page: int = 1, limit: int = 20, filters: Optional[Dict[str, Any]] = None) -> dict:
        """Get tickets with filtering and pagination"""
        try:
            # Build query
            query = {}
            if filters:
                for key, value in filters.items():
                    if value is not None:
                        query[key] = value

            # Count total documents
            total = await self.tickets_collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit

            # Get tickets with sorting (priority + created date)
            priority_order = {"urgent": 4, "high": 3, "medium": 2, "low": 1}

            cursor = self.tickets_collection.find(query).sort([
                ("status", 1),  # Open tickets first
                ("priority", -1),  # High priority first
                ("created_at", -1)  # Newest first
            ]).skip(skip).limit(limit)

            tickets = []
            async for ticket in cursor:
                ticket["id"] = str(ticket["_id"])
                ticket["_id"] = str(ticket["_id"])

                # Add computed fields
                ticket["comment_count"] = len(ticket.get("comments", []))
                ticket["is_overdue"] = self._is_ticket_overdue(ticket)
                ticket["priority_order"] = priority_order.get(ticket.get("priority", "medium"), 2)

                # Get creator info
                creator = await self.users_collection.find_one(
                    {"email": ticket["created_by"]},
                    {"first_name": 1, "last_name": 1, "company_name": 1}
                )
                ticket["creator_info"] = creator if creator else {"first_name": "Unknown", "last_name": "User"}

                tickets.append(ticket)

            return serialize_mongo_doc({
                "tickets": tickets,
                "total": total,
                "page": page,
                "pages": pages
            })

        except Exception as e:
            logger.error(f"Error getting tickets: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving tickets: {str(e)}")

    async def get_ticket(self, ticket_id: str, current_user) -> dict:
        """Get specific ticket by ID"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(ticket_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            ticket = await self.tickets_collection.find_one({"_id": obj_id})
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")

            # Check permissions - users can only see their own tickets unless they're ROOT_ADMIN
            if current_user.role != "ROOT_ADMIN" and ticket["created_by"] != current_user.email:
                raise HTTPException(status_code=403, detail="Access denied")

            ticket["id"] = str(ticket["_id"])
            ticket["_id"] = str(ticket["_id"])

            # Add computed fields
            ticket["comment_count"] = len(ticket.get("comments", []))
            ticket["is_overdue"] = self._is_ticket_overdue(ticket)

            # Get creator info
            creator = await self.users_collection.find_one(
                {"email": ticket["created_by"]},
                {"first_name": 1, "last_name": 1, "company_name": 1, "email": 1}
            )
            ticket["creator_info"] = creator if creator else {"first_name": "Unknown", "last_name": "User"}

            # Get assignee info if assigned
            if ticket.get("assigned_to"):
                assignee = await self.users_collection.find_one(
                    {"email": ticket["assigned_to"]},
                    {"first_name": 1, "last_name": 1, "email": 1}
                )
                ticket["assignee_info"] = assignee

            # Filter internal comments for non-admin users
            if current_user.role != "ROOT_ADMIN":
                ticket["comments"] = [
                    comment for comment in ticket.get("comments", [])
                    if not comment.get("is_internal", False)
                ]

            return serialize_mongo_doc(ticket)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting ticket: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving ticket: {str(e)}")

    async def update_ticket(self, ticket_id: str, update_data: dict, current_user) -> dict:
        """Update a ticket"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(ticket_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            # Check if ticket exists
            existing = await self.tickets_collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Ticket not found")

            # Check permissions
            if current_user.role != "ROOT_ADMIN" and existing["created_by"] != current_user.email:
                # Non-admin users can only update certain fields of their own tickets
                allowed_fields = {"subject", "description"}
                if not all(field in allowed_fields for field in update_data.keys()):
                    raise HTTPException(status_code=403, detail="Access denied")

            # Prepare update data
            update_data["updated_at"] = datetime.now(timezone.utc)

            # Handle status changes
            if "status" in update_data:
                if update_data["status"] in ["resolved", "closed"] and not existing.get("resolved_at"):
                    update_data["resolved_at"] = datetime.now(timezone.utc)
                elif update_data["status"] not in ["resolved", "closed"] and existing.get("resolved_at"):
                    update_data["resolved_at"] = None

            # Update ticket
            result = await self.tickets_collection.update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Ticket update failed")

            return {
                "message": "Ticket updated successfully",
                "updated_fields": list(update_data.keys())
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating ticket: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating ticket: {str(e)}")

    async def add_comment(self, ticket_id: str, comment_data: dict, current_user) -> dict:
        """Add comment to ticket"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(ticket_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            # Check if ticket exists and user has permission
            ticket = await self.tickets_collection.find_one({"_id": obj_id})
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")

            # Check permissions
            if current_user.role != "ROOT_ADMIN" and ticket["created_by"] != current_user.email:
                raise HTTPException(status_code=403, detail="Access denied")

            # Only ROOT_ADMIN can create internal comments
            if comment_data.get("is_internal") and current_user.role != "ROOT_ADMIN":
                comment_data["is_internal"] = False

            # Prepare comment
            comment = {
                "id": str(ObjectId()),
                "user_id": current_user.email,
                "message": comment_data["message"],
                "created_at": datetime.now(timezone.utc),
                "is_internal": comment_data.get("is_internal", False)
            }

            # Add comment to ticket
            result = await self.tickets_collection.update_one(
                {"_id": obj_id},
                {
                    "$push": {"comments": comment},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Failed to add comment")

            # Notify planner when ROOT_ADMIN responds (not internal comments)
            if current_user.role == "ROOT_ADMIN" and not comment_data.get("is_internal", False):
                # Only notify if the planner is not the commenter
                if ticket["created_by"] != current_user.email:
                    try:
                        await self._notify_planner_ticket_response(ticket, comment, current_user)
                    except Exception as notif_error:
                        logger.error(f"Failed to send ticket response notification: {str(notif_error)}")
                        # Don't fail the comment if notification fails

            # Log activity for all comments
            try:
                activity_logs_collection = mongo.db["activity_logs"]
                await activity_logs_collection.insert_one({
                    "type": "support_ticket_comment",
                    "message": f"Comment added to ticket {ticket.get('ticket_number', 'Unknown')}",
                    "timestamp": datetime.now(timezone.utc),
                    "created_at": datetime.now(timezone.utc),
                    "planner_email": ticket["created_by"],
                    "actor_email": current_user.email,
                    "metadata": {
                        "ticket_number": ticket.get("ticket_number"),
                        "ticket_id": ticket_id,
                        "comment_id": comment["id"],
                        "is_internal": comment_data.get("is_internal", False)
                    }
                })
            except Exception as activity_error:
                logger.error(f"Failed to log activity for comment: {str(activity_error)}")
                # Don't fail the comment if activity logging fails

            return {
                "message": "Comment added successfully",
                "comment_id": comment["id"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding comment: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error adding comment: {str(e)}")

    async def get_comments(self, ticket_id: str, current_user, include_internal: bool = False) -> dict:
        """Get ticket comments"""
        try:
            # Get ticket with permission check
            ticket = await self.get_ticket(ticket_id, current_user)

            comments = ticket.get("comments", [])

            # Filter internal comments for non-admin users
            if current_user.role != "ROOT_ADMIN" or not include_internal:
                comments = [
                    comment for comment in comments
                    if not comment.get("is_internal", False)
                ]

            # Add user info to comments
            for comment in comments:
                user = await self.users_collection.find_one(
                    {"email": comment["user_id"]},
                    {"first_name": 1, "last_name": 1, "role": 1}
                )
                comment["user_info"] = user if user else {"first_name": "Unknown", "last_name": "User"}

            return {
                "comments": comments,
                "total": len(comments)
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting comments: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving comments: {str(e)}")

    async def assign_ticket(self, ticket_id: str, agent_email: str, assigned_by: str) -> dict:
        """Assign ticket to support agent"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(ticket_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            # Check if agent exists
            agent = await self.users_collection.find_one({"email": agent_email})
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            ticket = await self.tickets_collection.find_one({"_id": obj_id})
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")

            new_status = "in_progress" if ticket.get("status") == "open" else ticket.get("status", "in_progress")

            # Update ticket
            result = await self.tickets_collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "assigned_to": agent_email,
                        "updated_at": datetime.now(timezone.utc),
                        "status": new_status
                    }
                }
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Ticket not found")

            return {
                "message": f"Ticket assigned to {agent.get('first_name', '')} {agent.get('last_name', agent_email)}"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error assigning ticket: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error assigning ticket: {str(e)}")

    async def get_analytics(self, period: str = "30d") -> dict:
        """Get support analytics"""
        try:
            now = datetime.now(timezone.utc)
            if period == "7d":
                start_date = now - timedelta(days=7)
            elif period == "30d":
                start_date = now - timedelta(days=30)
            elif period == "90d":
                start_date = now - timedelta(days=90)
            elif period == "1y":
                start_date = now - timedelta(days=365)
            else:
                start_date = now - timedelta(days=30)

            pipeline = [
                {"$match": {"created_at": {"$gte": start_date}}},
                {
                    "$group": {
                        "_id": {"status": "$status", "priority": "$priority", "category": "$category"},
                        "count": {"$sum": 1},
                        "avg_resolution_time": {
                            "$avg": {
                                "$subtract": [
                                    {"$ifNull": ["$resolved_at", now]},
                                    "$created_at",
                                ]
                            }
                        },
                    }
                },
            ]

            results = [doc async for doc in self.tickets_collection.aggregate(pipeline)]

            analytics = {
                "period": period,
                "total_tickets": sum(r.get("count", 0) for r in results),
                "by_status": {},
                "by_priority": {},
                "by_category": {},
                "avg_resolution_time_hours": 0,
            }

            resolution_times = []
            for result in results:
                key = result.get("_id") or {}
                status = key.get("status") or "unknown"
                priority = key.get("priority") or "unknown"
                category = key.get("category") or "unknown"
                count = result.get("count", 0)

                analytics["by_status"][status] = analytics["by_status"].get(status, 0) + count
                analytics["by_priority"][priority] = analytics["by_priority"].get(priority, 0) + count
                analytics["by_category"][category] = analytics["by_category"].get(category, 0) + count

                avg_ms = result.get("avg_resolution_time")
                if avg_ms:
                    resolution_times.append(avg_ms / 1000 / 3600)

            if resolution_times:
                analytics["avg_resolution_time_hours"] = sum(resolution_times) / len(resolution_times)

            return analytics

        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving analytics: {str(e)}")

    async def get_support_agents(self) -> dict:
        """Get support agents available for assignment"""
        try:
            agents = []
            cursor = self.users_collection.find(
                {"role": {"$in": ["ROOT_ADMIN"]}, "is_active": True},
                {"email": 1, "first_name": 1, "last_name": 1, "role": 1},
            )
            async for agent in cursor:
                agent["_id"] = str(agent["_id"])
                agent["assigned_tickets"] = await self.tickets_collection.count_documents(
                    {"assigned_to": agent["email"], "status": {"$in": ["open", "in_progress"]}}
                )
                agents.append(agent)

            return serialize_mongo_doc({"agents": agents})

        except Exception as e:
            logger.error(f"Error getting support agents: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving support agents: {str(e)}")

    async def get_dashboard_metrics(self) -> dict:
        """Get support dashboard metrics"""
        try:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

            metrics: Dict[str, Any] = {
                "open_tickets": await self.tickets_collection.count_documents({"status": "open"}),
                "in_progress_tickets": await self.tickets_collection.count_documents({"status": "in_progress"}),
                "resolved_today": await self.tickets_collection.count_documents(
                    {"status": "resolved", "resolved_at": {"$gte": today}}
                ),
                "new_tickets_today": await self.tickets_collection.count_documents({"created_at": {"$gte": today}}),
                "urgent_tickets": await self.tickets_collection.count_documents(
                    {"priority": "urgent", "status": {"$in": ["open", "in_progress"]}}
                ),
                "overdue_tickets": 0,
            }

            weekly_trend = []
            for i in range(7):
                day_start = today - timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                daily_count = await self.tickets_collection.count_documents(
                    {"created_at": {"$gte": day_start, "$lt": day_end}}
                )
                weekly_trend.append({"date": day_start.strftime("%Y-%m-%d"), "tickets": daily_count})

            metrics["weekly_trend"] = list(reversed(weekly_trend))
            return metrics

        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving dashboard metrics: {str(e)}")

    async def upload_attachment(self, ticket_id: str, file: UploadFile, current_user) -> dict:
        """Upload attachment to ticket"""
        try:
            # Validate ticket and permissions (also ensures ticket exists)
            await self.get_ticket(ticket_id, current_user)

            try:
                obj_id = ObjectId(ticket_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            allowed_types = [
                "image/jpeg",
                "image/png",
                "image/gif",
                "application/pdf",
                "text/plain",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ]
            if file.content_type not in allowed_types:
                raise HTTPException(status_code=400, detail="File type not allowed")

            content = await file.read()
            file_size = len(content)
            if file_size > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="File too large (max 10MB)")

            upload_dir = os.getenv("SUPPORT_ATTACHMENTS_DIR", "uploads/support_attachments")
            os.makedirs(upload_dir, exist_ok=True)

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_name = os.path.basename(file.filename or "attachment")
            stored_filename = f"{ticket_id}_{timestamp}_{safe_name}"
            file_path = os.path.join(upload_dir, stored_filename)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: open(file_path, "wb").write(content))

            file_url_prefix = os.getenv("SUPPORT_ATTACHMENTS_URL_PREFIX", "/uploads/support_attachments")
            file_url = f"{file_url_prefix}/{stored_filename}"

            result = await self.tickets_collection.update_one(
                {"_id": obj_id},
                {
                    "$push": {
                        "attachments": {
                            "filename": safe_name,
                            "stored_filename": stored_filename,
                            "path": file_path,
                            "url": file_url,
                            "uploaded_by": current_user.email,
                            "uploaded_at": datetime.now(timezone.utc),
                            "file_size": file_size,
                            "content_type": file.content_type,
                        }
                    },
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Failed to attach file")

            return {"message": "File uploaded successfully", "filename": safe_name, "url": file_url}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading attachment: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error uploading attachment: {str(e)}")

    def _is_ticket_overdue(self, ticket: dict) -> bool:
        """Check if ticket is overdue based on priority and creation time"""
        try:
            now = datetime.now(timezone.utc)
            created = ticket["created_at"]
            priority = ticket.get("priority", "medium")

            # SLA times in hours
            sla_times = {
                "urgent": 4,
                "high": 24,
                "medium": 72,
                "low": 168  # 1 week
            }

            sla_hours = sla_times.get(priority, 72)
            due_time = created + timedelta(hours=sla_hours)

            # Not overdue if already resolved
            if ticket.get("status") in ["resolved", "closed"]:
                return False

            return now > due_time

        except Exception:
            return False

    async def _send_new_ticket_notification(self, ticket: dict, created_by: str) -> None:
        """Send email notification to root admin when a new support ticket is created"""
        try:
            from app.services.email_service_resend import ResendEmailService

            email_service = ResendEmailService()

            creator_info = await self.users_collection.find_one(
                {"email": created_by},
                {"first_name": 1, "last_name": 1, "company_name": 1},
            )

            creator_name = "Unknown User"
            if creator_info:
                if creator_info.get("company_name"):
                    creator_name = creator_info["company_name"]
                else:
                    creator_name = (
                        f"{creator_info.get('first_name', '')} {creator_info.get('last_name', '')}".strip() or created_by
                    )

            priority = (ticket.get("priority") or "medium").lower()
            priority_color_map = {
                "urgent": "#dc2626",
                "high": "#f97316",
                "medium": "#2563eb",
                "low": "#16a34a",
            }
            priority_color = priority_color_map.get(priority, "#2563eb")

            frontend_url = (os.getenv("FRONTEND_URL") or "").rstrip("/")
            dashboard_url = f"{frontend_url}/admin/support" if frontend_url else ""

            html_content = f"""\
                    <!doctype html>
                    <html>
                        <body style="font-family: Arial, sans-serif; background-color: #ffffff; color: #111827; margin: 0; padding: 0;">
                        <div style="max-width: 640px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden;">
                            <div style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); padding: 24px; text-align: center;">
                            <h1 style="color: white; margin: 0; font-size: 22px;">New Support Ticket</h1>
                            </div>

                            <div style="padding: 24px;">
                            <div style="background-color: #f8fafc; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                                <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280; width: 120px;">Ticket #:</td>
                                    <td style="padding: 6px 0; font-weight: 600;">{ticket.get('ticket_number', 'N/A')}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">From:</td>
                                    <td style="padding: 6px 0; font-weight: 600;">{creator_name}<br>
                                    <span style="font-weight: normal; color: #6b7280;">{created_by}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">Category:</td>
                                    <td style="padding: 6px 0; text-transform: capitalize;">{(ticket.get('category') or 'general').replace('_', ' ')}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">Priority:</td>
                                    <td style="padding: 6px 0;">
                                    <span style="background-color: {priority_color}; color: white; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; text-transform: uppercase;">
                                        {priority}
                                    </span>
                                    </td>
                                </tr>
                                </table>
                            </div>

                            <h2 style="margin: 0 0 10px 0; font-size: 18px;">{ticket.get('subject', 'No Subject')}</h2>

                            <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px; border-radius: 0 8px 8px 0;">
                                <p style="margin: 0; line-height: 1.6; white-space: pre-wrap;">{ticket.get('description', 'No description provided')}</p>
                            </div>

                            {f'''
                            <div style="text-align: center; margin-top: 20px;">
                                <a href="{dashboard_url}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: 700;">
                                View in Dashboard
                                </a>
                            </div>
                            ''' if dashboard_url else ''}
                            </div>

                            <div style="background-color: #f8fafc; padding: 14px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="color: #6b7280; font-size: 12px; margin: 0;">
                                This email was sent from WeddingApp Support System
                            </p>
                            </div>
                        </div>
                        </body>
                    </html>
                    """

            subject = f"[{priority.upper()}] New Support Ticket: {ticket.get('subject', 'No Subject')}"

            await email_service.send_email(
                to_email=ROOT_ADMIN_EMAIL,
                subject=subject,
                html_content=html_content,
                from_name="WeddingApp Support",
                email_type="support_ticket_notification",
            )

            logger.info(
                f"Support ticket notification sent to {ROOT_ADMIN_EMAIL} for ticket {ticket.get('ticket_number')}"
            )

        except Exception as e:
            logger.error(f"Failed to send support ticket notification: {str(e)}")
            raise

    async def _notify_planner_ticket_response(
        self,
        ticket: dict,
        comment: dict,
        responder
    ) -> None:
        """Notify planner when root admin responds to their support ticket"""
        try:
            planner_email = ticket["created_by"]
            ticket_number = ticket.get("ticket_number", "Unknown")
            ticket_subject = ticket.get("subject", "No Subject")
            ticket_id = str(ticket["_id"])

            # Get responder name
            responder_info = await self.users_collection.find_one(
                {"email": responder.email},
                {"first_name": 1, "last_name": 1}
            )
            responder_name = "Support Team"
            if responder_info:
                responder_name = f"{responder_info.get('first_name', '')} {responder_info.get('last_name', '')}".strip()
                if not responder_name:
                    responder_name = "Support Team"

            # 1. Create in-app planner notification
            from app.services.planner_notification_service import planner_notification_service
            await planner_notification_service.notify_support_ticket_response(
                planner_id=planner_email,
                ticket_number=ticket_number,
                ticket_subject=ticket_subject,
                responder_name=responder_name,
                ticket_id=ticket_id,
                message_preview=comment.get("message")
            )
            logger.info(f"Planner notification created for ticket response: {ticket_number}")

            # 2. Send email notification
            await self._send_ticket_response_email(
                planner_email=planner_email,
                ticket=ticket,
                comment=comment,
                responder_name=responder_name
            )

        except Exception as e:
            logger.error(f"Failed to notify planner about ticket response: {str(e)}")
            raise

    async def _send_ticket_response_email(
        self,
        planner_email: str,
        ticket: dict,
        comment: dict,
        responder_name: str
    ) -> None:
        """Send email notification to planner when admin responds to their ticket"""
        try:
            from app.services.email_service_resend import ResendEmailService

            email_service = ResendEmailService()

            ticket_number = ticket.get("ticket_number", "Unknown")
            ticket_subject = ticket.get("subject", "No Subject")
            message_content = comment.get("message", "")

            frontend_url = (os.getenv("FRONTEND_URL") or "").rstrip("/")
            support_url = f"{frontend_url}/admin/support" if frontend_url else ""

            html_content = f"""
            <!doctype html>
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #ffffff; color: #111827; margin: 0; padding: 0;">
                <div style="max-width: 640px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden;">
                    <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 24px; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 22px;">Support Response</h1>
                    </div>

                    <div style="padding: 24px;">
                        <div style="background-color: #f8fafc; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280; width: 120px;">Ticket #:</td>
                                    <td style="padding: 6px 0; font-weight: 600;">{ticket_number}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">Subject:</td>
                                    <td style="padding: 6px 0; font-weight: 600;">{ticket_subject}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">Responded by:</td>
                                    <td style="padding: 6px 0;">{responder_name}</td>
                                </tr>
                            </table>
                        </div>

                        <h2 style="margin: 20px 0 10px 0; font-size: 16px; color: #374151;">Response:</h2>

                        <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 16px; border-radius: 0 8px 8px 0;">
                            <p style="margin: 0; line-height: 1.6; white-space: pre-wrap;">{message_content}</p>
                        </div>

                        {f'''
                        <div style="text-align: center; margin-top: 24px;">
                            <a href="{support_url}" style="display: inline-block; background-color: #10b981; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                                View in Support Center
                            </a>
                        </div>
                        ''' if support_url else ''}
                    </div>

                    <div style="background-color: #f8fafc; padding: 16px; text-align: center; border-top: 1px solid #e5e7eb;">
                        <p style="color: #6b7280; font-size: 12px; margin: 0;">
                            This email was sent from TheSpecialWedding Support System
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            await email_service.send_email(
                to_email=planner_email,
                subject=f"Support Response: {ticket_subject} (#{ticket_number})",
                html_content=html_content,
                from_name="TheSpecialWedding Support",
                email_type="support_ticket_response"
            )

            logger.info(f"Ticket response email sent to {planner_email} for ticket {ticket_number}")

        except Exception as e:
            logger.error(f"Failed to send ticket response email: {str(e)}")

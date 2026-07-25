import asyncio
import html
import logging
import os
import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, UploadFile

from app.constants.roles import ROLE_ROOT_ADMIN
from app.constants.support_conversations import (
    CONVERSATION_KIND_FIELD,
    PLATFORM_SUPPORT_KIND,
    actor_owns_support_ticket,
    is_platform_support_ticket,
    platform_support_ticket_scope,
    support_actor_key,
    support_ticket_owner_scope,
)
from app.core.database import mongo
from app.utils.serializers import serialize_mongo_doc
from app.utils.support_inbox_links import (
    build_support_inbox_path,
    build_support_inbox_url,
)

logger = logging.getLogger(__name__)

# Root admin email for support notifications
# Default fallback uses .io domain (SAAS platform) - should be configured via env var
ROOT_ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "admin@thespecialwedding.io")


class SupportService:
    def __init__(self):
        self.tickets_collection = mongo.db["support_tickets"]
        self.read_states_collection = mongo.db["support_ticket_read_states"]
        self.users_collection = mongo.get_users_collection()

    def generate_ticket_number(self) -> str:
        """Generate a unique ticket number"""
        prefix = "TKT"
        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        random_suffix = "".join(secrets.choice(string.digits) for _ in range(4))
        return f"{prefix}-{timestamp}-{random_suffix}"

    async def _mark_ticket_read(self, ticket_id: str, current_user) -> None:
        try:
            actor_key = support_actor_key(current_user)
            now = datetime.now(UTC)
            await self.read_states_collection.update_one(
                {"ticket_id": ticket_id, "actor_key": actor_key},
                {
                    "$set": {
                        "ticket_id": ticket_id,
                        "actor_key": actor_key,
                        "last_read_at": now,
                        "updated_at": now,
                    }
                },
                upsert=True,
            )
        except Exception as error:
            logger.warning(
                "Failed to mark support ticket %s read: %s", ticket_id, error
            )

    async def _is_ticket_read(self, ticket: dict, current_user) -> bool:
        try:
            state = await self.read_states_collection.find_one(
                {
                    "ticket_id": str(ticket["_id"]),
                    "actor_key": support_actor_key(current_user),
                }
            )
        except Exception as error:
            logger.warning("Failed to read support ticket state: %s", error)
            return False
        if not state or not state.get("last_read_at"):
            return False

        activity_at = ticket.get("updated_at") or ticket.get("created_at")
        if not activity_at:
            return True
        last_read_at = state["last_read_at"]
        if last_read_at.tzinfo is None:
            last_read_at = last_read_at.replace(tzinfo=UTC)
        if activity_at.tzinfo is None:
            activity_at = activity_at.replace(tzinfo=UTC)
        return last_read_at >= activity_at

    async def create_ticket(self, ticket_data: dict, current_user) -> dict:
        """Create a new support ticket"""
        try:
            created_by = current_user.email
            creator_user_id = str(current_user.user_data.get("_id") or "") or None
            owner_planner_id = None
            if bool(getattr(current_user, "is_wedding_planner", False)):
                owner_planner_id = creator_user_id
            elif bool(getattr(current_user, "is_team_member", False)):
                owner_planner_id = (
                    str(getattr(current_user, "parent_planner_id", "") or "") or None
                )

            # Generate unique ticket number
            ticket_number = self.generate_ticket_number()

            # Ensure unique ticket number
            while await self.tickets_collection.find_one(
                {"ticket_number": ticket_number}
            ):
                ticket_number = self.generate_ticket_number()

            # Prepare ticket document
            ticket = {
                "_id": ObjectId(),
                "ticket_number": ticket_number,
                CONVERSATION_KIND_FIELD: PLATFORM_SUPPORT_KIND,
                "subject": ticket_data["subject"],
                "description": ticket_data["description"],
                "priority": ticket_data["priority"],
                "category": ticket_data["category"],
                "status": "open",
                "created_by": created_by,
                "creator_user_id": creator_user_id,
                "creator_role": current_user.role,
                "owner_planner_id": owner_planner_id,
                "assigned_to": None,
                "wedding_id": ticket_data.get("wedding_id"),
                "attachments": ticket_data.get("attachments", []),
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
                "resolved_at": None,
                "comments": [],
                "tags": [],
                "satisfaction_rating": None,
            }

            # Insert ticket
            result = await self.tickets_collection.insert_one(ticket)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create ticket")

            await self._mark_ticket_read(str(result.inserted_id), current_user)

            logger.info(
                f"Support ticket {ticket_number} created successfully by {created_by}"
            )

            # Log activity for planner dashboard (activity_logs collection)
            try:
                activity_logs_collection = mongo.db["activity_logs"]
                await activity_logs_collection.insert_one(
                    {
                        "type": "support_ticket_created",
                        "message": f"Support ticket created: {ticket['subject'][:50]}",
                        "timestamp": datetime.now(UTC),
                        "created_at": datetime.now(UTC),
                        "planner_email": created_by,
                        "actor_email": created_by,
                        "metadata": {
                            "ticket_number": ticket_number,
                            "ticket_id": str(result.inserted_id),
                            "priority": ticket["priority"],
                            "category": ticket["category"],
                        },
                    }
                )
                logger.info(f"Activity logged for support ticket {ticket_number}")
            except Exception as activity_error:
                logger.error(
                    f"Failed to log activity for ticket {ticket_number}: {activity_error!s}"
                )
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
                        "action_url": build_support_inbox_path(
                            "support_ticket",
                            ticket_id=str(result.inserted_id),
                        ),
                        "is_dismissible": True,
                        "priority": (
                            "high"
                            if ticket["priority"] in ["urgent", "high"]
                            else "medium"
                        ),
                    },
                    created_by="system",
                )
                logger.info(
                    f"In-app notification created for support ticket {ticket_number}"
                )
            except Exception as notif_error:
                logger.error(
                    f"Failed to create notification for ticket {ticket_number}: {notif_error!s}"
                )
                # Don't fail ticket creation if notification fails

            # Send email notification to root admin
            try:
                await self._send_new_ticket_notification(ticket, created_by)
            except Exception as email_error:
                logger.error(
                    f"Failed to send email notification for ticket {ticket_number}: {email_error!s}"
                )
                # Don't fail the ticket creation if email fails

            return {
                "id": str(result.inserted_id),
                "ticket_number": ticket_number,
                "message": "Support ticket created successfully",
                "created_at": ticket["created_at"],
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating ticket: {e!s}")
            raise HTTPException(status_code=500, detail=f"Error creating ticket: {e!s}")

    async def get_tickets(
        self,
        page: int = 1,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
        *,
        platform_support_only: bool = False,
        active_statuses: list[str] | None = None,
        current_user=None,
        include_internal_comments: bool = False,
    ) -> dict:
        """Get tickets with filtering and pagination"""
        try:
            # Build query
            query = {}
            if filters:
                for key, value in filters.items():
                    if value is not None:
                        query[key] = value
            if platform_support_only:
                query = platform_support_ticket_scope(query)
            if active_statuses:
                query["status"] = {"$in": active_statuses}

            # Count total documents
            total = await self.tickets_collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit

            # Get tickets with sorting (priority + created date)
            priority_order = {"urgent": 4, "high": 3, "medium": 2, "low": 1}

            cursor = (
                self.tickets_collection.find(query)
                .sort(
                    [
                        ("status", 1),  # Open tickets first
                        ("priority", -1),  # High priority first
                        ("created_at", -1),  # Newest first
                    ]
                )
                .skip(skip)
                .limit(limit)
            )

            tickets = []
            unread_count = 0
            async for ticket in cursor:
                ticket["id"] = str(ticket["_id"])
                ticket["_id"] = str(ticket["_id"])

                if not include_internal_comments:
                    ticket["comments"] = [
                        comment
                        for comment in ticket.get("comments", [])
                        if not comment.get("is_internal", False)
                    ]

                # Add computed fields
                ticket["comment_count"] = len(ticket.get("comments", []))
                ticket["is_overdue"] = self._is_ticket_overdue(ticket)
                ticket["priority_order"] = priority_order.get(
                    ticket.get("priority", "medium"), 2
                )

                # Get creator info
                creator = await self.users_collection.find_one(
                    {"email": ticket["created_by"]},
                    {"first_name": 1, "last_name": 1, "company_name": 1},
                )
                ticket["creator_info"] = (
                    creator
                    if creator
                    else {"first_name": "Unknown", "last_name": "User"}
                )

                if current_user is not None:
                    ticket["is_read"] = await self._is_ticket_read(ticket, current_user)
                    if not ticket["is_read"]:
                        unread_count += 1

                tickets.append(ticket)

            return serialize_mongo_doc(
                {
                    "tickets": tickets,
                    "total": total,
                    "page": page,
                    "pages": pages,
                    "unread_count": unread_count,
                }
            )

        except Exception as e:
            logger.error(f"Error getting tickets: {e!s}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving tickets: {e!s}"
            )

    async def get_ticket(self, ticket_id: str, current_user) -> dict:
        """Get specific ticket by ID"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(ticket_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            ticket = await self.tickets_collection.find_one(
                platform_support_ticket_scope({"_id": obj_id})
            )
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")
            if not is_platform_support_ticket(ticket):
                raise HTTPException(status_code=404, detail="Ticket not found")

            is_root_admin = bool(getattr(current_user, "is_root_admin", False))
            if not is_root_admin and not actor_owns_support_ticket(
                ticket, current_user
            ):
                raise HTTPException(status_code=403, detail="Access denied")

            ticket["id"] = str(ticket["_id"])
            ticket["_id"] = str(ticket["_id"])

            # Add computed fields
            ticket["comment_count"] = len(ticket.get("comments", []))
            ticket["is_overdue"] = self._is_ticket_overdue(ticket)

            # Get creator info
            creator = await self.users_collection.find_one(
                {"email": ticket["created_by"]},
                {"first_name": 1, "last_name": 1, "company_name": 1, "email": 1},
            )
            ticket["creator_info"] = (
                creator if creator else {"first_name": "Unknown", "last_name": "User"}
            )

            # Get assignee info if assigned
            if ticket.get("assigned_to"):
                assignee = await self.users_collection.find_one(
                    {"email": ticket["assigned_to"]},
                    {"first_name": 1, "last_name": 1, "email": 1},
                )
                ticket["assignee_info"] = assignee

            # Filter internal comments for non-admin users
            if not is_root_admin:
                ticket["comments"] = [
                    comment
                    for comment in ticket.get("comments", [])
                    if not comment.get("is_internal", False)
                ]

            await self._mark_ticket_read(ticket_id, current_user)
            ticket["is_read"] = True

            return serialize_mongo_doc(ticket)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting ticket: {e!s}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving ticket: {e!s}"
            )

    async def update_ticket(
        self, ticket_id: str, update_data: dict, current_user
    ) -> dict:
        """Update a ticket"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(ticket_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            # Check if ticket exists
            existing = await self.tickets_collection.find_one(
                platform_support_ticket_scope({"_id": obj_id})
            )
            if not existing:
                raise HTTPException(status_code=404, detail="Ticket not found")
            if not is_platform_support_ticket(existing):
                raise HTTPException(
                    status_code=400,
                    detail="SMS support tickets must be updated via SMS support endpoints",
                )

            # Keep platform-support ownership and operational controls separate.
            # Non-root users may edit only the content of tickets they created;
            # status, priority, and assignment remain root-operated fields.
            is_root_admin = bool(getattr(current_user, "is_root_admin", False))
            if not is_root_admin:
                if not actor_owns_support_ticket(existing, current_user):
                    raise HTTPException(status_code=403, detail="Access denied")

                allowed_fields = {"subject", "description"}
                if not all(field in allowed_fields for field in update_data):
                    raise HTTPException(status_code=403, detail="Access denied")

            # Prepare update data
            update_data["updated_at"] = datetime.now(UTC)

            # Handle status changes
            if "status" in update_data:
                if update_data["status"] in ["resolved", "closed"] and not existing.get(
                    "resolved_at"
                ):
                    update_data["resolved_at"] = datetime.now(UTC)
                elif update_data["status"] not in [
                    "resolved",
                    "closed",
                ] and existing.get("resolved_at"):
                    update_data["resolved_at"] = None

            # Update ticket
            update_query: dict[str, Any] = platform_support_ticket_scope(
                {"_id": obj_id}
            )
            if not is_root_admin:
                update_query.update(support_ticket_owner_scope(current_user))

            result = await self.tickets_collection.update_one(
                update_query, {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Ticket update failed")

            return {
                "message": "Ticket updated successfully",
                "updated_fields": list(update_data.keys()),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating ticket: {e!s}")
            raise HTTPException(status_code=500, detail=f"Error updating ticket: {e!s}")

    async def add_comment(
        self, ticket_id: str, comment_data: dict, current_user
    ) -> dict:
        """Add comment to ticket"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(ticket_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            # Check if ticket exists and user has permission
            ticket = await self.tickets_collection.find_one(
                platform_support_ticket_scope({"_id": obj_id})
            )
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")
            if not is_platform_support_ticket(ticket):
                raise HTTPException(
                    status_code=400,
                    detail="SMS support tickets must be replied to via SMS support endpoints",
                )

            is_root_admin = bool(getattr(current_user, "is_root_admin", False))
            if not is_root_admin and not actor_owns_support_ticket(
                ticket, current_user
            ):
                raise HTTPException(status_code=403, detail="Access denied")

            # Only ROOT_ADMIN can create internal comments
            if comment_data.get("is_internal") and not is_root_admin:
                comment_data["is_internal"] = False

            # Prepare comment
            comment = {
                "id": str(ObjectId()),
                "user_id": current_user.email,
                "message": comment_data["message"],
                "created_at": datetime.now(UTC),
                "is_internal": comment_data.get("is_internal", False),
            }

            # Add comment to ticket
            now = datetime.now(UTC)
            update: dict[str, Any] = {
                "$push": {"comments": comment},
                "$set": {"updated_at": now},
            }
            if (
                is_root_admin
                and not comment_data.get("is_internal", False)
                and ticket.get("status") == "open"
            ):
                update["$set"]["status"] = "in_progress"

            update_query = platform_support_ticket_scope({"_id": obj_id})
            if not is_root_admin:
                update_query.update(support_ticket_owner_scope(current_user))
            result = await self.tickets_collection.update_one(update_query, update)

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Failed to add comment")

            # Notify planner when ROOT_ADMIN responds (not internal comments)
            await self._mark_ticket_read(ticket_id, current_user)

            if is_root_admin and not comment_data.get("is_internal", False):
                # Only notify if the planner is not the commenter
                if ticket["created_by"] != current_user.email:
                    try:
                        await self._notify_planner_ticket_response(
                            ticket, comment, current_user
                        )
                    except Exception as notif_error:
                        logger.error(
                            f"Failed to send ticket response notification: {notif_error!s}"
                        )
                        # Don't fail the comment if notification fails

            # Log activity for all comments
            try:
                activity_logs_collection = mongo.db["activity_logs"]
                await activity_logs_collection.insert_one(
                    {
                        "type": "support_ticket_comment",
                        "message": f"Comment added to ticket {ticket.get('ticket_number', 'Unknown')}",
                        "timestamp": now,
                        "created_at": now,
                        "planner_email": ticket["created_by"],
                        "actor_email": current_user.email,
                        "metadata": {
                            "ticket_number": ticket.get("ticket_number"),
                            "ticket_id": ticket_id,
                            "comment_id": comment["id"],
                            "is_internal": comment_data.get("is_internal", False),
                        },
                    }
                )
            except Exception as activity_error:
                logger.error(f"Failed to log activity for comment: {activity_error!s}")
                # Don't fail the comment if activity logging fails

            return {
                "message": "Comment added successfully",
                "comment_id": comment["id"],
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding comment: {e!s}")
            raise HTTPException(status_code=500, detail=f"Error adding comment: {e!s}")

    async def get_comments(
        self, ticket_id: str, current_user, include_internal: bool = False
    ) -> dict:
        """Get ticket comments"""
        try:
            # Get ticket with permission check
            ticket = await self.get_ticket(ticket_id, current_user)

            comments = ticket.get("comments", [])

            # Filter internal comments for non-admin users
            if (
                not bool(getattr(current_user, "is_root_admin", False))
                or not include_internal
            ):
                comments = [
                    comment
                    for comment in comments
                    if not comment.get("is_internal", False)
                ]

            # Add user info to comments
            for comment in comments:
                user = await self.users_collection.find_one(
                    {"email": comment["user_id"]},
                    {"first_name": 1, "last_name": 1, "role": 1},
                )
                comment["user_info"] = (
                    user if user else {"first_name": "Unknown", "last_name": "User"}
                )

            return {"comments": comments, "total": len(comments)}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting comments: {e!s}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving comments: {e!s}"
            )

    async def assign_ticket(
        self, ticket_id: str, agent_email: str, assigned_by: str
    ) -> dict:
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

            ticket = await self.tickets_collection.find_one(
                platform_support_ticket_scope({"_id": obj_id})
            )
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")

            if not is_platform_support_ticket(ticket):
                raise HTTPException(
                    status_code=400,
                    detail="SMS support tickets cannot be assigned via support ticket endpoints",
                )

            new_status = (
                "in_progress"
                if ticket.get("status") == "open"
                else ticket.get("status", "in_progress")
            )

            # Update ticket
            result = await self.tickets_collection.update_one(
                platform_support_ticket_scope({"_id": obj_id}),
                {
                    "$set": {
                        "assigned_to": agent_email,
                        "updated_at": datetime.now(UTC),
                        "status": new_status,
                    }
                },
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Ticket not found")

            return {
                "message": f"Ticket assigned to {agent.get('first_name', '')} {agent.get('last_name', agent_email)}"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error assigning ticket: {e!s}")
            raise HTTPException(
                status_code=500, detail=f"Error assigning ticket: {e!s}"
            )

    async def get_analytics(self, period: str = "30d") -> dict:
        """Get support analytics"""
        try:
            now = datetime.now(UTC)
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
                {
                    "$match": platform_support_ticket_scope(
                        {"created_at": {"$gte": start_date}}
                    )
                },
                {
                    "$group": {
                        "_id": {
                            "status": "$status",
                            "priority": "$priority",
                            "category": "$category",
                        },
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

                analytics["by_status"][status] = (
                    analytics["by_status"].get(status, 0) + count
                )
                analytics["by_priority"][priority] = (
                    analytics["by_priority"].get(priority, 0) + count
                )
                analytics["by_category"][category] = (
                    analytics["by_category"].get(category, 0) + count
                )

                avg_ms = result.get("avg_resolution_time")
                if avg_ms:
                    resolution_times.append(avg_ms / 1000 / 3600)

            if resolution_times:
                analytics["avg_resolution_time_hours"] = sum(resolution_times) / len(
                    resolution_times
                )

            return analytics

        except Exception as e:
            logger.error(f"Error getting analytics: {e!s}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving analytics: {e!s}"
            )

    async def get_support_agents(self) -> dict:
        """Get support agents available for assignment"""
        try:
            agents = []
            cursor = self.users_collection.find(
                {"role": {"$in": [ROLE_ROOT_ADMIN]}, "is_active": True},
                {"email": 1, "first_name": 1, "last_name": 1, "role": 1},
            )
            async for agent in cursor:
                agent["_id"] = str(agent["_id"])
                agent[
                    "assigned_tickets"
                ] = await self.tickets_collection.count_documents(
                    platform_support_ticket_scope(
                        {
                            "assigned_to": agent["email"],
                            "status": {"$in": ["open", "in_progress"]},
                        }
                    )
                )
                agents.append(agent)

            return serialize_mongo_doc({"agents": agents})

        except Exception as e:
            logger.error(f"Error getting support agents: {e!s}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving support agents: {e!s}"
            )

    async def get_dashboard_metrics(self) -> dict:
        """Get support dashboard metrics"""
        try:
            today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

            metrics: dict[str, Any] = {
                "open_tickets": await self.tickets_collection.count_documents(
                    platform_support_ticket_scope({"status": "open"})
                ),
                "in_progress_tickets": await self.tickets_collection.count_documents(
                    platform_support_ticket_scope({"status": "in_progress"})
                ),
                "resolved_today": await self.tickets_collection.count_documents(
                    platform_support_ticket_scope(
                        {"status": "resolved", "resolved_at": {"$gte": today}}
                    )
                ),
                "new_tickets_today": await self.tickets_collection.count_documents(
                    platform_support_ticket_scope({"created_at": {"$gte": today}})
                ),
                "urgent_tickets": await self.tickets_collection.count_documents(
                    platform_support_ticket_scope(
                        {
                            "priority": "urgent",
                            "status": {"$in": ["open", "in_progress"]},
                        }
                    )
                ),
                "overdue_tickets": 0,
            }

            weekly_trend = []
            for i in range(7):
                day_start = today - timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                daily_count = await self.tickets_collection.count_documents(
                    platform_support_ticket_scope(
                        {"created_at": {"$gte": day_start, "$lt": day_end}}
                    )
                )
                weekly_trend.append(
                    {"date": day_start.strftime("%Y-%m-%d"), "tickets": daily_count}
                )

            metrics["weekly_trend"] = list(reversed(weekly_trend))
            return metrics

        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {e!s}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving dashboard metrics: {e!s}"
            )

    async def upload_attachment(
        self, ticket_id: str, file: UploadFile, current_user
    ) -> dict:
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

            upload_dir = os.getenv(
                "SUPPORT_ATTACHMENTS_DIR", "uploads/support_attachments"
            )
            os.makedirs(upload_dir, exist_ok=True)

            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            safe_name = os.path.basename(file.filename or "attachment")
            stored_filename = f"{ticket_id}_{timestamp}_{safe_name}"
            file_path = os.path.join(upload_dir, stored_filename)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, lambda: open(file_path, "wb").write(content)
            )

            file_url_prefix = os.getenv(
                "SUPPORT_ATTACHMENTS_URL_PREFIX", "/uploads/support_attachments"
            )
            file_url = f"{file_url_prefix}/{stored_filename}"

            update_query = platform_support_ticket_scope({"_id": obj_id})
            if not bool(getattr(current_user, "is_root_admin", False)):
                update_query.update(support_ticket_owner_scope(current_user))
            result = await self.tickets_collection.update_one(
                update_query,
                {
                    "$push": {
                        "attachments": {
                            "filename": safe_name,
                            "stored_filename": stored_filename,
                            "path": file_path,
                            "url": file_url,
                            "uploaded_by": current_user.email,
                            "uploaded_at": datetime.now(UTC),
                            "file_size": file_size,
                            "content_type": file.content_type,
                        }
                    },
                    "$set": {"updated_at": datetime.now(UTC)},
                },
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Failed to attach file")

            return {
                "message": "File uploaded successfully",
                "filename": safe_name,
                "url": file_url,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading attachment: {e!s}")
            raise HTTPException(
                status_code=500, detail=f"Error uploading attachment: {e!s}"
            )

    def _is_ticket_overdue(self, ticket: dict) -> bool:
        """Check if ticket is overdue based on priority and creation time"""
        try:
            now = datetime.now(UTC)
            created = ticket["created_at"]
            priority = ticket.get("priority", "medium")

            # SLA times in hours
            sla_times = {
                "urgent": 4,
                "high": 24,
                "medium": 72,
                "low": 168,  # 1 week
            }

            sla_hours = sla_times.get(priority, 72)
            due_time = created + timedelta(hours=sla_hours)

            # Not overdue if already resolved
            if ticket.get("status") in ["resolved", "closed"]:
                return False

            return now > due_time

        except Exception:
            return False

    async def _send_new_ticket_notification(
        self, ticket: dict, created_by: str
    ) -> None:
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
                        f"{creator_info.get('first_name', '')} {creator_info.get('last_name', '')}".strip()
                        or created_by
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
            inbox_url = ""
            if frontend_url:
                inbox_url = build_support_inbox_url(
                    frontend_url=frontend_url,
                    conversation="support_ticket",
                    ticket_id=str(ticket.get("_id")),
                    wedding_id=ticket.get("wedding_id"),
                )

            safe_ticket_number = html.escape(
                str(ticket.get("ticket_number", "N/A")), quote=True
            )
            safe_creator_name = html.escape(creator_name, quote=True)
            safe_created_by = html.escape(str(created_by or ""), quote=True)
            safe_category = html.escape(
                (ticket.get("category") or "general").replace("_", " "), quote=True
            )
            safe_priority_color = html.escape(priority_color, quote=True)
            safe_priority = html.escape(priority, quote=True)
            safe_subject = html.escape(
                str(ticket.get("subject", "No Subject")), quote=True
            )
            safe_description = html.escape(
                str(ticket.get("description", "No description provided")),
                quote=True,
            )
            safe_inbox_url = html.escape(inbox_url, quote=True) if inbox_url else ""

            inbox_button_html = (
                f'''
                            <div style="text-align: center; margin-top: 20px;">
                                <a href="{safe_inbox_url}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: 700;">
                                Open in Inbox
                                </a>
                            </div>
                            '''
                if inbox_url
                else ""
            )

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
                                    <td style="padding: 6px 0; font-weight: 600;">{safe_ticket_number}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">From:</td>
                                    <td style="padding: 6px 0; font-weight: 600;">{safe_creator_name}<br>
                                    <span style="font-weight: normal; color: #6b7280;">{safe_created_by}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">Category:</td>
                                    <td style="padding: 6px 0; text-transform: capitalize;">{safe_category}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">Priority:</td>
                                    <td style="padding: 6px 0;">
                                    <span style="background-color: {safe_priority_color}; color: white; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; text-transform: uppercase;">
                                        {safe_priority}
                                    </span>
                                    </td>
                                </tr>
                                </table>
                            </div>

                            <h2 style="margin: 0 0 10px 0; font-size: 18px;">{safe_subject}</h2>

                            <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px; border-radius: 0 8px 8px 0;">
                                <p style="margin: 0; line-height: 1.6; white-space: pre-wrap;">{safe_description}</p>
                            </div>

                            {inbox_button_html}
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
            logger.error(f"Failed to send support ticket notification: {e!s}")
            raise

    async def _notify_planner_ticket_response(
        self, ticket: dict, comment: dict, responder
    ) -> None:
        """Notify planner when root admin responds to their support ticket"""
        try:
            planner_email = ticket["created_by"]
            ticket_number = ticket.get("ticket_number", "Unknown")
            ticket_subject = ticket.get("subject", "No Subject")
            ticket_id = str(ticket["_id"])

            # Get responder name
            responder_info = await self.users_collection.find_one(
                {"email": responder.email}, {"first_name": 1, "last_name": 1}
            )
            responder_name = "Support Team"
            if responder_info:
                responder_name = f"{responder_info.get('first_name', '')} {responder_info.get('last_name', '')}".strip()
                if not responder_name:
                    responder_name = "Support Team"

            # 1. Create in-app planner notification
            from app.services.planner_notification_service import (
                planner_notification_service,
            )

            await planner_notification_service.notify_support_ticket_response(
                planner_id=planner_email,
                ticket_number=ticket_number,
                ticket_subject=ticket_subject,
                responder_name=responder_name,
                ticket_id=ticket_id,
                message_preview=comment.get("message"),
            )
            logger.info(
                f"Planner notification created for ticket response: {ticket_number}"
            )

            # 2. Send email notification
            await self._send_ticket_response_email(
                planner_email=planner_email,
                ticket=ticket,
                comment=comment,
                responder_name=responder_name,
            )

        except Exception as e:
            logger.error(f"Failed to notify planner about ticket response: {e!s}")
            raise

    async def _send_ticket_response_email(
        self, planner_email: str, ticket: dict, comment: dict, responder_name: str
    ) -> None:
        """Send email notification to planner when admin responds to their ticket"""
        try:
            from app.services.email_service_resend import ResendEmailService

            email_service = ResendEmailService()

            ticket_id = str(ticket.get("_id"))
            ticket_number = ticket.get("ticket_number", "Unknown")
            ticket_subject = ticket.get("subject", "No Subject")
            message_content = comment.get("message", "")

            frontend_url = (os.getenv("FRONTEND_URL") or "").rstrip("/")
            support_url = ""
            if frontend_url:
                support_url = build_support_inbox_url(
                    frontend_url=frontend_url,
                    conversation="support_ticket",
                    ticket_id=ticket_id,
                    wedding_id=ticket.get("wedding_id"),
                )

            safe_ticket_number = html.escape(str(ticket_number), quote=True)
            safe_ticket_subject = html.escape(str(ticket_subject), quote=True)
            safe_responder_name = html.escape(str(responder_name), quote=True)
            safe_message_content = html.escape(str(message_content), quote=True)
            safe_support_url = (
                html.escape(support_url, quote=True) if support_url else ""
            )

            inbox_button_html = (
                f'''
                        <div style="text-align: center; margin-top: 24px;">
                            <a href="{safe_support_url}" style="display: inline-block; background-color: #10b981; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                                Open in Inbox
                            </a>
                        </div>
                        '''
                if support_url
                else ""
            )

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
                                    <td style="padding: 6px 0; font-weight: 600;">{safe_ticket_number}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">Subject:</td>
                                    <td style="padding: 6px 0; font-weight: 600;">{safe_ticket_subject}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #6b7280;">Responded by:</td>
                                    <td style="padding: 6px 0;">{safe_responder_name}</td>
                                </tr>
                            </table>
                        </div>

                        <h2 style="margin: 20px 0 10px 0; font-size: 16px; color: #374151;">Response:</h2>

                        <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 16px; border-radius: 0 8px 8px 0;">
                            <p style="margin: 0; line-height: 1.6; white-space: pre-wrap;">{safe_message_content}</p>
                        </div>

                        {inbox_button_html}
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
                email_type="support_ticket_response",
            )

            logger.info(
                f"Ticket response email sent to {planner_email} for ticket {ticket_number}"
            )

        except Exception as e:
            logger.error(f"Failed to send ticket response email: {e!s}")

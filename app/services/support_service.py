from fastapi import HTTPException, UploadFile
from app.core.database import mongo
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from bson import ObjectId
import secrets
import string
import logging
import os

logger = logging.getLogger(__name__)

class SupportService:
    def __init__(self):
        self.tickets_collection = mongo.db["support_tickets"]
        self.users_collection = mongo.db["users"]

    def generate_ticket_number(self) -> str:
        """Generate a unique ticket number"""
        prefix = "TKT"
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
        return f"{prefix}-{timestamp}-{random_suffix}"

    async def create_ticket(self, ticket_data: dict, created_by: str) -> dict:
        """Create a new support ticket"""
        try:
            # Generate unique ticket number
            ticket_number = self.generate_ticket_number()

            # Ensure unique ticket number
            while self.tickets_collection.find_one({"ticket_number": ticket_number}):
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
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "resolved_at": None,
                "comments": [],
                "tags": [],
                "satisfaction_rating": None
            }

            # Insert ticket
            result = self.tickets_collection.insert_one(ticket)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create ticket")

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
            total = self.tickets_collection.count_documents(query)

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
            for ticket in cursor:
                ticket["id"] = str(ticket["_id"])
                ticket["_id"] = str(ticket["_id"])

                # Add computed fields
                ticket["comment_count"] = len(ticket.get("comments", []))
                ticket["is_overdue"] = self._is_ticket_overdue(ticket)
                ticket["priority_order"] = priority_order.get(ticket.get("priority", "medium"), 2)

                # Get creator info
                creator = self.users_collection.find_one(
                    {"email": ticket["created_by"]},
                    {"first_name": 1, "last_name": 1, "company_name": 1}
                )
                ticket["creator_info"] = creator if creator else {"first_name": "Unknown", "last_name": "User"}

                tickets.append(ticket)

            return {
                "tickets": tickets,
                "total": total,
                "page": page,
                "pages": pages
            }

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

            ticket = self.tickets_collection.find_one({"_id": obj_id})
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
            creator = self.users_collection.find_one(
                {"email": ticket["created_by"]},
                {"first_name": 1, "last_name": 1, "company_name": 1, "email": 1}
            )
            ticket["creator_info"] = creator if creator else {"first_name": "Unknown", "last_name": "User"}

            # Get assignee info if assigned
            if ticket.get("assigned_to"):
                assignee = self.users_collection.find_one(
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

            return ticket

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
            existing = self.tickets_collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Ticket not found")

            # Check permissions
            if current_user.role != "ROOT_ADMIN" and existing["created_by"] != current_user.email:
                # Non-admin users can only update certain fields of their own tickets
                allowed_fields = {"subject", "description"}
                if not all(field in allowed_fields for field in update_data.keys()):
                    raise HTTPException(status_code=403, detail="Access denied")

            # Prepare update data
            update_data["updated_at"] = datetime.utcnow()

            # Handle status changes
            if "status" in update_data:
                if update_data["status"] in ["resolved", "closed"] and not existing.get("resolved_at"):
                    update_data["resolved_at"] = datetime.utcnow()
                elif update_data["status"] not in ["resolved", "closed"] and existing.get("resolved_at"):
                    update_data["resolved_at"] = None

            # Update ticket
            result = self.tickets_collection.update_one(
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
            except:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            # Check if ticket exists and user has permission
            ticket = self.tickets_collection.find_one({"_id": obj_id})
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
                "created_at": datetime.utcnow(),
                "is_internal": comment_data.get("is_internal", False)
            }

            # Add comment to ticket
            result = self.tickets_collection.update_one(
                {"_id": obj_id},
                {
                    "$push": {"comments": comment},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Failed to add comment")

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
                user = self.users_collection.find_one(
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
            except:
                raise HTTPException(status_code=400, detail="Invalid ticket ID")

            # Check if agent exists
            agent = self.users_collection.find_one({"email": agent_email})
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            # Fetch current ticket to determine status transition
            current_ticket = self.tickets_collection.find_one({"_id": obj_id}, {"status": 1})
            current_status = current_ticket.get("status") if current_ticket else None

            # Update ticket
            update_result = self.tickets_collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "assigned_to": agent_email,
                        "updated_at": datetime.utcnow(),
                        # Transition open -> in_progress, otherwise keep existing or default to in_progress
                        "status": "in_progress" if current_status == "open" else (current_status or "in_progress")
                    }
                }
            )

            if update_result.modified_count == 0:
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
            # Calculate date range
            now = datetime.utcnow()
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

            # Get tickets in period
            pipeline = [
                {"$match": {"created_at": {"$gte": start_date}}},
                {"$group": {
                    "_id": {
                        "status": "$status",
                        "priority": "$priority",
                        "category": "$category"
                    },
                    "count": {"$sum": 1},
                    "avg_resolution_time": {
                        "$avg": {
                            "$subtract": [
                                {"$ifNull": ["$resolved_at", now]},
                                "$created_at"
                            ]
                        }
                    }
                }}
            ]

            results = list(self.tickets_collection.aggregate(pipeline))

            # Process results
            analytics = {
                "period": period,
                "total_tickets": sum(r["count"] for r in results),
                "by_status": {},
                "by_priority": {},
                "by_category": {},
                "avg_resolution_time_hours": 0
            }

            resolution_times = []
            for result in results:
                status = result["_id"]["status"]
                priority = result["_id"]["priority"]
                category = result["_id"]["category"]
                count = result["count"]

                # Group by status
                if status not in analytics["by_status"]:
                    analytics["by_status"][status] = 0
                analytics["by_status"][status] += count

                # Group by priority
                if priority not in analytics["by_priority"]:
                    analytics["by_priority"][priority] = 0
                analytics["by_priority"][priority] += count

                # Group by category
                if category not in analytics["by_category"]:
                    analytics["by_category"][category] = 0
                analytics["by_category"][category] += count

                # Calculate resolution time
                if result["avg_resolution_time"]:
                    resolution_times.append(result["avg_resolution_time"] / 1000 / 3600)  # Convert to hours

            if resolution_times:
                analytics["avg_resolution_time_hours"] = sum(resolution_times) / len(resolution_times)

            return analytics

        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving analytics: {str(e)}")

    async def get_support_agents(self) -> dict:
        """Get list of support agents"""
        try:
            # Get all admin users who can be assigned tickets
            agents = list(self.users_collection.find(
                {"role": {"$in": ["ROOT_ADMIN"]}, "is_active": True},
                {"email": 1, "first_name": 1, "last_name": 1, "role": 1}
            ))

            for agent in agents:
                agent["_id"] = str(agent["_id"])
                # Get ticket counts for each agent
                agent["assigned_tickets"] = self.tickets_collection.count_documents({
                    "assigned_to": agent["email"],
                    "status": {"$in": ["open", "in_progress"]}
                })

            return {"agents": agents}

        except Exception as e:
            logger.error(f"Error getting support agents: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving support agents: {str(e)}")

    async def get_dashboard_metrics(self) -> dict:
        """Get support dashboard metrics"""
        try:
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = today - timedelta(days=7)

            # Get various metrics
            metrics: Dict[str, Any] = {
                "open_tickets": self.tickets_collection.count_documents({"status": "open"}),
                "in_progress_tickets": self.tickets_collection.count_documents({"status": "in_progress"}),
                "resolved_today": self.tickets_collection.count_documents({
                    "status": "resolved",
                    "resolved_at": {"$gte": today}
                }),
                "new_tickets_today": self.tickets_collection.count_documents({
                    "created_at": {"$gte": today}
                }),
                "urgent_tickets": self.tickets_collection.count_documents({
                    "priority": "urgent",
                    "status": {"$in": ["open", "in_progress"]}
                }),
                "overdue_tickets": 0,  # Would need SLA definitions
                "weekly_trend": []  # Initialized for type safety
            }

            # Get weekly trend
            weekly_trend = []
            for i in range(7):
                day_start = today - timedelta(days=i)
                day_end = day_start + timedelta(days=1)

                daily_count = self.tickets_collection.count_documents({
                    "created_at": {"$gte": day_start, "$lt": day_end}
                })

                weekly_trend.append({
                    "date": day_start.strftime("%Y-%m-%d"),
                    "tickets": daily_count
                })

            metrics["weekly_trend"] = list(reversed(weekly_trend))

            return metrics

        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving dashboard metrics: {str(e)}")

    async def upload_attachment(self, ticket_id: str, file: UploadFile, current_user) -> dict:
        """Upload attachment to ticket"""
        try:
            # Validate ticket and permissions
            ticket = await self.get_ticket(ticket_id, current_user)

            # Validate file (determine size safely since UploadFile.size may be None)
            try:
                current_pos = file.file.tell()
            except Exception:
                current_pos = 0
            file.file.seek(0, os.SEEK_END)
            file_size = file.file.tell()
            file.file.seek(current_pos)
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                raise HTTPException(status_code=400, detail="File too large (max 10MB)")

            allowed_types = [
                "image/jpeg", "image/png", "image/gif",
                "application/pdf", "text/plain",
                "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ]

            if file.content_type not in allowed_types:
                raise HTTPException(status_code=400, detail="File type not allowed")

            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{ticket_id}_{timestamp}_{file.filename}"

            # For now, return a placeholder URL
            # In production, you would upload to S3/R2 or local storage
            file_url = f"/uploads/support/{filename}"

            # Add attachment to ticket
            obj_id = ObjectId(ticket_id)
            result = self.tickets_collection.update_one(
                {"_id": obj_id},
                {
                    "$push": {
                        "attachments": {
                            "filename": file.filename,
                            "url": file_url,
                            "uploaded_by": current_user.email,
                            "uploaded_at": datetime.utcnow(),
                            "file_size": file_size,
                            "content_type": file.content_type
                        }
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Failed to attach file")

            return {
                "message": "File uploaded successfully",
                "filename": file.filename,
                "url": file_url
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading attachment: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error uploading attachment: {str(e)}")

    def _is_ticket_overdue(self, ticket: dict) -> bool:
        """Check if ticket is overdue based on priority and creation time"""
        try:
            now = datetime.utcnow()
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
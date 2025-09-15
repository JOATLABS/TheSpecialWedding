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
        """Send notification to target audience"""
        try:
            # Get notification
            notification = await self.get_notification(notification_id)

            # For now, this is a placeholder for actual notification sending
            # In a real implementation, you would:
            # 1. Get target audience based on notification.target_audience
            # 2. Send emails/SMS/push notifications
            # 3. Update notification status

            # Mark as sent
            obj_id = ObjectId(notification_id)
            self.notifications_collection.update_one(
                {"_id": obj_id},
                {"$set": {"status": "sent", "sent_at": datetime.utcnow()}}
            )

            return {
                "message": "Notification sent successfully",
                "recipients": notification["total_recipients"]
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
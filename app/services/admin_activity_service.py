"""
Admin Activity Logging Service

Handles tracking and retrieval of root admin activities such as:
- Invitation sent/resent/cancelled
- Planner suspended/activated/deleted
- Subscription changes

This provides audit trail and dashboard display for admin actions.
"""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException

from app.core.database import mongo

logger = logging.getLogger(__name__)


class AdminActivityTypes:
    """Activity type constants for admin actions"""

    # Invitation actions
    INVITATION_SENT = "invitation_sent"
    INVITATION_RESENT = "invitation_resent"
    INVITATION_CANCELLED = "invitation_cancelled"
    INVITATION_COMPLETED = "invitation_completed"
    INVITATION_EXPIRED = "invitation_expired"

    # Planner management
    PLANNER_SUSPENDED = "planner_suspended"
    PLANNER_ACTIVATED = "planner_activated"
    PLANNER_DELETED = "planner_deleted"

    # Subscription management
    SUBSCRIPTION_UPGRADED = "subscription_upgraded"
    SUBSCRIPTION_DOWNGRADED = "subscription_downgraded"
    TRIAL_EXTENDED = "trial_extended"


class AdminActivityService:
    """Service for logging and retrieving admin activities"""

    def __init__(self):
        self.collection = mongo.db["admin_activity_log"]

    async def log_activity(
        self,
        admin_id: str,
        action_type: str,
        title: str,
        message: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """
        Create a new activity log entry.

        Args:
            admin_id: Email of the admin who performed the action
            action_type: Type of action (use AdminActivityTypes constants)
            title: Short title for the activity
            message: Detailed message describing the activity
            entity_type: Type of entity affected (invitation, planner, subscription)
            entity_id: ID of the affected entity
            metadata: Additional context data
        """
        try:
            doc = {
                "admin_id": admin_id,
                "action_type": action_type,
                "title": title,
                "message": message,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata": metadata or {},
                "created_at": datetime.now(UTC),
                "is_read": False,
            }

            result = await self.collection.insert_one(doc)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to log activity")

            logger.info(f"Logged admin activity: {action_type} by {admin_id}")

            return {
                "id": str(result.inserted_id),
                "message": "Activity logged successfully",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error logging admin activity: {e!s}")
            # Don't raise - activity logging should not block main operations
            return {"id": None, "message": f"Failed to log activity: {e!s}"}

    async def get_activity_log(
        self,
        page: int = 1,
        limit: int = 50,
        action_type: str | None = None,
        entity_type: str | None = None,
        admin_id: str | None = None,
    ) -> dict:
        """
        Get paginated activity log.

        Args:
            page: Page number (1-indexed)
            limit: Items per page
            action_type: Filter by action type
            entity_type: Filter by entity type
            admin_id: Filter by admin who performed the action
        """
        try:
            query = {}

            if action_type:
                query["action_type"] = action_type

            if entity_type:
                query["entity_type"] = entity_type

            if admin_id:
                query["admin_id"] = admin_id

            total = await self.collection.count_documents(query)
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit if total > 0 else 0

            cursor = (
                self.collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            activities = []

            async for doc in cursor:
                # Use defensive .get() access to prevent KeyError on malformed documents
                doc_id = doc.get("_id", "")
                created_at = doc.get("created_at")
                activities.append(
                    {
                        "_id": str(doc_id) if doc_id else "",
                        "id": str(doc_id) if doc_id else "",
                        "admin_id": doc.get("admin_id", ""),
                        "action_type": doc.get("action_type", "unknown"),
                        "title": doc.get("title", ""),
                        "message": doc.get("message", ""),
                        "entity_type": doc.get("entity_type"),
                        "entity_id": doc.get("entity_id"),
                        "metadata": doc.get("metadata", {}),
                        "is_read": doc.get("is_read", False),
                        "created_at": created_at.isoformat() if created_at else None,
                    }
                )

            return {
                "activities": activities,
                "total": total,
                "page": page,
                "pages": pages,
            }

        except Exception as e:
            logger.error(f"Error getting activity log: {e!s}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Error retrieving activity log: {e!s}"
            )

    async def get_recent_activities(self, limit: int = 10) -> list[dict]:
        """
        Get most recent activities for dashboard display.

        Args:
            limit: Maximum number of activities to return
        """
        try:
            cursor = self.collection.find().sort("created_at", -1).limit(limit)
            activities = []

            async for doc in cursor:
                # Use defensive .get() access to prevent KeyError on malformed documents
                doc_id = doc.get("_id", "")
                created_at = doc.get("created_at")
                activities.append(
                    {
                        "_id": str(doc_id) if doc_id else "",
                        "id": str(doc_id) if doc_id else "",
                        "admin_id": doc.get("admin_id", ""),
                        "action_type": doc.get("action_type", "unknown"),
                        "title": doc.get("title", ""),
                        "message": doc.get("message", ""),
                        "entity_type": doc.get("entity_type"),
                        "entity_id": doc.get("entity_id"),
                        "metadata": doc.get("metadata", {}),
                        "created_at": created_at.isoformat() if created_at else None,
                    }
                )

            return activities

        except Exception as e:
            logger.error(f"Error getting recent activities: {e!s}", exc_info=True)
            return []

    # ==================== CONVENIENCE METHODS ====================

    async def log_invitation_sent(
        self,
        admin_id: str,
        email: str,
        plan_name: str,
        trial_days: int,
        invitation_id: str | None = None,
    ) -> dict:
        """Log when an invitation is sent to a new planner"""
        return await self.log_activity(
            admin_id=admin_id,
            action_type=AdminActivityTypes.INVITATION_SENT,
            title="Invitation Sent",
            message=f"Sent invitation to {email} with {trial_days}-day trial on {plan_name} plan",
            entity_type="invitation",
            entity_id=invitation_id,
            metadata={"email": email, "plan_name": plan_name, "trial_days": trial_days},
        )

    async def log_invitation_resent(
        self, admin_id: str, email: str, invitation_id: str | None = None
    ) -> dict:
        """Log when an invitation is resent"""
        return await self.log_activity(
            admin_id=admin_id,
            action_type=AdminActivityTypes.INVITATION_RESENT,
            title="Invitation Resent",
            message=f"Resent invitation to {email}",
            entity_type="invitation",
            entity_id=invitation_id,
            metadata={"email": email},
        )

    async def log_invitation_cancelled(
        self,
        admin_id: str,
        email: str,
        reason: str | None = None,
        invitation_id: str | None = None,
    ) -> dict:
        """Log when an invitation is cancelled"""
        msg = f"Cancelled invitation for {email}"
        if reason:
            msg += f" - Reason: {reason}"

        return await self.log_activity(
            admin_id=admin_id,
            action_type=AdminActivityTypes.INVITATION_CANCELLED,
            title="Invitation Cancelled",
            message=msg,
            entity_type="invitation",
            entity_id=invitation_id,
            metadata={"email": email, "reason": reason},
        )

    async def log_invitation_completed(
        self, admin_id: str, email: str, invitation_id: str | None = None
    ) -> dict:
        """Log when a planner completes their account setup from invitation"""
        return await self.log_activity(
            admin_id=admin_id,
            action_type=AdminActivityTypes.INVITATION_COMPLETED,
            title="Invitation Completed",
            message=f"{email} completed account setup",
            entity_type="invitation",
            entity_id=invitation_id,
            metadata={"email": email},
        )

    async def log_planner_suspended(
        self,
        admin_id: str,
        planner_email: str,
        reason: str | None = None,
        planner_id: str | None = None,
    ) -> dict:
        """Log when a planner is suspended"""
        msg = f"Suspended planner {planner_email}"
        if reason:
            msg += f" - Reason: {reason}"

        return await self.log_activity(
            admin_id=admin_id,
            action_type=AdminActivityTypes.PLANNER_SUSPENDED,
            title="Planner Suspended",
            message=msg,
            entity_type="planner",
            entity_id=planner_id,
            metadata={"email": planner_email, "reason": reason},
        )

    async def log_planner_activated(
        self, admin_id: str, planner_email: str, planner_id: str | None = None
    ) -> dict:
        """Log when a planner is activated/unsuspended"""
        return await self.log_activity(
            admin_id=admin_id,
            action_type=AdminActivityTypes.PLANNER_ACTIVATED,
            title="Planner Activated",
            message=f"Activated planner {planner_email}",
            entity_type="planner",
            entity_id=planner_id,
            metadata={"email": planner_email},
        )

    async def log_planner_deleted(
        self, admin_id: str, planner_email: str, planner_id: str | None = None
    ) -> dict:
        """Log when a planner account is deleted"""
        return await self.log_activity(
            admin_id=admin_id,
            action_type=AdminActivityTypes.PLANNER_DELETED,
            title="Planner Deleted",
            message=f"Deleted planner account {planner_email}",
            entity_type="planner",
            entity_id=planner_id,
            metadata={"email": planner_email},
        )


# Singleton instance
admin_activity_service = AdminActivityService()

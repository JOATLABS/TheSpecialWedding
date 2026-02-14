"""
Web Push Notification Service

Sends browser push notifications using the Web Push API (VAPID).
This is the standard browser-based push notification system.

Users just click "Allow" in their browser and receive notifications.
No external apps required.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pywebpush import webpush, WebPushException
from app.core.database import mongo

logger = logging.getLogger(__name__)


class WebPushService:
    """Service for sending Web Push notifications via VAPID"""

    def __init__(self):
        self.vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
        self.vapid_public_key = os.getenv("VAPID_PUBLIC_KEY")
        self.vapid_email = os.getenv("VAPID_EMAIL", "mailto:admin@thespecialwedding.io")

        self.enabled = bool(self.vapid_private_key and self.vapid_public_key)

        if not self.enabled:
            logger.warning("Web Push disabled - VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY not configured")
        else:
            logger.info("Web Push notifications enabled")

    def get_public_key(self) -> Optional[str]:
        """Get the VAPID public key for client subscription"""
        return self.vapid_public_key

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Web Push service health.
        Used by platform monitoring dashboard.
        """
        result = {
            "status": "unknown",
            "configured": self.enabled,
            "enabled": self.enabled,
            "has_public_key": bool(self.vapid_public_key),
            "has_private_key": bool(self.vapid_private_key),
            "vapid_email": self.vapid_email,
            "error": None,
            "total_subscriptions": 0,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

        if not self.enabled:
            result["status"] = "disabled"
            result["error"] = "VAPID keys not configured"
            return result

        try:
            # Count total active subscriptions
            collection = mongo.db["push_subscriptions"]
            total_subs = await collection.count_documents({})
            result["total_subscriptions"] = total_subs
            result["status"] = "healthy"

        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Database check failed: {str(e)}"

        return result

    async def save_subscription(
        self,
        user_id: str,
        subscription: Dict[str, Any],
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Save a push subscription for a user.
        Each user can have multiple subscriptions (different browsers/devices).
        """
        try:
            collection = mongo.db["push_subscriptions"]

            # Extract endpoint to use as unique identifier
            endpoint = subscription.get("endpoint")
            if not endpoint:
                logger.error("Subscription missing endpoint")
                return False

            # Upsert subscription (update if same endpoint exists)
            await collection.update_one(
                {"endpoint": endpoint},
                {
                    "$set": {
                        "user_id": user_id,
                        "subscription": subscription,
                        "user_agent": user_agent,
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$setOnInsert": {
                        "created_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True
            )

            logger.info(f"Saved push subscription for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving push subscription: {e}")
            return False

    async def remove_subscription(self, endpoint: str) -> bool:
        """Remove a push subscription by endpoint"""
        try:
            collection = mongo.db["push_subscriptions"]
            result = await collection.delete_one({"endpoint": endpoint})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error removing push subscription: {e}")
            return False

    async def remove_user_subscriptions(self, user_id: str) -> int:
        """Remove all push subscriptions for a user"""
        try:
            collection = mongo.db["push_subscriptions"]
            result = await collection.delete_many({"user_id": user_id})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error removing user subscriptions: {e}")
            return 0

    async def get_user_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all push subscriptions for a user"""
        try:
            collection = mongo.db["push_subscriptions"]
            cursor = collection.find({"user_id": user_id})
            return await cursor.to_list(length=100)
        except Exception as e:
            logger.error(f"Error getting user subscriptions: {e}")
            return []

    async def send_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        url: Optional[str] = None,
        tag: Optional[str] = None,
        icon: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a push notification to all of a user's subscribed devices.

        Returns dict with success count and any errors.
        """
        if not self.enabled:
            return {"success": False, "error": "Web Push not configured"}

        subscriptions = await self.get_user_subscriptions(user_id)
        if not subscriptions:
            return {"success": False, "error": "No subscriptions found"}

        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url or "/",
            "tag": tag or f"notification-{datetime.now(timezone.utc).timestamp()}",
            "icon": icon or "/icon-192x192.png",
            **(data or {})
        })

        success_count = 0
        errors = []
        expired_endpoints = []

        for sub_doc in subscriptions:
            subscription = sub_doc.get("subscription")
            if not subscription:
                continue

            try:
                webpush(
                    subscription_info=subscription,
                    data=payload,
                    vapid_private_key=self.vapid_private_key,
                    vapid_claims={"sub": self.vapid_email}
                )
                success_count += 1

            except WebPushException as e:
                error_msg = str(e)
                logger.warning(f"WebPush error for {sub_doc.get('endpoint', 'unknown')}: {error_msg}")

                # If subscription expired or invalid, mark for removal
                if e.response and e.response.status_code in [404, 410]:
                    expired_endpoints.append(subscription.get("endpoint"))
                else:
                    errors.append(error_msg)

            except Exception as e:
                logger.error(f"Unexpected error sending push: {e}")
                errors.append(str(e))

        # Clean up expired subscriptions
        for endpoint in expired_endpoints:
            await self.remove_subscription(endpoint)
            logger.info(f"Removed expired subscription: {endpoint[:50]}...")

        return {
            "success": success_count > 0,
            "sent": success_count,
            "total": len(subscriptions),
            "expired_removed": len(expired_endpoints),
            "errors": errors if errors else None
        }

    async def send_to_multiple_users(
        self,
        user_ids: List[str],
        title: str,
        body: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Send notification to multiple users"""
        results = {"total_users": len(user_ids), "success": 0, "failed": 0}

        for user_id in user_ids:
            result = await self.send_notification(user_id, title, body, **kwargs)
            if result.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1

        return results

    async def check_user_subscribed(self, user_id: str) -> bool:
        """Check if a user has any active push subscriptions"""
        try:
            collection = mongo.db["push_subscriptions"]
            count = await collection.count_documents({"user_id": user_id})
            return count > 0
        except Exception:
            return False


# Singleton instance
web_push_service = WebPushService()

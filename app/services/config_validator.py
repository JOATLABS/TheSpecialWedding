"""
Configuration Validator Service

Validates critical environment variables at startup and notifies root admin
of any missing configuration through:
1. Platform notification system (in-app notification)
2. Web Push notification (if admin has subscribed)
"""

import os
import logging
from datetime import datetime
from typing import List, Dict
from app.core.database import mongo

logger = logging.getLogger(__name__)

# Lazy import to avoid circular imports
_web_push_service = None


def _get_web_push_service():
    """Lazy load web push service to avoid circular imports"""
    global _web_push_service
    if _web_push_service is None:
        try:
            from app.services.web_push_service import web_push_service
            _web_push_service = web_push_service
        except ImportError:
            logger.warning("Web Push service not available")
            _web_push_service = False
    return _web_push_service if _web_push_service else None

# Root admin email - the platform developer
ROOT_ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")

# Critical environment variables that MUST be set for the platform to function
CRITICAL_ENV_VARS = {
    "SECRET_KEY": "JWT/session signing key - SECURITY CRITICAL",
    "FRONTEND_URL": "Frontend URL for email links and redirects",
    "NEXT_PUBLIC_API_BASE_URL": "API base URL for backend services",
    "MEDIA_DOMAIN": "Media domain for S3/R2 file URLs",
    "GOOGLE_REDIRECT_URI": "Google OAuth callback URL",
}

# Optional but recommended environment variables
RECOMMENDED_ENV_VARS = {
    "VAPID_PUBLIC_KEY": "Web Push VAPID public key for notifications",
    "VAPID_PRIVATE_KEY": "Web Push VAPID private key for notifications",
    "RESEND_API_KEY": "Email service API key",
    "STRIPE_SECRET_KEY": "Payment processing API key",
    "STRIPE_WEBHOOK_SECRET": "Stripe webhook signature verification",
    "TWILIO_ACCOUNT_SID": "SMS service credentials",
    "S3_ENDPOINT_URL": "S3/R2 storage endpoint URL",
    "S3_ACCESS_KEY_ID": "S3/R2 access key ID",
    "S3_SECRET_ACCESS_KEY": "S3/R2 secret access key",
    "S3_BUCKET_NAME": "S3/R2 bucket name for file uploads",
}


async def validate_environment_and_notify() -> Dict[str, List[str]]:
    """
    Validate environment variables and create root admin notification if any are missing.

    Returns:
        Dict with 'missing_critical' and 'missing_recommended' lists
    """
    missing_critical = []
    missing_recommended = []

    # Check critical vars
    for var_name, description in CRITICAL_ENV_VARS.items():
        if not os.getenv(var_name):
            missing_critical.append(f"{var_name}: {description}")
            logger.error(f"CRITICAL: Missing environment variable {var_name} - {description}")

    # Check recommended vars
    for var_name, description in RECOMMENDED_ENV_VARS.items():
        if not os.getenv(var_name):
            missing_recommended.append(f"{var_name}: {description}")
            logger.warning(f"RECOMMENDED: Missing environment variable {var_name} - {description}")

    # If any critical vars are missing, notify root admin
    if missing_critical:
        await _create_root_admin_notification(
            title="CRITICAL: Missing Environment Configuration",
            message=_build_notification_message(missing_critical, missing_recommended),
            priority="critical"
        )
    elif missing_recommended:
        # Only notify about recommended if there are no critical issues
        await _create_root_admin_notification(
            title="Configuration Warning: Missing Recommended Settings",
            message=_build_notification_message([], missing_recommended),
            priority="high"
        )

    return {
        "missing_critical": missing_critical,
        "missing_recommended": missing_recommended
    }


def _build_notification_message(critical: List[str], recommended: List[str]) -> str:
    """Build a detailed notification message"""
    parts = []

    if critical:
        parts.append("CRITICAL - These environment variables MUST be set:")
        for item in critical:
            parts.append(f"  • {item}")
        parts.append("")

    if recommended:
        parts.append("RECOMMENDED - These variables should be set for full functionality:")
        for item in recommended:
            parts.append(f"  • {item}")
        parts.append("")

    parts.append("Update your .env file or deployment environment variables and restart the server.")

    return "\n".join(parts)


async def _create_root_admin_notification(title: str, message: str, priority: str = "high"):
    """
    Create a notification for the root admin about configuration issues.
    Sends both:
    1. In-app notification (stored in database)
    2. Web Push notification (if admin has subscribed to push notifications)
    """
    # Send Web Push notification for immediate alerting
    await _send_push_alert(title, message, priority)

    try:
        notifications_collection = mongo.db["notifications"]

        # Check if we already have an unread notification about this
        existing = await notifications_collection.find_one({
            "title": title,
            "type": "system_config",
            "status": "active",
            "read_by.user_id": {"$ne": ROOT_ADMIN_EMAIL}
        })

        if existing:
            # Update the existing notification instead of creating a new one
            await notifications_collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "message": message,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info("Updated existing config notification for root admin")
            return

        # Create new notification
        notification = {
            "title": title,
            "message": message,
            "type": "system_config",
            "target_audience": "root_admin",
            "created_by": "system",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_dismissible": True,
            "priority": priority,
            "status": "active",
            "read_by": [],
            "dismissed_by": [],
            "metadata": {
                "source": "config_validator",
                "auto_generated": True
            }
        }

        await notifications_collection.insert_one(notification)
        logger.info(f"Created config notification for root admin: {title}")

    except Exception as e:
        # If we can't create the notification, at least log it prominently
        logger.critical(f"FAILED TO NOTIFY ROOT ADMIN: {title}")
        logger.critical(f"Message: {message}")
        logger.critical(f"Error: {str(e)}")


async def _send_push_alert(title: str, message: str, priority: str):
    """Send Web Push notification for critical config alerts to root admin"""
    web_push = _get_web_push_service()
    if not web_push or not web_push.enabled:
        logger.debug("Web Push service not available for config alert")
        return

    try:
        # Send to root admin if they have subscribed
        await web_push.send_notification(
            user_id=ROOT_ADMIN_EMAIL,
            title=title,
            body=message[:200] + "..." if len(message) > 200 else message,
            url="/admin/platform",
            tag="config-alert"
        )
    except Exception as e:
        logger.warning(f"Failed to send Web Push config alert: {e}")


async def clear_config_notifications():
    """
    Clear resolved configuration notifications.
    Call this when all config issues are fixed.
    """
    try:
        notifications_collection = mongo.db["notifications"]
        result = await notifications_collection.update_many(
            {"type": "system_config", "status": "active"},
            {"$set": {"status": "resolved", "resolved_at": datetime.utcnow()}}
        )
        if result.modified_count > 0:
            logger.info(f"Cleared {result.modified_count} resolved config notifications")
    except Exception as e:
        logger.error(f"Error clearing config notifications: {str(e)}")

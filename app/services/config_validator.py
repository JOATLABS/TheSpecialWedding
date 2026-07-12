"""
Configuration Validator Service

Validates critical environment variables at startup and notifies root admin
of any missing configuration through:
1. Platform notification system (in-app notification)
2. Web Push notification (if admin has subscribed)
"""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List

from app.core.database import mongo
from app.core.settings import settings
from app.services.media_storage import MediaStorage, StorageTarget

logger = logging.getLogger(__name__)

# Lazy import to avoid circular imports
_web_push_service = None
_web_push_checked = False


def _get_web_push_service():
    """Lazy load web push service to avoid circular imports"""
    global _web_push_service, _web_push_checked
    if not _web_push_checked:
        _web_push_checked = True
        try:
            from app.services.web_push_service import web_push_service

            _web_push_service = web_push_service
        except ImportError:
            logger.warning("Web Push service not available")
            _web_push_service = None
    return _web_push_service


# Root admin email - the platform developer
ROOT_ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")

# Critical environment variables that MUST be set for the platform to function
CRITICAL_ENV_VARS = {
    "SECRET_KEY": "JWT/session signing key - SECURITY CRITICAL",
    "FRONTEND_URL": "Frontend URL for email links and redirects",
    "NEXT_PUBLIC_API_BASE_URL": "API base URL for backend services",
    "MEDIA_DOMAIN": "Media domain for S3/R2 file URLs",
    "GOOGLE_REDIRECT_URI": "Google OAuth callback URL",
}

# Optional but recommended environment variables that are not storage-target specific
RECOMMENDED_ENV_VARS = {
    "VAPID_PUBLIC_KEY": "Web Push VAPID public key for notifications",
    "VAPID_PRIVATE_KEY": "Web Push VAPID private key for notifications",
    "RESEND_API_KEY": "Email service API key",
    "STRIPE_SECRET_KEY": "Payment processing API key",
    "STRIPE_WEBHOOK_SECRET": "Stripe webhook signature verification",
    "TWILIO_ACCOUNT_SID": "SMS service credentials",
    "CLOUDFLARE_ACCOUNT_ID": "Cloudflare account identifier for Stream ingest",
    "CLOUDFLARE_STREAM_API_TOKEN": "Cloudflare API token with Stream permissions",
}

STORAGE_RECOMMENDED_ENV_VARS = {
    "S3_ENDPOINT_URL": "S3/R2 storage endpoint URL",
    "S3_ACCESS_KEY_ID": "S3/R2 access key ID",
    "S3_SECRET_ACCESS_KEY": "S3/R2 secret access key",
    "S3_BUCKET_NAME": "S3/R2 bucket name for file uploads",
    "S3_GUEST_MEDIA_BUCKET_NAME": "Dedicated guest memories R2 bucket",
    "S3_AD_BUCKET_NAME": "Dedicated ad-assets R2 bucket",
    "S3_BLOG_BUCKET_NAME": "Dedicated blog-assets R2 bucket",
    "S3_STOREFRONT_STAGING_BUCKET_NAME": "Private storefront-upload staging R2 bucket",
}


def _collect_storage_recommendations(storage: MediaStorage | None = None) -> List[str]:
    recommended: List[str] = []

    if not settings.s3_endpoint_url:
        recommended.append(
            f"S3_ENDPOINT_URL: {STORAGE_RECOMMENDED_ENV_VARS['S3_ENDPOINT_URL']}"
        )
    if not settings.s3_access_key_id:
        recommended.append(
            f"S3_ACCESS_KEY_ID: {STORAGE_RECOMMENDED_ENV_VARS['S3_ACCESS_KEY_ID']}"
        )
    if not settings.s3_secret_access_key:
        recommended.append(
            f"S3_SECRET_ACCESS_KEY: {STORAGE_RECOMMENDED_ENV_VARS['S3_SECRET_ACCESS_KEY']}"
        )
    if not settings.primary_media_bucket_name:
        recommended.append(
            f"S3_BUCKET_NAME: {STORAGE_RECOMMENDED_ENV_VARS['S3_BUCKET_NAME']}"
        )
    if not settings.guest_media_bucket_name:
        recommended.append(
            "S3_GUEST_MEDIA_BUCKET_NAME: "
            f"{STORAGE_RECOMMENDED_ENV_VARS['S3_GUEST_MEDIA_BUCKET_NAME']}"
        )
    if not settings.ad_media_bucket_name:
        recommended.append(
            f"S3_AD_BUCKET_NAME: {STORAGE_RECOMMENDED_ENV_VARS['S3_AD_BUCKET_NAME']}"
        )
    if not settings.blog_media_bucket_name:
        recommended.append(
            f"S3_BLOG_BUCKET_NAME: {STORAGE_RECOMMENDED_ENV_VARS['S3_BLOG_BUCKET_NAME']}"
        )
    if not settings.storefront_staging_bucket_name:
        recommended.append(
            "S3_STOREFRONT_STAGING_BUCKET_NAME: "
            f"{STORAGE_RECOMMENDED_ENV_VARS['S3_STOREFRONT_STAGING_BUCKET_NAME']}"
        )

    if settings.ad_media_bucket_name and not settings.ad_media_domain:
        recommended.append("AD_MEDIA_DOMAIN: Public CDN/domain for ad asset URLs")
    if settings.blog_media_bucket_name and not settings.blog_media_domain:
        recommended.append("BLOG_MEDIA_DOMAIN: Public CDN/domain for blog asset URLs")

    if settings.s3_credentials_configured:
        storage = storage or MediaStorage()
        target_env_map = {
            StorageTarget.PRIMARY: "S3_BUCKET_NAME",
            StorageTarget.GUEST_MEDIA: "S3_GUEST_MEDIA_BUCKET_NAME",
            StorageTarget.AD_ASSETS: "S3_AD_BUCKET_NAME",
            StorageTarget.BLOG_ASSETS: "S3_BLOG_BUCKET_NAME",
            StorageTarget.STOREFRONT_STAGING: "S3_STOREFRONT_STAGING_BUCKET_NAME",
        }
        for target, env_name in target_env_map.items():
            health = storage.target_health(target)
            if health.bucket_name and health.status == "unavailable":
                recommended.append(
                    f"{env_name}: {health.issue} Verify the bucket name and signer permissions."
                )

    return recommended


async def _collect_browser_upload_recommendations(storage: MediaStorage) -> List[str]:
    recommendations: List[str] = []
    browser_origins = settings.browser_upload_origins
    if not browser_origins:
        return recommendations

    target_env_map = {
        StorageTarget.PRIMARY: "S3_BUCKET_NAME",
        StorageTarget.GUEST_MEDIA: "S3_GUEST_MEDIA_BUCKET_NAME",
        StorageTarget.AD_ASSETS: "S3_AD_BUCKET_NAME",
        StorageTarget.BLOG_ASSETS: "S3_BLOG_BUCKET_NAME",
        StorageTarget.STOREFRONT_STAGING: "S3_STOREFRONT_STAGING_BUCKET_NAME",
    }

    for target, env_name in target_env_map.items():
        target_health = storage.target_health(target)
        if not getattr(target_health, "is_ready", target_health.status == "ready"):
            continue

        upload_health = await storage.browser_upload_health(
            target, settings.browser_upload_origins
        )
        if upload_health.status in {"misconfigured", "error"} and upload_health.issue:
            recommendations.append(f"{env_name}: {upload_health.issue}")

    return recommendations


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
            logger.error(
                f"CRITICAL: Missing environment variable {var_name} - {description}"
            )

    # Check recommended vars
    for var_name, description in RECOMMENDED_ENV_VARS.items():
        if not os.getenv(var_name):
            missing_recommended.append(f"{var_name}: {description}")
    storage = MediaStorage() if settings.s3_credentials_configured else None
    missing_recommended.extend(_collect_storage_recommendations(storage))
    if storage is not None:
        missing_recommended.extend(
            await _collect_browser_upload_recommendations(storage)
        )
    for item in missing_recommended:
        logger.warning(f"RECOMMENDED: {item}")

    # If any critical vars are missing, notify root admin
    if missing_critical:
        await _create_root_admin_notification(
            title="CRITICAL: Missing Environment Configuration",
            message=_build_notification_message(missing_critical, missing_recommended),
            priority="critical",
        )
    elif missing_recommended:
        # Only notify about recommended if there are no critical issues
        await _create_root_admin_notification(
            title="Configuration Warning: Missing Recommended Settings",
            message=_build_notification_message([], missing_recommended),
            priority="high",
        )
    else:
        await clear_config_notifications()

    return {
        "missing_critical": missing_critical,
        "missing_recommended": missing_recommended,
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
        parts.append(
            "RECOMMENDED - These variables should be set for full functionality:"
        )
        for item in recommended:
            parts.append(f"  • {item}")
        parts.append("")

    parts.append(
        "Update your .env file or deployment environment variables and restart the server."
    )

    return "\n".join(parts)


async def _create_root_admin_notification(
    title: str, message: str, priority: str = "high"
):
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
        existing = await notifications_collection.find_one(
            {
                "title": title,
                "type": "system_config",
                "status": "active",
                "read_by.user_id": {"$ne": ROOT_ADMIN_EMAIL},
            }
        )

        if existing:
            # Update the existing notification instead of creating a new one
            await notifications_collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "message": message,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
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
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "is_dismissible": True,
            "priority": priority,
            "status": "active",
            "read_by": [],
            "dismissed_by": [],
            "metadata": {"source": "config_validator", "auto_generated": True},
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
            tag="config-alert",
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
            {"$set": {"status": "resolved", "resolved_at": datetime.now(timezone.utc)}},
        )
        if result.modified_count > 0:
            logger.info(
                f"Cleared {result.modified_count} resolved config notifications"
            )
    except Exception as e:
        logger.error(f"Error clearing config notifications: {str(e)}")

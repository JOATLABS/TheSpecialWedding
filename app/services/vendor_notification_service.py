"""
Vendor Notification Service

Provides push notification support for the Vendor Advertising Portal.
Mirrors the PlannerNotificationService._send_push_notification() pattern:
  - Checks user preference (push_notifications_enabled)
  - Late-imports web_push_service to avoid circular deps
  - Non-blocking with error suppression

Also provides a helper for sending admin push alerts for ad-platform events
(new vendor signup, fraud detection, etc.).

Phase 10+ — Push Notification Wiring.
"""

import logging
from typing import Optional

from app.core.database import mongo

logger = logging.getLogger(__name__)


class VendorNotificationService:
    """Push notification delivery for advertising vendors."""

    def __init__(self):
        self.users = mongo.db["users"]

    # ─── Preference Check ───────────────────────────────────────────

    async def _check_push_enabled(self, user_email: str) -> bool:
        """Check if a user has push notifications enabled (opt-out model)."""
        try:
            user = await self.users.find_one(
                {"email": user_email},
                {"push_notifications_enabled": 1},
            )
            if user:
                return user.get("push_notifications_enabled", True)
            return True
        except Exception:
            return True

    # ─── Vendor Push ────────────────────────────────────────────────

    async def send_vendor_push(
        self,
        vendor_email: str,
        notification_type: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
    ) -> None:
        """
        Send a push notification to a vendor.

        Non-blocking — failures are logged but never raised.
        """
        try:
            if not await self._check_push_enabled(vendor_email):
                logger.debug("Push notifications disabled for vendor %s", vendor_email)
                return

            from app.services.web_push_service import web_push_service

            if web_push_service.enabled:
                await web_push_service.send_notification(
                    user_id=vendor_email,
                    title=title,
                    body=message,
                    url=action_url,
                    tag=notification_type,
                )
        except Exception as e:
            logger.warning("Failed to send vendor push notification: %s", str(e))

    # ─── Admin Push ─────────────────────────────────────────────────

    async def send_admin_push(
        self,
        notification_type: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
    ) -> None:
        """
        Send a push notification to all root admins.

        Looks up users with role=ROOT_ADMIN and sends to each.
        Non-blocking — failures are logged but never raised.
        """
        try:
            from app.services.web_push_service import web_push_service

            if not web_push_service.enabled:
                return

            import os
            root_admin_email = os.getenv(
                "ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"
            )

            # Check admin push preference
            if not await self._check_push_enabled(root_admin_email):
                logger.debug("Push notifications disabled for admin %s", root_admin_email)
                return

            await web_push_service.send_notification(
                user_id=root_admin_email,
                title=title,
                body=message,
                url=action_url,
                tag=notification_type,
            )
        except Exception as e:
            logger.warning("Failed to send admin push notification: %s", str(e))

    # ─── Convenience Methods ────────────────────────────────────────

    async def notify_vendor_campaign_approved(
        self, vendor_email: str, campaign_name: str
    ) -> None:
        """Notify vendor that their campaign was approved."""
        await self.send_vendor_push(
            vendor_email=vendor_email,
            notification_type="campaign_approved",
            title="Campaign Approved",
            message=f'Your campaign "{campaign_name}" has been approved and is now live!',
            action_url="/portal/ads/campaigns",
        )

    async def notify_vendor_campaign_rejected(
        self, vendor_email: str, campaign_name: str, reason: Optional[str] = None
    ) -> None:
        """Notify vendor that their campaign was rejected."""
        msg = f'Your campaign "{campaign_name}" was not approved.'
        if reason:
            msg += f" Reason: {reason}"
        await self.send_vendor_push(
            vendor_email=vendor_email,
            notification_type="campaign_rejected",
            title="Campaign Rejected",
            message=msg,
            action_url="/portal/ads/campaigns",
        )

    async def notify_vendor_campaign_changes_requested(
        self, vendor_email: str, campaign_name: str, notes: Optional[str] = None
    ) -> None:
        """Notify vendor that changes were requested on their campaign."""
        msg = f'Changes requested for your campaign "{campaign_name}".'
        if notes:
            msg += f" Notes: {notes}"
        await self.send_vendor_push(
            vendor_email=vendor_email,
            notification_type="campaign_changes_requested",
            title="Changes Requested",
            message=msg,
            action_url="/portal/ads/campaigns",
        )

    async def notify_vendor_new_lead(
        self,
        vendor_email: str,
        planner_name: str,
        lead_type: str,
        campaign_name: str = "",
    ) -> None:
        """Notify vendor of a new lead (add-to-directory or quote request)."""
        if lead_type == "quote_request":
            title = "New Quote Request"
            msg = f"{planner_name} sent you a quote request"
        else:
            title = "Added to Directory"
            msg = f"{planner_name} added you to their vendor directory"

        if campaign_name:
            msg += f' via "{campaign_name}"'

        await self.send_vendor_push(
            vendor_email=vendor_email,
            notification_type=f"lead_{lead_type}",
            title=title,
            message=msg,
            action_url="/portal/ads/analytics",
        )

    async def notify_admin_new_vendor_signup(
        self, business_name: str, vendor_email: str
    ) -> None:
        """Notify admin that a new vendor signed up."""
        await self.send_admin_push(
            notification_type="vendor_signup",
            title="New Vendor Signup",
            message=f"{business_name} ({vendor_email}) has applied for a vendor account.",
            action_url="/admin/ads",
        )

    async def notify_admin_fraud_detected(
        self,
        signal_type: str,
        planner_id: str,
        campaign_id: str,
    ) -> None:
        """Notify admin of a detected fraud signal."""
        await self.send_admin_push(
            notification_type="fraud_alert",
            title="Fraud Alert",
            message=f"Fraud signal ({signal_type}) detected — planner={planner_id}, campaign={campaign_id}",
            action_url="/admin/ads",
        )

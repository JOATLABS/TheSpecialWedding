"""
Ntfy Push Notification Service

Sends push notifications to planners via self-hosted Ntfy server.
Each planner gets a unique topic based on their user ID.

Usage:
    from app.services.ntfy_service import ntfy_service

    await ntfy_service.send_notification(
        planner_id="planner@example.com",
        title="New RSVP",
        message="John Smith confirmed attendance",
        tags=["white_check_mark"],
        priority="default"
    )
"""

import httpx
import hashlib
import logging
from typing import Optional, Literal
from app.core.config import settings

logger = logging.getLogger(__name__)

# Priority levels: 1=min, 2=low, 3=default, 4=high, 5=urgent
PriorityLevel = Literal["min", "low", "default", "high", "urgent"]

# Map notification types to emoji tags
NOTIFICATION_TYPE_TAGS = {
    "form_submission": ["page_facing_up", "inbox_tray"],
    "rsvp_update": ["white_check_mark", "busts_in_silhouette"],
    "guest_message": ["speech_balloon", "envelope"],
    "payment_received": ["money_with_wings", "white_check_mark"],
    "payment_failed": ["x", "credit_card"],
    "contract_signed": ["memo", "black_nib"],
    "vendor_response": ["package", "handshake"],
    "reminder": ["bell", "alarm_clock"],
    "system": ["gear", "information_source"],
}

# Map notification types to priority
NOTIFICATION_TYPE_PRIORITY = {
    "form_submission": "default",
    "rsvp_update": "default",
    "guest_message": "default",
    "payment_received": "high",
    "payment_failed": "urgent",
    "contract_signed": "high",
    "vendor_response": "default",
    "reminder": "default",
    "system": "low",
}


class NtfyNotificationService:
    """Service for sending push notifications via Ntfy"""

    def __init__(self):
        # Get URL from settings, ensure it has https:// prefix
        raw_url = getattr(settings, 'SERVICE_URL_NTFY', None)
        if raw_url:
            # Add https:// if no protocol specified
            if not raw_url.startswith(('http://', 'https://')):
                self.server_url = f"https://{raw_url}"
            else:
                self.server_url = raw_url
        else:
            self.server_url = None

        self.enabled = bool(self.server_url)

        if not self.enabled:
            logger.warning("Ntfy push notifications disabled - SERVICE_URL_NTFY not configured")
        else:
            logger.info(f"Ntfy push notifications enabled: {self.server_url}")

    def _get_planner_topic(self, planner_id: str) -> str:
        """
        Generate a unique topic for a planner.
        Uses a hash to create URL-safe topic names.
        """
        # Create a short hash of the planner ID for privacy
        hash_suffix = hashlib.sha256(planner_id.encode()).hexdigest()[:12]
        return f"wedding-planner-{hash_suffix}"

    def get_subscription_url(self, planner_id: str) -> str:
        """
        Get the subscription URL for a planner to use in the Ntfy app.
        """
        if not self.server_url:
            return ""
        topic = self._get_planner_topic(planner_id)
        return f"{self.server_url}/{topic}"

    async def send_notification(
        self,
        planner_id: str,
        title: str,
        message: str,
        notification_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        priority: Optional[PriorityLevel] = None,
        click_url: Optional[str] = None,
        wedding_name: Optional[str] = None,
    ) -> bool:
        """
        Send a push notification to a planner's Ntfy topic.

        Args:
            planner_id: The planner's email/ID
            title: Notification title
            message: Notification body
            notification_type: Type of notification (for auto tags/priority)
            tags: Custom emoji tags (overrides type-based tags)
            priority: Notification priority (overrides type-based priority)
            click_url: URL to open when notification is clicked
            wedding_name: Wedding name to include in message

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Ntfy disabled, skipping push notification")
            return False

        topic = self._get_planner_topic(planner_id)
        url = f"{self.server_url}/{topic}"

        # Determine tags from notification type if not provided
        if tags is None and notification_type:
            tags = NOTIFICATION_TYPE_TAGS.get(notification_type, ["bell"])
        elif tags is None:
            tags = ["bell"]

        # Determine priority from notification type if not provided
        final_priority: str
        if priority is not None:
            final_priority = priority
        elif notification_type:
            final_priority = NOTIFICATION_TYPE_PRIORITY.get(notification_type, "default")
        else:
            final_priority = "default"

        # Enhance message with wedding name if provided
        if wedding_name:
            message = f"[{wedding_name}] {message}"

        # Build headers
        headers: dict[str, str] = {
            "Title": title,
            "Priority": final_priority,
            "Tags": ",".join(tags),
        }

        if click_url:
            headers["Click"] = click_url

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    content=message,
                    headers=headers,
                )

                if response.status_code == 200:
                    logger.info(f"Push notification sent to topic {topic}: {title}")
                    return True
                else:
                    logger.error(f"Ntfy returned {response.status_code}: {response.text}")
                    return False

        except httpx.TimeoutException:
            logger.error(f"Timeout sending notification to {topic}")
            return False
        except Exception as e:
            logger.error(f"Error sending Ntfy notification: {str(e)}")
            return False

    async def send_rsvp_notification(
        self,
        planner_id: str,
        guest_name: str,
        status: str,
        wedding_name: Optional[str] = None,
        click_url: Optional[str] = None,
    ) -> bool:
        """Send RSVP update notification"""
        status_emoji = "white_check_mark" if status == "confirmed" else "x" if status == "declined" else "question"
        title = f"RSVP: {guest_name}"
        message = f"{guest_name} has {status} their attendance"

        return await self.send_notification(
            planner_id=planner_id,
            title=title,
            message=message,
            notification_type="rsvp_update",
            tags=[status_emoji, "busts_in_silhouette"],
            wedding_name=wedding_name,
            click_url=click_url,
        )

    async def send_form_notification(
        self,
        planner_id: str,
        form_name: str,
        submitter_name: str,
        wedding_name: Optional[str] = None,
        click_url: Optional[str] = None,
    ) -> bool:
        """Send form submission notification"""
        title = f"Form Submitted: {form_name}"
        message = f"{submitter_name} submitted the {form_name} form"

        return await self.send_notification(
            planner_id=planner_id,
            title=title,
            message=message,
            notification_type="form_submission",
            wedding_name=wedding_name,
            click_url=click_url,
        )

    async def send_payment_notification(
        self,
        planner_id: str,
        amount: float,
        payer_name: str,
        success: bool = True,
        wedding_name: Optional[str] = None,
        click_url: Optional[str] = None,
    ) -> bool:
        """Send payment notification"""
        if success:
            title = f"Payment Received: ${amount:.2f}"
            message = f"{payer_name} paid ${amount:.2f}"
            notification_type = "payment_received"
        else:
            title = f"Payment Failed: ${amount:.2f}"
            message = f"Payment of ${amount:.2f} from {payer_name} failed"
            notification_type = "payment_failed"

        return await self.send_notification(
            planner_id=planner_id,
            title=title,
            message=message,
            notification_type=notification_type,
            wedding_name=wedding_name,
            click_url=click_url,
        )

    async def send_contract_notification(
        self,
        planner_id: str,
        signer_name: str,
        wedding_name: Optional[str] = None,
        click_url: Optional[str] = None,
    ) -> bool:
        """Send contract signed notification"""
        title = "Contract Signed"
        message = f"{signer_name} has signed the contract"

        return await self.send_notification(
            planner_id=planner_id,
            title=title,
            message=message,
            notification_type="contract_signed",
            wedding_name=wedding_name,
            click_url=click_url,
        )

    async def send_admin_alert(
        self,
        title: str,
        message: str,
        priority: PriorityLevel = "urgent",
        tags: Optional[list[str]] = None,
    ) -> bool:
        """
        Send an urgent alert to the admin notification topic.
        Used for critical system alerts like missing configuration.

        Uses a fixed admin topic so root admin can subscribe once.
        """
        if not self.enabled:
            logger.warning(f"Ntfy disabled - cannot send admin alert: {title}")
            return False

        # Admin topic from settings (configurable via NTFY_ADMIN_TOPIC env var)
        admin_topic = getattr(settings, 'NTFY_ADMIN_TOPIC', 'wedding-platform-admin')
        url = f"{self.server_url}/{admin_topic}"

        if tags is None:
            tags = ["rotating_light", "warning"]

        headers: dict[str, str] = {
            "Title": title,
            "Priority": priority,
            "Tags": ",".join(tags),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    content=message,
                    headers=headers,
                )

                if response.status_code == 200:
                    logger.info(f"Admin alert sent: {title}")
                    return True
                else:
                    logger.error(f"Ntfy admin alert failed {response.status_code}: {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Error sending admin alert: {str(e)}")
            return False


# Singleton instance
ntfy_service = NtfyNotificationService()

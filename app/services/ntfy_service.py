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
import socket
import uuid
from datetime import datetime
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

    async def health_check(self) -> dict:
        """
        Test ntfy connectivity and return diagnostic info.
        Used by platform monitoring to show ntfy status.
        """
        result = {
            "status": "unknown",
            "configured": bool(self.server_url),
            "enabled": self.enabled,
            "server_url": self.server_url,
            "admin_topic": getattr(settings, 'NTFY_ADMIN_TOPIC', None),
            "dns_resolved": False,
            "connection_successful": False,
            "error": None,
            "checked_at": datetime.utcnow().isoformat()
        }

        if not self.enabled:
            result["status"] = "disabled"
            result["error"] = "SERVICE_URL_NTFY not configured"
            return result

        # Test DNS resolution
        try:
            # Extract hostname from URL (handle http://, https://, and ports)
            hostname = self.server_url.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
            socket.gethostbyname(hostname)
            result["dns_resolved"] = True
        except socket.gaierror as e:
            result["status"] = "error"
            result["error"] = f"DNS resolution failed: {str(e)}"
            return result

        # Test HTTP connectivity
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Just test connectivity - GET request to server root
                response = await client.get(f"{self.server_url}")
                result["connection_successful"] = True
                result["http_status"] = response.status_code

                # ntfy returns 200 for valid topics, 404 for root is OK (means server responding)
                if response.status_code in [200, 404]:
                    result["status"] = "healthy"
                elif response.status_code == 401:
                    result["status"] = "auth_required"
                    result["error"] = "Server requires authentication"
                else:
                    result["status"] = "error"
                    result["error"] = f"HTTP {response.status_code}"

        except httpx.TimeoutException:
            result["status"] = "timeout"
            result["error"] = "Connection timeout (5s)"
        except httpx.ConnectError as e:
            result["status"] = "unreachable"
            result["error"] = f"Connection failed: {str(e)}"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    async def _log_notification_failure(
        self,
        topic: str,
        title: str,
        error_message: str,
        http_status: Optional[int] = None
    ) -> None:
        """Log failed notification to errors collection for admin visibility."""
        try:
            from app.core.database import mongo
            await mongo.db["errors"].insert_one({
                "error_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow(),
                "error_type": "NtfyNotificationFailed",
                "error_message": f"Failed to send push notification: {error_message}",
                "severity": "warning",
                "acknowledged": False,
                "source": "ntfy_service",
                "metadata": {
                    "topic": topic,
                    "title": title,
                    "http_status": http_status,
                    "server_url": self.server_url
                }
            })
        except Exception as e:
            logger.debug(f"Failed to log ntfy error to database: {e}")

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
                    error_msg = f"Ntfy returned {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    await self._log_notification_failure(topic, title, error_msg, response.status_code)
                    return False

        except httpx.TimeoutException:
            error_msg = f"Timeout sending notification to {topic}"
            logger.error(error_msg)
            await self._log_notification_failure(topic, title, error_msg)
            return False
        except Exception as e:
            error_msg = f"Error sending Ntfy notification: {str(e)}"
            logger.error(error_msg)
            await self._log_notification_failure(topic, title, error_msg)
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
            await self._fallback_email_alert(title, message)
            return False

        admin_topic = getattr(settings, 'NTFY_ADMIN_TOPIC', None)
        if not admin_topic:
            logger.warning(f"NTFY_ADMIN_TOPIC not configured - using email fallback: {title}")
            await self._fallback_email_alert(title, message)
            return False

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

    async def _fallback_email_alert(self, title: str, message: str) -> None:
        """Send email, create support ticket, and log to errors collection when Ntfy is unavailable."""
        import os

        root_admin_email = os.getenv("ROOT_ADMIN_EMAIL")

        # Log to errors collection (shows in /admin/platform)
        try:
            from app.core.database import mongo
            error_doc = {
                "error_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow(),
                "error_type": "SystemAlert",
                "error_message": message,
                "severity": "critical",
                "acknowledged": False,
                "source": "ntfy_fallback",
                "request": {
                    "method": "SYSTEM",
                    "path": title,
                },
                "metadata": {
                    "alert_title": title,
                    "ntfy_disabled": not self.enabled,
                    "admin_topic_missing": not getattr(settings, 'NTFY_ADMIN_TOPIC', None),
                }
            }
            await mongo.db["errors"].insert_one(error_doc)
        except Exception as e:
            logger.error(f"Failed to log alert to errors collection: {e}")

        if not root_admin_email:
            logger.error(f"ROOT_ADMIN_EMAIL not configured. Alert: {title}")
            return

        try:
            from app.services.email_service_resend import EmailService
            from app.services.support_service import SupportService

            email_service = EmailService()
            support_service = SupportService()

            html_content = f"""
            <h2>System Alert: {title}</h2>
            <p>{message}</p>
            <hr>
            <p><small>This alert was sent because Ntfy push notifications are not configured.</small></p>
            """
            await email_service.send_email(
                to_email=root_admin_email,
                subject=f"[CRITICAL] {title}",
                html_content=html_content
            )
            logger.info(f"Fallback email sent to {root_admin_email}: {title}")

            ticket_data = {
                "subject": f"[System Alert] {title}",
                "description": message,
                "category": "system",
                "priority": "urgent",
                "status": "open"
            }
            await support_service.create_ticket(ticket_data, created_by="system")
            logger.info(f"Support ticket created for alert: {title}")

        except Exception as e:
            logger.error(f"Failed to send fallback alert: {e}")


# Singleton instance
ntfy_service = NtfyNotificationService()

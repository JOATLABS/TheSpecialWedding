import os
import logging
from typing import Dict, Any
from app.core.sms_config import get_active_sms_provider, SMSProvider

logger = logging.getLogger(__name__)

class SMSService:
    """Unified SMS service that wraps both Twilio and Telnyx providers"""

    def __init__(self):
        self.provider = get_active_sms_provider()
        self.configured = False

        if self.provider == SMSProvider.TWILIO:
            self._init_twilio()
        elif self.provider == SMSProvider.TELNYX:
            self._init_telnyx()
    def _init_twilio(self):
        """Initialize Twilio client"""
        try:
            from twilio.rest import Client
            from twilio.http.http_client import TwilioHttpClient

            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            self.from_phone = os.getenv("TWILIO_PHONE_NUMBER")

            if not all([account_sid, auth_token, self.from_phone]):
                logger.warning("Twilio SMS service not configured. Missing required environment variables.")
                return

            http_client = TwilioHttpClient(pool_connections=False)
            self.client = Client(
                username=account_sid,
                password=auth_token,
                http_client=http_client,
                region=os.getenv("TWILIO_REGION"),
                edge=os.getenv("TWILIO_EDGE")
            )
            self.configured = True
            logger.info("Twilio SMS service initialized successfully")
        except ImportError:
            logger.error("Twilio not installed. Install with: pip install twilio")
        except Exception as e:
            logger.error(f"Failed to initialize Twilio SMS service: {str(e)}")
    def _init_telnyx(self):
        """Initialize Telnyx client"""
        try:
            import telnyx

            api_key = os.getenv("TELNYX_API_KEY")
            self.from_phone = os.getenv("TELNYX_PHONE_NUMBER")

            if not all([api_key, self.from_phone]):
                logger.warning("Telnyx SMS service not configured. Missing required environment variables.")
                return

            telnyx.api_key = api_key
            self.client = telnyx
            self.configured = True
            logger.info("Telnyx SMS service initialized successfully")
        except ImportError:
            logger.error("Telnyx not installed. Install with: pip install telnyx")
        except Exception as e:
            logger.error(f"Failed to initialize Telnyx SMS service: {str(e)}")

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        """
        Send SMS message via the configured provider

        Args:
            to_phone: Phone number to send to (E.164 format recommended)
            message: Message content

        Returns:
            Dict with success status and provider response
        """
        if not self.configured:
            return {
                "success": False,
                "error": f"{self.provider.value} SMS service not configured",
                "provider": self.provider.value
            }
        try:
            if self.provider == SMSProvider.TWILIO:
                return self._send_twilio(to_phone, message)
            elif self.provider == SMSProvider.TELNYX:
                return self._send_telnyx(to_phone, message)
            else:
                return {
                    "success": False,
                    "error": f"Unknown SMS provider: {self.provider.value}",
                    "provider": self.provider.value
                }
        except Exception as e:
            logger.error(f"SMS send failed via {self.provider.value}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "provider": self.provider.value
            }
    def _send_twilio(self, to_phone: str, message: str) -> Dict[str, Any]:
        """Send SMS via Twilio"""
        try:
            message_obj = self.client.messages.create(
                to=to_phone,
                from_=self.from_phone,
                body=message
            )

            logger.info(f"SMS sent via Twilio to {to_phone}, SID: {message_obj.sid}")

            return {
                "success": True,
                "provider": "twilio",
                "message_id": message_obj.sid,
                "status": message_obj.status
            }

        except Exception as e:
            logger.error(f"Twilio SMS failed: {str(e)}")
            raise

    def _send_telnyx(self, to_phone: str, message: str) -> Dict[str, Any]:
        """Send SMS via Telnyx"""
        try:
            response = self.client.Message.create(
                from_=self.from_phone,
                to=to_phone,
                text=message
            )

            logger.info(f"SMS sent via Telnyx to {to_phone}, ID: {response.data.id}")

            return {
                "success": True,
                "provider": "telnyx",
                "message_id": response.data.id,
                "status": response.data.status
            }

        except Exception as e:
            logger.error(f"Telnyx SMS failed: {str(e)}")
            raise

    def get_provider_name(self) -> str:
        """Get the name of the active SMS provider"""
        return self.provider.value

    def is_configured(self) -> bool:
        """Check if SMS service is properly configured"""
        return self.configured
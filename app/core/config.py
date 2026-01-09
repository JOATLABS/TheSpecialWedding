import os
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    PROJECT_NAME: str = "Wedding WebApp"
    VERSION: str = "0.1.0"
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "wedding")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    API_KEY: str = os.getenv("API_KEY", "default-api-key")
    PLATFORM_METRICS_TOKEN: str = (
        os.getenv("PLATFORM_METRICS_TOKEN")
        or os.getenv("API_TOKEN")
        or API_KEY
    )

    # ==================== URL Configuration ====================
    # Single source of truth - NO FALLBACKS
    FRONTEND_URL: Optional[str] = os.getenv("FRONTEND_URL")
    API_BASE_URL: Optional[str] = os.getenv("API_BASE_URL")
    MEDIA_DOMAIN: Optional[str] = os.getenv("MEDIA_DOMAIN")

    # Google Calendar Integration
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: Optional[str] = os.getenv("GOOGLE_REDIRECT_URI")

    # Scopes needed for calendar read/write access
    GOOGLE_CALENDAR_SCOPES: list = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    # Ntfy Push Notification Service
    SERVICE_URL_NTFY: Optional[str] = os.getenv("SERVICE_URL_NTFY")

    def get_required_url(self, url_name: str) -> str:
        """
        Get a required URL from settings.
        Logs an error if missing - root admin should be notified via monitoring.
        """
        url = getattr(self, url_name, None)
        if not url:
            logger.error(f"CRITICAL: Required environment variable {url_name} is not configured!")
            return ""
        return url


settings = Settings()

# Log warnings for missing critical URLs at startup
_critical_urls = ["FRONTEND_URL", "API_BASE_URL", "MEDIA_DOMAIN"]
for _url_name in _critical_urls:
    if not getattr(settings, _url_name, None):
        logger.warning(f"Environment variable {_url_name} is not set - some features may not work correctly")

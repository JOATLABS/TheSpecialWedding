import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "Wedding WebApp"
    VERSION: str = "0.1.0"
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "wedding")
    SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")
    API_KEY: Optional[str] = os.getenv("API_KEY")
    PLATFORM_METRICS_TOKEN: Optional[str] = (
        os.getenv("PLATFORM_METRICS_TOKEN") or os.getenv("API_TOKEN") or API_KEY
    )

    # ==================== URL Configuration ====================
    # Single source of truth - NO FALLBACKS
    # Missing vars will trigger root admin notification at startup
    FRONTEND_URL: Optional[str] = os.getenv("FRONTEND_URL")
    NEXT_PUBLIC_API_BASE_URL: Optional[str] = os.getenv("NEXT_PUBLIC_API_BASE_URL")
    MEDIA_DOMAIN: Optional[str] = os.getenv("MEDIA_DOMAIN")

    def get_required_url(self, url_name: str) -> str:
        """
        Get a required URL configuration value.
        Returns the URL or raises ValueError if not configured.
        """
        url_map = {
            "FRONTEND_URL": self.FRONTEND_URL,
            "NEXT_PUBLIC_API_BASE_URL": self.NEXT_PUBLIC_API_BASE_URL,
            "MEDIA_DOMAIN": self.MEDIA_DOMAIN,
        }
        value = url_map.get(url_name) or os.getenv(url_name)
        if not value:
            raise ValueError(f"{url_name} environment variable is not configured")
        return value

    # Google Calendar Integration
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: Optional[str] = os.getenv("GOOGLE_REDIRECT_URI")
    GOOGLE_OAUTH_STATE_SIGNING_KEY: Optional[str] = os.getenv(
        "GOOGLE_OAUTH_STATE_SIGNING_KEY"
    )
    TOKEN_ENCRYPTION_KEY: Optional[str] = os.getenv("TOKEN_ENCRYPTION_KEY")
    GOOGLE_CALENDAR_DEFAULT_TIMEZONE: str = os.getenv(
        "GOOGLE_CALENDAR_DEFAULT_TIMEZONE", "UTC"
    )
    GOOGLE_APP_PUBLIC_HOME_URL: Optional[str] = os.getenv(
        "GOOGLE_APP_PUBLIC_HOME_URL"
    )
    GOOGLE_APP_PRIVACY_URL: Optional[str] = os.getenv("GOOGLE_APP_PRIVACY_URL")
    GOOGLE_APP_TERMS_URL: Optional[str] = os.getenv("GOOGLE_APP_TERMS_URL")
    GOOGLE_APP_SUPPORT_URL: Optional[str] = os.getenv("GOOGLE_APP_SUPPORT_URL")
    GOOGLE_APP_DATA_DELETION_URL: Optional[str] = os.getenv(
        "GOOGLE_APP_DATA_DELETION_URL"
    )

    # Scopes needed for calendar read/write access
    GOOGLE_CALENDAR_SCOPES: list = [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
    ]

    # Web Push Notification Service (VAPID)
    VAPID_PUBLIC_KEY: Optional[str] = os.getenv("VAPID_PUBLIC_KEY")
    VAPID_PRIVATE_KEY: Optional[str] = os.getenv("VAPID_PRIVATE_KEY")
    VAPID_EMAIL: str = os.getenv("VAPID_EMAIL", "mailto:admin@thespecialwedding.io")


settings = Settings()

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
        os.getenv("PLATFORM_METRICS_TOKEN")
        or os.getenv("API_TOKEN")
        or API_KEY
    )

    # ==================== URL Configuration ====================
    # Single source of truth - NO FALLBACKS
    # Missing vars will trigger root admin notification at startup
    FRONTEND_URL: Optional[str] = os.getenv("FRONTEND_URL")
    NEXT_PUBLIC_API_BASE_URL: Optional[str] = os.getenv("NEXT_PUBLIC_API_BASE_URL")
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

    # Ntfy Push Notification Service - NO FALLBACKS
    SERVICE_URL_NTFY: Optional[str] = os.getenv("SERVICE_URL_NTFY")
    NTFY_ADMIN_TOPIC: Optional[str] = os.getenv("NTFY_ADMIN_TOPIC")


settings = Settings()

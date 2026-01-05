import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

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

    # Google Calendar Integration
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:3000/admin/planner/calendar/callback"
    )
    # Scopes needed for calendar read/write access
    GOOGLE_CALENDAR_SCOPES: list = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    # Ntfy Push Notification Service
    SERVICE_URL_NTFY: Optional[str] = os.getenv("SERVICE_URL_NTFY")


settings = Settings()

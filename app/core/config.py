import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "Wedding WebApp"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
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

    # Calendar aggregator integration (Aurinko)
    AURINKO_API_KEY: Optional[str] = os.getenv("AURINKO_API_KEY")
    AURINKO_APP_ID: Optional[str] = os.getenv("AURINKO_APP_ID")
    AURINKO_CLIENT_ID: Optional[str] = os.getenv("AURINKO_CLIENT_ID")
    AURINKO_CLIENT_SECRET: Optional[str] = os.getenv("AURINKO_CLIENT_SECRET")
    AURINKO_WEBHOOK_SECRET: Optional[str] = os.getenv("AURINKO_WEBHOOK_SECRET")
    AURINKO_API_BASE_URL: str = os.getenv(
        "AURINKO_API_BASE_URL", "https://api.aurinko.io/v1"
    )
    AURINKO_OAUTH_STATE_SIGNING_KEY: Optional[str] = os.getenv(
        "AURINKO_OAUTH_STATE_SIGNING_KEY"
    )
    AURINKO_REDIRECT_URI: Optional[str] = os.getenv("AURINKO_REDIRECT_URI")
    TOKEN_ENCRYPTION_KEY: Optional[str] = os.getenv("TOKEN_ENCRYPTION_KEY")
    CALENDAR_DEFAULT_TIMEZONE: str = os.getenv("CALENDAR_DEFAULT_TIMEZONE", "UTC")
    CALENDAR_WEBHOOK_REPLAY_WINDOW_SECONDS: int = int(
        os.getenv("CALENDAR_WEBHOOK_REPLAY_WINDOW_SECONDS", "300")
    )
    CALENDAR_SHARED_EVENTS_CACHE_SECONDS: int = int(
        os.getenv("CALENDAR_SHARED_EVENTS_CACHE_SECONDS", "60")
    )
    CALENDAR_JOB_BATCH_SIZE: int = int(os.getenv("CALENDAR_JOB_BATCH_SIZE", "25"))
    CALENDAR_JOB_MAX_ATTEMPTS: int = int(os.getenv("CALENDAR_JOB_MAX_ATTEMPTS", "5"))
    CALENDAR_JOB_INITIAL_BACKOFF_SECONDS: int = int(
        os.getenv("CALENDAR_JOB_INITIAL_BACKOFF_SECONDS", "30")
    )
    CALENDAR_IDEMPOTENCY_TTL_HOURS: int = int(
        os.getenv("CALENDAR_IDEMPOTENCY_TTL_HOURS", "24")
    )
    CALENDAR_IDEMPOTENCY_IN_PROGRESS_TIMEOUT_SECONDS: int = int(
        os.getenv("CALENDAR_IDEMPOTENCY_IN_PROGRESS_TIMEOUT_SECONDS", "300")
    )
    CALENDAR_SYNC_RETRY_BATCH_SIZE: int = int(
        os.getenv("CALENDAR_SYNC_RETRY_BATCH_SIZE", "50")
    )
    CALENDAR_SYNC_RETRY_MAX_ATTEMPTS: int = int(
        os.getenv("CALENDAR_SYNC_RETRY_MAX_ATTEMPTS", "5")
    )
    CALENDAR_SYNC_RETRY_INITIAL_BACKOFF_SECONDS: int = int(
        os.getenv("CALENDAR_SYNC_RETRY_INITIAL_BACKOFF_SECONDS", "60")
    )
    CALENDAR_DRIFT_CHECK_BATCH_SIZE: int = int(
        os.getenv("CALENDAR_DRIFT_CHECK_BATCH_SIZE", "50")
    )
    CALENDAR_DRIFT_CHECK_INTERVAL_MINUTES: int = int(
        os.getenv("CALENDAR_DRIFT_CHECK_INTERVAL_MINUTES", "30")
    )

    # Aurinko scopes requested when starting the OAuth connect flow.
    # Calendar.ReadWrite supersedes Calendar.Read — requesting both is
    # redundant and clutters the consent screen, so we ask only for
    # ReadWrite. ``AccountInfo.Read`` was previously included for the
    # identity call at /am/accounts/me, but Aurinko's scope parser
    # rejects it as unknown ("Unable to parse Scopes"). The /am/accounts/me
    # call appears to work on the base account-token grant without an
    # explicit scope — if a future error surfaces a missing identity
    # scope, the canonical name needs to come from the Aurinko docs page
    # at docs.aurinko.io/authentication/authentication-scopes.
    AURINKO_SCOPES: list = [
        "Calendar.ReadWrite",
    ]

    # Web Push Notification Service (VAPID)
    VAPID_PUBLIC_KEY: Optional[str] = os.getenv("VAPID_PUBLIC_KEY")
    VAPID_PRIVATE_KEY: Optional[str] = os.getenv("VAPID_PRIVATE_KEY")
    VAPID_EMAIL: str = os.getenv("VAPID_EMAIL", "mailto:admin@thespecialwedding.io")


settings = Settings()

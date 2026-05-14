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

    # ==================== Umami Analytics (ROOT_ADMIN only) ====================
    # Server-to-server connection to the self-hosted Umami instance (Coolify).
    # Used by /admin/analytics/funnel for the root admin acquisition card.
    # These are NEVER `NEXT_PUBLIC_*` — they must not be exposed to the browser.
    #
    # Auth model:
    #   - Self-hosted Umami v3 has no API-key UI; backend exchanges
    #     UMAMI_USERNAME + UMAMI_PASSWORD for a JWT via POST /api/auth/login,
    #     caches it in Redis, sends as `Authorization: Bearer <token>`.
    #   - If UMAMI_API_KEY is set (e.g. Umami Cloud, or a future self-hosted
    #     build that exposes API keys), it takes precedence and is sent as
    #     `x-umami-api-key` — no login round-trip.
    #
    # UMAMI_API_BASE      — full base of Umami's REST API. Prefer the internal
    #                       Docker hostname so this stays inside the overlay
    #                       network (e.g. http://<umami-service>:3000/api).
    # UMAMI_USERNAME      — login username for the backend's dedicated Umami
    #                       user (best practice: not the human admin user).
    # UMAMI_PASSWORD      — login password for that user.
    # UMAMI_API_KEY       — optional; only used if Umami Cloud or a build that
    #                       supports it. Bypasses the login flow when set.
    # UMAMI_WEBSITE_ID    — same UUID the public tracker uses; kept separate
    #                       from the NEXT_PUBLIC_ version so the backend never
    #                       reads a client-bundled env var.
    # UMAMI_DASHBOARD_URL — public Umami URL for "open in Umami" deep links.
    UMAMI_API_BASE: Optional[str] = os.getenv("UMAMI_API_BASE")
    UMAMI_USERNAME: Optional[str] = os.getenv("UMAMI_USERNAME")
    UMAMI_PASSWORD: Optional[str] = os.getenv("UMAMI_PASSWORD")
    UMAMI_API_KEY: Optional[str] = os.getenv("UMAMI_API_KEY")
    UMAMI_WEBSITE_ID: Optional[str] = os.getenv("UMAMI_WEBSITE_ID")
    UMAMI_DASHBOARD_URL: Optional[str] = os.getenv("UMAMI_DASHBOARD_URL")

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
    GOOGLE_APP_PUBLIC_HOME_URL: Optional[str] = os.getenv("GOOGLE_APP_PUBLIC_HOME_URL")
    GOOGLE_APP_PRIVACY_URL: Optional[str] = os.getenv("GOOGLE_APP_PRIVACY_URL")
    GOOGLE_APP_TERMS_URL: Optional[str] = os.getenv("GOOGLE_APP_TERMS_URL")
    GOOGLE_APP_SUPPORT_URL: Optional[str] = os.getenv("GOOGLE_APP_SUPPORT_URL")
    GOOGLE_APP_DATA_DELETION_URL: Optional[str] = os.getenv(
        "GOOGLE_APP_DATA_DELETION_URL"
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

    # ==================== Aurinko (multi-provider calendar) ====================
    # Aurinko is the unified-mailbox layer that brokers OAuth + tokens for
    # Google, Office 365, iCloud, and EWS/Exchange under a single API. Account
    # tokens are exchanged via the platform basic-auth (client_id/client_secret)
    # and stored encrypted on calendar_connections rows. Webhook payloads are
    # signed with the dashboard "Signing secret" (NOT the client secret) — see
    # docs.aurinko.io/unified-apis/webhooks-api/authentication for the spec.
    # /v1 IS part of the base URL because AurinkoClient builds requests as
    # ``f"{base_url}{path}"`` with paths like "/subscriptions",
    # "/auth/authorize", "/calendars/{id}/events". Verified against the
    # Aurinko API reference at apirefs.aurinko.io — canonical paths start
    # with /v1 and the .env in this repo uses ``https://api.aurinko.io/v1``.
    AURINKO_API_BASE_URL: str = os.getenv(
        "AURINKO_API_BASE_URL", "https://api.aurinko.io/v1"
    )
    AURINKO_APP_ID: Optional[str] = os.getenv("AURINKO_APP_ID")
    AURINKO_CLIENT_ID: Optional[str] = os.getenv("AURINKO_CLIENT_ID")
    AURINKO_CLIENT_SECRET: Optional[str] = os.getenv("AURINKO_CLIENT_SECRET")
    AURINKO_API_KEY: Optional[str] = os.getenv("AURINKO_API_KEY")
    # Signature verification key (dashboard "Signing secret"). MUST NOT be the
    # client secret — clobbering this with the client secret will silently fail
    # every webhook signature check.
    AURINKO_WEBHOOK_SECRET: Optional[str] = os.getenv("AURINKO_WEBHOOK_SECRET")
    AURINKO_REDIRECT_URI: Optional[str] = os.getenv("AURINKO_REDIRECT_URI")
    AURINKO_OAUTH_STATE_SIGNING_KEY: Optional[str] = os.getenv(
        "AURINKO_OAUTH_STATE_SIGNING_KEY"
    )
    # Comma-separated provider list passed to the hosted-auth URL as
    # serviceType=Google,Office365,iCloud,EWS. Order is preserved for the
    # provider selector UI Aurinko renders.
    AURINKO_SCOPES: str = os.getenv(
        "AURINKO_SCOPES",
        "Calendar.Read,Calendar.ReadWrite",
    )
    AURINKO_SERVICE_TYPES: str = os.getenv(
        "AURINKO_SERVICE_TYPES",
        "Google,Office365,iCloud,EWS",
    )
    # Maximum age (in seconds) of an Aurinko webhook delivery before we treat
    # it as a replay. 300s = 5 minutes is the industry-standard window
    # (Stripe, Slack, GitHub all use 5 min). Header timestamp is sourced from
    # X-Aurinko-Request-Timestamp.
    CALENDAR_WEBHOOK_REPLAY_WINDOW_SECONDS: int = int(
        os.getenv("CALENDAR_WEBHOOK_REPLAY_WINDOW_SECONDS", "300")
    )


settings = Settings()

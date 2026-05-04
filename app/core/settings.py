"""
Centralized configuration management using Pydantic Settings
"""

import json
import ipaddress
from enum import Enum
from functools import lru_cache
from typing import Annotated, Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator

# Use pydantic-settings for proper Pydantic v2 compatibility
from pydantic_settings import BaseSettings, NoDecode


class Environment(str, Enum):
    """Application environments"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


def _parse_env_list(value: Any) -> list[str]:
    """Accept JSON arrays or comma-separated strings for list-like env vars."""
    if value in (None, ""):
        return []

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []

        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]

        return [item.strip() for item in stripped.split(",") if item.strip()]

    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]

    return value


def _expand_loopback_origins(origins: list[str]) -> list[str]:
    """
    Normalize local development origins so localhost, 127.0.0.1, and ::1
    work interchangeably on the same port.
    """
    expanded: list[str] = []

    for origin in origins:
        if origin not in expanded:
            expanded.append(origin)

        try:
            parsed = urlparse(origin)
        except Exception:
            continue

        hostname = parsed.hostname
        if hostname not in {"localhost", "127.0.0.1", "::1"}:
            continue

        scheme = parsed.scheme or "http"
        port = parsed.port
        if port is None:
            continue

        for alias in ("localhost", "127.0.0.1", "[::1]"):
            alias_origin = f"{scheme}://{alias}:{port}"
            if alias_origin not in expanded:
                expanded.append(alias_origin)

    return expanded


def _normalize_optional_public_base(value: Any) -> Optional[str]:
    """Normalize optional public base URLs/domains to https://host style."""
    if value in (None, ""):
        return None

    normalized = str(value).strip()
    if not normalized:
        return None

    if normalized.startswith(("http://", "https://")):
        return normalized.rstrip("/")

    return f"https://{normalized}".rstrip("/")


def _normalize_origin(value: Any) -> Optional[str]:
    """Normalize an origin-like value to scheme://host[:port]."""
    if value in (None, ""):
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    if "://" not in candidate:
        return None

    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.hostname:
        return None

    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _normalize_cookie_domain(value: Any) -> Optional[str]:
    """Normalize cookie domains to a consistent, browser-compatible shape."""
    if value in (None, ""):
        return None

    candidate = str(value).strip().lower()
    if not candidate:
        return None

    if "://" in candidate:
        parsed = urlparse(candidate)
        candidate = (parsed.hostname or "").strip().lower()

    candidate = candidate.lstrip(".")
    if not candidate:
        return None

    if "/" in candidate:
        raise ValueError("COOKIE_DOMAIN must be a bare host/domain, not a URL path")

    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        pass

    if candidate == "localhost":
        return candidate

    if "." not in candidate:
        raise ValueError("COOKIE_DOMAIN must contain a valid shared domain")

    return f".{candidate}"


class Settings(BaseSettings):
    """
    Application settings with validation and type checking
    """

    # Environment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, alias="ENVIRONMENT"
    )
    debug: bool = Field(default=False, alias="DEBUG")
    testing: bool = Field(default=False, alias="TESTING")
    # Application
    app_name: str = Field(default="Wedding WebApp API", alias="APP_NAME")
    app_version: str = Field(default="1.3.0", alias="APP_VERSION")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    # URL Configuration - Single source of truth, NO FALLBACKS
    frontend_url: Optional[str] = Field(default=None, alias="FRONTEND_URL")
    api_base_url: Optional[str] = Field(default=None, alias="NEXT_PUBLIC_API_BASE_URL")
    cookie_domain: Optional[str] = Field(default=None, alias="COOKIE_DOMAIN")
    media_domain: Optional[str] = Field(default=None, alias="MEDIA_DOMAIN")
    guest_media_domain: Optional[str] = Field(default=None, alias="GUEST_MEDIA_DOMAIN")
    ad_media_domain: Optional[str] = Field(default=None, alias="AD_MEDIA_DOMAIN")
    blog_media_domain: Optional[str] = Field(default=None, alias="BLOG_MEDIA_DOMAIN")
    form_uploads_domain: Optional[str] = Field(
        default=None, alias="FORM_UPLOADS_DOMAIN"
    )

    # Security
    secret_key: str = Field(
        default="", alias="SECRET_KEY"
    )  # Required - validated below
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    guest_access_session_minutes: int = Field(
        default=180, alias="GUEST_ACCESS_SESSION_MINUTES"
    )
    # CORS
    cors_origins: Annotated[List[str], NoDecode] = Field(
        default=[], alias="CORS_ORIGINS"
    )  # Required - validated below

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret_key is not a weak default"""
        weak_keys = {"changeme", "secret", "password", "test", "development"}
        if v.lower() in weak_keys or len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters and not a common default"
            )
        return v

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: List[str]) -> List[str]:
        """Ensure cors_origins is configured"""
        if not v:
            raise ValueError("CORS_ORIGINS must be configured with at least one origin")
        return _expand_loopback_origins(v)

    cors_credentials: bool = Field(default=True, alias="CORS_CREDENTIALS")
    cors_methods: Annotated[List[str], NoDecode] = Field(
        default=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        alias="CORS_METHODS",
    )
    cors_headers: Annotated[List[str], NoDecode] = Field(
        default=[
            "Authorization",
            "Content-Type",
            "Accept",
            "X-Requested-With",
            "Cache-Control",
            "Pragma",
        ],
        alias="CORS_HEADERS",
    )
    allowed_hosts: Annotated[List[str], NoDecode] = Field(
        default=[], alias="ALLOWED_HOSTS"
    )
    # Database
    mongo_uri: str = Field(default="mongodb://localhost:27017", alias="MONGO_URI")
    mongo_db: str = Field(default="wedding", alias="MONGO_DB")
    mongo_max_pool_size: int = Field(default=10, alias="MONGO_MAX_POOL_SIZE")
    mongo_min_pool_size: int = Field(default=1, alias="MONGO_MIN_POOL_SIZE")
    # Redis Cache
    redis_enabled: bool = Field(default=False, alias="REDIS_ENABLED")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_max_connections: int = Field(default=10, alias="REDIS_MAX_CONNECTIONS")
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_calls: int = Field(default=100, alias="RATE_LIMIT_CALLS")
    rate_limit_period: int = Field(default=60, alias="RATE_LIMIT_PERIOD")
    rate_limit_auth_calls: int = Field(default=10, alias="RATE_LIMIT_AUTH_CALLS")
    rate_limit_auth_period: int = Field(default=60, alias="RATE_LIMIT_AUTH_PERIOD")
    rate_limit_login_ip_calls: int = Field(
        default=30, alias="RATE_LIMIT_LOGIN_IP_CALLS"
    )
    rate_limit_login_principal_calls: int = Field(
        default=5, alias="RATE_LIMIT_LOGIN_PRINCIPAL_CALLS"
    )
    rate_limit_login_period: int = Field(default=60, alias="RATE_LIMIT_LOGIN_PERIOD")
    # Email Service (Resend)
    resend_api_key: Optional[str] = Field(default=None, alias="RESEND_API_KEY")
    resend_from_email: str = Field(
        default="noreply@thespecialwedding.io", alias="RESEND_FROM_EMAIL"
    )
    resend_billing_email: Optional[str] = Field(
        default=None, alias="RESEND_BILLING_EMAIL"
    )
    resend_from_name: str = Field(
        default="The Special Wedding", alias="RESEND_FROM_NAME"
    )
    # SMS Services
    twilio_enabled: bool = Field(default=False, alias="TWILIO_ENABLED")
    twilio_account_sid: Optional[str] = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_from_number: Optional[str] = Field(default=None, alias="TWILIO_FROM_NUMBER")

    telnyx_enabled: bool = Field(default=False, alias="TELNYX_ENABLED")
    telnyx_api_key: Optional[str] = Field(default=None, alias="TELNYX_API_KEY")
    telnyx_from_number: Optional[str] = Field(default=None, alias="TELNYX_FROM_NUMBER")

    # AWS S3 / Cloudflare R2 - variable names match .env exactly
    s3_enabled: bool = Field(default=False, alias="S3_ENABLED")
    s3_access_key_id: Optional[str] = Field(default=None, alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: Optional[str] = Field(
        default=None, alias="S3_SECRET_ACCESS_KEY"
    )
    s3_bucket_name: Optional[str] = Field(default=None, alias="S3_BUCKET_NAME")
    s3_guest_media_bucket_name: Optional[str] = Field(
        default=None, alias="S3_GUEST_MEDIA_BUCKET_NAME"
    )
    s3_ad_bucket_name: Optional[str] = Field(default=None, alias="S3_AD_BUCKET_NAME")
    s3_blog_bucket_name: Optional[str] = Field(
        default=None, alias="S3_BLOG_BUCKET_NAME"
    )
    s3_form_uploads_bucket_name: Optional[str] = Field(
        default=None, alias="S3_FORM_UPLOADS_BUCKET"
    )

    # AI model configuration (env-overridable so a Gemini rename / EOL
    # is a config rollout, not a code deploy).
    ai_gemini_model_primary: Optional[str] = Field(
        default="gemini-2.5-flash", alias="AI_GEMINI_MODEL_PRIMARY"
    )
    ai_gemini_model_economy: Optional[str] = Field(
        default="gemini-2.0-flash", alias="AI_GEMINI_MODEL_ECONOMY"
    )
    ai_low_credit_threshold: float = Field(
        default=0.10, alias="AI_LOW_CREDIT_THRESHOLD"
    )
    s3_region: str = Field(default="auto", alias="S3_REGION")
    s3_endpoint_url: Optional[str] = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_healthcheck_ttl_seconds: int = Field(
        default=60, alias="S3_HEALTHCHECK_TTL_SECONDS"
    )
    cloudflare_account_id: Optional[str] = Field(
        default=None, alias="CLOUDFLARE_ACCOUNT_ID"
    )
    cloudflare_api_token: Optional[str] = Field(
        default=None, alias="CLOUDFLARE_API_TOKEN"
    )
    # Security Features
    # CSRF disabled - JWT Bearer auth is already CSRF-immune (browsers don't auto-attach
    # Authorization headers cross-origin), and guest endpoints use token-based auth
    csrf_enabled: bool = Field(default=False, alias="CSRF_ENABLED")
    csrf_cookie_name: str = Field(default="csrf_token", alias="CSRF_COOKIE_NAME")
    csrf_header_name: str = Field(default="X-CSRF-Token", alias="CSRF_HEADER_NAME")

    security_headers_enabled: bool = Field(
        default=True, alias="SECURITY_HEADERS_ENABLED"
    )
    hsts_enabled: bool = Field(default=True, alias="HSTS_ENABLED")
    csp_enabled: bool = Field(default=True, alias="CSP_ENABLED")

    # Audit Logging
    audit_logging_enabled: bool = Field(default=True, alias="AUDIT_LOGGING_ENABLED")
    audit_log_to_db: bool = Field(default=True, alias="AUDIT_LOG_TO_DB")
    audit_log_to_file: bool = Field(default=True, alias="AUDIT_LOG_TO_FILE")
    audit_log_file: str = Field(default="audit.log", alias="AUDIT_LOG_FILE")
    security_log_to_file: bool = Field(default=True, alias="SECURITY_LOG_TO_FILE")
    security_log_file: str = Field(
        default="logs/security_audit.log", alias="SECURITY_LOG_FILE"
    )
    # Performance
    enable_compression: bool = Field(default=True, alias="ENABLE_COMPRESSION")
    enable_cache_headers: bool = Field(default=True, alias="ENABLE_CACHE_HEADERS")
    static_cache_max_age: int = Field(default=86400, alias="STATIC_CACHE_MAX_AGE")
    # Allows safe (idempotent) GETs on /admin/, /api/, /couple/, etc. to
    # be cached briefly by the browser instead of being marked
    # ``no-store``.  Default off: existing behavior is preserved unless
    # explicitly enabled.  When set, the response Cache-Control becomes
    # ``private, max-age=<safe_get_cache_max_age>`` for safe-method
    # responses; mutations remain ``no-store`` regardless.  The
    # auth-extended Redis cache invalidates on every state-flipping
    # mutation, so a short browser cache window is safe.
    safe_get_cache_enabled: bool = Field(default=False, alias="SAFE_GET_CACHE_ENABLED")
    safe_get_cache_max_age: int = Field(default=5, alias="SAFE_GET_CACHE_MAX_AGE")

    # Monitoring
    enable_metrics: bool = Field(default=False, alias="ENABLE_METRICS")
    metrics_endpoint: str = Field(default="/metrics", alias="METRICS_ENDPOINT")
    enable_api_docs: Optional[bool] = Field(default=None, alias="ENABLE_API_DOCS")

    # Feature Flags
    feature_ai_tools: bool = Field(default=True, alias="FEATURE_AI_TOOLS")
    feature_advanced_reporting: bool = Field(
        default=True, alias="FEATURE_ADVANCED_REPORTING"
    )
    feature_white_label: bool = Field(default=False, alias="FEATURE_WHITE_LABEL")
    feature_custom_integrations: bool = Field(
        default=False, alias="FEATURE_CUSTOM_INTEGRATIONS"
    )
    # Subscription & Billing
    stripe_enabled: bool = Field(default=True, alias="STRIPE_ENABLED")
    stripe_secret_key: Optional[str] = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: Optional[str] = Field(
        default=None, alias="STRIPE_PUBLISHABLE_KEY"
    )
    stripe_webhook_secret: Optional[str] = Field(
        default=None, alias="STRIPE_WEBHOOK_SECRET"
    )

    free_trial_days: int = Field(
        default=0, alias="FREE_TRIAL_DAYS"
    )  # 0 = no free trial

    # Admin Settings
    root_admin_email: Optional[str] = Field(default=None, alias="ROOT_ADMIN_EMAIL")
    root_admin_password: Optional[str] = Field(
        default=None, alias="ROOT_ADMIN_PASSWORD"
    )

    # AI Service (Gemini)
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")

    @property
    def ai_api_key(self) -> Optional[str]:
        """Get the AI API key (supports both GOOGLE_API_KEY and GEMINI_API_KEY)."""
        return self.google_api_key or self.gemini_api_key

    @property
    def ai_enabled(self) -> bool:
        """Check if AI features are enabled (requires Google/Gemini API key)."""
        return bool(self.ai_api_key)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @field_validator(
        "cors_origins", "cors_methods", "cors_headers", "allowed_hosts", mode="before"
    )
    @classmethod
    def parse_string_lists(cls, v):
        """Parse list-like env vars from JSON arrays or comma-separated strings."""
        return _parse_env_list(v)

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse explicit host allowlist from JSON or comma-separated values."""
        return _parse_env_list(v)

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v):
        """Validate and set environment"""
        if isinstance(v, str):
            v = v.lower()
            if v in [e.value for e in Environment]:
                return Environment(v)
        return Environment.DEVELOPMENT

    @field_validator("debug", mode="before")
    @classmethod
    def set_debug_based_on_environment(cls, v, info):
        """Automatically set debug based on environment"""
        if info.data and "environment" in info.data:
            if info.data["environment"] == Environment.PRODUCTION:
                return False
            elif info.data["environment"] == Environment.DEVELOPMENT:
                return True
        return v

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def normalize_cookie_domain(cls, v):
        """Accept either example.com or .example.com for shared auth cookies."""
        return _normalize_cookie_domain(v)

    def get_database_url(self) -> str:
        """Get full database URL with options"""
        base_url = self.mongo_uri
        if "?" in base_url:
            separator = "&"
        else:
            separator = "?"
        options = [
            f"maxPoolSize={self.mongo_max_pool_size}",
            f"minPoolSize={self.mongo_min_pool_size}",
            "retryWrites=true",
            "w=majority",
        ]

        return f"{base_url}{separator}{'&'.join(options)}"

    def get_redis_url(self) -> str:
        """Get Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == Environment.DEVELOPMENT

    def is_testing(self) -> bool:
        """Check if running in testing mode"""
        return self.testing or self.environment == Environment.TESTING

    @property
    def normalized_media_domain(self) -> Optional[str]:
        """Canonical public domain/base URL for primary media assets."""
        return _normalize_optional_public_base(self.media_domain)

    @property
    def normalized_ad_media_domain(self) -> Optional[str]:
        """Canonical public domain/base URL for ad assets."""
        return _normalize_optional_public_base(self.ad_media_domain)

    @property
    def normalized_guest_media_domain(self) -> Optional[str]:
        """Canonical public domain/base URL for guest media assets."""
        return _normalize_optional_public_base(self.guest_media_domain)

    @property
    def normalized_blog_media_domain(self) -> Optional[str]:
        """Canonical public domain/base URL for blog assets."""
        return _normalize_optional_public_base(self.blog_media_domain)

    @property
    def normalized_form_uploads_domain(self) -> Optional[str]:
        """Canonical public domain/base URL for form-attachment uploads."""
        return _normalize_optional_public_base(self.form_uploads_domain)

    @property
    def browser_upload_origins(self) -> List[str]:
        """
        Browser origins that are expected to perform direct presigned uploads.

        This is intentionally frontend-focused, not a copy of the backend CORS
        allowlist. The API origin itself does not need to be present in bucket
        CORS for browser-direct uploads.
        """
        origins: list[str] = []
        api_origin = _normalize_origin(self.api_base_url)
        excluded_origins = (
            set(_expand_loopback_origins([api_origin])) if api_origin else set()
        )
        frontend_origin = _normalize_origin(self.frontend_url)

        def is_loopback_origin(origin: str) -> bool:
            parsed = urlparse(origin)
            return parsed.hostname in {"localhost", "127.0.0.1", "::1"}

        def add_origin(candidate: Any) -> None:
            origin = _normalize_origin(candidate)
            if not origin or origin in excluded_origins:
                return
            if origin not in origins:
                origins.append(origin)

        add_origin(self.frontend_url)
        for origin in self.cors_origins:
            normalized_origin = _normalize_origin(origin)
            if (
                normalized_origin
                and normalized_origin != frontend_origin
                and is_loopback_origin(normalized_origin)
            ):
                continue
            add_origin(origin)

        return origins

    @property
    def primary_media_bucket_name(self) -> Optional[str]:
        """Canonical primary bucket for gallery/profile/document media."""
        return self.s3_bucket_name

    @property
    def guest_media_bucket_name(self) -> Optional[str]:
        """Dedicated guest media bucket."""
        return self.s3_guest_media_bucket_name

    @property
    def ad_media_bucket_name(self) -> Optional[str]:
        """Dedicated ad asset bucket."""
        return self.s3_ad_bucket_name

    @property
    def blog_media_bucket_name(self) -> Optional[str]:
        """Dedicated blog asset bucket."""
        return self.s3_blog_bucket_name

    @property
    def form_uploads_bucket_name(self) -> Optional[str]:
        """Dedicated bucket for FILE_UPLOAD form-field attachments.

        Public form respondents upload here when filling out a form that
        contains FILE_UPLOAD fields. Storage is segregated from primary
        media so a misconfigured public form cannot leak into other
        asset surfaces.
        """
        return self.s3_form_uploads_bucket_name

    @property
    def s3_credentials_configured(self) -> bool:
        """Whether shared S3/R2 credentials are configured."""
        return bool(
            self.s3_endpoint_url and self.s3_access_key_id and self.s3_secret_access_key
        )

    @property
    def api_docs_enabled(self) -> bool:
        """Check if interactive API docs and schema should be exposed."""
        if self.enable_api_docs is not None:
            return self.enable_api_docs
        return not self.is_production()

    @property
    def trusted_hosts(self) -> List[str]:
        """
        Return the Host-header allowlist for TrustedHostMiddleware.

        Explicit ALLOWED_HOSTS entries win, but we also derive safe defaults
        from the configured frontend/API URLs and CORS origins so production
        deployments gain host validation without requiring duplicate config.
        """
        hosts: list[str] = []

        def add_host(candidate: Optional[str]) -> None:
            if not candidate:
                return

            value = str(candidate).strip()
            if not value:
                return

            normalized: Optional[str]
            if "://" in value:
                normalized = urlparse(value).hostname
            elif value.startswith("*.") or value == "*":
                normalized = value
            else:
                normalized = value.split("/")[0].split(":")[0].strip()

            if normalized and normalized not in hosts:
                hosts.append(normalized)

        for host in self.allowed_hosts:
            add_host(host)

        if hosts:
            return hosts

        for url in [self.frontend_url, self.api_base_url, *self.cors_origins]:
            add_host(url)

        if self.is_development() or self.is_testing():
            for dev_host in ("localhost", "127.0.0.1", "testserver"):
                add_host(dev_host)

        return hosts

    def get_feature_flags(self) -> Dict[str, bool]:
        """Get all feature flags"""
        return {
            "ai_tools": self.feature_ai_tools,
            "advanced_reporting": self.feature_advanced_reporting,
            "white_label": self.feature_white_label,
            "custom_integrations": self.feature_custom_integrations,
        }

    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration"""
        return {
            "csrf_enabled": self.csrf_enabled,
            "security_headers_enabled": self.security_headers_enabled,
            "hsts_enabled": self.hsts_enabled,
            "csp_enabled": self.csp_enabled,
            "audit_logging_enabled": self.audit_logging_enabled,
        }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Returns:
        Settings: Application settings
    """
    return Settings()


# Create a global settings instance
settings = get_settings()

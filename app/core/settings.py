"""
Centralized configuration management using Pydantic Settings
"""
# Use pydantic-settings for proper Pydantic v2 compatibility
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator
from typing import List, Optional, Dict, Any
from functools import lru_cache
from enum import Enum


class Environment(str, Enum):
    """Application environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    """
    Application settings with validation and type checking
    """
    # Environment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        alias="ENVIRONMENT"
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
    media_domain: Optional[str] = Field(default=None, alias="MEDIA_DOMAIN")

    # Security
    secret_key: str = Field(default="", alias="SECRET_KEY")  # Required - validated below
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    # CORS
    cors_origins: List[str] = Field(default=[], alias="CORS_ORIGINS")  # Required - validated below

    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret_key is not a weak default"""
        weak_keys = {'changeme', 'secret', 'password', 'test', 'development'}
        if v.lower() in weak_keys or len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters and not a common default')
        return v

    @field_validator('cors_origins')
    @classmethod
    def validate_cors_origins(cls, v: List[str]) -> List[str]:
        """Ensure cors_origins is configured"""
        if not v:
            raise ValueError('CORS_ORIGINS must be configured with at least one origin')
        return v
    cors_credentials: bool = Field(default=True, alias="CORS_CREDENTIALS")
    cors_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        alias="CORS_METHODS"
    )
    cors_headers: List[str] = Field(
        default=["Authorization", "Content-Type", "Accept", "X-Requested-With", "Cache-Control", "Pragma"],
        alias="CORS_HEADERS"
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
    # Email Service (Resend)
    resend_api_key: Optional[str] = Field(default=None, alias="RESEND_API_KEY")
    resend_from_email: str = Field(default="noreply@thespecialwedding.com", alias="RESEND_FROM_EMAIL")
    resend_from_name: str = Field(default="The Special Wedding", alias="RESEND_FROM_NAME")
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
    s3_secret_access_key: Optional[str] = Field(default=None, alias="S3_SECRET_ACCESS_KEY")
    s3_bucket_name: Optional[str] = Field(default=None, alias="S3_BUCKET_NAME")
    s3_region: str = Field(default="auto", alias="S3_REGION")
    s3_endpoint_url: Optional[str] = Field(default=None, alias="S3_ENDPOINT_URL")
    # Security Features
    csrf_enabled: bool = Field(default=True, alias="CSRF_ENABLED")
    csrf_cookie_name: str = Field(default="csrf_token", alias="CSRF_COOKIE_NAME")
    csrf_header_name: str = Field(default="X-CSRF-Token", alias="CSRF_HEADER_NAME")

    security_headers_enabled: bool = Field(default=True, alias="SECURITY_HEADERS_ENABLED")
    hsts_enabled: bool = Field(default=True, alias="HSTS_ENABLED")
    csp_enabled: bool = Field(default=True, alias="CSP_ENABLED")

    # Audit Logging
    audit_logging_enabled: bool = Field(default=True, alias="AUDIT_LOGGING_ENABLED")
    audit_log_to_db: bool = Field(default=True, alias="AUDIT_LOG_TO_DB")
    audit_log_to_file: bool = Field(default=True, alias="AUDIT_LOG_TO_FILE")
    audit_log_file: str = Field(default="audit.log", alias="AUDIT_LOG_FILE")
    # Performance
    enable_compression: bool = Field(default=True, alias="ENABLE_COMPRESSION")
    enable_cache_headers: bool = Field(default=True, alias="ENABLE_CACHE_HEADERS")
    static_cache_max_age: int = Field(default=86400, alias="STATIC_CACHE_MAX_AGE")

    # Monitoring
    enable_metrics: bool = Field(default=False, alias="ENABLE_METRICS")
    metrics_endpoint: str = Field(default="/metrics", alias="METRICS_ENDPOINT")

    # Feature Flags
    feature_ai_tools: bool = Field(default=True, alias="FEATURE_AI_TOOLS")
    feature_advanced_reporting: bool = Field(default=True, alias="FEATURE_ADVANCED_REPORTING")
    feature_white_label: bool = Field(default=False, alias="FEATURE_WHITE_LABEL")
    feature_custom_integrations: bool = Field(default=False, alias="FEATURE_CUSTOM_INTEGRATIONS")
    # Subscription & Billing
    stripe_enabled: bool = Field(default=True, alias="STRIPE_ENABLED")
    stripe_secret_key: Optional[str] = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: Optional[str] = Field(default=None, alias="STRIPE_PUBLISHABLE_KEY")
    stripe_webhook_secret: Optional[str] = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")

    free_trial_days: int = Field(default=0, alias="FREE_TRIAL_DAYS")  # 0 = no free trial

    # Admin Settings
    root_admin_email: Optional[str] = Field(default=None, alias="ROOT_ADMIN_EMAIL")
    root_admin_password: Optional[str] = Field(default=None, alias="ROOT_ADMIN_PASSWORD")

    # Firebase (for messaging)
    firebase_enabled: bool = Field(default=False, alias="FIREBASE_ENABLED")
    firebase_project_id: Optional[str] = Field(default=None, alias="FIREBASE_PROJECT_ID")
    firebase_client_email: Optional[str] = Field(default=None, alias="FIREBASE_CLIENT_EMAIL")
    firebase_private_key: Optional[str] = Field(default=None, alias="FIREBASE_PRIVATE_KEY")
    firebase_private_key_id: Optional[str] = Field(default=None, alias="FIREBASE_PRIVATE_KEY_ID")
    firebase_client_id: Optional[str] = Field(default=None, alias="FIREBASE_CLIENT_ID")
    firebase_token_uri: str = Field(
        default="https://oauth2.googleapis.com/token",
        alias="FIREBASE_TOKEN_URI"
    )
    firebase_auth_uri: str = Field(
        default="https://accounts.google.com/o/oauth2/auth",
        alias="FIREBASE_AUTH_URI"
    )
    firebase_provider_cert_url: str = Field(
        default="https://www.googleapis.com/oauth2/v1/certs",
        alias="FIREBASE_PROVIDER_CERT_URL"
    )
    firebase_client_cert_url: Optional[str] = Field(
        default=None,
        alias="FIREBASE_CLIENT_CERT_URL"
    )
    firebase_service_account_json: Optional[str] = Field(
        default=None,
        alias="FIREBASE_SERVICE_ACCOUNT_JSON"
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
        "extra": "ignore"
    }

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

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

    @model_validator(mode="after")
    def validate_production_security(self):
        """
        Fail-fast validation for critical security settings in production.
        Prevents deployment with insecure defaults.
        """
        if self.environment == Environment.PRODUCTION:
            errors = []

            # SECRET_KEY must not be the default placeholder
            if self.secret_key == "changeme":
                errors.append(
                    "SECRET_KEY cannot be 'changeme' in production. "
                    "Set a secure random key via SECRET_KEY environment variable."
                )

            # CORS_ORIGINS must be explicitly configured
            if not self.cors_origins:
                errors.append(
                    "CORS_ORIGINS cannot be empty in production. "
                    "Set allowed origins via CORS_ORIGINS environment variable "
                    "(comma-separated list of allowed domains)."
                )

            # Warn about wildcard CORS with credentials (security risk)
            if "*" in self.cors_origins and self.cors_credentials:
                errors.append(
                    "CORS_ORIGINS contains '*' with CORS_CREDENTIALS=true. "
                    "This is forbidden by CORS spec and will fail in browsers. "
                    "Specify explicit origins or set CORS_CREDENTIALS=false."
                )

            if errors:
                raise ValueError(
                    f"Production security validation failed:\n" +
                    "\n".join(f"  - {e}" for e in errors)
                )

        return self

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
            "w=majority"
        ]

        return f"{base_url}{separator}{'&'.join(options)}"

    def get_redis_url(self) -> str:
        """Get Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def is_firebase_configured(self) -> bool:
        """Determine whether Firebase integration is enabled and has credentials."""
        if not self.firebase_enabled:
            return False

        if self.firebase_service_account_json:
            return True

        required_fields = [
            self.firebase_project_id,
            self.firebase_client_email,
            self.firebase_private_key,
            self.firebase_private_key_id,
            self.firebase_client_id,
        ]
        return all(required_fields)

    def get_firebase_service_account(self) -> Optional[Dict[str, Any]]:
        """Return service account credentials for Firebase if configured."""
        if not self.is_firebase_configured():
            return None

        if self.firebase_service_account_json:
            try:
                import json
                return json.loads(self.firebase_service_account_json)
            except Exception:
                raise ValueError("Invalid FIREBASE_SERVICE_ACCOUNT_JSON payload; expected valid JSON string")

        private_key = None
        if self.firebase_private_key:
            private_key = self.firebase_private_key.replace("\\n", "\n")

        return {
            "type": "service_account",
            "project_id": self.firebase_project_id,
            "private_key_id": self.firebase_private_key_id,
            "private_key": private_key,
            "client_email": self.firebase_client_email,
            "client_id": self.firebase_client_id,
            "auth_uri": self.firebase_auth_uri,
            "token_uri": self.firebase_token_uri,
            "auth_provider_x509_cert_url": self.firebase_provider_cert_url,
            "client_x509_cert_url": self.firebase_client_cert_url,
        }

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == Environment.DEVELOPMENT

    def is_testing(self) -> bool:
        """Check if running in testing mode"""
        return self.testing or self.environment == Environment.TESTING

    def get_feature_flags(self) -> Dict[str, bool]:
        """Get all feature flags"""
        return {
            "ai_tools": self.feature_ai_tools,
            "advanced_reporting": self.feature_advanced_reporting,
            "white_label": self.feature_white_label,
            "custom_integrations": self.feature_custom_integrations
        }

    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration"""
        return {
            "csrf_enabled": self.csrf_enabled,
            "security_headers_enabled": self.security_headers_enabled,
            "hsts_enabled": self.hsts_enabled,
            "csp_enabled": self.csp_enabled,
            "audit_logging_enabled": self.audit_logging_enabled
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

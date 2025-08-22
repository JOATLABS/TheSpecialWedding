"""
Centralized configuration management using Pydantic Settings
"""
try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional, Dict, Any
from functools import lru_cache
import os
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
    
    # Security
    secret_key: str = Field(..., alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # CORS
    cors_origins: List[str] = Field(default=[], alias="CORS_ORIGINS")
    cors_credentials: bool = Field(default=True, alias="CORS_CREDENTIALS")
    cors_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        alias="CORS_METHODS"
    )
    cors_headers: List[str] = Field(
        default=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
        alias="CORS_HEADERS"
    )
    
    # Database
    mongo_uri: str = Field(..., alias="MONGO_URI")
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
    
    # AWS S3 / Cloudflare R2
    s3_enabled: bool = Field(default=False, alias="S3_ENABLED")
    s3_access_key: Optional[str] = Field(default=None, alias="S3_ACCESS_KEY")
    s3_secret_key: Optional[str] = Field(default=None, alias="S3_SECRET_KEY")
    s3_bucket_name: Optional[str] = Field(default=None, alias="S3_BUCKET_NAME")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
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
    stripe_enabled: bool = Field(default=False, alias="STRIPE_ENABLED")
    stripe_secret_key: Optional[str] = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[str] = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    
    free_trial_days: int = Field(default=14, alias="FREE_TRIAL_DAYS")
    
    # Admin Settings
    root_admin_email: Optional[str] = Field(default=None, alias="ROOT_ADMIN_EMAIL")
    root_admin_password: Optional[str] = Field(default=None, alias="ROOT_ADMIN_PASSWORD")
    
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
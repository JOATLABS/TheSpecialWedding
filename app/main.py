"""
Optimized FastAPI application with enhanced security, performance monitoring, and caching
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import json
from bson import ObjectId
from datetime import datetime

# Import settings and core components
from app.core.settings import settings
from app.core.database import init_database, close_database
from app.core.cache import init_cache, close_cache, cache
from app.core.database_indexes import create_all_indexes

# Import middleware
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.rate_limiting import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.audit_logging import AuditLoggingMiddleware
from app.middleware.performance_monitoring import PerformanceMonitoringMiddleware

# Import API routers
from app.api.health import router as health_router
from app.api.guest import router as guest_router
from app.api.admin_import import router as import_router
from app.api.rspv import router as rsvp_router
from app.api.plus_one import router as plus_one_router
from app.api.admin_rsvp import router as admin_rsvp_router
from app.api.admin_auth import router as auth_router
from app.api.reminder import router as reminder_router
from app.api.reminder_telnyx import router as reminder_telnyx_router
from app.api.reminder_twilio import router as reminder_twilio_router
from app.api.email_reminders import router as email_reminder_router
from app.api.checkin import router as checkin_router
from app.api.gallery_public import router as gallery_public_router
from app.api.gallery_admin import router as gallery_admin_router
from app.api.wedding import router as wedding_router
from app.api.reminder_utilities import router as reminder_utils_router
from app.api.platform_metrics import router as platform_metrics_router
from app.api.user_management import router as user_management_router
from app.api.subscription_management import router as subscription_router
from app.api.saas_config import router as saas_config_router
from app.api.planner_metrics import router as planner_metrics_router
from app.api.forms import router as forms_router
from app.api.guest_verification import router as guest_verification_router
from app.api.trial_management import router as trial_management_router
from app.api.vendor_forms import router as vendor_forms_router
from app.api.vendor_dashboard import router as vendor_dashboard_router
from app.api.vendor_management import router as vendor_management_router
from app.api.budget import router as budget_router
from app.api.otp import router as otp_router
from app.api.notification_management import router as notification_router
from app.api.support_management import router as support_router
from app.api.public_contact import router as public_contact_router
from app.api.stripe_payment import router as stripe_router
from app.api.admin_platform_metrics import router as admin_platform_metrics_router
from app.api.admin_backup import router as backup_router
from app.api.email_webhooks import router as email_webhooks_router
from app.api.twilio_webhooks import router as twilio_webhooks_router
from app.api.billing_jobs import router as billing_jobs_router
from app.api.metering import router as metering_router
from app.api.planner_calendar import router as planner_calendar_router
from app.api.packages import router as packages_router
from app.api.contracts import router as contracts_router
from app.api.autopilot import router as autopilot_router
from app.api.ai import router as ai_router
from app.api.planner_notifications import router as planner_notifications_router
from app.api.tables import router as tables_router
from app.api.config_errors import router as config_errors_router
from app.api.admin_activity import router as admin_activity_router
from app.api.scheduler_jobs import router as scheduler_jobs_router
from app.api.guest_export import router as guest_export_router
from app.api.web_push import router as web_push_router
from app.api.knowledge_base import router as knowledge_base_router
from app.api.vendor_contract_public import router as vendor_contract_public_router
from app.api.notification_stream import router as notification_stream_router
from app.api.team_management import router as team_management_router
from app.api.inbound_emails import router as inbound_emails_router

# Setup logging
logging.basicConfig(
    level=logging.INFO if settings.is_production() else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Register ObjectId and datetime with FastAPI's jsonable_encoder so it knows
# how to serialize them before they reach the JSON response renderer.
from fastapi.encoders import ENCODERS_BY_TYPE
ENCODERS_BY_TYPE[ObjectId] = str


class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles MongoDB ObjectId and datetime objects."""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class MongoJSONResponse(JSONResponse):
    """Custom JSONResponse that serializes MongoDB ObjectId and datetime objects."""
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            cls=MongoJSONEncoder,
            ensure_ascii=False,
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    try:
        # Initialize database connection
        await init_database()
        logger.info("Database initialized")

        # Initialize cache if enabled
        if settings.redis_enabled:
            await init_cache()
            logger.info("Cache initialized")

        # Create database indexes
        await create_all_indexes()
        logger.info("Database indexes created/verified")

        # Run database migrations
        from app.utils.migrations import migration_manager, migration_registry
        migrations = migration_registry.get_all_migrations()
        await migration_manager.run_migrations(migrations)
        logger.info("Database migrations completed")

        # Validate environment configuration and notify root admin of issues
        from app.services.config_validator import validate_environment_and_notify
        config_result = await validate_environment_and_notify()
        if config_result["missing_critical"]:
            logger.critical(f"CRITICAL: {len(config_result['missing_critical'])} required environment variables are missing!")
        elif config_result["missing_recommended"]:
            logger.warning(f"WARNING: {len(config_result['missing_recommended'])} recommended environment variables are missing")
        else:
            logger.info("Environment configuration validated successfully")

        # Alert root admin if email service failed to initialize
        from app.api.email_reminders import email_available
        if not email_available:
            from app.services.config_validator import _create_root_admin_notification
            await _create_root_admin_notification(
                title="Email Service Unavailable",
                message="The email service (Resend) failed to initialize. RSVP invitations, reminders, and notification emails will not work. Check RESEND_API_KEY and server logs for details.",
                priority="critical"
            )
            logger.warning("Email service is not available — root admin notified")

        # Seed Knowledge Base with official platform docs (skips if already seeded)
        try:
            from app.scripts.seed_knowledge_base import seed_knowledge_base
            kb_result = await seed_knowledge_base()
            if kb_result["inserted"] > 0:
                logger.info(f"Knowledge Base seeded: {kb_result['inserted']} articles added")
            else:
                logger.info("Knowledge Base already seeded, no new articles")
        except Exception as e:
            logger.warning(f"Knowledge Base seeding skipped: {e}")

        logger.info("Application startup complete")

        yield  # Application runs here

    finally:
        # Shutdown
        logger.info("Shutting down application")

        # Close database connection
        await close_database()
        logger.info("Database connection closed")

        # Close cache connection
        if settings.redis_enabled:
            await close_cache()
            logger.info("Cache connection closed")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    default_response_class=MongoJSONResponse,
    openapi_tags=[
        {"name": "Health", "description": "Health check operations"},
        {"name": "Auth", "description": "Authentication operations"},
        {"name": "Admin", "description": "Admin operations requiring authentication"},
        {"name": "Guest", "description": "Guest management operations"},
        {"name": "RSVP", "description": "RSVP operations"},
        {"name": "Plus-Ones", "description": "Plus-one management"},
        {"name": "Wedding", "description": "Wedding management"},
        {"name": "Forms", "description": "Custom form operations"},
        {"name": "Gallery", "description": "Photo gallery operations"},
        {"name": "Subscription", "description": "Subscription management"},
        {"name": "Metrics", "description": "Analytics and reporting"}
    ]
)

# ==================== MIDDLEWARE STACK ====================
# Order matters! Add from outermost to innermost

# 1. Error handling (outermost) - Enhanced with MongoDB logging and email alerts
app.add_middleware(
    ErrorHandlerMiddleware,
    enable_email_alerts=settings.is_production()  # Only send emails in production
)

# 2. Security headers
if settings.security_headers_enabled:
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=settings.hsts_enabled,
        enable_csp=settings.csp_enabled
    )

# 3. Audit logging
if settings.audit_logging_enabled:
    app.add_middleware(
        AuditLoggingMiddleware,
        log_to_db=settings.audit_log_to_db,
        log_to_file=settings.audit_log_to_file
    )

# 5. Performance monitoring
if settings.enable_metrics:
    app.add_middleware(
        PerformanceMonitoringMiddleware,
        slow_request_threshold=1.0,
        enable_detailed_logging=not settings.is_production()
    )

# 6. Rate limiting
if settings.rate_limit_enabled:
    app.add_middleware(
        RateLimitMiddleware,
        calls=settings.rate_limit_calls,
        period=settings.rate_limit_period,
        auth_calls=settings.rate_limit_auth_calls,
        auth_period=settings.rate_limit_auth_period
    )

# 7. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
    expose_headers=[
        "Content-Length",
        "Content-Type",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Response-Time"
    ],
    max_age=3600,
)

# 8. Compression (innermost)
if settings.enable_compression:
    app.add_middleware(GZipMiddleware, minimum_size=1000)


# ==================== VALIDATION ERROR LOGGING ====================
# Log detailed Pydantic validation errors so 422s can be debugged from server logs

@app.exception_handler(RequestValidationError)
async def log_validation_errors(request: Request, exc: RequestValidationError):
    body: str = ""
    try:
        raw_body = await request.body()
        body = raw_body.decode("utf-8")[:2000]  # cap at 2 KB for logging
    except Exception as e:
        logger.debug(f"Failed to read request body for logging: {e}")
        body = "<could not read body>"

    logger.warning(
        f"422 Validation Error on {request.method} {request.url.path} | "
        f"body={body} | errors={exc.errors()}"
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# ==================== ROUTE REGISTRATION ====================

# Health and monitoring endpoints
app.include_router(health_router, prefix="/health", tags=["Health"])

# Performance metrics endpoint (if enabled)
if settings.enable_metrics:
    @app.get(settings.metrics_endpoint, tags=["Metrics"])
    async def get_metrics():
        """Get application performance metrics"""
        from app.middleware.performance_monitoring import performance_monitor
        return await performance_monitor.get_metrics()

# Public routes (no authentication required)
app.include_router(guest_router, prefix="/guest", tags=["Guest"])
app.include_router(rsvp_router, prefix="/rsvp", tags=["RSVP"])
app.include_router(plus_one_router, prefix="/plus_one", tags=["Plus-Ones"])
app.include_router(wedding_router, tags=["Wedding"])  # Public wedding endpoints
app.include_router(gallery_public_router, tags=["Gallery"])  # Public gallery endpoints
app.include_router(subscription_router, tags=["Subscription"])  # Public subscription plans
app.include_router(saas_config_router, prefix="/saas", tags=["Subscription"])
app.include_router(public_contact_router, tags=["Sales"])
app.include_router(guest_verification_router, tags=["Guest"])
app.include_router(forms_router, tags=["Forms"])  # Public form submission endpoints
app.include_router(vendor_forms_router, prefix="/vendor-form", tags=["Vendor Forms"])  # Public vendor forms
app.include_router(vendor_dashboard_router, prefix="/vendor", tags=["Vendor Dashboard"])
app.include_router(vendor_management_router, prefix="/admin", tags=["Vendor Contracts"])  # Vendor management endpoints (admin only)
app.include_router(vendor_contract_public_router, prefix="/vendor-contract", tags=["Public Contract Access"])  # Public vendor contract endpoints (no auth required)
app.include_router(user_management_router, tags=["Auth"])  # Public registration endpoints
app.include_router(otp_router, tags=["OTP"])  # Public OTP verification endpoints
app.include_router(email_webhooks_router, tags=["Webhooks"])  # Resend email webhooks
app.include_router(twilio_webhooks_router, tags=["Webhooks"])  # Twilio SMS delivery webhooks
app.include_router(stripe_router, prefix="/stripe", tags=["Payments"])
app.include_router(stripe_router, prefix="/api/stripe", tags=["Payments"])  # Alias so webhooks work at /api/stripe/webhook too
app.include_router(platform_metrics_router, tags=["Metrics"])  # Metrics ingestion and snapshots
app.include_router(contracts_router, tags=["Public Contracts"])  # Public contract viewing/signing
app.include_router(config_errors_router, tags=["System"])  # Public config error reporting
app.include_router(scheduler_jobs_router, prefix="/scheduler", tags=["Scheduler"])  # Scheduled task processing

# Admin routes (authentication required)
# Note: Routers already registered publicly with route-level auth are excluded to avoid duplicate routes
admin_routers = [
    (auth_router, "Auth"),
    (import_router, "Admin"),
    (admin_rsvp_router, "RSVP"),
    (reminder_router, "Admin"),
    (reminder_telnyx_router, "Admin"),
    (reminder_twilio_router, "Admin"),
    (email_reminder_router, "Admin"),
    (checkin_router, "Admin"),
    (gallery_admin_router, "Gallery"),
    (reminder_utils_router, "Admin"),
    # user_management_router - already registered publicly with route-level auth
    # subscription_router - already registered publicly with route-level auth
    # saas_config_router - already registered publicly with route-level auth
    (budget_router, "Budget"),
    (planner_metrics_router, "Metrics"),
    # forms_router - already registered publicly with route-level auth
    (trial_management_router, "Admin"),
    # vendor_forms_router - already registered publicly with route-level auth
    # vendor_management_router - registered at /admin prefix (line ~300)
    (notification_router, "Notifications"),
    (support_router, "Support"),
    (admin_platform_metrics_router, "ROOT_ADMIN"),
    (backup_router, "ROOT_ADMIN"),
    (admin_activity_router, "ROOT_ADMIN"),
    (billing_jobs_router, "Admin"),
    (metering_router, "ROOT_ADMIN"),
    (planner_calendar_router, "Planner Calendar"),
    (packages_router, "Packages"),
    # contracts_router - already registered publicly with route-level auth
    (autopilot_router, "Autopilot"),
    (ai_router, "AI"),
    (planner_notifications_router, "Planner Notifications"),
    (tables_router, "Seating"),
    (guest_export_router, "Guest Export"),
    (web_push_router, "Web Push"),
    (knowledge_base_router, "Knowledge Base"),
    (notification_stream_router, "Notifications SSE"),
    (team_management_router, "Team Management"),
    (inbound_emails_router, "Inbound Emails"),
]

for router, tag in admin_routers:
    app.include_router(router, prefix="/admin", tags=[tag])

# Admin wedding, guest, and plus-one endpoints (special handling to avoid conflicts)
app.include_router(wedding_router, prefix="/admin", tags=["Wedding"])
app.include_router(guest_router, prefix="/admin", tags=["Guest"])
app.include_router(plus_one_router, prefix="/admin/plus-one", tags=["Plus-Ones"])


# ==================== CUSTOM ENDPOINTS ====================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "environment": settings.environment,
        "docs_url": "/docs"
    }


@app.get("/info", tags=["Health"])
async def app_info():
    """Application information"""
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "features": settings.get_feature_flags(),
        "security": {
            "csrf_enabled": settings.csrf_enabled,
            "rate_limiting": settings.rate_limit_enabled,
            "audit_logging": settings.audit_logging_enabled
        }
    }


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    """Add appropriate cache headers"""
    response = await call_next(request)

    # Add cache headers for static content
    if settings.enable_cache_headers:
        path = request.url.path

        if any(path.endswith(ext) for ext in ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2']):
            response.headers["Cache-Control"] = f"public, max-age={settings.static_cache_max_age}"
        elif path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        else:
            response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes for other content
    return response


# Development-only endpoints
if settings.is_development():
    @app.get("/dev/cache-stats", tags=["Metrics"])
    async def cache_stats():
        """Get cache statistics (development only)"""
        if cache.enabled and cache.redis_client:
            try:
                # Get Redis info
                info = await cache.redis_client.info()
                if info:
                    return {
                        "connected_clients": info.get("connected_clients", 0),
                        "used_memory": info.get("used_memory_human", "Unknown"),
                        "keyspace_hits": info.get("keyspace_hits", 0),
                        "keyspace_misses": info.get("keyspace_misses", 0),
                        "hit_rate": (
                            info.get("keyspace_hits", 0) / (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
                        )
                    }
                else:
                    return {"message": "Unable to retrieve cache info"}
            except Exception as e:
                return {"message": f"Cache error: {str(e)}"}
        return {"message": "Cache not enabled"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development(),
        log_level="info"
    )

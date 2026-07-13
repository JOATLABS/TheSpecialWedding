"""
Optimized FastAPI application with enhanced security, performance monitoring, and caching
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import FastAPI, Request
from fastapi.encoders import ENCODERS_BY_TYPE
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.admin_activity import router as admin_activity_router
from app.api.admin_auth import router as auth_router
from app.api.admin_backup import router as backup_router
from app.api.admin_campaigns import router as admin_campaigns_router
from app.api.admin_import import router as import_router
from app.api.admin_analytics import router as admin_analytics_router
from app.api.admin_platform_config import router as admin_platform_config_router
from app.api.admin_platform_metrics import router as admin_platform_metrics_router
from app.api.admin_rsvp import router as admin_rsvp_router
from app.api.ai import router as ai_router
from app.api.autopilot import router as autopilot_router
from app.api.behavioral_analytics import couple_router as couple_analytics_router
from app.api.behavioral_analytics import router as behavioral_analytics_router
from app.api.billing_jobs import router as billing_jobs_router
from app.api.blog import router as blog_router
from app.api.budget import router as budget_router
from app.api.config_errors import router as config_errors_router
from app.api.contracts import (
    client_contracts_admin_router,
    client_contracts_cron_router,
    client_contracts_public_router,
)

# Couple Portal routers
from app.api.couple_auth import router as couple_auth_router
from app.api.couple_invite import router as couple_invite_router
from app.api.couple_notification_stream import (
    router as couple_notification_stream_router,
)
from app.api.couple_portal import router as couple_portal_router
from app.api.email_reminders import router as email_reminder_router
from app.api.aurinko_redirector import router as aurinko_redirector_router
from app.api.calendar_webhooks import router as calendar_webhooks_router
from app.api.email_webhooks import router as email_webhooks_router
from app.api.forms import router as forms_router
from app.api.gallery_admin import router as gallery_admin_router
from app.api.gallery_public import router as gallery_public_router
from app.api.guest import router as guest_router
from app.api.guest_export import router as guest_export_router
from app.api.guest_help import router as guest_help_router
from app.api.guest_memories import router as guest_memories_router
from app.api.guest_verification import router as guest_verification_router

# Import API routers
from app.api.health import router as health_router
from app.api.inbound_emails import router as inbound_emails_router
from app.api.knowledge_base import router as knowledge_base_router
from app.api.metering import router as metering_router
from app.api.notification_management import router as notification_router
from app.api.notification_stream import router as notification_stream_router
from app.api.otp import router as otp_router
from app.api.packages import router as packages_router
from app.api.planner_ad_interactions import router as planner_ad_interactions_router
from app.api.planner_ad_preferences import router as planner_ad_preferences_router
from app.api.planner_calendar import router as planner_calendar_router
from app.api.planner_metrics import router as planner_metrics_router
from app.api.planner_notifications import router as planner_notifications_router
from app.api.platform_metrics import router as platform_metrics_router
from app.api.plus_one import router as plus_one_router
from app.api.public_contact import router as public_contact_router
from app.api.public_knowledge_base import router as public_knowledge_base_router
from app.api.reminder import router as reminder_router
from app.api.reminder_telnyx import router as reminder_telnyx_router
from app.api.reminder_twilio import router as reminder_twilio_router
from app.api.reminder_utilities import router as reminder_utils_router
from app.api.rspv import router as rsvp_router
from app.api.saas_config import router as saas_config_router
from app.api.scheduler_jobs import router as scheduler_jobs_router
from app.api.stripe_payment import router as stripe_router
from app.api.subscription_management import router as subscription_router
from app.api.support_management import router as support_router
from app.api.tables import router as tables_router
from app.api.team_management import router as team_management_router
from app.api.testimonials import router as testimonials_router
from app.api.trial_management import router as trial_management_router
from app.api.twilio_webhooks import router as twilio_webhooks_router
from app.api.user_management import router as user_management_router
from app.api.vendor_campaigns import router as vendor_campaigns_router
from app.api.vendor_contract_public import router as vendor_contract_public_router
from app.api.vendor_dashboard import router as vendor_dashboard_router
from app.api.vendor_forms import router as vendor_forms_router
from app.api.vendor_import import router as vendor_import_router
from app.api.vendor_management import router as vendor_management_router
from app.api.vendor_public import router as vendor_public_router
from app.api.vendor_signup import router as vendor_signup_router
from app.api.storefront import (
    router as storefront_router,
    public_router as storefront_public_router,
)
from app.api.web_push import router as web_push_router
from app.api.wedding import router as wedding_router
from app.core.cache import cache, close_cache, init_cache
from app.core.database import close_database, init_database
from app.core.database_indexes import create_all_indexes

# Import settings and core components
from app.core.settings import settings
from app.middleware.audit_logging import AuditLoggingMiddleware, audit_buffer

# Import middleware
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.performance_monitoring import PerformanceMonitoringMiddleware
from app.middleware.rate_limiting import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

# Setup logging
logging.basicConfig(
    level=logging.INFO if settings.is_production() else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Register ObjectId and datetime with FastAPI's jsonable_encoder so it knows
# how to serialize them before they reach the JSON response renderer.
ENCODERS_BY_TYPE[ObjectId] = str


class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles MongoDB ObjectId and datetime objects."""

    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


class MongoJSONResponse(JSONResponse):
    """Custom JSONResponse that serializes MongoDB ObjectId and datetime objects."""

    def render(self, content) -> bytes:
        return json.dumps(
            content,
            cls=MongoJSONEncoder,
            ensure_ascii=False,
        ).encode("utf-8")


SCHEDULER_LEASE_NAME = "background_schedulers"
SCHEDULER_LEASE_TTL_SECONDS = 180
SCHEDULER_LEADERSHIP_RETRY_SECONDS = 30
SCHEDULER_LEADERSHIP_RENEWAL_SECONDS = max(30, SCHEDULER_LEASE_TTL_SECONDS // 3)


def _build_scheduler_holder_id() -> str:
    """Build a stable per-process identifier for scheduler leadership."""
    import os
    import socket

    return f"{socket.gethostname()}:{os.getpid()}"


async def _acquire_scheduler_leadership(holder_id: str) -> bool:
    """Acquire or renew the singleton scheduler lease in MongoDB."""
    from pymongo import ReturnDocument
    from pymongo.errors import DuplicateKeyError

    from app.core.database import mongo

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=SCHEDULER_LEASE_TTL_SECONDS)

    try:
        lease = await mongo.db["runtime_leases"].find_one_and_update(
            {
                "_id": SCHEDULER_LEASE_NAME,
                "$or": [
                    {"expires_at": {"$lte": now}},
                    {"holder_id": holder_id},
                ],
            },
            {
                "$set": {
                    "holder_id": holder_id,
                    "expires_at": expires_at,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return bool(lease and lease.get("holder_id") == holder_id)
    except DuplicateKeyError:
        return False
    except Exception as e:
        logger.warning(f"Failed to acquire scheduler leadership: {e}")
        return False


async def _release_scheduler_leadership(holder_id: str) -> None:
    """Release the singleton scheduler lease on shutdown."""
    from app.core.database import mongo

    try:
        await mongo.db["runtime_leases"].delete_one(
            {
                "_id": SCHEDULER_LEASE_NAME,
                "holder_id": holder_id,
            }
        )
    except Exception as e:
        logger.warning(f"Failed to release scheduler leadership: {e}")


async def _nightly_rollup_scheduler():
    """
    Background task that runs the ad stats daily rollup at 2:00 AM UTC.

    Computes yesterday's rollup from raw ad_events into ad_stats_daily.
    Idempotent and safe to re-run. Runs continuously until cancelled.
    """
    from app.core.database import mongo

    while True:
        try:
            # Calculate seconds until next 2:00 AM UTC
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()

            logger.info(
                f"Ad rollup scheduler: next run at {next_run.isoformat()} "
                f"({wait_seconds / 3600:.1f}h from now)"
            )
            await asyncio.sleep(wait_seconds)

            # Run the campaign-centric rollup (ad_campaigns -> campaign_day_stats + placement_day_stats)
            from app.services.campaign_rollup_service import CampaignRollupService

            campaign_rollup = CampaignRollupService(mongo.db)
            campaign_result = await campaign_rollup.compute_daily_rollup()
            logger.info(
                f"Nightly campaign rollup complete: "
                f"{campaign_result['campaign_stats']} campaign_day_stats + "
                f"{campaign_result['placement_stats']} placement_day_stats upserted"
            )

            # Auto-complete expired campaigns
            from app.services.vendor_campaign_service import VendorCampaignService

            vendor_svc = VendorCampaignService(mongo.db)
            expired_count = await vendor_svc.complete_expired_campaigns()
            if expired_count > 0:
                logger.info(f"Auto-completed {expired_count} expired campaigns")

            # Run batch fraud detection
            try:
                from app.services.ad_fraud_detection_service import (
                    AdFraudDetectionService,
                )

                fraud_svc = AdFraudDetectionService(mongo.db)
                fraud_result = await fraud_svc.run_batch_detection()
                if fraud_result.get("signals_created", 0) > 0:
                    logger.info(
                        f"Fraud detection: {fraud_result['signals_created']} signals created"
                    )
            except Exception as fraud_err:
                logger.error(f"Batch fraud detection failed: {fraud_err}")

        except asyncio.CancelledError:
            logger.info("Ad rollup scheduler shutting down")
            raise
        except Exception as e:
            logger.error(f"Ad rollup scheduler error: {e}", exc_info=True)
            # Wait 1 hour before retrying on error
            await asyncio.sleep(3600)


async def _monthly_billing_scheduler():
    """
    Background task that finalizes ad billing invoices on the 1st of each month at 6:00 AM UTC.

    Collects all pending CPL charges from the previous month, creates Stripe invoices
    for each vendor, and updates billing records. Idempotent and safe to re-run.
    """
    from app.core.database import mongo

    while True:
        try:
            # Calculate seconds until next 1st of month at 6:00 AM UTC
            now = datetime.now(timezone.utc)
            if now.month == 12:
                next_run = now.replace(
                    year=now.year + 1,
                    month=1,
                    day=1,
                    hour=6,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                next_run = now.replace(
                    month=now.month + 1,
                    day=1,
                    hour=6,
                    minute=0,
                    second=0,
                    microsecond=0,
                )

            wait_seconds = (next_run - now).total_seconds()

            logger.info(
                f"Ad billing scheduler: next invoice finalization at {next_run.isoformat()} "
                f"({wait_seconds / 3600:.1f}h from now)"
            )
            await asyncio.sleep(wait_seconds)

            # Run monthly invoice finalization
            from app.services.ad_billing_service import AdBillingService

            try:
                from app.services.stripe_service import StripeService

                stripe_svc = StripeService(mongo.db)
            except Exception:
                stripe_svc = None

            billing_svc = AdBillingService(mongo.db, stripe_service=stripe_svc)
            result = await billing_svc.finalize_monthly_invoices()
            logger.info(
                f"Monthly ad billing finalization complete: "
                f"{result.get('invoices_created', 0)} invoices created, "
                f"{len(result.get('errors', []))} errors"
            )

        except asyncio.CancelledError:
            logger.info("Ad billing scheduler shutting down")
            raise
        except Exception as e:
            logger.error(f"Ad billing scheduler error: {e}", exc_info=True)
            # Wait 1 hour before retrying on error
            await asyncio.sleep(3600)


async def _form_reminder_scheduler():
    """
    Background task that sends single-shot reminder emails for unsubmitted
    form distributions whose ``reminder_days`` window has elapsed. Runs
    daily at 9:00 AM UTC and is leader-elected like the other schedulers
    so multiple replicas don't double-send.
    """
    from app.services.form_service import FormService

    while True:
        try:
            # Calculate seconds until next 9:00 AM UTC.
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(
                f"Form reminder scheduler: next run at {next_run.isoformat()} "
                f"({wait_seconds / 3600:.1f}h from now)"
            )
            await asyncio.sleep(wait_seconds)

            form_service = FormService()
            result = await form_service.send_form_reminders()
            if result.get("sent") or result.get("failed"):
                logger.info(
                    "Form reminder pass: sent=%s skipped=%s failed=%s",
                    result.get("sent"),
                    result.get("skipped"),
                    result.get("failed"),
                )

        except asyncio.CancelledError:
            logger.info("Form reminder scheduler shutting down")
            raise
        except Exception as e:
            logger.error(f"Form reminder scheduler error: {e}", exc_info=True)
            # Wait an hour and retry on transient failures.
            await asyncio.sleep(3600)


async def _guest_media_maintenance_scheduler():
    """
    Background task that drains durable guest media work:
    - queued / stale video ingest jobs
    - queued / stale export jobs
    """
    from app.services.guest_media_service import guest_media_service

    while True:
        try:
            processed_video_jobs = await guest_media_service.process_pending_video_jobs(
                limit=6
            )
            processed_export_jobs = (
                await guest_media_service.process_pending_export_jobs(limit=1)
            )

            if processed_video_jobs or processed_export_jobs:
                logger.info(
                    "Guest media scheduler processed %s video job(s) and %s export job(s)",
                    processed_video_jobs,
                    processed_export_jobs,
                )

            await asyncio.sleep(15)
        except asyncio.CancelledError:
            logger.info("Guest media scheduler shutting down")
            raise
        except Exception as e:
            logger.error(f"Guest media scheduler error: {e}", exc_info=True)
            await asyncio.sleep(30)


async def _storefront_media_maintenance_scheduler():
    """Recover durable storefront media and inquiry work on the leader."""

    from app.services.storefront_inquiry_service import storefront_inquiry_service
    from app.services.storefront_media_service import storefront_media_service

    while True:
        try:
            processed = await storefront_media_service.sweep_abandoned_assets()
            if processed:
                logger.info(
                    "Storefront media scheduler cleaned %s abandoned asset(s)",
                    processed,
                )
        except asyncio.CancelledError:
            logger.info("Storefront media scheduler shutting down")
            raise
        except Exception as e:
            logger.error(f"Storefront media scheduler error: {e}", exc_info=True)

        try:
            processed_inquiries = (
                await storefront_inquiry_service.process_pending_notifications()
            )
            if processed_inquiries:
                logger.info(
                    "Storefront scheduler recovered %s inquiry notification(s)",
                    processed_inquiries,
                )
        except asyncio.CancelledError:
            logger.info("Storefront media scheduler shutting down")
            raise
        except Exception as e:
            logger.error(f"Storefront inquiry scheduler error: {e}", exc_info=True)

        await asyncio.sleep(60)


def _start_background_scheduler_tasks() -> list[asyncio.Task]:
    """Start one generation of scheduler tasks after leadership is confirmed."""
    rollup_task = asyncio.create_task(_nightly_rollup_scheduler())
    billing_task = asyncio.create_task(_monthly_billing_scheduler())
    guest_media_task = asyncio.create_task(_guest_media_maintenance_scheduler())
    storefront_media_task = asyncio.create_task(
        _storefront_media_maintenance_scheduler()
    )
    form_reminder_task = asyncio.create_task(_form_reminder_scheduler())
    return [
        rollup_task,
        billing_task,
        guest_media_task,
        storefront_media_task,
        form_reminder_task,
    ]


async def _cancel_background_scheduler_tasks(tasks: list[asyncio.Task]) -> None:
    """Cancel and fully drain one scheduler generation before another starts."""
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _background_scheduler_supervisor(holder_id: str) -> None:
    """Continuously acquire, renew, and safely recover scheduler leadership."""
    scheduler_tasks: list[asyncio.Task] = []
    owns_lease = False

    try:
        while True:
            acquired = await _acquire_scheduler_leadership(holder_id)
            if not acquired:
                if owns_lease:
                    logger.warning(
                        "Scheduler leadership lost; cancelling background schedulers"
                    )
                owns_lease = False
                await _cancel_background_scheduler_tasks(scheduler_tasks)
                scheduler_tasks = []
                await asyncio.sleep(SCHEDULER_LEADERSHIP_RETRY_SECONDS)
                continue

            owns_lease = True
            if not scheduler_tasks:
                scheduler_tasks = _start_background_scheduler_tasks()
                logger.info(
                    "Background schedulers started on leader replica %s", holder_id
                )

            await asyncio.sleep(SCHEDULER_LEADERSHIP_RENEWAL_SECONDS)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"Scheduler leadership supervisor failed: {e}", exc_info=True)
    finally:
        await _cancel_background_scheduler_tasks(scheduler_tasks)
        if owns_lease:
            await _release_scheduler_leadership(holder_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    scheduler_supervisor_task: asyncio.Task | None = None
    scheduler_holder_id: str | None = None

    try:
        # Initialize database connection
        await init_database()
        logger.info("Database initialized")

        # Start the audit-log batch buffer.  Once running, the
        # AuditLoggingMiddleware enqueues entries here instead of doing
        # one ``insert_one`` per request, removing a Mongo round trip
        # from every authenticated request.  See AuditLogBuffer in
        # app/middleware/audit_logging.py for durability semantics.
        if settings.audit_log_to_db:
            from app.core.database import mongo

            await audit_buffer.start(mongo.db["audit_logs"])
            logger.info("Audit log buffer started")

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
            logger.critical(
                f"CRITICAL: {len(config_result['missing_critical'])} required environment variables are missing!"
            )
        elif config_result["missing_recommended"]:
            logger.warning(
                f"WARNING: {len(config_result['missing_recommended'])} recommended environment variables are missing"
            )
        else:
            logger.info("Environment configuration validated successfully")

        # Alert root admin if email service failed to initialize
        from app.api.email_reminders import email_available

        if not email_available:
            from app.services.config_validator import _create_root_admin_notification

            await _create_root_admin_notification(
                title="Email Service Unavailable",
                message="The email service (Resend) failed to initialize. RSVP invitations, reminders, and notification emails will not work. Check RESEND_API_KEY and server logs for details.",
                priority="critical",
            )
            logger.warning("Email service is not available — root admin notified")

        # Seed Knowledge Base with official platform docs (skips if already seeded)
        try:
            from app.scripts.seed_knowledge_base import seed_knowledge_base

            kb_result = await seed_knowledge_base()
            if kb_result["inserted"] > 0:
                logger.info(
                    f"Knowledge Base seeded: {kb_result['inserted']} articles added"
                )
            else:
                logger.info("Knowledge Base already seeded, no new articles")
        except Exception as e:
            logger.warning(f"Knowledge Base seeding skipped: {e}")

        # Seed Blog with launch articles (skips if already seeded)
        try:
            from app.scripts.seed_blog import seed_blog

            blog_result = await seed_blog()
            if blog_result["inserted"] > 0:
                logger.info(f"Blog seeded: {blog_result['inserted']} articles added")
            else:
                logger.info("Blog already seeded, no new articles")
        except Exception as e:
            logger.warning(f"Blog seeding skipped: {e}")

        # Start SSE Redis pub/sub listener for cross-worker broadcasting
        from app.services.sse_manager import sse_manager

        await sse_manager.start_redis_listener()
        logger.info("SSE Redis pub/sub listener started")

        # Every replica supervises the singleton lease so a follower can take over.
        scheduler_holder_id = _build_scheduler_holder_id()
        scheduler_supervisor_task = asyncio.create_task(
            _background_scheduler_supervisor(scheduler_holder_id)
        )
        logger.info("Background scheduler leadership supervisor started")

        logger.info("Application startup complete")

        yield  # Application runs here

        # The supervisor drains child schedulers and conditionally releases its lease.
        if scheduler_supervisor_task and not scheduler_supervisor_task.done():
            scheduler_supervisor_task.cancel()
        if scheduler_supervisor_task:
            try:
                await scheduler_supervisor_task
            except asyncio.CancelledError:
                pass

        # Stop SSE Redis listener
        await sse_manager.stop_redis_listener()

        # Drain the audit-log buffer before the DB connection closes.
        # ``shutdown()`` is idempotent — the ``finally`` block below
        # will no-op if we already drained here.
        if settings.audit_log_to_db:
            await audit_buffer.shutdown()
            logger.info("Audit log buffer drained")

    finally:
        # Shutdown
        logger.info("Shutting down application")

        # Also cover failures raised after the supervisor starts but before yield.
        if scheduler_supervisor_task and not scheduler_supervisor_task.done():
            scheduler_supervisor_task.cancel()
            try:
                await scheduler_supervisor_task
            except asyncio.CancelledError:
                pass

        # Defensive: if startup raised before the post-yield drain
        # could run, flush whatever is in the buffer before we close
        # the DB connection.  ``shutdown()`` is idempotent.
        if settings.audit_log_to_db:
            try:
                await audit_buffer.shutdown()
            except Exception as e:
                logger.error(f"Audit buffer shutdown raised in finally: {e}")

        # Close database connection
        await close_database()
        logger.info("Database connection closed")

        # Close cache connection
        if settings.redis_enabled:
            await close_cache()
            logger.info("Cache connection closed")


# Create FastAPI application
api_docs_enabled = settings.api_docs_enabled
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    default_response_class=MongoJSONResponse,
    docs_url="/docs" if api_docs_enabled else None,
    redoc_url="/redoc" if api_docs_enabled else None,
    openapi_url="/openapi.json" if api_docs_enabled else None,
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
        {"name": "Metrics", "description": "Analytics and reporting"},
    ],
)

# ==================== MIDDLEWARE STACK ====================
# Order matters! Add from outermost to innermost

# 1. Error handling (outermost) - Enhanced with MongoDB logging and email alerts
app.add_middleware(
    ErrorHandlerMiddleware,
    enable_email_alerts=settings.is_production(),  # Only send emails in production
)

# 2. Security headers
if settings.security_headers_enabled:
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=settings.hsts_enabled,
        enable_csp=settings.csp_enabled,
    )

# 3. Audit logging
if settings.audit_logging_enabled:
    app.add_middleware(
        AuditLoggingMiddleware,
        log_to_db=settings.audit_log_to_db,
        log_to_file=settings.audit_log_to_file,
    )

# 5. Performance monitoring
if settings.enable_metrics:
    app.add_middleware(
        PerformanceMonitoringMiddleware,
        slow_request_threshold=1.0,
        enable_detailed_logging=not settings.is_production(),
    )

# 6. Rate limiting
if settings.rate_limit_enabled:
    app.add_middleware(
        RateLimitMiddleware,
        calls=settings.rate_limit_calls,
        period=settings.rate_limit_period,
        auth_calls=settings.rate_limit_auth_calls,
        auth_period=settings.rate_limit_auth_period,
        login_ip_calls=settings.rate_limit_login_ip_calls,
        login_principal_calls=settings.rate_limit_login_principal_calls,
        login_period=settings.rate_limit_login_period,
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
        "X-Response-Time",
    ],
    max_age=3600,
)

# 8. Compression (innermost)
# NOTE: GZipMiddleware must NOT compress SSE (text/event-stream) responses.
# Starlette's GZip skips streaming responses without Content-Length, but we add
# an explicit guard: a thin middleware that strips Accept-Encoding for SSE
# requests so the compressor never buffers them.


class SSEGzipBypassMiddleware(BaseHTTPMiddleware):
    """Prevent GZip from buffering SSE responses by removing Accept-Encoding."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.endswith(
            "/notifications/stream"
        ) or request.url.path.endswith("/couple/notifications/stream"):
            # Mutate scope so downstream middleware sees no Accept-Encoding
            headers = dict(request.scope["headers"])
            headers.pop(b"accept-encoding", None)
            request.scope["headers"] = list(headers.items())
        return await call_next(request)


if settings.enable_compression:
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(SSEGzipBypassMiddleware)


# ==================== VALIDATION ERROR LOGGING ====================
# Log detailed Pydantic validation errors so 422s can be debugged from server logs


def _sanitize_validation_errors(errors: list[dict]) -> list[dict]:
    """Make Pydantic v2's exc.errors() JSON-serializable.

    Pydantic v2 places the raw exception instance in ``ctx['error']`` (e.g.
    a ``ValueError`` raised from a ``@model_validator``). ``JSONResponse``
    can't serialize that, and the resulting ``TypeError`` was being caught
    by the global error handler and turned into a 500 — masking the real
    422. Convert any non-JSON-friendly values to strings.
    """
    sanitized: list[dict] = []
    for err in errors:
        clean = {k: v for k, v in err.items() if k != "ctx"}
        ctx = err.get("ctx")
        if isinstance(ctx, dict):
            clean["ctx"] = {
                k: (str(v) if isinstance(v, BaseException) else v)
                for k, v in ctx.items()
            }
        sanitized.append(clean)
    return sanitized


@app.exception_handler(RequestValidationError)
async def log_validation_errors(request: Request, exc: RequestValidationError):
    body: str = ""
    try:
        raw_body = await request.body()
        body = raw_body.decode("utf-8")[:2000]  # cap at 2 KB for logging
    except Exception as e:
        logger.debug(f"Failed to read request body for logging: {e}")
        body = "<could not read body>"

    sanitized = _sanitize_validation_errors(exc.errors())

    logger.warning(
        f"422 Validation Error on {request.method} {request.url.path} | "
        f"body={body} | errors={sanitized}"
    )
    return JSONResponse(
        status_code=422,
        content={"detail": sanitized},
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
app.include_router(
    subscription_router, tags=["Subscription"]
)  # Public subscription plans
app.include_router(saas_config_router, prefix="/saas", tags=["Subscription"])
app.include_router(testimonials_router, prefix="/saas", tags=["Testimonials"])
app.include_router(public_contact_router, tags=["Sales"])
app.include_router(public_knowledge_base_router, tags=["Public Knowledge Base"])
app.include_router(guest_help_router, tags=["Guest"])
app.include_router(guest_verification_router, tags=["Guest"])
app.include_router(forms_router, tags=["Forms"])  # Legacy + public form endpoints
app.include_router(
    forms_router, prefix="/admin", tags=["Forms"]
)  # Canonical admin form endpoints used by the frontend
app.include_router(
    vendor_forms_router, prefix="/vendor-form", tags=["Vendor Forms"]
)  # Public vendor forms
app.include_router(vendor_dashboard_router, prefix="/vendor", tags=["Vendor Dashboard"])
app.include_router(
    vendor_management_router, prefix="/admin", tags=["Vendor Contracts"]
)  # Vendor management endpoints (admin only)
app.include_router(
    vendor_import_router, prefix="/admin", tags=["Vendor Import"]
)  # Vendor scraper import (root admin only)
app.include_router(
    behavioral_analytics_router, prefix="/admin", tags=["Behavioral Analytics"]
)  # Product metrics (WAU, funnels, retention)
app.include_router(
    vendor_contract_public_router,
    prefix="/vendor-contract",
    tags=["Public Contract Access"],
)  # Public vendor contract endpoints (no auth required)
app.include_router(
    user_management_router, tags=["Auth"]
)  # Public registration endpoints
app.include_router(otp_router, tags=["OTP"])  # Public OTP verification endpoints
app.include_router(storefront_public_router, prefix="/api", tags=["storefront"])
app.include_router(email_webhooks_router, tags=["Webhooks"])  # Resend email webhooks
app.include_router(
    twilio_webhooks_router, tags=["Webhooks"]
)  # Twilio SMS delivery webhooks
app.include_router(
    calendar_webhooks_router, tags=["Webhooks"]
)  # Aurinko calendar-change webhooks at POST /api/calendar/webhooks/aurinko
app.include_router(
    aurinko_redirector_router, tags=["Aurinko OAuth"]
)  # Intermediate redirect for Aurinko's Google OAuth flow at
#   GET /v1/auth/callback — DNS aurinko.thespecialwedding.io should
#   CNAME to this host for prod (see docs.aurinko.io OAuth flow page).
app.include_router(stripe_router, prefix="/stripe", tags=["Payments"])
app.include_router(
    stripe_router, prefix="/api/stripe", tags=["Payments"]
)  # Alias so webhooks work at /api/stripe/webhook too
app.include_router(
    platform_metrics_router, tags=["Metrics"]
)  # Metrics ingestion and snapshots
app.include_router(
    client_contracts_public_router, tags=["Public Contracts"]
)  # Public couple contract viewing/signing and portal access
app.include_router(
    client_contracts_cron_router, tags=["Cron"]
)  # Internal couple-contract cron endpoints
app.include_router(
    config_errors_router, tags=["System"]
)  # Public config error reporting
app.include_router(
    scheduler_jobs_router, prefix="/scheduler", tags=["Scheduler"]
)  # Scheduled task processing

app.include_router(
    vendor_campaigns_router, tags=["Vendor Campaigns"]
)  # Vendor campaign portal (has own /portal/ads prefix)
app.include_router(
    admin_campaigns_router, tags=["Admin Campaigns"]
)  # Admin campaign management (has own /admin/ads/campaigns prefix)
app.include_router(
    planner_ad_interactions_router, tags=["Planner Ad Interactions"]
)  # Planner ad interaction flows (has own /planner/ads prefix)
app.include_router(
    admin_platform_config_router, tags=["Admin Platform Config"]
)  # Platform config, pipeline status, data export (has own /admin/ads/config prefix)
app.include_router(
    planner_ad_preferences_router, tags=["Planner Ad Preferences"]
)  # Planner ad preferences (has own /planner/ads/preferences prefix)
app.include_router(
    vendor_public_router, tags=["Public Vendors"]
)  # Public vendor profiles (has own /api/v1/vendors prefix)
app.include_router(
    vendor_signup_router, tags=["Vendor Signup"]
)  # Vendor self-signup + onboarding (has own /api/v1/vendors prefix)
app.include_router(
    blog_router, tags=["Blog"]
)  # Public blog + admin blog endpoints (has own /api/v1/blog and /blog/admin prefixes)

# Couple Portal routes (public - couple auth is handled at route level)
app.include_router(
    couple_auth_router, tags=["Couple Auth"]
)  # Couple login, setup, verify invite
app.include_router(
    couple_portal_router, tags=["Couple Portal"]
)  # Couple dashboard, forms, updates
app.include_router(couple_notification_stream_router, tags=["Couple Notifications SSE"])
app.include_router(
    couple_analytics_router, prefix="/couple", tags=["Couple Portal Analytics"]
)  # Couple-auth behavioral analytics
app.include_router(
    guest_memories_router, tags=["Guest Memories"]
)  # Public upload + couple memories endpoints
app.include_router(
    client_contracts_admin_router, prefix="/admin", tags=["Contracts"]
)  # Canonical planner/couple contract admin endpoints

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
    (gallery_admin_router, "Gallery"),
    (reminder_utils_router, "Admin"),
    # user_management_router - already registered publicly with route-level auth
    # subscription_router - already registered publicly with route-level auth
    # saas_config_router - already registered publicly with route-level auth
    (budget_router, "Budget"),
    (planner_metrics_router, "Metrics"),
    # forms_router - mounted above with /admin prefix and public-compatible aliases
    (trial_management_router, "Admin"),
    # vendor_forms_router - already registered publicly with route-level auth
    # vendor_management_router - registered at /admin prefix (line ~300)
    (
        notification_stream_router,
        "Notifications SSE",
    ),  # Must come BEFORE notification_router so /notifications/stream matches before /notifications/{notification_id}
    (notification_router, "Notifications"),
    (support_router, "Support"),
    (admin_platform_metrics_router, "ROOT_ADMIN"),
    (admin_analytics_router, "ROOT_ADMIN"),
    (backup_router, "ROOT_ADMIN"),
    (admin_activity_router, "ROOT_ADMIN"),
    (billing_jobs_router, "Admin"),
    (metering_router, "ROOT_ADMIN"),
    (planner_calendar_router, "Planner Calendar"),
    (packages_router, "Packages"),
    # client_contracts_admin_router - mounted explicitly at /admin/client-contracts
    (autopilot_router, "Autopilot"),
    (ai_router, "AI"),
    (planner_notifications_router, "Planner Notifications"),
    (tables_router, "Seating"),
    (guest_export_router, "Guest Export"),
    (web_push_router, "Web Push"),
    (knowledge_base_router, "Knowledge Base"),
    (team_management_router, "Team Management"),
    (inbound_emails_router, "Inbound Emails"),
    (
        couple_invite_router,
        "Couple Portal",
    ),  # Planner-side couple invitation management
]

for router, tag in admin_routers:
    app.include_router(router, prefix="/admin", tags=[tag])

app.include_router(storefront_router, prefix="/admin", tags=["Storefront"])

# Admin wedding, guest, and plus-one endpoints (special handling to avoid conflicts)
app.include_router(wedding_router, prefix="/admin", tags=["Wedding"])
app.include_router(guest_router, prefix="/admin", tags=["Guest"])
app.include_router(plus_one_router, prefix="/admin/plus-one", tags=["Plus-Ones"])


# ==================== CUSTOM ENDPOINTS ====================


def build_root_response(config) -> dict[str, object]:
    """Build the root health/info payload with environment-aware docs metadata."""
    response = {
        "message": f"Welcome to {config.app_name}",
        "version": config.app_version,
        "environment": config.environment,
    }
    if config.api_docs_enabled:
        response["docs_url"] = "/docs"
    return response


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint"""
    return build_root_response(settings)


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
            "audit_logging": settings.audit_logging_enabled,
        },
    }


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    """Add appropriate cache headers"""
    response = await call_next(request)

    # Add cache headers for static content
    if settings.enable_cache_headers:
        path = request.url.path

        # Next.js build chunks (_next/static) contain content-hashed filenames
        # so they can be cached forever safely — the hash changes on rebuild.
        # But during development, _next/ paths must NOT be cached or HMR
        # will serve stale module factories ("module factory is not available").
        is_nextjs_asset = "/_next/" in path

        if is_nextjs_asset:
            if settings.is_development():
                # Dev: never cache JS/CSS chunks — Turbopack HMR needs fresh loads
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
            else:
                # Prod: _next/static files have content hashes, safe to cache long
                response.headers["Cache-Control"] = (
                    f"public, max-age={settings.static_cache_max_age}, immutable"
                )
        elif any(
            path.endswith(ext)
            for ext in [
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".ico",
                ".woff",
                ".woff2",
                ".svg",
            ]
        ):
            # Truly static binary assets — safe to cache
            response.headers["Cache-Control"] = (
                f"public, max-age={settings.static_cache_max_age}"
            )
        elif any(path.endswith(ext) for ext in [".css", ".js"]):
            # Non-Next.js CSS/JS (custom static files) — moderate cache
            response.headers["Cache-Control"] = "public, max-age=3600"
        elif request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # Mutations must never be cached
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        elif (
            path.startswith("/api/")
            or path.startswith("/couple-portal/")
            or path.startswith("/couple/")
            or path.startswith("/admin/")
            or path.startswith("/vendor-contract/")
            # 2026-05-13: /subscription-plans is the ROOT_ADMIN-only admin
            # CRUD surface for the plan catalog. The router lives at the
            # root path (not /admin/) because the same module also exposes
            # /public/subscription-plans; auth is gated per-route via
            # require_root_admin. Without this branch the fall-through
            # below assigned ``public, max-age=300``, letting the browser's
            # HTTP cache serve a 5-minute-stale plan list right after an
            # admin save — see app/admin/saas/page.tsx handleSavePlan
            # post-save refetch which uses default fetch cache mode.
            or path.startswith("/subscription-plans")
        ):
            # Dynamic API/portal endpoints.  When SAFE_GET_CACHE_ENABLED
            # is set, idempotent GET/HEAD responses get a short private
            # cache window instead of ``no-store``.  This is safe because
            # the auth-extended Redis cache invalidates on every state
            # flip (Stripe webhooks, trial expiry, team-permission
            # changes), so a 5-second browser cache cannot serve stale
            # billing/role state.  Mutations and the default branch keep
            # the previous ``no-store`` behavior.
            if settings.safe_get_cache_enabled and request.method in ("GET", "HEAD"):
                response.headers["Cache-Control"] = (
                    f"private, max-age={settings.safe_get_cache_max_age}"
                )
            else:
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
        else:
            response.headers["Cache-Control"] = (
                "public, max-age=300"  # 5 minutes for other content
            )
    return response


# Paths that must never appear in a public search index.
#
# Background (2026-05-14 GSC "Some fixes failed" forensics):
# Before this middleware existed, robots.txt Disallow'd these paths so
# Googlebot couldn't crawl them — but Disallow only prevents *crawling*,
# not *indexing*. Anything that had previously been indexed (or that had
# inbound links Googlebot already knew about) stayed in the index as
# "crawled, currently not indexed" / "discovered, currently not indexed"
# entries. Re-submitting them for validation in Search Console fails
# because the bot can't fetch them to confirm the fix.
#
# The correct two-step pattern is:
#   1. Remove the path from robots.txt Disallow (so Googlebot CAN fetch it).
#   2. Return ``X-Robots-Tag: noindex, nofollow`` on the response (so
#      Google removes it from the index on re-crawl).
# Once GSC reports the URLs as not-indexed, the path may optionally be
# re-added to robots.txt Disallow for crawl-budget protection.
#
# See app/robots.ts for the matching robots.txt source — the two must
# stay in lockstep or de-indexing stalls.
_NOINDEX_PATH_PREFIXES = (
    "/admin",
    "/api",
    "/otp",
    "/setup-account",
    "/reset-password",
    "/forgot-password",
    "/login",  # legacy; redirect target is /admin/login (already covered above)
    "/token",
    "/auth",
    "/couple-portal",
    "/couple/",  # couple workspace — gated by per-wedding token, not public
    "/vendor-contract",
)

# Paths that LOOK like they would match a noindex prefix above but are
# legitimately public marketing/legal/data-deletion pages that must stay
# indexable.
_NOINDEX_PATH_EXEMPT_EXACT = frozenset(
    {
        "/admin/login",  # public sign-in surface, intentionally indexable
    }
)


@app.middleware("http")
async def add_robots_headers(request: Request, call_next):
    """Emit ``X-Robots-Tag: noindex, nofollow`` for non-public surfaces.

    Pairs with ``app/robots.ts``. Disallow alone cannot remove a URL
    from Google's index; this header is what actually de-indexes pages
    that should never have been crawled in the first place.
    """
    response = await call_next(request)
    path = request.url.path

    if path in _NOINDEX_PATH_EXEMPT_EXACT:
        return response

    if any(
        path == prefix or path.startswith(prefix + "/")
        for prefix in _NOINDEX_PATH_PREFIXES
    ):
        # ``noindex`` removes the URL from the index on next crawl.
        # ``nofollow`` tells Google not to follow links from these pages
        # (admin/couple/vendor surfaces leak internal route hints we
        # don't want shaping crawl frontier).
        response.headers["X-Robots-Tag"] = "noindex, nofollow"

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
                            info.get("keyspace_hits", 0)
                            / (
                                info.get("keyspace_hits", 0)
                                + info.get("keyspace_misses", 1)
                            )
                        ),
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
        host="0.0.0.0",  # nosec B104
        port=8000,
        reload=settings.is_development(),
        log_level="info",
    )

"""
Enhanced Error Handler Middleware with MongoDB Logging and Email Alerts

Zero-cost error tracking alternative to Sentry:
- Logs all errors to MongoDB "errors" collection
- Sends email alerts for critical errors via Resend (you already have it!)
- Provides error_id for user reference
- Full stack trace and request context
- Self-hosted error dashboard
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.exceptions import WeddingAppException
import logging
import traceback
from datetime import datetime
import uuid
import os
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Enhanced error handler with self-hosted error tracking
    """

    def __init__(self, app, enable_email_alerts: bool = True):
        super().__init__(app)
        self.enable_email_alerts = enable_email_alerts
        self.root_admin_email = os.getenv("ROOT_ADMIN_EMAIL", "admin@example.com")

        # Import Resend if email alerts enabled
        if self.enable_email_alerts:
            try:
                import resend
                self.resend = resend
                self.resend_api_key = os.getenv("RESEND_API_KEY")
                if self.resend_api_key:
                    resend.api_key = self.resend_api_key
                    logger.info("Email alerts enabled via Resend")
                else:
                    logger.warning("RESEND_API_KEY not set, email alerts disabled")
                    self.enable_email_alerts = False
            except ImportError:
                logger.warning("resend package not installed, email alerts disabled. Install with: pip install resend")
                self.enable_email_alerts = False

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except WeddingAppException as e:
            # Handle custom application exceptions
            return await self._handle_wedding_app_exception(request, e)
        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            return await self._handle_http_exception(request, e)
        except Exception as e:
            # Handle unexpected exceptions (this is where we log to MongoDB)
            return await self._handle_unexpected_exception(request, e)

    async def _handle_wedding_app_exception(self, request: Request, exc: WeddingAppException) -> JSONResponse:
        """Handle custom WeddingApp exceptions"""

        # Log the error
        logger.error(f"WeddingApp Exception: {exc.error_code} - {exc.message}")

        error_response = {
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            }
        }

        # Add field information for validation errors
        if hasattr(exc, 'field') and exc.field:
            error_response["error"]["field"] = exc.field

        # Add retry_after for rate limit errors
        if hasattr(exc, 'retry_after'):
            error_response["error"]["retry_after"] = exc.retry_after

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )

    async def _handle_http_exception(self, request: Request, exc: HTTPException) -> JSONResponse:
        """Handle FastAPI HTTP exceptions"""

        # Map HTTP status codes to error codes
        status_to_code = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_SERVER_ERROR"
        }

        error_code = status_to_code.get(exc.status_code, "HTTP_ERROR")

        # Log the error
        logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")

        # Handle validation errors from Pydantic
        if exc.status_code == 422 and isinstance(exc.detail, list):
            errors = []
            for error in exc.detail:
                field = ".".join(str(loc) for loc in error.get("loc", []))
                errors.append({
                    "field": field,
                    "message": error.get("msg", "Validation error"),
                    "type": error.get("type", "value_error")
                })

            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Validation failed",
                        "errors": errors,
                        "timestamp": datetime.utcnow().isoformat(),
                        "path": str(request.url.path)
                    }
                }
            )

        # Standard error response
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": error_code,
                    "message": str(exc.detail),
                    "timestamp": datetime.utcnow().isoformat(),
                    "path": str(request.url.path)
                }
            }
        )

    async def _handle_unexpected_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """
        Handle unexpected exceptions - The key enhancement!

        This logs to MongoDB and sends email alerts for critical errors.
        """

        error_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()

        # Get request body if available (safely)
        request_body = None
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                # Try to get body without consuming it
                body = await request.body()
                if body:
                    request_body = body.decode('utf-8')[:1000]  # Limit size
        except Exception:
            pass

        # Capture full context
        error_doc = {
            "error_id": error_id,
            "timestamp": timestamp,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "stack_trace": traceback.format_exc(),
            "request": {
                "method": request.method,
                "path": str(request.url.path),
                "query_params": dict(request.query_params),
                "headers": {
                    key: value for key, value in request.headers.items()
                    if key.lower() not in ['authorization', 'cookie', 'x-api-key']  # Don't log secrets
                },
                "body": request_body,
                "client_ip": self._get_client_ip(request)
            },
            "user": {
                "authenticated": bool(request.headers.get("Authorization")),
                "user_agent": request.headers.get("User-Agent", "Unknown")
            },
            "environment": os.getenv("ENVIRONMENT", "development"),
            "acknowledged": False,
            "severity": self._get_error_severity(exc)
        }

        # Log to console
        logger.error(
            f"Unexpected error [{error_id}]: {type(exc).__name__}: {str(exc)}",
            exc_info=exc,
            extra={"error_id": error_id}
        )

        # Save to MongoDB "errors" collection (async)
        try:
            from app.core.database_async import async_mongo
            await async_mongo.db["errors"].insert_one(error_doc)
            logger.info(f"Error {error_id} saved to database")
        except Exception as db_error:
            logger.error(f"Failed to save error to database: {str(db_error)}")

        # Send email alert if critical
        if self._is_critical_error(exc) and self.enable_email_alerts:
            try:
                await self._send_alert_email(error_doc)
                logger.info(f"Alert email sent for error {error_id}")
            except Exception as email_error:
                logger.error(f"Failed to send alert email: {str(email_error)}")

        # Return user-friendly error response
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Our team has been notified.",
                    "error_id": error_id,  # User can reference this in support tickets
                    "timestamp": timestamp.isoformat(),
                    "path": str(request.url.path)
                }
            }
        )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers (reverse proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"

    def _is_critical_error(self, exc: Exception) -> bool:
        """
        Determine if error is critical enough to send email alert

        Critical errors:
        - Database connection errors
        - Payment/Stripe errors
        - Authentication system errors
        - Any unhandled exception in production
        """
        error_type = type(exc).__name__

        critical_errors = [
            "ConnectionError",
            "DatabaseError",
            "MongoServerError",
            "StripeError",
            "PaymentError",
            "AuthenticationError",
            "KeyError",  # Often indicates missing config
        ]

        # In production, all unexpected errors are critical
        is_production = os.getenv("ENVIRONMENT", "development") == "production"

        return error_type in critical_errors or is_production

    def _get_error_severity(self, exc: Exception) -> str:
        """Get error severity level"""
        if self._is_critical_error(exc):
            return "critical"

        error_type = type(exc).__name__

        if error_type in ["ValueError", "TypeError", "AttributeError"]:
            return "high"

        return "medium"

    async def _send_alert_email(self, error_doc: dict):
        """
        Send email alert using Resend (you already pay for this!)

        Resend free tier: 100 emails/day - perfect for error alerts
        """
        if not self.enable_email_alerts or not self.resend_api_key:
            return

        try:
            # Build email content
            error_html = self._build_error_email_html(error_doc)

            # Send email
            params = {
                "from": os.getenv("RESEND_FROM_EMAIL", "alerts@thespecialwedding.com"),
                "to": [self.root_admin_email],
                "subject": f"🚨 {error_doc['severity'].upper()}: {error_doc['error_type']}",
                "html": error_html
            }

            self.resend.Emails.send(params)

            logger.info(f"Alert email sent for error {error_doc['error_id']}")

        except Exception as e:
            logger.error(f"Failed to send alert email: {str(e)}")
            # Don't raise - we don't want email failures to cause more errors

    def _build_error_email_html(self, error_doc: dict) -> str:
        """Build HTML email for error alert"""

        severity_colors = {
            "critical": "#DC2626",  # Red
            "high": "#EA580C",      # Orange
            "medium": "#D97706"     # Amber
        }

        severity = error_doc.get("severity", "medium")
        color = severity_colors.get(severity, "#6B7280")

        # Get admin dashboard URL
        dashboard_url = os.getenv("FRONTEND_URL")
        if not dashboard_url:
            raise ValueError("FRONTEND_URL environment variable is required")
        error_url = f"{dashboard_url}/admin/errors/{error_doc['error_id']}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">

            <div style="background-color: {color}; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0; font-size: 24px;">🚨 Platform Error Alert</h1>
                <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">
                    Severity: <strong>{severity.upper()}</strong>
                </p>
            </div>

            <div style="background-color: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">

                <div style="background-color: white; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                    <h2 style="margin: 0 0 10px 0; font-size: 18px; color: #1f2937;">Error Details</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280; width: 120px;">Error ID:</td>
                            <td style="padding: 8px 0; font-family: monospace; font-size: 13px;">{error_doc['error_id']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Type:</td>
                            <td style="padding: 8px 0; color: {color}; font-weight: 600;">{error_doc['error_type']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Message:</td>
                            <td style="padding: 8px 0;">{error_doc['error_message']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Time:</td>
                            <td style="padding: 8px 0;">{error_doc['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Environment:</td>
                            <td style="padding: 8px 0; text-transform: uppercase; font-weight: 600;">{error_doc['environment']}</td>
                        </tr>
                    </table>
                </div>

                <div style="background-color: white; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                    <h2 style="margin: 0 0 10px 0; font-size: 18px; color: #1f2937;">Request Context</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280; width: 120px;">Endpoint:</td>
                            <td style="padding: 8px 0; font-family: monospace; font-size: 13px;">
                                {error_doc['request']['method']} {error_doc['request']['path']}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">IP Address:</td>
                            <td style="padding: 8px 0;">{error_doc['request']['client_ip']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">User Agent:</td>
                            <td style="padding: 8px 0; font-size: 12px; color: #6b7280;">
                                {error_doc['user']['user_agent'][:100]}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Authenticated:</td>
                            <td style="padding: 8px 0;">
                                {'✓ Yes' if error_doc['user']['authenticated'] else '✗ No'}
                            </td>
                        </tr>
                    </table>
                </div>

                <div style="background-color: white; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                    <h2 style="margin: 0 0 10px 0; font-size: 18px; color: #1f2937;">Stack Trace</h2>
                    <pre style="background-color: #1f2937; color: #f9fafb; padding: 15px; border-radius: 4px; overflow-x: auto; font-size: 11px; line-height: 1.4; margin: 0;">{error_doc['stack_trace']}</pre>
                </div>

                <div style="text-align: center; margin-top: 20px;">
                    <a href="{error_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600;">
                        View in Dashboard →
                    </a>
                </div>

                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 12px;">
                    <p style="margin: 0;">This is an automated alert from your Wedding Platform monitoring system.</p>
                    <p style="margin: 5px 0 0 0;">Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>

            </div>

        </body>
        </html>
        """

        return html

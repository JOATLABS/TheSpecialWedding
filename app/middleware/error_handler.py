"""
Unified secure and enhanced error handler middleware.

Features merged from enhanced and secure handlers:
- Sanitized, consistent error responses with unique error IDs
- Optional MongoDB persistence for unexpected errors
- Optional email alerts for critical errors (Resend)
- Basic IP-based error rate limiting to avoid abuse
"""

import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.exceptions import WeddingAppException
from app.utils.secure_error_handler import SecureErrorHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to handle all exceptions with secure responses, logging, and alerts."""

    def __init__(self, app, enable_email_alerts: bool = True):
        super().__init__(app)
        self.enable_email_alerts = enable_email_alerts
        self.root_admin_email = os.getenv("ROOT_ADMIN_EMAIL", "admin@example.com")
        self.debug_mode = os.getenv("DEBUG", "false").lower() == "true"
        self.secure_handler = SecureErrorHandler(debug_mode=self.debug_mode)

        # Error rate limiting (per IP)
        self.max_error_rate = 100  # per minute per IP
        self.error_tracking: Dict[str, Dict[str, Any]] = {}
        self.blocked_ips: set[str] = set()

        # Optional email alerts via Resend
        self.resend = None
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        if enable_email_alerts and self.resend_api_key:
            try:
                import resend

                resend.api_key = self.resend_api_key
                self.resend = resend
                logger.info("Email alerts enabled via Resend")
            except ImportError:
                logger.warning("resend package not installed, email alerts disabled.")
                self.enable_email_alerts = False
        else:
            if enable_email_alerts:
                logger.warning("RESEND_API_KEY not set, email alerts disabled.")
            self.enable_email_alerts = False

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)

        if self._is_ip_blocked(client_ip):
            return self._create_blocked_response(client_ip)

        try:
            response = await call_next(request)
            self._reset_success(client_ip)
            return response
        except Exception as exc:
            # Track and potentially block abusive IPs
            self._track_error(client_ip)
            if self._should_block_ip(client_ip):
                self.blocked_ips.add(client_ip)
                logger.warning(f"Blocking IP {client_ip} due to excessive errors")

            # Build secure response
            secure_response = self.secure_handler.handle_exception(request, exc)

            # Capture payload for logging/alerting
            error_payload = self._extract_payload(secure_response)
            error_id = self._get_error_id(error_payload)

            # Persist and alert on unexpected errors only
            if not isinstance(exc, (WeddingAppException, HTTPException)):
                await self._log_unexpected_error(request, exc, error_payload, client_ip, error_id)
                if self._is_critical_error(exc) and self.enable_email_alerts:
                    await self._send_alert_email(error_payload)

            return secure_response

    # ==================== SUPPORTING METHODS ====================

    def _extract_payload(self, response: JSONResponse) -> Dict:
        """Safely parse JSON payload from a JSONResponse."""
        try:
            return json.loads(bytes(response.body).decode("utf-8"))
        except Exception:
            return {}

    def _get_error_id(self, payload: Dict) -> str:
        return payload.get("error", {}).get("error_id") or str(uuid.uuid4())

    def _reset_success(self, client_ip: str) -> None:
        """Decay error counts after successful requests."""
        if client_ip in self.error_tracking:
            self.error_tracking[client_ip]["success_count"] += 1
            if self.error_tracking[client_ip]["success_count"] >= 10:
                self.error_tracking[client_ip]["error_count"] = max(
                    0, self.error_tracking[client_ip]["error_count"] - 5
                )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP with basic validation."""
        headers_to_check = [
            "X-Forwarded-For",
            "X-Real-IP",
            "X-Client-IP",
            "CF-Connecting-IP",
            "True-Client-IP",
        ]
        for header in headers_to_check:
            ip = request.headers.get(header)
            if ip:
                first_ip = ip.split(",")[0].strip()
                if first_ip and len(first_ip) <= 45 and self._is_valid_ip_format(first_ip):
                    return first_ip
        return getattr(request.client, "host", "unknown")

    def _is_valid_ip_format(self, ip: str) -> bool:
        import re

        ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
        if re.match(ipv4_pattern, ip):
            parts = ip.split(".")
            return all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)

        ipv6_pattern = r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"
        return bool(re.match(ipv6_pattern, ip))

    def _track_error(self, client_ip: str) -> None:
        current_time = datetime.utcnow()
        if client_ip not in self.error_tracking:
            self.error_tracking[client_ip] = {
                "error_count": 0,
                "success_count": 0,
                "last_error": None,
                "first_error": current_time,
            }
        self.error_tracking[client_ip]["error_count"] += 1
        self.error_tracking[client_ip]["last_error"] = current_time
        self._cleanup_old_tracking()

    def _should_block_ip(self, client_ip: str) -> bool:
        if client_ip == "unknown" or client_ip not in self.error_tracking:
            return False

        data = self.error_tracking[client_ip]
        error_count = data["error_count"]
        success_count = data["success_count"]

        if error_count > self.max_error_rate:
            return True

        total_requests = error_count + success_count
        return total_requests > 50 and (error_count / total_requests) > 0.9

    def _is_ip_blocked(self, client_ip: str) -> bool:
        return client_ip in self.blocked_ips

    def _create_blocked_response(self, client_ip: str) -> JSONResponse:
        logger.warning(f"Blocked IP {client_ip} attempted request")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "IP_BLOCKED",
                    "message": "Your IP has been temporarily blocked due to excessive errors. Please try again later.",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "retry_after": 3600,
                }
            },
            headers={"Retry-After": "3600", "X-Rate-Limit": "Blocked"},
        )

    def _cleanup_old_tracking(self) -> None:
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=1)
        expired_ips = [ip for ip, data in self.error_tracking.items() if data["first_error"] < cutoff_time]
        for ip in expired_ips:
            del self.error_tracking[ip]
            self.blocked_ips.discard(ip)

    async def _log_unexpected_error(
        self,
        request: Request,
        exc: Exception,
        payload: Dict,
        client_ip: str,
        error_id: str,
    ) -> None:
        """Persist unexpected errors to MongoDB when available."""
        error_doc = {
            "error_id": error_id,
            "timestamp": datetime.utcnow(),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "stack_trace": traceback.format_exc(),
            "request": {
                "method": request.method,
                "path": str(request.url.path),
                "query_params": dict(request.query_params),
                "headers": {
                    k: v
                    for k, v in request.headers.items()
                    if k.lower() not in ["authorization", "cookie", "x-api-key"]
                },
                "client_ip": client_ip,
            },
            "user": {
                "authenticated": bool(request.headers.get("Authorization")),
                "user_agent": request.headers.get("User-Agent", "Unknown"),
            },
            "environment": os.getenv("ENVIRONMENT", "development"),
            "acknowledged": False,
            "severity": self._get_error_severity(exc),
            "response": payload,
        }

        try:
            from app.core.database import mongo

            await mongo.db["errors"].insert_one(error_doc)
            logger.info(f"Error {error_id} saved to database")
        except Exception as db_error:
            logger.error(f"Failed to save error to database: {str(db_error)}")

    def _is_critical_error(self, exc: Exception) -> bool:
        error_type = type(exc).__name__
        critical_errors = {
            "ConnectionError",
            "DatabaseError",
            "MongoServerError",
            "StripeError",
            "PaymentError",
            "AuthenticationError",
            "KeyError",
        }
        is_production = os.getenv("ENVIRONMENT", "development") == "production"
        return error_type in critical_errors or is_production

    def _get_error_severity(self, exc: Exception) -> str:
        if self._is_critical_error(exc):
            return "critical"
        if isinstance(exc, (ValueError, TypeError, AttributeError)):
            return "high"
        return "medium"

    async def _send_alert_email(self, payload: Dict) -> None:
        """Send alert email for critical errors using Resend."""
        if not self.resend or not self.resend_api_key:
            return

        try:
            error = payload.get("error", {})
            error_html = self._build_error_email_html(error)
            params = {
                "from": os.getenv("RESEND_FROM_EMAIL", "alerts@thespecialwedding.com"),
                "to": [self.root_admin_email],
                "subject": f"Platform Error: {error.get('code', 'UNKNOWN')}",
                "html": error_html,
            }
            self.resend.Emails.send(params)  # type: ignore
            logger.info(f"Alert email sent for error {error.get('error_id')}")
        except Exception as e:
            logger.error(f"Failed to send alert email: {str(e)}")

    def _build_error_email_html(self, error: Dict) -> str:
        """Build a minimal HTML email for error alerts."""
        dashboard_url = os.getenv("FRONTEND_URL")
        error_id = error.get("error_id", "unknown")
        error_url = f"{dashboard_url}/admin/errors/{error_id}" if dashboard_url else "#"
        return f"""
        <html>
            <body style="font-family: sans-serif;">
                <h2>Platform Error Alert</h2>
                <p><strong>Error ID:</strong> {error_id}</p>
                <p><strong>Code:</strong> {error.get('code')}</p>
                <p><strong>Message:</strong> {error.get('message')}</p>
                <p><strong>Time:</strong> {error.get('timestamp')}</p>
                <p><a href="{error_url}">View in dashboard</a></p>
            </body>
        </html>
        """

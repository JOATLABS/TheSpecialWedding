"""
Unified secure and enhanced error handler middleware.

Features merged from enhanced and secure handlers:
- Sanitized, consistent error responses with unique error IDs
- Optional MongoDB persistence for unexpected errors
- Optional email alerts for critical errors (Resend)
- Basic IP-based error rate limiting to avoid abuse
"""

import ipaddress
import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

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

    # Paths commonly probed by scanners for sensitive files
    BLOCKED_PATH_PREFIXES = (
        "/.git",
        "/.env",
        "/.aws",
        "/.ssh",
        "/.svn",
        "/.hg",
        "/.docker",
        "/.vscode",
        "/wp-admin",
        "/wp-login",
        "/wp-content",
        "/wp-includes",
        "/wp",
        "/wordpress",
        "/phpmyadmin",
        "/administrator",
        "/cgi-bin",
        "/.htaccess",
        "/.htpasswd",
        "/.DS_Store",
        "/server-status",
        "/server-info",
        "/config.php",
        "/xmlrpc.php",
        "/debug",
        "/debugbar",
        "/_debugbar",
        "/blog",
        "/new",
        "/old",
        "/backup",
        "/aws-",
        "/test.php",
        "/info.php",
        "/phpinfo.php",
        "/config.js",
    )

    BLOCKED_PATH_SUFFIXES = (
        ".php",
        ".asp",
        ".aspx",
        ".jsp",
        ".env",
        ".env.backup",
        "aws.json",
        "aws-credentials",
        "aws.config.js",
        ".s3cfg",
        "config.js",
    )

    # RFC 1918 / RFC 4193 private networks used by internal services
    # (Next.js SSR container, K8s sidecars, etc.).
    # Trusted-IP checks are ONLY applied to the *direct* TCP peer
    # (request.client.host), never to forwarded headers — this prevents
    # X-Forwarded-For spoofing from bypassing rate limiting.
    PRIVATE_NETWORKS = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("::1/128"),  # IPv6 loopback
        ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
        ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    )

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

        # Allow additional trusted IPs/CIDRs via environment variable (comma-separated).
        # Supports both individual IPs ("10.48.0.2") and CIDR ranges ("10.48.0.0/24").
        self.extra_trusted_networks: list[
            ipaddress.IPv4Network | ipaddress.IPv6Network
        ] = []
        extra_trusted = os.getenv("TRUSTED_IPS", "")
        for entry in extra_trusted.split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                # strict=False allows "10.48.0.2/24" to be treated as "10.48.0.0/24"
                self.extra_trusted_networks.append(
                    ipaddress.ip_network(entry, strict=False)
                )
            except ValueError:
                logger.warning(
                    f"Invalid IP/CIDR in TRUSTED_IPS env var, skipping: {entry}"
                )
        if self.extra_trusted_networks:
            logger.info(
                f"Loaded {len(self.extra_trusted_networks)} trusted network(s) from TRUSTED_IPS env var"
            )

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

    def _is_suspicious_path(self, path: str) -> bool:
        """Check if the request path is a known scanner/probe target."""
        path_lower = path.lower()
        if any(path_lower.startswith(p) for p in self.BLOCKED_PATH_PREFIXES):
            return True
        if any(path_lower.endswith(s) for s in self.BLOCKED_PATH_SUFFIXES):
            return True
        return False

    async def dispatch(self, request: Request, call_next):
        # For rate-limiting decisions we use the *direct peer* IP so that
        # trusted internal services (Next.js SSR, K8s probes) are never
        # blocked.  The forwarded "real client" IP is only resolved when
        # the peer is a trusted proxy — see _get_client_ip.
        direct_ip = getattr(request.client, "host", "unknown")
        is_trusted = self._is_trusted_ip(direct_ip)

        # Resolve the client IP (may follow proxy headers for trusted peers)
        client_ip = self._get_client_ip(request)

        if not is_trusted and client_ip in self.blocked_ips:
            return self._create_blocked_response(client_ip)

        # Block known scanner/probe paths — but let trusted services through
        if self._is_suspicious_path(request.url.path) and not is_trusted:
            logger.warning(
                f"Blocked suspicious path probe: {request.url.path} from {client_ip}"
            )
            self._track_error(client_ip)
            if self._should_block_ip(client_ip):
                self.blocked_ips.add(client_ip)
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        try:
            response = await call_next(request)
            if not is_trusted:
                self._reset_success(client_ip)

            # Skip logging 404s with suspicious paths (scanner probes)
            if response.status_code == 404 and self._is_suspicious_path(
                request.url.path
            ):
                logger.debug(f"Ignoring 404 for scanner probe path: {request.url.path}")
                return response

            return response
        except Exception as exc:
            # Only track/block errors for non-trusted IPs
            if not is_trusted:
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
            # Note: HTTPException (including 401, 402, 403 auth responses) are not logged as errors
            # because they are normal application responses, not unexpected failures
            if not isinstance(exc, (WeddingAppException, HTTPException)):
                await self._log_unexpected_error(
                    request, exc, error_payload, client_ip, error_id
                )
                if self._is_critical_error(exc) and self.enable_email_alerts:
                    await self._send_alert_email(error_payload, exc, request, client_ip)

            return secure_response

    # ==================== SUPPORTING METHODS ====================

    def _extract_payload(self, response: JSONResponse) -> Dict:
        """Safely parse JSON payload from a JSONResponse."""
        try:
            return json.loads(bytes(response.body).decode("utf-8"))
        except Exception as e:
            logger.warning(
                f"Failed to extract payload from response: {e}", exc_info=True
            )
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
        """Extract the real client IP.

        Proxy headers (X-Forwarded-For, CF-Connecting-IP, etc.) are ONLY
        trusted when the direct TCP peer (request.client.host) is itself a
        private/trusted IP — i.e. a reverse proxy, load balancer, or
        Cloudflare edge server.  This prevents external attackers from
        spoofing a private IP via X-Forwarded-For to bypass rate limiting.
        """
        direct_ip = getattr(request.client, "host", "unknown")

        # Only trust forwarded headers if the direct peer is a trusted proxy
        if self._is_private_ip(direct_ip):
            headers_to_check = [
                "CF-Connecting-IP",  # Cloudflare (most specific, check first)
                "True-Client-IP",  # Cloudflare Enterprise
                "X-Real-IP",  # nginx
                "X-Forwarded-For",  # Generic (take first entry)
                "X-Client-IP",  # Legacy
            ]
            for header in headers_to_check:
                value = request.headers.get(header)
                if value:
                    candidate = value.split(",")[0].strip()
                    if self._is_valid_ip(candidate):
                        return candidate

        return direct_ip

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        """Validate an IP address string using the ipaddress module."""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def _track_error(self, client_ip: str) -> None:
        current_time = datetime.now(timezone.utc)
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
        if self._is_trusted_ip(client_ip):
            return False

        data = self.error_tracking[client_ip]
        error_count = data["error_count"]
        success_count = data["success_count"]

        if error_count > self.max_error_rate:
            return True

        total_requests = error_count + success_count
        return total_requests > 50 and (error_count / total_requests) > 0.9

    def _parse_ip(
        self, ip_str: str
    ) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
        """Parse an IP string once; returns None for invalid input."""
        try:
            return ipaddress.ip_address(ip_str)
        except ValueError:
            return None

    def _is_in_private_network(
        self, addr: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> bool:
        """Check if a *parsed* IP belongs to a private/loopback network."""
        return any(addr in net for net in self.PRIVATE_NETWORKS)

    def _is_private_ip(self, ip_str: str) -> bool:
        """Check if an IP string belongs to a private/loopback network (RFC 1918 / RFC 4193)."""
        addr = self._parse_ip(ip_str)
        return addr is not None and self._is_in_private_network(addr)

    def _is_trusted_ip(self, client_ip: str) -> bool:
        """Check if the IP is an internal/trusted service (e.g. Next.js SSR container).

        This is checked against the *direct TCP peer* IP, not forwarded headers,
        so it cannot be spoofed by external attackers.
        """
        addr = self._parse_ip(client_ip)
        if addr is None:
            return False
        if self._is_in_private_network(addr):
            return True
        # Check additional trusted networks from env var
        if any(addr in net for net in self.extra_trusted_networks):
            return True
        return False

    def _is_ip_blocked(self, client_ip: str) -> bool:
        # Note: in dispatch(), is_trusted is pre-computed from the direct peer.
        # This fallback is for any other callers.
        if self._is_trusted_ip(client_ip):
            return False
        return client_ip in self.blocked_ips

    def _create_blocked_response(self, client_ip: str) -> JSONResponse:
        logger.warning(f"Blocked IP {client_ip} attempted request")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "IP_BLOCKED",
                    "message": "Your IP has been temporarily blocked due to excessive errors. Please try again later.",
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                    "retry_after": 3600,
                }
            },
            headers={"Retry-After": "3600", "X-Rate-Limit": "Blocked"},
        )

    def _cleanup_old_tracking(self) -> None:
        current_time = datetime.now(timezone.utc)
        cutoff_time = current_time - timedelta(hours=1)
        expired_ips = [
            ip
            for ip, data in self.error_tracking.items()
            if data["first_error"] < cutoff_time
        ]
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
            "timestamp": datetime.now(timezone.utc),
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
        # Errors that always warrant an alert regardless of environment
        critical_errors = {
            "ConnectionError",
            "DatabaseError",
            "MongoServerError",
            "StripeError",
            "PaymentError",
            "AuthenticationError",
        }
        if error_type in critical_errors:
            return True
        # In production, also alert on system-level errors — but NOT on
        # routine user-input errors like ValueError/TypeError/KeyError,
        # which would cause alert fatigue.
        is_production = os.getenv("ENVIRONMENT", "development") == "production"
        if is_production and error_type in {
            "MemoryError",
            "RuntimeError",
            "SystemError",
            "OSError",
        }:
            return True
        return False

    def _get_error_severity(self, exc: Exception) -> str:
        if self._is_critical_error(exc):
            return "critical"
        if isinstance(exc, (ValueError, TypeError, AttributeError)):
            return "high"
        return "medium"

    async def _send_alert_email(
        self,
        payload: Dict,
        exc: Optional[Exception] = None,
        request: Optional[Request] = None,
        client_ip: Optional[str] = None,
    ) -> None:
        """Send alert email for critical errors using Resend."""
        if not self.resend or not self.resend_api_key:
            return

        try:
            error = payload.get("error", {})
            error_html = self._build_error_email_html(error, exc, request, client_ip)
            exc_type = type(exc).__name__ if exc else "UNKNOWN"
            params = {
                "from": os.getenv("RESEND_FROM_EMAIL", "alerts@thespecialwedding.io"),
                "to": [self.root_admin_email],
                "subject": f"[{self._get_error_severity(exc).upper() if exc else 'ERROR'}] {exc_type}: {str(request.url.path) if request else 'unknown path'}",
                "html": error_html,
            }
            self.resend.Emails.send(params)  # type: ignore
            logger.info(f"Alert email sent for error {error.get('error_id')}")
        except Exception as e:
            logger.error(f"Failed to send alert email: {str(e)}")

    def _build_error_email_html(
        self,
        error: Dict,
        exc: Optional[Exception] = None,
        request: Optional[Request] = None,
        client_ip: Optional[str] = None,
    ) -> str:
        """Build a detailed HTML email for error alerts."""
        dashboard_url = os.getenv("FRONTEND_URL")
        error_id = error.get("error_id", "unknown")
        error_url = (
            f"{dashboard_url}/admin/platform/errors/{error_id}"
            if dashboard_url
            else "#"
        )
        severity = self._get_error_severity(exc) if exc else "unknown"
        environment = os.getenv("ENVIRONMENT", "development")

        # Extract real error details
        exc_type = type(exc).__name__ if exc else "Unknown"
        exc_message = str(exc)[:500] if exc else error.get("message", "No message")
        request_method = request.method if request else "N/A"
        request_path = str(request.url.path) if request else "N/A"
        user_agent = request.headers.get("User-Agent", "N/A") if request else "N/A"

        # Get first meaningful stack frame
        stack_summary = ""
        if exc:
            tb_lines = traceback.format_exc().strip().split("\n")
            # Get last 4 lines (the most relevant part)
            relevant_lines = tb_lines[-4:] if len(tb_lines) >= 4 else tb_lines
            stack_summary = "\n".join(relevant_lines)

        severity_colors = {
            "critical": "#dc2626",
            "high": "#ea580c",
            "medium": "#ca8a04",
        }
        severity_color = severity_colors.get(severity, "#6b7280")

        return f"""
        <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1a1a2e;">
                <div style="border-left: 4px solid {
            severity_color
        }; padding: 12px 16px; margin-bottom: 20px; background: #f8f9fa;">
                    <h2 style="margin: 0 0 4px 0; font-size: 18px;">Platform Error Alert</h2>
                    <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; background: {
            severity_color
        }; color: white; font-size: 12px; font-weight: 600; text-transform: uppercase;">{
            severity
        }</span>
                    <span style="margin-left: 8px; color: #6b7280; font-size: 13px;">{
            environment
        }</span>
                </div>

                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <tr><td style="padding: 6px 0; color: #6b7280; width: 120px;">Error ID</td><td style="padding: 6px 0; font-family: monospace; font-size: 13px;">{
            error_id
        }</td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">Exception</td><td style="padding: 6px 0; font-weight: 600;">{
            exc_type
        }</td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">Endpoint</td><td style="padding: 6px 0;"><code>{
            request_method
        } {request_path}</code></td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">Client IP</td><td style="padding: 6px 0;">{
            client_ip or "N/A"
        }</td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">Time</td><td style="padding: 6px 0;">{
            error.get("timestamp", "N/A")
        }</td></tr>
                </table>

                <div style="margin-top: 16px;">
                    <p style="margin: 0 0 6px 0; color: #6b7280; font-size: 13px; font-weight: 600;">Error Message</p>
                    <div style="background: #f1f5f9; padding: 10px 14px; border-radius: 6px; font-size: 13px; word-break: break-word;">{
            exc_message
        }</div>
                </div>

                {
            f'''<div style="margin-top: 16px;">
                    <p style="margin: 0 0 6px 0; color: #6b7280; font-size: 13px; font-weight: 600;">Stack Trace (summary)</p>
                    <pre style="background: #1e293b; color: #e2e8f0; padding: 12px 14px; border-radius: 6px; font-size: 12px; overflow-x: auto; white-space: pre-wrap;">{stack_summary}</pre>
                </div>'''
            if stack_summary
            else ""
        }

                <div style="margin-top: 20px;">
                    <a href="{
            error_url
        }" style="display: inline-block; padding: 10px 20px; background: #1a1a2e; color: white; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: 500;">View full details in dashboard</a>
                </div>

                <p style="margin-top: 16px; font-size: 12px; color: #9ca3af;">User Agent: {
            user_agent[:100]
        }</p>
            </body>
        </html>
        """

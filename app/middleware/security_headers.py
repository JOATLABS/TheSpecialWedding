"""
Unified Security Headers Middleware with CSP nonce support and threat logging.
"""

import logging
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

security_logger = logging.getLogger("wedding_security_headers")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add comprehensive security headers with CSP nonces, HSTS, and basic threat signals.
    Compatible with previous parameters (enable_hsts/enable_csp/csp_directives) while
    exposing enhanced options for reporting and strict policies.
    """

    def __init__(
        self,
        app,
        enable_hsts: bool = True,
        enable_csp: bool = True,
        csp_directives: Optional[Dict[str, List[str]]] = None,
        hsts_max_age: int = 31536000,
        csp_report_uri: Optional[str] = None,
        enable_csp_reporting: bool = True,
        allowed_origins: Optional[List[str]] = None,
        debug_mode: bool = False,
    ):
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.enable_csp = enable_csp
        self.hsts_max_age = hsts_max_age
        self.csp_report_uri = csp_report_uri
        self.enable_csp_reporting = enable_csp_reporting
        self.allowed_origins = allowed_origins or []
        self.debug_mode = debug_mode
        self.csp_directives = csp_directives  # Optional override

        # Track suspicious requests (lightweight; not a full rate limiter)
        self.suspicious_requests: Dict[str, Dict[str, Any]] = {}

    async def dispatch(self, request: Request, call_next) -> Response:
        nonce = self._generate_nonce()
        request.state.csp_nonce = nonce

        try:
            self._check_suspicious_request(request)
            response = await call_next(request)
            self._add_security_headers(response, request, nonce)
            self._log_security_response(request, response)
            return response
        except Exception as exc:
            security_logger.error(f"Security headers middleware error: {exc}")
            response = await call_next(request)
            self._add_basic_security_headers(response)
            return response

    # ==================== HEADER BUILDERS ====================

    def _add_security_headers(self, response: Response, request: Request, nonce: str) -> None:
        if self.enable_hsts and not self.debug_mode and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        if self.enable_csp:
            csp_policy = self._build_csp_policy(nonce, request)
            if csp_policy:
                response.headers["Content-Security-Policy"] = csp_policy

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = self._build_permissions_policy()
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Security-Policy"] = "strict"

        if self._is_sensitive_path(request.url.path):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # Hide default server header
        if "Server" in response.headers:
            del response.headers["Server"]
        response.headers["Server"] = "WeddingApp-Secure"

        request_id = getattr(request.state, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id

    def _build_csp_policy(self, nonce: str, request: Request) -> str:
        is_admin = "/admin/" in request.url.path
        is_api = "/api/" in request.url.path

        # Allow overrides if explicitly provided
        base_directives = self.csp_directives or {
            "default-src": ["'self'"],
            "script-src": ["'self'", f"'nonce-{nonce}'", "'strict-dynamic'"],
            "style-src": ["'self'", f"'nonce-{nonce}'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:", "https:"],
            "font-src": ["'self'", "https://fonts.gstatic.com"],
            "connect-src": ["'self'"] + self.allowed_origins,
            "media-src": ["'self'"],
            "object-src": ["'none'"],
            "frame-src": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "frame-ancestors": ["'none'"],
            "upgrade-insecure-requests": [],
        }

        if is_admin:
            base_directives["script-src"].extend(["https://cdn.jsdelivr.net", "https://unpkg.com"])
            base_directives["style-src"].extend(["https://fonts.googleapis.com", "https://cdn.jsdelivr.net"])

        if is_api:
            base_directives = {
                "default-src": ["'none'"],
                "frame-ancestors": ["'none'"],
                "base-uri": ["'none'"],
                "form-action": ["'none'"],
            }

        csp_parts = []
        for directive, sources in base_directives.items():
            if sources:
                csp_parts.append(f"{directive} {' '.join(sources)}")
            else:
                csp_parts.append(directive)

        if self.enable_csp_reporting and self.csp_report_uri:
            csp_parts.append(f"report-uri {self.csp_report_uri}")

        return "; ".join(csp_parts)

    def _build_permissions_policy(self) -> str:
        permissions = [
            "camera=()",
            "microphone=()",
            "geolocation=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "gyroscope=()",
            "accelerometer=()",
            "ambient-light-sensor=()",
            "autoplay=()",
            "encrypted-media=()",
            "fullscreen=(self)",
            "picture-in-picture=()",
        ]
        return ", ".join(permissions)

    def _add_basic_security_headers(self, response: Response) -> None:
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # ==================== SUSPICIOUS REQUEST SIGNALS ====================

    def _check_suspicious_request(self, request: Request) -> None:
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        path = request.url.path

        indicators = []
        if self._is_suspicious_user_agent(user_agent):
            indicators.append("suspicious_user_agent")
        if self._has_path_traversal_attempts(path):
            indicators.append("path_traversal")
        if request.url.query and self._has_suspicious_query(str(request.url.query)):
            indicators.append("suspicious_query")
        if self._is_excessive_requests(client_ip):
            indicators.append("excessive_requests")

        if indicators:
            security_logger.warning(
                f"Suspicious request from {client_ip}: path={path}, indicators={indicators}, "
                f"user_agent={user_agent[:100]}"
            )
            request.state.suspicious = True
            request.state.suspicious_indicators = indicators

    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        suspicious_patterns = [
            "sqlmap", "nikto", "nmap", "masscan", "nessus",
            "burpsuite", "owasp", "zap", "w3af", "skipfish",
            "python-requests", "curl", "wget", "gobuster",
            "dirb", "dirbuster", "wfuzz", "ffuf",
            "<script", "javascript:", "vbscript:",
            "union select", "or 1=1", "../", "..\\",
            "cmd.exe", "/bin/bash", "whoami",
        ]
        user_agent_lower = user_agent.lower()
        return any(pattern in user_agent_lower for pattern in suspicious_patterns)

    def _has_path_traversal_attempts(self, path: str) -> bool:
        traversal_patterns = [
            "../", "..\\", "%2e%2e%2f", "%2e%2e%5c",
            "%252e%252e%252f", "%252e%252e%255c",
            "..%2f", "..%5c", "%2e%2e/",
            "/etc/passwd", "/etc/shadow",
            "C:\\Windows\\", "C:\\Users\\",
            "/proc/version", "/proc/self/environ",
        ]
        path_decoded = path.replace("%", "\\x").encode().decode("unicode_escape", errors="ignore")
        return any(pattern in path or pattern in path_decoded for pattern in traversal_patterns)

    def _has_suspicious_query(self, query: str) -> bool:
        suspicious_patterns = [
            "union+select", "or+1=1", "and+1=1",
            "javascript:", "vbscript:", "<script",
            "onload=", "onerror=", "onclick=",
            "exec(", "eval(", "system(",
            "../", "..\\", "/etc/passwd",
        ]
        query_lower = query.lower()
        return any(pattern in query_lower for pattern in suspicious_patterns)

    def _is_excessive_requests(self, client_ip: str) -> bool:
        current_time = datetime.utcnow()
        if client_ip not in self.suspicious_requests:
            self.suspicious_requests[client_ip] = {
                "count": 1,
                "first_request": current_time,
                "last_request": current_time,
            }
            return False

        data = self.suspicious_requests[client_ip]
        data["count"] += 1
        data["last_request"] = current_time

        window = (current_time - data["first_request"]).total_seconds()
        if window < 60 and data["count"] > 100:
            return True

        if window > 60:
            self.suspicious_requests[client_ip] = {
                "count": 1,
                "first_request": current_time,
                "last_request": current_time,
            }
        return False

    def _get_client_ip(self, request: Request) -> str:
        headers_to_check = [
            "X-Forwarded-For",
            "X-Real-IP",
            "X-Client-IP",
            "CF-Connecting-IP",
        ]
        for header in headers_to_check:
            ip = request.headers.get(header)
            if ip:
                return ip.split(",")[0].strip()
        return getattr(request.client, "host", "unknown")

    def _log_security_response(self, request: Request, response: Response) -> None:
        if getattr(request.state, "suspicious", False):
            security_logger.warning(
                f"Response to suspicious request: status={response.status_code}, "
                f"path={request.url.path}, ip={self._get_client_ip(request)}"
            )

        required_headers = [
            "Content-Security-Policy",
            "X-Frame-Options",
            "X-Content-Type-Options",
        ]
        missing_headers = [h for h in required_headers if h not in response.headers]
        if missing_headers:
            security_logger.error(
                f"Missing security headers: {missing_headers} for path {request.url.path}"
            )

    def _is_sensitive_path(self, path: str) -> bool:
        sensitive_patterns = [
            "/admin/",
            "/api/admin/",
            "/weddings/verify-guest-access",
            "/weddings/privacy-info",
            "/login",
            "/token",
            "/auth",
            "/users",
            "/forms",
        ]
        return any(pattern in path for pattern in sensitive_patterns)

    @staticmethod
    def _generate_nonce() -> str:
        return secrets.token_urlsafe(16)

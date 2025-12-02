"""
Enhanced Security Headers Middleware - Enterprise-Grade Security
Implements comprehensive security headers and protection mechanisms.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import logging
from datetime import datetime
import secrets
import hashlib
from typing import Dict, List, Optional

# Configure security logging
security_logger = logging.getLogger("wedding_security_headers")

class EnhancedSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Enhanced security headers middleware with comprehensive protection.
    Security Features:
    - Content Security Policy (CSP) with nonce support
    - HTTP Strict Transport Security (HSTS)
    - X-Frame-Options protection
    - X-Content-Type-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Permissions-Policy
    - Cross-Origin policies
    - Security event logging
    """

    def __init__(
        self,
        app,
        hsts_max_age: int = 31536000,  # 1 year
        csp_report_uri: Optional[str] = None,
        enable_csp_reporting: bool = True,
        allowed_origins: List[str] = None,
        debug_mode: bool = False
    ):
        super().__init__(app)
        self.hsts_max_age = hsts_max_age
        self.csp_report_uri = csp_report_uri
        self.enable_csp_reporting = enable_csp_reporting
        self.allowed_origins = allowed_origins or []
        self.debug_mode = debug_mode

        # Security configuration
        self.nonce_cache = {}  # Store nonces per request
        self.suspicious_requests = {}  # Track suspicious activity

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Add comprehensive security headers to all responses.
        """
        try:
            # Generate nonce for this request
            request_nonce = self._generate_nonce()

            # Store nonce in request state
            request.state.csp_nonce = request_nonce

            # Check for suspicious patterns
            self._check_suspicious_request(request)

            # Process the request
            response = await call_next(request)

            # Add security headers
            self._add_security_headers(response, request, request_nonce)

            # Log security events if needed
            self._log_security_response(request, response)

            return response

        except Exception as e:
            security_logger.error(f"Security headers middleware error: {str(e)}")
            # Continue processing even if security headers fail
            response = await call_next(request)
            self._add_basic_security_headers(response)
            return response

    def _generate_nonce(self) -> str:
        """Generate a cryptographically secure nonce"""
        return secrets.token_urlsafe(16)

    def _add_security_headers(self, response: Response, request: Request, nonce: str):
        """Add comprehensive security headers to response"""

        # HTTP Strict Transport Security (HSTS)
        if not self.debug_mode:  # Only in production
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # Content Security Policy (CSP)
        csp_policy = self._build_csp_policy(nonce, request)
        response.headers["Content-Security-Policy"] = csp_policy

        # X-Frame-Options
        response.headers["X-Frame-Options"] = "DENY"

        # X-Content-Type-Options
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy
        response.headers["Permissions-Policy"] = self._build_permissions_policy()

        # Cross-Origin Policies
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        # Cache Control for sensitive responses
        if self._is_sensitive_path(request.url.path):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # Custom security headers
        response.headers["X-Security-Policy"] = "strict"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Server information hiding
        response.headers.pop("Server", None)
        response.headers["Server"] = "WeddingApp-Secure"

        # Request ID for tracking
        request_id = getattr(request.state, 'request_id', None)
        if request_id:
            response.headers["X-Request-ID"] = request_id

    def _build_csp_policy(self, nonce: str, request: Request) -> str:
        """Build Content Security Policy with nonce support"""

        # Determine if this is an admin or public page
        is_admin = "/admin/" in request.url.path
        is_api = "/api/" in request.url.path or request.url.path.startswith("/")

        # Base CSP policy
        csp_directives = {
            "default-src": ["'self'"],
            "script-src": [
                "'self'",
                f"'nonce-{nonce}'",
                "'strict-dynamic'"
            ],
            "style-src": [
                "'self'",
                f"'nonce-{nonce}'",
                "'unsafe-inline'"  # Required for some UI frameworks
            ],
            "img-src": [
                "'self'",
                "data:",
                "https:"
            ],
            "font-src": [
                "'self'",
                "https://fonts.gstatic.com"
            ],
            "connect-src": [
                "'self'"
            ],
            "media-src": ["'self'"],
            "object-src": ["'none'"],
            "frame-src": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "frame-ancestors": ["'none'"],
            "upgrade-insecure-requests": []
        }
        # Additional sources for admin pages
        if is_admin:
            csp_directives["script-src"].extend([
                "https://cdn.jsdelivr.net",  # For admin UI libraries
                "https://unpkg.com"
            ])
            csp_directives["style-src"].extend([
                "https://fonts.googleapis.com",
                "https://cdn.jsdelivr.net"
            ])
        # API endpoints have stricter policy
        if is_api:
            csp_directives = {
                "default-src": ["'none'"],
                "frame-ancestors": ["'none'"],
                "base-uri": ["'none'"],
                "form-action": ["'none'"]
            }
        # Build CSP string
        csp_parts = []
        for directive, sources in csp_directives.items():
            if sources:
                csp_parts.append(f"{directive} {' '.join(sources)}")
            else:
                csp_parts.append(directive)

        csp_policy = "; ".join(csp_parts)

        # Add report URI if configured
        if self.enable_csp_reporting and self.csp_report_uri:
            csp_policy += f"; report-uri {self.csp_report_uri}"

        return csp_policy

    def _build_permissions_policy(self) -> str:
        """Build Permissions Policy header"""

        # Restrictive permissions policy
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
            "picture-in-picture=()"
        ]

        return ", ".join(permissions)

    def _is_sensitive_path(self, path: str) -> bool:
        """Check if path contains sensitive information"""

        sensitive_patterns = [
            "/admin/",
            "/api/admin/",
            "/weddings/verify-guest-access",
            "/weddings/privacy-info",
            "/login",
            "/token",
            "/auth",
            "/users",
            "/forms"
        ]

        return any(pattern in path for pattern in sensitive_patterns)

    def _check_suspicious_request(self, request: Request):
        """Check for suspicious request patterns"""

        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        path = request.url.path

        suspicious_indicators = []

        # Check for suspicious user agents
        if self._is_suspicious_user_agent(user_agent):
            suspicious_indicators.append("suspicious_user_agent")

        # Check for path traversal attempts
        if self._has_path_traversal_attempts(path):
            suspicious_indicators.append("path_traversal")

        # Check for suspicious query parameters
        if request.url.query and self._has_suspicious_query(str(request.url.query)):
            suspicious_indicators.append("suspicious_query")

        # Check for excessive requests from same IP
        if self._is_excessive_requests(client_ip):
            suspicious_indicators.append("excessive_requests")

        # Log suspicious activity
        if suspicious_indicators:
            security_logger.warning(
                f"Suspicious request from {client_ip}: "
                f"path={path}, indicators={suspicious_indicators}, user_agent={user_agent[:100]}"
            )

            # Store in request state for potential blocking
            request.state.suspicious = True
            request.state.suspicious_indicators = suspicious_indicators

    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check for suspicious user agents"""

        suspicious_patterns = [
            "sqlmap", "nikto", "nmap", "masscan", "nessus",
            "burpsuite", "owasp", "zap", "w3af", "skipfish",
            "python-requests", "curl", "wget", "gobuster",
            "dirb", "dirbuster", "wfuzz", "ffuf",
            "<script", "javascript:", "vbscript:",
            "union select", "or 1=1", "../", "..\\",
            "cmd.exe", "/bin/bash", "whoami"
        ]

        user_agent_lower = user_agent.lower()
        return any(pattern in user_agent_lower for pattern in suspicious_patterns)

    def _has_path_traversal_attempts(self, path: str) -> bool:
        """Check for path traversal attempts"""

        traversal_patterns = [
            "../", "..\\", "%2e%2e%2f", "%2e%2e%5c",
            "%252e%252e%252f", "%252e%252e%255c",
            "..%2f", "..%5c", "%2e%2e/",
            "/etc/passwd", "/etc/shadow",
            "C:\\Windows\\", "C:\\Users\\",
            "/proc/version", "/proc/self/environ"
        ]

        path_decoded = path.replace("%", "\\x").encode().decode('unicode_escape', errors='ignore')
        return any(pattern in path or pattern in path_decoded for pattern in traversal_patterns)

    def _has_suspicious_query(self, query: str) -> bool:
        """Check for suspicious query parameters"""

        suspicious_patterns = [
            "union+select", "or+1=1", "and+1=1",
            "javascript:", "vbscript:", "<script",
            "onload=", "onerror=", "onclick=",
            "exec(", "eval(", "system(",
            "../", "..\\", "/etc/passwd"
        ]

        query_lower = query.lower()
        return any(pattern in query_lower for pattern in suspicious_patterns)

    def _is_excessive_requests(self, client_ip: str) -> bool:
        """Check for excessive requests from same IP"""

        current_time = datetime.utcnow()

        if client_ip not in self.suspicious_requests:
            self.suspicious_requests[client_ip] = {
                "count": 1,
                "first_request": current_time,
                "last_request": current_time
            }
            return False

        # Update request tracking
        self.suspicious_requests[client_ip]["count"] += 1
        self.suspicious_requests[client_ip]["last_request"] = current_time

        # Check if excessive (more than 100 requests in 1 minute)
        time_window = (current_time - self.suspicious_requests[client_ip]["first_request"]).total_seconds()
        request_count = self.suspicious_requests[client_ip]["count"]

        if time_window < 60 and request_count > 100:
            return True

        # Reset counter if time window exceeded
        if time_window > 60:
            self.suspicious_requests[client_ip] = {
                "count": 1,
                "first_request": current_time,
                "last_request": current_time
            }

        return False

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""

        headers_to_check = [
            "X-Forwarded-For",
            "X-Real-IP",
            "X-Client-IP",
            "CF-Connecting-IP"
        ]
        for header in headers_to_check:
            ip = request.headers.get(header)
            if ip:
                return ip.split(",")[0].strip()

        return getattr(request.client, 'host', 'unknown')

    def _add_basic_security_headers(self, response: Response):
        """Add basic security headers as fallback"""

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    def _log_security_response(self, request: Request, response: Response):
        """Log security-related response information"""

        # Log suspicious requests
        if hasattr(request.state, 'suspicious') and request.state.suspicious:
            security_logger.warning(
                f"Response to suspicious request: "
                f"status={response.status_code}, "
                f"path={request.url.path}, "
                f"ip={self._get_client_ip(request)}"
            )
        # Log security header failures
        required_headers = [
            "Content-Security-Policy",
            "X-Frame-Options",
            "X-Content-Type-Options"
        ]
        missing_headers = [h for h in required_headers if h not in response.headers]
        if missing_headers:
            security_logger.error(
                f"Missing security headers: {missing_headers} for path {request.url.path}"
            )


# Backward compatibility
SecurityHeadersMiddleware = EnhancedSecurityHeadersMiddleware
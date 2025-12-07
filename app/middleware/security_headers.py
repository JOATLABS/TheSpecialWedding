"""
Security Headers Middleware
"""
from typing import Dict, List, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses
    """
    
    def __init__(
        self,
        app,
        enable_hsts: bool = True,
        enable_csp: bool = True,
        csp_directives: Optional[Dict[str, List[str]]] = None
    ):
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.enable_csp = enable_csp
        self.csp_directives = csp_directives or self._default_csp_directives()
    
    def _default_csp_directives(self) -> Dict[str, List[str]]:
        """Default Content Security Policy directives"""
        return {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
            "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
            "font-src": ["'self'", "https://fonts.gstatic.com"],
            "img-src": ["'self'", "data:", "https:", "blob:"],
            "connect-src": ["'self'", "https://api.thespecialwedding.com"],
            "frame-ancestors": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"]
        }
    
    def _build_csp_header(self) -> str:
        """Build Content Security Policy header value"""
        directives = []
        for directive, sources in self.csp_directives.items():
            sources_str = " ".join(sources)
            directives.append(f"{directive} {sources_str}")
        return "; ".join(directives)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response"""
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), "
            "accelerometer=(), gyroscope=()"
        )
        
        # Add HSTS header for HTTPS connections
        if self.enable_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # Add Content Security Policy
        if self.enable_csp:
            response.headers["Content-Security-Policy"] = self._build_csp_header()
        
        return response
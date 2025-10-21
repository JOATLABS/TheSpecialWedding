"""
Secure Global Error Handler Middleware - Prevents Information Disclosure
Completely replaces vulnerable error handling with enterprise-grade security controls.
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.exceptions import WeddingAppException
from app.utils.secure_error_handler import secure_error_handler
import logging
import os
from datetime import datetime

# Configure secure logging
logger = logging.getLogger("wedding_secure_error_handler")
logger.setLevel(logging.INFO)

# Determine if we're in debug mode
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

class SecureErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Secure middleware to handle all exceptions without information disclosure.
    
    Security Features:
    - Prevents stack trace exposure
    - Sanitizes error messages
    - Logs security events
    - Prevents system information leakage
    - Provides consistent error responses
    - Rate limits error responses
    - Generates unique error IDs for tracking
    """
    
    def __init__(self, app):
        super().__init__(app)
        # Initialize secure error handler with debug mode setting
        self.secure_handler = secure_error_handler
        self.secure_handler.debug_mode = DEBUG_MODE
        
        # Security configuration
        self.max_error_rate = 100  # Max errors per minute per IP
        self.error_tracking = {}  # Track error rates per IP
        self.blocked_ips = set()   # Temporarily blocked IPs
    
    async def dispatch(self, request: Request, call_next):
        """
        Main dispatch method that handles all requests and exceptions securely.
        """
        client_ip = self._get_client_ip(request)
        
        try:
            # Check if IP is blocked due to excessive errors
            if self._is_ip_blocked(client_ip):
                return self._create_blocked_response(client_ip)
            
            # Process the request
            response = await call_next(request)
            
            # Reset error count on successful request
            if client_ip in self.error_tracking:
                self.error_tracking[client_ip]["success_count"] += 1
                # If success rate improves, reduce error penalty
                if self.error_tracking[client_ip]["success_count"] >= 10:
                    self.error_tracking[client_ip]["error_count"] = max(
                        0, self.error_tracking[client_ip]["error_count"] - 5
                    )
            
            return response
            
        except Exception as e:
            # Track error rate
            self._track_error(client_ip)
            
            # Check if this IP should be blocked
            if self._should_block_ip(client_ip):
                self.blocked_ips.add(client_ip)
                logger.warning(f"Blocking IP {client_ip} due to excessive errors")
            
            # Use secure error handler for all exceptions
            return self.secure_handler.handle_exception(request, e)
    
    def _get_client_ip(self, request: Request) -> str:
        """Safely extract client IP for tracking and logging"""
        
        # Try headers in order of preference
        headers_to_check = [
            "X-Forwarded-For",
            "X-Real-IP", 
            "X-Client-IP",
            "CF-Connecting-IP",
            "True-Client-IP"
        ]
        
        for header in headers_to_check:
            ip = request.headers.get(header)
            if ip:
                # Get first IP if comma-separated
                first_ip = ip.split(",")[0].strip()
                if first_ip and len(first_ip) <= 45:  # Max IPv6 length
                    # Basic IP validation
                    if self._is_valid_ip_format(first_ip):
                        return first_ip
        
        # Fallback to client host
        return getattr(request.client, 'host', 'unknown')
    
    def _is_valid_ip_format(self, ip: str) -> bool:
        """Validate IP address format"""
        import re
        
        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ipv4_pattern, ip):
            parts = ip.split('.')
            return all(0 <= int(part) <= 255 for part in parts)
        
        # IPv6 pattern (basic)
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        if re.match(ipv6_pattern, ip):
            return True
        
        return False
    
    def _track_error(self, client_ip: str):
        """Track error counts per IP address"""
        current_time = datetime.utcnow()
        
        if client_ip not in self.error_tracking:
            self.error_tracking[client_ip] = {
                "error_count": 0,
                "success_count": 0,
                "last_error": None,
                "first_error": current_time
            }
        
        self.error_tracking[client_ip]["error_count"] += 1
        self.error_tracking[client_ip]["last_error"] = current_time
        
        # Clean up old tracking data (older than 1 hour)
        self._cleanup_old_tracking()
    
    def _should_block_ip(self, client_ip: str) -> bool:
        """Determine if an IP should be blocked due to excessive errors"""
        if client_ip == "unknown":
            return False  # Don't block unknown IPs
        
        if client_ip not in self.error_tracking:
            return False
        
        tracking_data = self.error_tracking[client_ip]
        error_count = tracking_data["error_count"]
        success_count = tracking_data["success_count"]
        
        # Block if error rate is too high
        if error_count > self.max_error_rate:
            return True
        
        # Block if error ratio is too high (90% errors)
        total_requests = error_count + success_count
        if total_requests > 50 and (error_count / total_requests) > 0.9:
            return True
        
        return False
    
    def _is_ip_blocked(self, client_ip: str) -> bool:
        """Check if an IP is currently blocked"""
        return client_ip in self.blocked_ips
    
    def _create_blocked_response(self, client_ip: str) -> JSONResponse:
        """Create response for blocked IPs"""
        logger.warning(f"Blocked IP {client_ip} attempted request")
        
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "IP_BLOCKED",
                    "message": "Your IP has been temporarily blocked due to excessive errors. Please try again later.",
                    "timestamp": datetime.utcnow().isoformat(),
                    "retry_after": 3600  # 1 hour
                }
            },
            headers={
                "Retry-After": "3600",
                "X-Rate-Limit": "Blocked"
            }
        )
    
    def _cleanup_old_tracking(self):
        """Clean up old error tracking data"""
        current_time = datetime.utcnow()
        cutoff_time = current_time - datetime.timedelta(hours=1)
        
        # Remove old tracking data
        expired_ips = []
        for ip, data in self.error_tracking.items():
            if data["first_error"] < cutoff_time:
                expired_ips.append(ip)
        
        for ip in expired_ips:
            del self.error_tracking[ip]
            # Also unblock if blocked
            self.blocked_ips.discard(ip)
    
    def get_error_stats(self) -> dict:
        """Get current error statistics (for monitoring)"""
        total_tracked_ips = len(self.error_tracking)
        total_blocked_ips = len(self.blocked_ips)
        total_errors = sum(data["error_count"] for data in self.error_tracking.values())
        
        return {
            "tracked_ips": total_tracked_ips,
            "blocked_ips": total_blocked_ips,
            "total_errors": total_errors,
            "health_status": "ok" if total_blocked_ips < 10 else "degraded"
        }


# Backward compatibility alias
ErrorHandlerMiddleware = SecureErrorHandlerMiddleware
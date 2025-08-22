"""
CSRF Protection Middleware
"""
from fastapi import Request, HTTPException, Header
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import secrets
import hashlib
import time
from typing import Optional, Dict
from collections import defaultdict


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF Protection using Double Submit Cookie pattern
    """
    
    def __init__(
        self,
        app,
        secret_key: str,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        safe_methods: list = None,
        exclude_paths: list = None
    ):
        super().__init__(app)
        self.secret_key = secret_key
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.safe_methods = safe_methods or ["GET", "HEAD", "OPTIONS", "TRACE"]
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json", "/admin/token"]
        
        # Store tokens with expiration
        self.token_store: Dict[str, float] = {}
        self.token_lifetime = 3600  # 1 hour
    
    def _generate_csrf_token(self, session_id: str) -> str:
        """Generate a new CSRF token"""
        # Create a unique token based on session and timestamp
        timestamp = str(time.time())
        token_data = f"{session_id}:{timestamp}:{self.secret_key}"
        token = hashlib.sha256(token_data.encode()).hexdigest()
        
        # Store token with expiration
        self.token_store[token] = time.time() + self.token_lifetime
        
        # Clean expired tokens
        self._cleanup_expired_tokens()
        
        return token
    
    def _cleanup_expired_tokens(self):
        """Remove expired tokens from store"""
        current_time = time.time()
        expired_tokens = [
            token for token, expiry in self.token_store.items()
            if expiry < current_time
        ]
        for token in expired_tokens:
            del self.token_store[token]
    
    def _verify_csrf_token(self, cookie_token: str, header_token: str) -> bool:
        """Verify CSRF token"""
        # Check if tokens match
        if cookie_token != header_token:
            return False
        
        # Check if token exists and is not expired
        if cookie_token not in self.token_store:
            return False
        
        if self.token_store[cookie_token] < time.time():
            del self.token_store[cookie_token]
            return False
        
        return True
    
    def _is_excluded_path(self, path: str) -> bool:
        """Check if path is excluded from CSRF protection"""
        return any(excluded in path for excluded in self.exclude_paths)
    
    def _get_session_id(self, request: Request) -> str:
        """Get or create session ID from request"""
        # Try to get from cookie first
        session_id = request.cookies.get("session_id")
        
        if not session_id:
            # Generate new session ID
            session_id = secrets.token_urlsafe(32)
        
        return session_id
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with CSRF protection"""
        
        # Skip CSRF check for safe methods
        if request.method in self.safe_methods:
            response = await call_next(request)
            return response
        
        # Skip CSRF check for excluded paths
        if self._is_excluded_path(request.url.path):
            response = await call_next(request)
            return response
        
        # Get session ID
        session_id = self._get_session_id(request)
        
        # Get CSRF tokens
        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get(self.header_name)
        
        # For non-safe methods, verify CSRF token
        if not cookie_token or not header_token:
            # Generate new token for first request
            if not cookie_token:
                new_token = self._generate_csrf_token(session_id)
                response = await call_next(request)
                response.set_cookie(
                    key=self.cookie_name,
                    value=new_token,
                    httponly=False,  # JavaScript needs to read this
                    samesite="strict",
                    secure=True,  # Only over HTTPS in production
                    max_age=self.token_lifetime
                )
                response.set_cookie(
                    key="session_id",
                    value=session_id,
                    httponly=True,
                    samesite="strict",
                    secure=True,
                    max_age=86400  # 24 hours
                )
                return response
            else:
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token missing in request header"
                )
        
        # Verify CSRF token
        if not self._verify_csrf_token(cookie_token, header_token):
            raise HTTPException(
                status_code=403,
                detail="Invalid CSRF token"
            )
        
        # Token is valid, continue with request
        response = await call_next(request)
        
        # Refresh token expiration
        if cookie_token in self.token_store:
            self.token_store[cookie_token] = time.time() + self.token_lifetime
        
        return response


class CSRFTokenGenerator:
    """
    Utility class for generating CSRF tokens for forms
    """
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    
    def generate_token(self, user_id: str) -> str:
        """Generate a CSRF token for a specific user"""
        timestamp = str(int(time.time()))
        token_data = f"{user_id}:{timestamp}:{self.secret_key}"
        return hashlib.sha256(token_data.encode()).hexdigest()
    
    def verify_token(self, token: str, user_id: str, max_age: int = 3600) -> bool:
        """Verify a CSRF token"""
        # In production, this would check against stored tokens
        # For now, we'll regenerate and compare
        current_time = int(time.time())
        
        # Check tokens within the time window
        for time_offset in range(0, max_age, 60):  # Check every minute
            check_time = current_time - time_offset
            expected_token = hashlib.sha256(
                f"{user_id}:{check_time}:{self.secret_key}".encode()
            ).hexdigest()
            
            if token == expected_token:
                return True
        
        return False
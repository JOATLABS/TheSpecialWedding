"""
Audit Logging Middleware for security and compliance
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import json
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.core.database import mongo
import hashlib
import asyncio


# Setup audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# File handler for audit logs
file_handler = logging.FileHandler("audit.log")
file_handler.setLevel(logging.INFO)

# Formatter for audit logs
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
audit_logger.addHandler(file_handler)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Audit logging middleware for tracking security-relevant events
    """
    def __init__(
        self,
        app,
        log_to_db: bool = True,
        log_to_file: bool = True,
        sensitive_paths: list = None,
        excluded_paths: list = None
    ):
        super().__init__(app)
        self.log_to_db = log_to_db
        self.log_to_file = log_to_file
        self.sensitive_paths = sensitive_paths or [
            "/admin/",
            "/api/auth/",
            "/api/users/",
            "/api/subscription/"
        ]
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/static/"
        ]

        # Audit collection in database
        if self.log_to_db:
            self.audit_collection = mongo.db["audit_logs"]

    def _should_log(self, path: str) -> bool:
        """Determine if request should be logged"""
        # Skip excluded paths
        if any(excluded in path for excluded in self.excluded_paths):
            return False

        # Always log sensitive paths
        if any(sensitive in path for sensitive in self.sensitive_paths):
            return True

        # Log all POST, PUT, DELETE, PATCH requests
        return True

    def _get_client_info(self, request: Request) -> Dict[str, Any]:
        """Extract client information from request"""
        # Get IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        else:
            ip_address = request.headers.get("X-Real-IP") or request.client.host

        # Get user agent
        user_agent = request.headers.get("User-Agent", "Unknown")

        # Get authentication info
        auth_header = request.headers.get("Authorization", "")
        is_authenticated = bool(auth_header)

        return {
            "ip_address": ip_address,
            "user_agent": user_agent,
            "is_authenticated": is_authenticated,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params)
        }
    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize sensitive data before logging"""
        if isinstance(data, dict):
            sanitized = {}
            sensitive_keys = [
                "password", "token", "secret", "api_key", "credit_card",
                "ssn", "social_security", "bank_account", "private_key"
            ]
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    sanitized[key] = "***REDACTED***"
                elif isinstance(value, dict):
                    sanitized[key] = self._sanitize_data(value)
                elif isinstance(value, list):
                    sanitized[key] = [self._sanitize_data(item) for item in value]
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        else:
            return data
    def _create_audit_entry(
        self,
        request_info: Dict[str, Any],
        response_status: int,
        response_time: float,
        user_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create audit log entry"""
        return {
            "timestamp": datetime.now(timezone.utc),
            "event_type": self._determine_event_type(request_info["method"], request_info["path"]),
            "user_id": user_id,
            "ip_address": request_info["ip_address"],
            "user_agent": request_info["user_agent"],
            "method": request_info["method"],
            "path": request_info["path"],
            "query_params": self._sanitize_data(request_info["query_params"]),
            "response_status": response_status,
            "response_time_ms": round(response_time * 1000, 2),
            "success": 200 <= response_status < 400,
            "error_message": error_message,
            "session_hash": self._generate_session_hash(request_info)
        }
    def _determine_event_type(self, method: str, path: str) -> str:
        """Determine the type of event for categorization"""
        if "login" in path or "token" in path:
            return "authentication"
        elif "logout" in path:
            return "logout"
        elif "register" in path or "signup" in path:
            return "registration"
        elif "admin" in path:
            return "admin_action"
        elif "subscription" in path or "payment" in path:
            return "billing"
        elif method in ["POST", "PUT", "PATCH"]:
            return "data_modification"
        elif method == "DELETE":
            return "data_deletion"
        elif method == "GET":
            return "data_access"
        else:
            return "other"
    def _generate_session_hash(self, request_info: Dict[str, Any]) -> str:
        """Generate a session hash for correlating requests"""
        session_data = f"{request_info['ip_address']}:{request_info['user_agent']}"
        return hashlib.md5(session_data.encode()).hexdigest()[:16]
    async def _log_to_database(self, audit_entry: Dict[str, Any]):
        """Log audit entry to database"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.audit_collection.insert_one,
                audit_entry
            )
        except Exception as e:
            audit_logger.error(f"Failed to log to database: {str(e)}")
    def _log_to_file(self, audit_entry: Dict[str, Any]):
        """Log audit entry to file"""
        # Convert datetime to string for JSON serialization
        audit_entry_copy = audit_entry.copy()
        audit_entry_copy["timestamp"] = audit_entry_copy["timestamp"].isoformat()

        log_message = json.dumps(audit_entry_copy)

        # Log based on event severity
        if audit_entry["success"]:
            audit_logger.info(log_message)
        else:
            audit_logger.warning(log_message)

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with audit logging"""

        # Check if request should be logged
        if not self._should_log(request.url.path):
            return await call_next(request)

        # Capture request information
        request_info = self._get_client_info(request)
        start_time = time.time()

        # Process request
        try:
            response = await call_next(request)
            response_time = time.time() - start_time
            # Create audit entry
            audit_entry = self._create_audit_entry(
                request_info,
                response.status_code,
                response_time
            )

            # Log to database (async)
            if self.log_to_db:
                asyncio.create_task(self._log_to_database(audit_entry))

            # Log to file
            if self.log_to_file:
                self._log_to_file(audit_entry)

            return response

        except Exception as e:
            response_time = time.time() - start_time

            # Create error audit entry
            audit_entry = self._create_audit_entry(
                request_info,
                500,
                response_time,
                error_message=str(e)
            )

            # Log error
            if self.log_to_db:
                asyncio.create_task(self._log_to_database(audit_entry))

            if self.log_to_file:
                self._log_to_file(audit_entry)

            # Re-raise the exception
            raise


class AuditEventLogger:
    """
    Utility class for logging specific audit events
    """

    def __init__(self):
        self.audit_collection = mongo.db["audit_logs"]

    async def log_login_attempt(
        self,
        email: str,
        success: bool,
        ip_address: str,
        error_message: Optional[str] = None
    ):
        """Log login attempt"""
        await self.audit_collection.insert_one({
            "timestamp": datetime.now(timezone.utc),
            "event_type": "login_attempt",
            "email": email,
            "success": success,
            "ip_address": ip_address,
            "error_message": error_message
        })
    async def log_data_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: str
    ):
        """Log data access event"""
        await self.audit_collection.insert_one({
            "timestamp": datetime.now(timezone.utc),
            "event_type": "data_access",
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "ip_address": ip_address
        })
    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log security event"""
        await self.audit_collection.insert_one({
            "timestamp": datetime.now(timezone.utc),
            "event_type": "security_event",
            "security_event_type": event_type,
            "severity": severity,
            "description": description,
            "user_id": user_id,
            "ip_address": ip_address,
            "additional_data": additional_data
        })
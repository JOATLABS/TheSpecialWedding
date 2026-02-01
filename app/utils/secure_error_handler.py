"""
Secure Error Handler - Prevents Information Disclosure
Provides sanitized error responses for production environment
"""

import logging
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.utils.exceptions import WeddingAppException
import secrets

# Configure secure logging
secure_logger = logging.getLogger("wedding_security_errors")
secure_logger.setLevel(logging.INFO)

class SecureErrorHandler:
    """
    Secure error handler that prevents information disclosure vulnerabilities.
    Sanitizes all error responses and logs security events.
    """

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.error_id_cache = {}

    def handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """
        Handle any exception securely without exposing system information.

        Args:
            request: FastAPI request object
            exc: Exception that occurred

        Returns:
            JSONResponse with sanitized error information
        """
        # Generate unique error ID for tracking
        error_id = self._generate_error_id()

        # Log the full error details securely (server-side only)
        self._log_full_error(error_id, request, exc)

        if isinstance(exc, WeddingAppException):
            return self._handle_wedding_app_exception(request, exc, error_id)
        elif isinstance(exc, HTTPException):
            return self._handle_http_exception(request, exc, error_id)
        else:
            return self._handle_unexpected_exception(request, exc, error_id)

    def _handle_wedding_app_exception(self, request: Request, exc: WeddingAppException, error_id: str) -> JSONResponse:
        """Handle custom WeddingApp exceptions"""

        # Sanitize the error message
        sanitized_message = self._sanitize_error_message(exc.message)

        error_response = {
            "error": {
                "code": exc.error_code,
                "message": sanitized_message,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "error_id": error_id
            }
        }

        # Only add field information for validation errors (safe to expose)
        if hasattr(exc, 'field') and exc.field and exc.error_code in ["VALIDATION_ERROR", "INVALID_INPUT"]:
            error_response["error"]["field"] = self._sanitize_field_name(exc.field)

        # Add retry_after for rate limit errors
        if hasattr(exc, 'retry_after'):
            error_response["error"]["retry_after"] = exc.retry_after

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )

    def _handle_http_exception(self, request: Request, exc: HTTPException, error_id: str) -> JSONResponse:
        """Handle FastAPI HTTP exceptions"""

        # Map HTTP status codes to secure error messages
        secure_messages = {
            400: "Bad request - invalid input provided",
            401: "Authentication required",
            403: "Access denied - insufficient permissions",
            404: "Resource not found",
            405: "Method not allowed",
            408: "Request timeout",
            409: "Conflict - resource already exists",
            410: "Resource no longer available",
            413: "Request too large",
            422: "Invalid input data",
            429: "Too many requests - please try again later",
            500: "Internal server error",
            502: "Service temporarily unavailable",
            503: "Service temporarily unavailable",
            504: "Request timeout"
        }

        status_code = exc.status_code
        secure_message = secure_messages.get(status_code, "An error occurred")

        # Handle validation errors specially
        if status_code == 422 and isinstance(exc.detail, list):
            return self._handle_validation_errors(request, exc.detail, error_id)

        error_response = {
            "error": {
                "code": self._get_error_code_from_status(status_code),
                "message": secure_message,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "error_id": error_id
            }
        }
        return JSONResponse(
            status_code=status_code,
            content=error_response
        )

    def _handle_validation_errors(self, request: Request, details: list, error_id: str) -> JSONResponse:
        """Handle Pydantic validation errors securely"""

        sanitized_errors = []
        for error in details:
            # Extract field path safely
            field_path = []
            for loc in error.get("loc", []):
                if isinstance(loc, (str, int)):
                    field_path.append(str(loc))

            field = ".".join(field_path) if field_path else "unknown"

            # Sanitize error message
            error_type = error.get("type", "validation_error")
            message = self._get_validation_error_message(error_type)

            sanitized_errors.append({
                "field": self._sanitize_field_name(field),
                "message": message,
                "type": error_type
            })
        error_response = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "error_id": error_id,
                "details": sanitized_errors
            }
        }
        return JSONResponse(
            status_code=422,
            content=error_response
        )

    def _handle_unexpected_exception(self, request: Request, exc: Exception, error_id: str) -> JSONResponse:
        """Handle unexpected exceptions without exposing system information"""

        # Log security event for unexpected errors
        self._log_security_event("UNEXPECTED_ERROR", {
            "error_id": error_id,
            "exception_type": type(exc).__name__,
            "path": str(request.url.path),
            "method": request.method
        })
        error_response = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "error_id": error_id
            }
        }
        return JSONResponse(
            status_code=500,
            content=error_response
        )
    def _sanitize_error_message(self, message: str) -> str:
        """Sanitize error message to prevent information disclosure"""
        if not message:
            return "An error occurred"
        # Remove file paths, stack traces, and system information
        sensitive_patterns = [
            r'/[\w/]+\.py',  # File paths
            r'C:\\[\w\\]+\.py',  # Windows file paths
            r'File ".*?"',  # Python file references
            r'line \d+',  # Line numbers
            r'Traceback.*?:',  # Stack trace headers
            r'Error.*?:.*?\n',  # Error details with newlines
            r'Exception.*?:',  # Exception details
            r'mongodb://.*?@',  # Database URLs
            r'postgres://.*?@',  # Database URLs
            r'mysql://.*?@',  # Database URLs
            r'redis://.*?@',  # Redis URLs
            r'Database.*?error',  # Database error messages
            r'Connection.*?refused',  # Connection errors
            r'Permission denied',  # System permission errors
            r'No such file or directory',  # File system errors
        ]

        import re
        sanitized = message

        for pattern in sensitive_patterns:
            sanitized = re.sub(pattern, '[SYSTEM_INFO_REMOVED]', sanitized, flags=re.IGNORECASE)

        # Remove any remaining file extensions and paths
        sanitized = re.sub(r'\b[\w/\\]+\.(py|js|ts|sql|json)\b', '[FILE_REMOVED]', sanitized)

        # Truncate very long messages
        if len(sanitized) > 200:
            sanitized = sanitized[:197] + "..."

        return sanitized

    def _sanitize_field_name(self, field: str) -> str:
        """Sanitize field names to prevent information disclosure"""
        if not field:
            return "field"

        # Only allow alphanumeric characters, dots, and underscores
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9._]', '', field)

        # Truncate long field names
        if len(sanitized) > 50:
            sanitized = sanitized[:50]

        return sanitized or "field"

    def _get_validation_error_message(self, error_type: str) -> str:
        """Get user-friendly validation error messages"""

        error_messages = {
            "missing": "This field is required",
            "value_error": "Invalid value provided",
            "type_error": "Invalid data type",
            "string_too_short": "Input is too short",
            "string_too_long": "Input is too long",
            "string_pattern_mismatch": "Input format is invalid",
            "number_not_gt": "Number must be greater than minimum value",
            "number_not_ge": "Number must be greater than or equal to minimum value",
            "number_not_lt": "Number must be less than maximum value",
            "number_not_le": "Number must be less than or equal to maximum value",
            "email": "Invalid email address format",
            "url": "Invalid URL format",
            "json_invalid": "Invalid JSON format",
            "uuid_invalid": "Invalid UUID format",
            "datetime_parsing": "Invalid date/time format",
            "list_min_length": "List must have minimum required items",
            "list_max_length": "List has too many items",
            "dict_key_required": "Required dictionary key missing"
        }

        return error_messages.get(error_type, "Invalid input provided")

    def _get_error_code_from_status(self, status_code: int) -> str:
        """Map HTTP status codes to error codes"""

        status_to_code = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            408: "REQUEST_TIMEOUT",
            409: "CONFLICT",
            410: "GONE",
            413: "PAYLOAD_TOO_LARGE",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_SERVER_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
            504: "GATEWAY_TIMEOUT"
        }

        return status_to_code.get(status_code, "HTTP_ERROR")

    def _generate_error_id(self) -> str:
        """Generate unique error ID for tracking"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_part = secrets.token_hex(4)
        return f"ERR-{timestamp}-{random_part}"

    def _log_full_error(self, error_id: str, request: Request, exc: Exception):
        """Log full error details for debugging (server-side only)"""

        try:
            error_details = {
                "error_id": error_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "path": str(request.url.path),
                "method": request.method,
                "user_agent": request.headers.get("user-agent", "unknown"),
                "client_ip": self._get_client_ip(request)
            }

            # Log the full traceback if in debug mode
            if self.debug_mode:
                error_details["traceback"] = traceback.format_exc()

            secure_logger.error(f"Error {error_id}: {error_details}")

        except Exception as log_exc:
            # If logging fails, at least try to log the basic error
            secure_logger.error(f"Failed to log error details: {str(log_exc)}")

    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security-related events"""

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "severity": "WARNING",
            "details": details
        }

        secure_logger.warning(f"Security Event: {event_type} - {details}")

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address safely"""

        # Try various headers for real IP
        ip_headers = [
            "X-Forwarded-For",
            "X-Real-IP",
            "X-Client-IP",
            "CF-Connecting-IP"
        ]

        for header in ip_headers:
            ip = request.headers.get(header)
            if ip:
                # Take first IP if comma-separated
                return ip.split(",")[0].strip()
        # Fallback to request client
        return getattr(request.client, 'host', 'unknown')


# Global secure error handler instance
secure_error_handler = SecureErrorHandler()
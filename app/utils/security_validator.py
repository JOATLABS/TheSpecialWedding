"""
Comprehensive Security Validator for Wedding Application
Implements enterprise-grade security controls for production deployment
"""

import hashlib
import html
import logging
import re
import secrets
import time
import unicodedata
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

# Configure security logging
security_logger = logging.getLogger("wedding_security")
security_logger.setLevel(logging.INFO)


class SecurityValidator:
    """
    Comprehensive security validation utility for the wedding application.
    Implements defense-in-depth security controls.
    """

    # Security patterns for injection detection
    NOSQL_INJECTION_PATTERNS = [
        r"\$where\s*:",
        r"\$regex\s*:",
        r"\$ne\s*:",
        r"\$nin\s*:",
        r"\$or\s*:",
        r"\$and\s*:",
        r"\$nor\s*:",
        r"\$not\s*:",
        r"\$exists\s*:",
        r"\$type\s*:",
        r"\$elemMatch\s*:",
        r"\$size\s*:",
        r"\$all\s*:",
        r"\$mod\s*:",
        r"javascript:",
        r"eval\s*\(",
        r"function\s*\(",
        r"constructor",
        r"\$\w+\s*:",
        r"\{\s*\$\w+",
        r"ObjectId\s*\(",
        r"ISODate\s*\(",
        r"new\s+Date\s*\(",
        r"new\s+ObjectId\s*\(",
    ]
    SQL_INJECTION_PATTERNS = [
        r"union\s+select",
        r"or\s+1\s*=\s*1",
        r"and\s+1\s*=\s*1",
        r"drop\s+table",
        r"delete\s+from",
        r"insert\s+into",
        r"update\s+set",
        r"create\s+table",
        r"alter\s+table",
        r"exec\s*\(",
        r"sp_\w+",
        r"xp_\w+",
        r"--",
        r"/\*",
        r"\*/",
        r"char\s*\(",
        r"cast\s*\(",
        r"convert\s*\(",
    ]
    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"</script>",
        r"javascript:",
        r"vbscript:",
        r"onload\s*=",
        r"onerror\s*=",
        r"onclick\s*=",
        r"onmouseover\s*=",
        r"<iframe[^>]*>",
        r"</iframe>",
        r"<object[^>]*>",
        r"</object>",
        r"<embed[^>]*>",
        r"<form[^>]*>",
        r"<input[^>]*>",
        r"expression\s*\(",
        r"url\s*\(",
        r"@import",
        r"<meta[^>]*>",
    ]
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e%2f",
        r"%2e%2e%5c",
        r"%252e%252e%252f",
        r"%252e%252e%255c",
        r"..%2f",
        r"..%5c",
        r"%2e%2e/",
        r"\.\./\.\./\.\./\.\./\.\./\.\./\.\.",
        r"/etc/passwd",
        r"/etc/shadow",
        r"C:\\Windows\\",
        r"C:\\Users\\",
    ]
    COMMAND_INJECTION_PATTERNS = [
        r";.*(?:rm|del|cat|type|curl|wget|nc|netcat)",
        r"\|.*(?:rm|del|cat|type|curl|wget|nc|netcat)",
        r"&&.*(?:rm|del|cat|type|curl|wget|nc|netcat)",
        r"\`.*(?:rm|del|cat|type|curl|wget|nc|netcat)",
        r"\$\(.*(?:rm|del|cat|type|curl|wget|nc|netcat)",
        r"exec\s*\(",
        r"eval\s*\(",
        r"system\s*\(",
        r"shell_exec\s*\(",
    ]

    def __init__(self):
        self.failed_attempts = {}
        self.blocked_ips = {}
        self.token_store = {}
        self.max_attempts = 5
        self.lockout_duration = 300  # 5 minutes
        self.progressive_delays = [1, 2, 4, 8, 16]  # Progressive delays in seconds

    def validate_input_security(
        self, value: Any, field_name: str, context: str = ""
    ) -> tuple[bool, str]:
        """
        Comprehensive input validation for security vulnerabilities.

        Args:
            value: Input value to validate
            field_name: Name of the field being validated
            context: Context for logging
        Returns:
            Tuple of (is_valid, sanitized_value or error_message)
        """
        if value is None:
            return True, ""

        try:
            # Convert to string for validation
            str_value = str(value).strip()

            # Check for empty/whitespace only
            if not str_value:
                return True, ""

            # Length validation
            if len(str_value) > 1000:  # Reasonable limit
                security_logger.warning(
                    f"Input length exceeded for field {field_name}: {len(str_value)} chars"
                )
                return False, "Input too long"

            # Unicode normalization to prevent bypass attempts
            normalized_value = unicodedata.normalize("NFKC", str_value)

            # Check for NoSQL injection patterns
            if self._contains_injection_patterns(
                normalized_value, self.NOSQL_INJECTION_PATTERNS
            ):
                security_logger.warning(
                    f"NoSQL injection attempt detected in field {field_name}: {context}"
                )
                return False, "Invalid input detected"
            # Check for SQL injection patterns
            if self._contains_injection_patterns(
                normalized_value, self.SQL_INJECTION_PATTERNS
            ):
                security_logger.warning(
                    f"SQL injection attempt detected in field {field_name}: {context}"
                )
                return False, "Invalid input detected"
            # Check for XSS patterns
            if self._contains_injection_patterns(normalized_value, self.XSS_PATTERNS):
                security_logger.warning(
                    f"XSS attempt detected in field {field_name}: {context}"
                )
                return False, "Invalid input detected"
            # Check for path traversal patterns
            if self._contains_injection_patterns(
                normalized_value, self.PATH_TRAVERSAL_PATTERNS
            ):
                security_logger.warning(
                    f"Path traversal attempt detected in field {field_name}: {context}"
                )
                return False, "Invalid input detected"
            # Check for command injection patterns
            if self._contains_injection_patterns(
                normalized_value, self.COMMAND_INJECTION_PATTERNS
            ):
                security_logger.warning(
                    f"Command injection attempt detected in field {field_name}: {context}"
                )
                return False, "Invalid input detected"
            # Field-specific validation
            sanitized_value = self._field_specific_validation(
                normalized_value, field_name
            )
            if sanitized_value is False:
                return False, "Invalid field format"

            return True, sanitized_value

        except Exception as e:
            security_logger.error(
                f"Security validation error for field {field_name}: {e!s}"
            )
            return False, "Validation error"

    def _contains_injection_patterns(self, value: str, patterns: list[str]) -> bool:
        """Check if value contains any injection patterns"""
        value_lower = value.lower()

        for pattern in patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False

    def _field_specific_validation(self, value: str, field_name: str) -> str | bool:
        """Perform field-specific validation and sanitization"""

        if field_name.lower() in ["name", "guest_name", "full_name"]:
            return self._validate_name(value)
        elif field_name.lower() in ["phone", "phone_number"]:
            return self._validate_phone(value)
        elif field_name.lower() in ["token", "guest_token", "verification_token"]:
            return self._validate_token(value)
        elif field_name.lower() in ["password", "wedding_password"]:
            return self._validate_password(value)
        elif field_name.lower() in ["slug", "wedding_slug"]:
            return self._validate_slug(value)
        elif field_name.lower() in ["email"]:
            return self._validate_email(value)
        else:
            # Generic sanitization
            return html.escape(value, quote=True)

    def _validate_name(self, value: str) -> str | bool:
        """Validate and sanitize name fields"""
        # Allow letters, spaces, hyphens, apostrophes, and common unicode characters
        name_pattern = r"^[a-zA-Z\u00C0-\u017F\u0100-\u024F\u1E00-\u1EFF\s\-'.]+$"

        if not re.match(name_pattern, value):
            return False

        if len(value) > 100:  # Reasonable name length
            return False

        # Remove extra whitespace and normalize
        sanitized = re.sub(r"\s+", " ", value.strip())
        return html.escape(sanitized, quote=True)

    def _validate_phone(self, value: str) -> str | bool:
        """Validate and sanitize phone numbers"""
        # Remove all non-digit characters for validation
        digits_only = re.sub(r"\D", "", value)

        # Check if it's a valid phone number length
        if len(digits_only) < 10 or len(digits_only) > 15:
            return False

        # Only allow digits, spaces, hyphens, parentheses, and plus sign
        phone_pattern = r"^[\d\s\-\(\)\+\.]+$"

        if not re.match(phone_pattern, value):
            return False

        return html.escape(value.strip(), quote=True)

    def _validate_token(self, value: str) -> str | bool:
        """Validate security tokens"""
        # Tokens should be alphanumeric with possible hyphens/underscores
        token_pattern = r"^[a-zA-Z0-9\-_]+$"

        if not re.match(token_pattern, value):
            return False

        # Reasonable token length
        if len(value) < 8 or len(value) > 255:
            return False

        return value  # No need to escape tokens

    def _validate_password(self, value: str) -> str | bool:
        """Validate passwords (for wedding password protection)"""
        # Password should not contain HTML or script tags
        if "<" in value or ">" in value or "script" in value.lower():
            return False

        if len(value) > 128:  # Reasonable password length
            return False

        return value  # Don't escape passwords

    def _validate_slug(self, value: str) -> str | bool:
        """Validate wedding slugs"""
        # Slugs should be lowercase alphanumeric with hyphens
        slug_pattern = r"^[a-z0-9\-]+$"

        if not re.match(slug_pattern, value):
            return False

        if len(value) > 100:
            return False

        return value

    def _validate_email(self, value: str) -> str | bool:
        """Validate email addresses"""
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(email_pattern, value):
            return False

        if len(value) > 254:  # RFC 5321 limit
            return False

        return html.escape(value.lower().strip(), quote=True)

    def validate_object_id(self, value: str) -> tuple[bool, str | None]:
        """Validate MongoDB ObjectId"""
        try:
            if not value:
                return False, "ObjectId cannot be empty"

            # Check if it's a valid ObjectId format
            ObjectId(value)
            return True, value

        except InvalidId:
            security_logger.warning(f"Invalid ObjectId format: {value}")
            return False, "Invalid ID format"
        except Exception as e:
            security_logger.error(f"ObjectId validation error: {e!s}")
            return False, "ID validation error"

    def check_brute_force_protection(
        self, identifier: str, context: str = ""
    ) -> tuple[bool, int]:
        """
        Check and enforce brute force protection with progressive delays.

        Args:
            identifier: IP address or user identifier
            context: Context for logging

        Returns:
            Tuple of (is_allowed, delay_seconds)
        """
        current_time = time.time()

        # Clean up old failed attempts (older than lockout duration)
        self._cleanup_old_attempts(current_time)

        # Check if IP is blocked
        if identifier in self.blocked_ips:
            block_time, block_duration = self.blocked_ips[identifier]
            if current_time < block_time + block_duration:
                remaining_time = int((block_time + block_duration) - current_time)
                security_logger.warning(
                    f"Blocked identifier {identifier} attempted access. Context: {context}"
                )
                return False, remaining_time
            else:
                # Unblock expired blocks
                del self.blocked_ips[identifier]

        # Get failed attempt count
        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = []

        attempts = self.failed_attempts[identifier]
        recent_attempts = [
            t for t in attempts if current_time - t < self.lockout_duration
        ]

        # Progressive delays based on attempt count
        if len(recent_attempts) > 0:
            delay_index = min(
                len(recent_attempts) - 1, len(self.progressive_delays) - 1
            )
            delay = self.progressive_delays[delay_index]
            # If too many attempts, block the identifier
            if len(recent_attempts) >= self.max_attempts:
                self.blocked_ips[identifier] = (current_time, self.lockout_duration)
                security_logger.warning(
                    f"Identifier {identifier} blocked due to excessive failed attempts. Context: {context}"
                )
                return False, self.lockout_duration

            return True, delay

        return True, 0

    def record_failed_attempt(self, identifier: str, context: str = ""):
        """Record a failed authentication attempt"""
        current_time = time.time()

        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = []

        self.failed_attempts[identifier].append(current_time)

        security_logger.warning(
            f"Failed attempt recorded for {identifier}. Context: {context}"
        )

    def record_successful_attempt(self, identifier: str, context: str = ""):
        """Record a successful authentication attempt and clear failed attempts"""
        if identifier in self.failed_attempts:
            del self.failed_attempts[identifier]

        if identifier in self.blocked_ips:
            del self.blocked_ips[identifier]

        security_logger.info(
            f"Successful authentication for {identifier}. Context: {context}"
        )

    def _cleanup_old_attempts(self, current_time: float):
        """Clean up old failed attempts and expired blocks"""
        # Clean failed attempts
        for identifier in list(self.failed_attempts.keys()):
            attempts = self.failed_attempts[identifier]
            recent_attempts = [
                t for t in attempts if current_time - t < self.lockout_duration
            ]
            if recent_attempts:
                self.failed_attempts[identifier] = recent_attempts
            else:
                del self.failed_attempts[identifier]
        # Clean expired blocks
        for identifier in list(self.blocked_ips.keys()):
            block_time, block_duration = self.blocked_ips[identifier]
            if current_time >= block_time + block_duration:
                del self.blocked_ips[identifier]

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure token"""
        return secrets.token_urlsafe(length)

    def validate_token_format(self, token: str, expected_length: int = None) -> bool:
        """Validate token format and optionally length"""
        if not token:
            return False

        # Check for valid characters (URL-safe base64)
        if not re.match(r"^[A-Za-z0-9\-_]+$", token):
            return False

        # Check length if specified
        if expected_length and len(token) != expected_length:
            return False

        return True

    def hash_sensitive_data(self, data: str, salt: str = None) -> str:
        """Hash sensitive data with salt"""
        if salt is None:
            salt = secrets.token_hex(16)

        combined = f"{data}{salt}".encode()
        hashed = hashlib.sha256(combined).hexdigest()

        return f"{salt}${hashed}"

    def verify_hashed_data(self, data: str, hashed: str) -> bool:
        """Verify data against hash"""
        try:
            if "$" not in hashed:
                return False

            salt, expected_hash = hashed.split("$", 1)
            combined = f"{data}{salt}".encode()
            actual_hash = hashlib.sha256(combined).hexdigest()

            return secrets.compare_digest(expected_hash, actual_hash)
        except Exception:
            return False

    def log_security_event(
        self, event_type: str, details: dict[str, Any], severity: str = "INFO"
    ):
        """Log security events with structured data"""
        if severity == "WARNING":
            security_logger.warning(f"Security Event: {event_type} - {details}")
        elif severity == "ERROR":
            security_logger.error(f"Security Event: {event_type} - {details}")
        else:
            security_logger.info(f"Security Event: {event_type} - {details}")


# Global security validator instance
security_validator = SecurityValidator()

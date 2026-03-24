"""
Security utilities for input sanitization, validation, and XSS prevention
"""
import re
import html
import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
import bleach
from datetime import datetime, timedelta, timezone
import secrets

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security configuration constants"""

    # HTML sanitization settings
    ALLOWED_TAGS = ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li']
    ALLOWED_ATTRIBUTES: Dict[str, List[str]] = {}

    # Input length limits
    MAX_FORM_NAME_LENGTH = 100
    MAX_FORM_TITLE_LENGTH = 200
    MAX_FORM_DESCRIPTION_LENGTH = 1000
    MAX_FIELD_LABEL_LENGTH = 100
    MAX_FIELD_PLACEHOLDER_LENGTH = 200
    MAX_FIELD_DESCRIPTION_LENGTH = 500
    MAX_OPTIONS_COUNT = 50
    MAX_OPTION_LENGTH = 100
    MAX_FIELDS_COUNT = 50
    # Pattern validation
    SAFE_ID_PATTERN = r'^[a-zA-Z0-9_-]+$'
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    URL_PATTERN = r'^https?://[^\s/$.?#].[^\s]*$'
    # Rate limiting
    FORM_CREATION_RATE_LIMIT = 10  # forms per hour
    FORM_SUBMISSION_RATE_LIMIT = 100  # submissions per hour


class InputSanitizer:
    """Input sanitization and validation utilities"""
    @staticmethod
    def sanitize_html(text: str, allow_basic_formatting: bool = False) -> str:
        """
        Sanitize HTML content to prevent XSS attacks

        Args:
            text: Input text that may contain HTML
            allow_basic_formatting: Whether to allow basic formatting tags

        Returns:
            Sanitized text safe for display
        """
        if not text or not isinstance(text, str):
            return ""
        if allow_basic_formatting:
            # Allow basic formatting but strip dangerous elements
            return bleach.clean(
                text,
                tags=SecurityConfig.ALLOWED_TAGS,
                attributes=SecurityConfig.ALLOWED_ATTRIBUTES,
                strip=True
            )
        else:
            # Escape all HTML entities
            return html.escape(text, quote=True)
    
    @staticmethod
    def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize plain text input

        Args:
            text: Input text
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not text or not isinstance(text, str):
            return ""

        # Remove null bytes and control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

        # Strip whitespace
        text = text.strip()

        # Enforce length limit
        if max_length and len(text) > max_length:
            text = text[:max_length]

        return text

    @staticmethod
    def sanitize_field_id(field_id: str) -> str:
        """
        Sanitize field ID to prevent injection attacks

        Args:
            field_id: Field identifier

        Returns:
            Sanitized field ID

        Raises:
            ValueError: If field ID is invalid
        """
        if not field_id or not isinstance(field_id, str):
            raise ValueError("Field ID is required")
        # First check if it contains any dangerous patterns
        dangerous_patterns = [
            r'<[^>]*>',  # HTML tags
            r'javascript:',  # JavaScript URLs
            r'[;\'"<>{}()\s@]',  # Dangerous characters including spaces and @
            r'\\x[0-9a-fA-F]{2}',  # Hex encoded characters
            r'\.\.',  # Path traversal
            r'DROP\s+TABLE',  # SQL injection keywords
            r'SELECT\s+\*',
            r'INSERT\s+INTO',
            r'DELETE\s+FROM'
        ]
        original_field_id = field_id
        for pattern in dangerous_patterns:
            if re.search(pattern, field_id, re.IGNORECASE):
                raise ValueError("Field ID contains dangerous characters")

        # Remove any remaining dangerous characters
        field_id = re.sub(r'[^a-zA-Z0-9_-]', '', field_id)

        if not field_id:
            raise ValueError("Field ID contains no valid characters")

        if not re.match(SecurityConfig.SAFE_ID_PATTERN, field_id):
            raise ValueError("Field ID contains invalid characters")

        if len(field_id) > 50:
            raise ValueError("Field ID too long")

        # If the sanitized version is very different from original, reject it
        if len(field_id) < len(original_field_id) * 0.5:
            raise ValueError("Field ID contains too many invalid characters")

        return field_id

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address format

        Args:
            email: Email address to validate

        Returns:
            True if valid, False otherwise
        """
        if not email or not isinstance(email, str):
            return False

        if len(email) > 254:  # RFC 5321 limit
            return False

        return bool(re.match(SecurityConfig.EMAIL_PATTERN, email))

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate URL format and scheme

        Args:
            url: URL to validate

        Returns:
            True if valid, False otherwise
        """
        if not url or not isinstance(url, str):
            return False
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and parsed.netloc
        except Exception:
            return False
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        Generate a cryptographically secure random token

        Args:
            length: Token length in bytes

        Returns:
            URL-safe base64 encoded token
        """
        return secrets.token_urlsafe(length)


class FormSecurityValidator:
    """Form-specific security validation"""
    @staticmethod
    def validate_form_data(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize form creation data

        Args:
            form_data: Raw form data

        Returns:
            Sanitized form data

        Raises:
            ValueError: If validation fails
        """
        if not isinstance(form_data, dict):
            raise ValueError("Form data must be a dictionary")

        sanitized: Dict[str, Any] = {}

        # Validate form name
        name = form_data.get('name', '')
        if not name:
            raise ValueError("Form name is required")

        sanitized['name'] = InputSanitizer.sanitize_text(
            name, SecurityConfig.MAX_FORM_NAME_LENGTH
        )

        if not sanitized['name']:
            raise ValueError("Form name is invalid")

        # Validate settings
        settings = form_data.get('settings', {})
        if not isinstance(settings, dict):
            raise ValueError("Form settings must be a dictionary")

        sanitized['settings'] = FormSecurityValidator.validate_form_settings(settings)

        # Validate fields
        fields = form_data.get('fields', [])
        if not isinstance(fields, list):
            raise ValueError("Form fields must be a list")

        if len(fields) > SecurityConfig.MAX_FIELDS_COUNT:
            raise ValueError(f"Too many fields (max {SecurityConfig.MAX_FIELDS_COUNT})")

        sanitized['fields'] = [
            FormSecurityValidator.validate_form_field(field)
            for field in fields
        ]

        # Validate field IDs are unique
        field_ids = [field['id'] for field in sanitized['fields']]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("Field IDs must be unique")
        # Optional fields
        if 'wedding_id' in form_data:
            wedding_id = form_data['wedding_id']
            if wedding_id and not isinstance(wedding_id, str):
                raise ValueError("Wedding ID must be a string")
            sanitized['wedding_id'] = wedding_id
        if 'template_type' in form_data:
            template_type = form_data['template_type']
            if template_type and not isinstance(template_type, str):
                raise ValueError("Template type must be a string")
            sanitized['template_type'] = InputSanitizer.sanitize_text(template_type, 50)

        # Validate form_type polymorphic discriminator (P0-10)
        if 'form_type' in form_data:
            form_type = form_data['form_type']
            allowed_form_types = {
                'general', 'vendor_intake', 'rsvp_custom', 'wedding_feedback',
                'guest_feedback', 'vendor_questionnaire', 'contact_form',
                'survey', 'registration',
            }
            if form_type and isinstance(form_type, str) and form_type in allowed_form_types:
                sanitized['form_type'] = form_type
            elif form_type:
                raise ValueError(f"Invalid form type: {form_type}. Allowed: {', '.join(sorted(allowed_form_types))}")

        return sanitized

    @staticmethod
    def validate_form_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize form settings

        Args:
            settings: Raw settings data

        Returns:
            Sanitized settings data
        """
        sanitized: Dict[str, Any] = {}
        # Required fields
        title = settings.get('title', '')
        if not title:
            raise ValueError("Form title is required")

        sanitized['title'] = InputSanitizer.sanitize_html(
            title, allow_basic_formatting=False
        )[:SecurityConfig.MAX_FORM_TITLE_LENGTH]

        # Optional fields with sanitization
        if 'description' in settings:
            description = settings['description']
            if description:
                sanitized['description'] = InputSanitizer.sanitize_html(
                    description, allow_basic_formatting=True
                )[:SecurityConfig.MAX_FORM_DESCRIPTION_LENGTH]
        # Text fields
        text_fields = ['submit_button_text', 'success_message']
        for field in text_fields:
            if field in settings:
                value = settings[field]
                if value:
                    sanitized[field] = InputSanitizer.sanitize_text(value, 100)
        # URL validation
        if 'redirect_url' in settings:
            redirect_url = settings['redirect_url']
            if redirect_url:
                if not InputSanitizer.validate_url(redirect_url):
                    raise ValueError("Invalid redirect URL")
                sanitized['redirect_url'] = redirect_url

        # Boolean fields
        bool_fields = [
            'allow_multiple_submissions', 'collect_email',
            'is_public', 'requires_auth'
        ]
        for field in bool_fields:
            if field in settings:
                sanitized[field] = bool(settings[field])

        return sanitized

    @staticmethod
    def validate_form_field(field: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize form field data

        Args:
            field: Raw field data

        Returns:
            Sanitized field data
        """
        if not isinstance(field, dict):
            raise ValueError("Field must be a dictionary")

        sanitized: Dict[str, Any] = {}

        # Required fields
        field_id = field.get('id', '')
        if not field_id:
            raise ValueError("Field ID is required")

        sanitized['id'] = InputSanitizer.sanitize_field_id(field_id)

        label = field.get('label', '')
        if not label:
            raise ValueError("Field label is required")

        sanitized['label'] = InputSanitizer.sanitize_html(
            label, allow_basic_formatting=False
        )[:SecurityConfig.MAX_FIELD_LABEL_LENGTH]

        field_type = field.get('type', '')
        if not field_type:
            raise ValueError("Field type is required")

        # Validate field type against allowed types
        allowed_types = [
            'text', 'email', 'phone', 'number', 'date', 'textarea',
            'select', 'radio', 'checkbox', 'file_upload', 'rating', 'scale'
        ]
        if field_type not in allowed_types:
            raise ValueError(f"Invalid field type: {field_type}")

        sanitized['type'] = field_type

        # Optional fields
        if 'placeholder' in field:
            placeholder = field['placeholder']
            if placeholder:
                sanitized['placeholder'] = InputSanitizer.sanitize_text(
                    placeholder, SecurityConfig.MAX_FIELD_PLACEHOLDER_LENGTH
                )
        if 'description' in field:
            description = field['description']
            if description:
                sanitized['description'] = InputSanitizer.sanitize_html(
                    description, allow_basic_formatting=True
                )[:SecurityConfig.MAX_FIELD_DESCRIPTION_LENGTH]

        # Boolean and numeric fields
        sanitized['required'] = bool(field.get('required', False))
        sanitized['order'] = int(field.get('order', 0))

        # Options for select/radio/checkbox fields
        if 'options' in field:
            options = field['options']
            if isinstance(options, list):
                if len(options) > SecurityConfig.MAX_OPTIONS_COUNT:
                    raise ValueError(f"Too many options (max {SecurityConfig.MAX_OPTIONS_COUNT})")
                sanitized['options'] = [
                    InputSanitizer.sanitize_text(opt, SecurityConfig.MAX_OPTION_LENGTH)
                    for opt in options
                    if opt and isinstance(opt, str)
                ]

        return sanitized

    @staticmethod
    def validate_form_response(response_data: Dict[str, Any], form_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate and sanitize form response data

        Args:
            response_data: Raw response data
            form_fields: Form field definitions

        Returns:
            Sanitized response data
        """
        if not isinstance(response_data, dict):
            raise ValueError("Response data must be a dictionary")

        sanitized: Dict[str, Any] = {}
        field_map = {field['id']: field for field in form_fields}

        for field_id, value in response_data.items():
            if field_id not in field_map:
                continue  # Skip unknown fields

            field_def = field_map[field_id]
            field_type = field_def['type']

            # Sanitize based on field type
            try:
                if field_type in ['text', 'textarea']:
                    if isinstance(value, str):
                        max_length = 1000 if field_type == 'textarea' else 255
                        sanitized[field_id] = InputSanitizer.sanitize_text(value, max_length)

                elif field_type == 'email':
                    if isinstance(value, str) and InputSanitizer.validate_email(value):
                        sanitized[field_id] = value.lower().strip()

                elif field_type in ['number', 'rating', 'scale']:
                    if isinstance(value, (int, float)):
                        sanitized[field_id] = value
                    elif isinstance(value, str) and value.isdigit():
                        sanitized[field_id] = int(value)

                elif field_type in ['select', 'radio']:
                    if isinstance(value, str) and value in field_def.get('options', []):
                        sanitized[field_id] = InputSanitizer.sanitize_text(value, 100)

                elif field_type == 'checkbox':
                    if isinstance(value, list):
                        options = field_def.get('options', [])
                        sanitized[field_id] = [
                            InputSanitizer.sanitize_text(v, 100)
                            for v in value
                            if isinstance(v, str) and v in options
                        ]
                    elif isinstance(value, bool):
                        sanitized[field_id] = value
                elif field_type == 'date':
                    if isinstance(value, str):
                        # Basic date format validation
                        try:
                            datetime.fromisoformat(value.replace('Z', '+00:00'))
                            sanitized[field_id] = value
                        except ValueError:
                            pass  # Skip invalid dates

            except Exception as e:
                logger.warning(f"Error sanitizing field {field_id}: {str(e)}")
                continue  # Skip problematic fields

        return sanitized


class SecurityHeaders:
    """Security headers for form responses"""
    @staticmethod
    def get_form_security_headers() -> Dict[str, str]:
        """
        Get security headers for form responses
        Returns:
            Dictionary of security headers
        """
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        }


class RateLimitTracker:
    """Simple in-memory rate limiting tracker"""

    def __init__(self):
        self._requests = {}

    def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Check if request is within rate limit

        Args:
            key: Unique identifier (IP, user email, etc.)
            limit: Maximum requests allowed
            window_seconds: Time window in seconds
        Returns:
            True if within limit, False otherwise
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)
        # Clean old entries
        if key in self._requests:
            self._requests[key] = [
                timestamp for timestamp in self._requests[key]
                if timestamp > cutoff
            ]
        else:
            self._requests[key] = []

        # Check current count
        if len(self._requests[key]) >= limit:
            return False

        # Add current request
        self._requests[key].append(now)
        return True


# Global rate limiter instance
rate_limiter = RateLimitTracker()
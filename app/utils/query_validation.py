"""
Query Parameter Validation Utilities

Validates and sanitizes pagination, sorting, and filtering parameters
to prevent injection and ensure sensible bounds.
"""
from typing import Optional, List, Any
from fastapi import Query, HTTPException
import logging

logger = logging.getLogger(__name__)


def validated_page(page: int = Query(1, ge=1, le=10000, description="Page number")) -> int:
    """
    Validate page number for pagination.

    Args:
        page: Page number (default 1, min 1, max 10000)

    Returns:
        Validated page number
    """
    return page


def validated_limit(limit: int = Query(20, ge=1, le=100, description="Items per page")) -> int:
    """
    Validate limit/items per page parameter.

    Args:
        limit: Items per page (default 20, min 1, max 100)

    Returns:
        Validated limit
    """
    return limit


def validated_limit_extended(limit: int = Query(50, ge=1, le=200, description="Items per page")) -> int:
    """
    Validate limit for endpoints that need more items per page.

    Args:
        limit: Items per page (default 50, min 1, max 200)

    Returns:
        Validated limit
    """
    return limit


def validated_skip(skip: int = Query(0, ge=0, le=100000)) -> int:
    """
    Validate skip parameter for pagination.

    DEPRECATED: Use cursor-based pagination for new endpoints.
    See app.utils.cursor_pagination for CursorPage, cursor_paginate(),
    validated_cursor(), and validated_cursor_limit() implementations.

    Offset-based pagination (skip/limit) has O(n) performance at scale
    because MongoDB must scan and discard all skipped documents. Cursor-based
    pagination uses document position markers for O(1) performance.

    Args:
        skip: Number of items to skip (default 0, min 0, max 100000)

    Returns:
        Validated skip value
    """
    return skip


def validate_sort_field(
    sort: str,
    allowed_fields: Optional[List[str]] = None,
    default_field: str = "created_at"
) -> str:
    """
    Validate sort field against an allowlist to prevent MongoDB injection.

    Supports ascending (-) and descending order by prefixing with minus sign.

    Args:
        sort: Sort field name (may include leading - for desc order)
        allowed_fields: List of allowed field names. Defaults to common fields.
        default_field: Field to use if sort is invalid (default "created_at")

    Returns:
        Validated sort field, or default if invalid
    """
    default_allowed = [
        "created_at",
        "updated_at",
        "name",
        "email",
        "date",
        "timestamp",
        "status",
        "priority",
        "category",
        "title",
        "start_date",
        "end_date",
        "due_date",
        "_id"
    ]

    allowed = allowed_fields or default_allowed

    # Handle descending order (prefix with -)
    field_name = sort.lstrip("-")

    # Validate field is in allowlist
    if field_name not in allowed:
        logger.warning(f"Invalid sort field requested: {sort}. Using default: {default_field}")
        return default_field

    # Return original sort value (with - prefix if present)
    return sort


def validate_sort_direction(direction: str) -> int:
    """
    Validate and convert sort direction to MongoDB format.

    Args:
        direction: Sort direction ("asc" or "desc")

    Returns:
        MongoDB sort direction: 1 for ascending, -1 for descending
    """
    if direction.lower() in ["desc", "descending", "-1"]:
        return -1
    return 1  # Default to ascending


def validated_string_filter(
    value: Optional[str],
    max_length: int = 100,
    allow_regex: bool = False
) -> Optional[str]:
    """
    Validate and sanitize a string filter parameter.

    Args:
        value: String value to validate
        max_length: Maximum allowed string length
        allow_regex: Whether to allow regex patterns (not recommended for user input)

    Returns:
        Validated string or None if invalid
    """
    if value is None:
        return None

    if not isinstance(value, str):
        return None

    # Enforce max length
    if len(value) > max_length:
        logger.warning(f"Filter string exceeded max length {max_length}")
        return None

    # Strip whitespace
    value = value.strip()

    if not value:
        return None

    # Basic regex injection prevention - only allow alphanumeric, common punctuation
    if not allow_regex:
        # Remove dangerous regex special characters
        dangerous_chars = ['$', '{', '}', '|', '[', ']', '(', ')', '^', '\\']
        for char in dangerous_chars:
            if char in value:
                logger.warning(f"Dangerous character in filter: {char}")
                value = value.replace(char, '')

    return value


def validated_status_filter(
    status: Optional[str],
    allowed_statuses: List[str]
) -> Optional[str]:
    """
    Validate a status filter against an allowlist.

    Args:
        status: Status value to validate
        allowed_statuses: List of valid status values

    Returns:
        Validated status or None if invalid
    """
    if status is None:
        return None

    if status not in allowed_statuses:
        logger.warning(f"Invalid status filter: {status}. Allowed: {allowed_statuses}")
        return None

    return status


def validated_boolean_filter(value: Optional[bool]) -> Optional[bool]:
    """
    Validate a boolean filter parameter.

    Args:
        value: Boolean value

    Returns:
        Validated boolean or None
    """
    return value


def validated_date_string(date_str: Optional[str]) -> Optional[str]:
    """
    Validate ISO 8601 date string format.

    Args:
        date_str: ISO date string

    Returns:
        Validated date string or None if invalid
    """
    if date_str is None:
        return None

    if not isinstance(date_str, str):
        return None

    try:
        # Basic ISO 8601 format check
        from datetime import datetime
        # Try parsing as ISO format
        datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_str
    except (ValueError, TypeError):
        logger.warning(f"Invalid date format: {date_str}")
        return None


def calculate_pagination_params(
    page: int,
    limit: int
) -> tuple[int, int]:
    """
    Calculate skip and limit values for pagination.

    Args:
        page: Page number (1-indexed)
        limit: Items per page

    Returns:
        Tuple of (skip, limit)
    """
    skip = (page - 1) * limit
    return skip, limit


def validated_enum_filter(
    value: Optional[str],
    allowed_values: List[str]
) -> Optional[str]:
    """
    Validate an enum filter against allowed values.

    Args:
        value: Enum value to validate
        allowed_values: List of allowed values

    Returns:
        Validated value or None if not in allowed list
    """
    if value is None:
        return None

    if value not in allowed_values:
        logger.warning(f"Invalid enum value: {value}. Allowed: {allowed_values}")
        return None

    return value

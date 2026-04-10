"""
Standardized API Response Envelope

All API endpoints should use these helpers to ensure consistent response format.

Standard Response Format:
  Success: {success: true, data: {...}, message?: "...", meta?: {...}}
  Error: {success: false, message: "...", errors?: [...]}
  Paginated: {success: true, data: [...], meta: {total, page, per_page, ...}}
"""

from typing import Any, Dict, List

from fastapi.responses import JSONResponse


def success_response(
    data: Any = None, message: str = None, meta: Dict = None, status_code: int = 200
) -> JSONResponse:
    """
    Standard success response envelope.

    Args:
        data: The response data (can be object, list, or None)
        message: Optional success message
        meta: Optional metadata (pagination, totals, etc.)
        status_code: HTTP status code (default 200)

    Returns:
        JSONResponse with standardized envelope
    """
    body = {"success": True}
    if data is not None:
        body["data"] = data
    if message:
        body["message"] = message
    if meta:
        body["meta"] = meta
    return JSONResponse(status_code=status_code, content=body)


def error_response(
    message: str, errors: List[Dict] = None, status_code: int = 400
) -> JSONResponse:
    """
    Standard error response envelope.

    Args:
        message: Error message
        errors: Optional list of detailed errors [{field, message}, ...]
        status_code: HTTP status code (default 400)

    Returns:
        JSONResponse with standardized error envelope
    """
    body = {"success": False, "message": message}
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status_code, content=body)


def paginated_response(
    data: List, total: int, page: int = 1, per_page: int = 20, status_code: int = 200
) -> JSONResponse:
    """
    Standard paginated response.

    Args:
        data: List of items for this page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        per_page: Number of items per page
        status_code: HTTP status code

    Returns:
        JSONResponse with standardized paginated envelope
    """
    total_pages = (total + per_page - 1) // per_page
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "meta": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        },
    )


def dict_response(
    data: Dict = None, message: str = None, status_code: int = 200
) -> Dict:
    """
    Return a dictionary response (for compatibility with direct returns).
    Use this when you need to return a dict instead of JSONResponse.

    Args:
        data: Dictionary data to return
        message: Optional message
        status_code: Not used for dict returns (for API consistency)

    Returns:
        Dictionary with standardized envelope
    """
    body = {"success": True}
    if data is not None:
        body["data"] = data
    if message:
        body["message"] = message
    return body

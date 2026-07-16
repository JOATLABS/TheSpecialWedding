"""Customer-safe error envelopes for the storefront custom-domain API."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


STOREFRONT_DOMAIN_PATH_PREFIX = "/admin/storefront/custom-domain"
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
_SAFE_SUPPORT_ID = re.compile(r"^[A-Za-z0-9_-]{6,96}$")


def is_storefront_domain_path(path: str) -> bool:
    return path == STOREFRONT_DOMAIN_PATH_PREFIX or path.startswith(
        f"{STOREFRONT_DOMAIN_PATH_PREFIX}/"
    )


def _nonempty_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _safe_field_errors(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    sanitized: dict[str, str] = {}
    for raw_field, raw_message in value.items():
        field = _nonempty_string(raw_field)
        message = _nonempty_string(raw_message)
        if field and message and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", field):
            sanitized[field] = message[:300]
    return sanitized


def build_storefront_domain_error_payload(
    status_code: int,
    detail: Any,
    *,
    support_id: str | None = None,
    field_errors: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Normalize service/FastAPI failures without exposing raw provider payloads."""

    candidate = detail
    if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        candidate = detail["error"]
    if not isinstance(candidate, dict):
        candidate = {}

    code = _nonempty_string(candidate.get("code"))
    if not code or not _SAFE_CODE.fullmatch(code):
        code = "storefront_domain_request_failed"

    message = _nonempty_string(candidate.get("message"))
    if not message or message.lstrip().startswith(("{", "[")):
        message = "The custom-domain request could not be completed."

    customer_action = _nonempty_string(candidate.get("customer_action"))
    if not customer_action or customer_action.lstrip().startswith(("{", "[")):
        customer_action = "Check the domain details and try again. If this continues, contact support."

    candidate_support_id = _nonempty_string(candidate.get("support_id"))
    resolved_support_id = support_id or candidate_support_id
    if not resolved_support_id or not _SAFE_SUPPORT_ID.fullmatch(resolved_support_id):
        resolved_support_id = f"sfd_{uuid4().hex[:16]}"

    resolved_field_errors = _safe_field_errors(field_errors)
    if not resolved_field_errors:
        resolved_field_errors = _safe_field_errors(candidate.get("field_errors"))

    retryable_value = candidate.get("retryable")
    retryable = (
        retryable_value
        if isinstance(retryable_value, bool)
        else status_code in {408, 425, 429, 500, 502, 503, 504}
    )
    return {
        "error": {
            "code": code,
            "message": message[:500],
            "customer_action": customer_action[:700],
            "retryable": retryable,
            "support_id": resolved_support_id,
            "field_errors": resolved_field_errors,
        }
    }


def validation_field_errors(exc: RequestValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for item in exc.errors():
        location = item.get("loc")
        if not isinstance(location, (tuple, list)):
            continue
        field_parts = [
            str(part)
            for part in location
            if part not in {"body", "query", "path", "header"}
        ]
        field = ".".join(field_parts) or "request"
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", field):
            field = "request"
        message = _nonempty_string(item.get("msg")) or "Enter a valid value."
        errors.setdefault(field, message[:300])
    return errors


async def storefront_domain_http_exception_handler(
    request: Request, exc: HTTPException
):
    if not is_storefront_domain_path(request.url.path):
        return await http_exception_handler(request, exc)
    return JSONResponse(
        status_code=exc.status_code,
        content=build_storefront_domain_error_payload(exc.status_code, exc.detail),
        headers=exc.headers,
    )


async def storefront_domain_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=build_storefront_domain_error_payload(
            422,
            {
                "code": "invalid_request",
                "message": "Check the highlighted domain setup fields.",
                "customer_action": "Correct the listed fields and try again.",
                "retryable": False,
            },
            field_errors=validation_field_errors(exc),
        ),
    )

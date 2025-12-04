"""
Global error handler middleware for standardized error responses
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.exceptions import WeddingAppException
import logging
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle all exceptions and return standardized error responses
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except WeddingAppException as e:
            # Handle custom application exceptions
            return await self._handle_wedding_app_exception(request, e)
        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            return await self._handle_http_exception(request, e)
        except Exception as e:
            # Handle unexpected exceptions
            return await self._handle_unexpected_exception(request, e)

    async def _handle_wedding_app_exception(self, request: Request, exc: WeddingAppException) -> JSONResponse:
        """Handle custom WeddingApp exceptions"""

        # Log the error
        logger.error(f"WeddingApp Exception: {exc.error_code} - {exc.message}")

        error_response = {
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            }
        }

        # Add field information for validation errors
        if hasattr(exc, 'field') and exc.field:
            error_response["error"]["field"] = exc.field

        # Add retry_after for rate limit errors
        if hasattr(exc, 'retry_after'):
            error_response["error"]["retry_after"] = exc.retry_after

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )

    async def _handle_http_exception(self, request: Request, exc: HTTPException) -> JSONResponse:
        """Handle FastAPI HTTP exceptions"""

        # Map HTTP status codes to error codes
        status_to_code = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_SERVER_ERROR"
        }

        error_code = status_to_code.get(exc.status_code, "HTTP_ERROR")

        # Log the error
        logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")

        # Handle validation errors from Pydantic
        if exc.status_code == 422 and isinstance(exc.detail, list):
            errors = []
            for error in exc.detail:
                field = ".".join(str(loc) for loc in error.get("loc", []))
                errors.append({
                    "field": field,
                    "message": error.get("msg", "Validation error"),
                    "type": error.get("type", "value_error")
                })

            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Validation failed",
                        "timestamp": datetime.utcnow().isoformat(),
                        "path": str(request.url.path),
                        "details": errors
                    }
                }
            )

        error_response = {
            "error": {
                "code": error_code,
                "message": str(exc.detail) if exc.detail else "An error occurred",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            }
        }

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )

    async def _handle_unexpected_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions"""

        # Log the full exception with traceback
        logger.error(f"Unexpected exception: {str(exc)}")
        logger.error(traceback.format_exc())

        # Don't expose internal error details in production
        error_response = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            }
        }

        return JSONResponse(
            status_code=500,
            content=error_response
        )
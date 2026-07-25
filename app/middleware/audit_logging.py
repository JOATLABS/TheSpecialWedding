"""
Audit Logging Middleware for security and compliance
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.database import mongo
from app.core.settings import settings
from app.utils.auth_utils import verify_token

# Setup audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False


# ── Audit log batch buffer ─────────────────────────────────────────────
# Replaces per-request ``audit_logs.insert_one`` with an in-memory queue
# flushed every ``flush_interval_s`` seconds (or eagerly when the queue
# hits ``batch_size``).  This removes one Mongo round trip from every
# authenticated request while preserving durability via two layers:
#
#   1. The synchronous file appender (``_log_to_file``) still runs on
#      every request, so a hard crash never silently loses audit data —
#      the file is the recovery source of truth.
#   2. ``shutdown()`` is wired into the FastAPI lifespan so a graceful
#      stop drains the buffer before the database connection closes.
#
# If a flush fails three times in a row we drop the oldest 50% of the
# batch to prevent unbounded memory growth, surface an ``audit_logger``
# error, and continue.  The file appender still has the dropped entries
# for offline replay if needed.
class AuditLogBuffer:
    """Async in-memory buffer for batched audit-log writes."""

    def __init__(
        self,
        flush_interval_s: float = 1.0,
        batch_size: int = 100,
        max_buffer: int = 10000,
    ) -> None:
        self._queue: list[dict[str, Any]] = []
        self._collection: Any | None = None
        self._flush_task: asyncio.Task | None = None
        self._stopped = asyncio.Event()
        self._flush_interval_s = flush_interval_s
        self._batch_size = batch_size
        self._max_buffer = max_buffer
        self._consecutive_failures = 0
        self._dropped_total = 0
        self._batch_event = asyncio.Event()

    def append(self, entry: dict[str, Any]) -> None:
        """Append an audit entry. Sync, lock-free, safe to call from middleware.

        CPython list operations are GIL-protected, and the flush loop's
        snapshot-and-clear sequence runs without an intervening ``await``,
        so we can avoid an asyncio.Lock on the hot path.
        """
        if self._collection is None:
            # Buffer not started — happens during very early startup and
            # in unit tests.  The file appender still captures the entry,
            # so this is degraded-not-lost.
            return
        if len(self._queue) >= self._max_buffer:
            # Hard cap — drop oldest to make room.  Soft race here is
            # harmless (only affects warning frequency).
            try:
                self._queue.pop(0)
                self._dropped_total += 1
            except IndexError:
                pass
            if self._dropped_total % 100 == 1:
                audit_logger.warning(
                    f"Audit buffer at hard cap ({self._max_buffer}); "
                    f"dropped {self._dropped_total} entries total"
                )
        self._queue.append(entry)
        # Eager flush trigger when batch threshold is reached.  The loop
        # picks this up via wait_for(_batch_event) and flushes immediately
        # instead of waiting for the next interval tick.
        if len(self._queue) >= self._batch_size:
            self._batch_event.set()

    async def start(self, collection: Any) -> None:
        """Start the flush loop. Idempotent.

        Must be called *after* ``init_database()`` so ``mongo.db`` is
        available, and the collection passed in is alive.
        """
        if self._flush_task is not None and not self._flush_task.done():
            return
        self._collection = collection
        self._stopped.clear()
        self._batch_event.clear()
        self._flush_task = asyncio.create_task(self._flush_loop())
        audit_logger.info(
            f"Audit log buffer started "
            f"(interval={self._flush_interval_s}s, batch={self._batch_size}, "
            f"max={self._max_buffer})"
        )

    async def shutdown(self) -> None:
        """Stop the flush loop and drain remaining entries.

        Called from the FastAPI lifespan shutdown.  Idempotent — safe to
        call from both the post-yield block and the ``finally`` block.
        """
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = None
            self._collection = None
            return

        # Signal the loop to exit cleanly
        self._stopped.set()
        self._batch_event.set()
        try:
            await asyncio.wait_for(self._flush_task, timeout=5.0)
        except TimeoutError:
            # Loop didn't exit in time — cancel and move on
            self._flush_task.cancel()
            try:
                await self._flush_task
            except (asyncio.CancelledError, Exception):
                pass

        # Final drain of anything that arrived after the loop's last tick
        if self._queue and self._collection is not None:
            try:
                await self._flush_once(final=True)
            except Exception as e:
                audit_logger.error(
                    f"Final audit drain failed; "
                    f"{len(self._queue)} entries remain in memory only: {e}"
                )

        self._flush_task = None
        self._collection = None
        audit_logger.info("Audit log buffer shut down")

    async def _flush_loop(self) -> None:
        """Background loop: flush every ``flush_interval_s`` or on batch event."""
        try:
            while not self._stopped.is_set():
                # Wait for either the interval to elapse OR the batch
                # threshold to fire — whichever comes first.
                try:
                    await asyncio.wait_for(
                        self._batch_event.wait(),
                        timeout=self._flush_interval_s,
                    )
                except TimeoutError:
                    pass
                self._batch_event.clear()
                if self._stopped.is_set():
                    break
                if self._queue:
                    try:
                        await self._flush_once()
                    except Exception as e:
                        audit_logger.error(f"Audit flush iteration failed: {e}")
        except asyncio.CancelledError:
            audit_logger.info("Audit flush loop cancelled")
            raise
        except Exception as e:
            audit_logger.error(f"Audit flush loop crashed: {e}", exc_info=True)

    async def _flush_once(self, final: bool = False) -> None:
        """Drain the queue and ``insert_many`` to Mongo.

        Snapshot-and-clear is two bytecode ops with no intervening await,
        so it is atomic against ``append()`` in CPython.
        """
        if not self._queue or self._collection is None:
            return

        # Atomic snapshot in CPython (no await between these two lines)
        batch = self._queue
        self._queue = []

        try:
            # ordered=False so a single bad doc doesn't abort the batch
            await self._collection.insert_many(batch, ordered=False)
            self._consecutive_failures = 0
        except Exception as e:
            self._consecutive_failures += 1
            audit_logger.error(
                f"Audit batch flush failed "
                f"(attempt {self._consecutive_failures}, batch={len(batch)}): {e}"
            )
            if self._consecutive_failures >= 3:
                # Three strikes — drop the oldest half of the failed batch
                # to keep memory bounded.  File appender retains the
                # dropped entries for offline replay.
                drop_count = len(batch) // 2
                kept = batch[drop_count:]
                self._queue = kept + self._queue
                self._dropped_total += drop_count
                self._consecutive_failures = 0
                audit_logger.error(
                    f"Audit flush failed 3x consecutively; "
                    f"dropped {drop_count} oldest entries from batch "
                    f"({self._dropped_total} dropped total)"
                )
            else:
                # Retry on next tick: re-prepend the failed batch
                self._queue = batch + self._queue
            if final:
                # Surface the failure on shutdown so it isn't silent
                raise


# Module-level singleton.  Constructed at import time; ``start()`` is
# called from the FastAPI lifespan after ``init_database()``.
audit_buffer = AuditLogBuffer()

_OBJECT_ID_SEGMENT_RE = re.compile(r"/[a-f0-9]{24}(?=/|$)", re.IGNORECASE)
_UUID_SEGMENT_RE = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}(?=/|$)",
    re.IGNORECASE,
)
_NUMERIC_SEGMENT_RE = re.compile(r"/\d+(?=/|$)")
_PREFIXED_ID_SEGMENT_RE = re.compile(
    r"/(?:acct|camp|cs|cus|evt|link|pi|price|sess|sub|wedding)_[A-Za-z0-9][A-Za-z0-9_-]*(?=/|$)"
)


def _normalize_route_template(path: str) -> str:
    """Group high-cardinality REST paths into stable performance buckets."""
    normalized = _UUID_SEGMENT_RE.sub("/{id}", path)
    normalized = _OBJECT_ID_SEGMENT_RE.sub("/{id}", normalized)
    normalized = _PREFIXED_ID_SEGMENT_RE.sub("/{id}", normalized)
    normalized = _NUMERIC_SEGMENT_RE.sub("/{id}", normalized)
    return normalized


def _extract_route_template(request: Request) -> str | None:
    """Read the FastAPI route template after routing has matched the request."""
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if not isinstance(route_path, str) or not route_path:
        return None

    root_path = request.scope.get("root_path") or ""
    if root_path and not route_path.startswith(root_path):
        return f"{root_path}{route_path}"
    return route_path


def _ensure_audit_file_handler(log_file_path: str) -> None:
    """Attach a single configured file handler for structured audit log output."""
    normalized_path = os.path.abspath(log_file_path)

    for handler in audit_logger.handlers:
        if (
            isinstance(handler, logging.FileHandler)
            and getattr(handler, "baseFilename", None) == normalized_path
        ):
            return

    log_dir = os.path.dirname(normalized_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(normalized_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
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
        sensitive_paths: list[str] | None = None,
        excluded_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.log_to_db = log_to_db
        self.log_to_file = log_to_file
        self.sensitive_paths = sensitive_paths or [
            "/admin/",
            "/api/auth/",
            "/api/users/",
            "/api/subscription/",
        ]
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/static/",
            "/_next/",
            "/favicon",
            "/robots.txt",
            "/sitemap.xml",
        ]

        # Database writes flow through the module-level ``audit_buffer``
        # singleton (started/stopped in the FastAPI lifespan).  The
        # middleware no longer holds a direct collection handle.

        if self.log_to_file:
            _ensure_audit_file_handler(settings.audit_log_file)

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

    def _get_client_info(self, request: Request) -> dict[str, Any]:
        """Extract client information from request"""
        # Get IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        else:
            ip_address = request.headers.get("X-Real-IP") or (
                request.client.host if request.client else "unknown"
            )

        # Get user agent
        user_agent = request.headers.get("User-Agent", "Unknown")

        # Get authentication info
        auth_header = request.headers.get("Authorization", "")
        is_authenticated = bool(auth_header)
        user_email = None
        user_role = None
        if auth_header.startswith("Bearer "):
            try:
                payload = verify_token(auth_header.split(" ", 1)[1])
                user_email = payload.get("sub")
                user_role = payload.get("role")
            except Exception:
                # Invalid tokens should still be logged, just without decoded identity.
                pass

        return {
            "request_id": request.headers.get("X-Request-ID") or str(uuid4()),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "is_authenticated": is_authenticated,
            "user_email": user_email,
            "user_role": user_role,
            "method": request.method,
            "path": request.url.path,
            "host": request.headers.get("host"),
            "referer": request.headers.get("referer"),
            "origin": request.headers.get("origin"),
            "query_params": dict(request.query_params),
        }

    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize sensitive data before logging"""
        if isinstance(data, dict):
            sanitized = {}
            sensitive_keys = [
                "password",
                "token",
                "secret",
                "api_key",
                "credit_card",
                "ssn",
                "social_security",
                "bank_account",
                "private_key",
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
        request_info: dict[str, Any],
        response_status: int,
        response_time: float,
        user_id: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Create audit log entry"""
        return {
            "timestamp": datetime.now(UTC),
            "request_id": request_info["request_id"],
            "event_type": self._determine_event_type(
                request_info["method"], request_info["path"]
            ),
            "user_id": user_id or request_info.get("user_email"),
            "user_email": request_info.get("user_email"),
            "user_role": request_info.get("user_role"),
            "ip_address": request_info["ip_address"],
            "user_agent": request_info["user_agent"],
            "method": request_info["method"],
            "path": request_info["path"],
            "route_template": request_info.get("route_template")
            or _normalize_route_template(request_info["path"]),
            "host": request_info.get("host"),
            "referer": request_info.get("referer"),
            "origin": request_info.get("origin"),
            "query_params": self._sanitize_data(request_info["query_params"]),
            "response_status": response_status,
            "response_time_ms": round(response_time * 1000, 2),
            "success": 200 <= response_status < 400,
            "error_message": error_message,
            "session_hash": self._generate_session_hash(request_info),
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

    def _generate_session_hash(self, request_info: dict[str, Any]) -> str:
        """Generate a session hash for correlating requests"""
        session_data = f"{request_info['ip_address']}:{request_info['user_agent']}"
        return hashlib.sha256(session_data.encode()).hexdigest()[:16]

    def _schedule_database_log(self, audit_entry: dict[str, Any]) -> None:
        """Queue the audit entry for batched flush to Mongo.

        Replaces the previous ``asyncio.create_task(insert_one(...))`` per
        request.  The shared :data:`audit_buffer` flushes every 1 s or
        when 100 entries accumulate, removing one Mongo round trip from
        every authenticated request while preserving durability via the
        synchronous file appender (``_log_to_file``).
        """
        audit_buffer.append(audit_entry)

    def _log_to_file(self, audit_entry: dict[str, Any]):
        """Log audit entry to file"""
        # Convert datetime to string for JSON serialization
        audit_entry_copy = audit_entry.copy()
        audit_entry_copy["timestamp"] = audit_entry_copy["timestamp"].isoformat()

        log_message = json.dumps(audit_entry_copy)

        # Log based on event severity
        # 401 (Unauthorized), 402 (Payment Required), 403 (Forbidden) are not errors -
        # they're normal auth/authz rejections that don't need to be logged as warnings
        status = audit_entry.get("response_status", 0)
        if audit_entry["success"] or status in (401, 402, 403):
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
            route_template = _extract_route_template(request)
            if route_template:
                request_info["route_template"] = route_template
            # Create audit entry
            audit_entry = self._create_audit_entry(
                request_info, response.status_code, response_time
            )

            # Log to database (async)
            if self.log_to_db:
                self._schedule_database_log(audit_entry)

            # Log to file
            if self.log_to_file:
                self._log_to_file(audit_entry)

            response.headers.setdefault("X-Request-ID", request_info["request_id"])
            return response

        except Exception as e:
            response_time = time.time() - start_time
            route_template = _extract_route_template(request)
            if route_template:
                request_info["route_template"] = route_template

            # Create error audit entry
            audit_entry = self._create_audit_entry(
                request_info, 500, response_time, error_message=str(e)
            )

            # Log error
            if self.log_to_db:
                self._schedule_database_log(audit_entry)

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
        error_message: str | None = None,
    ):
        """Log login attempt"""
        await self.audit_collection.insert_one(
            {
                "timestamp": datetime.now(UTC),
                "event_type": "login_attempt",
                "email": email,
                "success": success,
                "ip_address": ip_address,
                "error_message": error_message,
            }
        )

    async def log_data_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: str,
    ):
        """Log data access event"""
        await self.audit_collection.insert_one(
            {
                "timestamp": datetime.now(UTC),
                "event_type": "data_access",
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "ip_address": ip_address,
            }
        )

    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        user_id: str | None = None,
        ip_address: str | None = None,
        additional_data: dict[str, Any] | None = None,
    ):
        """Log security event"""
        await self.audit_collection.insert_one(
            {
                "timestamp": datetime.now(UTC),
                "event_type": "security_event",
                "security_event_type": event_type,
                "severity": severity,
                "description": description,
                "user_id": user_id,
                "ip_address": ip_address,
                "additional_data": additional_data,
            }
        )

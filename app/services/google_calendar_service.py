"""Google Calendar OAuth, connection management, and event projection service."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

import httpx
import jwt
from bson import ObjectId
from cryptography.fernet import Fernet
from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from app.core.cache import cache
from app.core.config import settings
from app.core.database import mongo
from app.models.calendar import ScheduleItemType, VisibilityMode
from app.models.calendar_connection import (
    CalendarSchedulerAccessMode,
    CalendarSyncTargetingMode,
    CalendarConnectionStatus,
    CalendarSchedulerRole,
)
from app.models.calendar_sync import CalendarSyncStatusValue
from app.services.calendar_audit_service import calendar_audit_service

logger = logging.getLogger(__name__)


# Hard cap on calendarList pagination to prevent unbounded loops on Google
# accounts with thousands of subscribed calendars. 250 items per page * 20
# pages = 5,000 calendars before we stop and log a warning.
_CALENDAR_LIST_PAGE_SIZE = 250
_CALENDAR_LIST_MAX_PAGES = 20


# Mapping from event hex color to Google Calendar's numeric colorId. Hoisted
# to module scope so it is not rebuilt on every event sync.
_GOOGLE_EVENT_COLOR_MAP: Dict[str, str] = {
    "#a4bdfc": "1",
    "#7ae7bf": "2",
    "#dbadff": "3",
    "#ff887c": "4",
    "#fbd75b": "5",
    "#ffb878": "6",
    "#46d6db": "7",
    "#e1e1e1": "8",
    "#5484ed": "9",
    "#51b749": "10",
    "#dc2127": "11",
}


# Environment values that disable production security checks. Anything not in
# this set (including misconfigurations and unknown values) is treated as
# production so security-critical env vars are required (fail-closed).
_NON_PRODUCTION_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "ci"})


# Regex used to scrub OAuth-bearing substrings from log/DB error strings. We
# strip anything that looks like a Google OAuth code/token query parameter,
# JSON field, or the literal token bodies that occasionally appear in error
# payloads. Conservative on purpose — false positives are fine, leaks are not.
_REDACT_NAMED_PATTERNS = [
    re.compile(r"(?i)(refresh_token['\"\s:=]+)[A-Za-z0-9._\-/+]+"),
    re.compile(r"(?i)(access_token['\"\s:=]+)[A-Za-z0-9._\-/+]+"),
    re.compile(r"(?i)(\bcode['\"\s:=]+)[A-Za-z0-9._\-/+]+"),
    re.compile(r"(?i)(authorization['\"\s:=]+)Bearer\s+[A-Za-z0-9._\-/+]+"),
]
_REDACT_TOKEN_SHAPES = [
    re.compile(r"\b1//[A-Za-z0-9_\-]+\b"),  # Google refresh-token shape
    re.compile(r"\bya29\.[A-Za-z0-9_\-]+\b"),  # Google access-token shape
]


def _redact_sensitive(text: Any) -> str:
    """Strip OAuth tokens / codes / bearer values from a log or error string."""
    if text is None:
        return ""
    out = str(text)
    for pattern in _REDACT_NAMED_PATTERNS:
        out = pattern.sub(r"\1[REDACTED]", out)
    for pattern in _REDACT_TOKEN_SHAPES:
        out = pattern.sub("[REDACTED]", out)
    return out


@asynccontextmanager
async def _account_token_lock(
    *, user_id: str, provider_account_email: str
) -> AsyncIterator[None]:
    """Per-Google-account lock so concurrent token refreshes don't race.

    Guards `get_credentials_for_connection` against the rotating-refresh-token
    invalidation case where two parallel requests both refresh and the second
    refresh invalidates the first one's stored tokens. Fails open if Redis is
    unavailable (acquire returns None) — same fail-open posture as
    `_meeting_mutation_lock` in `app/api/planner_calendar.py`.
    """
    lock_key = f"calendar_account_token_lock:{user_id}:{provider_account_email}"
    lock_value = uuid4().hex
    acquired = await cache.acquire_lock(lock_key, lock_value, expire=30)
    if acquired is False:
        # Another request is currently refreshing tokens for this account.
        # Raise 409 so the client can retry rather than racing.
        raise HTTPException(
            status_code=409,
            detail="Calendar credentials are being refreshed by another request. Try again.",
        )
    try:
        yield
    finally:
        if acquired:
            await cache.release_lock(lock_key, lock_value)


class GoogleCalendarService:
    """Handles Google Calendar OAuth, connection lifecycle, and event projection."""

    def __init__(self):
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_calendar_event_syncs_collection()
        self.tasks_collection = mongo.get_planner_tasks_collection()
        self._validate_security_configuration()

    def _google_integration_configured(self) -> bool:
        return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)

    def _is_production_environment(self) -> bool:
        """Fail-closed environment check.

        Returns False only for known dev/test/CI values. Anything unknown
        (typos, misconfiguration, future env names) is treated as production
        so security-critical env vars are required.
        """
        env = (settings.ENVIRONMENT or "").lower().strip()
        return env not in _NON_PRODUCTION_ENVIRONMENTS

    def _validate_security_configuration(self) -> None:
        if not (
            self._google_integration_configured() and self._is_production_environment()
        ):
            return

        missing_keys: list[str] = []
        if not settings.GOOGLE_OAUTH_STATE_SIGNING_KEY:
            missing_keys.append("GOOGLE_OAUTH_STATE_SIGNING_KEY")
        if not settings.TOKEN_ENCRYPTION_KEY:
            missing_keys.append("TOKEN_ENCRYPTION_KEY")
        if missing_keys:
            raise RuntimeError(
                "Google Calendar integration requires explicit security keys in production: "
                + ", ".join(missing_keys)
            )

    def _normalize_string_list(self, values: list[Any] | None) -> list[str]:
        if not values:
            return []
        return list(dict.fromkeys(str(value) for value in values if value))

    def _normalize_scheduler_user_grants(self, values: list[Any] | None) -> list[str]:
        return self._normalize_string_list(values)

    def _serialized_scheduler_user_grants(
        self, connection_doc: dict[str, Any]
    ) -> list[str]:
        grants = self._normalize_scheduler_user_grants(
            connection_doc.get("allowed_scheduler_user_ids", [])
        )
        access_mode = self._normalize_scheduler_access_mode(
            connection_doc.get("scheduler_access_mode")
        )
        owner_id = str(connection_doc.get("owner_planner_id") or "")
        user_id = str(connection_doc.get("user_id") or "")
        if (
            access_mode == CalendarSchedulerAccessMode.WORKSPACE_DEFAULT.value
            and owner_id
            and user_id
            and owner_id != user_id
        ):
            return [value for value in grants if value != user_id]
        return grants

    def _normalize_scheduler_access_mode(self, value: Any) -> str:
        normalized = str(value or CalendarSchedulerAccessMode.WORKSPACE_DEFAULT.value)
        valid_values = {mode.value for mode in CalendarSchedulerAccessMode}
        if normalized not in valid_values:
            raise HTTPException(
                status_code=400,
                detail="Invalid scheduler access mode supplied for this calendar connection",
            )
        return normalized

    def _normalize_sync_targeting_mode(self, value: Any) -> str:
        normalized = str(value or CalendarSyncTargetingMode.AUTOMATIC_AND_MANUAL.value)
        valid_values = {mode.value for mode in CalendarSyncTargetingMode}
        if normalized not in valid_values:
            raise HTTPException(
                status_code=400,
                detail="Invalid sync targeting mode supplied for this calendar connection",
            )
        return normalized

    def _normalize_scheduler_roles(self, values: list[Any] | None) -> list[str]:
        normalized = self._normalize_string_list(values)
        valid_values = {role.value for role in CalendarSchedulerRole}
        invalid = [value for value in normalized if value not in valid_values]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail="Invalid scheduler roles supplied for this calendar connection",
            )
        return normalized

    def _normalize_schedule_item_types(self, values: list[Any] | None) -> list[str]:
        normalized = self._normalize_string_list(values)
        valid_values = {item.value for item in ScheduleItemType}
        invalid = [value for value in normalized if value not in valid_values]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail="Invalid schedule item types supplied for this calendar connection",
            )
        return normalized

    def _external_events_cache_key(
        self,
        *,
        connection_id: str,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> str:
        return (
            "calendar_external_events:"
            f"{connection_id}:"
            f"{time_min.isoformat()}:"
            f"{time_max.isoformat()}:"
            f"{max_results}"
        )

    async def invalidate_connection_events_cache(self, connection_id: str) -> None:
        await cache.clear_pattern(f"calendar_external_events:{connection_id}:*")

    def _classify_google_exception(self, exc: Exception) -> dict[str, Any]:
        status_code: Optional[int] = None
        error_reason: Optional[str] = None
        # Redact at the source — `message` flows into `last_error` in the DB
        # via `_apply_provider_error_to_connection`.
        message = _redact_sensitive(exc)

        if isinstance(exc, HttpError):
            status_code = int(getattr(exc.resp, "status", 0) or 0)
            try:
                payload = json.loads(exc.content.decode("utf-8"))
            except Exception:
                payload = {}
            error_block = payload.get("error", {}) if isinstance(payload, dict) else {}
            error_rows = error_block.get("errors", [])
            if isinstance(error_rows, list) and error_rows:
                first_error = error_rows[0] or {}
                error_reason = first_error.get("reason")
                message = (
                    first_error.get("message") or error_block.get("message") or message
                )
            else:
                error_reason = error_block.get("status")
                message = error_block.get("message") or message
        elif isinstance(exc, (TimeoutError, ConnectionError, OSError)):
            return {
                "retryable": True,
                "error_category": "temporary",
                "status_code": None,
                "error_reason": "transport_error",
                "error_message": message,
            }

        if status_code == 429 or error_reason in {
            "rateLimitExceeded",
            "userRateLimitExceeded",
        }:
            return {
                "retryable": True,
                "error_category": "rate_limited",
                "status_code": status_code,
                "error_reason": error_reason,
                "error_message": message,
            }

        if status_code == 403 and error_reason in {
            "quotaExceeded",
            "dailyLimitExceeded",
            "calendarUsageLimitsExceeded",
        }:
            return {
                "retryable": False,
                "error_category": "quota_exceeded",
                "status_code": status_code,
                "error_reason": error_reason,
                "error_message": message,
            }

        if status_code == 401:
            return {
                "retryable": False,
                "error_category": "auth_revoked",
                "status_code": status_code,
                "error_reason": error_reason,
                "error_message": message,
            }

        if status_code == 403:
            return {
                "retryable": False,
                "error_category": "permission_denied",
                "status_code": status_code,
                "error_reason": error_reason,
                "error_message": message,
            }

        if status_code == 404:
            return {
                "retryable": False,
                "error_category": "not_found",
                "status_code": status_code,
                "error_reason": error_reason,
                "error_message": message,
            }

        if status_code is not None and status_code >= 500:
            return {
                "retryable": True,
                "error_category": "temporary",
                "status_code": status_code,
                "error_reason": error_reason,
                "error_message": message,
            }

        return {
            "retryable": False,
            "error_category": "unknown",
            "status_code": status_code,
            "error_reason": error_reason,
            "error_message": message,
        }

    async def _apply_provider_error_to_connection(
        self,
        connection_doc: dict[str, Any],
        classification: dict[str, Any],
    ) -> None:
        error_category = classification.get("error_category")
        status = connection_doc.get(
            "connection_status", CalendarConnectionStatus.ERROR.value
        )
        if error_category == "auth_revoked":
            status = CalendarConnectionStatus.REVOKED.value
        elif error_category in {"rate_limited", "quota_exceeded", "not_found"}:
            status = CalendarConnectionStatus.ACTIVE.value
        else:
            status = CalendarConnectionStatus.ERROR.value

        await self.connections_collection.update_one(
            {"_id": connection_doc["_id"]},
            {
                "$set": {
                    "connection_status": status,
                    "last_error": classification.get("error_message"),
                    "updated_at": datetime.now(UTC),
                }
            },
        )

    def _build_provider_result(
        self,
        *,
        success: bool,
        connection_doc: dict[str, Any],
        external_event_id: Optional[str] = None,
        etag: Optional[str] = None,
        classification: Optional[dict[str, Any]] = None,
        event: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        classification = classification or {}
        return {
            "success": success,
            "calendar_id": connection_doc.get("calendar_id"),
            "external_event_id": external_event_id,
            "etag": etag,
            "retryable": bool(classification.get("retryable", False)),
            "error_category": classification.get("error_category"),
            "error_message": classification.get("error_message"),
            "status_code": classification.get("status_code"),
            "event": event,
        }

    def _get_client_config(self) -> Dict[str, Any]:
        """Build OAuth client configuration from settings."""
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=503,
                detail="Google Calendar integration not configured. Missing client credentials.",
            )

        return {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        }

    def _get_state_signing_key(self) -> str:
        if (
            self._is_production_environment()
            and not settings.GOOGLE_OAUTH_STATE_SIGNING_KEY
        ):
            raise RuntimeError(
                "GOOGLE_OAUTH_STATE_SIGNING_KEY must be configured in production"
            )
        return (
            settings.GOOGLE_OAUTH_STATE_SIGNING_KEY
            or settings.SECRET_KEY
            or "dev-google-oauth-state-key"
        )

    def _get_fernet(self) -> Fernet:
        if self._is_production_environment() and not settings.TOKEN_ENCRYPTION_KEY:
            raise RuntimeError("TOKEN_ENCRYPTION_KEY must be configured in production")
        raw_key = (
            settings.TOKEN_ENCRYPTION_KEY or settings.SECRET_KEY or "dev-token-key"
        )
        derived_key = base64.urlsafe_b64encode(
            hashlib.sha256(raw_key.encode()).digest()
        )
        return Fernet(derived_key)

    def _encrypt_token(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        return self._get_fernet().encrypt(token.encode()).decode()

    def _decrypt_token(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        return self._get_fernet().decrypt(token.encode()).decode()

    def _build_state(
        self,
        user_id: str,
        user_email: str,
        owner_id: str,
        owner_email: str,
        redirect_to: Optional[str] = None,
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "user_email": user_email,
            "owner_id": owner_id,
            "owner_email": owner_email,
            "redirect_to": redirect_to or "/admin/planner/calendar",
            "nonce": secrets.token_urlsafe(16),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        }
        return jwt.encode(
            payload,
            self._get_state_signing_key(),
            algorithm="HS256",
        )

    def _decode_state(self, state: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(
                state,
                self._get_state_signing_key(),
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=400, detail="OAuth state has expired"
            ) from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status_code=400, detail="Invalid OAuth state") from exc

        # Validate required structural fields so downstream code can safely
        # use .get(). Missing fields = malformed state = treat as invalid.
        required_fields = ("sub", "user_email", "owner_id", "owner_email")
        if not all(payload.get(field) for field in required_fields):
            raise HTTPException(
                status_code=400, detail="OAuth state is missing required fields"
            )
        return payload

    async def get_authorization_url(
        self,
        *,
        user_id: str,
        user_email: str,
        owner_id: str,
        owner_email: str,
        redirect_to: Optional[str] = None,
    ) -> str:
        """Generate an OAuth authorization URL for a planner/team member."""
        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

        # Note: `prompt="consent"` is deliberate — Google only returns a
        # refresh_token on the response when the user re-consents. Removing it
        # would silently break offline access for re-connects.
        # `include_granted_scopes` is intentionally NOT passed; it is for
        # incremental authorization, which we do not use (our scope set is
        # fixed at request time).
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            state=self._build_state(
                user_id=user_id,
                user_email=user_email,
                owner_id=owner_id,
                owner_email=owner_email,
                redirect_to=redirect_to,
            ),
        )
        return auth_url

    async def handle_oauth_callback(
        self,
        *,
        code: str,
        state: str,
        current_user_context: Optional[dict[str, Optional[str]]] = None,
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens and persist connection rows."""
        state_payload = self._decode_state(state)

        if current_user_context:
            expected_user_id = current_user_context.get("user_id")
            expected_user_email = current_user_context.get("user_email")
            if expected_user_id and expected_user_id != state_payload.get("sub"):
                raise HTTPException(
                    status_code=403, detail="OAuth callback user mismatch"
                )
            if expected_user_email and expected_user_email != state_payload.get(
                "user_email"
            ):
                raise HTTPException(
                    status_code=403, detail="OAuth callback email mismatch"
                )

        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

        try:
            # Blocking HTTP call — run off the event loop.
            await asyncio.to_thread(flow.fetch_token, code=code)
        except Exception as exc:
            logger.error(
                "Failed to fetch Google OAuth token: %s",
                _redact_sensitive(exc),
            )
            raise HTTPException(
                status_code=400, detail="Failed to complete Google authorization"
            ) from exc

        credentials = flow.credentials
        calendar_service = build("calendar", "v3", credentials=credentials)
        oauth_service = build("oauth2", "v2", credentials=credentials)

        # H-5: userinfo.email is in our scope set, so this MUST succeed. If it
        # fails we cannot reliably bind tokens to a Google account; fall-back
        # to the planner's app email could mis-bind an entirely different
        # Google identity. Hard-fail instead.
        try:
            account_info = await asyncio.to_thread(
                lambda: oauth_service.userinfo().get().execute()
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch Google userinfo during OAuth callback: %s",
                _redact_sensitive(exc),
            )
            raise HTTPException(
                status_code=502,
                detail="Could not verify Google account identity. Please try again.",
            ) from exc

        provider_account_email = account_info.get("email")
        if not provider_account_email:
            raise HTTPException(
                status_code=502,
                detail="Google did not return an account email. Please try again.",
            )
        provider_account_name = (
            account_info.get("name")
            or account_info.get("given_name")
            or provider_account_email
        )

        # C-5: capped calendarList pagination so a corporate account with
        # thousands of subscribed calendars cannot run away with a worker.
        calendars: list[dict[str, Any]] = []
        page_token: Optional[str] = None
        for _page_index in range(_CALENDAR_LIST_MAX_PAGES):
            response = await asyncio.to_thread(
                lambda token=page_token: (
                    calendar_service.calendarList()
                    .list(pageToken=token, maxResults=_CALENDAR_LIST_PAGE_SIZE)
                    .execute()
                )
            )
            calendars.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        else:
            logger.warning(
                "calendarList pagination hit %d-page cap for account %s "
                "(returning first %d calendars)",
                _CALENDAR_LIST_MAX_PAGES,
                provider_account_email,
                len(calendars),
            )

        if not calendars:
            raise HTTPException(
                status_code=400,
                detail="Google account did not return any calendars to connect",
            )

        encrypted_access = self._encrypt_token(credentials.token)
        encrypted_refresh = self._encrypt_token(credentials.refresh_token)
        now = datetime.now(UTC)
        owner_id = str(state_payload.get("owner_id") or "")
        owner_email = str(state_payload.get("owner_email") or "")
        user_id = str(state_payload.get("sub") or "")
        user_email = str(state_payload.get("user_email") or "")

        writable_calendar_ids = [
            entry["id"]
            for entry in calendars
            if entry.get("accessRole") in {"owner", "writer"}
        ]
        primary_writable_id = next(
            (
                entry["id"]
                for entry in calendars
                if entry.get("primary")
                and entry.get("accessRole") in {"owner", "writer"}
            ),
            None,
        )
        default_write_id = primary_writable_id or (
            writable_calendar_ids[0] if writable_calendar_ids else None
        )
        seen_calendar_ids: list[str] = []

        for entry in calendars:
            calendar_id = entry["id"]
            seen_calendar_ids.append(calendar_id)
            is_writable = entry.get("accessRole") in {"owner", "writer"}
            connection_query = {
                "user_id": user_id,
                "provider_account_email": provider_account_email,
                "calendar_id": calendar_id,
            }
            existing_doc = await self.connections_collection.find_one(connection_query)
            connection_doc = {
                "owner_planner_id": owner_id,
                "owner_planner_email": owner_email,
                "user_id": user_id,
                "user_email": user_email,
                "provider": "google",
                "provider_account_email": provider_account_email,
                "provider_account_name": provider_account_name,
                "calendar_id": calendar_id,
                "calendar_name": entry.get("summaryOverride")
                or entry.get("summary")
                or calendar_id,
                "access_role": entry.get("accessRole"),
                "is_writable": is_writable,
                "is_primary": bool(entry.get("primary")),
                "is_default_write_target": bool(
                    is_writable
                    and (
                        existing_doc.get("is_default_write_target")
                        if existing_doc is not None
                        else calendar_id == default_write_id
                    )
                ),
                "scheduler_access_mode": self._normalize_scheduler_access_mode(
                    existing_doc.get("scheduler_access_mode")
                    if existing_doc is not None
                    else CalendarSchedulerAccessMode.WORKSPACE_DEFAULT.value
                ),
                "sync_targeting_mode": self._normalize_sync_targeting_mode(
                    existing_doc.get("sync_targeting_mode")
                    if existing_doc is not None
                    else CalendarSyncTargetingMode.AUTOMATIC_AND_MANUAL.value
                ),
                "allowed_scheduler_user_ids": self._normalize_scheduler_user_grants(
                    existing_doc.get("allowed_scheduler_user_ids", [])
                    if existing_doc is not None
                    else []
                ),
                "is_shared_in_team_view": (
                    existing_doc.get("is_shared_in_team_view", False)
                    if existing_doc is not None
                    else False
                ),
                "details_visibility": (
                    existing_doc.get(
                        "details_visibility",
                        VisibilityMode.BUSY_ONLY.value,
                    )
                    if existing_doc is not None
                    else VisibilityMode.BUSY_ONLY.value
                ),
                "sync_enabled": (
                    existing_doc.get("sync_enabled", is_writable)
                    if existing_doc is not None and is_writable
                    else is_writable
                ),
                "connection_status": CalendarConnectionStatus.ACTIVE.value,
                "access_token_encrypted": encrypted_access,
                "refresh_token_encrypted": encrypted_refresh,
                "token_expiry": credentials.expiry,
                "scope_version": ",".join(settings.GOOGLE_CALENDAR_SCOPES),
                "last_error": None,
                "updated_at": now,
            }
            await self.connections_collection.update_one(
                connection_query,
                {"$set": connection_doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )

        await self.connections_collection.delete_many(
            {
                "user_id": user_id,
                "provider_account_email": provider_account_email,
                "calendar_id": {"$nin": seen_calendar_ids},
            }
        )

        existing_default = await self.connections_collection.find_one(
            {
                "user_id": user_id,
                "provider_account_email": provider_account_email,
                "is_writable": True,
                "is_default_write_target": True,
            }
        )
        if not existing_default and default_write_id:
            await self.connections_collection.update_one(
                {
                    "user_id": user_id,
                    "provider_account_email": provider_account_email,
                    "calendar_id": default_write_id,
                    "is_writable": True,
                },
                {
                    "$set": {
                        "is_default_write_target": True,
                        "updated_at": now,
                    }
                },
            )

        await calendar_audit_service.log(
            action="calendar_connection_connected",
            message=f"Connected Google Calendar account {provider_account_email}",
            owner_planner_email=owner_email,
            actor_email=user_email,
            actor_role="planner" if owner_id == user_id else "team_member",
            metadata={
                "provider": "google",
                "provider_account_email": provider_account_email,
                "connections_created": len(calendars),
                "default_write_calendar_id": default_write_id,
            },
        )

        return {
            "connected": True,
            "calendar_id": default_write_id,
            "connections_created": len(calendars),
            "redirect_to": state_payload.get("redirect_to"),
            "message": "Successfully connected Google Calendar",
        }

    def _serialize_connection(self, doc: dict) -> dict:
        """Return a safe API representation for a calendar connection."""
        return {
            "id": str(doc["_id"]),
            "owner_planner_id": doc.get("owner_planner_id"),
            "owner_planner_email": doc.get("owner_planner_email"),
            "user_id": doc.get("user_id"),
            "user_email": doc.get("user_email"),
            "provider": doc.get("provider", "google"),
            "provider_account_email": doc.get("provider_account_email"),
            "provider_account_name": doc.get("provider_account_name"),
            "calendar_id": doc.get("calendar_id"),
            "calendar_name": doc.get("calendar_name"),
            "access_role": doc.get("access_role"),
            "is_writable": doc.get("is_writable", False),
            "is_primary": doc.get("is_primary", False),
            "is_default_write_target": doc.get("is_default_write_target", False),
            "scheduler_access_mode": self._normalize_scheduler_access_mode(
                doc.get("scheduler_access_mode")
            ),
            "sync_targeting_mode": self._normalize_sync_targeting_mode(
                doc.get("sync_targeting_mode")
            ),
            "allowed_scheduler_user_ids": self._serialized_scheduler_user_grants(doc),
            "allowed_scheduler_roles": self._normalize_scheduler_roles(
                doc.get("allowed_scheduler_roles", [])
            ),
            "allowed_schedule_item_types": self._normalize_schedule_item_types(
                doc.get("allowed_schedule_item_types", [])
            ),
            "allowed_wedding_ids": self._normalize_string_list(
                doc.get("allowed_wedding_ids", [])
            ),
            "is_shared_in_team_view": doc.get("is_shared_in_team_view", False),
            "details_visibility": doc.get(
                "details_visibility", VisibilityMode.BUSY_ONLY.value
            ),
            "sync_enabled": doc.get("sync_enabled", False),
            "task_sync_enabled": doc.get("task_sync_enabled", False),
            "task_sync_tasklist_id": doc.get("task_sync_tasklist_id"),
            "task_sync_tasklist_name": doc.get("task_sync_tasklist_name"),
            "task_sync_subscription_id": doc.get("task_sync_subscription_id"),
            "contact_sync_enabled": doc.get("contact_sync_enabled", False),
            "contact_sync_book_id": doc.get("contact_sync_book_id"),
            "contact_sync_book_name": doc.get("contact_sync_book_name"),
            "contact_sync_group_id": doc.get("contact_sync_group_id"),
            "contact_sync_group_name": doc.get("contact_sync_group_name"),
            "contact_sync_subscription_id": doc.get("contact_sync_subscription_id"),
            "connection_scopes": self._normalize_string_list(
                doc.get("connection_scopes", [])
            ),
            "connection_status": doc.get(
                "connection_status", CalendarConnectionStatus.ERROR.value
            ),
            "token_expiry": doc.get("token_expiry"),
            "last_sync_at": doc.get("last_sync_at"),
            "last_healthcheck_at": doc.get("last_healthcheck_at"),
            "last_error": doc.get("last_error"),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
        }

    async def list_connections(
        self,
        *,
        owner_id: str,
        current_user_id: Optional[str],
        include_all_owner_connections: bool,
    ) -> List[dict]:
        """List visible calendar connections within an owner scope."""
        query: dict[str, Any] = {"owner_planner_id": owner_id}
        if not include_all_owner_connections and current_user_id:
            query["$or"] = [
                {"user_id": current_user_id},
                {"is_shared_in_team_view": True},
            ]

        docs = (
            await self.connections_collection.find(query)
            .sort([("user_email", 1), ("calendar_name", 1)])
            .to_list(length=500)
        )
        return [self._serialize_connection(doc) for doc in docs]

    async def _get_connection_doc(self, connection_id: str) -> dict:
        try:
            oid = ObjectId(connection_id)
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail="Invalid connection ID"
            ) from exc

        doc = await self.connections_collection.find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Calendar connection not found")
        return doc

    async def _update_account_tokens(
        self,
        connection_doc: dict,
        *,
        access_token: str,
        refresh_token: Optional[str],
        token_expiry: Optional[datetime],
        connection_status: str = CalendarConnectionStatus.ACTIVE.value,
        last_error: Optional[str] = None,
    ) -> None:
        """Update all calendar rows for the same user/provider account."""
        query = {
            "user_id": connection_doc.get("user_id"),
            "provider_account_email": connection_doc.get("provider_account_email"),
        }
        update_doc = {
            "access_token_encrypted": self._encrypt_token(access_token),
            "refresh_token_encrypted": self._encrypt_token(refresh_token),
            "token_expiry": token_expiry,
            "connection_status": connection_status,
            "last_error": last_error,
            "updated_at": datetime.now(UTC),
        }
        await self.connections_collection.update_many(query, {"$set": update_doc})

    async def get_credentials_for_connection(
        self, connection_id: str
    ) -> Optional[Credentials]:
        """Load decrypted credentials for a connection, refreshing if needed.

        Refreshes are guarded by a per-account lock so concurrent requests for
        the same Google account cannot race on a rotating refresh token. After
        acquiring the lock we re-read the connection doc — if a sibling
        request already refreshed, we use the freshly-stored tokens instead of
        refreshing again.
        """
        connection_doc = await self._get_connection_doc(connection_id)

        def _build_credentials(doc: dict) -> Credentials:
            return Credentials(
                token=self._decrypt_token(doc.get("access_token_encrypted")),
                refresh_token=self._decrypt_token(doc.get("refresh_token_encrypted")),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=settings.GOOGLE_CALENDAR_SCOPES,
            )

        credentials = _build_credentials(connection_doc)

        # Fast path: token still valid, no refresh needed, no lock needed.
        if not (credentials.expired and credentials.refresh_token):
            return credentials

        user_id = str(connection_doc.get("user_id") or "")
        provider_account_email = str(connection_doc.get("provider_account_email") or "")

        try:
            async with _account_token_lock(
                user_id=user_id,
                provider_account_email=provider_account_email,
            ):
                # Re-read the doc inside the lock so we pick up any tokens a
                # sibling request just persisted. This avoids double refresh
                # under a rotating-refresh-token policy.
                fresh_doc = await self.connections_collection.find_one(
                    {"_id": connection_doc["_id"]}
                )
                if fresh_doc is None:
                    return None
                connection_doc = fresh_doc
                credentials = _build_credentials(connection_doc)

                if not (credentials.expired and credentials.refresh_token):
                    return credentials

                # Blocking HTTP — run off the event loop.
                await asyncio.to_thread(credentials.refresh, Request())
                if not credentials.token:
                    raise HTTPException(
                        status_code=400,
                        detail="Failed to refresh Google access token",
                    )
                await self._update_account_tokens(
                    connection_doc,
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    token_expiry=credentials.expiry,
                )
        except HTTPException:
            raise
        except Exception as exc:
            redacted = _redact_sensitive(exc)
            logger.error("Failed to refresh Google credentials: %s", redacted)
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "connection_status": CalendarConnectionStatus.ERROR.value,
                        "last_error": redacted,
                        "last_healthcheck_at": datetime.now(UTC),
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            return None

        return credentials

    async def update_connection(
        self,
        connection_id: str,
        updates: dict[str, Any],
        *,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> dict:
        """Update mutable connection flags."""
        connection_doc = await self._get_connection_doc(connection_id)
        set_doc = {
            k: v
            for k, v in updates.items()
            if k
            in {
                "is_default_write_target",
                "scheduler_access_mode",
                "sync_targeting_mode",
                "allowed_scheduler_user_ids",
                "allowed_scheduler_roles",
                "allowed_schedule_item_types",
                "allowed_wedding_ids",
                "is_shared_in_team_view",
                "details_visibility",
                "sync_enabled",
                "task_sync_enabled",
                "task_sync_tasklist_id",
                "task_sync_tasklist_name",
                "contact_sync_enabled",
                "contact_sync_book_id",
                "contact_sync_book_name",
                "contact_sync_group_id",
                "contact_sync_group_name",
                "connection_scopes",
            }
            and v is not None
        }
        if not set_doc:
            return self._serialize_connection(connection_doc)

        if "allowed_scheduler_user_ids" in set_doc:
            set_doc["allowed_scheduler_user_ids"] = (
                self._normalize_scheduler_user_grants(
                    set_doc["allowed_scheduler_user_ids"]
                )
            )
        if "scheduler_access_mode" in set_doc:
            set_doc["scheduler_access_mode"] = self._normalize_scheduler_access_mode(
                set_doc["scheduler_access_mode"]
            )
        if "sync_targeting_mode" in set_doc:
            set_doc["sync_targeting_mode"] = self._normalize_sync_targeting_mode(
                set_doc["sync_targeting_mode"]
            )
        if "allowed_scheduler_roles" in set_doc:
            set_doc["allowed_scheduler_roles"] = self._normalize_scheduler_roles(
                set_doc["allowed_scheduler_roles"]
            )
        if "allowed_schedule_item_types" in set_doc:
            set_doc["allowed_schedule_item_types"] = (
                self._normalize_schedule_item_types(
                    set_doc["allowed_schedule_item_types"]
                )
            )
        if "allowed_wedding_ids" in set_doc:
            set_doc["allowed_wedding_ids"] = self._normalize_string_list(
                set_doc["allowed_wedding_ids"]
            )
        if "connection_scopes" in set_doc:
            set_doc["connection_scopes"] = self._normalize_string_list(
                set_doc["connection_scopes"]
            )

        if set_doc.get("is_default_write_target") and not (
            connection_doc.get("is_writable")
            and set_doc.get("sync_enabled", connection_doc.get("sync_enabled", False))
        ):
            raise HTTPException(
                status_code=400,
                detail="Only writable, sync-enabled calendars can be the default write target",
            )

        if set_doc.get("is_default_write_target"):
            await self.connections_collection.update_many(
                {
                    "user_id": connection_doc["user_id"],
                    "provider_account_email": connection_doc["provider_account_email"],
                    "is_writable": True,
                },
                {"$set": {"is_default_write_target": False}},
            )

        if set_doc.get("sync_enabled") is False and connection_doc.get(
            "is_default_write_target"
        ):
            set_doc["is_default_write_target"] = False

        set_doc["updated_at"] = datetime.now(UTC)
        await self.connections_collection.update_one(
            {"_id": connection_doc["_id"]},
            {"$set": set_doc},
        )
        await self.invalidate_connection_events_cache(connection_id)

        if set_doc.get("sync_enabled") is False and connection_doc.get(
            "is_default_write_target"
        ):
            replacement = await self.connections_collection.find_one(
                {
                    "user_id": connection_doc["user_id"],
                    "provider_account_email": connection_doc["provider_account_email"],
                    "_id": {"$ne": connection_doc["_id"]},
                    "is_writable": True,
                    "sync_enabled": True,
                }
            )
            if replacement:
                await self.connections_collection.update_one(
                    {"_id": replacement["_id"]},
                    {
                        "$set": {
                            "is_default_write_target": True,
                            "updated_at": datetime.now(UTC),
                        }
                    },
                )
        if "is_default_write_target" in set_doc and (
            set_doc["is_default_write_target"]
            != connection_doc.get("is_default_write_target")
        ):
            await calendar_audit_service.log(
                action="calendar_default_target_changed",
                message=f"Changed default write target to {connection_doc.get('calendar_name')}",
                owner_planner_email=connection_doc.get("owner_planner_email"),
                actor_email=actor_email,
                actor_role=actor_role,
                metadata={
                    "connection_id": connection_id,
                    "calendar_name": connection_doc.get("calendar_name"),
                    "is_default_write_target": set_doc["is_default_write_target"],
                },
            )
        if "allowed_scheduler_user_ids" in set_doc and (
            set_doc["allowed_scheduler_user_ids"]
            != self._normalize_scheduler_user_grants(
                connection_doc.get("allowed_scheduler_user_ids", [])
            )
        ):
            await calendar_audit_service.log(
                action="calendar_allowlist_changed",
                message=f"Updated scheduler allowlist for {connection_doc.get('calendar_name')}",
                owner_planner_email=connection_doc.get("owner_planner_email"),
                actor_email=actor_email,
                actor_role=actor_role,
                metadata={
                    "connection_id": connection_id,
                    "calendar_name": connection_doc.get("calendar_name"),
                    "allowed_scheduler_user_ids": set_doc["allowed_scheduler_user_ids"],
                },
            )
        if any(
            key in set_doc
            for key in (
                "scheduler_access_mode",
                "sync_targeting_mode",
                "allowed_scheduler_roles",
                "allowed_schedule_item_types",
                "allowed_wedding_ids",
            )
        ):
            await calendar_audit_service.log(
                action="calendar_policy_changed",
                message=f"Updated connection policy for {connection_doc.get('calendar_name')}",
                owner_planner_email=connection_doc.get("owner_planner_email"),
                actor_email=actor_email,
                actor_role=actor_role,
                metadata={
                    "connection_id": connection_id,
                    "calendar_name": connection_doc.get("calendar_name"),
                    "scheduler_access_mode": set_doc.get(
                        "scheduler_access_mode",
                        self._normalize_scheduler_access_mode(
                            connection_doc.get("scheduler_access_mode")
                        ),
                    ),
                    "sync_targeting_mode": set_doc.get(
                        "sync_targeting_mode",
                        self._normalize_sync_targeting_mode(
                            connection_doc.get("sync_targeting_mode")
                        ),
                    ),
                    "allowed_scheduler_roles": set_doc.get(
                        "allowed_scheduler_roles",
                        self._normalize_scheduler_roles(
                            connection_doc.get("allowed_scheduler_roles", [])
                        ),
                    ),
                    "allowed_schedule_item_types": set_doc.get(
                        "allowed_schedule_item_types",
                        self._normalize_schedule_item_types(
                            connection_doc.get("allowed_schedule_item_types", [])
                        ),
                    ),
                    "allowed_wedding_ids": set_doc.get(
                        "allowed_wedding_ids",
                        self._normalize_string_list(
                            connection_doc.get("allowed_wedding_ids", [])
                        ),
                    ),
                },
            )
        return self._serialize_connection(await self._get_connection_doc(connection_id))

    async def healthcheck_connection(self, connection_id: str) -> dict:
        """Validate a connection against Google and persist health state."""
        connection_doc = await self._get_connection_doc(connection_id)
        now = datetime.now(UTC)
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return self._serialize_connection(
                await self._get_connection_doc(connection_id)
            )

        try:
            service = build("calendar", "v3", credentials=credentials)
            calendar_entry = await asyncio.to_thread(
                lambda: (
                    service.calendarList()
                    .get(calendarId=connection_doc["calendar_id"])
                    .execute()
                )
            )
            is_writable = calendar_entry.get("accessRole") in {"owner", "writer"}
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "access_role": calendar_entry.get("accessRole"),
                        "calendar_name": calendar_entry.get("summaryOverride")
                        or calendar_entry.get("summary")
                        or connection_doc.get("calendar_name"),
                        "is_primary": bool(calendar_entry.get("primary")),
                        "is_writable": is_writable,
                        "sync_enabled": (
                            connection_doc.get("sync_enabled", False) and is_writable
                        ),
                        "connection_status": CalendarConnectionStatus.ACTIVE.value,
                        "last_error": None,
                        "last_healthcheck_at": now,
                        "updated_at": now,
                    }
                },
            )
            if connection_doc.get("is_default_write_target") and not is_writable:
                replacement = await self.connections_collection.find_one(
                    {
                        "user_id": connection_doc["user_id"],
                        "provider_account_email": connection_doc[
                            "provider_account_email"
                        ],
                        "_id": {"$ne": connection_doc["_id"]},
                        "is_writable": True,
                        "sync_enabled": True,
                    }
                )
                if replacement:
                    await self.connections_collection.update_one(
                        {"_id": replacement["_id"]},
                        {
                            "$set": {
                                "is_default_write_target": True,
                                "updated_at": now,
                            }
                        },
                    )
            await self.invalidate_connection_events_cache(connection_id)
        except Exception as exc:
            classification = self._classify_google_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "last_healthcheck_at": now,
                        "updated_at": now,
                    }
                },
            )

        return self._serialize_connection(await self._get_connection_doc(connection_id))

    async def _revoke_provider_account(self, connection_doc: dict) -> bool:
        """Revoke Google access for a provider account.

        Returns True on success (including 200 and 400 invalid_token responses
        — Google returns 400 if the token has already been revoked, which we
        treat as success since the desired end state matches). Returns False
        on transient/unknown failures so the caller can decide whether to
        proceed with the local delete.

        Prefers the refresh token: revoking it invalidates the entire grant
        (every access token derived from it), where revoking just an access
        token leaves the refresh token live.
        """
        refresh_token = self._decrypt_token(
            connection_doc.get("refresh_token_encrypted")
        )
        access_token = self._decrypt_token(connection_doc.get("access_token_encrypted"))
        token = refresh_token or access_token
        if not token:
            # Nothing to revoke — treat as already disconnected.
            return True
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": token},
                )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.warning(
                "Network failure revoking Google token: %s",
                _redact_sensitive(exc),
            )
            return False

        # Google returns 200 on successful revoke. For an already-revoked or
        # malformed token it returns 400 with `invalid_token` — semantically
        # the same end state, so we treat it as success and let the local
        # delete proceed.
        if response.status_code == 200:
            return True
        if response.status_code == 400:
            try:
                payload = response.json()
            except Exception:
                payload = {}
            if isinstance(payload, dict) and payload.get("error") in {
                "invalid_token",
                "invalid_grant",
            }:
                return True
        logger.warning(
            "Unexpected response revoking Google token: status=%s body=%s",
            response.status_code,
            _redact_sensitive(response.text),
        )
        return False

    async def disconnect_connection(
        self,
        connection_id: str,
        *,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> dict:
        """Delete one connection row.

        Order of operations is deliberate:
        1. Determine if this is the last row for the provider account.
        2. If yes, attempt revoke at Google FIRST. On retryable failure raise
           503 and leave local state intact so the user can retry.
        3. Only after revoke succeeds (or there are sibling rows still pinning
           the grant), delete the local row + orphan its sync rows.

        Revoke is treated as idempotent — Google returning `invalid_token`
        (400) for an already-revoked grant is also success.
        """
        connection_doc = await self._get_connection_doc(connection_id)
        account_query = {
            "user_id": connection_doc["user_id"],
            "provider_account_email": connection_doc["provider_account_email"],
        }
        sibling_count = await self.connections_collection.count_documents(account_query)
        is_last_row_for_account = sibling_count <= 1

        # H-4 / C-4: revoke BEFORE the local delete, always (idempotent at
        # Google's end). If this is not the last row for the provider account
        # we skip revoke because other rows still legitimately need the grant.
        if is_last_row_for_account:
            revoked = await self._revoke_provider_account(connection_doc)
            if not revoked:
                # Transient revoke failure — bubble up so the user retries
                # rather than ending up with a stale grant at Google.
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Could not revoke Google access right now. "
                        "Please try disconnecting again in a moment."
                    ),
                )

        now = datetime.now(UTC)
        await self.syncs_collection.update_many(
            {"calendar_connection_id": connection_id},
            {
                "$set": {
                    "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                    "last_error": "Calendar connection disconnected",
                    "last_error_category": "connection_disconnected",
                    "retryable_error": False,
                    "next_retry_at": None,
                    "updated_at": now,
                },
                "$unset": {
                    "calendar_connection_id": "",
                    "calendar_id": "",
                },
            },
        )
        await self.connections_collection.delete_one({"_id": connection_doc["_id"]})
        await self.invalidate_connection_events_cache(connection_id)

        promoted = await self.connections_collection.find_one(
            {
                **account_query,
                "is_writable": True,
                "is_default_write_target": True,
            }
        )
        if not promoted:
            replacement = await self.connections_collection.find_one(
                {**account_query, "is_writable": True}
            )
            if replacement:
                await self.connections_collection.update_one(
                    {"_id": replacement["_id"]},
                    {"$set": {"is_default_write_target": True, "updated_at": now}},
                )

        await calendar_audit_service.log(
            action="calendar_connection_disconnected",
            message=f"Disconnected Google Calendar {connection_doc.get('calendar_name')}",
            owner_planner_email=connection_doc.get("owner_planner_email"),
            actor_email=actor_email or connection_doc.get("user_email"),
            actor_role=actor_role,
            metadata={
                "connection_id": connection_id,
                "provider": connection_doc.get("provider", "google"),
                "calendar_name": connection_doc.get("calendar_name"),
                "provider_account_email": connection_doc.get("provider_account_email"),
                "revoked_provider_grant": is_last_row_for_account,
            },
        )

        return {"disconnected": True, "connection_id": connection_id}

    async def get_default_write_connection_for_user(
        self,
        user_email: str,
    ) -> Optional[dict]:
        """Resolve the active default writable connection for a user."""
        query = {
            "user_email": user_email,
            "connection_status": CalendarConnectionStatus.ACTIVE.value,
            "is_writable": True,
            "sync_enabled": True,
        }
        connection = await self.connections_collection.find_one(
            {**query, "is_default_write_target": True}
        )
        if connection:
            return connection
        return await self.connections_collection.find_one(query)

    async def get_connection_status(self, user_email: str) -> Dict[str, Any]:
        """Compatibility helper for legacy UI that expects one status object."""
        connection = await self.get_default_write_connection_for_user(user_email)
        if not connection:
            return {
                "connected": False,
                "calendar_id": None,
                "last_sync": None,
                "sync_enabled": False,
                "events_synced": 0,
            }

        synced_count = await self.syncs_collection.count_documents(
            {
                "target_user_email": user_email,
                "sync_status": CalendarSyncStatusValue.SYNCED.value,
            }
        )
        return {
            "connected": True,
            "calendar_id": connection.get("calendar_id"),
            "last_sync": connection.get("last_sync_at"),
            "sync_enabled": connection.get("sync_enabled", True),
            "events_synced": synced_count,
        }

    async def disconnect(self, user_email: str) -> Dict[str, Any]:
        """Compatibility helper to disconnect every connection for a user.

        Performs revocation per *provider account* (not per row), then bulk
        deletes the rows in a single statement. Avoids the partial-failure
        and silent-truncation issues of the prior per-row loop.
        """
        docs = await self.connections_collection.find(
            {"user_email": user_email}
        ).to_list(length=None)
        if not docs:
            return {
                "disconnected": True,
                "message": "Google Calendar was not connected",
            }

        # Group rows by (user_id, provider_account_email) — one revoke per
        # Google account, regardless of how many calendars are connected.
        by_account: Dict[tuple[str, str], list[dict[str, Any]]] = {}
        for doc in docs:
            key = (
                str(doc.get("user_id") or ""),
                str(doc.get("provider_account_email") or ""),
            )
            by_account.setdefault(key, []).append(doc)

        revoke_failures: list[str] = []
        for (_user_id, provider_email), account_docs in by_account.items():
            # Pick any row from the account — they share the provider grant.
            sample = account_docs[0]
            revoked = await self._revoke_provider_account(sample)
            if not revoked:
                revoke_failures.append(provider_email)

        if revoke_failures:
            # Don't delete locally if we couldn't revoke at Google — surface
            # the failure so the user retries, matching disconnect_connection.
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not revoke Google access for "
                    f"{', '.join(revoke_failures)}. Please try again in a moment."
                ),
            )

        connection_ids = [str(doc["_id"]) for doc in docs]
        now = datetime.now(UTC)

        await self.syncs_collection.update_many(
            {"calendar_connection_id": {"$in": connection_ids}},
            {
                "$set": {
                    "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                    "last_error": "Calendar connection disconnected",
                    "last_error_category": "connection_disconnected",
                    "retryable_error": False,
                    "next_retry_at": None,
                    "updated_at": now,
                },
                "$unset": {
                    "calendar_connection_id": "",
                    "calendar_id": "",
                },
            },
        )
        await self.connections_collection.delete_many({"user_email": user_email})
        for connection_id in connection_ids:
            await self.invalidate_connection_events_cache(connection_id)

        # One audit log per account, summarizing the bulk disconnect.
        for (_user_id, provider_email), account_docs in by_account.items():
            sample = account_docs[0]
            await calendar_audit_service.log(
                action="calendar_connection_disconnected",
                message=f"Disconnected Google Calendar account {provider_email}",
                owner_planner_email=sample.get("owner_planner_email"),
                actor_email=sample.get("user_email"),
                actor_role=None,
                metadata={
                    "connection_ids": [str(d["_id"]) for d in account_docs],
                    "provider": "google",
                    "provider_account_email": provider_email,
                    "calendars_disconnected": len(account_docs),
                    "revoked_provider_grant": True,
                },
            )

        return {"disconnected": True, "message": "Google Calendar disconnected"}

    def _coerce_datetime(self, value: Any, field_name: str) -> datetime:
        """Normalize persisted schedule fields into datetimes before provider sync."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        raise ValueError(f"Task is missing a valid {field_name}")

    def _build_event_body(
        self,
        task: Dict[str, Any],
        attendee_emails: Optional[list[str]] = None,
    ) -> dict:
        """Translate a canonical task record into a Google Calendar event body."""
        event_body: dict[str, Any] = {
            "summary": task.get("title"),
            "description": task.get("description") or task.get("notes") or "",
        }
        timezone_name = (
            task.get("timezone") or settings.GOOGLE_CALENDAR_DEFAULT_TIMEZONE
        )
        start_date = self._coerce_datetime(task.get("start_date"), "start_date")
        end_date = self._coerce_datetime(
            task.get("end_date") or task.get("start_date"),
            "end_date",
        )

        if task.get("all_day"):
            event_body["start"] = {"date": start_date.strftime("%Y-%m-%d")}
            event_body["end"] = {
                "date": (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
            }
        else:
            event_body["start"] = {
                "dateTime": start_date.isoformat(),
                "timeZone": timezone_name,
            }
            event_body["end"] = {
                "dateTime": end_date.isoformat(),
                "timeZone": timezone_name,
            }

        if task.get("reminder_minutes"):
            event_body["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": task["reminder_minutes"]},
                ],
            }

        if task.get("is_recurring") and task.get("recurrence_rule"):
            event_body["recurrence"] = [f"RRULE:{task['recurrence_rule']}"]

        if task.get("conference_url"):
            event_body["location"] = task["conference_url"]

        if attendee_emails:
            event_body["attendees"] = [{"email": email} for email in attendee_emails]

        color = task.get("color")
        if color and color.lower() in _GOOGLE_EVENT_COLOR_MAP:
            event_body["colorId"] = _GOOGLE_EVENT_COLOR_MAP[color.lower()]

        return event_body

    async def create_google_event_for_connection(
        self,
        connection_id: str,
        task: Dict[str, Any],
        attendee_emails: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create an event on a specific Google calendar connection."""
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return {
                "success": False,
                "calendar_id": None,
                "external_event_id": None,
                "etag": None,
                "retryable": False,
                "error_category": "credentials_unavailable",
                "error_message": "Google credentials are unavailable for this connection",
                "status_code": None,
            }

        connection_doc = await self._get_connection_doc(connection_id)
        try:
            service = build("calendar", "v3", credentials=credentials)
            event_body = self._build_event_body(task, attendee_emails)
            event = await asyncio.to_thread(
                lambda: (
                    service.events()
                    .insert(
                        calendarId=connection_doc["calendar_id"],
                        body=event_body,
                    )
                    .execute()
                )
            )
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "last_sync_at": datetime.now(UTC),
                        "connection_status": CalendarConnectionStatus.ACTIVE.value,
                        "last_error": None,
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            await self.invalidate_connection_events_cache(connection_id)
            return self._build_provider_result(
                success=True,
                connection_doc=connection_doc,
                external_event_id=event.get("id"),
                etag=event.get("etag"),
            )
        except Exception as exc:
            classification = self._classify_google_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            logger.error(
                "Failed to create Google event for connection %s: %s",
                connection_id,
                _redact_sensitive(exc),
            )
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                classification=classification,
            )

    async def update_google_event_for_connection(
        self,
        connection_id: str,
        external_event_id: str,
        task: Dict[str, Any],
        attendee_emails: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Update an existing event on a specific Google calendar connection."""
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return {
                "success": False,
                "calendar_id": None,
                "external_event_id": external_event_id,
                "etag": None,
                "retryable": False,
                "error_category": "credentials_unavailable",
                "error_message": "Google credentials are unavailable for this connection",
                "status_code": None,
            }

        connection_doc = await self._get_connection_doc(connection_id)
        try:
            service = build("calendar", "v3", credentials=credentials)
            event_body = self._build_event_body(task, attendee_emails)
            event = await asyncio.to_thread(
                lambda: (
                    service.events()
                    .update(
                        calendarId=connection_doc["calendar_id"],
                        eventId=external_event_id,
                        body=event_body,
                    )
                    .execute()
                )
            )
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "last_sync_at": datetime.now(UTC),
                        "last_error": None,
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            await self.invalidate_connection_events_cache(connection_id)
            return self._build_provider_result(
                success=True,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                etag=event.get("etag"),
            )
        except Exception as exc:
            classification = self._classify_google_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            logger.error(
                "Failed to update Google event %s: %s",
                external_event_id,
                _redact_sensitive(exc),
            )
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                classification=classification,
            )

    async def delete_google_event_for_connection(
        self,
        connection_id: str,
        external_event_id: str,
    ) -> dict[str, Any]:
        """Delete an existing event from a specific Google calendar connection."""
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return {
                "success": False,
                "calendar_id": None,
                "external_event_id": external_event_id,
                "etag": None,
                "retryable": False,
                "error_category": "credentials_unavailable",
                "error_message": "Google credentials are unavailable for this connection",
                "status_code": None,
            }

        connection_doc = await self._get_connection_doc(connection_id)
        try:
            service = build("calendar", "v3", credentials=credentials)
            await asyncio.to_thread(
                lambda: (
                    service.events()
                    .delete(
                        calendarId=connection_doc["calendar_id"],
                        eventId=external_event_id,
                    )
                    .execute()
                )
            )
            await self.invalidate_connection_events_cache(connection_id)
            return self._build_provider_result(
                success=True,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
            )
        except Exception as exc:
            classification = self._classify_google_exception(exc)
            if classification.get("error_category") == "not_found":
                await self.invalidate_connection_events_cache(connection_id)
                return self._build_provider_result(
                    success=True,
                    connection_doc=connection_doc,
                    external_event_id=external_event_id,
                    classification=classification,
                )
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            logger.error(
                "Failed to delete Google event %s: %s",
                external_event_id,
                _redact_sensitive(exc),
            )
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                classification=classification,
            )

    async def get_google_event_for_connection(
        self,
        connection_id: str,
        external_event_id: str,
    ) -> dict[str, Any]:
        """Load one provider event for drift detection."""
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return {
                "success": False,
                "calendar_id": None,
                "external_event_id": external_event_id,
                "etag": None,
                "retryable": False,
                "error_category": "credentials_unavailable",
                "error_message": "Google credentials are unavailable for this connection",
                "status_code": None,
                "event": None,
            }

        connection_doc = await self._get_connection_doc(connection_id)
        try:
            service = build("calendar", "v3", credentials=credentials)
            event = await asyncio.to_thread(
                lambda: (
                    service.events()
                    .get(
                        calendarId=connection_doc["calendar_id"],
                        eventId=external_event_id,
                    )
                    .execute()
                )
            )
            return self._build_provider_result(
                success=True,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                etag=event.get("etag"),
                event=event,
            )
        except Exception as exc:
            classification = self._classify_google_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                classification=classification,
            )

    async def fetch_google_events_for_connection(
        self,
        connection_id: str,
        *,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 200,
    ) -> List[Dict[str, Any]]:
        """Fetch events from a specific connection for shared-calendar aggregation."""
        if not time_min:
            time_min = datetime.now(UTC)
        if not time_max:
            time_max = time_min + timedelta(days=30)

        connection_doc = await self._get_connection_doc(connection_id)
        cache_key = self._external_events_cache_key(
            connection_id=connection_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )
        cached_events = await cache.get(cache_key)
        if isinstance(cached_events, list):
            return [
                {
                    **event,
                    "_connection": self._serialize_connection(connection_doc),
                }
                for event in cached_events
            ]

        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return []

        try:
            service = build("calendar", "v3", credentials=credentials)
            events_result = await asyncio.to_thread(
                lambda: (
                    service.events()
                    .list(
                        calendarId=connection_doc["calendar_id"],
                        timeMin=time_min.isoformat(),
                        timeMax=time_max.isoformat(),
                        maxResults=max_results,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
            )
            events = events_result.get("items", [])
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "last_sync_at": datetime.now(UTC),
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            await cache.set(
                cache_key,
                events,
                expire=settings.CALENDAR_SHARED_EVENTS_CACHE_SECONDS,
            )
            for event in events:
                event["_connection"] = self._serialize_connection(connection_doc)
            return events
        except Exception as exc:
            classification = self._classify_google_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            logger.error(
                "Failed to fetch Google events for connection %s: %s",
                connection_id,
                _redact_sensitive(exc),
            )
            return []

    async def fetch_google_events(
        self,
        user_email: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Legacy wrapper for single-user Google event fetch."""
        connection = await self.get_default_write_connection_for_user(user_email)
        if not connection:
            return []
        return await self.fetch_google_events_for_connection(
            str(connection["_id"]),
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )


# Singleton instance
google_calendar_service = GoogleCalendarService()

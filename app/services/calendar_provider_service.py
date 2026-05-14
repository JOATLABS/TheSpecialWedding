"""Calendar provider service — thin wrapper over the Aurinko Unified API.

Aurinko owns the per-provider OAuth flow (Google, Microsoft 365, iCloud,
Exchange, Zoho) and exposes a unified API for calendar / event management.
We talk to one HTTP endpoint and route on the connection row's
``aurinko_account_id`` rather than per-provider clients.

This service is the single seam between WeddingWebApp and Aurinko. The
surrounding code (``calendar_sync_service``, ``calendar_aggregation_service``,
``calendar_webhook_service``, the team-availability API, the couple booking
endpoints) is provider-agnostic and consumes the result shapes returned here.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncIterator, Dict, List, Optional
from contextlib import asynccontextmanager
from urllib.parse import quote
from uuid import uuid4

import httpx
import jwt
from bson import ObjectId
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core.cache import cache
from app.core.config import settings
from app.core.database import mongo
from app.models.calendar import ScheduleItemType, VisibilityMode
from app.models.calendar_connection import (
    CalendarConnectionStatus,
    CalendarProvider,
    CalendarSchedulerAccessMode,
    CalendarSchedulerRole,
    CalendarSyncTargetingMode,
)
from app.models.calendar_sync import CalendarSyncStatusValue
from app.services.calendar_audit_service import calendar_audit_service

logger = logging.getLogger(__name__)


_NON_PRODUCTION_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "ci"})

_AURINKO_HTTP_TIMEOUT_SECONDS = 30.0
_AURINKO_LIST_PAGE_SIZE = 100
_AURINKO_LIST_MAX_PAGES = 50

# Shared httpx.AsyncClient — keeps connections alive across calls so the
# team-availability fan-out (one request per connection) reuses TCP/TLS state.
_aurinko_http_client: Optional[httpx.AsyncClient] = None


def _get_aurinko_http_client() -> httpx.AsyncClient:
    global _aurinko_http_client
    if _aurinko_http_client is None or _aurinko_http_client.is_closed:
        _aurinko_http_client = httpx.AsyncClient(
            timeout=_AURINKO_HTTP_TIMEOUT_SECONDS,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _aurinko_http_client


async def close_aurinko_http_client() -> None:
    """Close the shared client. Call from app shutdown."""
    global _aurinko_http_client
    if _aurinko_http_client is not None and not _aurinko_http_client.is_closed:
        await _aurinko_http_client.aclose()
    _aurinko_http_client = None


# Conservative scrubber for Aurinko-issued bearer tokens and OAuth codes that
# may surface inside error strings before they hit the database/log pipeline.
_REDACT_NAMED_PATTERNS = [
    re.compile(r"(?i)(access_token['\"\s:=]+)[A-Za-z0-9._\-/+]+"),
    re.compile(r"(?i)(refresh_token['\"\s:=]+)[A-Za-z0-9._\-/+]+"),
    re.compile(r"(?i)(\bcode['\"\s:=]+)[A-Za-z0-9._\-/+]+"),
    re.compile(r"(?i)(authorization['\"\s:=]+)Bearer\s+[A-Za-z0-9._\-/+]+"),
]


def _redact_sensitive(text: Any) -> str:
    if text is None:
        return ""
    out = str(text)
    for pattern in _REDACT_NAMED_PATTERNS:
        out = pattern.sub(r"\1[REDACTED]", out)
    return out


@asynccontextmanager
async def _account_token_lock(*, aurinko_account_id: str) -> AsyncIterator[None]:
    """Per-Aurinko-account lock so concurrent callers don't race on token state."""
    lock_key = f"calendar_account_token_lock:{aurinko_account_id}"
    lock_value = uuid4().hex
    acquired = await cache.acquire_lock(lock_key, lock_value, expire=30)
    if acquired is False:
        raise HTTPException(
            status_code=409,
            detail="Calendar credentials are being refreshed by another request. Try again.",
        )
    try:
        yield
    finally:
        if acquired:
            await cache.release_lock(lock_key, lock_value)


class AurinkoClient:
    """Thin HTTP client around the Aurinko Unified API.

    All endpoints that act on a connected account take the per-account bearer
    token issued during OAuth callback. Account-management endpoints (auth
    URL, token exchange, healthcheck via /accounts/me) authenticate with the
    platform-level Aurinko app credentials.
    """

    def __init__(self) -> None:
        self.base_url = settings.AURINKO_API_BASE_URL.rstrip("/")

    def _platform_basic_auth(self) -> tuple[str, str]:
        client_id = settings.AURINKO_CLIENT_ID or settings.AURINKO_APP_ID or ""
        client_secret = settings.AURINKO_CLIENT_SECRET or settings.AURINKO_API_KEY or ""
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=503,
                detail="Calendar aggregator is not configured. Missing Aurinko credentials.",
            )
        return client_id, client_secret

    def _account_headers(self, account_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {account_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        account_token: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
        platform_auth: bool = False,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        kwargs: dict[str, Any] = {"params": params}
        if json_body is not None:
            kwargs["json"] = json_body

        if platform_auth:
            client_id, client_secret = self._platform_basic_auth()
            kwargs["auth"] = (client_id, client_secret)
        elif account_token:
            kwargs["headers"] = self._account_headers(account_token)
        else:
            raise RuntimeError(
                "Aurinko request requires either an account token or platform auth"
            )

        client = _get_aurinko_http_client()
        return await client.request(method, url, **kwargs)

    # Provider id → Aurinko serviceType (exact strings from the
    # /v1/auth/authorize enum at apirefs.aurinko.io).
    _PROVIDER_TO_SERVICE_TYPE = {
        "google": "Google",
        "office365": "Office365",
        "icloud": "iCloud",
        "ews": "EWS",
    }
    # Aurinko's ``/v1/auth/authorize`` accepts a SINGLE serviceType value.
    # Passing a comma-separated multi-value (e.g. "Google,Office365,...")
    # returns 400 "customapi.notfound" — Aurinko looks up the literal
    # string as a service type and fails. There is no native picker
    # mode. The planner UI provides its own four-button picker (one
    # button per provider), so the default-Google fallback below only
    # fires when a caller forgets to pass a provider id.
    _DEFAULT_SERVICE_TYPE = "Google"

    @classmethod
    def resolve_service_type(cls, provider: Optional[str]) -> str:
        """Map a planner-facing provider id to Aurinko's ``serviceType``.

        - "google" / "office365" / "icloud" / "ews" (case-insensitive)
          → the single Aurinko-spec value, so the user lands directly on
          that provider's OAuth screen.
        - None / "" / unknown id → "Google" (safe fallback so the OAuth
          flow doesn't error out — the planner can cancel from Google's
          screen and re-initiate against a different provider).
        """
        if not provider:
            return cls._DEFAULT_SERVICE_TYPE
        return cls._PROVIDER_TO_SERVICE_TYPE.get(
            provider.strip().lower(), cls._DEFAULT_SERVICE_TYPE
        )

    async def authorize_url(
        self,
        *,
        scopes: list[str],
        return_url: str,
        state: str,
        service_type: Optional[str] = None,
    ) -> str:
        """Build a hosted-auth URL the user is redirected to.

        Aurinko's hosted-auth endpoint takes the platform app's clientId and a
        return URL we own. Aurinko handles the per-provider OAuth screens and
        redirects the user back to our return URL with a ``code`` query
        parameter that we exchange for an account token.

        ``service_type`` (optional) is forwarded as the ``serviceType`` query
        param. Pass a single Aurinko-spec value ("Google", "Office365",
        "iCloud", "EWS") to pre-select a provider and skip Aurinko's picker.
        Pass None (default) to send the full picker list so Aurinko renders
        its own provider chooser.
        """
        client_id, _ = self._platform_basic_auth()
        # Aurinko accepts a SINGLE serviceType value only. Live-verified
        # 2026-05-13: passing a comma-separated multi-value returns 400
        # "customapi.notfound" — Aurinko treats the whole string as a
        # service-type lookup key and can't resolve it. Per-provider
        # entry points pass one of {Google, Office365, iCloud, EWS};
        # missing/unknown falls back to "Google" via resolve_service_type.
        resolved_service_type = (
            service_type or ""
        ).strip() or self._DEFAULT_SERVICE_TYPE
        # On-prem Exchange uses "EWS" (Exchange Web Services) — "Exchange" is
        # silently dropped.
        #
        # Scopes MUST be space-separated. Live-verified 2026-05-13 against
        # api.aurinko.io/v1/auth/authorize via three back-to-back probes
        # with this app's clientId — results pinned here so future
        # contributors don't have to re-derive them:
        #
        #   scopes=Calendar.Read+Calendar.ReadWrite       → returnUrl.invalid
        #     (scopes accepted; the next validation step failed)
        #   scopes=Calendar.ReadOnly+Calendar.ReadWrite   → "Unable to parse
        #     Scopes" — the ".ReadOnly" suffix is NOT a real scope name
        #     despite appearing in
        #     docs.aurinko.io/authentication/google-oauth-setup
        #   scopes=Calendar.Read,Calendar.ReadWrite       → "Unable to parse
        #     Scopes" — comma delimiter is rejected despite appearing in
        #     the docs.aurinko.io/authentication/authentication-scopes
        #     curl example. Aurinko's docs are inconsistent across pages;
        #     the LIVE API only matches the URL example in
        #     account-oauth-flow.md.
        #
        # Canonical scope names (verified against the parser):
        #   Mail.Read, Mail.ReadWrite, Mail.Drafts (plural!), Mail.Send,
        #   Calendar.Read, Calendar.ReadWrite,
        #   Contacts.Read, Contacts.ReadWrite,
        #   Tasks.Read, Tasks.ReadWrite
        #
        # `+` and `%20` both encode space and are both accepted; httpx's
        # QueryParams uses `+` which is fine.
        params = {
            "clientId": client_id,
            "serviceType": resolved_service_type,
            "scopes": " ".join(scopes),
            "responseType": "code",
            "returnUrl": return_url,
            "state": state,
        }
        # httpx.QueryParams URL-encodes values when stringified — important
        # because both `state` (signed JWT with `=` `+` `/`) and `scopes`
        # (space-separated) contain reserved characters.
        query = str(httpx.QueryParams(params))
        return f"{self.base_url}/auth/authorize?{query}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange a hosted-auth code for an account-scoped access token."""
        response = await self._request(
            "POST",
            f"/auth/token/{quote(code, safe='')}",
            platform_auth=True,
        )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Aurinko token exchange failed: {response.status_code}",
            )
        return response.json()

    async def get_account(self, account_token: str) -> dict[str, Any]:
        """Fetch the connected account's identity info from Aurinko.

        Endpoint: ``GET /v1/account`` (NOT /am/accounts/me — that path
        resolves to /am/accounts/{id} with id="me" and 400s on the integer
        parse). Verified live 2026-05-12 against api.aurinko.io.
        """
        response = await self._request("GET", "/account", account_token=account_token)
        response.raise_for_status()
        return response.json()

    async def list_calendars(self, account_token: str) -> list[dict[str, Any]]:
        """List all calendars for the connected Aurinko account."""
        calendars: list[dict[str, Any]] = []
        offset = 0
        for _ in range(_AURINKO_LIST_MAX_PAGES):
            response = await self._request(
                "GET",
                "/calendars",
                account_token=account_token,
                params={"offset": offset, "pageSize": _AURINKO_LIST_PAGE_SIZE},
            )
            response.raise_for_status()
            payload = response.json()
            records = payload.get("records") or payload.get("calendars") or []
            calendars.extend(records)
            if len(records) < _AURINKO_LIST_PAGE_SIZE:
                break
            offset += _AURINKO_LIST_PAGE_SIZE
        return calendars

    async def list_events(
        self,
        *,
        account_token: str,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> list[dict[str, Any]]:
        """List events within a calendar/time-window with offset pagination.

        Aurinko's event endpoints take the calendar id in the URL path
        (``/calendars/{calId}/events``); it is not a query parameter.
        """
        page_size = min(max_results, _AURINKO_LIST_PAGE_SIZE)
        events: list[dict[str, Any]] = []
        offset = 0
        path = f"/calendars/{quote(calendar_id, safe='')}/events"
        for _ in range(_AURINKO_LIST_MAX_PAGES):
            params = {
                "start": time_min.isoformat(),
                "end": time_max.isoformat(),
                "pageSize": page_size,
                "offset": offset,
            }
            response = await self._request(
                "GET",
                path,
                account_token=account_token,
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            records = payload.get("records") or payload.get("events") or []
            events.extend(records)
            if len(records) < page_size or len(events) >= max_results:
                break
            offset += page_size
        return events[:max_results]

    async def create_event(
        self,
        *,
        account_token: str,
        calendar_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/calendars/{quote(calendar_id, safe='')}/events",
            account_token=account_token,
            json_body=body,
        )
        response.raise_for_status()
        return response.json()

    async def update_event(
        self,
        *,
        account_token: str,
        calendar_id: str,
        external_event_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        # Aurinko uses PATCH (not PUT) for event updates per their Calendar API
        # docs. PUT silently 404s on most providers via Aurinko's router.
        response = await self._request(
            "PATCH",
            f"/calendars/{quote(calendar_id, safe='')}/events/{quote(external_event_id, safe='')}",
            account_token=account_token,
            json_body=body,
        )
        response.raise_for_status()
        return response.json()

    async def delete_event(
        self,
        *,
        account_token: str,
        calendar_id: str,
        external_event_id: str,
    ) -> None:
        response = await self._request(
            "DELETE",
            f"/calendars/{quote(calendar_id, safe='')}/events/{quote(external_event_id, safe='')}",
            account_token=account_token,
        )
        if response.status_code == 404:
            return
        response.raise_for_status()

    async def get_event(
        self,
        *,
        account_token: str,
        calendar_id: str,
        external_event_id: str,
    ) -> dict[str, Any]:
        response = await self._request(
            "GET",
            f"/calendars/{quote(calendar_id, safe='')}/events/{quote(external_event_id, safe='')}",
            account_token=account_token,
        )
        response.raise_for_status()
        return response.json()

    async def create_subscription(
        self,
        *,
        account_token: str,
        calendar_id: str,
        webhook_url: str,
    ) -> dict[str, Any]:
        """Subscribe to change notifications for a single calendar.

        Aurinko subscriptions are scoped per-resource — there is no
        "all calendars on this account" subscription. The valid resource
        strings for calendar events are ``/calendars/primary/events`` and
        ``/calendars/{calId}/events``. We always use the explicit calendar id
        so a planner with multiple calendars connected gets per-calendar
        delivery.
        """
        body = {
            "resource": f"/calendars/{calendar_id}/events",
            "notificationUrl": webhook_url,
        }
        response = await self._request(
            "POST",
            "/subscriptions",
            account_token=account_token,
            json_body=body,
        )
        response.raise_for_status()
        return response.json()

    async def delete_subscription(
        self,
        *,
        account_token: str,
        subscription_id: str,
    ) -> None:
        response = await self._request(
            "DELETE",
            f"/subscriptions/{subscription_id}",
            account_token=account_token,
        )
        if response.status_code == 404:
            return
        response.raise_for_status()

    async def list_booking_profiles(
        self, *, account_token: str
    ) -> list[dict[str, Any]]:
        """List the Aurinko booking profiles available to this account.

        Each profile is a planner-published "scheduling profile" (per-duration,
        per-calendar set, per-availability-rules). Aurinko returns them under
        /v1/book/account/profiles.

        Returns the raw 'records' array; callers decide which profile is
        canonical for a given couple-booking request.
        """
        response = await self._request(
            "GET", "/book/account/profiles", account_token=account_token
        )
        response.raise_for_status()
        body = response.json()
        return body.get("records") or body.get("profiles") or []

    async def get_availability(
        self,
        *,
        account_token: str,
        profile: str,
        from_: datetime,
        to: datetime,
        duration_minutes: Optional[int] = None,
    ) -> dict[str, Any]:
        """Query Aurinko for free slots in [from_, to] for the given profile.

        Aurinko endpoint: GET /v1/book/account/profiles/{profile}/availability
        with `from` and `to` ISO timestamps. Optional `duration` (minutes) hints
        the slot length when the profile supports multiple. Returns the raw
        Aurinko response (slots list + metadata); the couple_booking_service
        decides how many to surface to the planner.
        """
        params: dict[str, Any] = {
            "from": from_.isoformat(),
            "to": to.isoformat(),
        }
        if duration_minutes is not None:
            params["duration"] = int(duration_minutes)
        response = await self._request(
            "GET",
            f"/book/account/profiles/{quote(profile, safe='')}/availability",
            account_token=account_token,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def create_booking(
        self,
        *,
        account_token: str,
        profile: str,
        start: datetime,
        duration_minutes: int,
        attendees: list[dict[str, Any]],
        subject: Optional[str] = None,
        notes: Optional[str] = None,
        start_conference: bool = False,
    ) -> dict[str, Any]:
        """Create a booking on Aurinko for a chosen slot.

        Endpoint: POST /v1/book/account/profiles/{profile}.
        Aurinko will (a) write the event on the planner's connected calendar
        via the underlying provider and (b) fire the /booking/{bookingId}
        webhook lifecycle (see docs.aurinko.io/unified-apis/webhooks-api).
        `start_conference=True` triggers Aurinko's conference auto-create
        (Zoom/Teams/Webex depending on the planner's enabled Messaging
        integrations on the Aurinko app dashboard).
        """
        body: dict[str, Any] = {
            "start": start.isoformat(),
            "duration": int(duration_minutes),
            "attendees": attendees,
        }
        if subject is not None:
            body["subject"] = subject
        if notes is not None:
            body["notes"] = notes
        if start_conference:
            body["startConference"] = True
        response = await self._request(
            "POST",
            f"/book/account/profiles/{quote(profile, safe='')}",
            account_token=account_token,
            json_body=body,
        )
        response.raise_for_status()
        return response.json()

    async def get_booking(
        self, *, account_token: str, booking_id: str
    ) -> dict[str, Any]:
        """Fetch a booking by id.

        Used to reconcile state after the /booking/{bookingId} webhook fires
        (which delivers only id + bookingId — no snapshot). Endpoint:
        GET /v1/book/account/bookings/{bookingId}.
        """
        response = await self._request(
            "GET",
            f"/book/account/bookings/{quote(booking_id, safe='')}",
            account_token=account_token,
        )
        response.raise_for_status()
        return response.json()

    async def cancel_booking(
        self,
        *,
        account_token: str,
        booking_id: str,
        reason: Optional[str] = None,
    ) -> None:
        """Cancel an Aurinko booking. Idempotent — 404 treated as success.

        Endpoint: DELETE /v1/book/account/bookings/{bookingId}.
        """
        params: dict[str, Any] = {}
        if reason is not None:
            params["reason"] = reason
        response = await self._request(
            "DELETE",
            f"/book/account/bookings/{quote(booking_id, safe='')}",
            account_token=account_token,
            params=params or None,
        )
        if response.status_code == 404:
            return
        response.raise_for_status()

    async def revoke_account(self, account_token: str) -> None:
        """Disconnect the Aurinko account; idempotent.

        Endpoint: ``DELETE /v1/account`` (NOT /am/accounts/me — that path
        is interpreted as /am/accounts/{id} where id="me" and 400s on the
        integer parse). Verified live 2026-05-12 against api.aurinko.io.

        Per docs (apirefs.aurinko.io/#tag/Account/operation/deleteAccount)
        this deletes the Aurinko account record entirely. The lighter-touch
        alternative ``DELETE /account/token`` revokes only the token +
        provider auth, keeping the Aurinko account row — switch to that if
        we ever want to preserve Aurinko-side history across reconnects.
        """
        response = await self._request(
            "DELETE",
            "/account",
            account_token=account_token,
        )
        if response.status_code in (200, 204, 404):
            return
        response.raise_for_status()


def _normalize_event_for_aggregation(
    raw_event: dict[str, Any],
    *,
    provider: str,
) -> dict[str, Any]:
    """Translate an Aurinko event into the shape calendar_aggregation_service consumes.

    Output schema mirrors the prior Google Calendar event shape so downstream
    code is a one-import change:

      {summary, description, location, status, htmlLink, attendees,
       start: {dateTime|date, timeZone},
       end:   {dateTime|date, timeZone},
       id, etag, updated, _provider}
    """
    when = raw_event.get("when") or {}
    start_value = when.get("start") or raw_event.get("start") or {}
    end_value = when.get("end") or raw_event.get("end") or {}
    parent_timezone = when.get("timeZone") or when.get("timezone")

    def _normalize_endpoint(endpoint: Any) -> dict[str, Any]:
        if isinstance(endpoint, str):
            if "T" in endpoint:
                normalized: dict[str, Any] = {"dateTime": endpoint}
                if parent_timezone:
                    normalized["timeZone"] = parent_timezone
                return normalized
            return {"date": endpoint}
        if isinstance(endpoint, dict):
            normalized = {}
            if endpoint.get("dateTime"):
                normalized["dateTime"] = endpoint["dateTime"]
            elif endpoint.get("date"):
                normalized["date"] = endpoint["date"]
            elif endpoint.get("time"):
                normalized["dateTime"] = endpoint["time"]
            tz = endpoint.get("timeZone") or endpoint.get("timezone") or parent_timezone
            if tz and "date" not in normalized:
                normalized["timeZone"] = tz
            return normalized
        return {}

    return {
        "id": raw_event.get("id") or raw_event.get("eventId"),
        "etag": raw_event.get("etag") or raw_event.get("changeKey"),
        "summary": raw_event.get("subject") or raw_event.get("summary") or "",
        "description": raw_event.get("description")
        or raw_event.get("bodyPreview")
        or "",
        "location": (raw_event.get("location") or {}).get("displayName")
        if isinstance(raw_event.get("location"), dict)
        else raw_event.get("location"),
        "status": raw_event.get("status") or raw_event.get("showAs"),
        "htmlLink": raw_event.get("htmlLink") or raw_event.get("webLink"),
        "attendees": raw_event.get("attendees") or [],
        "start": _normalize_endpoint(start_value),
        "end": _normalize_endpoint(end_value),
        "updated": raw_event.get("lastModifiedDateTime") or raw_event.get("updated"),
        "_provider": provider,
    }


class CalendarProviderService:
    """Connection lifecycle, event projection, and webhook plumbing via Aurinko."""

    def __init__(self) -> None:
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_calendar_event_syncs_collection()
        # Drafts hold the encrypted Aurinko account token + calendar list
        # between OAuth callback and the picker-modal submission. See
        # ``handle_oauth_callback`` / ``commit_calendar_selection``.
        self.drafts_collection = mongo.get_calendar_connection_drafts_collection()
        self.tasks_collection = mongo.get_planner_tasks_collection()
        self.client = AurinkoClient()
        self._validate_security_configuration()

    def _is_production_environment(self) -> bool:
        env = (settings.ENVIRONMENT or "").lower().strip()
        return env not in _NON_PRODUCTION_ENVIRONMENTS

    def _aurinko_configured(self) -> bool:
        return bool(
            (settings.AURINKO_CLIENT_ID or settings.AURINKO_APP_ID)
            and (settings.AURINKO_CLIENT_SECRET or settings.AURINKO_API_KEY)
        )

    def _webhook_url(self) -> Optional[str]:
        """Build the public Aurinko webhook delivery URL."""
        base = settings.NEXT_PUBLIC_API_BASE_URL
        if not base:
            return None
        return base.rstrip("/") + "/api/calendar/webhooks/aurinko"

    def _validate_security_configuration(self) -> None:
        if not (self._aurinko_configured() and self._is_production_environment()):
            return
        missing: list[str] = []
        if not settings.AURINKO_OAUTH_STATE_SIGNING_KEY:
            missing.append("AURINKO_OAUTH_STATE_SIGNING_KEY")
        if not settings.TOKEN_ENCRYPTION_KEY:
            missing.append("TOKEN_ENCRYPTION_KEY")
        if missing:
            raise RuntimeError(
                "Calendar aggregator integration requires explicit security keys "
                "in production: " + ", ".join(missing)
            )

    # ----- normalization helpers ------------------------------------------

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

    # ----- cache helpers --------------------------------------------------

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

    # ----- error classification & application -----------------------------

    def _classify_aurinko_exception(self, exc: Exception) -> dict[str, Any]:
        """Map Aurinko HTTP exceptions to internal error categories.

        Categories mirror the prior Google classification so calendar_sync and
        retry policy code sees the same shape.
        """
        message = _redact_sensitive(exc)
        status_code: Optional[int] = None
        error_reason: Optional[str] = None

        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            try:
                payload = exc.response.json()
            except Exception:
                payload = {}
            if isinstance(payload, dict):
                error_reason = payload.get("error") or payload.get("code")
                message = payload.get("message") or message
        elif isinstance(
            exc, (TimeoutError, ConnectionError, OSError, httpx.RequestError)
        ):
            return {
                "retryable": True,
                "error_category": "temporary",
                "status_code": None,
                "error_reason": "transport_error",
                "error_message": message,
            }

        if status_code == 429:
            return {
                "retryable": True,
                "error_category": "rate_limited",
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

    # ----- token encryption -----------------------------------------------

    def _get_state_signing_key(self) -> str:
        if (
            self._is_production_environment()
            and not settings.AURINKO_OAUTH_STATE_SIGNING_KEY
        ):
            raise RuntimeError(
                "AURINKO_OAUTH_STATE_SIGNING_KEY must be configured in production"
            )
        return (
            settings.AURINKO_OAUTH_STATE_SIGNING_KEY
            or settings.SECRET_KEY
            or "dev-aurinko-oauth-state-key"
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
        *,
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
        return jwt.encode(payload, self._get_state_signing_key(), algorithm="HS256")

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

        required_fields = ("sub", "user_email", "owner_id", "owner_email")
        if not all(payload.get(field) for field in required_fields):
            raise HTTPException(
                status_code=400, detail="OAuth state is missing required fields"
            )
        return payload

    # ----- OAuth -----------------------------------------------------------

    async def get_authorization_url(
        self,
        *,
        user_id: str,
        user_email: str,
        owner_id: str,
        owner_email: str,
        redirect_to: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> str:
        """Generate the Aurinko hosted-auth URL for a planner/team member.

        ``provider`` (optional) is a planner-facing id ("google", "office365",
        "icloud", "ews"). When set, the corresponding Aurinko ``serviceType``
        value is forwarded so the user lands directly on that provider's
        OAuth screen. When omitted, the full ``Google,Office365,iCloud,EWS``
        list is sent and Aurinko renders its own picker.
        """
        if not settings.AURINKO_REDIRECT_URI:
            raise HTTPException(
                status_code=503,
                detail="Calendar aggregator is not configured. Missing AURINKO_REDIRECT_URI.",
            )
        state = self._build_state(
            user_id=user_id,
            user_email=user_email,
            owner_id=owner_id,
            owner_email=owner_email,
            redirect_to=redirect_to,
        )
        # settings.AURINKO_SCOPES is a string (env values are strings). The
        # client's authorize_url expects list[str] and does ','.join(scopes)
        # — if we pass the raw string, ','.join iterates characters and
        # produces 'C,a,l,e,n,d,a,r,...'. Split on whitespace OR comma so
        # whatever form the env uses ("a b" or "a,b") parses correctly.
        scope_list = [
            s for s in re.split(r"[,\s]+", settings.AURINKO_SCOPES.strip()) if s
        ]
        service_type = AurinkoClient.resolve_service_type(provider)
        return await self.client.authorize_url(
            scopes=scope_list,
            return_url=settings.AURINKO_REDIRECT_URI,
            state=state,
            service_type=service_type,
        )

    async def handle_oauth_callback(
        self,
        *,
        code: str,
        state: str,
        current_user_context: Optional[dict[str, Optional[str]]] = None,
    ) -> Dict[str, Any]:
        """Exchange the Aurinko callback code for an account token and persist rows."""
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

        try:
            token_response = await self.client.exchange_code(code)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Aurinko code exchange failed: %s", _redact_sensitive(exc))
            raise HTTPException(
                status_code=400, detail="Failed to complete calendar authorization"
            ) from exc

        account_token = token_response.get("accessToken") or token_response.get("token")
        aurinko_account_id = str(
            token_response.get("accountId") or token_response.get("id") or ""
        )
        if not account_token or not aurinko_account_id:
            raise HTTPException(
                status_code=502,
                detail="Calendar aggregator did not return a usable account token",
            )

        # Identity probe is best-effort. /v1/account may require a scope
        # we no longer request (Aurinko's catalog has no AccountInfo.Read
        # equivalent), in which case it 401s. We can still serve the connect
        # flow by falling back to the email returned at token-exchange time
        # and finally to the planner's own email captured in the signed
        # state JWT — both are trusted sources we already validated above.
        account_info: dict[str, Any] = {}
        try:
            account_info = await self.client.get_account(account_token)
        except Exception as exc:
            logger.warning(
                "Aurinko /v1/account probe failed; continuing with token-response "
                "+ state-JWT identity fallback: %s",
                _redact_sensitive(exc),
            )

        provider_account_email = (
            account_info.get("email")
            or token_response.get("email")
            or state_payload.get("user_email")
        )
        if not provider_account_email:
            # Three independent sources empty — that should be impossible
            # because state_payload.user_email is required at state-build
            # time. If we land here, the state JWT itself was malformed and
            # we cannot proceed safely.
            raise HTTPException(
                status_code=502,
                detail=(
                    "Could not resolve a connected-account email from any source "
                    "(account info, token response, or signed state). Please retry."
                ),
            )
        provider_account_name = (
            account_info.get("name")
            or account_info.get("displayName")
            or provider_account_email
        )
        provider_label = self._map_aurinko_service_to_provider(
            account_info.get("type") or token_response.get("serviceType")
        )

        try:
            calendars = await self.client.list_calendars(account_token)
        except Exception as exc:
            logger.error(
                "Failed to list calendars during Aurinko OAuth callback: %s",
                _redact_sensitive(exc),
            )
            raise HTTPException(
                status_code=502,
                detail="Could not load calendars from your account. Please try again.",
            ) from exc

        if not calendars:
            raise HTTPException(
                status_code=400,
                detail="Calendar account did not return any calendars to connect",
            )

        encrypted_token = self._encrypt_token(account_token)
        now = datetime.now(UTC)
        owner_id = str(state_payload.get("owner_id") or "")
        owner_email = str(state_payload.get("owner_email") or "")
        user_id = str(state_payload.get("sub") or "")
        user_email = str(state_payload.get("user_email") or "")

        writable_calendar_ids = [
            entry.get("id") or entry.get("calendarId")
            for entry in calendars
            if self._is_writable_calendar(entry)
        ]
        primary_writable_id = next(
            (
                (entry.get("id") or entry.get("calendarId"))
                for entry in calendars
                if entry.get("primary") and self._is_writable_calendar(entry)
            ),
            None,
        )
        default_write_id = primary_writable_id or (
            writable_calendar_ids[0] if writable_calendar_ids else None
        )

        # Option B (deferred-creation): stash everything we need to
        # materialize connection rows + webhook subscriptions in a draft
        # row, then return the calendar list to the frontend's picker
        # modal. The planner picks which calendars to actually sync; on
        # POST /admin/planner/calendar/connections/select we drain the
        # draft into per-calendar rows for the picked subset only.
        # Un-picked calendars never get a row and never trigger a
        # webhook-subscribe attempt — which is the root cause fix for
        # the "Webhook subscription failed for N calendars" banner we
        # saw with read-only iCal feeds (Cushion, Holidays, etc.).
        picker_calendars: list[dict[str, Any]] = []
        for entry in calendars:
            calendar_id = entry.get("id") or entry.get("calendarId")
            if not calendar_id:
                continue
            is_writable = self._is_writable_calendar(entry)
            picker_calendars.append(
                {
                    "aurinko_calendar_id": calendar_id,
                    "name": (
                        entry.get("name")
                        or entry.get("summary")
                        or entry.get("title")
                        or calendar_id
                    ),
                    "access_role": entry.get("accessRole") or entry.get("access"),
                    "is_writable": is_writable,
                    "is_primary": bool(entry.get("primary")),
                    "suggested_default_write": bool(
                        is_writable and calendar_id == default_write_id
                    ),
                }
            )

        expires_at = now + timedelta(minutes=30)
        await self.drafts_collection.update_one(
            {"user_id": user_id, "aurinko_account_id": aurinko_account_id},
            {
                "$set": {
                    "owner_planner_id": owner_id,
                    "owner_planner_email": owner_email,
                    "user_id": user_id,
                    "user_email": user_email,
                    "provider": provider_label,
                    "provider_account_email": provider_account_email,
                    "provider_account_name": provider_account_name,
                    "aurinko_account_id": aurinko_account_id,
                    "aurinko_access_token_encrypted": encrypted_token,
                    # Full Aurinko-shape calendar payload for the commit step.
                    "calendars_payload": list(calendars),
                    "default_write_calendar_id": default_write_id,
                    "redirect_to": state_payload.get("redirect_to"),
                    "expires_at": expires_at,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        draft = await self.drafts_collection.find_one(
            {"user_id": user_id, "aurinko_account_id": aurinko_account_id}
        )
        draft_id = str(draft["_id"]) if draft else ""

        return {
            "connected": False,
            "needs_selection": True,
            "draft_id": draft_id,
            "account_email": provider_account_email,
            "account_name": provider_account_name,
            "provider": provider_label,
            "calendars": picker_calendars,
            "redirect_to": state_payload.get("redirect_to"),
            "message": (
                f"Found {len(picker_calendars)} calendar(s) on "
                f"{provider_account_email}. Pick which to sync."
            ),
        }

    async def commit_calendar_selection(
        self,
        *,
        draft_id: str,
        user_id: str,
        picks: list[dict[str, Any]],
    ) -> Dict[str, Any]:
        """Drain a draft into ``calendar_connections`` rows + webhook subs.

        Loads the draft created during ``handle_oauth_callback``, then
        for each picked calendar:
          1. Creates / updates a ``calendar_connections`` row with the
             same shape and defaults as the pre-Option-B flow.
          2. Registers an Aurinko webhook subscription for writable
             picks (read-only feeds skip the subscription per Aurinko's
             /subscriptions semantics — they wouldn't accept it anyway).

        Un-picked calendars are silently dropped — no rows, no
        subscriptions. The draft is deleted on success (or left to
        TTL-expire on partial failure so the picker can be retried).

        ``picks`` shape per entry::

            {
                "aurinko_calendar_id": str,           # REQUIRED
                "is_default_write_target": bool,     # optional override
                "details_visibility": "details"|"busy_only",  # optional
                "is_shared_in_team_view": bool,      # optional
            }

        Returns the same response shape the pre-Option-B
        ``handle_oauth_callback`` used to return, so the existing
        ``ProviderCallbackResponse`` model can carry it forward.
        """
        try:
            draft_oid = ObjectId(draft_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Invalid draft id") from exc

        # Guard: a planner must only be able to commit their OWN drafts.
        # Without this filter, a leaked draft id would let any
        # authenticated user activate someone else's connection.
        draft = await self.drafts_collection.find_one(
            {"_id": draft_oid, "user_id": user_id}
        )
        if draft is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Calendar selection draft not found or expired. Please "
                    "re-run the Connect calendar flow."
                ),
            )

        aurinko_account_id = str(draft.get("aurinko_account_id") or "")
        encrypted_token = draft.get("aurinko_access_token_encrypted")
        account_token = self._decrypt_token(encrypted_token)
        if not aurinko_account_id or not account_token:
            await self.drafts_collection.delete_one({"_id": draft_oid})
            raise HTTPException(
                status_code=500,
                detail="Draft token unreadable — please re-run Connect calendar.",
            )

        owner_id = str(draft.get("owner_planner_id") or "")
        owner_email = str(draft.get("owner_planner_email") or "")
        user_email = str(draft.get("user_email") or "")
        provider_label = str(draft.get("provider") or "")
        provider_account_email = str(draft.get("provider_account_email") or "")
        provider_account_name = str(draft.get("provider_account_name") or "")
        calendars = list(draft.get("calendars_payload") or [])
        draft_default_write = draft.get("default_write_calendar_id")

        # Index Aurinko's calendar payload by id so picks can join in.
        calendars_by_id: dict[str, dict[str, Any]] = {}
        for entry in calendars:
            cid = entry.get("id") or entry.get("calendarId")
            if cid:
                calendars_by_id[str(cid)] = entry

        # Picks → only keep those that reference a real calendar Aurinko
        # returned. Drops any client-side tampering attempts.
        picked_ids: list[str] = []
        pick_overrides: dict[str, dict[str, Any]] = {}
        for pick in picks or []:
            cid = str(pick.get("aurinko_calendar_id") or "").strip()
            if not cid or cid not in calendars_by_id:
                continue
            picked_ids.append(cid)
            pick_overrides[cid] = pick

        if not picked_ids:
            # "Skip for now" path — just delete the draft and return a
            # zero-rows success. The planner can re-open the picker from
            # Settings later (future work). No webhook attempts, no row
            # churn, no error toast.
            await self.drafts_collection.delete_one({"_id": draft_oid})
            return {
                "connected": True,
                "calendar_id": None,
                "connections_created": 0,
                "redirect_to": draft.get("redirect_to"),
                "message": (
                    "No calendars selected. You can connect calendars "
                    "later from Settings."
                ),
                "warning": None,
            }

        now = datetime.now(UTC)

        # Compute the effective default-write target from picks, falling
        # back to the suggested one if the picker didn't flip anyone.
        explicit_default_write = next(
            (
                cid
                for cid in picked_ids
                if pick_overrides.get(cid, {}).get("is_default_write_target")
            ),
            None,
        )
        effective_default_write = (
            explicit_default_write
            or (str(draft_default_write) if draft_default_write else None)
            or next(
                (
                    cid
                    for cid in picked_ids
                    if self._is_writable_calendar(calendars_by_id[cid])
                ),
                None,
            )
        )

        seen_calendar_ids: list[str] = []
        for calendar_id in picked_ids:
            entry = calendars_by_id[calendar_id]
            override = pick_overrides.get(calendar_id, {})
            seen_calendar_ids.append(calendar_id)
            is_writable = self._is_writable_calendar(entry)
            connection_query = {
                "user_id": user_id,
                "aurinko_account_id": aurinko_account_id,
                "aurinko_calendar_id": calendar_id,
            }
            existing_doc = await self.connections_collection.find_one(connection_query)
            connection_doc = {
                "owner_planner_id": owner_id,
                "owner_planner_email": owner_email,
                "user_id": user_id,
                "user_email": user_email,
                "provider": provider_label,
                "provider_account_email": provider_account_email,
                "provider_account_name": provider_account_name,
                "aurinko_account_id": aurinko_account_id,
                "aurinko_calendar_id": calendar_id,
                "aurinko_access_token_encrypted": encrypted_token,
                "calendar_id": calendar_id,
                "calendar_name": (
                    entry.get("name")
                    or entry.get("summary")
                    or entry.get("title")
                    or calendar_id
                ),
                "access_role": entry.get("accessRole") or entry.get("access"),
                "is_writable": is_writable,
                "is_primary": bool(entry.get("primary")),
                "is_default_write_target": bool(
                    is_writable and calendar_id == effective_default_write
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
                "is_shared_in_team_view": bool(
                    override.get(
                        "is_shared_in_team_view",
                        existing_doc.get("is_shared_in_team_view", False)
                        if existing_doc is not None
                        else False,
                    )
                ),
                "details_visibility": str(
                    override.get(
                        "details_visibility",
                        existing_doc.get(
                            "details_visibility", VisibilityMode.BUSY_ONLY.value
                        )
                        if existing_doc is not None
                        else VisibilityMode.BUSY_ONLY.value,
                    )
                ),
                "sync_enabled": (
                    existing_doc.get("sync_enabled", is_writable)
                    if existing_doc is not None and is_writable
                    else is_writable
                ),
                "connection_status": CalendarConnectionStatus.ACTIVE.value,
                "last_error": None,
                "updated_at": now,
            }
            await self.connections_collection.update_one(
                connection_query,
                {"$set": connection_doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )

        # Calendars that were present in a prior OAuth but are no longer
        # returned by Aurinko (e.g. user removed the calendar from their
        # provider) must be torn down completely: tear down each row's
        # per-calendar Aurinko subscription, mark dependent event_syncs as
        # ORPHANED, and only then delete the connection rows. Mirrors the
        # teardown pattern in ``disconnect()``.
        stale_filter = {
            "user_id": user_id,
            "aurinko_account_id": aurinko_account_id,
            "aurinko_calendar_id": {"$nin": seen_calendar_ids},
        }
        stale_rows = await self.connections_collection.find(stale_filter).to_list(
            length=None
        )
        if stale_rows:
            for stale_row in stale_rows:
                stale_subscription_id = stale_row.get("aurinko_subscription_id")
                if not stale_subscription_id:
                    continue
                stale_token = self._decrypt_token(
                    stale_row.get("aurinko_access_token_encrypted")
                )
                if not stale_token:
                    continue
                try:
                    await self.client.delete_subscription(
                        account_token=stale_token,
                        subscription_id=str(stale_subscription_id),
                    )
                except Exception as exc:
                    logger.warning(
                        "Aurinko unsubscribe for stale calendar %s on account %s "
                        "failed during reconnect teardown: %s",
                        stale_row.get("aurinko_calendar_id"),
                        aurinko_account_id,
                        _redact_sensitive(exc),
                    )
            stale_connection_ids = [str(row["_id"]) for row in stale_rows]
            if stale_connection_ids:
                await self.syncs_collection.update_many(
                    {"calendar_connection_id": {"$in": stale_connection_ids}},
                    {
                        "$set": {
                            "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                            "last_error": "Calendar removed from provider",
                            "last_error_category": "connection_disconnected",
                            "retryable_error": False,
                            "next_retry_at": None,
                            "updated_at": now,
                        },
                        "$unset": {"calendar_connection_id": "", "calendar_id": ""},
                    },
                )
        await self.connections_collection.delete_many(stale_filter)

        existing_default = await self.connections_collection.find_one(
            {
                "user_id": user_id,
                "aurinko_account_id": aurinko_account_id,
                "is_writable": True,
                "is_default_write_target": True,
            }
        )
        if not existing_default and effective_default_write:
            await self.connections_collection.update_one(
                {
                    "user_id": user_id,
                    "aurinko_account_id": aurinko_account_id,
                    "aurinko_calendar_id": effective_default_write,
                    "is_writable": True,
                },
                {"$set": {"is_default_write_target": True, "updated_at": now}},
            )

        # Register one Aurinko subscription per writable calendar. Aurinko
        # subscriptions are per-resource (``/calendars/{calId}/events``); there
        # is no "all calendars on this account" subscription. Reconnects must
        # tear down the prior per-row subscription before creating a new one
        # so subscriptions don't accumulate Aurinko-side.
        webhook_url = self._webhook_url()
        webhook_warning: Optional[str] = None
        webhook_failure_count = 0
        if webhook_url:
            writable_rows = await self.connections_collection.find(
                {
                    "user_id": user_id,
                    "aurinko_account_id": aurinko_account_id,
                    "is_writable": True,
                }
            ).to_list(length=None)

            for row in writable_rows:
                calendar_id = row.get("aurinko_calendar_id")
                if not calendar_id:
                    continue

                prior_subscription_id = row.get("aurinko_subscription_id")
                if prior_subscription_id:
                    try:
                        await self.client.delete_subscription(
                            account_token=account_token,
                            subscription_id=str(prior_subscription_id),
                        )
                    except Exception as exc:
                        logger.info(
                            "Could not delete prior Aurinko subscription %s for "
                            "calendar %s on account %s: %s",
                            prior_subscription_id,
                            calendar_id,
                            aurinko_account_id,
                            _redact_sensitive(exc),
                        )

                try:
                    subscription = await self.client.create_subscription(
                        account_token=account_token,
                        calendar_id=calendar_id,
                        webhook_url=webhook_url,
                    )
                    subscription_id = str(
                        subscription.get("id")
                        or subscription.get("subscriptionId")
                        or ""
                    )
                    await self.connections_collection.update_one(
                        {"_id": row["_id"]},
                        {
                            "$set": {
                                "aurinko_subscription_id": subscription_id or None,
                                "updated_at": now,
                            }
                        },
                    )
                except Exception as exc:
                    webhook_failure_count += 1
                    logger.warning(
                        "Failed to register Aurinko webhook subscription for "
                        "calendar %s on account %s: %s",
                        calendar_id,
                        aurinko_account_id,
                        _redact_sensitive(exc),
                    )

            if webhook_failure_count:
                webhook_warning = (
                    f"Webhook subscription failed for {webhook_failure_count} "
                    "calendar(s); external changes on those calendars won't be "
                    "detected in real time until you reconnect."
                )
                await self.connections_collection.update_many(
                    {
                        "user_id": user_id,
                        "aurinko_account_id": aurinko_account_id,
                        "is_writable": True,
                        "aurinko_subscription_id": None,
                    },
                    {
                        "$set": {
                            "last_error": webhook_warning,
                            "updated_at": now,
                        }
                    },
                )

        await calendar_audit_service.log(
            action="calendar_connection_connected",
            message=f"Connected calendar account {provider_account_email} ({provider_label})",
            owner_planner_email=owner_email,
            actor_email=user_email,
            actor_role="planner" if owner_id == user_id else "team_member",
            metadata={
                "provider": provider_label,
                "provider_account_email": provider_account_email,
                "aurinko_account_id": aurinko_account_id,
                "connections_created": len(seen_calendar_ids),
                "default_write_calendar_id": effective_default_write,
                "picked_via_modal": True,
            },
        )

        # Draft is drained — delete so the unique (user_id,
        # aurinko_account_id) index is free for the next reconnect.
        await self.drafts_collection.delete_one({"_id": draft_oid})

        message = "Successfully connected calendar account"
        if webhook_warning:
            message = f"{message}. {webhook_warning}"
        return {
            "connected": True,
            "calendar_id": effective_default_write,
            "connections_created": len(seen_calendar_ids),
            "redirect_to": draft.get("redirect_to"),
            "message": message,
            "warning": webhook_warning,
        }

    def _is_writable_calendar(self, entry: dict[str, Any]) -> bool:
        access = (
            entry.get("accessRole")
            or entry.get("access")
            or entry.get("permission")
            or ""
        ).lower()
        if access in {"owner", "writer", "editor", "write", "readwrite"}:
            return True
        capabilities = entry.get("capabilities") or {}
        return bool(capabilities.get("canEdit") or capabilities.get("canWrite"))

    def _map_aurinko_service_to_provider(self, service_type: Any) -> str:
        if not service_type:
            return CalendarProvider.UNKNOWN.value
        normalized = str(service_type).strip().lower()
        if normalized in {"google", "gmail"}:
            return CalendarProvider.GOOGLE.value
        if normalized in {"office365", "ms365", "microsoft365"}:
            return CalendarProvider.OFFICE365.value
        if normalized in {"outlook", "outlookcom", "outlook.com"}:
            return CalendarProvider.OUTLOOK.value
        if normalized in {"exchange", "ews"}:
            # Aurinko's hosted-auth uses "EWS" (Exchange Web Services) on the
            # request side and may echo either form back from /am/accounts/me;
            # both map to our EXCHANGE provider label.
            return CalendarProvider.EXCHANGE.value
        if normalized in {"icloud", "apple"}:
            return CalendarProvider.ICLOUD.value
        if normalized in {"zoho"}:
            return CalendarProvider.ZOHO.value
        return CalendarProvider.UNKNOWN.value

    # ----- connection CRUD -------------------------------------------------

    def _serialize_connection(self, doc: dict) -> dict:
        return {
            "id": str(doc["_id"]),
            "owner_planner_id": doc.get("owner_planner_id"),
            "owner_planner_email": doc.get("owner_planner_email"),
            "user_id": doc.get("user_id"),
            "user_email": doc.get("user_email"),
            "provider": doc.get("provider", CalendarProvider.UNKNOWN.value),
            "provider_account_email": doc.get("provider_account_email"),
            "provider_account_name": doc.get("provider_account_name"),
            "aurinko_account_id": doc.get("aurinko_account_id"),
            "aurinko_calendar_id": doc.get("aurinko_calendar_id"),
            "aurinko_subscription_id": doc.get("aurinko_subscription_id"),
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
            "couple_booking_auto_confirm": doc.get("couple_booking_auto_confirm", True),
            "conference_provider_default": doc.get("conference_provider_default"),
            "connection_status": doc.get(
                "connection_status", CalendarConnectionStatus.ERROR.value
            ),
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

    async def get_connection_doc(self, connection_id: str) -> dict:
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

    async def update_connection(
        self,
        connection_id: str,
        updates: dict[str, Any],
        *,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> dict:
        connection_doc = await self.get_connection_doc(connection_id)
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
                "couple_booking_auto_confirm",
                "conference_provider_default",
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
                    "aurinko_account_id": connection_doc["aurinko_account_id"],
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
            {"_id": connection_doc["_id"]}, {"$set": set_doc}
        )
        await self.invalidate_connection_events_cache(connection_id)

        # Subscription lifecycle on sync_enabled flip. Aurinko subscriptions
        # are per-resource (one per calendar), so we track them per-row.
        # true→false: tear down the row's subscription so we stop receiving
        # change notifications we no longer want to act on.
        # false→true: register a fresh subscription so external changes
        # surface again. No-op if calendar is not writable (subscriptions are
        # only meaningful for write-targets).
        if "sync_enabled" in set_doc and connection_doc.get("is_writable"):
            prior_sync_enabled = bool(connection_doc.get("sync_enabled", False))
            new_sync_enabled = bool(set_doc["sync_enabled"])
            token = await self._account_token_for_connection(connection_doc)
            calendar_id = connection_doc.get("aurinko_calendar_id")

            if prior_sync_enabled and not new_sync_enabled:
                prior_subscription_id = connection_doc.get("aurinko_subscription_id")
                if token and prior_subscription_id:
                    try:
                        await self.client.delete_subscription(
                            account_token=token,
                            subscription_id=str(prior_subscription_id),
                        )
                    except Exception as exc:
                        logger.warning(
                            "Aurinko unsubscribe on sync_enabled toggle failed for "
                            "calendar %s: %s",
                            calendar_id,
                            _redact_sensitive(exc),
                        )
                await self.connections_collection.update_one(
                    {"_id": connection_doc["_id"]},
                    {
                        "$set": {
                            "aurinko_subscription_id": None,
                            "updated_at": datetime.now(UTC),
                        }
                    },
                )

            if not prior_sync_enabled and new_sync_enabled:
                webhook_url = self._webhook_url()
                if webhook_url and token and calendar_id:
                    try:
                        subscription = await self.client.create_subscription(
                            account_token=token,
                            calendar_id=calendar_id,
                            webhook_url=webhook_url,
                        )
                        subscription_id = str(
                            subscription.get("id")
                            or subscription.get("subscriptionId")
                            or ""
                        )
                        await self.connections_collection.update_one(
                            {"_id": connection_doc["_id"]},
                            {
                                "$set": {
                                    "aurinko_subscription_id": subscription_id or None,
                                    "updated_at": datetime.now(UTC),
                                }
                            },
                        )
                    except Exception as exc:
                        logger.warning(
                            "Aurinko subscribe on sync_enabled toggle failed for "
                            "calendar %s: %s",
                            calendar_id,
                            _redact_sensitive(exc),
                        )

        if set_doc.get("sync_enabled") is False and connection_doc.get(
            "is_default_write_target"
        ):
            replacement = await self.connections_collection.find_one(
                {
                    "user_id": connection_doc["user_id"],
                    "aurinko_account_id": connection_doc["aurinko_account_id"],
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
                metadata={"connection_id": connection_id},
            )
        return self._serialize_connection(await self.get_connection_doc(connection_id))

    async def healthcheck_connection(self, connection_id: str) -> dict:
        """Validate a connection against Aurinko and persist health state."""
        connection_doc = await self.get_connection_doc(connection_id)
        now = datetime.now(UTC)
        token = self._decrypt_token(
            connection_doc.get("aurinko_access_token_encrypted")
        )
        if not token:
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "connection_status": CalendarConnectionStatus.REVOKED.value,
                        "last_error": "Aurinko account token unavailable; please reconnect",
                        "last_healthcheck_at": now,
                        "updated_at": now,
                    }
                },
            )
            return self._serialize_connection(
                await self.get_connection_doc(connection_id)
            )

        try:
            await self.client.get_account(token)
            calendar_id = connection_doc.get(
                "aurinko_calendar_id"
            ) or connection_doc.get("calendar_id")
            if calendar_id:
                calendars = await self.client.list_calendars(token)
                still_present = any(
                    (entry.get("id") or entry.get("calendarId")) == calendar_id
                    for entry in calendars
                )
                if not still_present:
                    await self.connections_collection.update_one(
                        {"_id": connection_doc["_id"]},
                        {
                            "$set": {
                                "connection_status": CalendarConnectionStatus.ERROR.value,
                                "last_error": (
                                    "Calendar is no longer available on the connected "
                                    "account. Please reconnect or pick another calendar."
                                ),
                                "last_healthcheck_at": now,
                                "updated_at": now,
                            }
                        },
                    )
                    return self._serialize_connection(
                        await self.get_connection_doc(connection_id)
                    )
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "connection_status": CalendarConnectionStatus.ACTIVE.value,
                        "last_error": None,
                        "last_healthcheck_at": now,
                        "updated_at": now,
                    }
                },
            )
        except Exception as exc:
            classification = self._classify_aurinko_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {"$set": {"last_healthcheck_at": now}},
            )
        return self._serialize_connection(await self.get_connection_doc(connection_id))

    async def disconnect_connection(
        self,
        connection_id: str,
        *,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> dict:
        """Delete one connection row, revoking the Aurinko account if last row."""
        connection_doc = await self.get_connection_doc(connection_id)
        account_query = {
            "user_id": connection_doc["user_id"],
            "aurinko_account_id": connection_doc["aurinko_account_id"],
        }
        sibling_count = await self.connections_collection.count_documents(account_query)
        is_last_row_for_account = sibling_count <= 1

        # Subscriptions are per-calendar — every row carries its own
        # ``aurinko_subscription_id``. Tear THIS row's subscription down
        # unconditionally, otherwise mid-row disconnects leak the
        # subscription on Aurinko's side. Account-token revocation, on the
        # other hand, MUST stay conditional on last-row — revoking the
        # account token mid-disconnect would kill every sibling row's
        # token.
        token = self._decrypt_token(
            connection_doc.get("aurinko_access_token_encrypted")
        )
        subscription_id = connection_doc.get("aurinko_subscription_id")
        if token and subscription_id:
            try:
                await self.client.delete_subscription(
                    account_token=token, subscription_id=str(subscription_id)
                )
            except Exception as exc:
                logger.warning(
                    "Aurinko unsubscribe for calendar %s on account %s failed: %s",
                    connection_doc.get("aurinko_calendar_id"),
                    connection_doc.get("aurinko_account_id"),
                    _redact_sensitive(exc),
                )
        if is_last_row_for_account and token:
            try:
                await self.client.revoke_account(token)
            except Exception as exc:
                logger.warning(
                    "Aurinko revoke for account %s failed (continuing with local "
                    "disconnect): %s",
                    connection_doc.get("aurinko_account_id"),
                    _redact_sensitive(exc),
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
                "$unset": {"calendar_connection_id": "", "calendar_id": ""},
            },
        )
        await self.connections_collection.delete_one({"_id": connection_doc["_id"]})
        await self.invalidate_connection_events_cache(connection_id)

        promoted = await self.connections_collection.find_one(
            {**account_query, "is_writable": True, "is_default_write_target": True}
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
            message=f"Disconnected calendar {connection_doc.get('calendar_name')}",
            owner_planner_email=connection_doc.get("owner_planner_email"),
            actor_email=actor_email or connection_doc.get("user_email"),
            actor_role=actor_role,
            metadata={
                "connection_id": connection_id,
                "provider": connection_doc.get("provider"),
                "calendar_name": connection_doc.get("calendar_name"),
                "provider_account_email": connection_doc.get("provider_account_email"),
                "aurinko_account_id": connection_doc.get("aurinko_account_id"),
                "revoked_aggregator_grant": is_last_row_for_account,
            },
        )
        return {"disconnected": True, "connection_id": connection_id}

    async def get_default_write_connection_for_user(
        self, user_email: str
    ) -> Optional[dict]:
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

    async def disconnect(
        self, user_email: str, *, owner_planner_id: str
    ) -> Dict[str, Any]:
        """Disconnect every connection for a (workspace, user) pair.

        Team-member identity is compound ``(owner_planner_id, user_email)``;
        the same email can legitimately appear in multiple planner
        workspaces. Filtering by ``user_email`` alone would cross-disconnect
        calendars in workspaces the caller never selected. Every Mongo
        filter inside this method MUST carry ``owner_planner_id`` to keep
        the action tenant-scoped.
        """
        scoped_filter = {
            "user_email": user_email,
            "owner_planner_id": owner_planner_id,
        }
        docs = await self.connections_collection.find(scoped_filter).to_list(
            length=None
        )
        if not docs:
            return {"disconnected": True, "message": "Calendar was not connected"}

        by_account: Dict[tuple[str, str], list[dict[str, Any]]] = {}
        for doc in docs:
            key = (
                str(doc.get("user_id") or ""),
                str(doc.get("aurinko_account_id") or ""),
            )
            by_account.setdefault(key, []).append(doc)

        for (_user_id, aurinko_account_id), account_docs in by_account.items():
            sample = account_docs[0]
            token = self._decrypt_token(sample.get("aurinko_access_token_encrypted"))
            # Each row carries its own per-calendar subscription. Unsubscribe
            # every row that has one — sharing-by-account is no longer the
            # subscription model.
            if token:
                for row in account_docs:
                    subscription_id = row.get("aurinko_subscription_id")
                    if not subscription_id:
                        continue
                    try:
                        await self.client.delete_subscription(
                            account_token=token,
                            subscription_id=str(subscription_id),
                        )
                    except Exception as exc:
                        logger.warning(
                            "Aurinko unsubscribe for calendar %s on account %s failed: %s",
                            row.get("aurinko_calendar_id"),
                            aurinko_account_id,
                            _redact_sensitive(exc),
                        )
                try:
                    await self.client.revoke_account(token)
                except Exception as exc:
                    logger.warning(
                        "Aurinko revoke for account %s failed: %s",
                        aurinko_account_id,
                        _redact_sensitive(exc),
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
                "$unset": {"calendar_connection_id": "", "calendar_id": ""},
            },
        )
        await self.connections_collection.delete_many(scoped_filter)
        for connection_id in connection_ids:
            await self.invalidate_connection_events_cache(connection_id)

        for (_user_id, aurinko_account_id), account_docs in by_account.items():
            sample = account_docs[0]
            await calendar_audit_service.log(
                action="calendar_connection_disconnected",
                message=f"Disconnected calendar account {sample.get('provider_account_email')}",
                owner_planner_email=sample.get("owner_planner_email"),
                actor_email=sample.get("user_email"),
                actor_role=None,
                metadata={
                    "connection_ids": [str(d["_id"]) for d in account_docs],
                    "provider": sample.get("provider"),
                    "provider_account_email": sample.get("provider_account_email"),
                    "aurinko_account_id": aurinko_account_id,
                    "calendars_disconnected": len(account_docs),
                    "revoked_aggregator_grant": True,
                },
            )
        return {"disconnected": True, "message": "Calendar disconnected"}

    # ----- event create/update/delete/get ---------------------------------

    def _coerce_datetime(self, value: Any, field_name: str) -> datetime:
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
        """Translate a canonical task into an Aurinko event body."""
        timezone_name = task.get("timezone") or settings.CALENDAR_DEFAULT_TIMEZONE
        start_date = self._coerce_datetime(task.get("start_date"), "start_date")
        end_date = self._coerce_datetime(
            task.get("end_date") or task.get("start_date"),
            "end_date",
        )
        body: dict[str, Any] = {
            "subject": task.get("title"),
            "description": task.get("description") or task.get("notes") or "",
        }
        if task.get("all_day"):
            body["when"] = {
                "type": "date",
                "start": start_date.strftime("%Y-%m-%d"),
                "end": (end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            }
        else:
            body["when"] = {
                "type": "datetime",
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "timeZone": timezone_name,
            }
        if task.get("conference_url"):
            body["location"] = {"displayName": task["conference_url"]}
        if attendee_emails:
            body["attendees"] = [{"emailAddress": email} for email in attendee_emails]
        return body

    async def _account_token_for_connection(
        self, connection_doc: dict[str, Any]
    ) -> Optional[str]:
        encrypted = connection_doc.get("aurinko_access_token_encrypted")
        return self._decrypt_token(encrypted)

    async def create_event_for_connection(
        self,
        connection_id: str,
        task: Dict[str, Any],
        attendee_emails: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        connection_doc = await self.get_connection_doc(connection_id)
        token = await self._account_token_for_connection(connection_doc)
        if not token:
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                classification={
                    "retryable": False,
                    "error_category": "credentials_unavailable",
                    "error_message": "Calendar credentials are unavailable for this connection",
                },
            )
        try:
            body = self._build_event_body(task, attendee_emails)
            event = await self.client.create_event(
                account_token=token,
                calendar_id=connection_doc["aurinko_calendar_id"],
                body=body,
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
                external_event_id=event.get("id") or event.get("eventId"),
                etag=event.get("etag") or event.get("changeKey"),
            )
        except Exception as exc:
            classification = self._classify_aurinko_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            logger.error(
                "Failed to create calendar event for connection %s: %s",
                connection_id,
                _redact_sensitive(exc),
            )
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                classification=classification,
            )

    async def update_event_for_connection(
        self,
        connection_id: str,
        external_event_id: str,
        task: Dict[str, Any],
        attendee_emails: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        connection_doc = await self.get_connection_doc(connection_id)
        token = await self._account_token_for_connection(connection_doc)
        if not token:
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                classification={
                    "retryable": False,
                    "error_category": "credentials_unavailable",
                    "error_message": "Calendar credentials are unavailable for this connection",
                },
            )
        try:
            body = self._build_event_body(task, attendee_emails)
            event = await self.client.update_event(
                account_token=token,
                calendar_id=connection_doc["aurinko_calendar_id"],
                external_event_id=external_event_id,
                body=body,
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
                etag=event.get("etag") or event.get("changeKey"),
            )
        except Exception as exc:
            classification = self._classify_aurinko_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            logger.error(
                "Failed to update calendar event %s: %s",
                external_event_id,
                _redact_sensitive(exc),
            )
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                classification=classification,
            )

    async def delete_event_for_connection(
        self,
        connection_id: str,
        external_event_id: str,
    ) -> dict[str, Any]:
        connection_doc = await self.get_connection_doc(connection_id)
        token = await self._account_token_for_connection(connection_doc)
        if not token:
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                classification={
                    "retryable": False,
                    "error_category": "credentials_unavailable",
                    "error_message": "Calendar credentials are unavailable for this connection",
                },
            )
        try:
            await self.client.delete_event(
                account_token=token,
                calendar_id=connection_doc["aurinko_calendar_id"],
                external_event_id=external_event_id,
            )
            await self.invalidate_connection_events_cache(connection_id)
            return self._build_provider_result(
                success=True,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
            )
        except Exception as exc:
            classification = self._classify_aurinko_exception(exc)
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
                "Failed to delete calendar event %s: %s",
                external_event_id,
                _redact_sensitive(exc),
            )
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                classification=classification,
            )

    async def get_event_for_connection(
        self,
        connection_id: str,
        external_event_id: str,
    ) -> dict[str, Any]:
        connection_doc = await self.get_connection_doc(connection_id)
        token = await self._account_token_for_connection(connection_doc)
        if not token:
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                classification={
                    "retryable": False,
                    "error_category": "credentials_unavailable",
                    "error_message": "Calendar credentials are unavailable for this connection",
                },
            )
        try:
            raw = await self.client.get_event(
                account_token=token,
                calendar_id=connection_doc["aurinko_calendar_id"],
                external_event_id=external_event_id,
            )
            normalized = _normalize_event_for_aggregation(
                raw,
                provider=connection_doc.get("provider", CalendarProvider.UNKNOWN.value),
            )
            return self._build_provider_result(
                success=True,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                etag=normalized.get("etag"),
                event=normalized,
            )
        except Exception as exc:
            classification = self._classify_aurinko_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            return self._build_provider_result(
                success=False,
                connection_doc=connection_doc,
                external_event_id=external_event_id,
                classification=classification,
            )

    async def fetch_external_events_for_connection(
        self,
        connection_id: str,
        *,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 200,
    ) -> List[Dict[str, Any]]:
        if not time_min:
            time_min = datetime.now(UTC)
        if not time_max:
            time_max = time_min + timedelta(days=30)

        connection_doc = await self.get_connection_doc(connection_id)
        cache_key = self._external_events_cache_key(
            connection_id=connection_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )
        cached_events = await cache.get(cache_key)
        if isinstance(cached_events, list):
            return [
                {**event, "_connection": self._serialize_connection(connection_doc)}
                for event in cached_events
            ]

        token = await self._account_token_for_connection(connection_doc)
        if not token:
            return []
        try:
            raw_events = await self.client.list_events(
                account_token=token,
                calendar_id=connection_doc["aurinko_calendar_id"],
                time_min=time_min,
                time_max=time_max,
                max_results=max_results,
            )
            events = [
                _normalize_event_for_aggregation(
                    raw,
                    provider=connection_doc.get(
                        "provider", CalendarProvider.UNKNOWN.value
                    ),
                )
                for raw in raw_events
            ]
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
            classification = self._classify_aurinko_exception(exc)
            await self._apply_provider_error_to_connection(
                connection_doc, classification
            )
            logger.error(
                "Failed to fetch calendar events for connection %s: %s",
                connection_id,
                _redact_sensitive(exc),
            )
            return []

    async def fetch_external_events(
        self,
        user_email: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Single-user wrapper used by the planner UI's events feed."""
        connection = await self.get_default_write_connection_for_user(user_email)
        if not connection:
            return []
        return await self.fetch_external_events_for_connection(
            str(connection["_id"]),
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )

    # ----- webhook subscription -------------------------------------------

    async def subscribe_webhook(self, connection_id: str, webhook_url: str) -> dict:
        connection_doc = await self.get_connection_doc(connection_id)
        token = await self._account_token_for_connection(connection_doc)
        if not token:
            raise HTTPException(
                status_code=400, detail="Connection has no Aurinko account token"
            )
        return await self.client.create_subscription(
            account_token=token, webhook_url=webhook_url
        )

    async def unsubscribe_webhook(
        self, connection_id: str, subscription_id: str
    ) -> None:
        connection_doc = await self.get_connection_doc(connection_id)
        token = await self._account_token_for_connection(connection_doc)
        if not token:
            return
        await self.client.delete_subscription(
            account_token=token, subscription_id=subscription_id
        )


# Singleton instance
calendar_provider_service = CalendarProviderService()

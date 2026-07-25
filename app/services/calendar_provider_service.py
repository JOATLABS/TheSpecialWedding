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
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx
import jwt
from bson import ObjectId
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pymongo import UpdateOne

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
_aurinko_http_client: httpx.AsyncClient | None = None


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
        account_token: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
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
            headers = self._account_headers(account_token)
            if extra_headers:
                headers.update(extra_headers)
            kwargs["headers"] = headers
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
    def resolve_service_type(cls, provider: str | None) -> str:
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
        service_type: str | None = None,
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

    async def list_tasklists(self, account_token: str) -> list[dict[str, Any]]:
        """List task lists for the connected account."""
        response = await self._request("GET", "/tasklists", account_token=account_token)
        response.raise_for_status()
        payload = response.json()
        return payload.get("records") or payload.get("tasklists") or []

    async def list_tasks(
        self,
        *,
        account_token: str,
        tasklist_id: str,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """List tasks from one Aurinko task list."""
        params: dict[str, Any] = {"pageSize": _AURINKO_LIST_PAGE_SIZE}
        if page_token:
            params["pageToken"] = page_token
        response = await self._request(
            "GET",
            f"/tasklists/{quote(tasklist_id, safe='')}/tasks",
            account_token=account_token,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def start_task_sync(
        self,
        *,
        account_token: str,
        tasklist_id: str,
        skip_completed_before_date: datetime | None = None,
        await_ready: bool | None = None,
    ) -> dict[str, Any]:
        """Provision Aurinko's task-list delta stream.

        Official Tasks API: ``POST /tasklists/{taskListId}/sync`` returns
        ``syncUpdatedToken`` / ``syncDeletedToken`` once ``ready`` is true.
        """
        params: dict[str, Any] = {}
        if skip_completed_before_date is not None:
            params["skipCompletedBeforeDate"] = skip_completed_before_date.isoformat()
        if await_ready is not None:
            params["awaitReady"] = str(bool(await_ready)).lower()
        response = await self._request(
            "POST",
            f"/tasklists/{quote(tasklist_id, safe='')}/sync",
            account_token=account_token,
            params=params or None,
        )
        response.raise_for_status()
        return response.json()

    async def list_task_sync_changes(
        self,
        *,
        account_token: str,
        tasklist_id: str,
        change_set: str,
        delta_token: str | None = None,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """Read one page from Aurinko's task ``updated`` or ``deleted`` stream."""
        if change_set not in {"updated", "deleted"}:
            raise ValueError("change_set must be 'updated' or 'deleted'")
        params: dict[str, Any] = {}
        if delta_token:
            params["deltaToken"] = delta_token
        if page_token:
            params["pageToken"] = page_token
        response = await self._request(
            "GET",
            f"/tasklists/{quote(tasklist_id, safe='')}/sync/{change_set}",
            account_token=account_token,
            params=params or None,
        )
        response.raise_for_status()
        return response.json()

    async def get_task(
        self,
        *,
        account_token: str,
        tasklist_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        response = await self._request(
            "GET",
            f"/tasklists/{quote(tasklist_id, safe='')}/tasks/{quote(task_id, safe='')}",
            account_token=account_token,
        )
        response.raise_for_status()
        return response.json()

    async def create_task(
        self,
        *,
        account_token: str,
        tasklist_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/tasklists/{quote(tasklist_id, safe='')}/tasks",
            account_token=account_token,
            json_body=body,
        )
        response.raise_for_status()
        return response.json()

    async def update_task(
        self,
        *,
        account_token: str,
        tasklist_id: str,
        task_id: str,
        body: dict[str, Any],
        etag: str | None = None,
    ) -> dict[str, Any]:
        response = await self._request(
            "PATCH",
            f"/tasklists/{quote(tasklist_id, safe='')}/tasks/{quote(task_id, safe='')}",
            account_token=account_token,
            json_body=body,
            extra_headers={"If-Match": etag} if etag else None,
        )
        response.raise_for_status()
        return response.json()

    async def delete_task(
        self,
        *,
        account_token: str,
        tasklist_id: str,
        task_id: str,
    ) -> None:
        response = await self._request(
            "DELETE",
            f"/tasklists/{quote(tasklist_id, safe='')}/tasks/{quote(task_id, safe='')}",
            account_token=account_token,
        )
        if response.status_code == 404:
            return
        response.raise_for_status()

    async def list_contact_books(self, account_token: str) -> list[dict[str, Any]]:
        """Return the default writable Contacts address book.

        Aurinko's public Contacts API exposes contact CRUD and sync endpoints,
        but not a documented contact-book or group enumeration endpoint. We
        therefore model the connected account's default contacts store as the
        selectable v1 book and keep planner grouping as an explicit keyword on
        mirrored contacts.
        """
        return [
            {
                "id": "default",
                "name": "Default contacts",
                "is_writable": True,
            }
        ]

    async def list_contacts(
        self,
        *,
        account_token: str,
        book_id: str | None = None,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if page_token:
            body["syncToken"] = page_token
        response = await self._request(
            "POST",
            "/contacts/sync/updated",
            account_token=account_token,
            json_body=body,
        )
        response.raise_for_status()
        return response.json()

    async def start_contacts_sync(
        self,
        *,
        account_token: str,
        await_ready: bool | None = None,
    ) -> dict[str, Any]:
        """Provision Aurinko's contacts delta stream.

        Official Contacts API: ``POST /contacts/sync`` returns
        ``syncUpdatedToken`` / ``syncDeletedToken`` once ``ready`` is true.
        """
        params: dict[str, Any] = {}
        if await_ready is not None:
            params["awaitReady"] = str(bool(await_ready)).lower()
        response = await self._request(
            "POST",
            "/contacts/sync",
            account_token=account_token,
            params=params or None,
        )
        response.raise_for_status()
        return response.json()

    async def list_contact_sync_changes(
        self,
        *,
        account_token: str,
        change_set: str,
        delta_token: str | None = None,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """Read one page from Aurinko's contacts ``updated`` or ``deleted`` stream."""
        if change_set not in {"updated", "deleted"}:
            raise ValueError("change_set must be 'updated' or 'deleted'")
        params: dict[str, Any] = {}
        if delta_token:
            params["deltaToken"] = delta_token
        if page_token:
            params["pageToken"] = page_token
        response = await self._request(
            "GET",
            f"/contacts/sync/{change_set}",
            account_token=account_token,
            params=params or None,
        )
        response.raise_for_status()
        return response.json()

    async def get_contact(
        self,
        *,
        account_token: str,
        contact_id: str,
    ) -> dict[str, Any]:
        response = await self._request(
            "GET",
            f"/contacts/{quote(contact_id, safe='')}",
            account_token=account_token,
        )
        response.raise_for_status()
        return response.json()

    async def create_contact(
        self,
        *,
        account_token: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            "/contacts",
            account_token=account_token,
            json_body=body,
        )
        response.raise_for_status()
        return response.json()

    async def update_contact(
        self,
        *,
        account_token: str,
        contact_id: str,
        body: dict[str, Any],
        etag: str | None = None,
    ) -> dict[str, Any]:
        response = await self._request(
            "PATCH",
            f"/contacts/{quote(contact_id, safe='')}",
            account_token=account_token,
            json_body=body,
            extra_headers={"If-Match": etag} if etag else None,
        )
        response.raise_for_status()
        return response.json()

    async def delete_contact(
        self,
        *,
        account_token: str,
        contact_id: str,
    ) -> None:
        response = await self._request(
            "DELETE",
            f"/contacts/{quote(contact_id, safe='')}",
            account_token=account_token,
        )
        if response.status_code == 404:
            return
        response.raise_for_status()

    async def create_group(self, account_token: str, name: str) -> dict[str, Any]:
        """Return a stable local sync label for mirrored contacts.

        The user-facing feature speaks in terms of a planner contacts group,
        but Aurinko's documented Contacts API does not expose a group-create
        endpoint. Persisting this deterministic id keeps the UX stable while
        avoiding an undocumented API guess.
        """
        normalized = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return {
            "id": f"local-keyword:{normalized or 'wedding-planner'}",
            "name": name,
        }

    async def create_subscription(
        self,
        *,
        account_token: str,
        calendar_id: str | None = None,
        resource: str | None = None,
        webhook_url: str,
    ) -> dict[str, Any]:
        """Subscribe to change notifications for one Aurinko resource.

        Aurinko subscriptions are scoped per-resource — there is no
        "all calendars on this account" subscription. The valid resource
        strings include ``/calendars/{calId}/events``,
        ``/tasklists/{taskListId}/tasks``, and ``/contacts``.
        """
        if resource is None:
            if not calendar_id:
                raise ValueError("create_subscription requires calendar_id or resource")
            resource = f"/calendars/{calendar_id}/events"
        body = {
            "resource": resource,
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
        duration_minutes: int | None = None,
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
        subject: str | None = None,
        notes: str | None = None,
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
        reason: str | None = None,
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
        self.task_sync_records_collection = mongo.get_task_sync_records_collection()
        self.contact_sync_records_collection = (
            mongo.get_contact_sync_records_collection()
        )
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

    def _webhook_url(self) -> str | None:
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
        status_code: int | None = None
        error_reason: str | None = None

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
        external_event_id: str | None = None,
        etag: str | None = None,
        classification: dict[str, Any] | None = None,
        event: dict[str, Any] | None = None,
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

    def _encrypt_token(self, token: str | None) -> str | None:
        if not token:
            return None
        return self._get_fernet().encrypt(token.encode()).decode()

    def _decrypt_token(self, token: str | None) -> str | None:
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
        redirect_to: str | None = None,
        service_type: str | None = None,
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "user_email": user_email,
            "owner_id": owner_id,
            "owner_email": owner_email,
            "redirect_to": redirect_to or "/admin/planner/calendar",
            "serviceType": service_type,
            "nonce": secrets.token_urlsafe(16),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        }
        return jwt.encode(payload, self._get_state_signing_key(), algorithm="HS256")

    def _decode_state(self, state: str) -> dict[str, Any]:
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

    def _configured_scopes(self) -> list[str]:
        return [s for s in re.split(r"[,\s]+", settings.AURINKO_SCOPES.strip()) if s]

    async def get_authorization_url(
        self,
        *,
        user_id: str,
        user_email: str,
        owner_id: str,
        owner_email: str,
        redirect_to: str | None = None,
        provider: str | None = None,
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
        service_type = AurinkoClient.resolve_service_type(provider)
        state = self._build_state(
            user_id=user_id,
            user_email=user_email,
            owner_id=owner_id,
            owner_email=owner_email,
            redirect_to=redirect_to,
            service_type=service_type,
        )
        # settings.AURINKO_SCOPES is a string (env values are strings). The
        # client's authorize_url expects list[str]; passing the raw string
        # would iterate characters instead of scope names. Split on
        # whitespace OR comma so whatever form the env uses ("a b" or "a,b")
        # parses correctly before authorize_url joins names with spaces.
        scope_list = self._configured_scopes()
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
        current_user_context: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
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
        # Three sources for provider identification, in order of trust:
        #   1. /v1/account.type      — Aurinko's own canonical view of the
        #                              connected account
        #   2. token_response.serviceType — set on the token-exchange leg
        #                                   for some providers
        #   3. state JWT serviceType — the value WE put into the OAuth
        #                              state at authorize-URL build time.
        #                              This is the always-available
        #                              fallback that keeps the connection
        #                              row from landing on "unknown" when
        #                              the first two are absent (which is
        #                              the dominant case for Aurinko's
        #                              current Google + Office365 flows).
        provider_label = self._map_aurinko_service_to_provider(
            account_info.get("type")
            or token_response.get("serviceType")
            or state_payload.get("serviceType")
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

        tasklists: list[dict[str, Any]] = []
        try:
            tasklists = await self.client.list_tasklists(account_token)
        except Exception as exc:
            logger.info(
                "Aurinko tasklists unavailable during OAuth callback; continuing "
                "calendar picker without tasklist rows: %s",
                _redact_sensitive(exc),
            )
        contact_books: list[dict[str, Any]] = []
        try:
            contact_books = await self.client.list_contact_books(account_token)
        except Exception as exc:
            logger.info(
                "Aurinko contact books unavailable during OAuth callback; continuing "
                "calendar picker without contact-book rows: %s",
                _redact_sensitive(exc),
            )

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

        picker_tasklists: list[dict[str, Any]] = []
        for entry in tasklists:
            tasklist_id = (
                entry.get("id") or entry.get("taskListId") or entry.get("tasklistId")
            )
            if not tasklist_id:
                continue
            picker_tasklists.append(
                {
                    "aurinko_tasklist_id": str(tasklist_id),
                    "name": entry.get("name") or entry.get("title") or str(tasklist_id),
                    "is_writable": bool(entry.get("is_writable", True)),
                    "suggested_default": bool(
                        entry.get("primary") or entry.get("default")
                    ),
                }
            )

        picker_contact_books: list[dict[str, Any]] = []
        for entry in contact_books:
            book_id = entry.get("id") or entry.get("bookId") or "default"
            picker_contact_books.append(
                {
                    "aurinko_contact_book_id": str(book_id),
                    "name": entry.get("name")
                    or entry.get("title")
                    or "Default contacts",
                    "is_writable": bool(entry.get("is_writable", True)),
                    "suggested_default": bool(
                        entry.get("primary")
                        or entry.get("default")
                        or book_id == "default"
                    ),
                }
            )

        expires_at = now + timedelta(minutes=30)
        # Mint a cryptographically random token for the picker handoff.
        # We DON'T expose the Mongo ObjectId because its embedded
        # timestamp + per-process random + counter give roughly 2^24
        # bits of unpredictability to an attacker who can guess the
        # rough creation time and host (OWASP ASVS v4 §6.3.1 — random
        # values that must be unguessable must come from a CSPRNG).
        # ``secrets.token_urlsafe(24)`` yields ~192 bits of CSPRNG
        # output base64url-encoded into a 32-char URL-safe string.
        draft_token = secrets.token_urlsafe(24)
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
                    "draft_token": draft_token,
                    # Full Aurinko-shape calendar payload for the commit step.
                    "calendars_payload": list(calendars),
                    "tasklists_payload": list(tasklists),
                    "contact_books_payload": list(contact_books),
                    "default_write_calendar_id": default_write_id,
                    "connection_scopes": self._configured_scopes(),
                    "redirect_to": state_payload.get("redirect_to"),
                    "expires_at": expires_at,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

        return {
            "connected": False,
            "needs_selection": True,
            # The frontend treats this as opaque. We hand back the
            # token, not the ObjectId — see security note above.
            "draft_id": draft_token,
            "account_email": provider_account_email,
            "account_name": provider_account_name,
            "provider": provider_label,
            "calendars": picker_calendars,
            "tasklists": picker_tasklists,
            "contact_books": picker_contact_books,
            "redirect_to": state_payload.get("redirect_to"),
            "message": (
                f"Found {len(picker_calendars)} calendar(s) on "
                f"{provider_account_email}. Pick which to sync."
            ),
        }

    async def get_active_picker_draft(
        self,
        *,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Return the planner's most recent unexpired picker draft, if any.

        Used by the callback page's "resume after refresh / back-button /
        network-drop" path: if the OAuth code was already redeemed (Aurinko
        returns 410 on the second redeem attempt) but the draft is still in
        Mongo, we can re-render the picker from the draft instead of
        showing a generic error. The draft id we return here is the same
        opaque CSPRNG token that ``handle_oauth_callback`` minted.
        """
        now = datetime.now(UTC)
        # We rely on the TTL index for cleanup, but ALSO filter on
        # expires_at here so a sweep-lag (Mongo TTL monitor is ~60 s)
        # can't surface a logically-expired draft.
        draft = await self.drafts_collection.find_one(
            {"user_id": user_id, "expires_at": {"$gt": now}},
            sort=[("updated_at", -1)],
        )
        if draft is None:
            return None

        # Rebuild the picker-row shape the frontend already knows. We do
        # NOT re-fetch the calendar list from Aurinko — we replay what
        # the original callback saw, which is what the user already
        # consented to.
        calendars = list(draft.get("calendars_payload") or [])
        tasklists = list(draft.get("tasklists_payload") or [])
        contact_books = list(draft.get("contact_books_payload") or [])
        default_write_id = draft.get("default_write_calendar_id")
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

        picker_tasklists: list[dict[str, Any]] = []
        for entry in tasklists:
            tasklist_id = (
                entry.get("id") or entry.get("taskListId") or entry.get("tasklistId")
            )
            if not tasklist_id:
                continue
            picker_tasklists.append(
                {
                    "aurinko_tasklist_id": str(tasklist_id),
                    "name": entry.get("name") or entry.get("title") or str(tasklist_id),
                    "is_writable": bool(entry.get("is_writable", True)),
                    "suggested_default": bool(
                        entry.get("primary") or entry.get("default")
                    ),
                }
            )

        picker_contact_books: list[dict[str, Any]] = []
        for entry in contact_books:
            book_id = entry.get("id") or entry.get("bookId") or "default"
            picker_contact_books.append(
                {
                    "aurinko_contact_book_id": str(book_id),
                    "name": entry.get("name")
                    or entry.get("title")
                    or "Default contacts",
                    "is_writable": bool(entry.get("is_writable", True)),
                    "suggested_default": bool(
                        entry.get("primary")
                        or entry.get("default")
                        or book_id == "default"
                    ),
                }
            )

        return {
            "connected": False,
            "needs_selection": True,
            "draft_id": str(draft.get("draft_token") or ""),
            "account_email": draft.get("provider_account_email"),
            "account_name": draft.get("provider_account_name"),
            "provider": draft.get("provider"),
            "calendars": picker_calendars,
            "tasklists": picker_tasklists,
            "contact_books": picker_contact_books,
            "redirect_to": draft.get("redirect_to"),
            "message": "Resumed your calendar selection.",
        }

    def _select_account_auxiliary_anchor_calendar_id(
        self,
        *,
        picked_ids: list[str],
        effective_default_write: str | None,
        calendars_by_id: dict[str, dict[str, Any]],
    ) -> str | None:
        """Choose the one row that owns account-scoped task/contact sync."""
        if effective_default_write and effective_default_write in picked_ids:
            return effective_default_write
        for calendar_id in picked_ids:
            if self._is_writable_calendar(calendars_by_id.get(calendar_id, {})):
                return calendar_id
        return picked_ids[0] if picked_ids else None

    def _select_existing_auxiliary_anchor_calendar_id(
        self,
        *,
        picked_ids: list[str],
        effective_default_write: str | None,
        existing_by_calendar: dict[str, dict[str, Any]],
        enabled_field: str,
    ) -> str | None:
        enabled_ids = [
            calendar_id
            for calendar_id in picked_ids
            if existing_by_calendar.get(calendar_id, {}).get(enabled_field)
        ]
        if not enabled_ids:
            return None
        if effective_default_write and effective_default_write in enabled_ids:
            return effective_default_write
        existing_default = next(
            (
                calendar_id
                for calendar_id in enabled_ids
                if existing_by_calendar[calendar_id].get("is_default_write_target")
            ),
            None,
        )
        return existing_default or enabled_ids[0]

    async def _delete_auxiliary_subscription(
        self,
        *,
        account_token: str,
        subscription_id: Any,
        label: str,
        aurinko_account_id: str,
    ) -> None:
        if not account_token or not subscription_id:
            return
        try:
            await self.client.delete_subscription(
                account_token=account_token,
                subscription_id=str(subscription_id),
            )
        except Exception as exc:
            logger.info(
                "Could not delete duplicate Aurinko %s subscription %s on "
                "account %s: %s",
                label,
                subscription_id,
                aurinko_account_id,
                _redact_sensitive(exc),
            )

    async def commit_calendar_selection(
        self,
        *,
        draft_id: str,
        user_id: str,
        picks: list[dict[str, Any]],
        task_picks: list[dict[str, Any]] | None = None,
        contact_picks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
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

        Optional ``task_picks`` / ``contact_picks`` select one tasklist or
        contacts book for the account. These are account-scoped resources in
        Aurinko, so v1 stores them on exactly one anchor connection row.

        Returns the same response shape the pre-Option-B
        ``handle_oauth_callback`` used to return, so the existing
        ``ProviderCallbackResponse`` model can carry it forward.

        Idempotency: if the same draft_token POSTs twice (network
        retry, double-submit), the second call finds the draft already
        drained and returns the same success shape derived from
        existing connection rows. Per IETF RFC 9110 §9.2.2 idempotency
        semantics and the active Idempotency-Key header draft.
        """
        if not draft_id or not isinstance(draft_id, str):
            raise HTTPException(status_code=400, detail="Missing draft id")

        # The draft id is an opaque CSPRNG token minted via
        # secrets.token_urlsafe in handle_oauth_callback. We do NOT
        # accept the Mongo ObjectId (insufficient entropy — see OWASP
        # ASVS v4 §6.3.1). The user_id filter is defense-in-depth so a
        # leaked token can't activate someone else's connection.
        draft = await self.drafts_collection.find_one(
            {"draft_token": draft_id, "user_id": user_id}
        )
        if draft is None:
            # Idempotency path: the draft is gone, which could mean (a)
            # never run, (b) TTL-expired, or (c) the FIRST commit
            # succeeded and this is a duplicate POST. Distinguish (c) by
            # checking for connection rows that match the planner's
            # picks — if they exist, this is a retry and we return the
            # same success shape so the UI doesn't error-toast a
            # successful run.
            retry_picked_ids = [
                str(pick.get("aurinko_calendar_id") or "").strip()
                for pick in picks or []
            ]
            retry_picked_ids = [cid for cid in retry_picked_ids if cid]
            if retry_picked_ids:
                already = await self.connections_collection.find(
                    {
                        "user_id": user_id,
                        "aurinko_calendar_id": {"$in": retry_picked_ids},
                    }
                ).to_list(length=None)
                if len(already) >= len(retry_picked_ids):
                    default_row = next(
                        (r for r in already if r.get("is_default_write_target")),
                        already[0] if already else None,
                    )
                    return {
                        "connected": True,
                        "calendar_id": (
                            default_row.get("aurinko_calendar_id")
                            if default_row
                            else None
                        ),
                        "connections_created": len(already),
                        "redirect_to": None,
                        "message": "Calendar selection already saved.",
                        "warning": None,
                    }
            raise HTTPException(
                status_code=404,
                detail=(
                    "Calendar selection draft not found or expired. Please "
                    "re-run the Connect calendar flow."
                ),
            )

        draft_oid = draft["_id"]
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
        tasklists = list(draft.get("tasklists_payload") or [])
        contact_books = list(draft.get("contact_books_payload") or [])
        draft_default_write = draft.get("default_write_calendar_id")
        connection_scopes = self._normalize_string_list(
            draft.get("connection_scopes") or self._configured_scopes()
        )

        # Index Aurinko's calendar payload by id so picks can join in.
        calendars_by_id: dict[str, dict[str, Any]] = {}
        for entry in calendars:
            cid = entry.get("id") or entry.get("calendarId")
            if cid:
                calendars_by_id[str(cid)] = entry

        tasklists_by_id: dict[str, dict[str, Any]] = {}
        for entry in tasklists:
            tid = entry.get("id") or entry.get("taskListId") or entry.get("tasklistId")
            if tid:
                tasklists_by_id[str(tid)] = entry

        contact_books_by_id: dict[str, dict[str, Any]] = {}
        for entry in contact_books:
            bid = entry.get("id") or entry.get("bookId") or "default"
            if bid:
                contact_books_by_id[str(bid)] = entry

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

        selected_tasklist_id: str | None = None
        selected_tasklist_name: str | None = None
        for pick in task_picks or []:
            tid = str(pick.get("aurinko_tasklist_id") or pick.get("tasklist_id") or "")
            tid = tid.strip()
            if not tid or tid not in tasklists_by_id:
                continue
            selected_tasklist_id = tid
            tasklist_entry = tasklists_by_id[tid]
            selected_tasklist_name = (
                tasklist_entry.get("name") or tasklist_entry.get("title") or tid
            )
            break

        selected_contact_book_id: str | None = None
        selected_contact_book_name: str | None = None
        for pick in contact_picks or []:
            bid = str(
                pick.get("aurinko_contact_book_id") or pick.get("contact_book_id") or ""
            ).strip()
            if not bid or bid not in contact_books_by_id:
                continue
            selected_contact_book_id = bid
            contact_book_entry = contact_books_by_id[bid]
            selected_contact_book_name = (
                contact_book_entry.get("name")
                or contact_book_entry.get("title")
                or "Default contacts"
            )
            break

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
            or (
                str(draft_default_write)
                if draft_default_write and str(draft_default_write) in picked_ids
                else None
            )
            or next(
                (
                    cid
                    for cid in picked_ids
                    if self._is_writable_calendar(calendars_by_id[cid])
                ),
                None,
            )
        )

        # P3#7 — batch the per-calendar upserts. Previous impl did one
        # find_one + one update_one per pick (N×2 round-trips). We now
        # do ONE find_many to load existing docs into a dict, then ONE
        # bulk_write for all upserts. Per MongoDB docs (Bulk Write
        # Operations) this cuts round-trips from 2N to 2 regardless of
        # pick count.
        existing_rows = await self.connections_collection.find(
            {
                "user_id": user_id,
                "aurinko_account_id": aurinko_account_id,
                "aurinko_calendar_id": {"$in": picked_ids},
            }
        ).to_list(length=None)
        existing_by_calendar: dict[str, dict[str, Any]] = {
            str(row.get("aurinko_calendar_id")): row for row in existing_rows
        }
        auxiliary_anchor_id = self._select_account_auxiliary_anchor_calendar_id(
            picked_ids=picked_ids,
            effective_default_write=effective_default_write,
            calendars_by_id=calendars_by_id,
        )
        existing_task_anchor_id = self._select_existing_auxiliary_anchor_calendar_id(
            picked_ids=picked_ids,
            effective_default_write=effective_default_write,
            existing_by_calendar=existing_by_calendar,
            enabled_field="task_sync_enabled",
        )
        existing_contact_anchor_id = self._select_existing_auxiliary_anchor_calendar_id(
            picked_ids=picked_ids,
            effective_default_write=effective_default_write,
            existing_by_calendar=existing_by_calendar,
            enabled_field="contact_sync_enabled",
        )
        task_anchor_id = (
            auxiliary_anchor_id
            if selected_tasklist_id is not None
            else existing_task_anchor_id
        )
        contact_anchor_id = (
            auxiliary_anchor_id
            if selected_contact_book_id is not None
            else existing_contact_anchor_id
        )

        seen_calendar_ids: list[str] = []
        disabled_task_connection_ids: list[str] = []
        disabled_contact_connection_ids: list[str] = []
        bulk_ops: list[UpdateOne] = []
        for calendar_id in picked_ids:
            entry = calendars_by_id[calendar_id]
            override = pick_overrides.get(calendar_id, {})
            seen_calendar_ids.append(calendar_id)
            is_writable = self._is_writable_calendar(entry)
            existing_doc = existing_by_calendar.get(calendar_id)
            existing_task_enabled = bool(
                existing_doc.get("task_sync_enabled", False)
                if existing_doc is not None
                else False
            )
            existing_contact_enabled = bool(
                existing_doc.get("contact_sync_enabled", False)
                if existing_doc is not None
                else False
            )
            task_sync_enabled = bool(task_anchor_id and calendar_id == task_anchor_id)
            contact_sync_enabled = bool(
                contact_anchor_id and calendar_id == contact_anchor_id
            )
            if task_sync_enabled:
                task_sync_tasklist_id = (
                    selected_tasklist_id
                    if selected_tasklist_id is not None
                    else (
                        existing_doc.get("task_sync_tasklist_id")
                        if existing_doc is not None
                        else None
                    )
                )
                task_sync_tasklist_name = (
                    selected_tasklist_name
                    if selected_tasklist_name is not None
                    else (
                        existing_doc.get("task_sync_tasklist_name")
                        if existing_doc is not None
                        else None
                    )
                )
            else:
                task_sync_tasklist_id = None
                task_sync_tasklist_name = None
            if contact_sync_enabled:
                contact_sync_book_id = (
                    selected_contact_book_id
                    if selected_contact_book_id is not None
                    else (
                        existing_doc.get("contact_sync_book_id")
                        if existing_doc is not None
                        else None
                    )
                )
                contact_sync_book_name = (
                    selected_contact_book_name
                    if selected_contact_book_name is not None
                    else (
                        existing_doc.get("contact_sync_book_name")
                        if existing_doc is not None
                        else None
                    )
                )
            else:
                contact_sync_book_id = None
                contact_sync_book_name = None
            if existing_doc is not None and not task_sync_enabled:
                await self._delete_auxiliary_subscription(
                    account_token=account_token,
                    subscription_id=existing_doc.get("task_sync_subscription_id"),
                    label="task",
                    aurinko_account_id=aurinko_account_id,
                )
                if existing_task_enabled:
                    disabled_task_connection_ids.append(str(existing_doc["_id"]))
            if existing_doc is not None and not contact_sync_enabled:
                await self._delete_auxiliary_subscription(
                    account_token=account_token,
                    subscription_id=existing_doc.get("contact_sync_subscription_id"),
                    label="contact",
                    aurinko_account_id=aurinko_account_id,
                )
                if existing_contact_enabled:
                    disabled_contact_connection_ids.append(str(existing_doc["_id"]))
            connection_query = {
                "user_id": user_id,
                "aurinko_account_id": aurinko_account_id,
                "aurinko_calendar_id": calendar_id,
            }
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
                "task_sync_enabled": task_sync_enabled,
                "task_sync_tasklist_id": task_sync_tasklist_id,
                "task_sync_tasklist_name": task_sync_tasklist_name,
                "task_sync_subscription_id": (
                    existing_doc.get("task_sync_subscription_id")
                    if existing_doc is not None and task_sync_enabled
                    else None
                ),
                "contact_sync_enabled": contact_sync_enabled,
                "contact_sync_book_id": contact_sync_book_id,
                "contact_sync_book_name": contact_sync_book_name,
                "contact_sync_subscription_id": (
                    existing_doc.get("contact_sync_subscription_id")
                    if existing_doc is not None and contact_sync_enabled
                    else None
                ),
                "contact_sync_group_id": (
                    existing_doc.get("contact_sync_group_id")
                    if existing_doc is not None and contact_sync_enabled
                    else None
                ),
                "contact_sync_group_name": (
                    existing_doc.get("contact_sync_group_name")
                    if existing_doc is not None and contact_sync_enabled
                    else None
                ),
                "connection_scopes": connection_scopes,
                "connection_status": CalendarConnectionStatus.ACTIVE.value,
                "last_error": None,
                "updated_at": now,
            }
            bulk_ops.append(
                UpdateOne(
                    connection_query,
                    {"$set": connection_doc, "$setOnInsert": {"created_at": now}},
                    upsert=True,
                )
            )

        if bulk_ops:
            await self.connections_collection.bulk_write(bulk_ops, ordered=False)
        if disabled_task_connection_ids:
            await self.task_sync_records_collection.update_many(
                {"connection_id": {"$in": disabled_task_connection_ids}},
                {
                    "$set": {
                        "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                        "last_error": "Task sync moved to account anchor connection",
                        "updated_at": now,
                    }
                },
            )
        if disabled_contact_connection_ids:
            await self.contact_sync_records_collection.update_many(
                {"connection_id": {"$in": disabled_contact_connection_ids}},
                {
                    "$set": {
                        "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                        "last_error": (
                            "Contact sync moved to account anchor connection"
                        ),
                        "updated_at": now,
                    }
                },
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
                stale_token = self._decrypt_token(
                    stale_row.get("aurinko_access_token_encrypted")
                )
                if not stale_token:
                    continue
                for stale_subscription_id in (
                    stale_row.get("aurinko_subscription_id"),
                    stale_row.get("task_sync_subscription_id"),
                    stale_row.get("contact_sync_subscription_id"),
                ):
                    if not stale_subscription_id:
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
                await self.task_sync_records_collection.update_many(
                    {"connection_id": {"$in": stale_connection_ids}},
                    {
                        "$set": {
                            "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                            "last_error": "Calendar removed from provider",
                            "updated_at": now,
                        }
                    },
                )
                await self.contact_sync_records_collection.update_many(
                    {"connection_id": {"$in": stale_connection_ids}},
                    {
                        "$set": {
                            "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                            "last_error": "Calendar removed from provider",
                            "updated_at": now,
                        }
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
        webhook_warning: str | None = None
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

                tasklist_id = row.get("task_sync_tasklist_id")
                if row.get("task_sync_enabled") and tasklist_id:
                    prior_task_subscription_id = row.get("task_sync_subscription_id")
                    if prior_task_subscription_id:
                        try:
                            await self.client.delete_subscription(
                                account_token=account_token,
                                subscription_id=str(prior_task_subscription_id),
                            )
                        except Exception as exc:
                            logger.info(
                                "Could not delete prior Aurinko task subscription %s "
                                "for tasklist %s on account %s: %s",
                                prior_task_subscription_id,
                                tasklist_id,
                                aurinko_account_id,
                                _redact_sensitive(exc),
                            )
                    try:
                        subscription = await self.client.create_subscription(
                            account_token=account_token,
                            resource=f"/tasklists/{tasklist_id}/tasks",
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
                                    "task_sync_subscription_id": subscription_id
                                    or None,
                                    "updated_at": now,
                                }
                            },
                        )
                    except Exception as exc:
                        webhook_failure_count += 1
                        logger.warning(
                            "Failed to register Aurinko task subscription for "
                            "tasklist %s on account %s: %s",
                            tasklist_id,
                            aurinko_account_id,
                            _redact_sensitive(exc),
                        )

                if row.get("contact_sync_enabled"):
                    prior_contact_subscription_id = row.get(
                        "contact_sync_subscription_id"
                    )
                    if prior_contact_subscription_id:
                        try:
                            await self.client.delete_subscription(
                                account_token=account_token,
                                subscription_id=str(prior_contact_subscription_id),
                            )
                        except Exception as exc:
                            logger.info(
                                "Could not delete prior Aurinko contact subscription "
                                "%s on account %s: %s",
                                prior_contact_subscription_id,
                                aurinko_account_id,
                                _redact_sensitive(exc),
                            )
                    try:
                        subscription = await self.client.create_subscription(
                            account_token=account_token,
                            resource="/contacts",
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
                                    "contact_sync_subscription_id": subscription_id
                                    or None,
                                    "updated_at": now,
                                }
                            },
                        )
                    except Exception as exc:
                        webhook_failure_count += 1
                        logger.warning(
                            "Failed to register Aurinko contacts subscription on "
                            "account %s: %s",
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
            return CalendarProvider.OFFICE365.value
        if normalized in {"exchange", "ews"}:
            # Aurinko's hosted-auth uses "EWS" (Exchange Web Services) on the
            # request side and may echo either form back from /am/accounts/me;
            # map to Exchange/EWS depending on which enum member exists.
            exchange_member = getattr(CalendarProvider, "EXCHANGE", None)
            if exchange_member is None:
                exchange_member = getattr(CalendarProvider, "EWS", None)
            if exchange_member is not None:
                return str(exchange_member.value)
            return CalendarProvider.UNKNOWN.value
        if normalized in {"icloud", "apple"}:
            return CalendarProvider.ICLOUD.value
        if normalized in {"zoho"}:
            zoho_member = getattr(CalendarProvider, "ZOHO", None)
            if zoho_member is not None:
                return str(zoho_member.value)
            return CalendarProvider.UNKNOWN.value
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
        current_user_id: str | None,
        include_all_owner_connections: bool,
    ) -> list[dict]:
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

    def _default_contact_group_name(self, connection_doc: dict[str, Any]) -> str:
        base = (
            connection_doc.get("provider_account_name")
            or connection_doc.get("owner_planner_email")
            or "Wedding planner"
        )
        return f"{base} (TheSpecialWedding)"

    async def _sync_auxiliary_subscription_state(
        self,
        connection_doc: dict[str, Any],
        set_doc: dict[str, Any],
    ) -> None:
        """Keep task/contact webhook subscriptions aligned with row settings."""
        connection_id = str(connection_doc["_id"])
        token = await self._account_token_for_connection(connection_doc)
        webhook_url = self._webhook_url()
        now = datetime.now(UTC)
        db_update: dict[str, Any] = {}

        old_task_enabled = bool(connection_doc.get("task_sync_enabled", False))
        new_task_enabled = bool(set_doc.get("task_sync_enabled", old_task_enabled))
        old_tasklist_id = connection_doc.get("task_sync_tasklist_id")
        new_tasklist_id = set_doc.get("task_sync_tasklist_id", old_tasklist_id)
        task_settings_changed = (
            "task_sync_enabled" in set_doc
            or "task_sync_tasklist_id" in set_doc
            or "task_sync_tasklist_name" in set_doc
        )
        if task_settings_changed:
            prior_subscription_id = connection_doc.get("task_sync_subscription_id")
            if (
                token
                and prior_subscription_id
                and (not new_task_enabled or new_tasklist_id != old_tasklist_id)
            ):
                try:
                    await self.client.delete_subscription(
                        account_token=token,
                        subscription_id=str(prior_subscription_id),
                    )
                except Exception as exc:
                    logger.warning(
                        "Aurinko task unsubscribe failed for connection %s: %s",
                        connection_id,
                        _redact_sensitive(exc),
                    )
                db_update["task_sync_subscription_id"] = None

            if not new_task_enabled:
                db_update.update(
                    {
                        "task_sync_tasklist_id": None,
                        "task_sync_tasklist_name": None,
                        "task_sync_subscription_id": None,
                    }
                )
                await self.task_sync_records_collection.update_many(
                    {"connection_id": connection_id},
                    {
                        "$set": {
                            "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                            "last_error": "Task sync disabled for connection",
                            "updated_at": now,
                        }
                    },
                )
            elif (
                webhook_url
                and token
                and new_tasklist_id
                and (not prior_subscription_id or new_tasklist_id != old_tasklist_id)
            ):
                try:
                    subscription = await self.client.create_subscription(
                        account_token=token,
                        resource=f"/tasklists/{new_tasklist_id}/tasks",
                        webhook_url=webhook_url,
                    )
                    db_update["task_sync_subscription_id"] = (
                        str(
                            subscription.get("id")
                            or subscription.get("subscriptionId")
                            or ""
                        )
                        or None
                    )
                except Exception as exc:
                    logger.warning(
                        "Aurinko task subscribe failed for connection %s: %s",
                        connection_id,
                        _redact_sensitive(exc),
                    )

        old_contact_enabled = bool(connection_doc.get("contact_sync_enabled", False))
        new_contact_enabled = bool(
            set_doc.get("contact_sync_enabled", old_contact_enabled)
        )
        contact_settings_changed = (
            "contact_sync_enabled" in set_doc
            or "contact_sync_book_id" in set_doc
            or "contact_sync_group_name" in set_doc
        )
        if contact_settings_changed:
            prior_subscription_id = connection_doc.get("contact_sync_subscription_id")
            if token and prior_subscription_id and not new_contact_enabled:
                try:
                    await self.client.delete_subscription(
                        account_token=token,
                        subscription_id=str(prior_subscription_id),
                    )
                except Exception as exc:
                    logger.warning(
                        "Aurinko contacts unsubscribe failed for connection %s: %s",
                        connection_id,
                        _redact_sensitive(exc),
                    )
                db_update["contact_sync_subscription_id"] = None

            if not new_contact_enabled:
                db_update.update(
                    {
                        "contact_sync_book_id": None,
                        "contact_sync_book_name": None,
                        "contact_sync_group_id": None,
                        "contact_sync_group_name": None,
                        "contact_sync_subscription_id": None,
                    }
                )
                await self.contact_sync_records_collection.update_many(
                    {"connection_id": connection_id},
                    {
                        "$set": {
                            "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                            "last_error": "Contact sync disabled for connection",
                            "updated_at": now,
                        }
                    },
                )
            else:
                group_name = (
                    set_doc.get("contact_sync_group_name")
                    or connection_doc.get("contact_sync_group_name")
                    or self._default_contact_group_name(connection_doc)
                )
                group = await self.client.create_group(token or "", group_name)
                db_update["contact_sync_group_id"] = group.get("id")
                db_update["contact_sync_group_name"] = group.get("name") or group_name
                if webhook_url and token and not prior_subscription_id:
                    try:
                        subscription = await self.client.create_subscription(
                            account_token=token,
                            resource="/contacts",
                            webhook_url=webhook_url,
                        )
                        db_update["contact_sync_subscription_id"] = (
                            str(
                                subscription.get("id")
                                or subscription.get("subscriptionId")
                                or ""
                            )
                            or None
                        )
                    except Exception as exc:
                        logger.warning(
                            "Aurinko contacts subscribe failed for connection %s: %s",
                            connection_id,
                            _redact_sensitive(exc),
                        )

        if db_update:
            db_update["updated_at"] = now
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]}, {"$set": db_update}
            )

    async def _disable_account_auxiliary_siblings(
        self,
        *,
        connection_doc: dict[str, Any],
        enabled_field: str,
        subscription_field: str,
        sync_records_collection: Any,
        sync_label: str,
        now: datetime,
    ) -> None:
        account_id = connection_doc.get("aurinko_account_id")
        if not account_id:
            return
        siblings = await self.connections_collection.find(
            {
                "user_id": connection_doc.get("user_id"),
                "aurinko_account_id": account_id,
                "_id": {"$ne": connection_doc["_id"]},
                enabled_field: True,
            }
        ).to_list(length=100)
        if not siblings:
            return
        for sibling in siblings:
            token = await self._account_token_for_connection(sibling)
            await self._delete_auxiliary_subscription(
                account_token=token or "",
                subscription_id=sibling.get(subscription_field),
                label=sync_label,
                aurinko_account_id=str(account_id),
            )
        sibling_ids = [row["_id"] for row in siblings]
        sibling_connection_ids = [str(row["_id"]) for row in siblings]
        clear_doc: dict[str, Any] = {
            enabled_field: False,
            subscription_field: None,
            "updated_at": now,
        }
        if sync_label == "task":
            clear_doc.update(
                {
                    "task_sync_tasklist_id": None,
                    "task_sync_tasklist_name": None,
                }
            )
        else:
            clear_doc.update(
                {
                    "contact_sync_book_id": None,
                    "contact_sync_book_name": None,
                    "contact_sync_group_id": None,
                    "contact_sync_group_name": None,
                }
            )
        await self.connections_collection.update_many(
            {"_id": {"$in": sibling_ids}},
            {"$set": clear_doc},
        )
        await sync_records_collection.update_many(
            {"connection_id": {"$in": sibling_connection_ids}},
            {
                "$set": {
                    "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                    "last_error": f"{sync_label.title()} sync moved to another connection",
                    "updated_at": now,
                }
            },
        )

    async def update_connection(
        self,
        connection_id: str,
        updates: dict[str, Any],
        *,
        actor_email: str | None = None,
        actor_role: str | None = None,
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
                "task_sync_enabled",
                "task_sync_tasklist_id",
                "task_sync_tasklist_name",
                "contact_sync_enabled",
                "contact_sync_book_id",
                "contact_sync_book_name",
                "contact_sync_group_id",
                "contact_sync_group_name",
                "connection_scopes",
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
        if "connection_scopes" in set_doc:
            set_doc["connection_scopes"] = self._normalize_string_list(
                set_doc["connection_scopes"]
            )
        if set_doc.get("task_sync_enabled") and not set_doc.get(
            "task_sync_tasklist_id", connection_doc.get("task_sync_tasklist_id")
        ):
            raise HTTPException(
                status_code=400,
                detail="Select a task list before enabling task sync",
            )
        if set_doc.get("contact_sync_enabled"):
            set_doc.setdefault(
                "contact_sync_book_id",
                connection_doc.get("contact_sync_book_id") or "default",
            )
            if not set_doc.get("contact_sync_group_name") and not connection_doc.get(
                "contact_sync_group_name"
            ):
                set_doc["contact_sync_group_name"] = self._default_contact_group_name(
                    connection_doc
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

        now = datetime.now(UTC)
        new_task_enabled = bool(
            set_doc.get(
                "task_sync_enabled", connection_doc.get("task_sync_enabled", False)
            )
        )
        new_contact_enabled = bool(
            set_doc.get(
                "contact_sync_enabled",
                connection_doc.get("contact_sync_enabled", False),
            )
        )
        if new_task_enabled and any(
            key in set_doc
            for key in (
                "task_sync_enabled",
                "task_sync_tasklist_id",
                "task_sync_tasklist_name",
            )
        ):
            await self._disable_account_auxiliary_siblings(
                connection_doc=connection_doc,
                enabled_field="task_sync_enabled",
                subscription_field="task_sync_subscription_id",
                sync_records_collection=self.task_sync_records_collection,
                sync_label="task",
                now=now,
            )
        if new_contact_enabled and any(
            key in set_doc
            for key in (
                "contact_sync_enabled",
                "contact_sync_book_id",
                "contact_sync_book_name",
                "contact_sync_group_name",
            )
        ):
            await self._disable_account_auxiliary_siblings(
                connection_doc=connection_doc,
                enabled_field="contact_sync_enabled",
                subscription_field="contact_sync_subscription_id",
                sync_records_collection=self.contact_sync_records_collection,
                sync_label="contact",
                now=now,
            )

        set_doc["updated_at"] = now
        await self.connections_collection.update_one(
            {"_id": connection_doc["_id"]}, {"$set": set_doc}
        )
        await self.invalidate_connection_events_cache(connection_id)

        await self._sync_auxiliary_subscription_state(connection_doc, set_doc)

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
        actor_email: str | None = None,
        actor_role: str | None = None,
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
        for field_name in (
            "task_sync_subscription_id",
            "contact_sync_subscription_id",
        ):
            auxiliary_subscription_id = connection_doc.get(field_name)
            if not token or not auxiliary_subscription_id:
                continue
            try:
                await self.client.delete_subscription(
                    account_token=token,
                    subscription_id=str(auxiliary_subscription_id),
                )
            except Exception as exc:
                logger.warning(
                    "Aurinko unsubscribe for %s on connection %s failed: %s",
                    field_name,
                    connection_id,
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
        await self.task_sync_records_collection.update_many(
            {"connection_id": connection_id},
            {
                "$set": {
                    "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                    "last_error": "Calendar connection disconnected",
                    "updated_at": now,
                }
            },
        )
        await self.contact_sync_records_collection.update_many(
            {"connection_id": connection_id},
            {
                "$set": {
                    "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                    "last_error": "Calendar connection disconnected",
                    "updated_at": now,
                }
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
    ) -> dict | None:
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

    async def get_connection_status(self, user_email: str) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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

        by_account: dict[tuple[str, str], list[dict[str, Any]]] = {}
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
                    for subscription_field in (
                        "aurinko_subscription_id",
                        "task_sync_subscription_id",
                        "contact_sync_subscription_id",
                    ):
                        subscription_id = row.get(subscription_field)
                        if not subscription_id:
                            continue
                        try:
                            await self.client.delete_subscription(
                                account_token=token,
                                subscription_id=str(subscription_id),
                            )
                        except Exception as exc:
                            logger.warning(
                                "Aurinko unsubscribe for %s on account %s failed: %s",
                                subscription_field,
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
        await self.task_sync_records_collection.update_many(
            {"connection_id": {"$in": connection_ids}},
            {
                "$set": {
                    "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                    "last_error": "Calendar connection disconnected",
                    "updated_at": now,
                }
            },
        )
        await self.contact_sync_records_collection.update_many(
            {"connection_id": {"$in": connection_ids}},
            {
                "$set": {
                    "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                    "last_error": "Calendar connection disconnected",
                    "updated_at": now,
                }
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
        task: dict[str, Any],
        attendee_emails: list[str] | None = None,
    ) -> dict:
        """Translate a canonical task into an Aurinko event body."""
        timezone_name = task.get("timezone") or getattr(
            settings, "GOOGLE_CALENDAR_DEFAULT_TIMEZONE", "UTC"
        )
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
    ) -> str | None:
        encrypted = connection_doc.get("aurinko_access_token_encrypted")
        return self._decrypt_token(encrypted)

    async def create_event_for_connection(
        self,
        connection_id: str,
        task: dict[str, Any],
        attendee_emails: list[str] | None = None,
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
        task: dict[str, Any],
        attendee_emails: list[str] | None = None,
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
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        max_results: int = 200,
    ) -> list[dict[str, Any]]:
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
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
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
            account_token=token,
            calendar_id=connection_doc["aurinko_calendar_id"],
            webhook_url=webhook_url,
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

"""Google Calendar OAuth, connection management, and event projection service."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
from bson import ObjectId
from cryptography.fernet import Fernet
from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.core.database import mongo
from app.models.calendar import VisibilityMode
from app.models.calendar_connection import CalendarConnectionStatus
from app.models.calendar_sync import CalendarSyncStatusValue

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """Handles Google Calendar OAuth, connection lifecycle, and event projection."""

    def __init__(self):
        self.tokens_collection = mongo.get_calendar_tokens_collection()
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_calendar_event_syncs_collection()
        self.tasks_collection = mongo.get_planner_tasks_collection()

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
        return (
            settings.GOOGLE_OAUTH_STATE_SIGNING_KEY
            or settings.SECRET_KEY
            or "dev-google-oauth-state-key"
        )

    def _get_fernet(self) -> Fernet:
        raw_key = settings.TOKEN_ENCRYPTION_KEY or settings.SECRET_KEY or "dev-token-key"
        derived_key = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())
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
            return jwt.decode(
                state,
                self._get_state_signing_key(),
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(status_code=400, detail="OAuth state has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status_code=400, detail="Invalid OAuth state") from exc

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

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
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
                raise HTTPException(status_code=403, detail="OAuth callback user mismatch")
            if expected_user_email and expected_user_email != state_payload.get("user_email"):
                raise HTTPException(status_code=403, detail="OAuth callback email mismatch")

        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

        try:
            flow.fetch_token(code=code)
        except Exception as exc:
            logger.error("Failed to fetch Google OAuth token: %s", exc)
            raise HTTPException(
                status_code=400, detail="Failed to complete Google authorization"
            ) from exc

        credentials = flow.credentials
        calendar_service = build("calendar", "v3", credentials=credentials)
        oauth_service = build("oauth2", "v2", credentials=credentials)

        try:
            account_info = oauth_service.userinfo().get().execute()
            provider_account_email = account_info.get("email") or state_payload["user_email"]
            provider_account_name = (
                account_info.get("name")
                or account_info.get("given_name")
                or provider_account_email
            )
        except Exception:
            provider_account_email = state_payload["user_email"]
            provider_account_name = provider_account_email

        calendars = []
        page_token = None
        while True:
            response = calendar_service.calendarList().list(pageToken=page_token).execute()
            calendars.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

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
                if entry.get("primary") and entry.get("accessRole") in {"owner", "writer"}
            ),
            None,
        )
        default_write_id = primary_writable_id or (writable_calendar_ids[0] if writable_calendar_ids else None)
        seen_calendar_ids: list[str] = []

        for entry in calendars:
            calendar_id = entry["id"]
            seen_calendar_ids.append(calendar_id)
            is_writable = entry.get("accessRole") in {"owner", "writer"}
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
                    is_writable and calendar_id == default_write_id
                ),
                "is_shared_in_team_view": False,
                "details_visibility": VisibilityMode.BUSY_ONLY.value,
                "sync_enabled": is_writable,
                "connection_status": CalendarConnectionStatus.ACTIVE.value,
                "access_token_encrypted": encrypted_access,
                "refresh_token_encrypted": encrypted_refresh,
                "token_expiry": credentials.expiry,
                "scope_version": ",".join(settings.GOOGLE_CALENDAR_SCOPES),
                "last_error": None,
                "updated_at": now,
            }
            await self.connections_collection.update_one(
                {
                    "user_id": user_id,
                    "provider_account_email": provider_account_email,
                    "calendar_id": calendar_id,
                },
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

        # Keep the legacy collection updated for smooth backward compatibility.
        await self.tokens_collection.update_one(
            {"user_email": user_email},
            {
                "$set": {
                    "user_email": user_email,
                    "access_token": encrypted_access,
                    "refresh_token": encrypted_refresh,
                    "token_expiry": credentials.expiry,
                    "calendar_id": default_write_id or "primary",
                    "sync_enabled": True,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
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
            "is_shared_in_team_view": doc.get("is_shared_in_team_view", False),
            "details_visibility": doc.get("details_visibility", VisibilityMode.BUSY_ONLY.value),
            "sync_enabled": doc.get("sync_enabled", False),
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
            raise HTTPException(status_code=400, detail="Invalid connection ID") from exc

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

    async def get_credentials_for_connection(self, connection_id: str) -> Optional[Credentials]:
        """Load decrypted credentials for a connection, refreshing if needed."""
        connection_doc = await self._get_connection_doc(connection_id)
        credentials = Credentials(
            token=self._decrypt_token(connection_doc.get("access_token_encrypted")),
            refresh_token=self._decrypt_token(
                connection_doc.get("refresh_token_encrypted")
            ),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
        )

        try:
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                await self._update_account_tokens(
                    connection_doc,
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    token_expiry=credentials.expiry,
                )
        except Exception as exc:
            logger.error("Failed to refresh Google credentials: %s", exc)
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "connection_status": CalendarConnectionStatus.ERROR.value,
                        "last_error": str(exc),
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
    ) -> dict:
        """Update mutable connection flags."""
        connection_doc = await self._get_connection_doc(connection_id)
        set_doc = {
            k: v
            for k, v in updates.items()
            if k
            in {
                "is_default_write_target",
                "is_shared_in_team_view",
                "details_visibility",
                "sync_enabled",
            }
            and v is not None
        }
        if not set_doc:
            return self._serialize_connection(connection_doc)

        if set_doc.get("is_default_write_target"):
            await self.connections_collection.update_many(
                {
                    "user_id": connection_doc["user_id"],
                    "provider_account_email": connection_doc["provider_account_email"],
                    "is_writable": True,
                },
                {"$set": {"is_default_write_target": False}},
            )

        set_doc["updated_at"] = datetime.now(UTC)
        await self.connections_collection.update_one(
            {"_id": connection_doc["_id"]},
            {"$set": set_doc},
        )
        return self._serialize_connection(await self._get_connection_doc(connection_id))

    async def healthcheck_connection(self, connection_id: str) -> dict:
        """Validate a connection against Google and persist health state."""
        connection_doc = await self._get_connection_doc(connection_id)
        now = datetime.now(UTC)
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return self._serialize_connection(await self._get_connection_doc(connection_id))

        try:
            service = build("calendar", "v3", credentials=credentials)
            service.calendarList().get(calendarId=connection_doc["calendar_id"]).execute()
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
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "connection_status": CalendarConnectionStatus.ERROR.value,
                        "last_error": str(exc),
                        "last_healthcheck_at": now,
                        "updated_at": now,
                    }
                },
            )

        return self._serialize_connection(await self._get_connection_doc(connection_id))

    async def _revoke_provider_account(self, connection_doc: dict) -> None:
        """Revoke Google access for a provider account."""
        token = self._decrypt_token(connection_doc.get("access_token_encrypted"))
        if not token:
            return
        try:
            import requests

            requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                timeout=10,
            )
        except Exception as exc:
            logger.warning("Failed to revoke Google token: %s", exc)

    async def disconnect_connection(self, connection_id: str) -> dict:
        """Delete one connection row, revoking access if it is the last row for that account."""
        connection_doc = await self._get_connection_doc(connection_id)
        account_query = {
            "user_id": connection_doc["user_id"],
            "provider_account_email": connection_doc["provider_account_email"],
        }
        sibling_count = await self.connections_collection.count_documents(account_query)
        await self.connections_collection.delete_one({"_id": connection_doc["_id"]})

        if sibling_count <= 1:
            await self._revoke_provider_account(connection_doc)
            await self.tokens_collection.delete_many({"user_email": connection_doc["user_email"]})

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
                    {"$set": {"is_default_write_target": True, "updated_at": datetime.now(UTC)}},
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
        """Compatibility helper to disconnect all connections for a user."""
        docs = await self.connections_collection.find({"user_email": user_email}).to_list(length=200)
        for doc in docs:
            await self.disconnect_connection(str(doc["_id"]))

        await self.tasks_collection.update_many(
            {"planner_email": user_email},
            {
                "$set": {
                    "synced_to_google": False,
                    "google_event_id": None,
                    "last_google_sync": None,
                    "updated_at": datetime.now(UTC),
                }
            },
        )
        return {"disconnected": True, "message": "Google Calendar disconnected"}

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
        timezone_name = task.get("timezone") or settings.GOOGLE_CALENDAR_DEFAULT_TIMEZONE
        start_date = task.get("start_date")
        end_date = task.get("end_date") or start_date

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

        color_map = {
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
        color = task.get("color")
        if color and color.lower() in color_map:
            event_body["colorId"] = color_map[color.lower()]

        return event_body

    async def create_google_event_for_connection(
        self,
        connection_id: str,
        task: Dict[str, Any],
        attendee_emails: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """Create an event on a specific Google calendar connection."""
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return None

        connection_doc = await self._get_connection_doc(connection_id)
        try:
            service = build("calendar", "v3", credentials=credentials)
            event = (
                service.events()
                .insert(
                    calendarId=connection_doc["calendar_id"],
                    body=self._build_event_body(task, attendee_emails),
                )
                .execute()
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
            return {
                "id": event.get("id"),
                "etag": event.get("etag"),
                "calendar_id": connection_doc["calendar_id"],
            }
        except Exception as exc:
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {
                    "$set": {
                        "connection_status": CalendarConnectionStatus.ERROR.value,
                        "last_error": str(exc),
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            logger.error("Failed to create Google event for connection %s: %s", connection_id, exc)
            return None

    async def update_google_event_for_connection(
        self,
        connection_id: str,
        external_event_id: str,
        task: Dict[str, Any],
        attendee_emails: Optional[list[str]] = None,
    ) -> bool:
        """Update an existing event on a specific Google calendar connection."""
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return False

        connection_doc = await self._get_connection_doc(connection_id)
        try:
            service = build("calendar", "v3", credentials=credentials)
            service.events().update(
                calendarId=connection_doc["calendar_id"],
                eventId=external_event_id,
                body=self._build_event_body(task, attendee_emails),
            ).execute()
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {"$set": {"last_sync_at": datetime.now(UTC), "last_error": None, "updated_at": datetime.now(UTC)}},
            )
            return True
        except HttpError as exc:
            logger.error("Failed to update Google event %s: %s", external_event_id, exc)
            return False

    async def delete_google_event_for_connection(
        self,
        connection_id: str,
        external_event_id: str,
    ) -> bool:
        """Delete an existing event from a specific Google calendar connection."""
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return False

        connection_doc = await self._get_connection_doc(connection_id)
        try:
            service = build("calendar", "v3", credentials=credentials)
            service.events().delete(
                calendarId=connection_doc["calendar_id"],
                eventId=external_event_id,
            ).execute()
            return True
        except HttpError as exc:
            if exc.resp.status == 404:
                return True
            logger.error("Failed to delete Google event %s: %s", external_event_id, exc)
            return False

    async def fetch_google_events_for_connection(
        self,
        connection_id: str,
        *,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 200,
    ) -> List[Dict[str, Any]]:
        """Fetch events from a specific connection for shared-calendar aggregation."""
        credentials = await self.get_credentials_for_connection(connection_id)
        if not credentials:
            return []

        connection_doc = await self._get_connection_doc(connection_id)
        if not time_min:
            time_min = datetime.now(UTC)
        if not time_max:
            time_max = time_min + timedelta(days=30)

        try:
            service = build("calendar", "v3", credentials=credentials)
            events_result = (
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
            events = events_result.get("items", [])
            await self.connections_collection.update_one(
                {"_id": connection_doc["_id"]},
                {"$set": {"last_sync_at": datetime.now(UTC), "updated_at": datetime.now(UTC)}},
            )
            for event in events:
                event["_connection"] = self._serialize_connection(connection_doc)
            return events
        except Exception as exc:
            logger.error("Failed to fetch Google events for connection %s: %s", connection_id, exc)
            return []

    async def create_google_event(
        self,
        user_email: str,
        task: Dict[str, Any],
    ) -> Optional[str]:
        """Legacy wrapper for single-user task sync."""
        connection = await self.get_default_write_connection_for_user(user_email)
        if not connection:
            return None
        result = await self.create_google_event_for_connection(str(connection["_id"]), task)
        return result.get("id") if result else None

    async def update_google_event(
        self,
        user_email: str,
        google_event_id: str,
        task: Dict[str, Any],
    ) -> bool:
        """Legacy wrapper for single-user task sync updates."""
        connection = await self.get_default_write_connection_for_user(user_email)
        if not connection:
            return False
        return await self.update_google_event_for_connection(
            str(connection["_id"]), google_event_id, task
        )

    async def delete_google_event(
        self,
        user_email: str,
        google_event_id: str,
    ) -> bool:
        """Legacy wrapper for single-user task sync deletions."""
        connection = await self.get_default_write_connection_for_user(user_email)
        if not connection:
            return False
        return await self.delete_google_event_for_connection(
            str(connection["_id"]), google_event_id
        )

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

    async def sync_task_to_google(
        self,
        user_email: str,
        task_id: str,
    ) -> bool:
        """Legacy wrapper to sync one canonical planner task using the user's default connection."""
        try:
            task_oid = ObjectId(task_id)
        except Exception:
            return False

        task = await self.tasks_collection.find_one({"_id": task_oid})
        if not task:
            return False

        if task.get("google_event_id"):
            return await self.update_google_event(
                user_email,
                task["google_event_id"],
                task,
            )

        google_event_id = await self.create_google_event(user_email, task)
        if not google_event_id:
            return False

        await self.tasks_collection.update_one(
            {"_id": task_oid},
            {
                "$set": {
                    "google_event_id": google_event_id,
                    "synced_to_google": True,
                    "last_google_sync": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                }
            },
        )
        return True


# Singleton instance
google_calendar_service = GoogleCalendarService()

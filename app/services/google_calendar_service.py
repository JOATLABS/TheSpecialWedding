"""Google Calendar OAuth and sync service for wedding planners."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, List

from bson import ObjectId
from fastapi import HTTPException
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.core.database import mongo

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """Handles Google Calendar OAuth flow and event synchronization."""

    def __init__(self):
        self.tokens_collection = mongo.get_calendar_tokens_collection()
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

    def get_authorization_url(self, user_email: str) -> str:
        """Generate OAuth authorization URL for user consent.

        Args:
            user_email: The planner's email for state tracking

        Returns:
            Authorization URL to redirect user to Google consent screen
        """
        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

        # Include email in state for callback verification
        auth_url, state = flow.authorization_url(
            access_type="offline",  # Request refresh token
            include_granted_scopes="true",
            prompt="consent",  # Force consent to get refresh token
            state=user_email,  # Pass email in state for callback
        )

        logger.info(f"Generated OAuth URL for user: {user_email}")
        return auth_url

    async def handle_oauth_callback(
        self,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens and store them.

        Args:
            code: Authorization code from Google callback
            state: State parameter containing user email

        Returns:
            Dict with connection status and calendar info
        """
        user_email = state

        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

        try:
            flow.fetch_token(code=code)
        except Exception as e:
            logger.error(f"Failed to fetch token for {user_email}: {str(e)}")
            raise HTTPException(
                status_code=400, detail="Failed to complete Google authorization"
            )

        credentials = flow.credentials

        # Store tokens in database
        token_data = {
            "user_email": user_email,
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_expiry": credentials.expiry,
            "calendar_id": "primary",
            "sync_enabled": True,
            "last_sync_at": None,
            "updated_at": datetime.now(UTC),
        }

        # Upsert: update if exists, insert if not
        await self.tokens_collection.update_one(
            {"user_email": user_email},
            {
                "$set": token_data,
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )

        logger.info(f"Stored calendar tokens for user: {user_email}")

        return {
            "connected": True,
            "calendar_id": "primary",
            "message": "Successfully connected to Google Calendar",
        }

    async def get_credentials(self, user_email: str) -> Optional[Credentials]:
        """Get valid credentials for a user, refreshing if needed.

        Args:
            user_email: The planner's email

        Returns:
            Google Credentials object or None if not connected
        """
        token_doc = await self.tokens_collection.find_one({"user_email": user_email})
        if not token_doc:
            return None

        credentials = Credentials(
            token=token_doc.get("access_token"),
            refresh_token=token_doc.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
        )

        # Check if token is expired and refresh if needed
        if credentials.expired and credentials.refresh_token:
            try:
                from google.auth.transport.requests import Request

                credentials.refresh(Request())

                # Update stored tokens
                await self.tokens_collection.update_one(
                    {"user_email": user_email},
                    {
                        "$set": {
                            "access_token": credentials.token,
                            "token_expiry": credentials.expiry,
                            "updated_at": datetime.now(UTC),
                        }
                    },
                )
                logger.info(f"Refreshed tokens for user: {user_email}")
            except Exception as e:
                logger.error(f"Failed to refresh token for {user_email}: {str(e)}")
                return None

        return credentials

    async def get_connection_status(self, user_email: str) -> Dict[str, Any]:
        """Check if user has connected Google Calendar.

        Args:
            user_email: The planner's email

        Returns:
            Connection status including calendar ID and sync info
        """
        token_doc = await self.tokens_collection.find_one({"user_email": user_email})

        if not token_doc:
            return {
                "connected": False,
                "calendar_id": None,
                "last_sync": None,
                "sync_enabled": False,
                "events_synced": 0,
            }

        # Count synced events
        synced_count = await self.tasks_collection.count_documents(
            {
                "planner_email": user_email,
                "synced_to_google": True,
            }
        )

        return {
            "connected": True,
            "calendar_id": token_doc.get("calendar_id", "primary"),
            "last_sync": token_doc.get("last_sync_at"),
            "sync_enabled": token_doc.get("sync_enabled", True),
            "events_synced": synced_count,
        }

    async def disconnect(self, user_email: str) -> Dict[str, Any]:
        """Disconnect Google Calendar for a user.

        Args:
            user_email: The planner's email

        Returns:
            Disconnection status
        """
        await self.tokens_collection.delete_one({"user_email": user_email})

        # Clear sync flags from tasks but keep the tasks
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

        logger.info(f"Disconnected Google Calendar for user: {user_email}")

        return {
            "disconnected": True,
            "message": "Google Calendar disconnected successfully",
        }

    async def create_google_event(
        self,
        user_email: str,
        task: Dict[str, Any],
    ) -> Optional[str]:
        """Create an event in Google Calendar.

        Args:
            user_email: The planner's email
            task: Task data to create as calendar event

        Returns:
            Google Calendar event ID or None if failed
        """
        credentials = await self.get_credentials(user_email)
        if not credentials:
            logger.warning(f"No credentials for {user_email}, skipping Google sync")
            return None

        try:
            service = build("calendar", "v3", credentials=credentials)

            # Build event body
            event_body = {
                "summary": task.get("title"),
                "description": task.get("description") or task.get("notes") or "",
            }

            start_date = task.get("start_date")
            end_date = task.get("end_date") or start_date

            if task.get("all_day"):
                # All-day events use date format
                if isinstance(start_date, datetime):
                    event_body["start"] = {"date": start_date.strftime("%Y-%m-%d")}
                    event_body["end"] = {
                        "date": (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
                    }
                else:
                    event_body["start"] = {"date": str(start_date)[:10]}
                    event_body["end"] = {"date": str(end_date)[:10]}
            else:
                # Timed events use dateTime format
                if isinstance(start_date, datetime):
                    event_body["start"] = {
                        "dateTime": start_date.isoformat(),
                        "timeZone": "UTC",
                    }
                    event_body["end"] = {
                        "dateTime": end_date.isoformat(),
                        "timeZone": "UTC",
                    }
                else:
                    event_body["start"] = {
                        "dateTime": str(start_date),
                        "timeZone": "UTC",
                    }
                    event_body["end"] = {"dateTime": str(end_date), "timeZone": "UTC"}

            # Add reminders if specified
            if task.get("reminder_minutes"):
                event_body["reminders"] = {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": task["reminder_minutes"]},
                    ],
                }

            # Add recurrence if specified
            if task.get("is_recurring") and task.get("recurrence_rule"):
                event_body["recurrence"] = [f"RRULE:{task['recurrence_rule']}"]

            # Add color if specified (Google uses colorId 1-11)
            color_map = {
                "#a4bdfc": "1",  # Lavender
                "#7ae7bf": "2",  # Sage
                "#dbadff": "3",  # Grape
                "#ff887c": "4",  # Flamingo
                "#fbd75b": "5",  # Banana
                "#ffb878": "6",  # Tangerine
                "#46d6db": "7",  # Peacock
                "#e1e1e1": "8",  # Graphite
                "#5484ed": "9",  # Blueberry
                "#51b749": "10",  # Basil
                "#dc2127": "11",  # Tomato
            }
            if task.get("color") and task["color"].lower() in color_map:
                event_body["colorId"] = color_map[task["color"].lower()]

            # Get calendar ID from stored tokens
            token_doc = await self.tokens_collection.find_one(
                {"user_email": user_email}
            )
            calendar_id = (
                token_doc.get("calendar_id", "primary") if token_doc else "primary"
            )

            event = (
                service.events()
                .insert(
                    calendarId=calendar_id,
                    body=event_body,
                )
                .execute()
            )

            logger.info(f"Created Google event {event['id']} for user {user_email}")
            return event.get("id")

        except HttpError as e:
            logger.error(f"Google Calendar API error for {user_email}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Failed to create Google event for {user_email}: {str(e)}")
            return None

    async def update_google_event(
        self,
        user_email: str,
        google_event_id: str,
        task: Dict[str, Any],
    ) -> bool:
        """Update an existing event in Google Calendar.

        Args:
            user_email: The planner's email
            google_event_id: The Google Calendar event ID
            task: Updated task data

        Returns:
            True if update succeeded, False otherwise
        """
        credentials = await self.get_credentials(user_email)
        if not credentials:
            return False

        try:
            service = build("calendar", "v3", credentials=credentials)

            token_doc = await self.tokens_collection.find_one(
                {"user_email": user_email}
            )
            calendar_id = (
                token_doc.get("calendar_id", "primary") if token_doc else "primary"
            )

            # Get existing event first
            existing = (
                service.events()
                .get(
                    calendarId=calendar_id,
                    eventId=google_event_id,
                )
                .execute()
            )

            # Update fields
            if task.get("title"):
                existing["summary"] = task["title"]
            if task.get("description") is not None:
                existing["description"] = task["description"]

            # Update dates if provided
            start_date = task.get("start_date")
            end_date = task.get("end_date")
            if start_date:
                if task.get("all_day"):
                    existing["start"] = {
                        "date": start_date.strftime("%Y-%m-%d")
                        if isinstance(start_date, datetime)
                        else str(start_date)[:10]
                    }
                    if end_date:
                        existing["end"] = {
                            "date": end_date.strftime("%Y-%m-%d")
                            if isinstance(end_date, datetime)
                            else str(end_date)[:10]
                        }
                else:
                    existing["start"] = {
                        "dateTime": start_date.isoformat()
                        if isinstance(start_date, datetime)
                        else str(start_date),
                        "timeZone": "UTC",
                    }
                    if end_date:
                        existing["end"] = {
                            "dateTime": end_date.isoformat()
                            if isinstance(end_date, datetime)
                            else str(end_date),
                            "timeZone": "UTC",
                        }

            service.events().update(
                calendarId=calendar_id,
                eventId=google_event_id,
                body=existing,
            ).execute()

            logger.info(f"Updated Google event {google_event_id} for user {user_email}")
            return True

        except HttpError as e:
            logger.error(f"Failed to update Google event {google_event_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error updating Google event: {str(e)}")
            return False

    async def delete_google_event(
        self,
        user_email: str,
        google_event_id: str,
    ) -> bool:
        """Delete an event from Google Calendar.

        Args:
            user_email: The planner's email
            google_event_id: The Google Calendar event ID

        Returns:
            True if deletion succeeded, False otherwise
        """
        credentials = await self.get_credentials(user_email)
        if not credentials:
            return False

        try:
            service = build("calendar", "v3", credentials=credentials)

            token_doc = await self.tokens_collection.find_one(
                {"user_email": user_email}
            )
            calendar_id = (
                token_doc.get("calendar_id", "primary") if token_doc else "primary"
            )

            service.events().delete(
                calendarId=calendar_id,
                eventId=google_event_id,
            ).execute()

            logger.info(f"Deleted Google event {google_event_id} for user {user_email}")
            return True

        except HttpError as e:
            if e.resp.status == 404:
                # Event already deleted, that's fine
                return True
            logger.error(f"Failed to delete Google event {google_event_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error deleting Google event: {str(e)}")
            return False

    async def fetch_google_events(
        self,
        user_email: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch events from Google Calendar.

        Args:
            user_email: The planner's email
            time_min: Start of time range (defaults to now)
            time_max: End of time range (defaults to 1 year from now)
            max_results: Maximum number of events to fetch

        Returns:
            List of Google Calendar events
        """
        credentials = await self.get_credentials(user_email)
        if not credentials:
            return []

        try:
            service = build("calendar", "v3", credentials=credentials)

            token_doc = await self.tokens_collection.find_one(
                {"user_email": user_email}
            )
            calendar_id = (
                token_doc.get("calendar_id", "primary") if token_doc else "primary"
            )

            if not time_min:
                time_min = datetime.now(UTC)
            if not time_max:
                time_max = time_min + timedelta(days=365)

            events_result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])

            # Update last sync timestamp
            await self.tokens_collection.update_one(
                {"user_email": user_email},
                {"$set": {"last_sync_at": datetime.now(UTC)}},
            )

            logger.info(
                f"Fetched {len(events)} events from Google Calendar for {user_email}"
            )
            return events

        except HttpError as e:
            logger.error(f"Failed to fetch Google events for {user_email}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error fetching Google events: {str(e)}")
            return []

    async def sync_task_to_google(
        self,
        user_email: str,
        task_id: str,
    ) -> bool:
        """Sync a specific task to Google Calendar.

        Args:
            user_email: The planner's email
            task_id: The local task ID to sync

        Returns:
            True if sync succeeded, False otherwise
        """
        try:
            task_oid = ObjectId(task_id)
        except Exception:
            return False

        task = await self.tasks_collection.find_one({"_id": task_oid})
        if not task:
            return False

        if task.get("google_event_id"):
            # Update existing event
            success = await self.update_google_event(
                user_email,
                task["google_event_id"],
                task,
            )
        else:
            # Create new event
            google_event_id = await self.create_google_event(user_email, task)
            if google_event_id:
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
                success = True
            else:
                success = False

        return success


# Singleton instance
google_calendar_service = GoogleCalendarService()

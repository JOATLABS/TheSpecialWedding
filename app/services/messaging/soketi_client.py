"""Soketi (Pusher-compatible) client for real-time messaging events.

Soketi is a self-hosted Pusher replacement that handles WebSocket connections
securely. This module provides a server-side client to trigger events.

Security Note: The server triggers events to Soketi, which then broadcasts
to authenticated clients. We don't implement WebSockets directly - Soketi
handles all socket security (auth, reconnection, rate limiting, etc.).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional

import httpx

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class SoketiClient:
    """HTTP client for triggering Soketi events.

    Uses the Pusher HTTP API protocol which Soketi implements.
    """

    def __init__(self):
        settings = get_settings()
        config = settings.get_soketi_config()

        self._app_id = config["app_id"]
        self._key = config["key"]
        self._secret = config["secret"]
        self._host = config["host"]
        self._port = config["port"]
        self._ssl = config["ssl"]
        self._enabled = settings.is_soketi_configured()

        protocol = "https" if self._ssl else "http"
        self._base_url = f"{protocol}://{self._host}:{self._port}"

    def _generate_signature(
        self,
        method: str,
        path: str,
        params: Dict[str, str],
        body: Optional[str] = None,
    ) -> str:
        """Generate HMAC signature for Pusher API authentication."""
        # Sort parameters and create query string
        sorted_params = "&".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )

        # Build string to sign
        string_to_sign = f"{method}\n{path}\n{sorted_params}"

        if body:
            body_md5 = hashlib.md5(body.encode()).hexdigest()
            string_to_sign = f"{method}\n{path}\n{sorted_params}\n{body_md5}"

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self._secret.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()

        return signature

    async def trigger(
        self,
        channel: str,
        event: str,
        data: Dict[str, Any],
        socket_id: Optional[str] = None,
    ) -> bool:
        """Trigger an event on a channel.

        Args:
            channel: The channel name (e.g., "private-conversation-123")
            event: The event name (e.g., "new-message")
            data: The event payload
            socket_id: Optional socket ID to exclude from broadcast

        Returns:
            True if the event was triggered successfully
        """
        if not self._enabled:
            logger.debug("Soketi not enabled, skipping event trigger")
            return False

        path = f"/apps/{self._app_id}/events"

        body_dict: Dict[str, Any] = {
            "name": event,
            "channel": channel,
            "data": json.dumps(data),
        }

        if socket_id:
            body_dict["socket_id"] = socket_id

        body = json.dumps(body_dict)

        # Auth parameters
        auth_timestamp = str(int(time.time()))
        auth_version = "1.0"

        params = {
            "auth_key": self._key,
            "auth_timestamp": auth_timestamp,
            "auth_version": auth_version,
            "body_md5": hashlib.md5(body.encode()).hexdigest(),
        }

        signature = self._generate_signature("POST", path, params, body)
        params["auth_signature"] = signature

        url = f"{self._base_url}{path}"
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{query_string}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    full_url,
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    logger.debug(
                        "Triggered event '%s' on channel '%s'",
                        event,
                        channel,
                    )
                    return True
                else:
                    logger.error(
                        "Failed to trigger event: %s %s",
                        response.status_code,
                        response.text,
                    )
                    return False

        except httpx.TimeoutException:
            logger.error("Timeout triggering Soketi event")
            return False
        except Exception as exc:
            logger.error("Error triggering Soketi event: %s", exc)
            return False

    async def trigger_batch(
        self,
        events: list[Dict[str, Any]],
    ) -> bool:
        """Trigger multiple events in a single request.

        Args:
            events: List of dicts with channel, name, and data keys

        Returns:
            True if all events were triggered successfully
        """
        if not self._enabled:
            logger.debug("Soketi not enabled, skipping batch trigger")
            return False

        path = f"/apps/{self._app_id}/batch_events"

        batch = []
        for event in events:
            batch.append({
                "channel": event["channel"],
                "name": event["name"],
                "data": json.dumps(event["data"]),
            })

        body = json.dumps({"batch": batch})

        auth_timestamp = str(int(time.time()))
        auth_version = "1.0"

        params = {
            "auth_key": self._key,
            "auth_timestamp": auth_timestamp,
            "auth_version": auth_version,
            "body_md5": hashlib.md5(body.encode()).hexdigest(),
        }

        signature = self._generate_signature("POST", path, params, body)
        params["auth_signature"] = signature

        url = f"{self._base_url}{path}"
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{query_string}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    full_url,
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    logger.debug("Triggered %d batch events", len(events))
                    return True
                else:
                    logger.error(
                        "Failed to trigger batch events: %s %s",
                        response.status_code,
                        response.text,
                    )
                    return False

        except Exception as exc:
            logger.error("Error triggering batch Soketi events: %s", exc)
            return False

    def generate_auth_token(
        self,
        socket_id: str,
        channel: str,
        user_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate authentication token for private/presence channels.

        This is called by the auth webhook to authorize channel subscriptions.

        Args:
            socket_id: The socket ID from the client
            channel: The channel being subscribed to
            user_data: For presence channels, the user info to broadcast

        Returns:
            Auth response dict with 'auth' key (and 'channel_data' for presence)
        """
        if user_data:
            # Presence channel
            channel_data = json.dumps(user_data)
            string_to_sign = f"{socket_id}:{channel}:{channel_data}"
            signature = hmac.new(
                self._secret.encode(),
                string_to_sign.encode(),
                hashlib.sha256
            ).hexdigest()

            return {
                "auth": f"{self._key}:{signature}",
                "channel_data": channel_data,
            }
        else:
            # Private channel
            string_to_sign = f"{socket_id}:{channel}"
            signature = hmac.new(
                self._secret.encode(),
                string_to_sign.encode(),
                hashlib.sha256
            ).hexdigest()

            return {
                "auth": f"{self._key}:{signature}",
            }


# Module-level singleton
_soketi_client: Optional[SoketiClient] = None


def get_soketi_client() -> SoketiClient:
    """Get the Soketi client singleton."""
    global _soketi_client
    if _soketi_client is None:
        _soketi_client = SoketiClient()
    return _soketi_client

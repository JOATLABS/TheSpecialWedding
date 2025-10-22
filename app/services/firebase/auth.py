"""Firebase authentication helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from firebase_admin import auth

from app.services.firebase.client import FirebaseInitializationError, get_firebase_app

logger = logging.getLogger(__name__)


class FirebaseAuthService:
    """Service wrapper around Firebase custom token generation."""

    def __init__(self) -> None:
        self._app = None

    def _ensure_app(self):
        if self._app is None:
            self._app = get_firebase_app()
        return self._app

    async def create_custom_token(
        self,
        uid: str,
        claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a Firebase custom token for the supplied UID."""
        if not uid:
            raise ValueError("uid is required to mint a Firebase custom token")

        app = self._ensure_app()
        try:
            token_bytes = await asyncio.to_thread(auth.create_custom_token, uid, claims or {}, app)
        except FirebaseInitializationError:
            raise
        except Exception as exc:  # pragma: no cover - firebase_admin raises specific errors
            logger.error("Failed to create Firebase custom token for %s: %s", uid, exc)
            raise RuntimeError("Unable to generate Firebase custom token") from exc

        if isinstance(token_bytes, bytes):
            return token_bytes.decode("utf-8")
        return str(token_bytes)

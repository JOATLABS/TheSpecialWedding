"""Firebase Admin SDK client helpers."""

from __future__ import annotations

import logging
import threading
from functools import lru_cache
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import App
from google.cloud.firestore import Client as FirestoreClient

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_app_lock = threading.Lock()
_default_app: Optional[App] = None
_firestore_client: Optional[FirestoreClient] = None


class FirebaseInitializationError(RuntimeError):
    """Raised when Firebase cannot be initialised."""


def _initialise_app() -> App:
    """Initialise and cache the Firebase app instance."""
    global _default_app

    if _default_app is not None:
        return _default_app

    with _app_lock:
        if _default_app is not None:
            return _default_app

        settings = get_settings()
        if not settings.is_firebase_configured():
            raise FirebaseInitializationError("Firebase integration is disabled or not configured")

        service_account = settings.get_firebase_service_account()
        if not service_account:
            raise FirebaseInitializationError("Firebase service account credentials are missing")

        try:
            cred = credentials.Certificate(service_account)
            _default_app = firebase_admin.initialize_app(cred, name="wedding-webapp")
            logger.info("Initialised Firebase app for project %s", service_account.get("project_id"))
        except Exception as exc:  # pragma: no cover - firebase_admin provides detailed errors
            logger.error("Failed to initialise Firebase app: %s", exc)
            raise FirebaseInitializationError("Unable to initialise Firebase Admin SDK") from exc

    return _default_app


def get_firebase_app() -> App:
    """Return the cached Firebase app instance."""
    return _initialise_app()


@lru_cache(maxsize=1)
def get_firestore_client() -> FirestoreClient:
    """Return a Firestore client bound to the configured Firebase app."""
    app = get_firebase_app()
    try:
        client = firestore.client(app=app)
    except Exception as exc:  # pragma: no cover - depends on firebase_admin internals
        logger.error("Failed to create Firestore client: %s", exc)
        raise FirebaseInitializationError("Unable to create Firestore client") from exc

    global _firestore_client
    _firestore_client = client
    return client


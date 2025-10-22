"""Firebase service utilities for messaging infrastructure."""

from .client import get_firebase_app, get_firestore_client
from .auth import FirebaseAuthService

__all__ = [
    "FirebaseAuthService",
    "get_firebase_app",
    "get_firestore_client",
]

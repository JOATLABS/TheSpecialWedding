"""Messaging service exports."""

from .mongo_repository import MongoMessagingRepository, MessagingRepositoryError
from .service import MessagingService
from .soketi_client import SoketiClient, get_soketi_client

# Keep FirestoreMessagingRepository import for backward compatibility (deprecated)
try:
    from .repository import FirestoreMessagingRepository
except ImportError:
    FirestoreMessagingRepository = None  # type: ignore

__all__ = [
    "MongoMessagingRepository",
    "MessagingRepositoryError",
    "MessagingService",
    "SoketiClient",
    "get_soketi_client",
    "FirestoreMessagingRepository",
]

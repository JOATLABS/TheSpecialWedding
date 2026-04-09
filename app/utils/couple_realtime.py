"""Helpers for couple-portal realtime channels."""

from app.utils.couple_identity import build_couple_principal_key


def couple_sse_channel(couple_id: str) -> str:
    """Stable SSE channel key for couple-scoped realtime events."""
    return build_couple_principal_key(couple_id)

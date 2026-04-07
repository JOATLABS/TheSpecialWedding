"""Helpers for couple-portal realtime channels."""


def couple_sse_channel(email: str) -> str:
    """Stable SSE channel key for couple-scoped realtime events."""
    return f"couple::{email.strip().lower()}"

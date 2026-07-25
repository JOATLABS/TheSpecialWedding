from __future__ import annotations

from typing import Literal
from urllib.parse import urlencode

SupportConversation = Literal["sms_support", "support_ticket"]


def build_support_inbox_path(
    conversation: SupportConversation,
    ticket_id: str,
    wedding_id: str | None = None,
) -> str:
    """Build a fail-closed communications inbox deep link for support threads."""
    if conversation not in {"sms_support", "support_ticket"}:
        raise ValueError(f"Unsupported support inbox conversation: {conversation}")
    if not ticket_id or not isinstance(ticket_id, str):
        raise ValueError("ticket_id is required")

    params = {"conversation": conversation, "ticket_id": ticket_id}
    if wedding_id:
        params["wedding_id"] = wedding_id

    return f"/admin/communications/inbox?{urlencode(params)}"


def build_support_inbox_url(
    frontend_url: str,
    conversation: SupportConversation,
    ticket_id: str,
    wedding_id: str | None = None,
) -> str:
    """Build an absolute communications inbox deep link for support threads."""
    base_url = (frontend_url or "").rstrip("/")
    if not base_url:
        raise ValueError("frontend_url is required")

    return f"{base_url}{build_support_inbox_path(conversation, ticket_id, wedding_id)}"

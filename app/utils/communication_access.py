"""Canonical capability policy for authenticated communications surfaces.

UI visibility is only an affordance. API routes must enforce the same
capability before reading or mutating a conversation domain.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import HTTPException, status


class CommunicationCapability(str, Enum):
    PLATFORM_SUPPORT = "platform_support"
    COUPLE_MESSAGES = "couple_messages"
    INBOUND_EMAIL = "inbound_email"
    GUEST_SMS = "guest_sms"
    RSVP_INVITES = "rsvp_invites"
    REMINDERS = "reminders"
    HISTORY = "history"


def has_communication_capability(
    user: Any, capability: CommunicationCapability
) -> bool:
    """Return whether an authenticated actor may use a communication domain."""

    if bool(getattr(user, "is_root_admin", False)):
        return capability is CommunicationCapability.PLATFORM_SUPPORT

    if bool(getattr(user, "is_wedding_planner", False)):
        return True

    if bool(getattr(user, "is_advertising_vendor", False)):
        return capability is CommunicationCapability.PLATFORM_SUPPORT

    if not bool(getattr(user, "is_team_member", False)):
        return False

    permissions = getattr(user, "team_permissions", None)
    if permissions is None:
        return False

    if capability in {
        CommunicationCapability.PLATFORM_SUPPORT,
        CommunicationCapability.GUEST_SMS,
    }:
        return True

    if capability is CommunicationCapability.COUPLE_MESSAGES:
        return bool(permissions.get("message_couples", False))

    can_send_rsvp = bool(permissions.get("send_rsvp", False))
    can_send_reminders = bool(permissions.get("send_reminders", False))

    if capability is CommunicationCapability.RSVP_INVITES:
        return can_send_rsvp
    if capability is CommunicationCapability.REMINDERS:
        return can_send_reminders
    if capability in {
        CommunicationCapability.INBOUND_EMAIL,
        CommunicationCapability.HISTORY,
    }:
        return can_send_rsvp or can_send_reminders

    return False


def enforce_communication_capability(
    user: Any, capability: CommunicationCapability
) -> None:
    """Fail closed when an actor lacks a communication capability."""

    if has_communication_capability(user, capability):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"{capability.value.replace('_', ' ').title()} access required",
    )

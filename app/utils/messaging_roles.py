"""Centralized constants and predicates for `couple_messages.sender_role`.

Mirrors the `planner_billing_scope` pattern: an isolated module exposing the
canonical string values and small predicates so service code can stop embedding
bare role literals. Scoped to `sender_role` on the couple_messages collection
— other role-shaped fields (`target_audience`, `submitted_by_type`,
`author_role`) are unrelated concerns and are tracked separately in AGENTS.md.
"""

from __future__ import annotations

# Canonical string values for the `sender_role` field on couple_messages
# documents. The string values are load-bearing: they persist in MongoDB and in
# the REST payload shape. Do not rename without a data migration.
SENDER_ROLE_COUPLE = "couple"
SENDER_ROLE_PLANNER = "planner"

VALID_SENDER_ROLES: tuple[str, ...] = (
    SENDER_ROLE_COUPLE,
    SENDER_ROLE_PLANNER,
)


def is_valid_sender_role(role: str | None) -> bool:
    """Return True when the role is a recognized sender_role value."""

    return role in VALID_SENDER_ROLES


def is_couple_sender_role(role: str | None) -> bool:
    """Return True when the sender_role identifies a message authored by the couple."""

    return role == SENDER_ROLE_COUPLE


def is_planner_sender_role(role: str | None) -> bool:
    """Return True when the sender_role identifies a message authored by a planner."""

    return role == SENDER_ROLE_PLANNER

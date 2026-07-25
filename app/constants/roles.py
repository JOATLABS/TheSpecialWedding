"""Canonical user-role constants and predicates.

Per AGENTS.md "Centralized Constants And Enums Rule": services must
not compare against bare role strings. Add new roles here first, then
expose a predicate helper next to it. A typo on an import is a
``NameError`` at startup; a typo on ``"wedding_planner"`` silently
bypasses an authorization gate or — in the catalog-seed case — silently
skips a critical onboarding side effect.

Existing role-aware modules:
- ``app.utils.planner_billing_scope.is_planner_billing_role`` — currently
  duplicates ``role == ROLE_WEDDING_PLANNER``. Migration is open tech
  debt; new code routes through this module.
- ``app.utils.messaging_roles.is_planner_sender_role``.
"""

from __future__ import annotations

from collections.abc import Mapping

ROLE_WEDDING_PLANNER = "wedding_planner"
ROLE_TEAM_MEMBER = "team_member"
ROLE_VENDOR = "advertising_vendor"
ROLE_ROOT_ADMIN = "ROOT_ADMIN"
ROLE_COUPLE = "couple"


def _normalize(role: str | None) -> str:
    """Strip + lower a role string, defending against case/whitespace drift.

    The canonical write path stores the lowercase form, but legacy or
    admin-imported rows can carry mixed-case values (notably ``ROOT_ADMIN``,
    which is the only canonical role that is intentionally upper-cased).
    Normalizing on the read side keeps every predicate forgiving without
    forcing every callsite to pre-process.
    """
    return (role or "").strip().lower()


def is_wedding_planner_role(role: str | None) -> bool:
    """Return True when ``role`` is the canonical wedding-planner role.

    Use this anywhere a service needs to gate planner-only behaviour
    (catalog seed, billing scope, planner-only notifications). Never
    compare against the raw string in service code.
    """
    return _normalize(role) == ROLE_WEDDING_PLANNER


def is_wedding_planner_user(user: Mapping[str, object] | None) -> bool:
    """Convenience: predicate over a user document instead of a raw role."""
    if not user:
        return False
    return is_wedding_planner_role(str(user.get("role") or "") or None)

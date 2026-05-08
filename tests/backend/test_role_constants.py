"""Canonical role predicates — defends the catalog-seed gates against
typo / case-drift on the bare ``"wedding_planner"`` string.

Per AGENTS.md "Centralized Constants And Enums Rule": role checks must
not be bare string compares scattered across services. Every new role
gate goes through these predicates, and these predicates have to keep
returning the right answer in the obvious places (case mismatch,
whitespace, None, non-planner roles).
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.constants.roles import (  # noqa: E402
    ROLE_ROOT_ADMIN,
    ROLE_TEAM_MEMBER,
    ROLE_VENDOR,
    ROLE_WEDDING_PLANNER,
    is_wedding_planner_role,
    is_wedding_planner_user,
)


def test_canonical_planner_role_constant_value():
    # If this assertion ever fails, every Mongo row written under the
    # old value silently stops matching the new gate.
    assert ROLE_WEDDING_PLANNER == "wedding_planner"


def test_is_wedding_planner_role_accepts_canonical():
    assert is_wedding_planner_role(ROLE_WEDDING_PLANNER) is True


def test_is_wedding_planner_role_normalizes_case_and_whitespace():
    # Admin-imported rows can drift; the predicate has to forgive both
    # without forcing every caller to pre-process.
    assert is_wedding_planner_role("Wedding_Planner") is True
    assert is_wedding_planner_role("  wedding_planner  ") is True
    assert is_wedding_planner_role("WEDDING_PLANNER") is True


def test_is_wedding_planner_role_rejects_other_roles():
    assert is_wedding_planner_role(ROLE_TEAM_MEMBER) is False
    assert is_wedding_planner_role(ROLE_VENDOR) is False
    assert is_wedding_planner_role(ROLE_ROOT_ADMIN.lower()) is False
    assert is_wedding_planner_role(None) is False
    assert is_wedding_planner_role("") is False
    assert is_wedding_planner_role("planner") is False  # similar but wrong
    assert is_wedding_planner_role("wedding_planners") is False


def test_is_wedding_planner_user_handles_missing_or_none():
    assert is_wedding_planner_user(None) is False
    assert is_wedding_planner_user({}) is False
    assert is_wedding_planner_user({"role": None}) is False


def test_is_wedding_planner_user_accepts_planner_doc():
    assert is_wedding_planner_user({"role": ROLE_WEDDING_PLANNER}) is True
    assert is_wedding_planner_user({"role": "  Wedding_Planner  "}) is True


def test_is_wedding_planner_user_rejects_non_planner_doc():
    assert is_wedding_planner_user({"role": ROLE_TEAM_MEMBER}) is False
    assert is_wedding_planner_user({"role": ROLE_VENDOR}) is False

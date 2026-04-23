import pytest

from app.utils.messaging_roles import (
    SENDER_ROLE_COUPLE,
    SENDER_ROLE_PLANNER,
    VALID_SENDER_ROLES,
    is_couple_sender_role,
    is_planner_sender_role,
    is_valid_sender_role,
)


def test_sender_role_constants_are_load_bearing_strings():
    # The string values persist in MongoDB and the REST payload shape.
    # Pin the values so an unintended rename is caught by a unit test.
    assert SENDER_ROLE_COUPLE == "couple"
    assert SENDER_ROLE_PLANNER == "planner"


def test_valid_sender_roles_contains_only_couple_and_planner():
    assert set(VALID_SENDER_ROLES) == {"couple", "planner"}


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("couple", True),
        ("planner", True),
        ("admin", False),
        ("wedding_planner", False),
        ("", False),
        (None, False),
        ("COUPLE", False),  # case-sensitive
        ("Planner", False),
    ],
)
def test_is_valid_sender_role(role, expected):
    assert is_valid_sender_role(role) is expected


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("couple", True),
        ("planner", False),
        ("admin", False),
        (None, False),
        ("", False),
    ],
)
def test_is_couple_sender_role(role, expected):
    assert is_couple_sender_role(role) is expected


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("planner", True),
        ("couple", False),
        ("admin", False),
        (None, False),
        ("", False),
    ],
)
def test_is_planner_sender_role(role, expected):
    assert is_planner_sender_role(role) is expected

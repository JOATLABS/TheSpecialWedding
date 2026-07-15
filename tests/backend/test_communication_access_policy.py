from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.dependencies import auth_extended


def _load_policy_module():
    try:
        return importlib.import_module("app.utils.communication_access")
    except ModuleNotFoundError:
        pytest.fail("canonical communication access policy is missing")


def _user(**overrides):
    values = {
        "is_root_admin": False,
        "is_wedding_planner": False,
        "is_team_member": False,
        "is_advertising_vendor": False,
        "team_permissions": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_root_admin_has_platform_support_only() -> None:
    policy = _load_policy_module()
    root = _user(is_root_admin=True)

    assert policy.has_communication_capability(
        root, policy.CommunicationCapability.PLATFORM_SUPPORT
    )
    for capability in (
        policy.CommunicationCapability.COUPLE_MESSAGES,
        policy.CommunicationCapability.INBOUND_EMAIL,
        policy.CommunicationCapability.GUEST_SMS,
        policy.CommunicationCapability.RSVP_INVITES,
        policy.CommunicationCapability.REMINDERS,
        policy.CommunicationCapability.HISTORY,
    ):
        assert not policy.has_communication_capability(root, capability)


def test_planner_keeps_all_communications_capabilities() -> None:
    policy = _load_policy_module()
    planner = _user(is_wedding_planner=True)

    assert all(
        policy.has_communication_capability(planner, capability)
        for capability in policy.CommunicationCapability
    )


def test_team_permissions_preserve_existing_channel_behavior() -> None:
    policy = _load_policy_module()
    empty_permissions = _user(is_team_member=True, team_permissions={})

    assert policy.has_communication_capability(
        empty_permissions, policy.CommunicationCapability.PLATFORM_SUPPORT
    )
    assert policy.has_communication_capability(
        empty_permissions, policy.CommunicationCapability.GUEST_SMS
    )
    assert not policy.has_communication_capability(
        empty_permissions, policy.CommunicationCapability.INBOUND_EMAIL
    )

    full_permissions = _user(
        is_team_member=True,
        team_permissions={
            "message_couples": True,
            "send_rsvp": True,
            "send_reminders": True,
        },
    )
    assert all(
        policy.has_communication_capability(full_permissions, capability)
        for capability in policy.CommunicationCapability
    )


def test_advertising_vendor_is_limited_to_platform_support() -> None:
    policy = _load_policy_module()
    vendor = _user(is_advertising_vendor=True)

    assert policy.has_communication_capability(
        vendor, policy.CommunicationCapability.PLATFORM_SUPPORT
    )
    assert not policy.has_communication_capability(
        vendor, policy.CommunicationCapability.INBOUND_EMAIL
    )


def test_enforcement_fails_closed() -> None:
    policy = _load_policy_module()
    root = _user(is_root_admin=True)

    with pytest.raises(HTTPException) as exc_info:
        policy.enforce_communication_capability(
            root, policy.CommunicationCapability.GUEST_SMS
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_dependency_factory_denies_root_from_planner_channels() -> None:
    policy = _load_policy_module()
    factory = getattr(auth_extended, "require_communication_capability", None)
    assert callable(factory), "communication dependency factory is missing"

    dependency = factory(policy.CommunicationCapability.INBOUND_EMAIL)
    root = _user(is_root_admin=True)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(root)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_dependency_factory_preserves_planner_access() -> None:
    policy = _load_policy_module()
    factory = getattr(auth_extended, "require_communication_capability", None)
    assert callable(factory), "communication dependency factory is missing"

    dependency = factory(policy.CommunicationCapability.INBOUND_EMAIL)
    planner = _user(is_wedding_planner=True)

    assert await dependency(planner) is planner

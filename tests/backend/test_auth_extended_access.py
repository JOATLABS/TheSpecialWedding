import pytest
from fastapi import HTTPException

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    require_wedding_planner_only,
)


@pytest.mark.asyncio
async def test_require_wedding_planner_only_allows_root_admin(monkeypatch):
    monkeypatch.setenv("ROOT_ADMIN_EMAIL", "root@example.com")
    current_user = ExtendedAuthUser(
        email="root@example.com",
        role="ROOT_ADMIN",
        user_data={"role": "ROOT_ADMIN"},
    )

    result = await require_wedding_planner_only(current_user)

    assert result is current_user


@pytest.mark.asyncio
async def test_require_wedding_planner_only_rejects_non_planner_roles():
    current_user = ExtendedAuthUser(
        email="vendor@example.com",
        role="vendor",
        user_data={"role": "vendor"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_wedding_planner_only(current_user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Wedding planner access required"

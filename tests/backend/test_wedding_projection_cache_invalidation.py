from __future__ import annotations

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_projection_cache_module():
    module_name = "app.services.wedding_projection_cache_service"
    assert importlib.util.find_spec(module_name) is not None, (
        "Wedding projection cache invalidation must live in one service"
    )
    from app.services import wedding_projection_cache_service

    return wedding_projection_cache_service


@pytest.mark.asyncio
async def test_wedding_projection_invalidation_clears_old_and_new_public_slug_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection_cache = _load_projection_cache_module()
    weddings = SimpleNamespace(
        find_one=AsyncMock(return_value={"slug": "new-couple-slug"})
    )
    monkeypatch.setattr(
        projection_cache,
        "mongo",
        SimpleNamespace(db={"weddings": weddings}),
    )
    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(projection_cache.cache, "delete", delete)

    await projection_cache.invalidate_wedding_projection_caches(
        "wedding_1",
        previous_slug="old-couple-slug",
    )

    assert [call.args[0] for call in delete.await_args_list] == [
        "wedding_privacy_info:old-couple-slug",
        "wedding_privacy_info:new-couple-slug",
    ]
    weddings.find_one.assert_awaited_once_with(
        {"_id": "wedding_1"},
        {"slug": 1},
    )


@pytest.mark.asyncio
async def test_wedding_projection_invalidation_uses_previous_slug_when_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection_cache = _load_projection_cache_module()
    weddings = SimpleNamespace(
        find_one=AsyncMock(side_effect=RuntimeError("mongo unavailable"))
    )
    monkeypatch.setattr(
        projection_cache,
        "mongo",
        SimpleNamespace(db={"weddings": weddings}),
    )
    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(projection_cache.cache, "delete", delete)

    await projection_cache.invalidate_wedding_projection_caches(
        "wedding_1",
        previous_slug="still-clear-this-slug",
    )

    delete.assert_awaited_once_with("wedding_privacy_info:still-clear-this-slug")


@pytest.mark.asyncio
async def test_shared_event_write_invalidates_only_after_the_durable_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import couple_portal as couple_portal_api

    call_order: list[str] = []

    async def update_one(*_args, **_kwargs):
        call_order.append("write")
        return SimpleNamespace(matched_count=1)

    async def invalidate(wedding_id: str, **_kwargs) -> None:
        assert wedding_id == "wedding_1"
        call_order.append("invalidate")

    monkeypatch.setattr(
        couple_portal_api,
        "mongo",
        SimpleNamespace(
            get_weddings_collection=lambda: SimpleNamespace(update_one=update_one)
        ),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "invalidate_wedding_projection_caches",
        invalidate,
        raising=False,
    )

    await couple_portal_api._save_wedding_events(
        {"_id": "wedding_1", "updated_at": "version_1"},
        "events.0.order_of_events",
        [{"id": "item_1"}],
        "planner@example.com",
    )

    assert call_order == ["write", "invalidate"]


@pytest.mark.asyncio
async def test_admin_wedding_update_passes_previous_slug_after_durable_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import wedding as wedding_api

    call_order: list[str] = []
    current_user = SimpleNamespace(
        is_team_member=False,
        parent_planner_id=None,
        team_owner_email=None,
        user_data={"_id": "planner_1"},
        email="planner@example.com",
        is_root_admin=False,
    )

    async def update_wedding(*_args, **_kwargs):
        call_order.append("write")
        return {"message": "Wedding updated successfully"}

    async def invalidate(
        wedding_id: str,
        *,
        previous_slug: str | None = None,
    ) -> None:
        assert wedding_id == "wedding_1"
        assert previous_slug == "old-slug"
        call_order.append("invalidate")

    monkeypatch.setattr(wedding_api, "enforce_team_permission", lambda *_args: None)
    monkeypatch.setattr(
        wedding_api, "check_wedding_access", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        wedding_api.wedding_service,
        "get_wedding",
        AsyncMock(
            return_value={
                "slug": "old-slug",
                "assigned_planner_id": "planner_1",
                "assigned_planner_email": "planner@example.com",
            }
        ),
    )
    monkeypatch.setattr(wedding_api.wedding_service, "update_wedding", update_wedding)
    monkeypatch.setattr(
        wedding_api, "_sync_couple_owner_mirrors", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        wedding_api.sse_manager,
        "broadcast_data_change",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        wedding_api,
        "invalidate_wedding_projection_caches",
        invalidate,
        raising=False,
    )

    result = await wedding_api.update_wedding_admin(
        "wedding_1",
        {"slug": "new-slug", "events": []},
        current_user=current_user,  # type: ignore[arg-type]
    )

    assert result == {"message": "Wedding updated successfully"}
    assert call_order[:2] == ["write", "invalidate"]


@pytest.mark.asyncio
async def test_admin_wedding_create_invalidates_after_durable_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import wedding as wedding_api
    from app.services import planner_notification_service

    call_order: list[str] = []
    current_user = SimpleNamespace(
        is_team_member=False,
        parent_planner_id=None,
        team_owner_email=None,
        user_data={"_id": "root_1"},
        email="root@example.com",
        is_root_admin=True,
    )

    async def create_wedding(_wedding):
        call_order.append("write")
        return {
            "message": "Wedding created successfully",
            "id": "wedding_1",
            "slug": "new-slug",
        }

    async def invalidate(wedding_id: str, **_kwargs) -> None:
        assert wedding_id == "wedding_1"
        call_order.append("invalidate")

    monkeypatch.setattr(wedding_api, "enforce_team_permission", lambda *_args: None)
    monkeypatch.setattr(wedding_api.wedding_service, "create_wedding", create_wedding)
    monkeypatch.setattr(
        wedding_api,
        "invalidate_wedding_projection_caches",
        invalidate,
    )
    monkeypatch.setattr(
        wedding_api.sse_manager,
        "broadcast_data_change",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        planner_notification_service.planner_notification_service,
        "notify_wedding_created",
        AsyncMock(return_value=None),
    )
    wedding_payload = SimpleNamespace(
        model_dump=lambda **_kwargs: {
            "_id": "wedding_1",
            "slug": "new-slug",
            "couple_names": "New Couple",
        }
    )

    result = await wedding_api.create_wedding(
        wedding_payload,  # type: ignore[arg-type]
        current_user=current_user,  # type: ignore[arg-type]
    )

    assert result["id"] == "wedding_1"
    assert call_order[:2] == ["write", "invalidate"]


@pytest.mark.asyncio
async def test_non_root_wedding_create_ignores_client_supplied_foreign_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import wedding as wedding_api

    class CapturedWrite(RuntimeError):
        pass

    captured: dict = {}
    current_user = SimpleNamespace(
        is_team_member=False,
        parent_planner_id=None,
        team_owner_email=None,
        user_data={"_id": "planner_owner"},
        email="owner@planner.example",
        is_root_admin=False,
    )
    wedding_payload = SimpleNamespace(
        model_dump=lambda **_kwargs: {
            "_id": "wedding_1",
            "slug": "new-slug",
            "couple_names": "New Couple",
            "assigned_planner_id": "foreign_planner",
            "assigned_planner_email": "foreign@planner.example",
        }
    )

    async def capture_write(wedding_data):
        captured.update(wedding_data)
        raise CapturedWrite

    monkeypatch.setattr(wedding_api, "enforce_team_permission", lambda *_args: None)
    monkeypatch.setattr(
        wedding_api.subscription_service,
        "check_usage_limits",
        AsyncMock(return_value={"allowed": True}),
    )
    monkeypatch.setattr(wedding_api.wedding_service, "create_wedding", capture_write)

    with pytest.raises(CapturedWrite):
        await wedding_api.create_wedding(
            wedding_payload,  # type: ignore[arg-type]
            current_user=current_user,  # type: ignore[arg-type]
        )

    assert captured["assigned_planner_id"] == "planner_owner"
    assert captured["assigned_planner_email"] == "owner@planner.example"


@pytest.mark.asyncio
async def test_admin_hard_delete_invalidates_previous_slug_after_durable_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import wedding as wedding_api

    call_order: list[str] = []
    current_user = SimpleNamespace(email="root@example.com")
    weddings = SimpleNamespace(
        find_one=AsyncMock(
            return_value={
                "_id": "wedding_1",
                "slug": "old-slug",
                "assigned_planner_id": "planner_1",
                "assigned_planner_email": "planner@example.com",
            }
        )
    )

    async def hard_delete(*_args, **_kwargs):
        call_order.append("write")
        return {"message": "Wedding permanently deleted"}

    async def invalidate(
        wedding_id: str,
        *,
        previous_slug: str | None = None,
    ) -> None:
        assert wedding_id == "wedding_1"
        assert previous_slug == "old-slug"
        call_order.append("invalidate")

    monkeypatch.setattr(
        wedding_api,
        "mongo",
        SimpleNamespace(db={"weddings": weddings}),
    )
    monkeypatch.setattr(
        wedding_api.cascade_delete_service,
        "hard_delete_wedding",
        hard_delete,
    )
    monkeypatch.setattr(
        wedding_api,
        "invalidate_wedding_projection_caches",
        invalidate,
    )
    monkeypatch.setattr(
        wedding_api.sse_manager,
        "broadcast_data_change",
        AsyncMock(return_value=None),
    )

    result = await wedding_api.delete_wedding_admin(
        "wedding_1",
        current_user=current_user,  # type: ignore[arg-type]
        hard_delete=True,
    )

    assert result == {"message": "Wedding permanently deleted"}
    assert call_order == ["write", "invalidate"]


@pytest.mark.asyncio
async def test_root_assignment_and_unassignment_invalidate_wedding_projections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import user_management_service as user_management_module
    from app.services.user_management_service import UserManagementService

    invalidate_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        user_management_module,
        "invalidate_wedding_projection_caches",
        invalidate_mock,
        raising=False,
    )
    service = UserManagementService.__new__(UserManagementService)
    service.users_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(
            return_value={
                "_id": "507f1f77bcf86cd799439011",
                "email": "planner@example.com",
                "role": "wedding_planner",
            }
        )
    )
    service.weddings_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(
            side_effect=[
                {
                    "assigned_planner_id": "old_planner_1",
                    "assigned_planner_email": "old-owner@example.com",
                },
                {
                    "assigned_planner_id": "507f1f77bcf86cd799439011",
                    "assigned_planner_email": "planner@example.com",
                },
                {
                    "assigned_planner_id": "507f1f77bcf86cd799439011",
                    "assigned_planner_email": "planner@example.com",
                },
                {"_id": "wedding_1"},
            ]
        ),
        update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)),
    )
    couple_users = SimpleNamespace(update_many=AsyncMock(return_value=None))
    monkeypatch.setattr(
        user_management_module,
        "mongo",
        SimpleNamespace(db={"couple_users": couple_users}),
    )

    await service.assign_wedding_to_planner(
        "507f1f77bcf86cd799439011",
        "wedding_1",
    )
    await service.unassign_wedding_from_planner(
        "507f1f77bcf86cd799439011",
        "wedding_1",
    )

    assert invalidate_mock.await_count == 2
    assert all(call.args == ("wedding_1",) for call in invalidate_mock.await_args_list)
    assert service.weddings_collection.update_one.await_args_list[0].args[1] == {
        "$set": {
            "assigned_planner_id": "507f1f77bcf86cd799439011",
            "assigned_planner_email": "planner@example.com",
        }
    }
    assert service.weddings_collection.update_one.await_args_list[1].args[1] == {
        "$unset": {
            "assigned_planner_id": "",
            "assigned_planner_email": "",
        }
    }
    assert couple_users.update_many.await_count == 2
    first_mirror_update = couple_users.update_many.await_args_list[0].args[1]
    assert first_mirror_update["$set"]["planner_id"] == ("507f1f77bcf86cd799439011")
    assert first_mirror_update["$set"]["planner_email"] == "planner@example.com"
    assert "updated_at" in first_mirror_update["$set"]
    assert couple_users.update_many.await_args_list[1].args[1]["$unset"] == {
        "planner_id": "",
        "planner_email": "",
    }


@pytest.mark.asyncio
async def test_root_unassignment_rejects_a_wedding_owned_by_another_planner() -> None:
    from fastapi import HTTPException

    from app.services.user_management_service import UserManagementService

    service = UserManagementService.__new__(UserManagementService)
    service.users_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(
            return_value={
                "_id": "507f1f77bcf86cd799439011",
                "email": "planner@example.com",
                "role": "wedding_planner",
            }
        )
    )
    service.weddings_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(
            return_value={
                "assigned_planner_id": "507f1f77bcf86cd799439012",
                "assigned_planner_email": "other-owner@example.com",
            }
        ),
        update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.unassign_wedding_from_planner(
            "507f1f77bcf86cd799439011",
            "wedding_1",
        )

    assert exc_info.value.status_code == 409
    service.weddings_collection.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_planner_wedding_directory_reads_fresh_data_without_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import planner_metrics as planner_module

    class CacheTripwire:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("The planner wedding directory must not read cache")

        async def set(self, *_args, **_kwargs):
            raise AssertionError("The planner wedding directory must not write cache")

    monkeypatch.setattr(planner_module, "cache", CacheTripwire(), raising=False)

    class WeddingCollection:
        def __init__(self) -> None:
            self.calls = 0

        def find(self, *_args, **_kwargs):
            self.calls += 1
            wedding_date = "2026-10-17" if self.calls == 1 else "2026-10-18"
            return SimpleNamespace(
                to_list=AsyncMock(
                    return_value=[
                        {
                            "_id": "wedding_1",
                            "couple_names": "Sofia & Daniel",
                            "date": wedding_date,
                            "slug": "sofia-and-daniel",
                        }
                    ]
                )
            )

    weddings = WeddingCollection()
    monkeypatch.setattr(
        planner_module,
        "mongo",
        SimpleNamespace(get_weddings_collection=lambda: weddings),
    )
    root_user = SimpleNamespace(is_root_admin=True, is_team_member=False)

    first = await planner_module.get_planner_weddings(
        current_user=root_user,  # type: ignore[arg-type]
        include_cancelled=False,
    )
    second = await planner_module.get_planner_weddings(
        current_user=root_user,  # type: ignore[arg-type]
        include_cancelled=False,
    )

    assert first[0].date == "2026-10-17"
    assert second[0].date == "2026-10-18"
    assert weddings.calls == 2


@pytest.mark.asyncio
async def test_cache_pattern_clear_uses_incremental_scan_not_blocking_keys() -> None:
    from app.core.cache import CacheManager

    class ScanOnlyRedis:
        def __init__(self) -> None:
            self.matches: list[tuple[str, int]] = []
            self.delete_batches: list[tuple[bytes, ...]] = []

        async def scan_iter(self, *, match: str, count: int):
            self.matches.append((match, count))
            for index in range(101):
                yield f"wedding_app:calendar_external_events:key-{index}".encode()

        async def delete(self, *keys: bytes) -> int:
            self.delete_batches.append(keys)
            return len(keys)

        async def keys(self, _pattern: str):  # pragma: no cover - safety tripwire
            raise AssertionError("Redis KEYS must never be used for pattern clearing")

    redis_client = ScanOnlyRedis()
    manager = CacheManager()
    manager.enabled = True
    manager.redis_client = redis_client  # type: ignore[assignment]

    deleted = await manager.clear_pattern("calendar_external_events:connection-1:*")

    assert deleted == 101
    assert redis_client.matches == [
        ("wedding_app:calendar_external_events:connection-1:*", 100)
    ]
    assert [len(batch) for batch in redis_client.delete_batches] == [100, 1]


@pytest.mark.asyncio
async def test_couple_dashboard_reads_fresh_aggregates_without_short_lived_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import couple_portal_service as portal_module

    class CacheTripwire:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("The aggregate dashboard must not read a stale cache")

        async def set(self, *_args, **_kwargs):
            raise AssertionError("The aggregate dashboard must not write a stale cache")

    monkeypatch.setattr(portal_module, "cache", CacheTripwire(), raising=False)
    weddings = SimpleNamespace(
        find_one=AsyncMock(
            side_effect=[
                {
                    "_id": "wedding_1",
                    "couple_names": "Sofia & Daniel",
                    "date": "2026-10-17",
                    "events": [],
                },
                {
                    "_id": "wedding_1",
                    "couple_names": "Sofia & Daniel",
                    "date": "2026-10-18",
                    "events": [],
                },
            ]
        )
    )
    monkeypatch.setattr(
        portal_module,
        "mongo",
        SimpleNamespace(get_weddings_collection=lambda: weddings),
    )

    service = portal_module.CouplePortalService()
    monkeypatch.setattr(service, "_get_guest_stats", AsyncMock(return_value={}))
    monkeypatch.setattr(service, "_get_budget_summary", AsyncMock(return_value={}))
    monkeypatch.setattr(service, "_get_contract_info", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_get_shared_forms", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_get_updates", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        portal_module.guest_media_service,
        "get_dashboard_summary",
        AsyncMock(return_value={}),
    )

    first = await service.get_portal_dashboard("wedding_1", "couple@example.com")
    second = await service.get_portal_dashboard("wedding_1", "couple@example.com")

    assert first is not None and second is not None
    assert first["wedding"]["date"] == "2026-10-17"
    assert second["wedding"]["date"] == "2026-10-18"
    assert weddings.find_one.await_count == 2

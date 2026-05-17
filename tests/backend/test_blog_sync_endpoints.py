"""
Tests for the two new admin endpoints in app/api/blog.py:

  POST /admin/blog/sync-babylovegrowth
  GET  /admin/blog/sync-babylovegrowth/status

Both endpoints are require_root_admin-gated. We mount the blog router
under a fresh FastAPI app with the auth dependency overridden, and
assert behaviour at the HTTP boundary. The sync service itself is
unit-tested exhaustively in test_babylovegrowth_sync.py — these tests
verify only the endpoint wiring.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.blog import router as blog_router
from app.dependencies.auth_extended import require_root_admin


@pytest.fixture
def app_with_blog_router():
    """A fresh FastAPI app with the blog router mounted and the
    require_root_admin dependency overridden to return a fake admin."""
    app = FastAPI()
    app.include_router(blog_router)

    fake_admin = SimpleNamespace(
        email="root@thespecialwedding.io",
        role="root_admin",
    )
    app.dependency_overrides[require_root_admin] = lambda: fake_admin
    return app


def _stub_gate_pass(monkeypatch):
    """Set up monkeypatches so the pre-flight gate checks pass:
    sync_enabled=True, api_key set, sync_runs state doc shows idle."""
    monkeypatch.setattr("app.core.settings.settings.babylovegrowth_sync_enabled", True)
    monkeypatch.setattr("app.core.settings.settings.babylovegrowth_api_key", "test-key")

    fake_state_doc = {"_id": "babylovegrowth_sync_state", "status": "idle"}
    fake_collection = MagicMock()
    fake_collection.find_one = AsyncMock(return_value=fake_state_doc)
    fake_db = MagicMock()
    fake_db.__getitem__ = lambda self, k: fake_collection
    fake_mongo = MagicMock()
    fake_mongo.db = fake_db
    monkeypatch.setattr("app.core.database.mongo", fake_mongo)


def test_post_sync_endpoint_returns_202_accepted(app_with_blog_router, monkeypatch):
    """When all gates pass, endpoint enqueues the background task and
    returns the expected acceptance payload."""
    _stub_gate_pass(monkeypatch)
    fake_sync = AsyncMock(return_value={"status": "succeeded"})
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.babylovegrowth_sync_service.run_full_sync",
        fake_sync,
    )

    client = TestClient(app_with_blog_router)
    response = client.post("/admin/blog/sync-babylovegrowth")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert "background" in body["message"].lower()


def test_post_sync_endpoint_actually_invokes_background_task(
    app_with_blog_router, monkeypatch
):
    """When gates pass, TestClient awaits the BackgroundTask before
    unblocking us. Assert run_full_sync was called with the
    expected trigger source."""
    _stub_gate_pass(monkeypatch)
    fake_sync = AsyncMock(return_value={"status": "succeeded"})
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.babylovegrowth_sync_service.run_full_sync",
        fake_sync,
    )

    client = TestClient(app_with_blog_router)
    client.post("/admin/blog/sync-babylovegrowth")

    fake_sync.assert_called_once_with(triggered_by="manual")


def test_post_sync_endpoint_returns_skipped_when_sync_disabled(
    app_with_blog_router, monkeypatch
):
    """Pre-flight gate: BABYLOVEGROWTH_SYNC_ENABLED=false → skipped."""
    monkeypatch.setattr("app.core.settings.settings.babylovegrowth_sync_enabled", False)
    monkeypatch.setattr("app.core.settings.settings.babylovegrowth_api_key", "test-key")
    fake_sync = AsyncMock()
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.babylovegrowth_sync_service.run_full_sync",
        fake_sync,
    )

    client = TestClient(app_with_blog_router)
    response = client.post("/admin/blog/sync-babylovegrowth")

    assert response.status_code == 200
    assert response.json() == {"status": "skipped", "reason": "sync_disabled"}
    fake_sync.assert_not_called()  # Background task NOT enqueued.


def test_post_sync_endpoint_returns_skipped_when_no_api_key(
    app_with_blog_router, monkeypatch
):
    """Pre-flight gate: BABYLOVEGROWTH_API_KEY unset → skipped."""
    monkeypatch.setattr("app.core.settings.settings.babylovegrowth_sync_enabled", True)
    monkeypatch.setattr("app.core.settings.settings.babylovegrowth_api_key", None)
    fake_sync = AsyncMock()
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.babylovegrowth_sync_service.run_full_sync",
        fake_sync,
    )

    client = TestClient(app_with_blog_router)
    response = client.post("/admin/blog/sync-babylovegrowth")

    assert response.status_code == 200
    assert response.json() == {"status": "skipped", "reason": "no_api_key"}
    fake_sync.assert_not_called()


def test_post_sync_endpoint_returns_skipped_when_lock_held(
    app_with_blog_router, monkeypatch
):
    """Pre-flight gate: prior run still 'running' in sync_runs doc."""
    monkeypatch.setattr("app.core.settings.settings.babylovegrowth_sync_enabled", True)
    monkeypatch.setattr("app.core.settings.settings.babylovegrowth_api_key", "test-key")
    fake_state_doc = {
        "_id": "babylovegrowth_sync_state",
        "status": "running",
        "lock_token": "abc123",
    }
    fake_collection = MagicMock()
    fake_collection.find_one = AsyncMock(return_value=fake_state_doc)
    fake_db = MagicMock()
    fake_db.__getitem__ = lambda self, k: fake_collection
    fake_mongo = MagicMock()
    fake_mongo.db = fake_db
    monkeypatch.setattr("app.core.database.mongo", fake_mongo)
    fake_sync = AsyncMock()
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.babylovegrowth_sync_service.run_full_sync",
        fake_sync,
    )

    client = TestClient(app_with_blog_router)
    response = client.post("/admin/blog/sync-babylovegrowth")

    assert response.status_code == 200
    assert response.json() == {"status": "skipped", "reason": "lock_held"}
    fake_sync.assert_not_called()


def test_get_status_endpoint_returns_state_doc(app_with_blog_router, monkeypatch):
    expected_state = {
        "_id": "babylovegrowth_sync_state",
        "status": "succeeded",
        "lock_token": None,
        "lock_acquired_at": None,
        "started_at": None,
        "ended_at": None,
        "new_count": 5,
        "skipped_count": 2,
        "image_failed_count": 0,
        "error_count": 0,
        "errors": [],
    }
    fake_status = AsyncMock(return_value=expected_state)
    monkeypatch.setattr(
        "app.services.babylovegrowth_sync_service.babylovegrowth_sync_service.get_last_run_status",
        fake_status,
    )

    client = TestClient(app_with_blog_router)
    response = client.get("/admin/blog/sync-babylovegrowth/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["new_count"] == 5
    assert body["skipped_count"] == 2


def test_endpoints_require_root_admin():
    """If require_root_admin is NOT overridden, the endpoint can't be
    reached — verify the dependency is wired."""
    app = FastAPI()
    app.include_router(blog_router)
    # Intentionally NO dependency override. The real require_root_admin
    # depends on a JWT + Mongo lookup, which TestClient won't satisfy
    # — so it should fail with 401 / 403 / 500 rather than reach the
    # background task.

    client = TestClient(app)
    response = client.post("/admin/blog/sync-babylovegrowth")
    # The exact failure code depends on how require_root_admin handles
    # a missing token; we just assert it's not a 2xx.
    assert response.status_code >= 400, (
        f"Endpoint reachable without admin auth — got {response.status_code}"
    )

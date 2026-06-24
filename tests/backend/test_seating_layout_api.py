import os
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")


class FakeUpdateResult:
    matched_count = 1
    modified_count = 1
    upserted_id = None


class FakeAsyncCollection:
    def __init__(self):
        self.docs = {}

    async def find_one(self, query):
        wedding_id = query.get("wedding_id")
        doc = self.docs.get(wedding_id)
        return deepcopy(doc) if doc else None

    async def update_one(self, query, update, upsert=False):
        wedding_id = query.get("wedding_id")
        if wedding_id not in self.docs:
            self.docs[wedding_id] = {"_id": f"layout-{wedding_id}"}

        if "$setOnInsert" in update:
            for key, value in update["$setOnInsert"].items():
                self.docs[wedding_id].setdefault(key, value)
        if "$set" in update:
            self.docs[wedding_id].update(update["$set"])

        return FakeUpdateResult()


class FakeDb:
    def __init__(self):
        self.collections = {"seating_layouts": FakeAsyncCollection()}

    def __getitem__(self, name):
        return self.collections[name]


def _build_client(monkeypatch, *, can_access=True):
    import app.api.tables as tables_api

    app = FastAPI()
    app.include_router(tables_api.router, prefix="/admin")

    fake_db = FakeDb()
    monkeypatch.setattr(tables_api, "mongo", SimpleNamespace(db=fake_db))
    monkeypatch.setattr(
        tables_api,
        "check_wedding_access",
        AsyncMock(return_value=can_access),
    )

    planner = tables_api.ExtendedAuthUser(
        email="planner@example.com",
        role="wedding_planner",
        user_data={"role": "wedding_planner"},
    )

    async def override_user():
        return planner

    app.dependency_overrides[tables_api.require_admin_or_planner] = override_user
    return TestClient(app), fake_db


def test_get_venue_layout_returns_default_for_empty_wedding(monkeypatch):
    client, _fake_db = _build_client(monkeypatch)

    response = client.get("/admin/tables/wedding-1/venue-layout")

    assert response.status_code == 200
    assert response.json() == {
        "id": None,
        "wedding_id": "wedding-1",
        "canvas_width": 1600,
        "canvas_height": 1000,
        "outline": [],
        "background_image_data_url": None,
        "background_image_name": None,
        "background_locked": True,
        "scale_pixels": None,
        "scale_distance": None,
        "scale_unit": "ft",
        "fixtures": [],
        "updated_at": None,
    }


def test_update_venue_layout_persists_outline(monkeypatch):
    client, _fake_db = _build_client(monkeypatch)

    payload = {
        "canvas_width": 1600,
        "canvas_height": 1000,
        "outline": [
            {"x": 120, "y": 100},
            {"x": 1480, "y": 100},
            {"x": 1480, "y": 900},
            {"x": 120, "y": 900},
        ],
        "background_image_data_url": "data:image/png;base64,abc123",
        "background_image_name": "venue-plan.png",
        "background_locked": True,
        "scale_pixels": 100,
        "scale_distance": 10,
        "scale_unit": "ft",
        "fixtures": [
            {
                "id": "dance-floor-1",
                "type": "dance_floor",
                "label": "Dance Floor",
                "x": 500,
                "y": 420,
                "width": 260,
                "height": 180,
                "rotation": 0,
            }
        ],
    }
    save_response = client.put("/admin/tables/wedding-1/venue-layout", json=payload)
    get_response = client.get("/admin/tables/wedding-1/venue-layout")

    assert save_response.status_code == 200
    assert save_response.json()["outline"] == payload["outline"]
    assert save_response.json()["background_image_name"] == "venue-plan.png"
    assert save_response.json()["scale_distance"] == 10
    assert save_response.json()["fixtures"] == payload["fixtures"]
    assert save_response.json()["updated_by"] == "planner@example.com"
    assert get_response.status_code == 200
    assert get_response.json()["outline"] == payload["outline"]
    assert get_response.json()["fixtures"] == payload["fixtures"]


def test_venue_layout_requires_wedding_access(monkeypatch):
    client, _fake_db = _build_client(monkeypatch, can_access=False)

    get_response = client.get("/admin/tables/other-wedding/venue-layout")
    put_response = client.put(
        "/admin/tables/other-wedding/venue-layout",
        json={"canvas_width": 1600, "canvas_height": 1000, "outline": []},
    )

    assert get_response.status_code == 403
    assert put_response.status_code == 403

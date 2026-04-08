"""
Wedding CRUD Tests

Tests the core wedding management lifecycle: create, read, update, delete.
This is the foundational entity — most other features depend on having a wedding.
"""

import pytest

from tests.integration.conftest import extract_items


@pytest.mark.integration
class TestWeddingCRUD:
    """Test the complete wedding lifecycle."""

    def test_create_wedding(self, api):
        """Create a new wedding."""
        resp = api.post(
            "/admin/weddings",
            json={
                "couple_names": "Integration & Test",
                "date": "2026-09-15T14:00:00Z",
                "venue": "CI/CD Chapel",
                "guest_count": 100,
            },
        )
        assert resp.status_code == 200, f"Create wedding failed: {resp.text}"
        data = resp.json()
        # The response structure may vary — check for an ID
        assert "id" in data or "wedding_id" in data or "_id" in data

    def test_list_weddings(self, api):
        """List all weddings for the admin."""
        resp = api.get("/admin/weddings")
        assert resp.status_code == 200
        weddings = extract_items(resp.json(), "weddings", "items")
        assert len(weddings) >= 1

    def test_get_wedding_by_id(self, api):
        """Fetch a specific wedding by ID."""
        # First get the list to find an ID
        list_resp = api.get("/admin/weddings")
        assert list_resp.status_code == 200
        weddings = extract_items(list_resp.json(), "weddings", "items")
        assert len(weddings) > 0

        wedding_id = (
            weddings[0].get("id")
            or weddings[0].get("_id")
            or weddings[0].get("wedding_id")
        )
        assert wedding_id is not None

        resp = api.get(f"/admin/weddings/{wedding_id}")
        assert resp.status_code == 200

    def test_update_wedding(self, api):
        """Update an existing wedding."""
        list_resp = api.get("/admin/weddings")
        weddings = extract_items(list_resp.json(), "weddings", "items")
        wedding_id = weddings[0].get("id") or weddings[0].get("_id")

        resp = api.put(
            f"/admin/weddings/{wedding_id}",
            json={
                "venue": "Updated Test Venue",
                "guest_count": 150,
            },
        )
        assert resp.status_code == 200

    def test_create_second_wedding(self, api):
        """Create another wedding to verify multi-wedding support."""
        resp = api.post(
            "/admin/weddings",
            json={
                "couple_names": "Smoke & Test",
                "date": "2026-12-20T16:00:00Z",
                "venue": "Pipeline Plaza",
                "guest_count": 50,
            },
        )
        assert resp.status_code == 200

    def test_list_weddings_returns_multiple(self, api):
        """Verify multiple weddings are returned."""
        resp = api.get("/admin/weddings")
        assert resp.status_code == 200
        weddings = extract_items(resp.json(), "weddings", "items")
        assert len(weddings) >= 2

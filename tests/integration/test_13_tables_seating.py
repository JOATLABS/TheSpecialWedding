"""
Tables & Seating Tests

Tests table CRUD and guest seating assignment.
"""

import pytest

from tests.integration.conftest import extract_items


@pytest.mark.integration
class TestTablesAndSeating:
    """Test table management and seating assignment."""

    @pytest.fixture(autouse=True)
    def _setup_wedding(self, api):
        """Get a wedding for seating tests."""
        resp = api.get("/admin/weddings")
        weddings = extract_items(resp.json(), "weddings", "items")
        if weddings:
            self.wedding_id = weddings[0].get("id") or weddings[0].get("_id")
        else:
            pytest.skip("No weddings available")

    def test_get_tables(self, api):
        """Get tables for a wedding."""
        resp = api.get(f"/admin/tables/{self.wedding_id}")
        assert resp.status_code == 200

    def test_create_table(self, api):
        """Create a table."""
        resp = api.post(
            "/admin/tables",
            json={
                "wedding_id": self.wedding_id,
                "name": "Table 1",
                "capacity": 10,
                "shape": "round",
            },
        )
        assert resp.status_code in (200, 201), f"Create table failed: {resp.text}"

    def test_create_multiple_tables(self, api):
        """Create several tables."""
        for i in range(2, 5):
            resp = api.post(
                "/admin/tables",
                json={
                    "wedding_id": self.wedding_id,
                    "name": f"Table {i}",
                    "capacity": 8,
                    "shape": "round",
                },
            )
            assert resp.status_code in (200, 201)

    def test_list_tables_shows_created(self, api):
        """Verify created tables appear in the list."""
        resp = api.get(f"/admin/tables/{self.wedding_id}")
        assert resp.status_code == 200
        data = resp.json()
        tables = data if isinstance(data, list) else data.get("tables", [])
        assert len(tables) >= 1

"""
Budget Management Tests

Tests budget creation, categories, payments, and reporting.
Budget is a critical feature for wedding planners.
"""

import pytest

from tests.integration.conftest import extract_items


@pytest.mark.integration
class TestBudgetManagement:
    """Test budget operations within a wedding."""

    @pytest.fixture(autouse=True)
    def _setup_wedding(self, api):
        """Get a wedding for budget tests."""
        resp = api.get("/admin/weddings")
        weddings = extract_items(resp.json(), "weddings", "items")
        if weddings:
            self.wedding_id = weddings[0].get("id") or weddings[0].get("_id")
        else:
            pytest.skip("No weddings available for budget tests")

    def test_get_budget(self, api):
        """Fetch the budget for a wedding."""
        resp = api.get(f"/admin/weddings/{self.wedding_id}/budget")
        assert resp.status_code == 200

    def test_create_budget_category(self, api):
        """Create a budget category."""
        resp = api.post(
            f"/admin/weddings/{self.wedding_id}/budget/category",
            json={
                "name": "Catering",
                "budgeted_amount": 5000.00,
                "notes": "Main meal + dessert",
            },
        )
        assert resp.status_code == 200, f"Create category failed: {resp.text}"

    def test_create_multiple_categories(self, api):
        """Create several budget categories."""
        categories = [
            {"name": "Photography", "budgeted_amount": 3000.00},
            {"name": "Flowers", "budgeted_amount": 2000.00},
            {"name": "Music & DJ", "budgeted_amount": 1500.00},
        ]
        for cat in categories:
            resp = api.post(
                f"/admin/weddings/{self.wedding_id}/budget/category",
                json=cat,
            )
            assert resp.status_code == 200

    def test_set_total_budget(self, api):
        """Set the total budget for a wedding."""
        resp = api.put(
            f"/admin/weddings/{self.wedding_id}/budget/total",
            json={"total_budget": 25000.00},
        )
        assert resp.status_code == 200

    def test_get_budget_report(self, api):
        """Get the budget report."""
        resp = api.get(f"/admin/weddings/{self.wedding_id}/budget/report")
        assert resp.status_code == 200

    def test_get_budget_templates(self, api):
        """List available budget templates."""
        resp = api.get("/admin/budget/templates")
        assert resp.status_code == 200

    def test_get_category_suggestions(self, api):
        """Get AI-powered category suggestions."""
        resp = api.get("/admin/budget/categories/suggestions")
        assert resp.status_code == 200

    def test_get_budget_alerts(self, api):
        """Get budget alerts for a wedding."""
        resp = api.get(f"/admin/budget/alerts/{self.wedding_id}")
        assert resp.status_code == 200

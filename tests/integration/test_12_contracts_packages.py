"""
Contracts & Packages Tests

Tests the contract lifecycle and package management.
These are premium features for wedding planners.
"""

import pytest

from tests.integration.conftest import extract_items


@pytest.mark.integration
class TestContracts:
    """Test contract management."""

    def test_list_contracts(self, api):
        """List contracts."""
        resp = api.get("/admin/client-contracts")
        assert resp.status_code == 200

    def test_contract_stats(self, api):
        """Get contract statistics."""
        resp = api.get("/admin/client-contracts/stats")
        assert resp.status_code == 200

    def test_create_contract(self, api):
        """Create a basic contract."""
        # Get a wedding and vendor first
        weddings_resp = api.get("/admin/weddings")
        weddings = extract_items(weddings_resp.json(), "weddings", "items")
        if not weddings:
            pytest.skip("No weddings available for contract test")

        wedding_id = weddings[0].get("id") or weddings[0].get("_id")

        resp = api.post(
            "/admin/client-contracts",
            json={
                "wedding_id": wedding_id,
                "vendor_name": "Test Vendor Co",
                "vendor_email": "vendor@test.com",
                "service_type": "photography",
                "total_amount": 5000.00,
                "status": "draft",
            },
        )
        # 200/201 success, 422 validation error if missing required fields
        assert resp.status_code in (200, 201, 422), f"Create contract: {resp.text}"


@pytest.mark.integration
class TestPackages:
    """Test package management.

    Packages are scoped to a planner owner (fix c0c0b3ab "scope packages to
    planner owner"): every package route resolves an owner id via
    get_owner_identity and fails closed with 403 when the session has no planner
    owner scope. The integration stack only seeds a root admin, which is
    intentionally *not* a planner owner, so these routes must fail closed here.
    The owner-scoped success path (planner/team-member) is covered by the unit
    suite tests/backend/test_package_owner_scope.py.
    """

    def test_list_packages_requires_planner_owner_scope(self, api):
        """Listing packages fails closed for a non-planner (root admin) session."""
        resp = api.get("/admin/packages")
        assert resp.status_code == 403, resp.text
        assert "owner scope" in resp.text.lower()

    def test_package_stats_requires_planner_owner_scope(self, api):
        """Package stats fails closed for a non-planner (root admin) session."""
        resp = api.get("/admin/packages/stats")
        assert resp.status_code == 403, resp.text
        assert "owner scope" in resp.text.lower()

    def test_create_package_requires_planner_owner_scope(self, api):
        """Creating a package fails closed for a non-planner (root admin) session."""
        resp = api.post(
            "/admin/packages",
            json={
                "name": "Gold Photography Package",
                "description": "8 hours of coverage, 500 edited photos",
                "price": 4500.00,
                "service_type": "photography",
                "features": [
                    "8 hours coverage",
                    "500 edited photos",
                    "Online gallery",
                    "Engagement session",
                ],
            },
        )
        assert resp.status_code == 403, f"Create package: {resp.text}"
        assert "owner scope" in resp.text.lower()


@pytest.mark.integration
class TestAutopilot:
    """Test autopilot (payment automation) status."""

    def test_autopilot_status(self, api):
        """Get autopilot system status."""
        resp = api.get("/admin/autopilot/status")
        assert resp.status_code == 200

    def test_due_payments(self, api):
        """Get due payments list."""
        resp = api.get("/admin/autopilot/due-payments")
        assert resp.status_code == 200

    def test_failed_payments(self, api):
        """Get failed payments."""
        resp = api.get("/admin/autopilot/failed-payments")
        assert resp.status_code == 200

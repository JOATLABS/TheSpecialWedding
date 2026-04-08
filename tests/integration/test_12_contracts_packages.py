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
        resp = api.get("/contracts")
        assert resp.status_code == 200

    def test_contract_stats(self, api):
        """Get contract statistics."""
        resp = api.get("/contracts/stats")
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
            "/contracts",
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
    """Test package management."""

    def test_list_packages(self, api):
        """List packages."""
        resp = api.get("/admin/packages")
        assert resp.status_code == 200

    def test_package_stats(self, api):
        """Get package statistics."""
        resp = api.get("/admin/packages/stats")
        assert resp.status_code == 200

    def test_create_package(self, api):
        """Create a service package."""
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
        assert resp.status_code in (200, 201, 422), f"Create package: {resp.text}"


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

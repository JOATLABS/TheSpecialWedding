"""
Vendor Management Tests

Tests vendor directory, vendor assignment to weddings, and vendor forms.
"""

import pytest

from tests.integration.conftest import extract_items


@pytest.mark.integration
class TestVendorManagement:
    """Test vendor CRUD and assignment operations."""

    def test_list_vendor_categories(self, api):
        """Get vendor categories."""
        resp = api.get("/admin/directory/categories")
        assert resp.status_code == 200

    def test_create_vendor(self, api):
        """Create a vendor in the directory."""
        resp = api.post(
            "/admin/directory",
            json={
                "business_name": "Test Photography Co",
                "contact_name": "Jamie Lens",
                "email": "photo@test.com",
                "phone": "+15559876543",
                "service_category": "photographer",
                "service_description": "Integration test photographer",
                "city": "Test City",
                "source": "manual",
            },
        )
        assert resp.status_code in (200, 201), f"Create vendor failed: {resp.text}"

    def test_list_vendors(self, api):
        """List vendors in the directory."""
        resp = api.get("/admin/directory")
        assert resp.status_code == 200

    def test_get_vendor_by_id(self, api):
        """Fetch a specific vendor."""
        list_resp = api.get("/admin/directory")
        data = list_resp.json()
        vendors = (
            data
            if isinstance(data, list)
            else data.get("vendors", data.get("items", []))
        )

        if not vendors:
            pytest.skip("No vendors available")

        vendor_id = vendors[0].get("id") or vendors[0].get("_id")
        resp = api.get(f"/admin/directory/{vendor_id}")
        assert resp.status_code == 200

    def test_assign_vendor_to_wedding(self, api):
        """Assign a vendor to a wedding."""
        # Get a vendor
        vendor_resp = api.get("/admin/directory")
        vendor_data = vendor_resp.json()
        vendors = (
            vendor_data
            if isinstance(vendor_data, list)
            else vendor_data.get("vendors", vendor_data.get("items", []))
        )

        # Get a wedding
        wedding_resp = api.get("/admin/weddings")
        weddings = extract_items(wedding_resp.json(), "weddings", "items")

        if not vendors or not weddings:
            pytest.skip("Need both vendors and weddings for assignment test")

        vendor_id = vendors[0].get("id") or vendors[0].get("_id")
        wedding_id = weddings[0].get("id") or weddings[0].get("_id")

        resp = api.post(
            "/admin/assign",
            json={
                "vendor_profile_id": vendor_id,
                "wedding_id": wedding_id,
                "service_notes": "Integration assignment",
            },
        )
        # 200 (success) or 409 (already assigned) both OK
        assert resp.status_code in (200, 201, 409), f"Assign vendor failed: {resp.text}"

    def test_get_wedding_vendors(self, api):
        """Get vendors assigned to a wedding."""
        wedding_resp = api.get("/admin/weddings")
        weddings = extract_items(wedding_resp.json(), "weddings", "items")
        if not weddings:
            pytest.skip("No weddings available")

        wedding_id = weddings[0].get("id") or weddings[0].get("_id")
        resp = api.get(f"/admin/weddings/{wedding_id}/vendors")
        assert resp.status_code == 200

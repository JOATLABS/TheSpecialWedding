"""
RSVP Flow Tests

Tests the end-to-end RSVP workflow:
1. Admin creates a guest with an invite token
2. Guest accesses their invite via token
3. Guest submits their RSVP
4. Admin can see the RSVP in the dashboard
"""

import pytest

from tests.integration.conftest import extract_items


@pytest.mark.integration
class TestRSVPFlow:
    """Test the complete guest RSVP journey."""

    def test_admin_rsvp_list(self, api):
        """Admin can list RSVPs."""
        # First get a wedding ID
        weddings_resp = api.get("/admin/weddings")
        weddings = extract_items(weddings_resp.json(), "weddings", "items")
        if not weddings:
            pytest.skip("No weddings available for RSVP tests")

        wedding_id = weddings[0].get("id") or weddings[0].get("_id")
        resp = api.get(f"/admin/rsvps?wedding_id={wedding_id}")
        assert resp.status_code == 200

    def test_admin_can_create_rsvp(self, api):
        """Admin can manually create/update an RSVP for a guest."""
        # Get a guest to RSVP for
        weddings_resp = api.get("/admin/weddings")
        weddings = extract_items(weddings_resp.json(), "weddings", "items")
        if not weddings:
            pytest.skip("No weddings available")

        wedding_id = weddings[0].get("id") or weddings[0].get("_id")
        guests_resp = api.get(f"/admin/guests?wedding_id={wedding_id}")
        guests_data = guests_resp.json()
        guests = (
            guests_data
            if isinstance(guests_data, list)
            else guests_data.get("guests", guests_data.get("items", []))
        )

        if not guests:
            pytest.skip("No guests available for RSVP test")

        guest_id = (
            guests[0].get("id") or guests[0].get("_id") or guests[0].get("guest_id")
        )

        resp = api.put(
            f"/admin/rsvps/{guest_id}",
            json={
                "status": "attending",
                "meal_preference": "chicken",
                "plus_one": False,
            },
        )
        # Accept 200 or 201
        assert resp.status_code in (200, 201), f"Admin RSVP failed: {resp.text}"

    def test_rsvp_export(self, api):
        """Admin can export RSVPs as CSV."""
        weddings_resp = api.get("/admin/weddings")
        weddings = extract_items(weddings_resp.json(), "weddings", "items")
        if not weddings:
            pytest.skip("No weddings available")

        wedding_id = weddings[0].get("id") or weddings[0].get("_id")
        resp = api.get(f"/admin/rsvps/export?wedding_id={wedding_id}")
        # Should return CSV data or 200
        assert resp.status_code == 200

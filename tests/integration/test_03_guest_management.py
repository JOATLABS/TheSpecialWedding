"""
Guest Management Tests

Tests guest CRUD operations, CSV import readiness, and guest listing.
Guests are the second most critical entity after weddings.
"""

import pytest

from tests.integration.conftest import extract_items


@pytest.mark.integration
class TestGuestManagement:
    """Test guest creation and management within a wedding."""

    def _create_guest(self, api, **overrides):
        payload = {
            "name": "Test Guest",
            "email": "test-guest@example.com",
            "role": "guest",
            "group_id": "friends",
            "plus_one_allowed": False,
            "number_of_plus_ones_allowed": 0,
        }
        payload.update(overrides)
        return api.post(
            f"/admin/guests?wedding_id={self.wedding_id}",
            json=payload,
        )

    @pytest.fixture(autouse=True)
    def _setup_wedding(self, api):
        """Ensure we have a wedding to add guests to."""
        resp = api.get("/admin/weddings")
        weddings = extract_items(resp.json(), "weddings", "items")
        if weddings:
            self.wedding_id = weddings[0].get("id") or weddings[0].get("_id")
        else:
            create_resp = api.post(
                "/admin/weddings",
                json={
                    "couple_names": "Guest & Test",
                    "date": "2026-08-01T12:00:00Z",
                    "venue": "Test Hall",
                },
            )
            data = create_resp.json()
            self.wedding_id = (
                data.get("id") or data.get("wedding_id") or data.get("_id")
            )

    def test_create_guest(self, api):
        """Create a new guest."""
        resp = self._create_guest(
            api,
            name="Jane Tester",
            email="jane@test.com",
            phone="+15551234567",
            plus_one_allowed=True,
            number_of_plus_ones_allowed=1,
        )
        assert resp.status_code == 200, f"Create guest failed: {resp.text}"

    def test_create_guest_minimal(self, api):
        """Create a guest with the minimum required data."""
        resp = self._create_guest(api, name="John Minimal", email="john@test.com")
        assert resp.status_code == 200

    def test_list_guests(self, api):
        """List guests for a wedding."""
        resp = api.get(f"/admin/guests?wedding_id={self.wedding_id}")
        assert resp.status_code == 200
        data = resp.json()
        guests = extract_items(data, "guests", "items")
        assert len(guests) >= 1

    def test_update_guest(self, api):
        """Update an existing guest."""
        # Get guest list
        resp = api.get(f"/admin/guests?wedding_id={self.wedding_id}")
        data = resp.json()
        guests = extract_items(data, "guests", "items")
        assert len(guests) > 0

        guest_id = (
            guests[0].get("id") or guests[0].get("_id") or guests[0].get("guest_id")
        )

        update_resp = api.put(
            f"/admin/guests/{guest_id}",
            json={"name": "Jane Updated", "group_id": "vip"},
        )
        assert update_resp.status_code == 200

    def test_create_guest_missing_name_fails(self, api):
        """Creating a guest without a name should fail."""
        resp = api.post(
            f"/admin/guests?wedding_id={self.wedding_id}",
            json={"email": "missing-name@test.com"},
        )
        assert resp.status_code == 422

    def test_create_guest_without_contact_fails(self, api):
        """Creating a guest without phone or email should fail."""
        resp = api.post(
            f"/admin/guests?wedding_id={self.wedding_id}",
            json={"name": "No Contact"},
        )
        assert resp.status_code == 400

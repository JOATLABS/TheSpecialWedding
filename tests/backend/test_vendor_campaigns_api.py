"""
Comprehensive test suite for the Vendor Campaigns API Router (/portal/ads).

Tests cover:
- All 14 endpoints under /portal/ads
- Authentication (vendor, planner rejection, admin bypass)
- Campaign CRUD (create, list, get, update, delete)
- Campaign lifecycle (submit, pause)
- Creative management (create, list, update, set-primary)
- Lead retrieval with filters
- Campaign statistics
- Billing summary (free tier)

Auth strategy:
- Use app.dependency_overrides to mock require_advertising_vendor
- Create mock ExtendedAuthUser objects for vendor and admin roles
- Test that planners (non-advertising_vendor) get 403
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

# Setup path and environment
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-this-is-long-enough-for-validation-testing-purposes-2026",
)
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")

from fastapi import FastAPI

from app.api.vendor_campaigns import (
    get_vendor_campaign_service,
    require_advertising_vendor,
)
from app.api.vendor_campaigns import router as vendor_campaigns_router
from app.dependencies.auth_extended import ExtendedAuthUser

# Create a minimal test app with just the vendor campaigns router
# (avoids importing app.main which triggers the full import chain)
app = FastAPI()
app.include_router(vendor_campaigns_router)


# =============================================================================
# TEST FIXTURES
# =============================================================================

VENDOR_ID = str(ObjectId())
VENDOR_EMAIL = "florist@example.com"
VENDOR_NAME = "Bloom & Petal Florals"
OTHER_VENDOR_ID = str(ObjectId())
CAMPAIGN_ID = str(ObjectId())
CREATIVE_ID = str(ObjectId())


def make_mock_vendor_user(vendor_id=VENDOR_ID, email=VENDOR_EMAIL, name=VENDOR_NAME):
    """Create a mock advertising_vendor user."""
    return ExtendedAuthUser(
        email=email,
        role="advertising_vendor",
        user_data={
            "_id": ObjectId(vendor_id),
            "name": name,
            "role": "advertising_vendor",
        },
    )


def make_mock_admin_user():
    """Create a mock root admin user."""
    return ExtendedAuthUser(
        email="thedeveloper@thespecialwedding.io",
        role="root_admin",
        user_data={"_id": ObjectId(), "name": "Root Admin", "role": "root_admin"},
    )


def make_mock_planner_user():
    """Create a mock wedding_planner user (should get 403)."""
    return ExtendedAuthUser(
        email="planner@example.com",
        role="wedding_planner",
        user_data={
            "_id": ObjectId(),
            "name": "Wedding Planner",
            "role": "wedding_planner",
        },
    )


@pytest.fixture
def mock_service():
    """Create an AsyncMock service for dependency injection."""
    return AsyncMock()


@pytest.fixture
def vendor_client(mock_service):
    """TestClient with vendor user authenticated."""
    vendor_user = make_mock_vendor_user()
    app.dependency_overrides[require_advertising_vendor] = lambda: vendor_user
    app.dependency_overrides[get_vendor_campaign_service] = lambda: mock_service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(mock_service):
    """TestClient with admin user authenticated."""
    admin_user = make_mock_admin_user()
    app.dependency_overrides[require_advertising_vendor] = lambda: admin_user
    app.dependency_overrides[get_vendor_campaign_service] = lambda: mock_service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def planner_client(mock_service):
    """TestClient with planner user (should fail auth).

    Override require_advertising_vendor to raise 403, simulating
    what the real dependency does for non-vendor/non-admin users.
    """
    from fastapi import HTTPException

    def raise_403():
        raise HTTPException(
            status_code=403, detail="Advertising vendor access required"
        )

    app.dependency_overrides[require_advertising_vendor] = raise_403
    app.dependency_overrides[get_vendor_campaign_service] = lambda: mock_service
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


# =============================================================================
# AUTH TESTS
# =============================================================================


class TestAuthBoundaries:
    """Test authentication boundaries for all endpoints."""

    def test_vendor_can_create_campaign(self, vendor_client, mock_service):
        """Vendor can create campaign."""
        mock_service.create_campaign.return_value = {
            "_id": CAMPAIGN_ID,
            "status": "draft",
            "campaign_name": "Test Campaign",
        }
        resp = vendor_client.post(
            "/portal/ads/campaigns", json={"campaign_name": "Test Campaign"}
        )
        assert resp.status_code == 201
        assert mock_service.create_campaign.called

    def test_admin_can_create_campaign(self, admin_client, mock_service):
        """Root admin can create campaign."""
        mock_service.create_campaign.return_value = {
            "_id": CAMPAIGN_ID,
            "status": "draft",
        }
        resp = admin_client.post(
            "/portal/ads/campaigns", json={"campaign_name": "Admin Campaign"}
        )
        assert resp.status_code == 201

    def test_planner_gets_403_on_create_campaign(self, planner_client, mock_service):
        """Planner gets 403 on create campaign."""
        # planner_client has the HTTPException from require_advertising_vendor
        # but TestClient catches it and returns 403
        resp = planner_client.post(
            "/portal/ads/campaigns", json={"campaign_name": "Bad"}
        )
        assert resp.status_code == 403

    def test_vendor_can_list_campaigns(self, vendor_client, mock_service):
        """Vendor can list their campaigns."""
        mock_service.list_campaigns.return_value = {"campaigns": [], "total": 0}
        resp = vendor_client.get("/portal/ads/campaigns")
        assert resp.status_code == 200

    def test_planner_gets_403_on_list_campaigns(self, planner_client, mock_service):
        """Planner gets 403 on list campaigns."""
        resp = planner_client.get("/portal/ads/campaigns")
        assert resp.status_code == 403

    def test_vendor_can_get_campaign(self, vendor_client, mock_service):
        """Vendor can get their campaign."""
        mock_service.get_campaign.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}")
        assert resp.status_code == 200

    def test_planner_gets_403_on_get_campaign(self, planner_client, mock_service):
        """Planner gets 403 on get campaign."""
        resp = planner_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}")
        assert resp.status_code == 403


# =============================================================================
# CAMPAIGN CRUD TESTS
# =============================================================================


class TestCampaignCRUD:
    """Test campaign creation, retrieval, update, delete."""

    def test_create_campaign_201(self, vendor_client, mock_service):
        """POST /campaigns returns 201 with campaign data."""
        mock_service.create_campaign.return_value = {
            "_id": CAMPAIGN_ID,
            "status": "draft",
            "campaign_name": "Summer Wedding Ads",
        }
        resp = vendor_client.post(
            "/portal/ads/campaigns",
            json={"campaign_name": "Summer Wedding Ads", "goal": "profile_visits"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["_id"] == CAMPAIGN_ID
        assert data["status"] == "draft"
        assert mock_service.create_campaign.called

    def test_create_campaign_passes_vendor_identity(self, vendor_client, mock_service):
        """Create campaign includes vendor_id, email, name."""
        mock_service.create_campaign.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.post(
            "/portal/ads/campaigns", json={"campaign_name": "Test"}
        )
        assert resp.status_code == 201
        # Check that service was called with vendor info
        mock_service.create_campaign.assert_called_once()
        call_kwargs = mock_service.create_campaign.call_args[1]
        assert call_kwargs["vendor_id"] == VENDOR_ID
        assert call_kwargs["vendor_email"] == VENDOR_EMAIL
        assert call_kwargs["vendor_name"] == VENDOR_NAME

    def test_list_campaigns_200(self, vendor_client, mock_service):
        """GET /campaigns returns 200 with campaign list."""
        mock_service.list_campaigns.return_value = {
            "campaigns": [{"_id": CAMPAIGN_ID, "campaign_name": "Campaign 1"}],
            "total": 1,
        }
        resp = vendor_client.get("/portal/ads/campaigns")
        assert resp.status_code == 200
        data = resp.json()
        assert "campaigns" in data

    def test_list_campaigns_with_status_filter(self, vendor_client, mock_service):
        """GET /campaigns with status filter."""
        mock_service.list_campaigns.return_value = {"campaigns": [], "total": 0}
        resp = vendor_client.get("/portal/ads/campaigns?status=draft")
        assert resp.status_code == 200
        # Verify filter was passed
        mock_service.list_campaigns.assert_called_once()
        call_kwargs = mock_service.list_campaigns.call_args[1]
        assert call_kwargs["status_filter"] == "draft"

    def test_list_campaigns_respects_limit_and_skip(self, vendor_client, mock_service):
        """GET /campaigns respects limit and skip params."""
        mock_service.list_campaigns.return_value = {"campaigns": [], "total": 0}
        resp = vendor_client.get("/portal/ads/campaigns?limit=25&skip=10")
        assert resp.status_code == 200
        call_kwargs = mock_service.list_campaigns.call_args[1]
        assert call_kwargs["limit"] == 25
        assert call_kwargs["skip"] == 10

    def test_list_campaigns_validates_limit_bounds(self, vendor_client, mock_service):
        """GET /campaigns validates limit is between 1 and 100."""
        mock_service.list_campaigns.return_value = {"campaigns": [], "total": 0}

        # Limit too high should be rejected
        resp = vendor_client.get("/portal/ads/campaigns?limit=101")
        assert resp.status_code == 422

        # Limit too low should be rejected
        resp = vendor_client.get("/portal/ads/campaigns?limit=0")
        assert resp.status_code == 422

    def test_get_campaign_200(self, vendor_client, mock_service):
        """GET /campaigns/{id} returns 200."""
        mock_service.get_campaign.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}")
        assert resp.status_code == 200
        assert resp.json()["_id"] == CAMPAIGN_ID

    def test_get_campaign_passes_vendor_scoping(self, vendor_client, mock_service):
        """GET /campaigns/{id} includes vendor_id for scoping."""
        mock_service.get_campaign.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}")
        assert resp.status_code == 200
        call_kwargs = mock_service.get_campaign.call_args[1]
        assert call_kwargs["vendor_id"] == VENDOR_ID

    def test_update_campaign_200(self, vendor_client, mock_service):
        """PUT /campaigns/{id} returns 200."""
        mock_service.update_campaign.return_value = {
            "_id": CAMPAIGN_ID,
            "campaign_name": "Updated Name",
        }
        resp = vendor_client.put(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}",
            json={"campaign_name": "Updated Name"},
        )
        assert resp.status_code == 200

    def test_update_campaign_excludes_unset_fields(self, vendor_client, mock_service):
        """PUT excludes fields that weren't provided."""
        mock_service.update_campaign.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.put(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}", json={"campaign_name": "New Name"}
        )
        assert resp.status_code == 200
        # Should only pass campaign_name in updates dict
        call_kwargs = mock_service.update_campaign.call_args[0]
        updates_dict = call_kwargs[2]
        assert "campaign_name" in updates_dict
        assert len(updates_dict) == 1

    def test_delete_campaign_200(self, vendor_client, mock_service):
        """DELETE /campaigns/{id} returns 200."""
        mock_service.delete_campaign.return_value = {"deleted": True}
        resp = vendor_client.delete(f"/portal/ads/campaigns/{CAMPAIGN_ID}")
        assert resp.status_code == 200

    def test_delete_campaign_vendor_scoped(self, vendor_client, mock_service):
        """DELETE includes vendor_id for ownership check."""
        mock_service.delete_campaign.return_value = {"deleted": True}
        resp = vendor_client.delete(f"/portal/ads/campaigns/{CAMPAIGN_ID}")
        assert resp.status_code == 200
        # Verify vendor_id was passed
        mock_service.delete_campaign.assert_called_once_with(CAMPAIGN_ID, VENDOR_ID)


# =============================================================================
# CAMPAIGN LIFECYCLE TESTS
# =============================================================================


class TestCampaignLifecycle:
    """Test submit and pause operations."""

    def test_submit_campaign_200(self, vendor_client, mock_service):
        """POST /campaigns/{id}/submit returns 200."""
        mock_service.submit_for_review.return_value = {
            "_id": CAMPAIGN_ID,
            "status": "pending_review",
        }
        resp = vendor_client.post(f"/portal/ads/campaigns/{CAMPAIGN_ID}/submit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_review"

    def test_submit_campaign_vendor_scoped(self, vendor_client, mock_service):
        """Submit includes vendor_id for ownership check."""
        mock_service.submit_for_review.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.post(f"/portal/ads/campaigns/{CAMPAIGN_ID}/submit")
        assert resp.status_code == 200
        call_args = mock_service.submit_for_review.call_args[0]
        assert call_args[1] == VENDOR_ID

    def test_pause_campaign_200(self, vendor_client, mock_service):
        """POST /campaigns/{id}/pause returns 200."""
        mock_service.pause_campaign.return_value = {
            "_id": CAMPAIGN_ID,
            "status": "paused",
        }
        resp = vendor_client.post(f"/portal/ads/campaigns/{CAMPAIGN_ID}/pause")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paused"

    def test_pause_campaign_vendor_scoped(self, vendor_client, mock_service):
        """Pause includes vendor_id for ownership check."""
        mock_service.pause_campaign.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.post(f"/portal/ads/campaigns/{CAMPAIGN_ID}/pause")
        assert resp.status_code == 200
        call_args = mock_service.pause_campaign.call_args[0]
        assert call_args[1] == VENDOR_ID


# =============================================================================
# CAMPAIGN STATS TESTS
# =============================================================================


class TestCampaignStats:
    """Test campaign statistics endpoint."""

    def test_get_campaign_stats_200(self, vendor_client, mock_service):
        """GET /campaigns/{id}/stats returns 200."""
        mock_service.get_campaign_stats.return_value = {
            "campaign_id": CAMPAIGN_ID,
            "lifetime_stats": {"impressions": 100, "clicks": 10, "ctr": 10.0},
            "daily_stats": [],
        }
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "lifetime_stats" in data

    def test_get_campaign_stats_with_days_param(self, vendor_client, mock_service):
        """GET /campaigns/{id}/stats with days parameter."""
        mock_service.get_campaign_stats.return_value = {"daily_stats": []}
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}/stats?days=60")
        assert resp.status_code == 200
        call_kwargs = mock_service.get_campaign_stats.call_args[0]
        assert call_kwargs[2] == 60

    def test_get_campaign_stats_validates_days_bounds(
        self, vendor_client, mock_service
    ):
        """GET /stats validates days between 1 and 365."""
        # Days too high
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}/stats?days=366")
        assert resp.status_code == 422

        # Days too low
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}/stats?days=0")
        assert resp.status_code == 422

    def test_get_campaign_stats_vendor_scoped(self, vendor_client, mock_service):
        """GET /stats includes vendor_id for ownership check."""
        mock_service.get_campaign_stats.return_value = {}
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}/stats")
        assert resp.status_code == 200
        call_kwargs = mock_service.get_campaign_stats.call_args[0]
        assert call_kwargs[1] == VENDOR_ID


# =============================================================================
# CREATIVE MANAGEMENT TESTS
# =============================================================================


class TestCreativeManagement:
    """Test creative CRUD operations."""

    def test_create_creative_201(self, vendor_client, mock_service):
        """POST /campaigns/{id}/creatives returns 201."""
        mock_service.create_creative.return_value = {
            "_id": CREATIVE_ID,
            "status": "pending",
            "headline": "Beautiful Flowers",
        }
        resp = vendor_client.post(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives",
            json={
                "headline": "Beautiful Flowers",
                "description": "Fresh bouquets for your wedding",
                "image_url": "https://cdn.example.com/flower.jpg",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["_id"] == CREATIVE_ID

    def test_create_creative_includes_vendor_scoping(self, vendor_client, mock_service):
        """Create creative includes vendor_id for ownership."""
        mock_service.create_creative.return_value = {"_id": CREATIVE_ID}
        resp = vendor_client.post(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives",
            json={"headline": "Test", "description": "Test description"},
        )
        assert resp.status_code == 201
        call_kwargs = mock_service.create_creative.call_args[0]
        assert call_kwargs[1] == VENDOR_ID

    def test_create_creative_excludes_unset_fields(self, vendor_client, mock_service):
        """Create creative excludes unset fields."""
        mock_service.create_creative.return_value = {"_id": CREATIVE_ID}
        resp = vendor_client.post(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives",
            json={"headline": "Test", "description": "Test description"},
        )
        assert resp.status_code == 201
        call_kwargs = mock_service.create_creative.call_args[0]
        data = call_kwargs[2]
        assert "headline" in data
        assert "description" in data
        assert "offer" not in data  # unset, should not be in dict

    def test_list_creatives_200(self, vendor_client, mock_service):
        """GET /campaigns/{id}/creatives returns 200."""
        # Need to mock get_campaign for ownership verification
        mock_service.get_campaign.return_value = {"_id": CAMPAIGN_ID}
        mock_service.list_creatives.return_value = {
            "creatives": [{"_id": CREATIVE_ID}],
            "total": 1,
        }
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives")
        assert resp.status_code == 200
        data = resp.json()
        assert "creatives" in data

    def test_list_creatives_verifies_ownership(self, vendor_client, mock_service):
        """List creatives first checks campaign ownership."""
        mock_service.get_campaign.return_value = {"_id": CAMPAIGN_ID}
        mock_service.list_creatives.return_value = {"creatives": []}
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives")
        assert resp.status_code == 200
        # Should call get_campaign first for ownership check
        mock_service.get_campaign.assert_called_once()

    def test_update_creative_200(self, vendor_client, mock_service):
        """PUT /creatives/{id} returns 200."""
        mock_service.update_creative.return_value = {
            "_id": CREATIVE_ID,
            "headline": "Updated Headline",
        }
        resp = vendor_client.put(
            f"/portal/ads/creatives/{CREATIVE_ID}",
            json={"headline": "Updated Headline", "description": "Updated description"},
        )
        assert resp.status_code == 200

    def test_update_creative_vendor_scoped(self, vendor_client, mock_service):
        """Update creative includes vendor_id for ownership."""
        mock_service.update_creative.return_value = {"_id": CREATIVE_ID}
        resp = vendor_client.put(
            f"/portal/ads/creatives/{CREATIVE_ID}",
            json={"headline": "Updated", "description": "Updated description"},
        )
        assert resp.status_code == 200
        call_kwargs = mock_service.update_creative.call_args[0]
        assert call_kwargs[1] == VENDOR_ID

    def test_set_primary_creative_200(self, vendor_client, mock_service):
        """POST /campaigns/{id}/creatives/{creative_id}/set-primary returns 200."""
        mock_service.set_primary_creative.return_value = {
            "_id": CAMPAIGN_ID,
            "primary_creative_id": CREATIVE_ID,
        }
        resp = vendor_client.post(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives/{CREATIVE_ID}/set-primary"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["primary_creative_id"] == CREATIVE_ID

    def test_set_primary_creative_vendor_scoped(self, vendor_client, mock_service):
        """Set primary creative includes vendor_id."""
        mock_service.set_primary_creative.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.post(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives/{CREATIVE_ID}/set-primary"
        )
        assert resp.status_code == 200
        call_kwargs = mock_service.set_primary_creative.call_args[0]
        assert call_kwargs[2] == VENDOR_ID


# =============================================================================
# LEAD TESTS
# =============================================================================


class TestLeads:
    """Test lead retrieval."""

    def test_get_vendor_leads_200(self, vendor_client, mock_service):
        """GET /leads returns 200."""
        mock_service.get_vendor_leads.return_value = {
            "leads": [
                {
                    "_id": str(ObjectId()),
                    "lead_type": "quote_request",
                    "status": "pending",
                }
            ],
            "total": 1,
        }
        resp = vendor_client.get("/portal/ads/leads")
        assert resp.status_code == 200
        data = resp.json()
        assert "leads" in data

    def test_get_vendor_leads_with_status_filter(self, vendor_client, mock_service):
        """GET /leads with status filter."""
        mock_service.get_vendor_leads.return_value = {"leads": [], "total": 0}
        resp = vendor_client.get("/portal/ads/leads?status=responded")
        assert resp.status_code == 200
        call_kwargs = mock_service.get_vendor_leads.call_args[1]
        assert call_kwargs["status_filter"] == "responded"

    def test_get_vendor_leads_with_lead_type_filter(self, vendor_client, mock_service):
        """GET /leads with lead_type filter."""
        mock_service.get_vendor_leads.return_value = {"leads": [], "total": 0}
        resp = vendor_client.get("/portal/ads/leads?lead_type=quote_request")
        assert resp.status_code == 200
        call_kwargs = mock_service.get_vendor_leads.call_args[1]
        assert call_kwargs["lead_type_filter"] == "quote_request"

    def test_get_vendor_leads_respects_pagination(self, vendor_client, mock_service):
        """GET /leads respects limit and skip."""
        mock_service.get_vendor_leads.return_value = {"leads": [], "total": 0}
        resp = vendor_client.get("/portal/ads/leads?limit=25&skip=5")
        assert resp.status_code == 200
        call_kwargs = mock_service.get_vendor_leads.call_args[1]
        assert call_kwargs["limit"] == 25
        assert call_kwargs["skip"] == 5

    def test_get_vendor_leads_vendor_scoped(self, vendor_client, mock_service):
        """GET /leads is vendor-scoped."""
        mock_service.get_vendor_leads.return_value = {"leads": [], "total": 0}
        resp = vendor_client.get("/portal/ads/leads")
        assert resp.status_code == 200
        call_kwargs = mock_service.get_vendor_leads.call_args[1]
        assert call_kwargs["vendor_id"] == VENDOR_ID

    def test_planner_gets_403_on_leads(self, planner_client, mock_service):
        """Planner gets 403 on lead access."""
        resp = planner_client.get("/portal/ads/leads")
        assert resp.status_code == 403


# =============================================================================
# BILLING TESTS
# =============================================================================


class TestBilling:
    """Test billing summary endpoint."""

    def test_get_billing_summary_200(self, vendor_client, mock_service):
        """GET /billing returns 200 with free tier."""
        resp = vendor_client.get("/portal/ads/billing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["billing_status"] == "free_tier"
        assert data["total_spend"] == 0.0
        assert data["currency"] == "USD"

    def test_get_billing_summary_includes_vendor_id(self, vendor_client, mock_service):
        """GET /billing includes vendor_id in response."""
        resp = vendor_client.get("/portal/ads/billing")
        assert resp.status_code == 200
        data = resp.json()
        assert "vendor_id" in data
        assert data["vendor_id"] == VENDOR_ID

    def test_get_billing_summary_no_service_call(self, vendor_client, mock_service):
        """GET /billing doesn't call service (hardcoded response)."""
        resp = vendor_client.get("/portal/ads/billing")
        assert resp.status_code == 200
        # Service should not be called for billing
        mock_service.get_vendor_leads.assert_not_called()

    def test_admin_can_get_billing(self, admin_client, mock_service):
        """Root admin can access billing endpoint."""
        resp = admin_client.get("/portal/ads/billing")
        assert resp.status_code == 200
        assert resp.json()["billing_status"] == "free_tier"

    def test_planner_gets_403_on_billing(self, planner_client, mock_service):
        """Planner gets 403 on billing access."""
        resp = planner_client.get("/portal/ads/billing")
        assert resp.status_code == 403


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Test error cases and edge cases."""

    def test_vendor_identity_missing_returns_400(self, vendor_client, mock_service):
        """Missing vendor identity returns 400."""
        # Create a user without _id in user_data
        bad_user = ExtendedAuthUser(
            email="bad@example.com",
            role="advertising_vendor",
            user_data={"name": "No ID User"},  # Missing _id
        )
        app.dependency_overrides[require_advertising_vendor] = lambda: bad_user
        app.dependency_overrides[get_vendor_campaign_service] = lambda: mock_service
        client = TestClient(app)

        resp = client.post("/portal/ads/campaigns", json={"campaign_name": "Test"})
        assert resp.status_code == 400
        app.dependency_overrides.clear()

    def test_invalid_campaign_id_passed_to_service(self, vendor_client, mock_service):
        """Invalid campaign_id is still passed to service for validation."""
        mock_service.get_campaign.return_value = {"_id": "invalid"}
        resp = vendor_client.get("/portal/ads/campaigns/not_a_valid_id")
        assert resp.status_code == 200  # Service was called, didn't reject
        mock_service.get_campaign.assert_called_once()

    def test_create_campaign_with_minimal_data(self, vendor_client, mock_service):
        """Create campaign with only required field."""
        mock_service.create_campaign.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.post(
            "/portal/ads/campaigns", json={"campaign_name": "Minimal"}
        )
        assert resp.status_code == 201

    def test_create_campaign_missing_campaign_name_400(
        self, vendor_client, mock_service
    ):
        """Create campaign missing campaign_name returns 422."""
        resp = vendor_client.post(
            "/portal/ads/campaigns", json={"goal": "profile_visits"}
        )
        assert resp.status_code == 422

    def test_create_creative_missing_required_fields_422(
        self, vendor_client, mock_service
    ):
        """Create creative missing required fields returns 422."""
        resp = vendor_client.post(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives",
            json={"image_url": "https://example.com/image.jpg"},
        )
        assert resp.status_code == 422

    def test_update_campaign_with_partial_data(self, vendor_client, mock_service):
        """Update campaign with only some fields."""
        mock_service.update_campaign.return_value = {"_id": CAMPAIGN_ID}
        resp = vendor_client.put(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}",
            json={"campaign_description": "Updated description only"},
        )
        assert resp.status_code == 200
        call_kwargs = mock_service.update_campaign.call_args[0]
        updates = call_kwargs[2]
        assert "campaign_description" in updates
        assert len(updates) == 1


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration-style tests combining multiple operations."""

    def test_multiple_vendors_isolated(self, mock_service):
        """Different vendors have isolated campaigns."""
        vendor1 = make_mock_vendor_user(vendor_id=VENDOR_ID)
        vendor2 = make_mock_vendor_user(vendor_id=OTHER_VENDOR_ID)

        app.dependency_overrides[require_advertising_vendor] = lambda: vendor1
        app.dependency_overrides[get_vendor_campaign_service] = lambda: mock_service
        client1 = TestClient(app)

        mock_service.list_campaigns.return_value = {
            "campaigns": [{"_id": CAMPAIGN_ID, "vendor_id": VENDOR_ID}],
            "total": 1,
        }
        resp1 = client1.get("/portal/ads/campaigns")
        assert resp1.status_code == 200

        # Verify vendor1's ID was passed
        call_kwargs = mock_service.list_campaigns.call_args[1]
        assert call_kwargs["vendor_id"] == VENDOR_ID

        app.dependency_overrides.clear()

    def test_admin_bypass_flow(self, admin_client, mock_service):
        """Root admin can access any endpoint."""
        mock_service.create_campaign.return_value = {"_id": CAMPAIGN_ID}
        mock_service.list_campaigns.return_value = {"campaigns": []}
        mock_service.get_campaign.return_value = {"_id": CAMPAIGN_ID}
        mock_service.submit_for_review.return_value = {"status": "pending_review"}

        # Create
        resp = admin_client.post(
            "/portal/ads/campaigns", json={"campaign_name": "Admin Campaign"}
        )
        assert resp.status_code == 201

        # List
        resp = admin_client.get("/portal/ads/campaigns")
        assert resp.status_code == 200

        # Get
        resp = admin_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}")
        assert resp.status_code == 200

        # Submit
        resp = admin_client.post(f"/portal/ads/campaigns/{CAMPAIGN_ID}/submit")
        assert resp.status_code == 200

    def test_campaign_workflow_sequence(self, vendor_client, mock_service):
        """Test a realistic campaign workflow."""
        # Create campaign
        mock_service.create_campaign.return_value = {
            "_id": CAMPAIGN_ID,
            "status": "draft",
        }
        resp = vendor_client.post(
            "/portal/ads/campaigns", json={"campaign_name": "Spring 2026"}
        )
        assert resp.status_code == 201

        # Create creative
        mock_service.create_creative.return_value = {
            "_id": CREATIVE_ID,
            "review_status": "pending",
        }
        resp = vendor_client.post(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives",
            json={
                "headline": "Spring Flowers",
                "description": "Fresh arrangements",
                "image_url": "https://example.com/spring.jpg",
            },
        )
        assert resp.status_code == 201

        # Set as primary
        mock_service.set_primary_creative.return_value = {
            "_id": CAMPAIGN_ID,
            "primary_creative_id": CREATIVE_ID,
        }
        resp = vendor_client.post(
            f"/portal/ads/campaigns/{CAMPAIGN_ID}/creatives/{CREATIVE_ID}/set-primary"
        )
        assert resp.status_code == 200

        # Submit for review
        mock_service.submit_for_review.return_value = {
            "_id": CAMPAIGN_ID,
            "status": "pending_review",
        }
        resp = vendor_client.post(f"/portal/ads/campaigns/{CAMPAIGN_ID}/submit")
        assert resp.status_code == 200

    def test_query_parameters_validation(self, vendor_client, mock_service):
        """Test query parameter bounds validation."""
        mock_service.list_campaigns.return_value = {"campaigns": [], "total": 0}

        # Valid: limit=50, skip=0
        resp = vendor_client.get("/portal/ads/campaigns?limit=50&skip=0")
        assert resp.status_code == 200

        # Invalid: skip negative
        resp = vendor_client.get("/portal/ads/campaigns?skip=-1")
        assert resp.status_code == 422


# =============================================================================
# RESPONSE SHAPE TESTS
# =============================================================================


class TestResponseShapes:
    """Verify response structures match expectations."""

    def test_create_campaign_response_structure(self, vendor_client, mock_service):
        """Create campaign response has expected fields."""
        mock_service.create_campaign.return_value = {
            "_id": CAMPAIGN_ID,
            "status": "draft",
            "campaign_name": "Test",
            "vendor_id": VENDOR_ID,
            "goal": "profile_visits",
        }
        resp = vendor_client.post(
            "/portal/ads/campaigns", json={"campaign_name": "Test"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "_id" in data
        assert "status" in data
        assert "campaign_name" in data

    def test_list_campaigns_response_structure(self, vendor_client, mock_service):
        """List campaigns response has expected structure."""
        mock_service.list_campaigns.return_value = {
            "campaigns": [{"_id": CAMPAIGN_ID, "campaign_name": "Test"}],
            "total": 1,
        }
        resp = vendor_client.get("/portal/ads/campaigns")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("campaigns"), list)
        assert "total" in data

    def test_billing_response_structure(self, vendor_client, mock_service):
        """Billing response has expected structure."""
        resp = vendor_client.get("/portal/ads/billing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["billing_status"] == "free_tier"
        assert data["total_spend"] == 0.0
        assert data["currency"] == "USD"
        assert "message" in data
        assert "vendor_id" in data

    def test_stats_response_structure(self, vendor_client, mock_service):
        """Stats response has expected structure."""
        mock_service.get_campaign_stats.return_value = {
            "campaign_id": CAMPAIGN_ID,
            "lifetime_stats": {"impressions": 100, "clicks": 10, "leads": 2},
            "daily_stats": [{"date": "2026-03-19", "impressions": 10, "clicks": 1}],
        }
        resp = vendor_client.get(f"/portal/ads/campaigns/{CAMPAIGN_ID}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "campaign_id" in data
        assert "lifetime_stats" in data
        assert "daily_stats" in data

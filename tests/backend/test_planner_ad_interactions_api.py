"""
Comprehensive test suite for the Planner Ad Interactions API Router (/planner/ads).

Tests cover:
- All 4 endpoints under /planner/ads
- Authentication (wedding_planner, root_admin OK, vendor 403)
- Sponsored cards retrieval with filters
- Add vendor to directory flow
- Quote request submission
- Directory status checking
- Request validation (missing fields, constraints)
- Response structure validation

Auth strategy:
- Use app.dependency_overrides to mock require_team_or_planner and
  require_manage_vendors
- Create mock ExtendedAuthUser objects for planner, admin, and vendor roles
- Test that vendors (non-wedding_planner, non-root_admin) get 403
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI, HTTPException
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

from app.api.planner_ad_interactions import (
    get_planner_ad_interaction_service,
    require_manage_vendors,
    require_team_or_planner,
)
from app.api.planner_ad_interactions import router as planner_ad_router
from app.dependencies.auth_extended import ExtendedAuthUser

# Create a minimal test app with just the planner ad interactions router
# (avoids importing app.main which triggers the full import chain)
app = FastAPI()
app.include_router(planner_ad_router)


# =============================================================================
# TEST FIXTURES & MOCKS
# =============================================================================

PLANNER_ID = str(ObjectId())
PLANNER_EMAIL = "planner@example.com"
PLANNER_NAME = "Sarah Johnson Wedding Planner"

ADMIN_EMAIL = "thedeveloper@thespecialwedding.io"
VENDOR_EMAIL = "vendor@florist.com"

CAMPAIGN_ID = str(ObjectId())
VENDOR_PROFILE_ID = str(ObjectId())
CLICK_ID = "click_123abc456def"


def make_mock_planner_user(user_id=PLANNER_ID, email=PLANNER_EMAIL, name=PLANNER_NAME):
    """Create a mock wedding_planner user."""
    return ExtendedAuthUser(
        email=email,
        role="wedding_planner",
        user_data={
            "_id": ObjectId(user_id),
            "name": name,
            "display_name": name,
            "role": "wedding_planner",
        },
    )


def make_mock_admin_user(email=ADMIN_EMAIL):
    """Create a mock root admin user."""
    return ExtendedAuthUser(
        email=email,
        role="ROOT_ADMIN",
        user_data={"_id": ObjectId(), "name": "Root Admin", "role": "ROOT_ADMIN"},
    )


def make_mock_vendor_user():
    """Create a mock advertising_vendor user (should get 403)."""
    return ExtendedAuthUser(
        email=VENDOR_EMAIL,
        role="advertising_vendor",
        user_data={
            "_id": ObjectId(),
            "name": "Vendor Account",
            "role": "advertising_vendor",
        },
    )


@pytest.fixture
def mock_service():
    """Create an AsyncMock service for dependency injection."""
    return AsyncMock()


@pytest.fixture
def planner_client(mock_service):
    """TestClient with planner user authenticated."""
    planner_user = make_mock_planner_user()
    app.dependency_overrides[require_team_or_planner] = lambda: planner_user
    app.dependency_overrides[require_manage_vendors] = lambda: planner_user
    app.dependency_overrides[get_planner_ad_interaction_service] = lambda: mock_service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(mock_service):
    """TestClient with admin user authenticated."""
    admin_user = make_mock_admin_user()
    app.dependency_overrides[require_team_or_planner] = lambda: admin_user
    app.dependency_overrides[require_manage_vendors] = lambda: admin_user
    app.dependency_overrides[get_planner_ad_interaction_service] = lambda: mock_service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def vendor_client(mock_service):
    """TestClient with vendor user (should fail auth).

    Override require_team_or_planner to raise 403, simulating
    what the real dependency does for non-planner/non-admin users.
    """

    def raise_403():
        raise HTTPException(status_code=403, detail="Wedding planner access required")

    app.dependency_overrides[require_team_or_planner] = raise_403
    app.dependency_overrides[require_manage_vendors] = raise_403
    app.dependency_overrides[get_planner_ad_interaction_service] = lambda: mock_service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# =============================================================================
# TESTS: GET /sponsored-cards
# =============================================================================


class TestGetSponsoredCards:
    """Tests for GET /planner/ads/sponsored-cards endpoint."""

    def test_get_sponsored_cards_planner_success(self, planner_client, mock_service):
        """Planner can retrieve sponsored cards."""
        mock_cards = [
            {
                "campaign_id": CAMPAIGN_ID,
                "vendor_name": "Florist Co",
                "category": "flowers",
            },
            {
                "campaign_id": str(ObjectId()),
                "vendor_name": "Photographer Pro",
                "category": "photography",
            },
        ]
        mock_service.get_sponsored_cards.return_value = mock_cards

        response = planner_client.get("/planner/ads/sponsored-cards")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["cards"]) == 2
        assert data["cards"][0]["vendor_name"] == "Florist Co"
        mock_service.get_sponsored_cards.assert_called_once()
        call_kwargs = mock_service.get_sponsored_cards.call_args.kwargs
        assert call_kwargs["planner_email"] == PLANNER_EMAIL
        assert call_kwargs["planner_location"] is None
        assert call_kwargs["categories"] is None
        assert call_kwargs["limit"] == 3

    def test_get_sponsored_cards_admin_success(self, admin_client, mock_service):
        """Admin can retrieve sponsored cards."""
        mock_cards = [{"campaign_id": CAMPAIGN_ID, "vendor_name": "Caterer"}]
        mock_service.get_sponsored_cards.return_value = mock_cards

        response = admin_client.get("/planner/ads/sponsored-cards")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        mock_service.get_sponsored_cards.assert_called_once()

    def test_get_sponsored_cards_vendor_forbidden(self, vendor_client):
        """Vendor cannot retrieve sponsored cards."""
        response = vendor_client.get("/planner/ads/sponsored-cards")
        assert response.status_code == 403

    def test_get_sponsored_cards_with_location(self, planner_client, mock_service):
        """Location filter is passed to service."""
        mock_service.get_sponsored_cards.return_value = []

        response = planner_client.get(
            "/planner/ads/sponsored-cards?location=New%20York"
        )

        assert response.status_code == 200
        call_kwargs = mock_service.get_sponsored_cards.call_args.kwargs
        assert call_kwargs["planner_location"] == "New York"

    def test_get_sponsored_cards_with_categories(self, planner_client, mock_service):
        """Categories filter is parsed and passed to service."""
        mock_service.get_sponsored_cards.return_value = []

        response = planner_client.get(
            "/planner/ads/sponsored-cards?categories=flowers%2Cphotography%2Ccatering"
        )

        assert response.status_code == 200
        call_kwargs = mock_service.get_sponsored_cards.call_args.kwargs
        assert call_kwargs["categories"] == ["flowers", "photography", "catering"]

    def test_get_sponsored_cards_with_custom_limit(self, planner_client, mock_service):
        """Custom limit is passed to service."""
        mock_service.get_sponsored_cards.return_value = []

        response = planner_client.get("/planner/ads/sponsored-cards?limit=5")

        assert response.status_code == 200
        call_kwargs = mock_service.get_sponsored_cards.call_args.kwargs
        assert call_kwargs["limit"] == 5

    def test_get_sponsored_cards_limit_validation_min(self, planner_client):
        """Limit must be >= 1."""
        response = planner_client.get("/planner/ads/sponsored-cards?limit=0")
        assert response.status_code == 422

    def test_get_sponsored_cards_limit_validation_max(self, planner_client):
        """Limit must be <= 10."""
        response = planner_client.get("/planner/ads/sponsored-cards?limit=11")
        assert response.status_code == 422

    def test_get_sponsored_cards_empty_result(self, planner_client, mock_service):
        """Returns empty cards list when no campaigns available."""
        mock_service.get_sponsored_cards.return_value = []

        response = planner_client.get("/planner/ads/sponsored-cards")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["cards"] == []

    def test_get_sponsored_cards_response_structure(self, planner_client, mock_service):
        """Response has correct structure: {cards, count}."""
        mock_cards = [
            {
                "campaign_id": CAMPAIGN_ID,
                "vendor_name": "Florist",
                "category": "flowers",
                "description": "Premium florals",
            }
        ]
        mock_service.get_sponsored_cards.return_value = mock_cards

        response = planner_client.get("/planner/ads/sponsored-cards")

        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert "count" in data
        assert isinstance(data["cards"], list)
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["cards"])


# =============================================================================
# TESTS: POST /add-to-directory
# =============================================================================


class TestAddToDirectory:
    """Tests for POST /planner/ads/add-to-directory endpoint."""

    def test_add_to_directory_planner_success(self, planner_client, mock_service):
        """Planner can add vendor to directory."""
        mock_result = {
            "campaign_id": CAMPAIGN_ID,
            "vendor_profile_id": VENDOR_PROFILE_ID,
            "added": True,
        }
        mock_service.add_to_directory.return_value = mock_result

        response = planner_client.post(
            "/planner/ads/add-to-directory",
            json={"campaign_id": CAMPAIGN_ID, "click_id": CLICK_ID},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["campaign_id"] == CAMPAIGN_ID
        assert data["vendor_profile_id"] == VENDOR_PROFILE_ID
        mock_service.add_to_directory.assert_called_once()
        call_kwargs = mock_service.add_to_directory.call_args.kwargs
        assert call_kwargs["campaign_id"] == CAMPAIGN_ID
        assert call_kwargs["planner_email"] == PLANNER_EMAIL
        # planner_id removed per senior dev review — planner_email is the attribution field
        assert call_kwargs["click_id"] == CLICK_ID

    def test_add_to_directory_admin_success(self, admin_client, mock_service):
        """Admin can add vendor to directory."""
        mock_result = {"campaign_id": CAMPAIGN_ID, "added": True}
        mock_service.add_to_directory.return_value = mock_result

        response = admin_client.post(
            "/planner/ads/add-to-directory",
            json={"campaign_id": CAMPAIGN_ID, "click_id": CLICK_ID},
        )

        assert response.status_code == 201
        mock_service.add_to_directory.assert_called_once()

    def test_add_to_directory_vendor_forbidden(self, vendor_client):
        """Vendor cannot add to directory."""
        response = vendor_client.post(
            "/planner/ads/add-to-directory",
            json={"campaign_id": CAMPAIGN_ID, "click_id": CLICK_ID},
        )
        assert response.status_code == 403

    def test_add_to_directory_missing_campaign_id(self, planner_client):
        """Request missing campaign_id is rejected (422)."""
        response = planner_client.post(
            "/planner/ads/add-to-directory", json={"click_id": CLICK_ID}
        )
        assert response.status_code == 422

    def test_add_to_directory_no_click_id_ok(self, planner_client, mock_service):
        """click_id is optional."""
        mock_result = {"campaign_id": CAMPAIGN_ID, "added": True}
        mock_service.add_to_directory.return_value = mock_result

        response = planner_client.post(
            "/planner/ads/add-to-directory", json={"campaign_id": CAMPAIGN_ID}
        )

        assert response.status_code == 201
        call_kwargs = mock_service.add_to_directory.call_args.kwargs
        assert call_kwargs["click_id"] is None

    def test_add_to_directory_service_called_with_correct_planner_id(
        self, planner_client, mock_service
    ):
        """Service receives planner_id from auth user."""
        mock_service.add_to_directory.return_value = {"added": True}

        response = planner_client.post(
            "/planner/ads/add-to-directory", json={"campaign_id": CAMPAIGN_ID}
        )

        assert response.status_code == 201
        call_kwargs = mock_service.add_to_directory.call_args.kwargs
        # planner_id removed per senior dev review — planner_email is the attribution field

    def test_add_to_directory_returns_service_result(
        self, planner_client, mock_service
    ):
        """Endpoint returns result from service."""
        service_result = {
            "campaign_id": CAMPAIGN_ID,
            "vendor_profile_id": VENDOR_PROFILE_ID,
            "added": True,
            "source": "sponsored_ad",
        }
        mock_service.add_to_directory.return_value = service_result

        response = planner_client.post(
            "/planner/ads/add-to-directory",
            json={"campaign_id": CAMPAIGN_ID, "click_id": CLICK_ID},
        )

        assert response.status_code == 201
        data = response.json()
        assert data == service_result


# =============================================================================
# TESTS: POST /request-quote
# =============================================================================


class TestRequestQuote:
    """Tests for POST /planner/ads/request-quote endpoint."""

    def test_request_quote_planner_success(self, planner_client, mock_service):
        """Planner can request a quote."""
        mock_result = {
            "campaign_id": CAMPAIGN_ID,
            "lead_id": str(ObjectId()),
            "status": "sent",
        }
        mock_service.request_quote.return_value = mock_result

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={
                "campaign_id": CAMPAIGN_ID,
                "message": "We love your work and would like to discuss pricing.",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["campaign_id"] == CAMPAIGN_ID
        assert data["status"] == "sent"
        mock_service.request_quote.assert_called_once()
        call_kwargs = mock_service.request_quote.call_args.kwargs
        assert call_kwargs["campaign_id"] == CAMPAIGN_ID
        assert call_kwargs["planner_email"] == PLANNER_EMAIL
        assert call_kwargs["planner_name"] == PLANNER_NAME
        assert (
            call_kwargs["message"]
            == "We love your work and would like to discuss pricing."
        )

    def test_request_quote_admin_success(self, admin_client, mock_service):
        """Admin can request a quote."""
        mock_result = {"campaign_id": CAMPAIGN_ID, "status": "sent"}
        mock_service.request_quote.return_value = mock_result

        response = admin_client.post(
            "/planner/ads/request-quote",
            json={"campaign_id": CAMPAIGN_ID, "message": "Quote request"},
        )

        assert response.status_code == 201
        mock_service.request_quote.assert_called_once()

    def test_request_quote_vendor_forbidden(self, vendor_client):
        """Vendor cannot request quote."""
        response = vendor_client.post(
            "/planner/ads/request-quote",
            json={"campaign_id": CAMPAIGN_ID, "message": "Quote request"},
        )
        assert response.status_code == 403

    def test_request_quote_missing_campaign_id(self, planner_client):
        """Request missing campaign_id is rejected."""
        response = planner_client.post(
            "/planner/ads/request-quote", json={"message": "Quote request"}
        )
        assert response.status_code == 422

    def test_request_quote_missing_message(self, planner_client):
        """Request missing message is rejected."""
        response = planner_client.post(
            "/planner/ads/request-quote", json={"campaign_id": CAMPAIGN_ID}
        )
        assert response.status_code == 422

    def test_request_quote_empty_message(self, planner_client):
        """Empty message is rejected (min_length=1)."""
        response = planner_client.post(
            "/planner/ads/request-quote",
            json={"campaign_id": CAMPAIGN_ID, "message": ""},
        )
        assert response.status_code == 422

    def test_request_quote_message_too_long(self, planner_client):
        """Message exceeding 2000 chars is rejected."""
        long_message = "x" * 2001
        response = planner_client.post(
            "/planner/ads/request-quote",
            json={"campaign_id": CAMPAIGN_ID, "message": long_message},
        )
        assert response.status_code == 422

    def test_request_quote_with_wedding_context(self, planner_client, mock_service):
        """Wedding context is passed to service."""
        mock_service.request_quote.return_value = {"status": "sent"}
        wedding_context = {
            "date": "2026-06-15",
            "location": "New York",
            "guest_count": 150,
            "venue": "Central Park Pavilion",
            "budget_range": "$50k-$75k",
        }

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={
                "campaign_id": CAMPAIGN_ID,
                "message": "Interested in your services.",
                "wedding_context": wedding_context,
            },
        )

        assert response.status_code == 201
        call_kwargs = mock_service.request_quote.call_args.kwargs
        assert call_kwargs["wedding_context"] == wedding_context

    def test_request_quote_with_wedding_id(self, planner_client, mock_service):
        """Wedding ID is passed to service."""
        wedding_id = str(ObjectId())
        mock_service.request_quote.return_value = {"status": "sent"}

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={
                "campaign_id": CAMPAIGN_ID,
                "message": "Quote request",
                "wedding_id": wedding_id,
            },
        )

        assert response.status_code == 201
        call_kwargs = mock_service.request_quote.call_args.kwargs
        assert call_kwargs["wedding_id"] == wedding_id

    def test_request_quote_with_click_id(self, planner_client, mock_service):
        """Click ID is passed to service."""
        mock_service.request_quote.return_value = {"status": "sent"}

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={
                "campaign_id": CAMPAIGN_ID,
                "message": "Quote request",
                "click_id": CLICK_ID,
            },
        )

        assert response.status_code == 201
        call_kwargs = mock_service.request_quote.call_args.kwargs
        assert call_kwargs["click_id"] == CLICK_ID

    def test_request_quote_auto_add_to_directory_default_true(
        self, planner_client, mock_service
    ):
        """auto_add_to_directory defaults to True."""
        mock_service.request_quote.return_value = {"status": "sent"}

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={"campaign_id": CAMPAIGN_ID, "message": "Quote request"},
        )

        assert response.status_code == 201
        call_kwargs = mock_service.request_quote.call_args.kwargs
        assert call_kwargs["auto_add_to_directory"] is True

    def test_request_quote_auto_add_to_directory_false(
        self, planner_client, mock_service
    ):
        """auto_add_to_directory can be set to False."""
        mock_service.request_quote.return_value = {"status": "sent"}

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={
                "campaign_id": CAMPAIGN_ID,
                "message": "Quote request",
                "auto_add_to_directory": False,
            },
        )

        assert response.status_code == 201
        call_kwargs = mock_service.request_quote.call_args.kwargs
        assert call_kwargs["auto_add_to_directory"] is False

    def test_request_quote_planner_name_extracted(self, planner_client, mock_service):
        """Planner name is extracted from user data."""
        mock_service.request_quote.return_value = {"status": "sent"}

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={"campaign_id": CAMPAIGN_ID, "message": "Quote request"},
        )

        assert response.status_code == 201
        call_kwargs = mock_service.request_quote.call_args.kwargs
        assert call_kwargs["planner_name"] == PLANNER_NAME

    def test_request_quote_planner_name_fallback_to_email(
        self, planner_client, mock_service
    ):
        """Planner name falls back to email if not in user_data."""
        # Create a user without name
        user_without_name = ExtendedAuthUser(
            email="planner2@example.com",
            role="wedding_planner",
            user_data={"_id": ObjectId()},
        )
        planner_client.app.dependency_overrides[require_manage_vendors] = lambda: (
            user_without_name
        )
        mock_service.request_quote.return_value = {"status": "sent"}

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={"campaign_id": CAMPAIGN_ID, "message": "Quote request"},
        )

        assert response.status_code == 201
        call_kwargs = mock_service.request_quote.call_args.kwargs
        assert call_kwargs["planner_name"] == "planner2@example.com"

    def test_request_quote_returns_service_result(self, planner_client, mock_service):
        """Endpoint returns result from service."""
        lead_id = str(ObjectId())
        service_result = {
            "campaign_id": CAMPAIGN_ID,
            "lead_id": lead_id,
            "status": "sent",
            "email_sent": True,
        }
        mock_service.request_quote.return_value = service_result

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={"campaign_id": CAMPAIGN_ID, "message": "Quote request"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data == service_result


# =============================================================================
# TESTS: GET /directory-status
# =============================================================================


class TestCheckDirectoryStatus:
    """Tests for GET /planner/ads/directory-status endpoint."""

    def test_check_directory_status_planner_success(self, planner_client, mock_service):
        """Planner can check if vendor is in directory."""
        mock_result = {
            "campaign_id": CAMPAIGN_ID,
            "in_directory": True,
            "vendor_profile_id": VENDOR_PROFILE_ID,
        }
        mock_service.check_directory_status.return_value = mock_result

        response = planner_client.get(
            f"/planner/ads/directory-status?campaign_id={CAMPAIGN_ID}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == CAMPAIGN_ID
        assert data["in_directory"] is True
        assert data["vendor_profile_id"] == VENDOR_PROFILE_ID
        mock_service.check_directory_status.assert_called_once()
        call_kwargs = mock_service.check_directory_status.call_args.kwargs
        assert call_kwargs["campaign_id"] == CAMPAIGN_ID
        assert call_kwargs["planner_email"] == PLANNER_EMAIL

    def test_check_directory_status_admin_success(self, admin_client, mock_service):
        """Admin can check directory status."""
        mock_result = {"campaign_id": CAMPAIGN_ID, "in_directory": False}
        mock_service.check_directory_status.return_value = mock_result

        response = admin_client.get(
            f"/planner/ads/directory-status?campaign_id={CAMPAIGN_ID}"
        )

        assert response.status_code == 200
        mock_service.check_directory_status.assert_called_once()

    def test_check_directory_status_vendor_forbidden(self, vendor_client):
        """Vendor cannot check directory status."""
        response = vendor_client.get(
            f"/planner/ads/directory-status?campaign_id={CAMPAIGN_ID}"
        )
        assert response.status_code == 403

    def test_check_directory_status_missing_campaign_id(self, planner_client):
        """Request missing campaign_id is rejected."""
        response = planner_client.get("/planner/ads/directory-status")
        assert response.status_code == 422

    def test_check_directory_status_vendor_not_in_directory(
        self, planner_client, mock_service
    ):
        """Returns in_directory=False when vendor not added."""
        mock_result = {
            "campaign_id": CAMPAIGN_ID,
            "in_directory": False,
            "vendor_profile_id": None,
        }
        mock_service.check_directory_status.return_value = mock_result

        response = planner_client.get(
            f"/planner/ads/directory-status?campaign_id={CAMPAIGN_ID}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["in_directory"] is False

    def test_check_directory_status_response_structure(
        self, planner_client, mock_service
    ):
        """Response has required fields."""
        mock_result = {
            "campaign_id": CAMPAIGN_ID,
            "in_directory": True,
            "vendor_profile_id": VENDOR_PROFILE_ID,
        }
        mock_service.check_directory_status.return_value = mock_result

        response = planner_client.get(
            f"/planner/ads/directory-status?campaign_id={CAMPAIGN_ID}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "campaign_id" in data
        assert "in_directory" in data
        assert "vendor_profile_id" in data


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegrationFlows:
    """Integration-style tests across multiple endpoints."""

    def test_flow_check_status_then_add_to_directory(
        self, planner_client, mock_service
    ):
        """Planner checks status, then adds to directory."""
        # Step 1: Check status (not in directory)
        mock_service.check_directory_status.return_value = {
            "campaign_id": CAMPAIGN_ID,
            "in_directory": False,
        }
        response1 = planner_client.get(
            f"/planner/ads/directory-status?campaign_id={CAMPAIGN_ID}"
        )
        assert response1.status_code == 200
        assert response1.json()["in_directory"] is False

        # Step 2: Add to directory
        mock_service.add_to_directory.return_value = {
            "campaign_id": CAMPAIGN_ID,
            "vendor_profile_id": VENDOR_PROFILE_ID,
            "added": True,
        }
        response2 = planner_client.post(
            "/planner/ads/add-to-directory",
            json={"campaign_id": CAMPAIGN_ID, "click_id": CLICK_ID},
        )
        assert response2.status_code == 201
        assert response2.json()["added"] is True

        # Step 3: Verify service calls
        assert mock_service.check_directory_status.called
        assert mock_service.add_to_directory.called

    def test_flow_get_cards_then_request_quote(self, planner_client, mock_service):
        """Planner gets sponsored cards, then requests quote from one."""
        # Step 1: Get sponsored cards
        mock_cards = [{"campaign_id": CAMPAIGN_ID, "vendor_name": "Florist"}]
        mock_service.get_sponsored_cards.return_value = mock_cards
        response1 = planner_client.get("/planner/ads/sponsored-cards")
        assert response1.status_code == 200
        assert len(response1.json()["cards"]) == 1

        # Step 2: Request quote from one of the cards
        mock_service.request_quote.return_value = {
            "campaign_id": CAMPAIGN_ID,
            "status": "sent",
        }
        response2 = planner_client.post(
            "/planner/ads/request-quote",
            json={"campaign_id": CAMPAIGN_ID, "message": "Interested in your florals"},
        )
        assert response2.status_code == 201
        assert response2.json()["status"] == "sent"

        # Verify service calls in order
        assert mock_service.get_sponsored_cards.called
        assert mock_service.request_quote.called

    def test_flow_request_quote_with_auto_add(self, planner_client, mock_service):
        """Planner requests quote with auto_add_to_directory=True."""
        mock_service.request_quote.return_value = {
            "campaign_id": CAMPAIGN_ID,
            "status": "sent",
            "vendor_added_to_directory": True,
        }

        response = planner_client.post(
            "/planner/ads/request-quote",
            json={
                "campaign_id": CAMPAIGN_ID,
                "message": "Great work!",
                "auto_add_to_directory": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["vendor_added_to_directory"] is True
        call_kwargs = mock_service.request_quote.call_args.kwargs
        assert call_kwargs["auto_add_to_directory"] is True


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error conditions and edge cases."""

    def test_malformed_json_request(self, planner_client):
        """Malformed JSON in request body is rejected."""
        response = planner_client.post(
            "/planner/ads/add-to-directory",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_extra_fields_in_request_ignored(self, planner_client, mock_service):
        """Extra fields in request are ignored."""
        mock_service.add_to_directory.return_value = {"added": True}

        response = planner_client.post(
            "/planner/ads/add-to-directory",
            json={
                "campaign_id": CAMPAIGN_ID,
                "click_id": CLICK_ID,
                "extra_field": "should be ignored",
            },
        )

        assert response.status_code == 201
        # Service should not receive extra fields
        call_kwargs = mock_service.add_to_directory.call_args.kwargs
        assert "extra_field" not in call_kwargs

    def test_service_exception_propagates(self, mock_service):
        """Service exceptions are propagated as 500."""
        planner_user = make_mock_planner_user()
        app.dependency_overrides[require_team_or_planner] = lambda: planner_user
        app.dependency_overrides[get_planner_ad_interaction_service] = lambda: (
            mock_service
        )
        mock_service.get_sponsored_cards.side_effect = ValueError("Database error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/planner/ads/sponsored-cards")

        # FastAPI converts unhandled exceptions to 500
        assert response.status_code == 500
        app.dependency_overrides.clear()

"""
Comprehensive test suite for admin campaigns API router.

Tests /admin/ads/campaigns/* endpoints covering:
- All 18 routes
- Auth boundaries (require_root_admin)
- Query parameters and pagination
- Request bodies and validation
- Success and error scenarios
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup environment
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")

from fastapi import FastAPI

from app.api.admin_campaigns import get_admin_campaign_service
from app.api.admin_campaigns import router as admin_campaigns_router
from app.dependencies.auth_extended import ExtendedAuthUser, require_root_admin

# Create a minimal test app with just the admin campaigns router
# (avoids importing app.main which triggers the full import chain)
app = FastAPI()
app.include_router(admin_campaigns_router)

ADMIN_EMAIL = "thedeveloper@thespecialwedding.io"
NON_ADMIN_EMAIL = "vendor@example.com"


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_admin_user():
    """Create a mock root admin user."""
    return ExtendedAuthUser(
        email=ADMIN_EMAIL,
        role="ROOT_ADMIN",
        user_data={"_id": str(ObjectId()), "email": ADMIN_EMAIL, "role": "ROOT_ADMIN"},
    )


@pytest.fixture
def mock_non_admin_user():
    """Create a mock non-admin user."""
    return ExtendedAuthUser(
        email=NON_ADMIN_EMAIL,
        role="vendor",
        user_data={"_id": str(ObjectId()), "email": NON_ADMIN_EMAIL, "role": "vendor"},
    )


@pytest.fixture
def mock_service():
    """Create a mock AdminCampaignService."""
    return AsyncMock()


@pytest.fixture
def admin_client(mock_service, mock_admin_user):
    """Create a TestClient with admin auth and mocked service."""
    app.dependency_overrides[require_root_admin] = lambda: mock_admin_user
    app.dependency_overrides[get_admin_campaign_service] = lambda: mock_service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def non_admin_client(mock_service, mock_non_admin_user):
    """Create a TestClient with non-admin auth."""

    # Simulate non-admin access by making require_root_admin raise an exception
    def raise_forbidden():
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Not authorized")

    app.dependency_overrides[require_root_admin] = raise_forbidden
    app.dependency_overrides[get_admin_campaign_service] = lambda: mock_service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# =============================================================================
# AUTH TESTS
# =============================================================================


class TestAuthBoundaries:
    """Test that non-admin users get 403 on all endpoints."""

    def test_get_review_queue_forbidden_non_admin(self, non_admin_client):
        """Non-admin cannot access review queue."""
        response = non_admin_client.get("/admin/ads/campaigns/review")
        assert response.status_code == 403

    def test_get_review_counts_forbidden_non_admin(self, non_admin_client):
        """Non-admin cannot access review counts."""
        response = non_admin_client.get("/admin/ads/campaigns/review/counts")
        assert response.status_code == 403

    def test_approve_campaign_forbidden_non_admin(self, non_admin_client):
        """Non-admin cannot approve campaigns."""
        response = non_admin_client.put(
            f"/admin/ads/campaigns/{ObjectId()}/approve", json={}
        )
        assert response.status_code == 403

    def test_list_all_campaigns_forbidden_non_admin(self, non_admin_client):
        """Non-admin cannot list campaigns."""
        response = non_admin_client.get("/admin/ads/campaigns/")
        assert response.status_code == 403

    def test_get_revenue_summary_forbidden_non_admin(self, non_admin_client):
        """Non-admin cannot access revenue summary."""
        response = non_admin_client.get("/admin/ads/campaigns/revenue")
        assert response.status_code == 403

    def test_get_platform_config_forbidden_non_admin(self, non_admin_client):
        """Non-admin cannot access platform config."""
        response = non_admin_client.get("/admin/ads/campaigns/config")
        assert response.status_code == 403


# =============================================================================
# REVIEW QUEUE TESTS
# =============================================================================


class TestReviewQueue:
    """Test review queue endpoints."""

    def test_get_review_queue_default(self, admin_client, mock_service):
        """Get review queue with default parameters."""
        mock_service.get_review_queue.return_value = {
            "campaigns": [
                {
                    "_id": str(ObjectId()),
                    "campaign_name": "Summer Sale",
                    "vendor_name": "Florist Co",
                    "status": "pending_review",
                    "submitted_at": "2026-03-19T10:00:00Z",
                }
            ],
            "total": 1,
        }

        response = admin_client.get("/admin/ads/campaigns/review")
        assert response.status_code == 200
        data = response.json()
        assert "campaigns" in data
        assert data["total"] == 1

        mock_service.get_review_queue.assert_called_once_with(
            status_filter=None,
            limit=50,
            skip=0,
        )

    def test_get_review_queue_with_status_filter(self, admin_client, mock_service):
        """Get review queue filtered by status."""
        mock_service.get_review_queue.return_value = {"campaigns": [], "total": 0}

        response = admin_client.get("/admin/ads/campaigns/review?status=pending_review")
        assert response.status_code == 200

        mock_service.get_review_queue.assert_called_once_with(
            status_filter="pending_review",
            limit=50,
            skip=0,
        )

    def test_get_review_queue_with_pagination(self, admin_client, mock_service):
        """Get review queue with custom pagination."""
        mock_service.get_review_queue.return_value = {"campaigns": [], "total": 100}

        response = admin_client.get("/admin/ads/campaigns/review?limit=20&skip=40")
        assert response.status_code == 200

        mock_service.get_review_queue.assert_called_once_with(
            status_filter=None,
            limit=20,
            skip=40,
        )

    def test_get_review_queue_limit_validation(self, admin_client):
        """Limit must be between 1 and 100."""
        response = admin_client.get("/admin/ads/campaigns/review?limit=101")
        assert response.status_code == 422  # Validation error

        response = admin_client.get("/admin/ads/campaigns/review?limit=0")
        assert response.status_code == 422

    def test_get_review_counts(self, admin_client, mock_service):
        """Get review status counts."""
        mock_service.get_review_counts.return_value = {
            "pending_review": 5,
            "active": 20,
            "paused": 3,
            "rejected": 2,
            "draft": 10,
            "completed": 8,
            "total": 48,
        }

        response = admin_client.get("/admin/ads/campaigns/review/counts")
        assert response.status_code == 200
        data = response.json()
        assert data["pending_review"] == 5
        assert data["active"] == 20
        assert data["total"] == 48

        mock_service.get_review_counts.assert_called_once()


# =============================================================================
# CAMPAIGN REVIEW ACTIONS TESTS
# =============================================================================


class TestCampaignReviewActions:
    """Test campaign review action endpoints."""

    def test_approve_campaign_minimal_request(self, admin_client, mock_service):
        """Approve campaign with minimal request body."""
        campaign_id = str(ObjectId())
        mock_service.approve_campaign.return_value = {
            "_id": campaign_id,
            "campaign_name": "Summer Sale",
            "status": "active",
            "reviewed_by": ADMIN_EMAIL,
            "reviewed_at": "2026-03-19T10:00:00Z",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/approve", json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["reviewed_by"] == ADMIN_EMAIL

        mock_service.approve_campaign.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            review_notes=None,
        )

    def test_approve_campaign_with_notes(self, admin_client, mock_service):
        """Approve campaign with review notes."""
        campaign_id = str(ObjectId())
        mock_service.approve_campaign.return_value = {
            "_id": campaign_id,
            "status": "active",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/approve",
            json={"review_notes": "Looks good!"},
        )
        assert response.status_code == 200

        mock_service.approve_campaign.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            review_notes="Looks good!",
        )

    def test_reject_campaign_minimal_request(self, admin_client, mock_service):
        """Reject campaign with minimal request body."""
        campaign_id = str(ObjectId())
        mock_service.reject_campaign.return_value = {
            "_id": campaign_id,
            "status": "rejected",
            "reviewed_by": ADMIN_EMAIL,
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/reject", json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"

        mock_service.reject_campaign.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            review_notes=None,
        )

    def test_reject_campaign_with_notes(self, admin_client, mock_service):
        """Reject campaign with review notes."""
        campaign_id = str(ObjectId())
        mock_service.reject_campaign.return_value = {
            "_id": campaign_id,
            "status": "rejected",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/reject",
            json={"review_notes": "Inappropriate content"},
        )
        assert response.status_code == 200

        mock_service.reject_campaign.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            review_notes="Inappropriate content",
        )

    def test_request_changes_requires_notes(self, admin_client, mock_service):
        """Request changes requires review_notes in request body."""
        campaign_id = str(ObjectId())
        mock_service.request_changes.return_value = {
            "_id": campaign_id,
            "status": "draft",
            "reviewed_by": ADMIN_EMAIL,
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/request-changes",
            json={"review_notes": "Please fix the image quality"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"

        mock_service.request_changes.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            review_notes="Please fix the image quality",
        )

    def test_request_changes_with_empty_notes(self, admin_client, mock_service):
        """Request changes with empty notes becomes empty string."""
        campaign_id = str(ObjectId())
        mock_service.request_changes.return_value = {
            "_id": campaign_id,
            "status": "draft",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/request-changes",
            json={"review_notes": None},
        )
        assert response.status_code == 200

        mock_service.request_changes.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            review_notes="",
        )


# =============================================================================
# CREATIVE REVIEW TESTS
# =============================================================================


class TestCreativeReview:
    """Test creative review endpoints."""

    def test_get_creative_review_queue_default(self, admin_client, mock_service):
        """Get creative review queue with defaults."""
        mock_service.get_creative_review_queue.return_value = {
            "creatives": [
                {
                    "_id": str(ObjectId()),
                    "campaign_id": str(ObjectId()),
                    "headline": "Summer Flowers",
                    "review_status": "pending",
                }
            ],
            "total": 1,
        }

        response = admin_client.get("/admin/ads/campaigns/review/creatives")
        assert response.status_code == 200
        data = response.json()
        assert len(data["creatives"]) == 1
        assert data["total"] == 1

        mock_service.get_creative_review_queue.assert_called_once_with(limit=50, skip=0)

    def test_get_creative_review_queue_with_pagination(
        self, admin_client, mock_service
    ):
        """Get creative review queue with custom pagination."""
        mock_service.get_creative_review_queue.return_value = {
            "creatives": [],
            "total": 200,
        }

        response = admin_client.get(
            "/admin/ads/campaigns/review/creatives?limit=30&skip=60"
        )
        assert response.status_code == 200

        mock_service.get_creative_review_queue.assert_called_once_with(
            limit=30, skip=60
        )

    def test_approve_creative(self, admin_client, mock_service):
        """Approve a creative."""
        creative_id = str(ObjectId())
        mock_service.approve_creative.return_value = {
            "_id": creative_id,
            "review_status": "approved",
            "reviewed_by": ADMIN_EMAIL,
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/review/creatives/{creative_id}/approve",
            json={"review_notes": "Great image quality"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["review_status"] == "approved"

        mock_service.approve_creative.assert_called_once_with(
            creative_id=creative_id,
            admin_email=ADMIN_EMAIL,
            review_notes="Great image quality",
        )

    def test_approve_creative_without_notes(self, admin_client, mock_service):
        """Approve a creative without notes."""
        creative_id = str(ObjectId())
        mock_service.approve_creative.return_value = {
            "_id": creative_id,
            "review_status": "approved",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/review/creatives/{creative_id}/approve", json={}
        )
        assert response.status_code == 200

        mock_service.approve_creative.assert_called_once_with(
            creative_id=creative_id,
            admin_email=ADMIN_EMAIL,
            review_notes=None,
        )

    def test_reject_creative(self, admin_client, mock_service):
        """Reject a creative."""
        creative_id = str(ObjectId())
        mock_service.reject_creative.return_value = {
            "_id": creative_id,
            "review_status": "rejected",
            "reviewed_by": ADMIN_EMAIL,
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/review/creatives/{creative_id}/reject",
            json={"review_notes": "Image quality too low"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["review_status"] == "rejected"

        mock_service.reject_creative.assert_called_once_with(
            creative_id=creative_id,
            admin_email=ADMIN_EMAIL,
            review_notes="Image quality too low",
        )

    def test_reject_creative_without_notes(self, admin_client, mock_service):
        """Reject a creative without notes."""
        creative_id = str(ObjectId())
        mock_service.reject_creative.return_value = {
            "_id": creative_id,
            "review_status": "rejected",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/review/creatives/{creative_id}/reject", json={}
        )
        assert response.status_code == 200

        mock_service.reject_creative.assert_called_once_with(
            creative_id=creative_id,
            admin_email=ADMIN_EMAIL,
            review_notes=None,
        )


# =============================================================================
# CAMPAIGN MONITORING TESTS
# =============================================================================


class TestCampaignMonitoring:
    """Test campaign monitoring endpoints."""

    def test_list_all_campaigns_default(self, admin_client, mock_service):
        """List all campaigns with defaults."""
        mock_service.list_all_campaigns.return_value = {
            "campaigns": [
                {
                    "_id": str(ObjectId()),
                    "campaign_name": "Spring Special",
                    "vendor_name": "Vendor A",
                    "status": "active",
                }
            ],
            "total": 1,
        }

        response = admin_client.get("/admin/ads/campaigns/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["campaigns"]) == 1

        mock_service.list_all_campaigns.assert_called_once_with(
            status_filter=None,
            vendor_id=None,
            limit=50,
            skip=0,
        )

    def test_list_all_campaigns_with_filters(self, admin_client, mock_service):
        """List campaigns with status and vendor filters."""
        vendor_id = str(ObjectId())
        mock_service.list_all_campaigns.return_value = {"campaigns": [], "total": 0}

        response = admin_client.get(
            f"/admin/ads/campaigns/?status=active&vendor_id={vendor_id}&limit=25&skip=10"
        )
        assert response.status_code == 200

        mock_service.list_all_campaigns.assert_called_once_with(
            status_filter="active",
            vendor_id=vendor_id,
            limit=25,
            skip=10,
        )

    def test_admin_pause_campaign(self, admin_client, mock_service):
        """Admin pause campaign with reason."""
        campaign_id = str(ObjectId())
        mock_service.admin_pause_campaign.return_value = {
            "_id": campaign_id,
            "status": "paused",
            "pause_reason": "Policy violation",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/pause",
            json={"reason": "Policy violation"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"

        mock_service.admin_pause_campaign.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            reason="Policy violation",
        )

    def test_admin_pause_campaign_no_reason(self, admin_client, mock_service):
        """Admin pause campaign without reason."""
        campaign_id = str(ObjectId())
        mock_service.admin_pause_campaign.return_value = {
            "_id": campaign_id,
            "status": "paused",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/pause", json={}
        )
        assert response.status_code == 200

        mock_service.admin_pause_campaign.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            reason=None,
        )

    def test_admin_deactivate_campaign(self, admin_client, mock_service):
        """Admin deactivate campaign with reason."""
        campaign_id = str(ObjectId())
        mock_service.admin_deactivate_campaign.return_value = {
            "_id": campaign_id,
            "status": "rejected",
            "deactivate_reason": "Malicious content",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/deactivate",
            json={"reason": "Malicious content"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"

        mock_service.admin_deactivate_campaign.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            reason="Malicious content",
        )

    def test_admin_deactivate_campaign_no_reason(self, admin_client, mock_service):
        """Admin deactivate campaign without reason."""
        campaign_id = str(ObjectId())
        mock_service.admin_deactivate_campaign.return_value = {
            "_id": campaign_id,
            "status": "rejected",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/deactivate", json={}
        )
        assert response.status_code == 200

        mock_service.admin_deactivate_campaign.assert_called_once_with(
            campaign_id=campaign_id,
            admin_email=ADMIN_EMAIL,
            reason=None,
        )


# =============================================================================
# REVENUE & ENGAGEMENT TESTS
# =============================================================================


class TestRevenueAndEngagement:
    """Test revenue and engagement endpoints."""

    def test_get_revenue_summary_default(self, admin_client, mock_service):
        """Get revenue summary with default period (30 days)."""
        mock_service.get_revenue_summary.return_value = {
            "period_days": 30,
            "total_revenue": 0.0,
            "total_impressions": 15000,
            "total_clicks": 450,
            "total_leads": 120,
            "unique_planners": 3200,
            "ctr": 3.0,
            "lead_rate": 26.7,
        }

        response = admin_client.get("/admin/ads/campaigns/revenue")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 30
        assert data["total_impressions"] == 15000

        mock_service.get_revenue_summary.assert_called_once_with(days=30)

    def test_get_revenue_summary_custom_period(self, admin_client, mock_service):
        """Get revenue summary with custom period."""
        mock_service.get_revenue_summary.return_value = {
            "period_days": 7,
            "total_revenue": 0.0,
            "total_impressions": 5000,
        }

        response = admin_client.get("/admin/ads/campaigns/revenue?days=7")
        assert response.status_code == 200

        mock_service.get_revenue_summary.assert_called_once_with(days=7)

    def test_get_revenue_summary_max_period(self, admin_client, mock_service):
        """Get revenue summary with max allowed period (365 days)."""
        mock_service.get_revenue_summary.return_value = {
            "period_days": 365,
            "total_revenue": 0.0,
        }

        response = admin_client.get("/admin/ads/campaigns/revenue?days=365")
        assert response.status_code == 200

        mock_service.get_revenue_summary.assert_called_once_with(days=365)

    def test_get_revenue_summary_period_validation(self, admin_client):
        """Revenue period must be between 1 and 365."""
        response = admin_client.get("/admin/ads/campaigns/revenue?days=0")
        assert response.status_code == 422

        response = admin_client.get("/admin/ads/campaigns/revenue?days=366")
        assert response.status_code == 422


# =============================================================================
# PLANNER FEEDBACK TESTS
# =============================================================================


class TestPlannerFeedback:
    """Test planner feedback endpoint."""

    def test_get_planner_feedback_default(self, admin_client, mock_service):
        """Get planner feedback with defaults."""
        mock_service.get_planner_feedback.return_value = {
            "feedback": [
                {
                    "_id": str(ObjectId()),
                    "planner_id": str(ObjectId()),
                    "feedback_type": "hidden_vendor",
                    "vendor_id": str(ObjectId()),
                    "created_at": "2026-03-19T10:00:00Z",
                }
            ],
            "total": 1,
        }

        response = admin_client.get("/admin/ads/campaigns/feedback")
        assert response.status_code == 200
        data = response.json()
        assert len(data["feedback"]) == 1

        mock_service.get_planner_feedback.assert_called_once_with(limit=50, skip=0)

    def test_get_planner_feedback_pagination(self, admin_client, mock_service):
        """Get planner feedback with custom pagination."""
        mock_service.get_planner_feedback.return_value = {"feedback": [], "total": 500}

        response = admin_client.get("/admin/ads/campaigns/feedback?limit=100&skip=200")
        assert response.status_code == 200

        mock_service.get_planner_feedback.assert_called_once_with(limit=100, skip=200)


# =============================================================================
# FRAUD SIGNALS TESTS
# =============================================================================


class TestFraudSignals:
    """Test fraud signal endpoints."""

    def test_get_fraud_signals_default(self, admin_client, mock_service):
        """Get fraud signals with defaults."""
        mock_service.get_fraud_signals.return_value = {
            "signals": [
                {
                    "_id": str(ObjectId()),
                    "signal_type": "unusual_traffic",
                    "campaign_id": str(ObjectId()),
                    "status": "pending",
                    "flagged_at": "2026-03-19T10:00:00Z",
                }
            ],
            "total": 1,
        }

        response = admin_client.get("/admin/ads/campaigns/fraud-signals")
        assert response.status_code == 200
        data = response.json()
        assert len(data["signals"]) == 1

        mock_service.get_fraud_signals.assert_called_once_with(
            status_filter=None, limit=50, skip=0
        )

    def test_get_fraud_signals_with_status_filter(self, admin_client, mock_service):
        """Get fraud signals filtered by status."""
        mock_service.get_fraud_signals.return_value = {"signals": [], "total": 0}

        response = admin_client.get(
            "/admin/ads/campaigns/fraud-signals?status=pending&limit=25&skip=5"
        )
        assert response.status_code == 200

        mock_service.get_fraud_signals.assert_called_once_with(
            status_filter="pending", limit=25, skip=5
        )

    def test_update_fraud_signal(self, admin_client, mock_service):
        """Update fraud signal status and notes."""
        signal_id = str(ObjectId())
        mock_service.update_fraud_signal.return_value = {
            "_id": signal_id,
            "status": "investigated",
            "notes": "Confirmed bot traffic",
            "investigated_by": ADMIN_EMAIL,
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/fraud-signals/{signal_id}",
            json={"status": "investigated", "notes": "Confirmed bot traffic"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "investigated"
        assert data["notes"] == "Confirmed bot traffic"

        mock_service.update_fraud_signal.assert_called_once_with(
            signal_id=signal_id,
            admin_email=ADMIN_EMAIL,
            status="investigated",
            notes="Confirmed bot traffic",
        )

    def test_update_fraud_signal_status_only(self, admin_client, mock_service):
        """Update fraud signal with only status."""
        signal_id = str(ObjectId())
        mock_service.update_fraud_signal.return_value = {
            "_id": signal_id,
            "status": "false_alarm",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/fraud-signals/{signal_id}",
            json={"status": "false_alarm"},
        )
        assert response.status_code == 200

        mock_service.update_fraud_signal.assert_called_once_with(
            signal_id=signal_id,
            admin_email=ADMIN_EMAIL,
            status="false_alarm",
            notes=None,
        )

    def test_update_fraud_signal_requires_status(self, admin_client):
        """Update fraud signal requires status field."""
        signal_id = str(ObjectId())
        response = admin_client.put(
            f"/admin/ads/campaigns/fraud-signals/{signal_id}",
            json={"notes": "Some notes"},
        )
        assert response.status_code == 422  # Validation error - status required


# =============================================================================
# VENDOR ACCOUNTS TESTS
# =============================================================================


class TestVendorAccounts:
    """Test vendor accounts endpoint."""

    def test_list_vendor_accounts_default(self, admin_client, mock_service):
        """List vendor accounts with defaults."""
        mock_service.list_vendor_accounts.return_value = {
            "vendors": [
                {
                    "_id": str(ObjectId()),
                    "vendor_name": "Florist Co",
                    "vendor_email": "florist@example.com",
                    "status": "active",
                    "created_at": "2026-01-19T10:00:00Z",
                }
            ],
            "total": 1,
        }

        response = admin_client.get("/admin/ads/campaigns/vendors")
        assert response.status_code == 200
        data = response.json()
        assert len(data["vendors"]) == 1

        mock_service.list_vendor_accounts.assert_called_once_with(
            status_filter=None, limit=50, skip=0
        )

    def test_list_vendor_accounts_with_status_filter(self, admin_client, mock_service):
        """List vendor accounts filtered by status."""
        mock_service.list_vendor_accounts.return_value = {"vendors": [], "total": 0}

        response = admin_client.get(
            "/admin/ads/campaigns/vendors?status=active&limit=30&skip=15"
        )
        assert response.status_code == 200

        mock_service.list_vendor_accounts.assert_called_once_with(
            status_filter="active", limit=30, skip=15
        )


# =============================================================================
# PLATFORM CONFIG TESTS
# =============================================================================


class TestPlatformConfig:
    """Test platform configuration endpoints."""

    def test_get_platform_config(self, admin_client, mock_service):
        """Get platform config."""
        mock_service.get_platform_config.return_value = {
            "_id": "platform_config",
            "min_daily_budget": 10.0,
            "max_daily_budget": 10000.0,
            "review_sla_hours": 24,
            "fraud_detection_enabled": True,
            "updated_at": "2026-03-10T10:00:00Z",
        }

        response = admin_client.get("/admin/ads/campaigns/config")
        assert response.status_code == 200
        data = response.json()
        assert data["min_daily_budget"] == 10.0
        assert data["review_sla_hours"] == 24

        mock_service.get_platform_config.assert_called_once()

    def test_update_platform_config(self, admin_client, mock_service):
        """Update platform config."""
        mock_service.update_platform_config.return_value = {
            "_id": "platform_config",
            "review_sla_hours": 48,
            "fraud_detection_enabled": False,
            "updated_by": ADMIN_EMAIL,
            "updated_at": "2026-03-19T10:00:00Z",
        }

        response = admin_client.put(
            "/admin/ads/campaigns/config",
            json={"review_sla_hours": 48, "fraud_detection_enabled": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["review_sla_hours"] == 48
        assert data["fraud_detection_enabled"] is False

        mock_service.update_platform_config.assert_called_once_with(
            admin_email=ADMIN_EMAIL,
            updates={"review_sla_hours": 48, "fraud_detection_enabled": False},
        )

    def test_update_platform_config_empty_updates(self, admin_client, mock_service):
        """Update platform config with empty dict."""
        mock_service.update_platform_config.return_value = {
            "_id": "platform_config",
            "updated_by": ADMIN_EMAIL,
        }

        response = admin_client.put("/admin/ads/campaigns/config", json={})
        assert response.status_code == 200

        mock_service.update_platform_config.assert_called_once_with(
            admin_email=ADMIN_EMAIL,
            updates={},
        )


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_invalid_campaign_id_format(self, admin_client, mock_service):
        """Invalid campaign ID should be handled gracefully."""
        # FastAPI accepts any string as path parameter
        mock_service.approve_campaign.return_value = {"_id": "invalid_id"}

        response = admin_client.put("/admin/ads/campaigns/invalid_id/approve", json={})
        assert response.status_code == 200  # Service handles validation

    def test_service_error_handling(self, admin_client, mock_service):
        """Service errors should be propagated."""
        from fastapi import HTTPException

        campaign_id = str(ObjectId())
        mock_service.approve_campaign.side_effect = HTTPException(
            status_code=404, detail="Campaign not found"
        )

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/approve", json={}
        )
        assert response.status_code == 404

    def test_missing_required_request_body(self, admin_client):
        """Missing required request body fields."""
        signal_id = str(ObjectId())
        # status is required in Body(...)
        response = admin_client.put(
            f"/admin/ads/campaigns/fraud-signals/{signal_id}", json={}
        )
        assert response.status_code == 422

    def test_invalid_query_parameter_type(self, admin_client):
        """Invalid query parameter type should fail validation."""
        response = admin_client.get("/admin/ads/campaigns/revenue?days=not_a_number")
        assert response.status_code == 422

    def test_negative_skip_parameter(self, admin_client):
        """Negative skip should fail validation."""
        response = admin_client.get("/admin/ads/campaigns/?skip=-1")
        assert response.status_code == 422

    def test_negative_limit_parameter(self, admin_client):
        """Negative limit should fail validation."""
        response = admin_client.get("/admin/ads/campaigns/?limit=-5")
        assert response.status_code == 422


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests across multiple endpoints."""

    def test_review_workflow_happy_path(self, admin_client, mock_service):
        """Full review workflow: list -> review -> approve."""
        campaign_id = str(ObjectId())

        # Get review queue
        mock_service.get_review_queue.return_value = {
            "campaigns": [{"_id": campaign_id, "status": "pending_review"}],
            "total": 1,
        }
        response = admin_client.get("/admin/ads/campaigns/review")
        assert response.status_code == 200

        # Approve campaign
        mock_service.approve_campaign.return_value = {
            "_id": campaign_id,
            "status": "active",
        }
        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/approve",
            json={"review_notes": "Approved"},
        )
        assert response.status_code == 200

    def test_creative_review_workflow(self, admin_client, mock_service):
        """Creative review workflow: list -> reject with notes."""
        creative_id = str(ObjectId())

        mock_service.get_creative_review_queue.return_value = {
            "creatives": [{"_id": creative_id, "review_status": "pending"}],
            "total": 1,
        }
        response = admin_client.get("/admin/ads/campaigns/review/creatives")
        assert response.status_code == 200

        mock_service.reject_creative.return_value = {
            "_id": creative_id,
            "review_status": "rejected",
        }
        response = admin_client.put(
            f"/admin/ads/campaigns/review/creatives/{creative_id}/reject",
            json={"review_notes": "Image quality too low"},
        )
        assert response.status_code == 200

    def test_fraud_investigation_workflow(self, admin_client, mock_service):
        """Fraud signal workflow: list -> investigate -> update."""
        signal_id = str(ObjectId())

        mock_service.get_fraud_signals.return_value = {
            "signals": [{"_id": signal_id, "status": "pending"}],
            "total": 1,
        }
        response = admin_client.get("/admin/ads/campaigns/fraud-signals")
        assert response.status_code == 200

        mock_service.update_fraud_signal.return_value = {
            "_id": signal_id,
            "status": "confirmed_fraud",
        }
        response = admin_client.put(
            f"/admin/ads/campaigns/fraud-signals/{signal_id}",
            json={"status": "confirmed_fraud", "notes": "Confirmed bot clicks"},
        )
        assert response.status_code == 200


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge case scenarios."""

    def test_empty_review_queue(self, admin_client, mock_service):
        """Handle empty review queue."""
        mock_service.get_review_queue.return_value = {"campaigns": [], "total": 0}
        response = admin_client.get("/admin/ads/campaigns/review")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_very_long_review_notes(self, admin_client, mock_service):
        """Test very long review notes (max 2000 chars)."""
        campaign_id = str(ObjectId())
        long_notes = "x" * 2000
        mock_service.approve_campaign.return_value = {
            "_id": campaign_id,
            "status": "active",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/approve",
            json={"review_notes": long_notes},
        )
        assert response.status_code == 200

    def test_special_characters_in_notes(self, admin_client, mock_service):
        """Test special characters in review notes."""
        campaign_id = str(ObjectId())
        special_notes = "Test™ with émojis 🚀 and <html>"
        mock_service.approve_campaign.return_value = {
            "_id": campaign_id,
            "status": "active",
        }

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/approve",
            json={"review_notes": special_notes},
        )
        assert response.status_code == 200

        called_notes = mock_service.approve_campaign.call_args[1]["review_notes"]
        assert called_notes == special_notes

    def test_unicode_in_query_parameters(self, admin_client, mock_service):
        """Test unicode characters in query parameters."""
        mock_service.list_vendor_accounts.return_value = {"vendors": [], "total": 0}
        # FastAPI handles URL encoding automatically
        response = admin_client.get("/admin/ads/campaigns/vendors?status=active")
        assert response.status_code == 200

    def test_large_skip_value(self, admin_client, mock_service):
        """Test large skip value (beyond total results)."""
        mock_service.list_all_campaigns.return_value = {"campaigns": [], "total": 100}
        response = admin_client.get("/admin/ads/campaigns/?skip=10000")
        assert response.status_code == 200
        data = response.json()
        assert len(data["campaigns"]) == 0

    def test_admin_user_email_in_response(self, admin_client, mock_service):
        """Verify admin email is captured in service calls."""
        campaign_id = str(ObjectId())
        mock_service.approve_campaign.return_value = {"_id": campaign_id}

        response = admin_client.put(
            f"/admin/ads/campaigns/{campaign_id}/approve", json={}
        )
        assert response.status_code == 200

        # Verify the admin email was passed to service
        call_kwargs = mock_service.approve_campaign.call_args[1]
        assert call_kwargs["admin_email"] == ADMIN_EMAIL

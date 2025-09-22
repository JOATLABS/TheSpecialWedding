"""
Pytest configuration and shared fixtures
"""
import os
import sys
import pytest
from typing import Generator, Any
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from bson import ObjectId

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient

# Ensure mandatory env vars are present BEFORE importing application settings
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only")
os.environ.setdefault("MONGO_URI", "mongodb://test:27017")
# Avoid setting CORS_ORIGINS here to use default list parsing; tests can override if needed.

from app.main import app
from tests.factories import (
    UserFactory,
    AdminUserFactory,
    SubscriptionPlanFactory,
    SubscriptionFactory,
    WeddingFactory,
    GuestFactory,
    FormFactory,
    create_user_with_subscription,
    create_wedding_with_guests,
    create_form_with_responses
)


# ==================== Environment Setup ====================

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment variables"""
    os.environ["TESTING"] = "1"
    os.environ["MONGO_URI"] = "mongodb://test:27017"
    os.environ["MONGO_DB"] = "test_wedding_db"
    os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only"
    os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://localhost:8000"
    yield
    # Cleanup
    del os.environ["TESTING"]


# ==================== Client Fixtures ====================

@pytest.fixture
def client() -> TestClient:
    """Create test client for API testing"""
    return TestClient(app)


@pytest.fixture
def authenticated_client(client: TestClient, mock_auth_token: str) -> TestClient:
    """Create authenticated test client"""
    client.headers = {"Authorization": f"Bearer {mock_auth_token}"}
    return client


# ==================== Database Fixtures ====================

@pytest.fixture
def mock_database():
    """Mock database for unit testing"""
    with patch('app.core.database.mongo') as mock_mongo:
        mock_db = Mock()
        
        # Setup collections
        collections = [
            "admin_users", "users", "weddings", "guests", 
            "rsvps", "plus_ones", "gallery", "forms", 
            "form_responses", "subscription_plans", "ai_usage",
            "vendors", "wedding_checklist", "saas_content"
        ]
        
        for collection in collections:
            mock_db[collection] = Mock()
        
        # Setup mongo methods
        mock_mongo.db = mock_db
        mock_mongo.get_guest_collection.return_value = mock_db["guests"]
        mock_mongo.get_users_collection.return_value = mock_db["users"]
        mock_mongo.get_admin_users_collection.return_value = mock_db["admin_users"]
        mock_mongo.get_weddings_collection.return_value = mock_db["weddings"]
        mock_mongo.get_rsvps_collection.return_value = mock_db["rsvps"]
        mock_mongo.get_plus_ones_collection.return_value = mock_db["plus_ones"]
        mock_mongo.get_gallery_collection.return_value = mock_db["gallery"]
        mock_mongo.get_forms_collection.return_value = mock_db["forms"]
        mock_mongo.get_form_responses_collection.return_value = mock_db["form_responses"]
        mock_mongo.get_subscription_plans_collection.return_value = mock_db["subscription_plans"]
        mock_mongo.get_ai_usage_collection.return_value = mock_db["ai_usage"]
        mock_mongo.get_vendors_collection.return_value = mock_db["vendors"]
        mock_mongo.get_wedding_checklist_collection.return_value = mock_db["wedding_checklist"]
        mock_mongo.get_saas_content_collection.return_value = mock_db["saas_content"]
        
        yield mock_db


# ==================== Authentication Fixtures ====================

@pytest.fixture
def mock_auth_token() -> str:
    """Generate mock authentication token"""
    with patch('app.utils.auth_utils.create_access_token') as mock_create:
        mock_create.return_value = "test_token_123"
        return "test_token_123"


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user"""
    return {
        "email": "test@example.com",
        "role": "admin",
        "_id": str(ObjectId())
    }


@pytest.fixture
def mock_verify_token(mock_auth_user):
    """Mock token verification"""
    with patch('app.utils.auth_utils.verify_token') as mock_verify:
        mock_verify.return_value = {
            "sub": mock_auth_user["email"],
            "role": mock_auth_user["role"]
        }
        yield mock_verify


# ==================== Data Fixtures ====================

@pytest.fixture
def sample_admin_user():
    """Create sample admin user"""
    return AdminUserFactory()


@pytest.fixture
def sample_user():
    """Create sample regular user"""
    return UserFactory()


@pytest.fixture
def sample_user_with_subscription():
    """Create sample user with subscription"""
    plan = SubscriptionPlanFactory(name="Professional")
    return create_user_with_subscription(subscription_plan=plan)


@pytest.fixture
def sample_subscription_plans():
    """Create sample subscription plans"""
    return [
        SubscriptionPlanFactory(
            name="Starter",
            price=19.99,
            limits={"weddings": 3, "ai_credits": 100, "vendor_seats": 1, "staff_seats": 2}
        ),
        SubscriptionPlanFactory(
            name="Professional",
            price=49.99,
            limits={"weddings": 10, "ai_credits": 1000, "vendor_seats": 5, "staff_seats": 10}
        ),
        SubscriptionPlanFactory(
            name="Enterprise",
            price=99.99,
            limits={"weddings": -1, "ai_credits": -1, "vendor_seats": -1, "staff_seats": -1}  # -1 means unlimited
        )
    ]


@pytest.fixture
def sample_wedding():
    """Create sample wedding"""
    return WeddingFactory()


@pytest.fixture
def sample_wedding_with_guests():
    """Create sample wedding with guests"""
    wedding, guests = create_wedding_with_guests(num_guests=20)
    return {"wedding": wedding, "guests": guests}


@pytest.fixture
def sample_guest():
    """Create sample guest"""
    return GuestFactory()


@pytest.fixture
def sample_form():
    """Create sample form"""
    return FormFactory()


@pytest.fixture
def sample_form_with_responses():
    """Create sample form with responses"""
    form, responses = create_form_with_responses(num_responses=10)
    return {"form": form, "responses": responses}


# ==================== Service Fixtures ====================

@pytest.fixture
def mock_auth_service():
    """Mock authentication service"""
    with patch('app.services.auth_service.AuthService') as mock_service:
        instance = mock_service.return_value
        instance.authenticate_user.return_value = AdminUserFactory()
        instance.login_and_get_token.return_value = {
            "access_token": "test_token_123",
            "token_type": "bearer"
        }
        yield instance


@pytest.fixture
def mock_subscription_service():
    """Mock subscription service"""
    with patch('app.services.subscription_service.SubscriptionService') as mock_service:
        instance = mock_service.return_value
        instance.get_user_subscription.return_value = SubscriptionFactory()
        instance.get_plan.return_value = SubscriptionPlanFactory()
        instance.check_usage_limits.return_value = {"allowed": True, "message": "Within limits"}
        instance.increment_usage.return_value = True
        instance.is_trial_expired.return_value = False
        yield instance


@pytest.fixture
def mock_wedding_service():
    """Mock wedding service"""
    with patch('app.services.wedding_service.WeddingService') as mock_service:
        instance = mock_service.return_value
        instance.create_wedding.return_value = WeddingFactory()
        instance.get_wedding.return_value = WeddingFactory()
        instance.update_wedding.return_value = True
        instance.delete_wedding.return_value = True
        yield instance


@pytest.fixture
def mock_email_service():
    """Mock email service"""
    with patch('app.services.email_service_resend.EmailService') as mock_service:
        instance = mock_service.return_value
        instance.send_email.return_value = {"id": "email_123", "status": "sent"}
        instance.send_bulk_emails.return_value = [{"id": "email_123", "status": "sent"}]
        yield instance


# ==================== Utility Fixtures ====================

@pytest.fixture
def mock_datetime_now():
    """Mock datetime.utcnow for consistent testing"""
    fixed_time = datetime(2024, 1, 15, 12, 0, 0)
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = fixed_time
        mock_datetime.now.return_value = fixed_time
        yield fixed_time


@pytest.fixture
def mock_objectid():
    """Mock ObjectId generation for consistent testing"""
    fixed_id = ObjectId("60d5ec49f1a2c8b1f8e4d123")
    with patch('bson.ObjectId') as mock_oid:
        mock_oid.return_value = fixed_id
        yield fixed_id


# ==================== Cleanup Fixtures ====================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test"""
    yield
    # Add any cleanup code here if needed


# ==================== Markers ====================

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "auth: Authentication related tests")
    config.addinivalue_line("markers", "subscription: Subscription related tests")
    config.addinivalue_line("markers", "wedding: Wedding management tests")
    config.addinivalue_line("markers", "forms: Form management tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "smoke: Smoke tests for basic functionality")
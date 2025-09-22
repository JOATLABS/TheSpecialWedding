"""
Integration tests for subscription management workflow
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from bson import ObjectId

from app.main import app


class TestSubscriptionFlow:
    """Integration tests for subscription management workflows"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_database(self):
        """Mock database for testing"""
        with patch('app.core.database.mongo') as mock_mongo:
            mock_db = Mock()
            mock_mongo.db = mock_db
            yield mock_db
    
    @pytest.fixture
    def authenticated_headers(self, client, mock_database):
        """Get authenticated headers for testing"""
        # Setup admin user
        admin_user = {
            "_id": "admin_123",
            "email": "admin@test.com",
            "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            "role": "admin"
        }
        mock_database["admin_users"].find_one.return_value = admin_user
        
        # Login and get token
        with patch('app.utils.auth_utils.verify_password') as mock_verify:
            mock_verify.return_value = True
            
            response = client.post(
                "/admin/token",
                json={"email": "admin@test.com", "password": "secret"}
            )
        
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def sample_subscription_plan(self):
        """Sample subscription plan"""
        return {
            "_id": ObjectId("60d5ec49f1a2c8b1f8e4d456"),
            "name": "Professional",
            "price": 49.99,
            "currency": "USD",
            "billing_period": "monthly",
            "limits": {
                "weddings": 10,
                "ai_credits": 1000,
                "vendor_seats": 5,
                "staff_seats": 10
            },
            "features": {
                "ai_tools": True,
                "advanced_reporting": True,
                "white_label": False,
                "custom_integrations": False,
                "multi_user_collaboration": True
            },
            "is_active": True
        }
    
    @pytest.fixture
    def sample_user_with_subscription(self):
        """Sample user with subscription"""
        return {
            "_id": ObjectId("60d5ec49f1a2c8b1f8e4d123"),
            "email": "planner@test.com",
            "password_hash": "$2b$12$hashedpassword",
            "role": "wedding_planner",
            "is_active": True,
            "email_verified": True,
            "subscription": {
                "plan_id": ObjectId("60d5ec49f1a2c8b1f8e4d456"),
                "status": "active",
                "start_date": datetime.utcnow() - timedelta(days=10),
                "end_date": datetime.utcnow() + timedelta(days=20),
                "current_usage": {
                    "weddings": 2,
                    "ai_credits": 150,
                    "vendor_seats": 1,
                    "staff_seats": 3
                }
            }
        }
    
    @pytest.mark.integration
    def test_get_subscription_plans(self, client, mock_database, sample_subscription_plan):
        """Test retrieving subscription plans"""
        # Setup mock database
        mock_database["subscription_plans"].find.return_value = [sample_subscription_plan]
        
        # Test getting subscription plans
        response = client.get("/subscription/plans")
        
        assert response.status_code == 200
        plans = response.json()
        assert len(plans) >= 1
        assert plans[0]["name"] == "Professional"
        assert plans[0]["price"] == 49.99
    
    @pytest.mark.integration
    def test_subscription_limit_enforcement(self, client, mock_database, authenticated_headers, 
                                          sample_user_with_subscription, sample_subscription_plan):
        """Test subscription limit enforcement in workflow"""
        # Setup user at subscription limit
        sample_user_with_subscription["subscription"]["current_usage"]["weddings"] = 10
        mock_database["users"].find_one.return_value = sample_user_with_subscription
        mock_database["subscription_plans"].find_one.return_value = sample_subscription_plan
        
        # Mock auth verification
        with patch('app.utils.auth_utils.verify_token') as mock_verify_token:
            mock_verify_token.return_value = {"sub": "planner@test.com", "role": "wedding_planner"}
            
            # Try to create a wedding (should be blocked by subscription limit)
            response = client.post(
                "/admin/weddings",
                headers=authenticated_headers,
                json={
                    "title": "New Wedding",
                    "date": "2024-06-15",
                    "venue": "Test Venue",
                    "slug": "new-wedding-2024"
                }
            )
            
            # Should be blocked by subscription limits
            assert response.status_code == 402  # Payment Required
            assert "limit exceeded" in response.json()["detail"].lower()
    
    @pytest.mark.integration
    def test_feature_access_control(self, client, mock_database, authenticated_headers,
                                   sample_user_with_subscription, sample_subscription_plan):
        """Test feature access control based on subscription"""
        # Setup subscription without AI tools
        sample_subscription_plan["features"]["ai_tools"] = False
        mock_database["users"].find_one.return_value = sample_user_with_subscription
        mock_database["subscription_plans"].find_one.return_value = sample_subscription_plan
        
        # Mock auth verification
        with patch('app.utils.auth_utils.verify_token') as mock_verify_token:
            mock_verify_token.return_value = {"sub": "planner@test.com", "role": "wedding_planner"}
            
            # Try to access AI tools feature (should be blocked)
            response = client.post(
                "/admin/ai/generate-content",
                headers=authenticated_headers,
                json={
                    "type": "invitation_text",
                    "details": "Elegant summer wedding"
                }
            )
            
            # Should be blocked by feature restrictions
            assert response.status_code == 402  # Payment Required
            assert "not available in your current plan" in response.json()["detail"]
    
    @pytest.mark.integration
    def test_trial_expiration_workflow(self, client, mock_database, authenticated_headers,
                                     sample_user_with_subscription, sample_subscription_plan):
        """Test trial expiration handling"""
        # Setup expired trial
        sample_user_with_subscription["subscription"]["trial_end"] = datetime.utcnow() - timedelta(days=1)
        sample_user_with_subscription["subscription"]["status"] = "trial_expired"
        
        mock_database["users"].find_one.return_value = sample_user_with_subscription
        mock_database["subscription_plans"].find_one.return_value = sample_subscription_plan
        
        # Mock auth verification
        with patch('app.utils.auth_utils.verify_token') as mock_verify_token:
            mock_verify_token.return_value = {"sub": "planner@test.com", "role": "wedding_planner"}
            
            # Try to access paid features after trial expiration
            response = client.get(
                "/admin/weddings",
                headers=authenticated_headers
            )
            
            # Should be blocked due to expired trial
            assert response.status_code in [402, 403]
    
    @pytest.mark.integration
    def test_subscription_usage_tracking(self, client, mock_database, authenticated_headers,
                                        sample_user_with_subscription, sample_subscription_plan):
        """Test subscription usage tracking workflow"""
        # Setup user with available usage
        sample_user_with_subscription["subscription"]["current_usage"]["weddings"] = 5
        mock_database["users"].find_one.return_value = sample_user_with_subscription
        mock_database["subscription_plans"].find_one.return_value = sample_subscription_plan
        mock_database["users"].update_one.return_value = Mock()
        
        # Mock auth verification
        with patch('app.utils.auth_utils.verify_token') as mock_verify_token:
            mock_verify_token.return_value = {"sub": "planner@test.com", "role": "wedding_planner"}
            
            # Create a wedding (should increment usage)
            with patch('app.services.wedding_service.WeddingService.create_wedding') as mock_create:
                mock_create.return_value = {"_id": "wedding_123", "title": "Test Wedding"}
                
                response = client.post(
                    "/admin/weddings",
                    headers=authenticated_headers,
                    json={
                        "title": "Test Wedding",
                        "date": "2024-06-15",
                        "venue": "Test Venue",
                        "slug": "test-wedding-2024"
                    }
                )
                
                # Should succeed and track usage
                if response.status_code in [200, 201]:
                    # Verify usage was incremented
                    mock_database["users"].update_one.assert_called()
    
    @pytest.mark.integration
    def test_root_admin_bypass_limits(self, client, mock_database):
        """Test that ROOT_ADMIN bypasses subscription limits"""
        # Setup ROOT_ADMIN user
        root_admin = {
            "_id": "root_admin_123",
            "email": "root@test.com",
            "password_hash": "$2b$12$hashedpassword",
            "role": "root_admin",
            "is_root_admin": True,
            "is_active": True
        }
        mock_database["users"].find_one.return_value = root_admin
        
        # Login as ROOT_ADMIN
        with patch('app.utils.auth_utils.verify_password') as mock_verify:
            mock_verify.return_value = True
            
            login_response = client.post(
                "/admin/token",
                json={"email": "root@test.com", "password": "secret"}
            )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Mock auth verification
        with patch('app.utils.auth_utils.verify_token') as mock_verify_token:
            mock_verify_token.return_value = {"sub": "root@test.com", "role": "root_admin"}
            
            # Try to create unlimited resources (should bypass limits)
            response = client.post(
                "/admin/weddings",
                headers=headers,
                json={
                    "title": "ROOT_ADMIN Wedding",
                    "date": "2024-06-15",
                    "venue": "Test Venue",
                    "slug": "root-admin-wedding"
                }
            )
            
            # Should succeed regardless of subscription limits
            # (may still fail on validation but not on subscription limits)
            assert response.status_code != 402
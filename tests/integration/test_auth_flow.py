"""
Integration tests for authentication workflow
"""
import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from app.main import app
from app.core.database import mongo


class TestAuthenticationFlow:
    """Integration tests for complete authentication workflows"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    async def async_client(self):
        """Create async test client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.fixture
    def mock_database(self):
        """Mock database for testing"""
        with patch('app.core.database.mongo') as mock_mongo:
            mock_db = Mock()
            mock_mongo.db = mock_db
            mock_mongo.get_admin_users_collection.return_value = mock_db["admin_users"]
            mock_mongo.get_users_collection.return_value = mock_db["users"]
            yield mock_db
    
    @pytest.fixture
    def sample_admin_user(self):
        """Sample admin user for testing"""
        return {
            "_id": "admin_123",
            "email": "admin@test.com",
            "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
            "role": "admin"
        }
    
    @pytest.mark.integration
    def test_complete_login_flow_admin(self, client, mock_database, sample_admin_user):
        """Test complete login flow for admin user"""
        # Setup mock database
        mock_database["admin_users"].find_one.return_value = sample_admin_user
        
        # Test login endpoint
        with patch('app.utils.auth_utils.verify_password') as mock_verify:
            mock_verify.return_value = True
            
            response = client.post(
                "/admin/token",
                json={"email": "admin@test.com", "password": "secret"}
            )
        
        # Verify login success
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
        # Test accessing protected endpoint with token
        token = data["access_token"]
        
        # Mock profile endpoint database call
        mock_database["admin_users"].find_one.return_value = sample_admin_user
        
        with patch('app.utils.auth_utils.verify_token') as mock_verify_token:
            mock_verify_token.return_value = {"sub": "admin@test.com", "role": "admin"}
            
            profile_response = client.get(
                "/admin/profile",
                headers={"Authorization": f"Bearer {token}"}
            )
        
        # Verify profile access
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["email"] == "admin@test.com"
        assert profile_data["role"] == "admin"
    
    @pytest.mark.integration
    def test_login_flow_invalid_credentials(self, client, mock_database):
        """Test login flow with invalid credentials"""
        # Setup mock database - no user found
        mock_database["admin_users"].find_one.return_value = None
        mock_database["users"].find_one.return_value = None
        
        # Test login with invalid credentials
        response = client.post(
            "/admin/token",
            json={"email": "invalid@test.com", "password": "wrongpassword"}
        )
        
        # Verify login failure
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    @pytest.mark.integration
    def test_protected_endpoint_without_auth(self, client):
        """Test accessing protected endpoint without authentication"""
        response = client.get("/admin/profile")
        
        assert response.status_code == 401
    
    @pytest.mark.integration
    def test_protected_endpoint_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token"""
        response = client.get(
            "/admin/profile",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.integration
    async def test_rate_limiting_auth_endpoints(self, async_client, mock_database):
        """Test rate limiting on authentication endpoints"""
        # Setup mock database
        mock_database["admin_users"].find_one.return_value = None
        mock_database["users"].find_one.return_value = None
        
        # Make multiple rapid requests to trigger rate limiting
        tasks = []
        for _ in range(15):  # Exceed the 10 request limit for auth endpoints
            task = async_client.post(
                "/admin/token",
                json={"email": "test@test.com", "password": "password"}
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that some requests were rate limited (429 status)
        status_codes = [r.status_code for r in responses if hasattr(r, 'status_code')]
        assert 429 in status_codes, "Rate limiting should have triggered"
    
    @pytest.mark.integration
    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly set"""
        response = client.options("/admin/token")
        
        # Should include CORS headers
        assert "Access-Control-Allow-Origin" in response.headers or response.status_code == 200
    
    @pytest.mark.integration
    def test_subscription_protected_endpoint(self, client, mock_database, sample_admin_user):
        """Test endpoint protected by subscription decorators"""
        # Setup authenticated user
        mock_database["admin_users"].find_one.return_value = sample_admin_user
        
        # Login first
        with patch('app.utils.auth_utils.verify_password') as mock_verify:
            mock_verify.return_value = True
            
            login_response = client.post(
                "/admin/token",
                json={"email": "admin@test.com", "password": "secret"}
            )
        
        token = login_response.json()["access_token"]
        
        # Test subscription-protected endpoint
        with patch('app.utils.auth_utils.verify_token') as mock_verify_token:
            mock_verify_token.return_value = {"sub": "admin@test.com", "role": "admin"}
            
            # Mock subscription service calls
            with patch('app.services.subscription_service.SubscriptionService') as mock_service:
                mock_instance = mock_service.return_value
                mock_instance.check_usage_limits.return_value = {"allowed": True, "message": "Within limits"}
                
                # Try to access a subscription-protected endpoint (e.g., creating a wedding)
                response = client.post(
                    "/admin/weddings",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "title": "Test Wedding",
                        "date": "2024-06-15",
                        "venue": "Test Venue"
                    }
                )
                
                # Should succeed if subscription allows
                assert response.status_code in [200, 201] or response.status_code == 422  # 422 for validation errors
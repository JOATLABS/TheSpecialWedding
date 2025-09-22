"""
Test suite for authentication endpoints
"""
import pytest
import requests
import os
from typing import Dict, Any

# Test configuration
BASE_URL = os.getenv("NEXT_PUBLIC_API_BASE_URL")
ADMIN_EMAIL = os.getenv("PRIMARY_ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("PRIMARY_ADMIN_PASSWORD")

# Ensure required environment variables are set
assert BASE_URL, "NEXT_PUBLIC_API_BASE_URL environment variable is required"
assert ADMIN_EMAIL, "PRIMARY_ADMIN_EMAIL environment variable is required"
assert ADMIN_PASSWORD, "PRIMARY_ADMIN_PASSWORD environment variable is required"


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.base_url = BASE_URL
        self.session = requests.Session()
        
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = self.session.get(f"{self.base_url}/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
    def test_admin_login_success(self):
        """Test successful admin login"""
        response = self.session.post(
            f"{self.base_url}/admin/token",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        
    def test_admin_login_invalid_credentials(self):
        """Test admin login with invalid credentials"""
        response = self.session.post(
            f"{self.base_url}/admin/token",
            json={
                "email": "invalid@email.com",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
        
    def test_admin_login_missing_fields(self):
        """Test admin login with missing fields"""
        response = self.session.post(
            f"{self.base_url}/admin/token",
            json={"email": ADMIN_EMAIL}
        )
        assert response.status_code == 422
        
    def test_protected_endpoint_without_token(self):
        """Test accessing protected endpoint without token"""
        response = self.session.get(f"{self.base_url}/admin/profile")
        assert response.status_code == 401
        
    def test_protected_endpoint_with_valid_token(self):
        """Test accessing protected endpoint with valid token"""
        # First get a token
        login_response = self.session.post(
            f"{self.base_url}/admin/token",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            }
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        # Then use it to access protected endpoint
        response = self.session.get(
            f"{self.base_url}/admin/profile",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "role" in data
        
    def test_protected_endpoint_with_invalid_token(self):
        """Test accessing protected endpoint with invalid token"""
        response = self.session.get(
            f"{self.base_url}/admin/profile",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
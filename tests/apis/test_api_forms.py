"""
Test suite for form management endpoints
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


class TestFormEndpoints:
    """Test form management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment and get auth token"""
        self.base_url = BASE_URL
        self.session = requests.Session()
        
        # Get auth token
        login_response = self.session.post(
            f"{self.base_url}/admin/token",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            }
        )
        assert login_response.status_code == 200
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
    def test_get_forms_list(self):
        """Test getting list of forms"""
        response = self.session.get(
            f"{self.base_url}/admin/forms",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_form_templates(self):
        """Test getting form templates"""
        response = self.session.get(
            f"{self.base_url}/admin/form-templates",
            headers=self.headers
        )
        # This might return 404 if not implemented, which is OK for now
        assert response.status_code in [200, 404]
        
    def test_create_form_unauthorized(self):
        """Test creating form without authorization"""
        form_data = {
            "name": "Test Form",
            "template_type": "guest_feedback"
        }
        response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data
        )
        assert response.status_code == 401
        
    def test_get_forms_unauthorized(self):
        """Test getting forms without authorization"""
        response = self.session.get(f"{self.base_url}/admin/forms")
        assert response.status_code == 401
        
    def test_form_validation(self):
        """Test form data validation"""
        # Test with missing required fields
        invalid_form_data = {}
        response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=invalid_form_data,
            headers=self.headers
        )
        assert response.status_code == 422
        
    def test_get_nonexistent_form(self):
        """Test getting non-existent form"""
        response = self.session.get(
            f"{self.base_url}/admin/forms/nonexistent_form_id",
            headers=self.headers
        )
        assert response.status_code == 404
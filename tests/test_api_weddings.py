"""
Test suite for wedding management endpoints
"""
import pytest
import requests
import os
from typing import Dict, Any

# Test configuration
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "j89x8G&8SM8^m")


class TestWeddingEndpoints:
    """Test wedding management endpoints"""
    
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
        
    def test_get_weddings_list(self):
        """Test getting list of weddings"""
        response = self.session.get(
            f"{self.base_url}/weddings",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_wedding_by_slug(self):
        """Test getting wedding by slug"""
        # First get list of weddings to find a valid slug
        weddings_response = self.session.get(
            f"{self.base_url}/weddings",
            headers=self.headers
        )
        assert weddings_response.status_code == 200
        weddings = weddings_response.json()
        
        if weddings:
            wedding = weddings[0]
            slug = wedding.get("slug")
            if slug:
                response = self.session.get(f"{self.base_url}/weddings/slug/{slug}")
                assert response.status_code == 200
                data = response.json()
                assert data["slug"] == slug
                
    def test_get_nonexistent_wedding_by_slug(self):
        """Test getting non-existent wedding by slug"""
        response = self.session.get(f"{self.base_url}/weddings/slug/nonexistent-slug")
        assert response.status_code == 404
        
    def test_create_wedding_unauthorized(self):
        """Test creating wedding without authorization"""
        wedding_data = {
            "_id": "test_wedding_123",
            "couple_names": "Test Couple",
            "date": "2025-12-25",
            "slug": "test-wedding-123"
        }
        response = self.session.post(
            f"{self.base_url}/weddings",
            json=wedding_data
        )
        assert response.status_code == 401
        
    def test_wedding_validation(self):
        """Test wedding data validation"""
        # Test with missing required fields
        invalid_wedding_data = {
            "couple_names": "Test Couple"
            # Missing required fields like _id, date, slug
        }
        response = self.session.post(
            f"{self.base_url}/weddings",
            json=invalid_wedding_data,
            headers=self.headers
        )
        assert response.status_code == 422
"""
Form Builder API Test Suite
===========================

Comprehensive API testing for the Form Builder system endpoints.
Tests all CRUD operations, validation, and edge cases.

Author: Claude Code Testing Framework
"""

import pytest
import requests
import json
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test Configuration
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8002")
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "j89x8G&8SM8^m")


class FormBuilderAPITest:
    """Test suite for Form Builder API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment and authenticate"""
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
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Store created form IDs for cleanup
        self.created_forms = []
    
    def teardown_method(self):
        """Cleanup created forms after each test"""
        for form_id in self.created_forms:
            try:
                self.session.delete(
                    f"{self.base_url}/admin/forms/{form_id}",
                    headers=self.headers
                )
            except:
                pass  # Ignore cleanup errors
    
    def test_health_check(self):
        """Test API health check"""
        response = self.session.get(f"{self.base_url}/")
        assert response.status_code == 200
    
    def test_get_forms_list_empty(self):
        """Test getting empty forms list"""
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
        assert response.status_code == 200
        
        data = response.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)
        
        # Verify template structure
        for template in data["templates"]:
            assert "id" in template
            assert "name" in template
            assert "description" in template
            assert "fields" in template
            assert isinstance(template["fields"], list)
    
    def test_create_form_basic(self):
        """Test basic form creation"""
        form_data = {
            "name": "Basic Test Form",
            "settings": {
                "title": "Test Form",
                "description": "A simple test form",
                "submit_button_text": "Submit",
                "success_message": "Thank you!",
                "allow_multiple_submissions": False,
                "collect_email": True,
                "is_public": True,
                "requires_auth": False
            },
            "fields": [
                {
                    "id": "test_field",
                    "label": "Test Field",
                    "type": "text",
                    "required": True,
                    "order": 1
                }
            ]
        }
        
        response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "message" in data
        
        # Store for cleanup
        self.created_forms.append(data["id"])
    
    def test_create_form_complex(self):
        """Test complex form creation with all field types"""
        form_data = {
            "name": "Complex Test Form",
            "settings": {
                "title": "Complex Form Test",
                "description": "Testing all field types",
                "submit_button_text": "Submit Complex Form",
                "success_message": "Complex form submitted!",
                "allow_multiple_submissions": True,
                "collect_email": True,
                "is_public": False,
                "requires_auth": True
            },
            "fields": [
                {
                    "id": "text_field",
                    "label": "Text Input",
                    "type": "text",
                    "required": True,
                    "order": 1,
                    "placeholder": "Enter text..."
                },
                {
                    "id": "email_field",
                    "label": "Email Address",
                    "type": "email",
                    "required": True,
                    "order": 2
                },
                {
                    "id": "phone_field",
                    "label": "Phone Number",
                    "type": "phone",
                    "required": False,
                    "order": 3
                },
                {
                    "id": "number_field",
                    "label": "Number Input",
                    "type": "number",
                    "required": False,
                    "order": 4
                },
                {
                    "id": "date_field",
                    "label": "Date Picker",
                    "type": "date",
                    "required": False,
                    "order": 5
                },
                {
                    "id": "textarea_field",
                    "label": "Text Area",
                    "type": "textarea",
                    "required": False,
                    "order": 6,
                    "placeholder": "Enter multiple lines..."
                },
                {
                    "id": "select_field",
                    "label": "Dropdown Selection",
                    "type": "select",
                    "required": True,
                    "order": 7,
                    "options": ["Option 1", "Option 2", "Option 3"]
                },
                {
                    "id": "radio_field",
                    "label": "Radio Buttons",
                    "type": "radio",
                    "required": True,
                    "order": 8,
                    "options": ["Choice A", "Choice B", "Choice C"]
                },
                {
                    "id": "checkbox_field",
                    "label": "Checkboxes",
                    "type": "checkbox",
                    "required": False,
                    "order": 9,
                    "options": ["Item 1", "Item 2", "Item 3", "Item 4"]
                },
                {
                    "id": "rating_field",
                    "label": "Star Rating",
                    "type": "rating",
                    "required": True,
                    "order": 10,
                    "description": "Rate from 1 to 5 stars"
                },
                {
                    "id": "scale_field",
                    "label": "Scale Rating",
                    "type": "scale",
                    "required": True,
                    "order": 11,
                    "description": "Rate from 1 to 10"
                }
            ],
            "wedding_id": "test_wedding_123",
            "template_type": "custom"
        }
        
        response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        
        # Store for cleanup
        form_id = data["id"]
        self.created_forms.append(form_id)
        
        # Verify form retrieval
        get_response = self.session.get(
            f"{self.base_url}/admin/forms/{form_id}",
            headers=self.headers
        )
        
        assert get_response.status_code == 200
        form_data_retrieved = get_response.json()
        
        # Verify field count and types
        assert len(form_data_retrieved["fields"]) == 11
        field_types = {field["type"] for field in form_data_retrieved["fields"]}
        expected_types = {"text", "email", "phone", "number", "date", "textarea", 
                         "select", "radio", "checkbox", "rating", "scale"}
        assert field_types == expected_types
    
    def test_create_form_validation_errors(self):
        """Test form creation validation"""
        
        # Test missing required fields
        invalid_forms = [
            {},  # Empty payload
            {"name": "Test"},  # Missing settings and fields
            {
                "name": "Test",
                "settings": {
                    "title": "Test"
                }
                # Missing fields array
            },
            {
                "name": "Test",
                "settings": {
                    "title": "Test"
                },
                "fields": []  # Empty fields array
            },
            {
                "name": "Test",
                "settings": {
                    "title": "Test"
                },
                "fields": [
                    {
                        "id": "field1",
                        "label": "Field 1",
                        "type": "text",
                        "required": True,
                        "order": 1
                    },
                    {
                        "id": "field1",  # Duplicate ID
                        "label": "Field 2",
                        "type": "email",
                        "required": True,
                        "order": 2
                    }
                ]
            }
        ]
        
        for invalid_form in invalid_forms:
            response = self.session.post(
                f"{self.base_url}/admin/forms",
                json=invalid_form,
                headers=self.headers
            )
            assert response.status_code in [400, 422], f"Expected validation error for: {invalid_form}"
    
    def test_create_form_from_template(self):
        """Test creating form from template"""
        response = self.session.post(
            f"{self.base_url}/admin/forms/from-template/wedding_feedback",
            params={
                "form_name": "Template Test Form",
                "wedding_id": "test_wedding_123"
            },
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        
        form_id = data["id"]
        self.created_forms.append(form_id)
        
        # Verify the form was created with template data
        get_response = self.session.get(
            f"{self.base_url}/admin/forms/{form_id}",
            headers=self.headers
        )
        
        assert get_response.status_code == 200
        form_data = get_response.json()
        assert form_data["template_type"] == "wedding_feedback"
        assert len(form_data["fields"]) > 0
    
    def test_get_form_by_id(self):
        """Test retrieving specific form"""
        # Create a form first
        form_data = {
            "name": "Retrieval Test Form",
            "settings": {
                "title": "Test Retrieval",
                "submit_button_text": "Submit"
            },
            "fields": [
                {
                    "id": "test_field",
                    "label": "Test Field",
                    "type": "text",
                    "required": True,
                    "order": 1
                }
            ]
        }
        
        create_response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        assert create_response.status_code == 200
        form_id = create_response.json()["id"]
        self.created_forms.append(form_id)
        
        # Retrieve the form
        get_response = self.session.get(
            f"{self.base_url}/admin/forms/{form_id}",
            headers=self.headers
        )
        
        assert get_response.status_code == 200
        retrieved_form = get_response.json()
        
        # Verify form structure
        required_keys = ["id", "name", "settings", "fields", "created_by", "created_at", "is_active"]
        for key in required_keys:
            assert key in retrieved_form
        
        assert retrieved_form["name"] == form_data["name"]
        assert retrieved_form["settings"]["title"] == form_data["settings"]["title"]
    
    def test_update_form(self):
        """Test form update functionality"""
        # Create a form first
        form_data = {
            "name": "Update Test Form",
            "settings": {
                "title": "Original Title",
                "submit_button_text": "Submit"
            },
            "fields": [
                {
                    "id": "original_field",
                    "label": "Original Field",
                    "type": "text",
                    "required": True,
                    "order": 1
                }
            ]
        }
        
        create_response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        assert create_response.status_code == 200
        form_id = create_response.json()["id"]
        self.created_forms.append(form_id)
        
        # Update the form
        update_data = {
            "name": "Updated Test Form",
            "settings": {
                "title": "Updated Title",
                "description": "Updated description",
                "submit_button_text": "Send Updated"
            },
            "fields": [
                {
                    "id": "updated_field",
                    "label": "Updated Field",
                    "type": "email",
                    "required": False,
                    "order": 1,
                    "placeholder": "Enter email..."
                },
                {
                    "id": "new_field",
                    "label": "New Field",
                    "type": "textarea",
                    "required": True,
                    "order": 2
                }
            ]
        }
        
        update_response = self.session.put(
            f"{self.base_url}/admin/forms/{form_id}",
            json=update_data,
            headers=self.headers
        )
        
        assert update_response.status_code == 200
        
        # Verify updates were applied
        get_response = self.session.get(
            f"{self.base_url}/admin/forms/{form_id}",
            headers=self.headers
        )
        
        assert get_response.status_code == 200
        updated_form = get_response.json()
        
        assert updated_form["name"] == update_data["name"]
        assert updated_form["settings"]["title"] == update_data["settings"]["title"]
        assert updated_form["settings"]["description"] == update_data["settings"]["description"]
        assert len(updated_form["fields"]) == 2
    
    def test_public_form_access(self):
        """Test public form access endpoints"""
        # Create a public form first
        form_data = {
            "name": "Public Test Form",
            "settings": {
                "title": "Public Form",
                "is_public": True,
                "submit_button_text": "Submit"
            },
            "fields": [
                {
                    "id": "public_field",
                    "label": "Public Field",
                    "type": "text",
                    "required": True,
                    "order": 1
                }
            ]
        }
        
        create_response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        assert create_response.status_code == 200
        form_id = create_response.json()["id"]
        self.created_forms.append(form_id)
        
        # Test public access (no authentication)
        public_session = requests.Session()
        public_response = public_session.get(
            f"{self.base_url}/public/forms/{form_id}"
        )
        
        assert public_response.status_code == 200
        public_form = public_response.json()
        
        # Verify only safe data is exposed
        allowed_keys = {"id", "settings", "fields", "is_active"}
        assert set(public_form.keys()).issubset(allowed_keys)
        
        # Verify essential data is present
        assert "settings" in public_form
        assert "fields" in public_form
        assert public_form["settings"]["title"] == "Public Form"
    
    def test_form_submission(self):
        """Test form submission endpoint"""
        # Create a form with various field types
        form_data = {
            "name": "Submission Test Form",
            "settings": {
                "title": "Submission Test",
                "is_public": True,
                "allow_multiple_submissions": True,
                "submit_button_text": "Submit"
            },
            "fields": [
                {
                    "id": "name_field",
                    "label": "Name",
                    "type": "text",
                    "required": True,
                    "order": 1
                },
                {
                    "id": "email_field",
                    "label": "Email",
                    "type": "email",
                    "required": True,
                    "order": 2
                },
                {
                    "id": "rating_field",
                    "label": "Rating",
                    "type": "rating",
                    "required": True,
                    "order": 3
                },
                {
                    "id": "optional_field",
                    "label": "Optional Field",
                    "type": "textarea",
                    "required": False,
                    "order": 4
                }
            ]
        }
        
        create_response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        assert create_response.status_code == 200
        form_id = create_response.json()["id"]
        self.created_forms.append(form_id)
        
        # Submit form response
        submission_data = {
            "responses": {
                "name_field": "John Doe",
                "email_field": "john.doe@example.com",
                "rating_field": 5,
                "optional_field": "This is an optional comment"
            },
            "submitted_by_email": "john.doe@example.com",
            "submitted_by_name": "John Doe"
        }
        
        public_session = requests.Session()
        submit_response = public_session.post(
            f"{self.base_url}/public/forms/{form_id}/submit",
            json=submission_data
        )
        
        assert submit_response.status_code == 200
        submit_data = submit_response.json()
        
        assert "id" in submit_data
        assert "message" in submit_data
        
        # Verify submission was saved (check via admin endpoint)
        responses_response = self.session.get(
            f"{self.base_url}/admin/forms/{form_id}/responses",
            headers=self.headers
        )
        
        assert responses_response.status_code == 200
        responses = responses_response.json()
        
        assert len(responses) >= 1
        assert responses[0]["responses"]["name_field"] == "John Doe"
    
    def test_form_validation_on_submission(self):
        """Test form submission validation"""
        # Create a form with required fields
        form_data = {
            "name": "Validation Test Form",
            "settings": {
                "title": "Validation Test",
                "is_public": True,
                "submit_button_text": "Submit"
            },
            "fields": [
                {
                    "id": "required_field",
                    "label": "Required Field",
                    "type": "text",
                    "required": True,
                    "order": 1
                },
                {
                    "id": "optional_field",
                    "label": "Optional Field",
                    "type": "text",
                    "required": False,
                    "order": 2
                }
            ]
        }
        
        create_response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        assert create_response.status_code == 200
        form_id = create_response.json()["id"]
        self.created_forms.append(form_id)
        
        # Test submission with missing required field
        invalid_submission = {
            "responses": {
                "optional_field": "This is provided"
                # Missing required_field
            },
            "submitted_by_email": "test@example.com",
            "submitted_by_name": "Test User"
        }
        
        public_session = requests.Session()
        invalid_response = public_session.post(
            f"{self.base_url}/public/forms/{form_id}/submit",
            json=invalid_submission
        )
        
        assert invalid_response.status_code == 400
        error_data = invalid_response.json()
        assert "required" in error_data["detail"].lower()
    
    def test_get_form_responses(self):
        """Test retrieving form responses"""
        # Create form and submit response first
        form_data = {
            "name": "Responses Test Form",
            "settings": {
                "title": "Responses Test",
                "is_public": True,
                "submit_button_text": "Submit"
            },
            "fields": [
                {
                    "id": "test_field",
                    "label": "Test Field",
                    "type": "text",
                    "required": True,
                    "order": 1
                }
            ]
        }
        
        create_response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        form_id = create_response.json()["id"]
        self.created_forms.append(form_id)
        
        # Submit multiple responses
        for i in range(3):
            submission = {
                "responses": {
                    "test_field": f"Response {i + 1}"
                },
                "submitted_by_email": f"user{i + 1}@example.com",
                "submitted_by_name": f"User {i + 1}"
            }
            
            public_session = requests.Session()
            public_session.post(
                f"{self.base_url}/public/forms/{form_id}/submit",
                json=submission
            )
        
        # Retrieve responses
        responses_response = self.session.get(
            f"{self.base_url}/admin/forms/{form_id}/responses",
            headers=self.headers
        )
        
        assert responses_response.status_code == 200
        responses = responses_response.json()
        
        assert len(responses) == 3
        
        # Verify response structure
        for response in responses:
            required_keys = ["id", "form_id", "responses", "submitted_at"]
            for key in required_keys:
                assert key in response
    
    def test_get_form_analytics(self):
        """Test form analytics endpoint"""
        # Create a form first
        form_data = {
            "name": "Analytics Test Form",
            "settings": {
                "title": "Analytics Test",
                "submit_button_text": "Submit"
            },
            "fields": [
                {
                    "id": "test_field",
                    "label": "Test Field",
                    "type": "text",
                    "required": True,
                    "order": 1
                }
            ]
        }
        
        create_response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        form_id = create_response.json()["id"]
        self.created_forms.append(form_id)
        
        # Get analytics
        analytics_response = self.session.get(
            f"{self.base_url}/admin/forms/{form_id}/analytics",
            headers=self.headers
        )
        
        assert analytics_response.status_code == 200
        analytics = analytics_response.json()
        
        # Verify analytics structure
        required_keys = ["form_id", "form_name", "total_responses", "distribution_stats"]
        for key in required_keys:
            assert key in analytics
        
        # Verify distribution stats structure
        dist_stats = analytics["distribution_stats"]
        stat_keys = ["sent", "opened", "clicked", "submitted", "completion_rate"]
        for key in stat_keys:
            assert key in dist_stats
    
    def test_delete_form(self):
        """Test form deletion"""
        # Create a form first
        form_data = {
            "name": "Delete Test Form",
            "settings": {
                "title": "Delete Test",
                "submit_button_text": "Submit"
            },
            "fields": [
                {
                    "id": "test_field",
                    "label": "Test Field",
                    "type": "text",
                    "required": True,
                    "order": 1
                }
            ]
        }
        
        create_response = self.session.post(
            f"{self.base_url}/admin/forms",
            json=form_data,
            headers=self.headers
        )
        
        form_id = create_response.json()["id"]
        
        # Delete the form
        delete_response = self.session.delete(
            f"{self.base_url}/admin/forms/{form_id}",
            headers=self.headers
        )
        
        assert delete_response.status_code == 200
        
        # Verify form is no longer accessible
        get_response = self.session.get(
            f"{self.base_url}/admin/forms/{form_id}",
            headers=self.headers
        )
        
        assert get_response.status_code == 404
    
    def test_unauthorized_access(self):
        """Test unauthorized access to admin endpoints"""
        # Test without authentication
        no_auth_session = requests.Session()
        
        endpoints = [
            f"{self.base_url}/admin/forms",
            f"{self.base_url}/admin/form-templates",
            f"{self.base_url}/admin/forms/test_id",
            f"{self.base_url}/admin/forms/test_id/responses",
            f"{self.base_url}/admin/forms/test_id/analytics"
        ]
        
        for endpoint in endpoints:
            response = no_auth_session.get(endpoint)
            assert response.status_code == 401, f"Expected 401 for {endpoint}"
    
    def test_form_not_found(self):
        """Test accessing non-existent forms"""
        non_existent_id = "non_existent_form_12345"
        
        # Test admin endpoints
        admin_endpoints = [
            f"{self.base_url}/admin/forms/{non_existent_id}",
            f"{self.base_url}/admin/forms/{non_existent_id}/responses",
            f"{self.base_url}/admin/forms/{non_existent_id}/analytics"
        ]
        
        for endpoint in admin_endpoints:
            response = self.session.get(endpoint, headers=self.headers)
            assert response.status_code == 404
        
        # Test public endpoint
        public_session = requests.Session()
        public_response = public_session.get(
            f"{self.base_url}/public/forms/{non_existent_id}"
        )
        assert public_response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
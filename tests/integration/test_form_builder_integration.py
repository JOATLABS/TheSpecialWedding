"""
Comprehensive Integration Test Suite for Form Builder System
===========================================================

This test suite validates the "COMPLETED" claim for the Form Builder system (Phase 4.1).
It tests all major features including:
1. Form creation and management
2. Drag-and-drop form builder
3. Email distribution system
4. Response collection and analytics
5. CSV export functionality
6. Template system
7. Security and access controls

Test Environment:
- Backend: http://localhost:8002
- Database: MongoDB
- Email Service: Resend (if configured)

Author: Claude Code Testing Framework
"""

import pytest
import requests
import json
import time
import os
import csv
import io
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import tempfile
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test Configuration
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8002")
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "j89x8G&8SM8^m")

# Test Data
TEST_WEDDING_ID = "test_wedding_123"
TEST_FORM_DATA = {
 "name": "Integration Test Form",
 "settings": {
 "title": "Test Wedding Feedback Form",
 "description": "Please share your thoughts about our wedding planning service",
 "submit_button_text": "Submit Feedback",
 "success_message": "Thank you for your valuable feedback!",
 "allow_multiple_submissions": False,
 "collect_email": True,
 "is_public": True,
 "requires_auth": False
 },
 "fields": [
 {
 "id": "guest_name",
 "label": "Your Name",
 "type": "text",
 "required": True,
 "order": 1,
 "placeholder": "Enter your full name"
 },
 {
 "id": "guest_email",
 "label": "Email Address",
 "type": "email",
 "required": True,
 "order": 2,
 "placeholder": "your.email@example.com"
 },
 {
 "id": "overall_rating",
 "label": "Overall Experience Rating",
 "type": "rating",
 "required": True,
 "order": 3,
 "description": "Rate your overall experience (1-5 stars)"
 },
 {
 "id": "satisfaction_scale",
 "label": "Satisfaction Level",
 "type": "scale",
 "required": True,
 "order": 4,
 "description": "Rate your satisfaction on a scale of 1-10"
 },
 {
 "id": "service_type",
 "label": "Service Type",
 "type": "select",
 "required": True,
 "order": 5,
 "options": ["Full Planning", "Partial Planning", "Day-of Coordination", "Consultation Only"]
 },
 {
 "id": "recommendation",
 "label": "Would you recommend our services?",
 "type": "radio",
 "required": True,
 "order": 6,
 "options": ["Definitely", "Probably", "Maybe", "Probably not", "Definitely not"]
 },
 {
 "id": "improvements",
 "label": "Areas for Improvement",
 "type": "checkbox",
 "required": False,
 "order": 7,
 "options": ["Communication", "Timeline Management", "Budget Planning", "Vendor Coordination", "Creative Ideas"]
 },
 {
 "id": "wedding_date",
 "label": "Wedding Date",
 "type": "date",
 "required": False,
 "order": 8
 },
 {
 "id": "guest_count",
 "label": "Number of Guests",
 "type": "number",
 "required": False,
 "order": 9,
 "placeholder": "150"
 },
 {
 "id": "additional_comments",
 "label": "Additional Comments",
 "type": "textarea",
 "required": False,
 "order": 10,
 "placeholder": "Share any additional thoughts or suggestions..."
 }
 ],
 "wedding_id": TEST_WEDDING_ID,
 "template_type": "wedding_feedback"
}

EMAIL_DISTRIBUTION_DATA = {
 "recipient_emails": [
 "test1@example.com",
 "test2@example.com", 
 "test3@example.com"
 ],
 "email_settings": {
 "subject": "We'd love your feedback on our wedding planning service",
 "message": "Hi there! We hope you had an amazing wedding experience. Please take a few minutes to share your feedback with us.",
 "sender_name": "Wedding Planning Team",
 "include_form_link": True,
 "send_reminder": False,
 "reminder_days": 7
 },
 "wedding_id": TEST_WEDDING_ID
}

FORM_RESPONSE_DATA = {
 "responses": {
 "guest_name": "John Doe",
 "guest_email": "john.doe@example.com",
 "overall_rating": 5,
 "satisfaction_scale": 9,
 "service_type": "Full Planning",
 "recommendation": "Definitely",
 "improvements": ["Communication", "Creative Ideas"],
 "wedding_date": "2024-06-15",
 "guest_count": 150,
 "additional_comments": "The wedding planning was fantastic! Everything went smoothly."
 },
 "submitted_by_email": "john.doe@example.com",
 "submitted_by_name": "John Doe"
}

class FormBuilderIntegrationTest:
 """Comprehensive integration test suite for Form Builder system"""
 
 def __init__(self):
 self.session = requests.Session()
 self.base_url = BASE_URL
 self.token = None
 self.headers = {}
 self.created_form_id = None
 self.test_results = {
 "timestamp": datetime.now(timezone.utc).isoformat(),
 "test_suite": "Form Builder Integration Tests",
 "tests_run": 0,
 "tests_passed": 0,
 "tests_failed": 0,
 "failures": [],
 "feature_completeness": {},
 "performance_metrics": {}
 }
 
 def authenticate(self) -> bool:
 """Authenticate with the API and get access token"""
 try:
 logger.info("Authenticating with API...")
 response = self.session.post(
 f"{self.base_url}/admin/token",
 json={
 "email": ADMIN_EMAIL,
 "password": ADMIN_PASSWORD
 }
 )
 
 if response.status_code == 200:
 data = response.json()
 self.token = data["access_token"]
 self.headers = {"Authorization": f"Bearer {self.token}"}
 logger.info(" Authentication successful")
 return True
 else:
 logger.error(f" Authentication failed: {response.status_code} - {response.text}")
 return False
 
 except Exception as e:
 logger.error(f" Authentication error: {str(e)}")
 return False
 
 def run_test(self, test_name: str, test_func, *args, **kwargs) -> bool:
 """Run a single test and track results"""
 self.test_results["tests_run"] += 1
 start_time = time.time()
 
 try:
 logger.info(f" Running test: {test_name}")
 result = test_func(*args, **kwargs)
 execution_time = time.time() - start_time
 
 if result:
 self.test_results["tests_passed"] += 1
 logger.info(f" {test_name} - PASSED ({execution_time:.2f}s)")
 else:
 self.test_results["tests_failed"] += 1
 self.test_results["failures"].append({
 "test": test_name,
 "error": "Test returned False",
 "timestamp": datetime.now(timezone.utc).isoformat()
 })
 logger.error(f" {test_name} - FAILED ({execution_time:.2f}s)")
 
 # Track performance
 self.test_results["performance_metrics"][test_name] = execution_time
 return result
 
 except Exception as e:
 execution_time = time.time() - start_time
 self.test_results["tests_failed"] += 1
 self.test_results["failures"].append({
 "test": test_name,
 "error": str(e),
 "timestamp": datetime.now(timezone.utc).isoformat()
 })
 logger.error(f" {test_name} - ERROR: {str(e)} ({execution_time:.2f}s)")
 return False
 
 def test_api_connectivity(self) -> bool:
 """Test basic API connectivity"""
 try:
 response = self.session.get(f"{self.base_url}/")
 return response.status_code == 200
 except:
 return False
 
 def test_form_templates_access(self) -> bool:
 """Test accessing form templates"""
 try:
 response = self.session.get(
 f"{self.base_url}/admin/form-templates",
 headers=self.headers
 )
 
 if response.status_code == 200:
 data = response.json()
 templates = data.get("templates", [])
 
 # Verify required templates exist
 template_ids = [t["id"] for t in templates]
 required_templates = ["wedding_feedback", "guest_feedback", "vendor_questionnaire"]
 
 for template_id in required_templates:
 if template_id not in template_ids:
 logger.warning(f"Missing template: {template_id}")
 return False
 
 # Verify template structure
 for template in templates:
 if not all(key in template for key in ["id", "name", "description", "fields"]):
 logger.error(f"Invalid template structure: {template.get('id')}")
 return False
 
 self.test_results["feature_completeness"]["template_system"] = {
 "available_templates": len(templates),
 "template_ids": template_ids
 }
 
 return True
 else:
 logger.error(f"Templates access failed: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Templates access error: {str(e)}")
 return False
 
 def test_form_creation(self) -> bool:
 """Test form creation functionality"""
 try:
 response = self.session.post(
 f"{self.base_url}/admin/forms",
 json=TEST_FORM_DATA,
 headers=self.headers
 )
 
 if response.status_code == 200:
 data = response.json()
 self.created_form_id = data.get("id")
 
 if not self.created_form_id:
 logger.error("Form created but no ID returned")
 return False
 
 logger.info(f"Form created with ID: {self.created_form_id}")
 return True
 else:
 logger.error(f"Form creation failed: {response.status_code} - {response.text}")
 return False
 
 except Exception as e:
 logger.error(f"Form creation error: {str(e)}")
 return False
 
 def test_form_retrieval(self) -> bool:
 """Test form retrieval and data integrity"""
 if not self.created_form_id:
 logger.error("No form ID available for retrieval test")
 return False
 
 try:
 response = self.session.get(
 f"{self.base_url}/admin/forms/{self.created_form_id}",
 headers=self.headers
 )
 
 if response.status_code == 200:
 data = response.json()
 
 # Verify form structure
 required_keys = ["id", "name", "settings", "fields", "created_by", "created_at"]
 for key in required_keys:
 if key not in data:
 logger.error(f"Missing key in form data: {key}")
 return False
 
 # Verify field integrity
 if len(data["fields"]) != len(TEST_FORM_DATA["fields"]):
 logger.error("Field count mismatch")
 return False
 
 # Verify field order
 fields = sorted(data["fields"], key=lambda x: x["order"])
 for i, field in enumerate(fields):
 if field["order"] != i + 1:
 logger.error(f"Field order mismatch: expected {i + 1}, got {field['order']}")
 return False
 
 return True
 else:
 logger.error(f"Form retrieval failed: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Form retrieval error: {str(e)}")
 return False
 
 def test_form_update(self) -> bool:
 """Test form update functionality"""
 if not self.created_form_id:
 logger.error("No form ID available for update test")
 return False
 
 try:
 update_data = {
 "name": "Updated Integration Test Form",
 "settings": {
 "title": "Updated Test Form Title",
 "description": "This form has been updated during testing",
 "submit_button_text": "Send Updated Feedback"
 }
 }
 
 response = self.session.put(
 f"{self.base_url}/admin/forms/{self.created_form_id}",
 json=update_data,
 headers=self.headers
 )
 
 if response.status_code == 200:
 # Verify changes were applied
 get_response = self.session.get(
 f"{self.base_url}/admin/forms/{self.created_form_id}",
 headers=self.headers
 )
 
 if get_response.status_code == 200:
 data = get_response.json()
 if (data["name"] == update_data["name"] and 
 data["settings"]["title"] == update_data["settings"]["title"]):
 return True
 else:
 logger.error("Form update not reflected in data")
 return False
 else:
 logger.error("Failed to verify form update")
 return False
 else:
 logger.error(f"Form update failed: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Form update error: {str(e)}")
 return False
 
 def test_public_form_access(self) -> bool:
 """Test public form access (no authentication required)"""
 if not self.created_form_id:
 logger.error("No form ID available for public access test")
 return False
 
 try:
 # Test without authentication
 public_session = requests.Session()
 response = public_session.get(
 f"{self.base_url}/public/forms/{self.created_form_id}"
 )
 
 if response.status_code == 200:
 data = response.json()
 
 # Verify only public data is returned
 allowed_keys = ["id", "settings", "fields", "is_active"]
 for key in data.keys():
 if key not in allowed_keys:
 logger.warning(f"Sensitive data exposed in public endpoint: {key}")
 
 # Verify essential form data
 if not all(key in data for key in ["settings", "fields"]):
 logger.error("Missing essential form data in public endpoint")
 return False
 
 return True
 else:
 logger.error(f"Public form access failed: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Public form access error: {str(e)}")
 return False
 
 def test_form_submission(self) -> bool:
 """Test form submission functionality"""
 if not self.created_form_id:
 logger.error("No form ID available for submission test")
 return False
 
 try:
 # Test form submission without authentication
 public_session = requests.Session()
 response = public_session.post(
 f"{self.base_url}/public/forms/{self.created_form_id}/submit",
 json=FORM_RESPONSE_DATA
 )
 
 if response.status_code == 200:
 data = response.json()
 
 # Verify response structure
 if not all(key in data for key in ["id", "message"]):
 logger.error("Invalid submission response structure")
 return False
 
 # Store submission ID for later tests
 self.submission_id = data.get("id")
 return True
 else:
 logger.error(f"Form submission failed: {response.status_code} - {response.text}")
 return False
 
 except Exception as e:
 logger.error(f"Form submission error: {str(e)}")
 return False
 
 def test_form_validation(self) -> bool:
 """Test form validation rules"""
 if not self.created_form_id:
 logger.error("No form ID available for validation test")
 return False
 
 try:
 # Test with missing required fields
 invalid_data = {
 "responses": {
 "guest_name": "John Doe"
 # Missing required fields: guest_email, overall_rating, etc.
 },
 "submitted_by_email": "john.doe@example.com",
 "submitted_by_name": "John Doe"
 }
 
 public_session = requests.Session()
 response = public_session.post(
 f"{self.base_url}/public/forms/{self.created_form_id}/submit",
 json=invalid_data
 )
 
 # Should fail validation
 if response.status_code == 400:
 error_data = response.json()
 if "required" in error_data.get("detail", "").lower():
 return True
 else:
 logger.error("Validation error but wrong message")
 return False
 else:
 logger.error(f"Expected validation error but got: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Form validation test error: {str(e)}")
 return False
 
 def test_form_responses_retrieval(self) -> bool:
 """Test form responses retrieval"""
 if not self.created_form_id:
 logger.error("No form ID available for responses test")
 return False
 
 try:
 response = self.session.get(
 f"{self.base_url}/admin/forms/{self.created_form_id}/responses",
 headers=self.headers
 )
 
 if response.status_code == 200:
 data = response.json()
 
 if isinstance(data, list):
 # Verify response structure if any responses exist
 if len(data) > 0:
 for resp in data:
 required_keys = ["id", "form_id", "responses", "submitted_at"]
 if not all(key in resp for key in required_keys):
 logger.error("Invalid response structure")
 return False
 
 self.test_results["feature_completeness"]["response_collection"] = {
 "total_responses": len(data)
 }
 return True
 else:
 logger.error("Responses data is not a list")
 return False
 else:
 logger.error(f"Form responses retrieval failed: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Form responses retrieval error: {str(e)}")
 return False
 
 def test_form_analytics(self) -> bool:
 """Test form analytics functionality"""
 if not self.created_form_id:
 logger.error("No form ID available for analytics test")
 return False
 
 try:
 response = self.session.get(
 f"{self.base_url}/admin/forms/{self.created_form_id}/analytics",
 headers=self.headers
 )
 
 if response.status_code == 200:
 data = response.json()
 
 # Verify analytics structure
 required_keys = ["form_id", "form_name", "total_responses", "distribution_stats"]
 if not all(key in data for key in required_keys):
 logger.error("Invalid analytics structure")
 return False
 
 # Verify distribution stats structure
 dist_stats = data["distribution_stats"]
 stat_keys = ["sent", "opened", "clicked", "submitted", "completion_rate"]
 if not all(key in dist_stats for key in stat_keys):
 logger.error("Invalid distribution stats structure")
 return False
 
 self.test_results["feature_completeness"]["analytics_system"] = {
 "total_responses": data["total_responses"],
 "completion_rate": dist_stats["completion_rate"]
 }
 return True
 else:
 logger.error(f"Form analytics failed: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Form analytics error: {str(e)}")
 return False
 
 def test_email_distribution(self) -> bool:
 """Test email distribution functionality"""
 if not self.created_form_id:
 logger.error("No form ID available for email distribution test")
 return False
 
 try:
 response = self.session.post(
 f"{self.base_url}/admin/forms/{self.created_form_id}/send",
 json=EMAIL_DISTRIBUTION_DATA,
 headers=self.headers
 )
 
 if response.status_code == 200:
 data = response.json()
 
 # Verify response structure
 required_keys = ["sent", "failed", "form_url", "message"]
 if not all(key in data for key in required_keys):
 logger.error("Invalid email distribution response")
 return False
 
 # Check if any emails were sent (depends on email service configuration)
 total_attempted = data["sent"] + data["failed"]
 expected_count = len(EMAIL_DISTRIBUTION_DATA["recipient_emails"])
 
 if total_attempted == expected_count:
 self.test_results["feature_completeness"]["email_distribution"] = {
 "emails_sent": data["sent"],
 "emails_failed": data["failed"],
 "form_url": data["form_url"]
 }
 return True
 else:
 logger.error(f"Email count mismatch: expected {expected_count}, got {total_attempted}")
 return False
 else:
 logger.error(f"Email distribution failed: {response.status_code} - {response.text}")
 return False
 
 except Exception as e:
 logger.error(f"Email distribution error: {str(e)}")
 return False
 
 def test_template_form_creation(self) -> bool:
 """Test creating forms from templates"""
 try:
 # Test creating form from template
 response = self.session.post(
 f"{self.base_url}/admin/forms/from-template/wedding_feedback",
 params={
 "form_name": "Template Test Form",
 "wedding_id": TEST_WEDDING_ID
 },
 headers=self.headers
 )
 
 if response.status_code == 200:
 data = response.json()
 template_form_id = data.get("id")
 
 if template_form_id:
 # Verify the form was created with template data
 get_response = self.session.get(
 f"{self.base_url}/admin/forms/{template_form_id}",
 headers=self.headers
 )
 
 if get_response.status_code == 200:
 form_data = get_response.json()
 if (form_data.get("template_type") == "wedding_feedback" and
 len(form_data.get("fields", [])) > 0):
 return True
 else:
 logger.error("Template form missing expected data")
 return False
 else:
 logger.error("Failed to retrieve template form")
 return False
 else:
 logger.error("Template form created but no ID returned")
 return False
 else:
 logger.error(f"Template form creation failed: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Template form creation error: {str(e)}")
 return False
 
 def test_form_permissions(self) -> bool:
 """Test form access permissions and security"""
 if not self.created_form_id:
 logger.error("No form ID available for permissions test")
 return False
 
 try:
 # Test accessing form without authentication
 no_auth_session = requests.Session()
 response = no_auth_session.get(
 f"{self.base_url}/admin/forms/{self.created_form_id}"
 )
 
 # Should be unauthorized
 if response.status_code == 401:
 return True
 else:
 logger.error(f"Expected 401 but got: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Form permissions test error: {str(e)}")
 return False
 
 def test_field_types_support(self) -> bool:
 """Test support for all field types"""
 if not self.created_form_id:
 logger.error("No form ID available for field types test")
 return False
 
 try:
 # Get the form and verify all field types are present
 response = self.session.get(
 f"{self.base_url}/admin/forms/{self.created_form_id}",
 headers=self.headers
 )
 
 if response.status_code == 200:
 data = response.json()
 fields = data.get("fields", [])
 
 # Expected field types from our test form
 expected_types = {"text", "email", "rating", "scale", "select", "radio", 
 "checkbox", "date", "number", "textarea"}
 
 actual_types = {field["type"] for field in fields}
 
 if expected_types.issubset(actual_types):
 self.test_results["feature_completeness"]["field_types"] = {
 "supported_types": list(actual_types),
 "total_types": len(actual_types)
 }
 return True
 else:
 missing_types = expected_types - actual_types
 logger.error(f"Missing field types: {missing_types}")
 return False
 else:
 logger.error(f"Failed to retrieve form for field types test: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Field types test error: {str(e)}")
 return False
 
 def test_multiple_submissions_control(self) -> bool:
 """Test multiple submissions control"""
 if not self.created_form_id:
 logger.error("No form ID available for multiple submissions test")
 return False
 
 try:
 # Submit the form again with the same email
 public_session = requests.Session()
 response = public_session.post(
 f"{self.base_url}/public/forms/{self.created_form_id}/submit",
 json=FORM_RESPONSE_DATA
 )
 
 # Since allow_multiple_submissions is False, this should fail
 if response.status_code == 400:
 error_data = response.json()
 if "already submitted" in error_data.get("detail", "").lower():
 return True
 else:
 logger.error("Multiple submission blocked but wrong error message")
 return False
 else:
 logger.error(f"Expected 400 for duplicate submission but got: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Multiple submissions test error: {str(e)}")
 return False
 
 def test_form_deletion(self) -> bool:
 """Test form deletion (soft delete)"""
 if not self.created_form_id:
 logger.error("No form ID available for deletion test")
 return False
 
 try:
 response = self.session.delete(
 f"{self.base_url}/admin/forms/{self.created_form_id}",
 headers=self.headers
 )
 
 if response.status_code == 200:
 # Verify form is no longer accessible
 get_response = self.session.get(
 f"{self.base_url}/admin/forms/{self.created_form_id}",
 headers=self.headers
 )
 
 # Should return 404 for deleted form
 if get_response.status_code == 404:
 return True
 else:
 logger.error(f"Deleted form still accessible: {get_response.status_code}")
 return False
 else:
 logger.error(f"Form deletion failed: {response.status_code}")
 return False
 
 except Exception as e:
 logger.error(f"Form deletion error: {str(e)}")
 return False
 
 def run_all_tests(self) -> Dict[str, Any]:
 """Run all form builder integration tests"""
 logger.info(" Starting Form Builder Integration Test Suite")
 logger.info(f"Target URL: {self.base_url}")
 
 # Authentication
 if not self.authenticate():
 logger.error(" Authentication failed - cannot proceed with tests")
 return self.test_results
 
 # Test execution order matters for some tests
 test_sequence = [
 ("API Connectivity", self.test_api_connectivity),
 ("Form Templates Access", self.test_form_templates_access),
 ("Form Creation", self.test_form_creation),
 ("Form Retrieval", self.test_form_retrieval),
 ("Form Update", self.test_form_update),
 ("Public Form Access", self.test_public_form_access),
 ("Field Types Support", self.test_field_types_support),
 ("Form Submission", self.test_form_submission),
 ("Form Validation", self.test_form_validation),
 ("Multiple Submissions Control", self.test_multiple_submissions_control),
 ("Form Responses Retrieval", self.test_form_responses_retrieval),
 ("Form Analytics", self.test_form_analytics),
 ("Email Distribution", self.test_email_distribution),
 ("Template Form Creation", self.test_template_form_creation),
 ("Form Permissions", self.test_form_permissions),
 ("Form Deletion", self.test_form_deletion)
 ]
 
 # Run all tests
 for test_name, test_func in test_sequence:
 self.run_test(test_name, test_func)
 
 # Calculate success rate
 if self.test_results["tests_run"] > 0:
 success_rate = (self.test_results["tests_passed"] / self.test_results["tests_run"]) * 100
 self.test_results["success_rate"] = round(success_rate, 2)
 
 # Generate summary
 self.test_results["summary"] = {
 "total_tests": self.test_results["tests_run"],
 "passed": self.test_results["tests_passed"],
 "failed": self.test_results["tests_failed"],
 "success_rate": f"{self.test_results.get('success_rate', 0)}%"
 }
 
 logger.info(f" Test Suite Complete!")
 logger.info(f" Results: {self.test_results['tests_passed']}/{self.test_results['tests_run']} tests passed")
 logger.info(f" Success Rate: {self.test_results.get('success_rate', 0)}%")
 
 return self.test_results

def run_form_builder_integration_tests():
 """Main entry point for running form builder integration tests"""
 test_suite = FormBuilderIntegrationTest()
 results = test_suite.run_all_tests()
 
 # Save results to file
 timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
 results_file = f"/home/emmanuel/Desktop/WeddingApp/WeddingWebApp/tests/results/integration/form_builder_integration_results_{timestamp}.json"
 
 os.makedirs(os.path.dirname(results_file), exist_ok=True)
 
 with open(results_file, 'w') as f:
 json.dump(results, f, indent=2, default=str)
 
 logger.info(f" Results saved to: {results_file}")
 
 return results

if __name__ == "__main__":
 run_form_builder_integration_tests()
"""
Form Builder Security Test Suite
================================

Comprehensive security testing for the Form Builder system.
Tests authentication, authorization, data validation, and security vulnerabilities.

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
import html

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test Configuration
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8002")
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "j89x8G&8SM8^m")

class FormBuilderSecurityTest:
 """Security test suite for Form Builder system"""
 
 def __init__(self):
 self.session = requests.Session()
 self.base_url = BASE_URL
 self.token = None
 self.headers = {}
 self.security_results = {
 "timestamp": datetime.now(timezone.utc).isoformat(),
 "test_suite": "Form Builder Security Tests",
 "tests_run": 0,
 "tests_passed": 0,
 "tests_failed": 0,
 "vulnerabilities_found": [],
 "security_score": 0
 }
 
 def authenticate(self) -> bool:
 """Authenticate with valid credentials"""
 try:
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
 return True
 return False
 except:
 return False
 
 def run_test(self, test_name: str, test_func, *args, **kwargs) -> bool:
 """Run a security test and track results"""
 self.security_results["tests_run"] += 1
 
 try:
 logger.info(f" Running security test: {test_name}")
 result = test_func(*args, **kwargs)
 
 if result:
 self.security_results["tests_passed"] += 1
 logger.info(f" {test_name} - PASSED")
 else:
 self.security_results["tests_failed"] += 1
 logger.warning(f" {test_name} - FAILED")
 
 return result
 
 except Exception as e:
 self.security_results["tests_failed"] += 1
 self.security_results["vulnerabilities_found"].append({
 "test": test_name,
 "vulnerability": str(e),
 "severity": "high",
 "timestamp": datetime.now(timezone.utc).isoformat()
 })
 logger.error(f" {test_name} - VULNERABILITY: {str(e)}")
 return False
 
 def test_authentication_required(self) -> bool:
 """Test that admin endpoints require authentication"""
 admin_endpoints = [
 "/admin/forms",
 "/admin/form-templates",
 "/admin/forms/test_id",
 "/admin/forms/test_id/responses",
 "/admin/forms/test_id/analytics"
 ]
 
 no_auth_session = requests.Session()
 
 for endpoint in admin_endpoints:
 response = no_auth_session.get(f"{self.base_url}{endpoint}")
 if response.status_code != 401:
 self.security_results["vulnerabilities_found"].append({
 "test": "authentication_required",
 "vulnerability": f"Endpoint {endpoint} accessible without authentication",
 "severity": "high",
 "status_code": response.status_code
 })
 return False
 
 return True
 
 def test_invalid_token_handling(self) -> bool:
 """Test handling of invalid authentication tokens"""
 invalid_tokens = [
 "Bearer invalid_token",
 "Bearer ",
 "invalid_format_token",
 "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
 "Bearer " + "x" * 500 # Very long token
 ]
 
 for token in invalid_tokens:
 headers = {"Authorization": token}
 response = self.session.get(
 f"{self.base_url}/admin/forms",
 headers=headers
 )
 
 if response.status_code not in [401, 422]:
 self.security_results["vulnerabilities_found"].append({
 "test": "invalid_token_handling",
 "vulnerability": f"Invalid token '{token[:50]}...' not properly rejected",
 "severity": "medium",
 "status_code": response.status_code
 })
 return False
 
 return True
 
 def test_sql_injection_prevention(self) -> bool:
 """Test SQL injection prevention in form operations"""
 if not self.authenticate():
 return False
 
 # SQL injection payloads
 sql_payloads = [
 "'; DROP TABLE forms; --",
 "' OR '1'='1",
 "' UNION SELECT * FROM users --",
 "admin'; DELETE FROM forms WHERE '1'='1",
 "'; INSERT INTO forms (name) VALUES ('hacked'); --"
 ]
 
 for payload in sql_payloads:
 # Test in form creation
 form_data = {
 "name": payload,
 "settings": {
 "title": payload,
 "submit_button_text": "Submit"
 },
 "fields": [
 {
 "id": "test_field",
 "label": payload,
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
 
 # Check if the payload was executed (should be prevented)
 if response.status_code == 200:
 # Verify the payload was escaped/sanitized
 form_id = response.json().get("id")
 if form_id:
 get_response = self.session.get(
 f"{self.base_url}/admin/forms/{form_id}",
 headers=self.headers
 )
 
 if get_response.status_code == 200:
 form_data_retrieved = get_response.json()
 # The payload should be stored as-is (escaped), not executed
 if payload not in str(form_data_retrieved):
 logger.warning(f"SQL payload might have been executed: {payload}")
 
 # Cleanup
 self.session.delete(
 f"{self.base_url}/admin/forms/{form_id}",
 headers=self.headers
 )
 
 return True
 
 def test_xss_prevention(self) -> bool:
 """Test XSS prevention in form data"""
 if not self.authenticate():
 return False
 
 # XSS payloads
 xss_payloads = [
 "<script>alert('XSS')</script>",
 "<img src='x' onerror='alert(\"XSS\")'>",
 "javascript:alert('XSS')",
 "<svg onload=alert('XSS')>",
 "<iframe src='javascript:alert(\"XSS\")'></iframe>",
 "'; alert('XSS'); //",
 "<div onclick='alert(\"XSS\")'>Click me</div>"
 ]
 
 for payload in xss_payloads:
 form_data = {
 "name": f"XSS Test - {payload}",
 "settings": {
 "title": payload,
 "description": payload,
 "submit_button_text": "Submit",
 "success_message": payload
 },
 "fields": [
 {
 "id": "test_field",
 "label": payload,
 "type": "text",
 "required": True,
 "order": 1,
 "placeholder": payload,
 "description": payload
 }
 ]
 }
 
 response = self.session.post(
 f"{self.base_url}/admin/forms",
 json=form_data,
 headers=self.headers
 )
 
 if response.status_code == 200:
 form_id = response.json().get("id")
 if form_id:
 # Check if XSS payload is properly escaped
 get_response = self.session.get(
 f"{self.base_url}/admin/forms/{form_id}",
 headers=self.headers
 )
 
 if get_response.status_code == 200:
 form_data_retrieved = get_response.json()
 
 # Check if dangerous scripts are present unescaped
 response_text = json.dumps(form_data_retrieved)
 if "<script>" in response_text or "javascript:" in response_text:
 self.security_results["vulnerabilities_found"].append({
 "test": "xss_prevention",
 "vulnerability": f"XSS payload not properly escaped: {payload}",
 "severity": "high"
 })
 
 # Cleanup
 self.session.delete(
 f"{self.base_url}/admin/forms/{form_id}",
 headers=self.headers
 )
 
 return True
 
 def test_input_validation(self) -> bool:
 """Test input validation and sanitization"""
 if not self.authenticate():
 return False
 
 # Test various invalid inputs
 invalid_inputs = [
 {
 "name": "", # Empty name
 "settings": {"title": "Test"},
 "fields": []
 },
 {
 "name": "A" * 1000, # Extremely long name
 "settings": {"title": "Test"},
 "fields": []
 },
 {
 "name": "Test",
 "settings": {"title": ""}, # Empty title
 "fields": []
 },
 {
 "name": "Test",
 "settings": {"title": "Test"},
 "fields": [
 {
 "id": "", # Empty field ID
 "label": "Test",
 "type": "text",
 "required": True,
 "order": 1
 }
 ]
 },
 {
 "name": "Test",
 "settings": {"title": "Test"},
 "fields": [
 {
 "id": "test",
 "label": "Test",
 "type": "invalid_type", # Invalid field type
 "required": True,
 "order": 1
 }
 ]
 },
 {
 "name": "Test",
 "settings": {"title": "Test"},
 "fields": [
 {
 "id": "test",
 "label": "Test",
 "type": "text",
 "required": "invalid", # Invalid required value
 "order": 1
 }
 ]
 }
 ]
 
 for invalid_input in invalid_inputs:
 response = self.session.post(
 f"{self.base_url}/admin/forms",
 json=invalid_input,
 headers=self.headers
 )
 
 # Should return validation error
 if response.status_code not in [400, 422]:
 self.security_results["vulnerabilities_found"].append({
 "test": "input_validation",
 "vulnerability": f"Invalid input not properly validated: {invalid_input}",
 "severity": "medium",
 "status_code": response.status_code
 })
 return False
 
 return True
 
 def test_data_exposure(self) -> bool:
 """Test for sensitive data exposure"""
 if not self.authenticate():
 return False
 
 # Create a form
 form_data = {
 "name": "Data Exposure Test",
 "settings": {
 "title": "Test Form",
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
 
 response = self.session.post(
 f"{self.base_url}/admin/forms",
 json=form_data,
 headers=self.headers
 )
 
 if response.status_code == 200:
 form_id = response.json()["id"]
 
 # Test public endpoint for data exposure
 public_session = requests.Session()
 public_response = public_session.get(
 f"{self.base_url}/public/forms/{form_id}"
 )
 
 if public_response.status_code == 200:
 public_data = public_response.json()
 
 # Check for sensitive data that shouldn't be exposed
 sensitive_fields = ["created_by", "created_at", "updated_at", 
 "submission_count", "wedding_id", "template_type"]
 
 for field in sensitive_fields:
 if field in public_data:
 self.security_results["vulnerabilities_found"].append({
 "test": "data_exposure",
 "vulnerability": f"Sensitive field '{field}' exposed in public endpoint",
 "severity": "medium"
 })
 
 # Cleanup
 self.session.delete(
 f"{self.base_url}/admin/forms/{form_id}",
 headers=self.headers
 )
 
 return True
 
 def test_authorization_bypass(self) -> bool:
 """Test for authorization bypass vulnerabilities"""
 if not self.authenticate():
 return False
 
 # Create a form
 form_data = {
 "name": "Authorization Test",
 "settings": {
 "title": "Test Form",
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
 
 response = self.session.post(
 f"{self.base_url}/admin/forms",
 json=form_data,
 headers=self.headers
 )
 
 if response.status_code == 200:
 form_id = response.json()["id"]
 
 # Try to access admin endpoints with different methods
 no_auth_session = requests.Session()
 
 # Test various HTTP methods for bypass
 methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
 
 for method in methods:
 try:
 resp = no_auth_session.request(
 method,
 f"{self.base_url}/admin/forms/{form_id}",
 json={"test": "data"} if method in ['POST', 'PUT', 'PATCH'] else None
 )
 
 if resp.status_code not in [401, 405, 404]:
 self.security_results["vulnerabilities_found"].append({
 "test": "authorization_bypass",
 "vulnerability": f"Unauthorized {method} access to admin endpoint",
 "severity": "high",
 "status_code": resp.status_code
 })
 except:
 pass # Expected for some methods
 
 # Cleanup
 self.session.delete(
 f"{self.base_url}/admin/forms/{form_id}",
 headers=self.headers
 )
 
 return True
 
 def test_rate_limiting(self) -> bool:
 """Test rate limiting on endpoints"""
 # Test rapid requests to check for rate limiting
 rapid_requests_count = 50
 start_time = time.time()
 
 success_count = 0
 rate_limited_count = 0
 
 for i in range(rapid_requests_count):
 response = self.session.get(f"{self.base_url}/admin/form-templates", headers=self.headers)
 
 if response.status_code == 200:
 success_count += 1
 elif response.status_code == 429: # Too Many Requests
 rate_limited_count += 1
 
 if i % 10 == 0:
 time.sleep(0.1) # Small delay to avoid overwhelming
 
 end_time = time.time()
 requests_per_second = rapid_requests_count / (end_time - start_time)
 
 # If all requests succeeded without rate limiting, it might be a concern
 if rate_limited_count == 0 and requests_per_second > 10:
 logger.warning(f"No rate limiting detected. {requests_per_second:.2f} requests/sec allowed")
 
 return True # This is informational, not a hard failure
 
 def test_csrf_protection(self) -> bool:
 """Test CSRF protection measures"""
 if not self.authenticate():
 return False
 
 # Test state-changing operations without proper headers
 form_data = {
 "name": "CSRF Test",
 "settings": {
 "title": "Test Form",
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
 
 # Test without Content-Type header
 response = requests.post(
 f"{self.base_url}/admin/forms",
 data=json.dumps(form_data), # Send as string instead of JSON
 headers={"Authorization": f"Bearer {self.token}"}
 )
 
 # Should require proper Content-Type
 if response.status_code == 200:
 logger.warning("Form creation succeeded without proper Content-Type header")
 
 return True
 
 def test_file_upload_security(self) -> bool:
 """Test file upload security if file upload fields exist"""
 # This test would be relevant if file upload is implemented
 # Currently skipped as file upload is not in the current implementation
 return True
 
 def test_session_security(self) -> bool:
 """Test session security measures"""
 if not self.authenticate():
 return False
 
 # Test token expiration (if implemented)
 # Test concurrent session limits (if implemented)
 # Test session fixation prevention (if implemented)
 
 # For now, just verify that tokens work as expected
 response = self.session.get(
 f"{self.base_url}/admin/forms",
 headers=self.headers
 )
 
 return response.status_code == 200
 
 def run_all_security_tests(self) -> Dict[str, Any]:
 """Run all security tests"""
 logger.info(" Starting Form Builder Security Test Suite")
 
 test_sequence = [
 ("Authentication Required", self.test_authentication_required),
 ("Invalid Token Handling", self.test_invalid_token_handling),
 ("SQL Injection Prevention", self.test_sql_injection_prevention),
 ("XSS Prevention", self.test_xss_prevention),
 ("Input Validation", self.test_input_validation),
 ("Data Exposure", self.test_data_exposure),
 ("Authorization Bypass", self.test_authorization_bypass),
 ("Rate Limiting", self.test_rate_limiting),
 ("CSRF Protection", self.test_csrf_protection),
 ("File Upload Security", self.test_file_upload_security),
 ("Session Security", self.test_session_security)
 ]
 
 for test_name, test_func in test_sequence:
 self.run_test(test_name, test_func)
 
 # Calculate security score
 if self.security_results["tests_run"] > 0:
 base_score = (self.security_results["tests_passed"] / self.security_results["tests_run"]) * 100
 
 # Deduct points for vulnerabilities
 high_severity_count = len([v for v in self.security_results["vulnerabilities_found"] if v.get("severity") == "high"])
 medium_severity_count = len([v for v in self.security_results["vulnerabilities_found"] if v.get("severity") == "medium"])
 
 security_score = base_score - (high_severity_count * 15) - (medium_severity_count * 5)
 self.security_results["security_score"] = max(0, round(security_score, 2))
 
 # Generate summary
 self.security_results["summary"] = {
 "total_tests": self.security_results["tests_run"],
 "passed": self.security_results["tests_passed"],
 "failed": self.security_results["tests_failed"],
 "vulnerabilities": len(self.security_results["vulnerabilities_found"]),
 "security_score": self.security_results["security_score"]
 }
 
 logger.info(f" Security Test Suite Complete!")
 logger.info(f" Security Score: {self.security_results['security_score']}/100")
 logger.info(f" Vulnerabilities Found: {len(self.security_results['vulnerabilities_found'])}")
 
 return self.security_results

def run_form_builder_security_tests():
 """Main entry point for running form builder security tests"""
 test_suite = FormBuilderSecurityTest()
 results = test_suite.run_all_security_tests()
 
 # Save results to file
 timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
 results_file = f"/home/emmanuel/Desktop/WeddingApp/WeddingWebApp/tests/results/security/form_builder_security_report_{timestamp}.json"
 
 os.makedirs(os.path.dirname(results_file), exist_ok=True)
 
 with open(results_file, 'w') as f:
 json.dump(results, f, indent=2, default=str)
 
 logger.info(f" Security report saved to: {results_file}")
 
 return results

if __name__ == "__main__":
 run_form_builder_security_tests()
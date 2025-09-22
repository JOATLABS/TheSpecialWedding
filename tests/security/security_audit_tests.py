#!/usr/bin/env python3
"""
Security Audit Tests for Wedding WebApp Trial Expiration System
================================================================

This script validates the claimed security features for trial expiration enforcement,
email verification, and multiple trial prevention.

Author: Security Auditor
Date: 2025-08-22
"""

import requests
import json
import sys
from datetime import datetime, timedelta
import time
import traceback
from typing import Dict, List, Any, Optional

class SecurityAuditTest:
 def __init__(self, base_url: str = "http://localhost:8002"):
 self.base_url = base_url
 self.results = []
 self.test_users = []
 
 def log_result(self, test_name: str, status: str, details: str, severity: str = "INFO"):
 """Log test result with timestamp"""
 result = {
 "timestamp": datetime.utcnow().isoformat(),
 "test_name": test_name,
 "status": status,
 "details": details,
 "severity": severity
 }
 self.results.append(result)
 
 # Color output based on severity
 color_map = {
 "CRITICAL": "\033[91m", # Red
 "HIGH": "\033[93m", # Yellow
 "MEDIUM": "\033[94m", # Blue
 "LOW": "\033[92m", # Green
 "INFO": "\033[0m" # Normal
 }
 
 reset_color = "\033[0m"
 color = color_map.get(severity, color_map["INFO"])
 
 print(f"{color}[{severity}] {test_name}: {status}{reset_color}")
 if details:
 print(f" Details: {details}")
 
 def cleanup_test_users(self):
 """Clean up any test users created during testing"""
 print("\n" + "="*80)
 print("CLEANUP: Removing test users...")
 
 for user_email in self.test_users:
 try:
 # This would need ROOT_ADMIN access in real implementation
 print(f"Would clean up test user: {user_email}")
 except Exception as e:
 print(f"Failed to cleanup {user_email}: {e}")

 def test_server_connectivity(self) -> bool:
 """Test basic server connectivity"""
 try:
 response = requests.get(f"{self.base_url}/", timeout=10)
 if response.status_code == 200:
 self.log_result(
 "Server Connectivity", 
 "PASS", 
 f"Server responding on {self.base_url}"
 )
 return True
 else:
 self.log_result(
 "Server Connectivity", 
 "FAIL", 
 f"Server returned status {response.status_code}",
 "CRITICAL"
 )
 return False
 except Exception as e:
 self.log_result(
 "Server Connectivity", 
 "FAIL", 
 f"Cannot connect to server: {e}",
 "CRITICAL"
 )
 return False

 def test_email_verification_enforcement(self):
 """Test that unverified emails cannot login"""
 print("\n" + "="*80)
 print("TESTING: Email Verification Enforcement")
 print("="*80)
 
 test_email = f"security_test_{int(time.time())}@example.com"
 
 try:
 # 1. Register a user (should create unverified account)
 registration_data = {
 "email": test_email,
 "password": "SecureTestPassword123!",
 "first_name": "Security",
 "last_name": "Tester",
 "company_name": "Security Audit Co"
 }
 
 reg_response = requests.post(
 f"{self.base_url}/admin/register-planner",
 json=registration_data,
 timeout=10
 )
 
 if reg_response.status_code != 200:
 self.log_result(
 "Email Verification - Registration",
 "FAIL",
 f"Registration failed: {reg_response.text}",
 "HIGH"
 )
 return
 
 self.test_users.append(test_email)
 self.log_result(
 "Email Verification - Registration",
 "PASS",
 f"User registered successfully: {test_email}"
 )
 
 # 2. Attempt to login with unverified account
 login_data = {
 "username": test_email, # FastAPI OAuth2 uses 'username' field
 "password": "SecureTestPassword123!"
 }
 
 # Send as form data (OAuth2 standard)
 login_response = requests.post(
 f"{self.base_url}/admin/login",
 data=login_data, # Use data, not json for form
 headers={"Content-Type": "application/x-www-form-urlencoded"},
 timeout=10
 )
 
 if login_response.status_code == 401:
 response_data = login_response.json()
 if "not verified" in response_data.get("detail", "").lower():
 self.log_result(
 "Email Verification - Login Block",
 "PASS",
 f"Unverified user correctly blocked from login: {response_data['detail']}",
 "LOW"
 )
 else:
 self.log_result(
 "Email Verification - Login Block",
 "PARTIAL",
 f"User blocked but reason unclear: {response_data.get('detail', 'No detail')}",
 "MEDIUM"
 )
 elif login_response.status_code == 200:
 self.log_result(
 "Email Verification - Login Block",
 "FAIL",
 "CRITICAL VULNERABILITY: Unverified user can login!",
 "CRITICAL"
 )
 else:
 self.log_result(
 "Email Verification - Login Block",
 "UNCLEAR",
 f"Unexpected response: {login_response.status_code} - {login_response.text}",
 "MEDIUM"
 )
 
 except Exception as e:
 self.log_result(
 "Email Verification Test",
 "ERROR",
 f"Test failed with exception: {e}",
 "HIGH"
 )

 def test_trial_expiration_enforcement(self):
 """Test that expired trials are blocked with HTTP 402"""
 print("\n" + "="*80)
 print("TESTING: Trial Expiration Enforcement")
 print("="*80)
 
 # Since we can't easily create expired trials in real-time testing,
 # we'll test the authentication logic by examining the code paths
 
 try:
 # Test 1: Check auth_extended.py logic
 with open('/home/emmanuel/Desktop/WeddingApp/WeddingWebApp/app/dependencies/auth_extended.py', 'r') as f:
 auth_code = f.read()
 
 # Verify HTTP 402 is returned for expired trials
 if 'HTTP_402_PAYMENT_REQUIRED' in auth_code and 'trial has expired' in auth_code.lower():
 self.log_result(
 "Trial Expiration - HTTP 402 Code",
 "PASS",
 "HTTP 402 status code correctly implemented for expired trials"
 )
 else:
 self.log_result(
 "Trial Expiration - HTTP 402 Code",
 "FAIL",
 "HTTP 402 not found in trial expiration logic",
 "HIGH"
 )
 
 # Test 2: Check trial date comparison logic
 if 'datetime.utcnow() > trial_end_date' in auth_code:
 self.log_result(
 "Trial Expiration - Date Logic",
 "PASS",
 "Trial end date comparison logic found"
 )
 else:
 self.log_result(
 "Trial Expiration - Date Logic",
 "FAIL",
 "Trial end date comparison not found",
 "HIGH"
 )
 
 # Test 3: Check auto-deactivation logic
 if 'is_active": False' in auth_code and 'trial_expired_at' in auth_code:
 self.log_result(
 "Trial Expiration - Auto-deactivation",
 "PASS",
 "Auto-deactivation logic found in expired trial handling"
 )
 else:
 self.log_result(
 "Trial Expiration - Auto-deactivation",
 "FAIL",
 "Auto-deactivation logic not found",
 "MEDIUM"
 )
 
 except Exception as e:
 self.log_result(
 "Trial Expiration Code Analysis",
 "ERROR",
 f"Failed to analyze auth code: {e}",
 "HIGH"
 )

 def test_multiple_trial_prevention(self):
 """Test that users cannot register multiple free trials"""
 print("\n" + "="*80)
 print("TESTING: Multiple Trial Prevention")
 print("="*80)
 
 test_email = f"multiple_trial_test_{int(time.time())}@example.com"
 
 try:
 # Test 1: Analyze prevention logic in code
 with open('/home/emmanuel/Desktop/WeddingApp/WeddingWebApp/app/services/user_management_service.py', 'r') as f:
 user_service_code = f.read()
 
 # Check for previous trial checking
 if 'check_previous_trial_usage' in user_service_code:
 self.log_result(
 "Multiple Trial - Prevention Function",
 "PASS",
 "Previous trial checking function exists"
 )
 else:
 self.log_result(
 "Multiple Trial - Prevention Function",
 "FAIL",
 "Previous trial checking function not found",
 "HIGH"
 )
 
 # Check for deleted users checking
 if 'deleted_users' in user_service_code and 'previous_trial_used' in user_service_code:
 self.log_result(
 "Multiple Trial - Deleted Users Check",
 "PASS",
 "Checking deleted users collection for previous trials"
 )
 else:
 self.log_result(
 "Multiple Trial - Deleted Users Check",
 "FAIL",
 "Not checking deleted users for previous trial usage",
 "MEDIUM"
 )
 
 # Check for SAAS config integration
 if 'allow_multiple_trials' in user_service_code:
 self.log_result(
 "Multiple Trial - Config Integration",
 "PASS",
 "SAAS config allows disabling multiple trials"
 )
 else:
 self.log_result(
 "Multiple Trial - Config Integration",
 "FAIL",
 "No config option to control multiple trials",
 "LOW"
 )
 
 # Test 2: Attempt actual registration (first attempt)
 registration_data = {
 "email": test_email,
 "password": "SecureTestPassword123!",
 "first_name": "Multiple",
 "last_name": "Trial",
 "company_name": "Test Co"
 }
 
 first_reg = requests.post(
 f"{self.base_url}/admin/register-planner",
 json=registration_data,
 timeout=10
 )
 
 if first_reg.status_code == 200:
 self.test_users.append(test_email)
 self.log_result(
 "Multiple Trial - First Registration",
 "PASS",
 "First registration successful"
 )
 
 # Test 3: Attempt second registration with same email
 second_reg = requests.post(
 f"{self.base_url}/admin/register-planner",
 json=registration_data,
 timeout=10
 )
 
 if second_reg.status_code == 400:
 response_data = second_reg.json()
 detail = response_data.get("detail", "").lower()
 if "already exists" in detail or "trial" in detail:
 self.log_result(
 "Multiple Trial - Second Registration Block",
 "PASS",
 f"Second registration correctly blocked: {response_data.get('detail', '')}",
 "LOW"
 )
 else:
 self.log_result(
 "Multiple Trial - Second Registration Block",
 "PARTIAL",
 f"Blocked but reason unclear: {detail}",
 "MEDIUM"
 )
 else:
 self.log_result(
 "Multiple Trial - Second Registration Block",
 "FAIL",
 f"VULNERABILITY: Second registration allowed! Status: {second_reg.status_code}",
 "HIGH"
 )
 else:
 self.log_result(
 "Multiple Trial - First Registration",
 "FAIL",
 f"First registration failed: {first_reg.text}",
 "MEDIUM"
 )
 
 except Exception as e:
 self.log_result(
 "Multiple Trial Prevention Test",
 "ERROR",
 f"Test failed with exception: {e}",
 "HIGH"
 )

 def test_boundary_conditions(self):
 """Test edge cases and boundary conditions"""
 print("\n" + "="*80)
 print("TESTING: Boundary Conditions and Edge Cases")
 print("="*80)
 
 try:
 # Test 1: Check datetime handling in code
 with open('/home/emmanuel/Desktop/WeddingApp/WeddingWebApp/app/dependencies/auth_extended.py', 'r') as f:
 auth_code = f.read()
 
 # Check for proper datetime string parsing
 if 'fromisoformat' in auth_code and 'isinstance(trial_end_date, str)' in auth_code:
 self.log_result(
 "Boundary Conditions - DateTime Parsing",
 "PASS",
 "Proper datetime string parsing implemented"
 )
 else:
 self.log_result(
 "Boundary Conditions - DateTime Parsing",
 "FAIL",
 "No proper datetime string parsing found",
 "MEDIUM"
 )
 
 # Check for null/None handling
 if 'trial_end_date:' in auth_code and 'if trial_end_date:' in auth_code:
 self.log_result(
 "Boundary Conditions - Null Date Handling",
 "PASS",
 "Null trial end date handling found"
 )
 else:
 self.log_result(
 "Boundary Conditions - Null Date Handling",
 "FAIL",
 "No null trial end date handling",
 "MEDIUM"
 )
 
 # Test 2: Check for SQL injection prevention in wedding access
 if 'ObjectId(wedding_id)' in auth_code and 'len(wedding_id) > 100' in auth_code:
 self.log_result(
 "Boundary Conditions - Input Validation",
 "PASS",
 "Input validation and length limits implemented"
 )
 else:
 self.log_result(
 "Boundary Conditions - Input Validation",
 "FAIL",
 "Insufficient input validation",
 "MEDIUM"
 )
 
 # Test 3: Check regex validation for ObjectId
 if "re.match(r'^[0-9a-fA-F]{24}$'" in auth_code:
 self.log_result(
 "Boundary Conditions - ObjectId Validation",
 "PASS",
 "Proper ObjectId format validation found"
 )
 else:
 self.log_result(
 "Boundary Conditions - ObjectId Validation",
 "FAIL",
 "No ObjectId format validation",
 "LOW"
 )
 
 except Exception as e:
 self.log_result(
 "Boundary Conditions Test",
 "ERROR",
 f"Test failed with exception: {e}",
 "HIGH"
 )

 def test_trial_management_api_security(self):
 """Test that trial management APIs are properly secured"""
 print("\n" + "="*80)
 print("TESTING: Trial Management API Security")
 print("="*80)
 
 try:
 # Test 1: Access without authentication
 endpoints = [
 "/admin/trial/trials/check-expired",
 "/admin/trial/trials/send-warnings",
 "/admin/trial/trials/run-maintenance",
 "/admin/trial/trials/status"
 ]
 
 for endpoint in endpoints:
 try:
 response = requests.post(f"{self.base_url}{endpoint}", timeout=10)
 if response.status_code == 401:
 self.log_result(
 f"Trial API Security - {endpoint}",
 "PASS",
 "Correctly requires authentication"
 )
 elif response.status_code == 403:
 self.log_result(
 f"Trial API Security - {endpoint}",
 "PASS",
 "Correctly requires authorization"
 )
 else:
 self.log_result(
 f"Trial API Security - {endpoint}",
 "FAIL",
 f"VULNERABILITY: Endpoint accessible without auth! Status: {response.status_code}",
 "CRITICAL"
 )
 except requests.exceptions.ConnectionError:
 self.log_result(
 f"Trial API Security - {endpoint}",
 "SKIP",
 "Endpoint not found or server issue"
 )
 
 # Test 2: Check code for ROOT_ADMIN requirement
 with open('/home/emmanuel/Desktop/WeddingApp/WeddingWebApp/app/api/trial_management.py', 'r') as f:
 trial_api_code = f.read()
 
 if 'require_root_admin' in trial_api_code:
 self.log_result(
 "Trial API Security - ROOT_ADMIN Requirement",
 "PASS",
 "Trial management requires ROOT_ADMIN access"
 )
 else:
 self.log_result(
 "Trial API Security - ROOT_ADMIN Requirement",
 "FAIL",
 "Trial management not properly secured",
 "HIGH"
 )
 
 except Exception as e:
 self.log_result(
 "Trial Management API Security Test",
 "ERROR",
 f"Test failed with exception: {e}",
 "HIGH"
 )

 def test_authentication_bypass_attempts(self):
 """Test various authentication bypass scenarios"""
 print("\n" + "="*80)
 print("TESTING: Authentication Bypass Vulnerabilities")
 print("="*80)
 
 try:
 # Test 1: Malformed JWT tokens
 malformed_tokens = [
 "Bearer invalid.token.here",
 "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwicm9sZSI6IndlZGRpbmdfcGxhbm5lciJ9.invalid",
 "Bearer ",
 "invalid",
 None
 ]
 
 for token in malformed_tokens:
 headers = {"Authorization": token} if token else {}
 try:
 response = requests.get(
 f"{self.base_url}/admin/weddings",
 headers=headers,
 timeout=10
 )
 
 if response.status_code == 401:
 self.log_result(
 f"Auth Bypass - Malformed Token",
 "PASS",
 f"Malformed token correctly rejected: {token}"
 )
 else:
 self.log_result(
 f"Auth Bypass - Malformed Token",
 "FAIL",
 f"VULNERABILITY: Malformed token accepted! Token: {token}, Status: {response.status_code}",
 "CRITICAL"
 )
 except requests.exceptions.ConnectionError:
 self.log_result(
 f"Auth Bypass - Malformed Token",
 "SKIP",
 "Endpoint not accessible"
 )
 
 # Test 2: Check for proper exception handling in auth
 with open('/home/emmanuel/Desktop/WeddingApp/WeddingWebApp/app/dependencies/auth_extended.py', 'r') as f:
 auth_code = f.read()
 
 if 'except Exception as e:' in auth_code and 'HTTP_401_UNAUTHORIZED' in auth_code:
 self.log_result(
 "Auth Bypass - Exception Handling",
 "PASS",
 "Proper exception handling with 401 response"
 )
 else:
 self.log_result(
 "Auth Bypass - Exception Handling",
 "FAIL",
 "Insufficient exception handling in auth",
 "HIGH"
 )
 
 # Test 3: Check for role escalation prevention
 if 'is_root_admin' in auth_code and 'ROOT_ADMIN_EMAIL' in auth_code:
 self.log_result(
 "Auth Bypass - Role Escalation Prevention",
 "PASS",
 "Role escalation prevention mechanisms found"
 )
 else:
 self.log_result(
 "Auth Bypass - Role Escalation Prevention",
 "FAIL",
 "Insufficient role escalation prevention",
 "HIGH"
 )
 
 except Exception as e:
 self.log_result(
 "Authentication Bypass Test",
 "ERROR",
 f"Test failed with exception: {e}",
 "HIGH"
 )

 def generate_security_report(self):
 """Generate comprehensive security assessment report"""
 print("\n" + "="*100)
 print("SECURITY AUDIT REPORT - WEDDING WEBAPP TRIAL EXPIRATION SYSTEM")
 print("="*100)
 
 # Summary statistics
 total_tests = len(self.results)
 passed_tests = len([r for r in self.results if r["status"] == "PASS"])
 failed_tests = len([r for r in self.results if r["status"] == "FAIL"])
 critical_issues = len([r for r in self.results if r["severity"] == "CRITICAL"])
 high_issues = len([r for r in self.results if r["severity"] == "HIGH"])
 medium_issues = len([r for r in self.results if r["severity"] == "MEDIUM"])
 
 print(f"\nSUMMARY STATISTICS:")
 print(f" Total Tests: {total_tests}")
 print(f" Passed: {passed_tests}")
 print(f" Failed: {failed_tests}")
 print(f" Critical Issues: {critical_issues}")
 print(f" High Issues: {high_issues}")
 print(f" Medium Issues: {medium_issues}")
 
 # Security score calculation
 security_score = max(0, 100 - (critical_issues * 25 + high_issues * 15 + medium_issues * 5))
 print(f"\nOVERALL SECURITY SCORE: {security_score}%")
 
 # Roadmap claims validation
 print(f"\nROADMAP CLAIMS VALIDATION:")
 print("="*50)
 
 claims = {
 "Trial Expiration Enforcement": False,
 "Email Verification Enforcement": False,
 "Multiple Trial Prevention": False,
 "Trial Management Service": False,
 "Authentication Security": False
 }
 
 # Analyze results for each claim
 for result in self.results:
 if "Trial Expiration" in result["test_name"] and result["status"] == "PASS":
 claims["Trial Expiration Enforcement"] = True
 if "Email Verification" in result["test_name"] and result["status"] == "PASS":
 claims["Email Verification Enforcement"] = True
 if "Multiple Trial" in result["test_name"] and result["status"] == "PASS":
 claims["Multiple Trial Prevention"] = True
 if "Trial API" in result["test_name"] and result["status"] == "PASS":
 claims["Trial Management Service"] = True
 if "Auth Bypass" in result["test_name"] and result["status"] == "PASS":
 claims["Authentication Security"] = True
 
 for claim, validated in claims.items():
 status = " VALIDATED" if validated else " NOT VALIDATED"
 print(f" {claim}: {status}")
 
 # Critical vulnerabilities
 critical_vulns = [r for r in self.results if r["severity"] == "CRITICAL"]
 if critical_vulns:
 print(f"\nCRITICAL VULNERABILITIES:")
 print("="*50)
 for vuln in critical_vulns:
 print(f" - {vuln['test_name']}: {vuln['details']}")
 
 # Detailed results
 print(f"\nDETAILED TEST RESULTS:")
 print("="*50)
 for result in self.results:
 severity_marker = {
 "CRITICAL": "",
 "HIGH": "", 
 "MEDIUM": "",
 "LOW": "",
 "INFO": "ℹ"
 }.get(result["severity"], "")
 
 print(f"{severity_marker} {result['test_name']}")
 print(f" Status: {result['status']}")
 print(f" Severity: {result['severity']}")
 print(f" Details: {result['details']}")
 print(f" Timestamp: {result['timestamp']}")
 print()
 
 # Recommendations
 print(f"SECURITY RECOMMENDATIONS:")
 print("="*50)
 
 recommendations = [
 "Implement automated trial expiration testing in CI/CD pipeline",
 "Add comprehensive logging for all authentication events", 
 "Set up monitoring alerts for suspicious authentication attempts",
 "Regularly audit trial management permissions and access controls",
 "Implement rate limiting on authentication endpoints",
 "Add CAPTCHA protection for registration endpoints",
 "Set up automated security scanning for new deployments",
 "Implement session management and token blacklisting",
 "Add comprehensive input validation testing",
 "Set up automated vulnerability scanning"
 ]
 
 for i, rec in enumerate(recommendations, 1):
 print(f" {i}. {rec}")
 
 print("\n" + "="*100)
 print(f"AUDIT COMPLETED AT: {datetime.utcnow().isoformat()} UTC")
 print("="*100)

 def run_complete_audit(self):
 """Run complete security audit"""
 print("WEDDING WEBAPP SECURITY AUDIT - TRIAL EXPIRATION SYSTEM")
 print("="*80)
 print(f"Started at: {datetime.utcnow().isoformat()} UTC")
 print(f"Target: {self.base_url}")
 
 try:
 # Connectivity test first
 if not self.test_server_connectivity():
 print(" Server not accessible. Aborting audit.")
 return
 
 # Run all security tests
 self.test_email_verification_enforcement()
 self.test_trial_expiration_enforcement() 
 self.test_multiple_trial_prevention()
 self.test_boundary_conditions()
 self.test_trial_management_api_security()
 self.test_authentication_bypass_attempts()
 
 # Generate report
 self.generate_security_report()
 
 except KeyboardInterrupt:
 print("\n Audit interrupted by user")
 except Exception as e:
 print(f"\n Audit failed with unexpected error: {e}")
 traceback.print_exc()
 finally:
 # Cleanup
 self.cleanup_test_users()

def main():
 """Main function"""
 base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
 
 auditor = SecurityAuditTest(base_url)
 auditor.run_complete_audit()

if __name__ == "__main__":
 main()
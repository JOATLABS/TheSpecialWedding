#!/usr/bin/env python3
"""
Focused Security Testing - Correct Endpoints
============================================

Test the actual security implementations found in the codebase.
"""

import requests
import json
import os
from datetime import datetime
import time

BASE_URL = os.getenv("NEXT_PUBLIC_API_BASE_URL")
assert BASE_URL, "NEXT_PUBLIC_API_BASE_URL environment variable is required"

def test_email_verification_with_correct_endpoint():
 """Test email verification enforcement using correct endpoint"""
 print("\n TESTING: Email Verification Enforcement (Correct Endpoint)")
 print("="*70)
 
 test_email = f"security_test_{int(time.time())}@example.com"
 
 # Test registration endpoint
 registration_data = {
 "email": test_email,
 "password": "SecureTestPassword123!",
 "first_name": "Security",
 "last_name": "Tester",
 "company_name": "Security Audit Co"
 }
 
 try:
 # Use correct registration endpoint
 reg_response = requests.post(
 f"{BASE_URL}/public/register",
 json=registration_data,
 timeout=10
 )
 
 print(f"Registration Status: {reg_response.status_code}")
 if reg_response.status_code == 200:
 print(" Registration successful")
 print(f"Response: {reg_response.json()}")
 
 # Test login with unverified account
 login_data = {
 "email": test_email,
 "password": "SecureTestPassword123!"
 }
 
 login_response = requests.post(
 f"{BASE_URL}/admin/token",
 json=login_data,
 timeout=10
 )
 
 print(f"Login Status: {login_response.status_code}")
 if login_response.status_code == 401:
 response_data = login_response.json()
 print(f" Login correctly blocked: {response_data.get('detail', 'No detail')}")
 if "not verified" in response_data.get("detail", "").lower():
 print(" PASS: Email verification correctly enforced")
 else:
 print(" PARTIAL: Blocked but reason unclear")
 elif login_response.status_code == 200:
 print(" CRITICAL: Unverified user can login!")
 else:
 print(f"Response: {login_response.json()}")
 
 else:
 print(f"Registration failed: {reg_response.json()}")
 
 except Exception as e:
 print(f" Test error: {e}")

def test_trial_management_endpoints_security():
 """Test trial management endpoint security with correct paths"""
 print("\n TESTING: Trial Management API Security (Correct Endpoints)")
 print("="*70)
 
 endpoints = [
 "/admin/trials/check-expired",
 "/admin/trials/send-warnings", 
 "/admin/trials/run-maintenance",
 "/admin/trials/status"
 ]
 
 for endpoint in endpoints:
 try:
 # Test without authentication
 response = requests.post(f"{BASE_URL}{endpoint}", timeout=5)
 print(f"Endpoint: {endpoint}")
 print(f"Status: {response.status_code}")
 
 if response.status_code == 401:
 print(" PASS: Correctly requires authentication")
 elif response.status_code == 403:
 print(" PASS: Correctly requires authorization")
 elif response.status_code == 422:
 print(" PASS: Input validation working")
 else:
 print(f" POTENTIAL ISSUE: Status {response.status_code}")
 print(f"Response: {response.text[:200]}")
 
 except Exception as e:
 print(f" Error testing {endpoint}: {e}")
 print()

def test_multiple_trial_prevention_real():
 """Test multiple trial prevention with real registration"""
 print("\n TESTING: Multiple Trial Prevention (Real Test)")
 print("="*70)
 
 test_email = f"multiple_trial_test_{int(time.time())}@example.com"
 
 registration_data = {
 "email": test_email,
 "password": "SecureTestPassword123!",
 "first_name": "Multiple",
 "last_name": "Trial",
 "company_name": "Test Co"
 }
 
 try:
 # First registration
 first_reg = requests.post(
 f"{BASE_URL}/public/register",
 json=registration_data,
 timeout=10
 )
 
 print(f"First registration: {first_reg.status_code}")
 if first_reg.status_code == 200:
 print(" First registration successful")
 
 # Attempt second registration
 second_reg = requests.post(
 f"{BASE_URL}/public/register",
 json=registration_data,
 timeout=10
 )
 
 print(f"Second registration: {second_reg.status_code}")
 if second_reg.status_code == 400:
 response_data = second_reg.json()
 detail = response_data.get("detail", "").lower()
 print(f"Response: {response_data.get('detail', '')}")
 
 if "already exists" in detail:
 print(" PASS: Multiple trial correctly prevented")
 elif "trial" in detail:
 print(" PASS: Trial limitation enforced") 
 else:
 print(" PARTIAL: Blocked but unclear reason")
 else:
 print(" VULNERABILITY: Second registration allowed!")
 print(f"Response: {second_reg.json()}")
 else:
 print(f"First registration failed: {first_reg.json()}")
 
 except Exception as e:
 print(f" Test error: {e}")

def test_trial_settings_access():
 """Test trial settings endpoint accessibility"""
 print("\n TESTING: Trial Settings Access")
 print("="*70)
 
 try:
 response = requests.get(f"{BASE_URL}/admin/trial-settings", timeout=5)
 print(f"Status: {response.status_code}")
 
 if response.status_code == 200:
 data = response.json()
 print(" Trial settings accessible")
 print(f"Settings: {json.dumps(data, indent=2)}")
 
 # Check for security-relevant settings
 if "allow_multiple_trials" in str(data):
 print(" Multiple trial control setting found")
 if "auto_expire_trials" in str(data):
 print(" Auto expiration setting found")
 
 else:
 print(f" Could not access trial settings: {response.text}")
 
 except Exception as e:
 print(f" Error: {e}")

def test_authentication_token_validation():
 """Test JWT token validation with various malformed tokens"""
 print("\n TESTING: Authentication Token Validation")
 print("="*70)
 
 # Test protected endpoint
 test_endpoint = f"{BASE_URL}/admin/weddings"
 
 malformed_tokens = [
 "Bearer invalid.jwt.token",
 "Bearer ",
 "invalid-format",
 "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
 ]
 
 for token in malformed_tokens:
 try:
 headers = {"Authorization": token}
 response = requests.get(test_endpoint, headers=headers, timeout=5)
 
 print(f"Token: {token}")
 print(f"Status: {response.status_code}")
 
 if response.status_code == 401:
 print(" PASS: Malformed token correctly rejected")
 elif response.status_code == 422:
 print(" PASS: Token validation working")
 else:
 print(f" POTENTIAL ISSUE: Status {response.status_code}")
 
 except Exception as e:
 print(f" Error: {e}")
 print()

def main():
 """Run focused security tests"""
 print(" FOCUSED SECURITY TESTING - WEDDING WEBAPP")
 print("="*80)
 print(f"Target: {BASE_URL}")
 print(f"Started: {datetime.now().isoformat()}")
 
 # Run focused tests
 test_email_verification_with_correct_endpoint()
 test_trial_management_endpoints_security() 
 test_multiple_trial_prevention_real()
 test_trial_settings_access()
 test_authentication_token_validation()
 
 print("\n" + "="*80)
 print(" FOCUSED TESTING COMPLETED")
 print("="*80)

if __name__ == "__main__":
 main()
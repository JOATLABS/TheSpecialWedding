#!/usr/bin/env python3
"""
Trial Expiration Security Test
==============================

Test expired trial enforcement and HTTP 402 responses.
"""

import requests
import json
from datetime import datetime, timedelta
import jwt
import os
from pymongo import MongoClient
import time

BASE_URL = os.getenv("NEXT_PUBLIC_API_BASE_URL")
assert BASE_URL, "NEXT_PUBLIC_API_BASE_URL environment variable is required"

def get_test_database():
 """Get database connection for testing"""
 try:
 client = MongoClient("mongodb://localhost:27017")
 db = client["wedding_webapp"]
 return db
 except Exception as e:
 print(f"Could not connect to database: {e}")
 return None

def create_expired_trial_user():
 """Create a user with an expired trial for testing"""
 db = get_test_database()
 if db is None:
 return None
 
 test_email = f"expired_trial_{int(time.time())}@example.com"
 expired_date = datetime.utcnow() - timedelta(days=1) # Yesterday
 
 # Create user with expired trial
 user_data = {
 "email": test_email,
 "password_hash": "$2b$12$example.hash.here", # Mock hash
 "role": "wedding_planner",
 "first_name": "Expired",
 "last_name": "Trial",
 "company_name": "Test Co",
 "subscription_status": "trial",
 "trial_end_date": expired_date,
 "is_active": True, # Initially active
 "email_verified": True, # Verified to test trial logic
 "created_at": datetime.utcnow() - timedelta(days=31)
 }
 
 try:
 result = db.users.insert_one(user_data)
 print(f" Created expired trial user: {test_email}")
 return test_email, str(result.inserted_id)
 except Exception as e:
 print(f" Failed to create expired trial user: {e}")
 return None, None

def create_valid_jwt_token(email: str, role: str = "wedding_planner"):
 """Create a valid JWT token for testing"""
 # Get secret key from environment or use default for testing
 secret_key = os.getenv("SECRET_KEY", "test-secret-key")
 
 payload = {
 "sub": email,
 "role": role,
 "exp": datetime.utcnow() + timedelta(hours=1)
 }
 
 return jwt.encode(payload, secret_key, algorithm="HS256")

def test_expired_trial_enforcement():
 """Test that expired trials return HTTP 402"""
 print("\n TESTING: Expired Trial Enforcement (HTTP 402)")
 print("="*70)
 
 # Create expired trial user
 expired_email, user_id = create_expired_trial_user()
 if not expired_email:
 print(" Could not create test user")
 return
 
 try:
 # Create a valid JWT token for the expired user
 token = create_valid_jwt_token(expired_email)
 headers = {"Authorization": f"Bearer {token}"}
 
 # Test accessing protected endpoint
 response = requests.get(
 f"{BASE_URL}/admin/weddings",
 headers=headers,
 timeout=10
 )
 
 print(f"Request to /admin/weddings with expired trial user:")
 print(f"Status Code: {response.status_code}")
 
 if response.status_code == 402:
 response_data = response.json()
 print(" SUCCESS: HTTP 402 correctly returned for expired trial")
 print(f"Response: {response_data.get('detail', 'No detail')}")
 
 # Check for proper error message
 detail = response_data.get('detail', '').lower()
 if 'trial has expired' in detail or 'expired' in detail:
 print(" SUCCESS: Proper error message for expired trial")
 else:
 print(" WARNING: Error message unclear")
 
 elif response.status_code == 401:
 response_data = response.json()
 detail = response_data.get('detail', '').lower()
 print(f"Response: {response_data.get('detail', 'No detail')}")
 
 if 'expired' in detail or 'trial' in detail:
 print(" PASS: Trial expiration detected (401 instead of 402)")
 elif 'deactivated' in detail:
 print(" PASS: Account properly deactivated on expiration")
 else:
 print(" PARTIAL: Authentication failed but reason unclear")
 
 else:
 print(f" VULNERABILITY: Expired trial user has access! Status: {response.status_code}")
 if response.status_code == 200:
 print(" CRITICAL: Expired trial user can access protected resources!")
 
 # Clean up test user
 if user_id:
 db = get_test_database()
 if db:
 db.users.delete_one({"_id": user_id})
 print(f" Cleaned up test user: {expired_email}")
 
 except Exception as e:
 print(f" Test error: {e}")

def test_trial_auto_expiration():
 """Test that expired trials are automatically deactivated"""
 print("\n TESTING: Trial Auto-Expiration Logic")
 print("="*70)
 
 db = get_test_database()
 if db is None:
 print(" Cannot access database")
 return
 
 try:
 # Look for users with expired trials
 expired_trials = list(db.users.find({
 "subscription_status": "trial",
 "trial_end_date": {"$lt": datetime.utcnow()}
 }))
 
 print(f"Found {len(expired_trials)} users with expired trials")
 
 if expired_trials:
 for user in expired_trials:
 print(f"User: {user['email']}")
 print(f"Trial End: {user.get('trial_end_date')}")
 print(f"Active: {user.get('is_active', 'Unknown')}")
 print(f"Status: {user.get('subscription_status')}")
 
 if user.get('is_active') and user.get('subscription_status') == 'trial':
 print(" WARNING: Expired trial user still active")
 else:
 print(" PASS: Expired trial properly handled")
 print()
 else:
 print(" No expired trials found (good)")
 
 # Check for properly expired users
 properly_expired = list(db.users.find({
 "subscription_status": "expired",
 "is_active": False
 }))
 
 print(f"Found {len(properly_expired)} properly expired trial users")
 if properly_expired:
 print(" PASS: Users are being properly expired")
 
 except Exception as e:
 print(f" Database check error: {e}")

def test_trial_warning_system():
 """Test trial warning email system"""
 print("\n TESTING: Trial Warning System")
 print("="*70)
 
 db = get_test_database()
 if db is None:
 print(" Cannot access database")
 return
 
 try:
 # Look for trials expiring soon
 warning_date = datetime.utcnow() + timedelta(days=7)
 expiring_soon = list(db.users.find({
 "subscription_status": "trial",
 "trial_end_date": {"$lte": warning_date, "$gt": datetime.utcnow()},
 "is_active": True,
 "email_verified": True
 }))
 
 print(f"Found {len(expiring_soon)} trials expiring within 7 days")
 
 for user in expiring_soon:
 days_left = (user['trial_end_date'] - datetime.utcnow()).days
 print(f"User: {user['email']} - {days_left} days left")
 print(f"Warning sent: {user.get('trial_warning_sent', False)}")
 
 # Check warning tracking
 warnings_sent = list(db.users.find({
 "trial_warning_sent": True
 }))
 
 print(f"Found {len(warnings_sent)} users who received trial warnings")
 if warnings_sent:
 print(" PASS: Trial warning system is tracking sent warnings")
 
 except Exception as e:
 print(f" Warning system check error: {e}")

def test_trial_settings_validation():
 """Test trial settings and their enforcement"""
 print("\n TESTING: Trial Settings Validation")
 print("="*70)
 
 try:
 # Get trial settings
 response = requests.get(f"{BASE_URL}/admin/trial-settings", timeout=5)
 
 if response.status_code == 200:
 settings = response.json()
 print(" Trial settings accessible")
 print(f"Settings: {json.dumps(settings, indent=2)}")
 
 # Validate critical settings
 critical_settings = [
 "default_trial_days",
 "trial_warning_days", 
 "auto_expire_trials",
 "allow_multiple_trials"
 ]
 
 for setting in critical_settings:
 if setting in settings:
 print(f" {setting}: {settings[setting]}")
 else:
 print(f" Missing critical setting: {setting}")
 
 # Check security implications
 if settings.get("allow_multiple_trials") is False:
 print(" SECURITY: Multiple trials properly disabled")
 else:
 print(" WARNING: Multiple trials may be allowed")
 
 if settings.get("auto_expire_trials") is True:
 print(" SECURITY: Auto-expiration enabled")
 else:
 print(" WARNING: Auto-expiration disabled")
 
 else:
 print(f" Could not get trial settings: {response.status_code}")
 
 except Exception as e:
 print(f" Settings test error: {e}")

def main():
 """Run trial expiration security tests"""
 print(" TRIAL EXPIRATION SECURITY TESTING")
 print("="*80)
 print(f"Target: {BASE_URL}")
 print(f"Started: {datetime.now().isoformat()}")
 
 # Run tests
 test_expired_trial_enforcement()
 test_trial_auto_expiration()
 test_trial_warning_system()
 test_trial_settings_validation()
 
 print("\n" + "="*80)
 print(" TRIAL EXPIRATION TESTING COMPLETED")
 print("="*80)

if __name__ == "__main__":
 main()
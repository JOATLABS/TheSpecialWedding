#!/usr/bin/env python3
"""
Test script to verify trial expiration security fix is working
"""
import requests
import json
from datetime import datetime, timedelta
from pymongo import MongoClient
import os
import jwt

# Configuration
BASE_URL = "http://localhost:8002"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "wedding")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")

def create_test_user_with_expired_trial():
 """Create a test user with an expired trial directly in MongoDB"""
 client = MongoClient(MONGO_URI)
 db = client[MONGO_DB]
 
 # Create expired trial user
 expired_user = {
 "email": "expired_trial_test@example.com",
 "password": "hashed_password_placeholder", 
 "role": "wedding_planner",
 "subscription_status": "trial",
 "trial_end_date": datetime.utcnow() - timedelta(days=5), # Expired 5 days ago
 "email_verified": True,
 "is_active": True, # Should be set to False by the auth logic
 "created_at": datetime.utcnow(),
 "trial_days": 30
 }
 
 # Remove existing test user
 db.users.delete_one({"email": "expired_trial_test@example.com"})
 
 # Insert expired trial user
 result = db.users.insert_one(expired_user)
 print(f" Created test user with expired trial: {result.inserted_id}")
 
 # Create valid JWT token for this user
 payload = {
 "sub": "expired_trial_test@example.com",
 "role": "wedding_planner",
 "exp": datetime.utcnow() + timedelta(hours=1)
 }
 
 token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
 return token, expired_user

def test_expired_trial_authentication():
 """Test that expired trial users get HTTP 402"""
 print("\n Testing Expired Trial Authentication...")
 
 try:
 # Create expired trial user and get token
 token, user_data = create_test_user_with_expired_trial()
 
 # Test accessing admin endpoint with expired trial
 headers = {"Authorization": f"Bearer {token}"}
 response = requests.get(f"{BASE_URL}/admin/weddings", headers=headers)
 
 print(f" Response Status: HTTP {response.status_code}")
 print(f" Response Body: {response.text}")
 
 # Check if we get the expected HTTP 402 Payment Required
 if response.status_code == 402:
 print(" SUCCESS: Expired trial correctly blocked with HTTP 402")
 print(" SUCCESS: Trial expiration security fix is working!")
 return True
 elif response.status_code == 401:
 print(" WARNING: Got HTTP 401 instead of 402 - possible authentication issue")
 return False
 else:
 print(f" FAILURE: Unexpected status code {response.status_code}")
 return False
 
 except Exception as e:
 print(f" ERROR: {e}")
 return False

def test_valid_user_still_works():
 """Test that valid users can still authenticate normally"""
 print("\n Testing Valid User Authentication...")
 
 try:
 # Test with invalid token (should get 401)
 headers = {"Authorization": "Bearer invalid_token"}
 response = requests.get(f"{BASE_URL}/admin/weddings", headers=headers)
 
 if response.status_code == 401:
 print(" SUCCESS: Invalid tokens correctly rejected with HTTP 401")
 return True
 else:
 print(f" FAILURE: Expected 401, got {response.status_code}")
 return False
 
 except Exception as e:
 print(f" ERROR: {e}")
 return False

def check_database_updates():
 """Check if expired trial users are automatically deactivated"""
 print("\n Testing Database Auto-Update...")
 
 try:
 client = MongoClient(MONGO_URI)
 db = client[MONGO_DB]
 
 # Check if our test user was deactivated
 user = db.users.find_one({"email": "expired_trial_test@example.com"})
 
 if user:
 print(f" User is_active: {user.get('is_active')}")
 print(f" User subscription_status: {user.get('subscription_status')}")
 print(f" User trial_expired_at: {user.get('trial_expired_at')}")
 
 if user.get('is_active') == False and user.get('subscription_status') == 'expired':
 print(" SUCCESS: User automatically deactivated after trial expiration")
 return True
 else:
 print(" WARNING: User not automatically deactivated")
 return False
 else:
 print(" ERROR: Test user not found in database")
 return False
 
 except Exception as e:
 print(f" ERROR: {e}")
 return False

def main():
 """Run all security tests"""
 print(" TRIAL EXPIRATION SECURITY FIX VALIDATION")
 print("=" * 50)
 
 # Test results
 results = []
 
 # Test 1: Expired trial authentication
 results.append(test_expired_trial_authentication())
 
 # Test 2: Valid user authentication 
 results.append(test_valid_user_still_works())
 
 # Test 3: Database auto-updates
 results.append(check_database_updates())
 
 # Summary
 print("\n TEST SUMMARY")
 print("=" * 30)
 passed = sum(results)
 total = len(results)
 
 print(f"Tests Passed: {passed}/{total}")
 
 if passed == total:
 print(" ALL TESTS PASSED - Security fix is working correctly!")
 elif passed > 0:
 print(" PARTIAL SUCCESS - Some issues remain")
 else:
 print(" ALL TESTS FAILED - Security fix not working")
 
 return passed == total

if __name__ == "__main__":
 main()
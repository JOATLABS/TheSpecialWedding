#!/usr/bin/env python3
"""
Advanced test for trial expiration security fix
"""
import requests
import json
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
import os
import jwt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "http://localhost:8002"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "wedding")
SECRET_KEY = os.getenv("SECRET_KEY")

def create_expired_trial_scenario():
 """Create a realistic expired trial scenario"""
 print(" Setting up expired trial test scenario...")
 
 # Connect to MongoDB
 client = MongoClient(MONGO_URI)
 db = client[MONGO_DB]
 
 # Create user with expired trial (5 days ago)
 expired_user = {
 "email": "test_expired@example.com",
 "password": "$2b$12$dummy_hash_for_testing", # Dummy bcrypt hash
 "role": "wedding_planner",
 "subscription_status": "trial",
 "trial_end_date": datetime.now(timezone.utc) - timedelta(days=5),
 "email_verified": True,
 "is_active": True,
 "created_at": datetime.now(timezone.utc),
 "trial_days": 30
 }
 
 # Remove any existing test user
 db.users.delete_one({"email": "test_expired@example.com"})
 
 # Insert the expired user
 result = db.users.insert_one(expired_user)
 print(f" Created expired trial user: {result.inserted_id}")
 
 # Create a VALID JWT token for this user (but user has expired trial)
 payload = {
 "sub": "test_expired@example.com",
 "role": "wedding_planner", 
 "exp": datetime.now(timezone.utc) + timedelta(hours=24) # Valid for 24 hours
 }
 
 # Use the same secret key and algorithm as the app
 token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
 print(f" Generated valid JWT token for expired user")
 
 return token, expired_user

def test_trial_expiration_enforcement():
 """Test the trial expiration enforcement"""
 print("\\n Testing Trial Expiration Enforcement...")
 
 # Create the test scenario
 token, user_data = create_expired_trial_scenario()
 
 # Test authentication with the expired trial user
 headers = {"Authorization": f"Bearer {token}"}
 
 try:
 response = requests.get(f"{BASE_URL}/admin/weddings", headers=headers)
 
 print(f" HTTP Status: {response.status_code}")
 print(f" Response: {response.text}")
 
 # Check for HTTP 402 Payment Required
 if response.status_code == 402:
 print(" SUCCESS: HTTP 402 Payment Required returned")
 print(" Trial expiration security is working!")
 
 # Check if response mentions trial expiration
 if "trial has expired" in response.text.lower():
 print(" SUCCESS: Correct trial expiration message")
 return True
 else:
 print(" WARNING: HTTP 402 but wrong message")
 return False
 
 elif response.status_code == 401:
 print(" FAILURE: Got HTTP 401 instead of 402")
 print(" Trial expiration logic may not be executing")
 return False
 
 else:
 print(f" FAILURE: Unexpected status {response.status_code}")
 return False
 
 except Exception as e:
 print(f" ERROR: {e}")
 return False

def check_user_auto_deactivation():
 """Check if the user was automatically deactivated"""
 print("\\n Checking User Auto-Deactivation...")
 
 client = MongoClient(MONGO_URI)
 db = client[MONGO_DB]
 
 # Check the user status after authentication attempt
 user = db.users.find_one({"email": "test_expired@example.com"})
 
 if user:
 print(f" is_active: {user.get('is_active')}")
 print(f" subscription_status: {user.get('subscription_status')}")
 print(f" trial_expired_at: {user.get('trial_expired_at')}")
 
 # Check if auto-deactivation occurred
 if (user.get('is_active') == False and 
 user.get('subscription_status') == 'expired' and
 user.get('trial_expired_at') is not None):
 print(" SUCCESS: User auto-deactivated correctly")
 return True
 else:
 print(" FAILURE: User not auto-deactivated")
 return False
 else:
 print(" ERROR: Test user not found")
 return False

def test_valid_token_format():
 """Test that our JWT tokens are being created correctly"""
 print("\\n Testing JWT Token Format...")
 
 try:
 # Create a token
 token, _ = create_expired_trial_scenario()
 
 # Try to decode it manually
 payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
 print(f" Token decoded successfully: {payload}")
 
 # Check required fields
 if "sub" in payload and "role" in payload and "exp" in payload:
 print(" Token has all required fields")
 return True
 else:
 print(" Token missing required fields")
 return False
 
 except Exception as e:
 print(f" Token decode error: {e}")
 return False

def main():
 """Run the advanced trial expiration test"""
 print(" ADVANCED TRIAL EXPIRATION SECURITY TEST")
 print("=" * 50)
 
 if not SECRET_KEY:
 print(" ERROR: SECRET_KEY environment variable not found")
 return False
 
 results = []
 
 # Test JWT token format first
 results.append(test_valid_token_format())
 
 # Test trial expiration enforcement
 results.append(test_trial_expiration_enforcement())
 
 # Check auto-deactivation
 results.append(check_user_auto_deactivation())
 
 # Summary
 print("\\n TEST RESULTS")
 print("=" * 30)
 passed = sum(results)
 total = len(results)
 
 print(f"Tests Passed: {passed}/{total}")
 
 if passed == total:
 print(" ALL TESTS PASSED - Security fix verified!")
 print(" Trial expiration enforcement is working correctly")
 else:
 print(" SOME TESTS FAILED - Security fix needs more work")
 
 return passed == total

if __name__ == "__main__":
 main()
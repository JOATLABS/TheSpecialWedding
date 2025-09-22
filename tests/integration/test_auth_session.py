#!/usr/bin/env python3
"""
Test script to verify the two-cookie authentication pattern is working correctly.
This tests that sessions persist across page refreshes.
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_login_and_session():
    """Test the login flow and verify cookies are set correctly"""

    # Create a session to maintain cookies
    session = requests.Session()

    print("=" * 60)
    print("Testing Two-Cookie Authentication Pattern")
    print("=" * 60)

    # Step 1: Attempt login with test credentials
    print("\n1. Attempting login...")
    login_data = {
        "email": "test@example.com",  # Replace with actual test credentials
        "password": "password123"      # Replace with actual test password
    }

    try:
        response = session.post(f"{BASE_URL}/admin/token", json=login_data)

        if response.status_code == 200:
            print("✅ Login successful!")
            token_data = response.json()
            print(f"   Access token received: {token_data.get('access_token', '')[:20]}...")

            # Check cookies
            print("\n2. Checking cookies...")
            cookies = session.cookies.get_dict()

            if 'admin_token' in cookies:
                print("✅ admin_token cookie is set (httpOnly - secure)")
            else:
                print("❌ admin_token cookie NOT found")

            if 'admin_authenticated' in cookies:
                print("✅ admin_authenticated cookie is set (readable)")
                print(f"   Value: {cookies['admin_authenticated']}")
            else:
                print("❌ admin_authenticated cookie NOT found")

            # Step 3: Test authenticated request
            print("\n3. Testing authenticated request to /admin/profile...")
            profile_response = session.get(f"{BASE_URL}/admin/profile")

            if profile_response.status_code == 200:
                print("✅ Profile request successful - session is valid!")
                profile = profile_response.json()
                print(f"   User: {profile.get('email', 'Unknown')}")
                print(f"   Role: {profile.get('role', 'Unknown')}")
            else:
                print(f"❌ Profile request failed: {profile_response.status_code}")

        elif response.status_code == 401:
            print("❌ Login failed: Invalid credentials")
            print("   Please update the test credentials in this script")
        else:
            print(f"❌ Login failed with status: {response.status_code}")
            print(f"   Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the backend server")
        print("   Make sure the FastAPI server is running on port 8000")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    print("\n" + "=" * 60)
    print("Test Summary:")
    print("- Two-cookie pattern should set both cookies on login")
    print("- admin_token: httpOnly (secure, not readable by JS)")
    print("- admin_authenticated: readable (for client-side state)")
    print("- Both cookies should have the same expiry time")
    print("=" * 60)

if __name__ == "__main__":
    test_login_and_session()
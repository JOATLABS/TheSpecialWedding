#!/usr/bin/env python3
"""Test authentication system"""

import requests
import sys
import json

def test_auth(base_url="http://localhost:8000"):
    """Test the authentication flow"""
    
    # Test login
    print("Testing login...")
    login_data = {
        "email": "test-email",
        "password": "change-me-in-production"  # Use your actual test credentials
    }
    
    response = requests.post(f"{base_url}/admin/token", json=login_data)
    
    if response.status_code != 200:
        print(f"Login failed: {response.status_code} - {response.text}")
        return
    
    token_data = response.json()
    access_token = token_data["access_token"]
    print(f"Login successful! Token: {access_token[:20]}...")
    
    # Test authenticated endpoint
    print("\nTesting authenticated endpoint...")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(f"{base_url}/admin/rsvps", headers=headers)
    
    if response.status_code == 200:
        print("Successfully accessed protected endpoint!")
        print(f"Response: {json.dumps(response.json(), indent=2)[:100]}...")
    else:
        print(f"Failed to access protected endpoint: {response.status_code} - {response.text}")
    
    # Test without token
    print("\nTesting without token...")
    response = requests.get(f"{base_url}/admin/rsvps")
    
    if response.status_code == 403 or response.status_code == 401:
        print("Correctly rejected unauthorized request!")
    else:
        print(f"Unexpected response: {response.status_code}")

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    test_auth(base_url)
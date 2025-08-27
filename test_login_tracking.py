#!/usr/bin/env python3
"""
Test script to verify login tracking functionality
"""
import sys
import requests
import json
from datetime import datetime

# Test login tracking
def test_login_tracking():
    base_url = "http://localhost:8000"
    
    print("=== Testing Login Tracking ===")
    
    # Test login with ROOT_ADMIN
    print("\n1. Testing ROOT_ADMIN login...")
    login_data = {
        "email": "thedeveloper@thespecialwedding.com",
        "password": "your_root_admin_password_here"  # You'll need to provide the actual password
    }
    
    try:
        # Attempt login
        response = requests.post(f"{base_url}/admin/token", json=login_data)
        
        if response.status_code == 200:
            print("✅ Login successful")
            token_data = response.json()
            token = token_data.get("access_token")
            
            # Check if last_login was updated by fetching wedding planners
            headers = {"Authorization": f"Bearer {token}"}
            planners_response = requests.get(f"{base_url}/saas/wedding-planners", headers=headers)
            
            if planners_response.status_code == 200:
                planners = planners_response.json()
                print(f"\n2. Found {len(planners)} planners:")
                
                for planner in planners:
                    last_login = planner.get("last_login")
                    print(f"   - {planner.get('email')}: Last login = {last_login or 'Never'}")
            else:
                print(f"❌ Failed to fetch planners: {planners_response.status_code}")
                print(f"Response: {planners_response.text}")
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"Response: {response.text}")
            print("\nNote: You need to provide the correct ROOT_ADMIN password in this script.")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure the FastAPI server is running on localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_login_tracking()
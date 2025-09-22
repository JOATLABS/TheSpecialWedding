#!/usr/bin/env python3
"""
Test script to verify all bulk endpoints are working correctly
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_BASE = "http://localhost:8000"
TEST_EMAIL = os.getenv("TEST_PLANNER_EMAIL", "test.verification@example.com")
TEST_PASSWORD = os.getenv("TEST_PLANNER_PASSWORD", "TestPass123!")


def get_auth_token():
    """Authenticate and get JWT token"""
    response = requests.post(
        f"{API_BASE}/admin/token",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}  # JSON body
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"❌ Authentication failed: {response.status_code}")
        return None


def test_bulk_endpoints(token):
    """Test all bulk endpoints"""
    print("\n" + "=" * 60)
    print("TESTING BULK ENDPOINTS")
    print("=" * 60)

    # Get weddings
    print("\n1️⃣ Fetching weddings...")
    response = requests.get(
        f"{API_BASE}/admin/planner/weddings",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code != 200:
        print("❌ Failed to fetch weddings")
        return

    weddings = response.json()
    if not weddings:
        print("❌ No weddings found")
        return

    wedding = weddings[0]
    wedding_id = wedding.get("id") or wedding.get("_id")
    print(f"✅ Using wedding ID: {wedding_id}")

    # Test Plus-Ones Bulk Endpoint
    print("\n2️⃣ Testing Plus-Ones Bulk Endpoint...")
    response = requests.get(
        f"{API_BASE}/plus_one/plus-ones/bulk/{wedding_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Plus-Ones Bulk Endpoint Working!")
        print(f"   - Wedding ID: {data.get('wedding_id')}")
        print(f"   - Total Plus-Ones: {data.get('total_plus_ones', 0)}")
        print(f"   - Guests with Plus-Ones: {data.get('guests_with_plus_ones', 0)}")
    else:
        print(f"❌ Plus-Ones Bulk Endpoint Failed: {response.status_code}")
        print(f"   Response: {response.text[:200]}")

    # Test RSVPs Endpoint (already optimized)
    print("\n3️⃣ Testing Optimized RSVPs Endpoint...")
    response = requests.get(
        f"{API_BASE}/admin/rsvps?wedding_id={wedding_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ RSVPs Endpoint Working!")
        print(f"   - Total RSVPs: {len(data) if isinstance(data, list) else 0}")
    else:
        print(f"❌ RSVPs Endpoint Failed: {response.status_code}")

    # Test Form Responses Bulk Endpoint
    print("\n4️⃣ Testing Form Responses Bulk Endpoint...")
    response = requests.get(
        f"{API_BASE}/forms/bulk/responses/{wedding_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Form Responses Bulk Endpoint Working!")
        print(f"   - Wedding ID: {data.get('wedding_id')}")
        print(f"   - Total Responses: {data.get('total_responses', 0)}")
        print(f"   - Form Count: {data.get('form_count', 0)}")
    else:
        print(f"❌ Form Responses Bulk Endpoint Failed: {response.status_code}")
        print(f"   Response: {response.text[:200]}")

    print("\n" + "=" * 60)
    print("✨ Bulk Endpoint Testing Complete!")
    print("=" * 60)


def main():
    print("🚀 Bulk Endpoint Verification Script")

    # Get auth token
    print("\n🔐 Authenticating...")
    token = get_auth_token()
    if not token:
        print("❌ Authentication failed. Please check credentials.")
        return

    print("✅ Authentication successful")

    # Test endpoints
    test_bulk_endpoints(token)


if __name__ == "__main__":
    main()
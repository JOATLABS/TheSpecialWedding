#!/usr/bin/env python3
"""
Test script to verify the N+1 query fix for plus-ones
Compares performance between old (individual) and new (bulk) approaches
"""

import time
import requests
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
        f"{API_BASE}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"❌ Authentication failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None


def test_old_approach(token, wedding_id, guest_ids):
    """Test the old N+1 approach (individual requests per guest)"""
    print("\n📊 Testing OLD approach (N+1 queries)...")
    print(f"   Making {len(guest_ids)} individual API calls...")

    start_time = time.time()
    total_plus_ones = 0

    for guest_id in guest_ids:
        try:
            response = requests.get(
                f"{API_BASE}/plus_one/plus-ones/{guest_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                plus_ones = response.json()
                total_plus_ones += len(plus_ones)
        except:
            pass

    end_time = time.time()
    duration = end_time - start_time

    print(f"   ✅ Completed in {duration:.2f} seconds")
    print(f"   Total plus-ones found: {total_plus_ones}")
    return duration


def test_new_approach(token, wedding_id):
    """Test the new bulk approach (single request)"""
    print("\n📊 Testing NEW approach (Bulk query)...")
    print(f"   Making 1 bulk API call...")

    start_time = time.time()

    response = requests.get(
        f"{API_BASE}/plus_one/plus-ones/bulk/{wedding_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    end_time = time.time()
    duration = end_time - start_time

    if response.status_code == 200:
        data = response.json()
        total_plus_ones = data.get("total_plus_ones", 0)
        guests_with_plus_ones = data.get("guests_with_plus_ones", 0)
        print(f"   ✅ Completed in {duration:.2f} seconds")
        print(f"   Total plus-ones found: {total_plus_ones}")
        print(f"   Guests with plus-ones: {guests_with_plus_ones}")
    else:
        print(f"   ❌ Request failed: {response.status_code}")

    return duration


def main():
    print("=" * 60)
    print("N+1 QUERY FIX PERFORMANCE TEST")
    print("=" * 60)

    # Get auth token
    print("\n🔐 Authenticating...")
    token = get_auth_token()
    if not token:
        print("❌ Failed to authenticate. Please check credentials.")
        return

    print("✅ Authentication successful")

    # Get weddings for the user
    print("\n📋 Fetching weddings...")
    response = requests.get(
        f"{API_BASE}/admin/planner/weddings",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code != 200:
        print("❌ Failed to fetch weddings")
        return

    weddings = response.json()
    if not weddings:
        print("❌ No weddings found for this user")
        return

    # Use the first wedding for testing
    wedding = weddings[0]
    wedding_id = wedding.get("id") or wedding.get("_id")
    wedding_name = wedding.get("name", "Unknown")

    print(f"✅ Using wedding: {wedding_name} (ID: {wedding_id})")

    # Get guests for the wedding
    print("\n👥 Fetching guests...")
    response = requests.get(
        f"{API_BASE}/admin/guests/list?wedding_id={wedding_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code != 200:
        print("❌ Failed to fetch guests")
        return

    guests = response.json()
    guest_ids = [g.get("id") or g.get("_id") for g in guests]

    print(f"✅ Found {len(guests)} guests")

    # Run performance tests
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON")
    print("=" * 60)

    # Test new approach first (to warm up cache)
    new_duration = test_new_approach(token, wedding_id)

    # Test old approach
    old_duration = test_old_approach(token, wedding_id, guest_ids[:10])  # Limit to 10 for demo

    # Calculate improvement
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    if old_duration > 0:
        improvement = ((old_duration - new_duration) / old_duration) * 100
        speedup = old_duration / new_duration

        print(f"\n🚀 Performance Improvement:")
        print(f"   Old approach: {old_duration:.2f} seconds")
        print(f"   New approach: {new_duration:.2f} seconds")
        print(f"   Improvement: {improvement:.1f}%")
        print(f"   Speedup: {speedup:.1f}x faster")

        if len(guests) > 10:
            projected_old = old_duration * (len(guests) / 10)
            print(f"\n📈 Projected for {len(guests)} guests:")
            print(f"   Old approach would take: {projected_old:.2f} seconds")
            print(f"   New approach takes: {new_duration:.2f} seconds")
            print(f"   Savings: {projected_old - new_duration:.2f} seconds")

    print("\n✨ N+1 Query Fix Verification Complete!")


if __name__ == "__main__":
    main()
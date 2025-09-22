#!/usr/bin/env python3
"""
Comprehensive Budget API Test Suite
Tests all budget endpoints with proper authentication and data validation
"""

import asyncio
import requests
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Test configuration
API_BASE_URL = os.getenv("NEXT_PUBLIC_API_BASE_URL")
TEST_USER_EMAIL = os.getenv("TEST_PLANNER_EMAIL")
TEST_USER_PASSWORD = os.getenv("TEST_PLANNER_PASSWORD")

# Ensure required environment variables are set
assert API_BASE_URL, "NEXT_PUBLIC_API_BASE_URL environment variable is required"
assert TEST_USER_EMAIL, "TEST_PLANNER_EMAIL environment variable is required"
assert TEST_USER_PASSWORD, "TEST_PLANNER_PASSWORD environment variable is required"

class BudgetAPITester:
    def __init__(self):
        self.api_url = API_BASE_URL
        self.token = None
        self.wedding_id = None
        self.created_category_id = None
        self.created_quote_id = None

    def authenticate(self):
        """Authenticate and get JWT token"""
        print("🔐 Authenticating test user...")

        auth_url = f"{self.api_url}/admin/token"
        auth_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }

        response = requests.post(auth_url, json=auth_data)
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            print(f"✅ Authentication successful")
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code} - {response.text}")
            return False

    def get_headers(self):
        """Get authentication headers"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def setup_test_wedding(self):
        """Use existing test wedding for budget testing"""
        print("🏰 Setting up test wedding...")

        # Use the known existing wedding ID
        self.wedding_id = "68ae66c5c30359265c544ca7"
        print(f"✅ Using existing wedding: {self.wedding_id}")
        return True

    def test_get_budget_summary(self):
        """Test GET /weddings/{wedding_id}/budget"""
        print("📊 Testing budget summary retrieval...")

        url = f"{self.api_url}/admin/weddings/{self.wedding_id}/budget"
        response = requests.get(url, headers=self.get_headers())

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Budget summary retrieved successfully")
            print(f"   📈 Total budget: ${data.get('summary', {}).get('total_budget', 0)}")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False

    def test_create_budget_category(self):
        """Test POST /weddings/{wedding_id}/budget/category"""
        print("📝 Testing budget category creation...")

        url = f"{self.api_url}/admin/weddings/{self.wedding_id}/budget/category"
        category_data = {
            "name": "Test Venue & Catering",
            "description": "Test budget category for venue and catering costs",
            "budgeted_amount": 25000.00,
            "priority": 1,
            "percentage_of_total": 50.0
        }

        response = requests.post(url, headers=self.get_headers(), json=category_data)

        print(f"   Status: {response.status_code}")
        if response.status_code in [200, 201]:
            data = response.json()
            category_data = data.get("category", {})
            # Extract ID and ensure it's a string
            category_id = category_data.get("id") or category_data.get("_id")
            self.created_category_id = str(category_id) if category_id else None
            print(f"   ✅ Budget category created successfully")
            print(f"   🏷️  Category ID: {self.created_category_id}")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False

    def test_update_budget_category(self):
        """Test PUT /budget/category/{category_id}"""
        if not self.created_category_id:
            print("   ⚠️  Skipping update test - no category created")
            return False

        print("✏️  Testing budget category update...")

        url = f"{self.api_url}/admin/budget/category/{self.created_category_id}"
        update_data = {
            "actual_spent": 22500.00,
            "payment_status": "partial",
            "budgeted_amount": 27000.00
        }

        response = requests.put(url, headers=self.get_headers(), json=update_data)

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Budget category updated successfully")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False

    def test_create_vendor_quote(self):
        """Test POST /weddings/{wedding_id}/quotes"""
        print("💰 Testing vendor quote creation...")

        url = f"{self.api_url}/admin/weddings/{self.wedding_id}/quotes"
        quote_data = {
            "vendor_name": "Test Photography Studio",
            "vendor_email": "info@testphotos.com",
            "vendor_phone": "555-TEST-PHOTO",
            "service_category": "photography",
            "quote_amount": 3500.00,
            "quote_details": {
                "hours": 8,
                "photographers": 2,
                "edited_photos": 500,
                "prints": "100 4x6 prints included"
            },
            "includes": ["8 hours coverage", "2 photographers", "500 edited photos", "online gallery"],
            "excludes": ["Video", "Albums", "Engagement session"],
            "terms_conditions": "50% deposit required to book",
            "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
            "notes": "Award-winning photography team"
        }

        response = requests.post(url, headers=self.get_headers(), json=quote_data)

        print(f"   Status: {response.status_code}")
        if response.status_code in [200, 201]:
            data = response.json()
            quote_data = data.get("quote", {})
            # Extract ID and ensure it's a string
            quote_id = quote_data.get("id") or quote_data.get("_id")
            self.created_quote_id = str(quote_id) if quote_id else None
            print(f"   ✅ Vendor quote created successfully")
            print(f"   🏷️  Quote ID: {self.created_quote_id}")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False

    def test_get_vendor_quotes(self):
        """Test GET /weddings/{wedding_id}/quotes"""
        print("📋 Testing vendor quotes retrieval...")

        url = f"{self.api_url}/admin/weddings/{self.wedding_id}/quotes"
        response = requests.get(url, headers=self.get_headers())

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            quotes = data if isinstance(data, list) else data.get("quotes", [])
            print(f"   ✅ Retrieved {len(quotes)} vendor quotes")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False

    def test_record_payment(self):
        """Test POST /budget/category/{category_id}/payment"""
        if not self.created_category_id:
            print("   ⚠️  Skipping payment test - no category created")
            return False

        print("💳 Testing payment recording...")

        url = f"{self.api_url}/admin/budget/category/{self.created_category_id}/payment"
        payment_data = {
            "vendor_name": "Test Venue LLC",
            "amount": 10000.00,
            "payment_method": "card",
            "payment_date": datetime.now().isoformat(),
            "description": "Venue deposit payment",
            "notes": "Initial deposit for venue booking"
        }

        response = requests.post(url, headers=self.get_headers(), json=payment_data)

        print(f"   Status: {response.status_code}")
        if response.status_code in [200, 201]:
            print(f"   ✅ Payment recorded successfully")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False

    def test_get_budget_templates(self):
        """Test GET /budget/templates"""
        print("📋 Testing budget templates retrieval...")

        url = f"{self.api_url}/admin/budget/templates"
        response = requests.get(url, headers=self.get_headers())

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            templates = data if isinstance(data, list) else data.get("templates", [])
            print(f"   ✅ Retrieved {len(templates)} budget templates")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False

    def test_cost_estimation(self):
        """Test POST /budget/estimate"""
        print("🧮 Testing cost estimation...")

        url = f"{self.api_url}/admin/budget/estimate"
        estimation_data = {
            "guest_count": 100,
            "wedding_type": "traditional",
            "region": "national"
        }

        response = requests.post(url, headers=self.get_headers(), json=estimation_data)

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            estimated_total = data.get("estimated_total", 0)
            print(f"   ✅ Cost estimation completed")
            print(f"   💰 Estimated total: ${estimated_total}")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False

    def test_budget_alerts(self):
        """Test GET /budget/alerts/{wedding_id}"""
        print("🚨 Testing budget alerts...")

        url = f"{self.api_url}/admin/budget/alerts/{self.wedding_id}"
        response = requests.get(url, headers=self.get_headers())

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            alerts = data if isinstance(data, list) else data.get("alerts", [])
            print(f"   ✅ Retrieved {len(alerts)} budget alerts")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False

    def cleanup(self):
        """Clean up test data"""
        print("🧹 Cleaning up test data...")

        # Delete created category
        if self.created_category_id:
            url = f"{self.api_url}/admin/budget/category/{self.created_category_id}"
            response = requests.delete(url, headers=self.get_headers())
            if response.status_code == 200:
                print("   ✅ Test category deleted")
            else:
                print(f"   ⚠️  Could not delete test category: {response.status_code}")

    def run_all_tests(self):
        """Run the complete budget test suite"""
        print("🧪 Starting Budget API Test Suite")
        print("=" * 50)

        tests = [
            ("Authentication", self.authenticate),
            ("Setup Test Wedding", self.setup_test_wedding),
            ("Get Budget Summary", self.test_get_budget_summary),
            ("Create Budget Category", self.test_create_budget_category),
            ("Update Budget Category", self.test_update_budget_category),
            ("Create Vendor Quote", self.test_create_vendor_quote),
            ("Get Vendor Quotes", self.test_get_vendor_quotes),
            ("Record Payment", self.test_record_payment),
            ("Get Budget Templates", self.test_get_budget_templates),
            ("Cost Estimation", self.test_cost_estimation),
            ("Budget Alerts", self.test_budget_alerts),
        ]

        results = {}

        for test_name, test_func in tests:
            print(f"\n🔍 {test_name}")
            try:
                results[test_name] = test_func()
            except Exception as e:
                print(f"   ❌ Test failed with exception: {str(e)}")
                results[test_name] = False

        # Cleanup
        self.cleanup()

        # Results summary
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)

        passed = sum(1 for result in results.values() if result)
        total = len(results)

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name}")

        print(f"\n🎯 OVERALL RESULT: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 ALL BUDGET TESTS PASSED! Budget feature is fully functional!")
            return True
        else:
            print("⚠️  Some tests failed. Budget feature needs attention.")
            return False

if __name__ == "__main__":
    tester = BudgetAPITester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
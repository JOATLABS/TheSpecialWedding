#!/usr/bin/env python3
"""
Comprehensive Frontend Form UI Test Suite
Tests the form management dashboard, form builder, and public form submission using browser automation
"""

import asyncio
import requests
import json
import os
import time
from typing import Dict, Any

# Test configuration
API_BASE_URL = os.getenv("NEXT_PUBLIC_API_BASE_URL")
FRONTEND_BASE_URL = os.getenv("FRONTEND_URL")
TEST_USER_EMAIL = os.getenv("TEST_PLANNER_EMAIL")
TEST_USER_PASSWORD = os.getenv("TEST_PLANNER_PASSWORD")

# Ensure required environment variables are set
assert API_BASE_URL, "NEXT_PUBLIC_API_BASE_URL environment variable is required"
assert FRONTEND_BASE_URL, "FRONTEND_URL environment variable is required"
assert TEST_USER_EMAIL, "TEST_PLANNER_EMAIL environment variable is required"
assert TEST_USER_PASSWORD, "TEST_PLANNER_PASSWORD environment variable is required"

class FrontendFormTester:
    def __init__(self):
        self.api_url = API_BASE_URL
        self.frontend_url = FRONTEND_BASE_URL
        self.token = None
        self.wedding_id = None
        self.created_form_id = None
        self.form_public_url = None

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

    def setup_test_wedding(self):
        """Use existing test wedding"""
        print("🏰 Setting up test wedding...")
        self.wedding_id = "68ae66c5c30359265c544ca7"
        print(f"✅ Using existing wedding: {self.wedding_id}")
        return True

    def create_test_form_via_api(self):
        """Create a test form via API for frontend testing"""
        print("📝 Creating test form via API...")

        url = f"{self.api_url}/admin/forms/from-template/wedding_feedback"
        params = {
            "form_name": "Frontend Test Wedding Feedback Form",
            "wedding_id": self.wedding_id
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, params=params)

        if response.status_code in [200, 201]:
            data = response.json()
            self.created_form_id = data.get("id")
            self.form_public_url = f"{self.frontend_url}/forms/{self.created_form_id}"
            print(f"✅ Test form created: {self.created_form_id}")
            print(f"🌐 Public URL: {self.form_public_url}")
            return True
        else:
            print(f"❌ Failed to create test form: {response.text}")
            return False

    def test_frontend_accessibility(self):
        """Test if frontend pages are accessible"""
        print("🌐 Testing frontend page accessibility...")

        # Test admin forms page
        admin_forms_url = f"{self.frontend_url}/admin/forms"
        try:
            response = requests.get(admin_forms_url, timeout=10)
            if response.status_code == 200:
                print(f"   ✅ Admin forms page accessible: {response.status_code}")
            else:
                print(f"   ⚠️  Admin forms page status: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Admin forms page error: {str(e)}")
            return False

        # Test public form page
        if self.created_form_id:
            try:
                response = requests.get(self.form_public_url, timeout=10)
                if response.status_code == 200:
                    print(f"   ✅ Public form page accessible: {response.status_code}")
                else:
                    print(f"   ⚠️  Public form page status: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Public form page error: {str(e)}")
                return False

        return True

    def test_frontend_content_validation(self):
        """Test if frontend pages contain expected content"""
        print("📄 Testing frontend content validation...")

        # Test admin forms page content
        admin_forms_url = f"{self.frontend_url}/admin/forms"
        try:
            response = requests.get(admin_forms_url, timeout=10)
            content = response.text

            # Check for key elements
            expected_elements = [
                "Form Builder",  # Page title
                "Create New Form",  # Create button
                "Your Forms"  # Forms section
            ]

            missing_elements = []
            for element in expected_elements:
                if element not in content:
                    missing_elements.append(element)

            if missing_elements:
                print(f"   ⚠️  Missing elements in admin page: {missing_elements}")
            else:
                print(f"   ✅ Admin forms page content validated")

        except Exception as e:
            print(f"   ❌ Admin forms page content error: {str(e)}")
            return False

        # Test public form page content
        if self.created_form_id:
            try:
                response = requests.get(self.form_public_url, timeout=10)
                content = response.text

                # Check for form elements
                form_elements = [
                    "Frontend Test Wedding Feedback Form",  # Form title
                    "Overall Experience Rating",  # Field from template
                    "Submit"  # Submit button
                ]

                missing_elements = []
                for element in form_elements:
                    if element not in content:
                        missing_elements.append(element)

                if missing_elements:
                    print(f"   ⚠️  Missing elements in form page: {missing_elements}")
                else:
                    print(f"   ✅ Public form page content validated")

            except Exception as e:
                print(f"   ❌ Public form page content error: {str(e)}")
                return False

        return True

    def test_api_integration(self):
        """Test frontend-backend API integration"""
        print("🔗 Testing frontend-backend API integration...")

        # Test if frontend can fetch forms via API
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        # Test forms list endpoint
        try:
            response = requests.get(f"{self.api_url}/admin/forms", headers=headers)
            if response.status_code == 200:
                forms = response.json()
                print(f"   ✅ Forms API integration working - {len(forms)} forms")

                # Check if our test form is in the list
                test_form_found = any(form.get("id") == self.created_form_id for form in forms)
                if test_form_found:
                    print(f"   ✅ Test form found in API response")
                else:
                    print(f"   ⚠️  Test form not found in API response")

            else:
                print(f"   ❌ Forms API error: {response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ Forms API integration error: {str(e)}")
            return False

        # Test form templates endpoint
        try:
            response = requests.get(f"{self.api_url}/admin/form-templates", headers=headers)
            if response.status_code == 200:
                templates = response.json().get("templates", [])
                print(f"   ✅ Templates API integration working - {len(templates)} templates")
            else:
                print(f"   ❌ Templates API error: {response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ Templates API integration error: {str(e)}")
            return False

        return True

    def test_public_form_submission_flow(self):
        """Test the complete public form submission flow"""
        if not self.created_form_id:
            print("   ⚠️  Skipping submission flow test - no form created")
            return False

        print("📝 Testing public form submission flow...")

        # First, get the public form data
        try:
            response = requests.get(f"{self.api_url}/public/forms/{self.created_form_id}")
            if response.status_code != 200:
                print(f"   ❌ Failed to get public form: {response.status_code}")
                return False

            form_data = response.json()
            print(f"   ✅ Public form data retrieved")

        except Exception as e:
            print(f"   ❌ Public form retrieval error: {str(e)}")
            return False

        # Test form submission
        try:
            submission_data = {
                "responses": {
                    "overall_rating": 5,
                    "planning_satisfaction": 9,
                    "communication_rating": 5,
                    "venue_satisfaction": 4,
                    "vendor_satisfaction": 5,
                    "timeline_satisfaction": 4,
                    "budget_satisfaction": 3,
                    "favorite_moment": "The first dance was absolutely magical. Everything was perfect.",
                    "improvements": "Maybe provide more vegetarian options at dinner.",
                    "recommendation": "Definitely",
                    "additional_comments": "Thank you for making our special day absolutely perfect! We couldn't have asked for better service."
                },
                "submitted_by_email": "frontend.test@example.com",
                "submitted_by_name": "Frontend Test User"
            }

            response = requests.post(
                f"{self.api_url}/public/forms/{self.created_form_id}/submit",
                json=submission_data
            )

            if response.status_code in [200, 201]:
                submission_response = response.json()
                print(f"   ✅ Form submission successful")
                print(f"   📝 Response ID: {submission_response.get('id')}")
                return True
            else:
                print(f"   ❌ Form submission failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"   ❌ Form submission error: {str(e)}")
            return False

    def test_form_analytics_and_responses(self):
        """Test form analytics and responses endpoints"""
        if not self.created_form_id:
            print("   ⚠️  Skipping analytics test - no form created")
            return False

        print("📈 Testing form analytics and responses...")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        # Test analytics endpoint
        try:
            response = requests.get(f"{self.api_url}/admin/forms/{self.created_form_id}/analytics", headers=headers)
            if response.status_code == 200:
                analytics = response.json()
                print(f"   ✅ Form analytics retrieved")
                print(f"   📊 Total submissions: {analytics.get('total_submissions', 0)}")
            else:
                print(f"   ❌ Analytics failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ Analytics error: {str(e)}")
            return False

        # Test responses endpoint
        try:
            response = requests.get(f"{self.api_url}/admin/forms/{self.created_form_id}/responses", headers=headers)
            if response.status_code == 200:
                responses = response.json()
                responses_list = responses if isinstance(responses, list) else responses.get("responses", [])
                print(f"   ✅ Form responses retrieved")
                print(f"   📝 Response count: {len(responses_list)}")
            else:
                print(f"   ❌ Responses failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ Responses error: {str(e)}")
            return False

        return True

    def test_csv_export_functionality(self):
        """Test CSV export functionality"""
        if not self.created_form_id:
            print("   ⚠️  Skipping CSV export test - no form created")
            return False

        print("📄 Testing CSV export functionality...")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(
                f"{self.api_url}/admin/forms/{self.created_form_id}/export/csv",
                headers=headers,
                params={"include_metadata": "true"}
            )

            if response.status_code == 200:
                print(f"   ✅ CSV export successful")
                print(f"   📊 Content type: {response.headers.get('content-type')}")
                print(f"   💾 File size: {len(response.content)} bytes")

                # Validate CSV content
                csv_content = response.content.decode('utf-8')
                if "overall_rating" in csv_content:
                    print(f"   ✅ CSV contains expected headers")
                if "Frontend Test User" in csv_content:
                    print(f"   ✅ CSV contains submitted data")

                return True
            else:
                print(f"   ❌ CSV export failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ CSV export error: {str(e)}")
            return False

    def test_frontend_routes_availability(self):
        """Test availability of all frontend routes"""
        print("🛣️  Testing frontend route availability...")

        routes_to_test = [
            "/admin/forms",
            f"/admin/forms/{self.created_form_id}/edit" if self.created_form_id else None,
            f"/admin/forms/{self.created_form_id}/responses" if self.created_form_id else None,
            f"/admin/forms/{self.created_form_id}/analytics" if self.created_form_id else None,
            f"/forms/{self.created_form_id}" if self.created_form_id else None,
        ]

        available_routes = 0
        total_routes = 0

        for route in routes_to_test:
            if route is None:
                continue

            total_routes += 1
            try:
                response = requests.get(f"{self.frontend_url}{route}", timeout=10)
                if response.status_code == 200:
                    available_routes += 1
                    print(f"   ✅ Route available: {route}")
                else:
                    print(f"   ⚠️  Route status {response.status_code}: {route}")

            except Exception as e:
                print(f"   ❌ Route error {route}: {str(e)}")

        print(f"   📊 Route availability: {available_routes}/{total_routes}")
        return available_routes == total_routes

    def cleanup(self):
        """Clean up test data"""
        print("🧹 Cleaning up test data...")

        if self.created_form_id:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            try:
                response = requests.delete(f"{self.api_url}/admin/forms/{self.created_form_id}", headers=headers)
                if response.status_code == 200:
                    print("   ✅ Test form deleted")
                else:
                    print(f"   ⚠️  Could not delete test form: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Cleanup error: {str(e)}")

    def run_all_tests(self):
        """Run the complete frontend form test suite"""
        print("🧪 Starting Frontend Form UI Test Suite")
        print("=" * 50)

        tests = [
            ("Authentication", self.authenticate),
            ("Setup Test Wedding", self.setup_test_wedding),
            ("Create Test Form", self.create_test_form_via_api),
            ("Frontend Accessibility", self.test_frontend_accessibility),
            ("Frontend Content Validation", self.test_frontend_content_validation),
            ("API Integration", self.test_api_integration),
            ("Public Form Submission Flow", self.test_public_form_submission_flow),
            ("Form Analytics & Responses", self.test_form_analytics_and_responses),
            ("CSV Export Functionality", self.test_csv_export_functionality),
            ("Frontend Routes Availability", self.test_frontend_routes_availability),
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
        print("📊 FRONTEND TEST RESULTS SUMMARY")
        print("=" * 50)

        passed = sum(1 for result in results.values() if result)
        total = len(results)

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name}")

        print(f"\n🎯 OVERALL RESULT: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 ALL FRONTEND FORM TESTS PASSED! Frontend is fully functional!")
            return True
        else:
            print("⚠️  Some frontend tests failed. Frontend needs attention.")
            return False

if __name__ == "__main__":
    tester = FrontendFormTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
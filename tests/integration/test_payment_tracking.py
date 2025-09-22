"""
Integration tests for payment tracking functionality
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_database
from app.models.budget import PaymentRecord, BudgetCategory
from app.services.budget_service import BudgetService

client = TestClient(app)

# Test data
VALID_PAYMENT = {
    "vendor_name": "Flowers by Jane",
    "amount": 2500.00,
    "payment_method": "card",
    "payment_date": datetime.now().isoformat(),
    "description": "50% deposit for wedding flowers",
    "notes": "Includes delivery and setup"
}

INVALID_PAYMENTS = [
    {
        "name": "negative_amount",
        "data": {
            "amount": -100,
            "payment_method": "cash",
            "payment_date": datetime.now().isoformat()
        },
        "expected_error": "Amount must be greater than 0"
    },
    {
        "name": "missing_method",
        "data": {
            "amount": 100,
            "payment_date": datetime.now().isoformat()
        },
        "expected_error": "Payment method is required"
    },
    {
        "name": "invalid_method",
        "data": {
            "amount": 100,
            "payment_method": "bitcoin",  # Not a valid method
            "payment_date": datetime.now().isoformat()
        },
        "expected_error": "Invalid payment method"
    },
    {
        "name": "future_date",
        "data": {
            "amount": 100,
            "payment_method": "cash",
            "payment_date": (datetime.now() + timedelta(days=7)).isoformat()
        },
        "expected_error": "Payment date cannot be in the future"
    }
]


class TestPaymentRecording:
    """Test payment recording functionality"""

    @pytest.fixture(autouse=True)
    def setup(self, test_database, test_user_token):
        """Set up test environment"""
        self.db = test_database
        self.token = test_user_token
        self.budget_service = BudgetService()

        # Create test wedding and budget category
        self.wedding_id = "test_wedding_123"
        self.category = self._create_test_category()

    def _create_test_category(self):
        """Create a test budget category"""
        category_data = {
            "wedding_id": self.wedding_id,
            "name": "Flowers",
            "description": "Floral arrangements and bouquets",
            "budgeted_amount": 5000.00,
            "actual_spent": 0,
            "priority": 2
        }
        result = self.db.budget_categories.insert_one(category_data)
        category_data["_id"] = str(result.inserted_id)
        return category_data

    def test_record_valid_payment(self):
        """Test recording a valid payment"""
        response = client.post(
            f"/admin/budget/category/{self.category['_id']}/payment",
            json=VALID_PAYMENT,
            headers={"Authorization": f"Bearer {self.token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "payment" in data
        assert data["payment"]["amount"] == VALID_PAYMENT["amount"]
        assert data["payment"]["vendor_name"] == VALID_PAYMENT["vendor_name"]

        # Verify category was updated
        updated_category = self.db.budget_categories.find_one(
            {"_id": self.category["_id"]}
        )
        assert updated_category["actual_spent"] == VALID_PAYMENT["amount"]

    @pytest.mark.parametrize("invalid_payment", INVALID_PAYMENTS)
    def test_record_invalid_payment(self, invalid_payment):
        """Test recording invalid payments"""
        response = client.post(
            f"/admin/budget/category/{self.category['_id']}/payment",
            json=invalid_payment["data"],
            headers={"Authorization": f"Bearer {self.token}"}
        )

        assert response.status_code == 400
        assert invalid_payment["expected_error"] in response.json()["detail"]

    def test_record_payment_nonexistent_category(self):
        """Test recording payment for non-existent category"""
        response = client.post(
            "/admin/budget/category/nonexistent_id/payment",
            json=VALID_PAYMENT,
            headers={"Authorization": f"Bearer {self.token}"}
        )

        assert response.status_code == 404
        assert "Category not found" in response.json()["detail"]

    def test_record_payment_unauthorized(self):
        """Test recording payment without authorization"""
        response = client.post(
            f"/admin/budget/category/{self.category['_id']}/payment",
            json=VALID_PAYMENT
        )

        assert response.status_code == 401

    def test_multiple_payments_accumulation(self):
        """Test that multiple payments accumulate correctly"""
        payments = [
            {"amount": 1000, "payment_method": "cash", "payment_date": datetime.now().isoformat()},
            {"amount": 1500, "payment_method": "card", "payment_date": datetime.now().isoformat()},
            {"amount": 500, "payment_method": "check", "payment_date": datetime.now().isoformat()}
        ]

        total_paid = 0
        for payment in payments:
            response = client.post(
                f"/admin/budget/category/{self.category['_id']}/payment",
                json=payment,
                headers={"Authorization": f"Bearer {self.token}"}
            )
            assert response.status_code == 200
            total_paid += payment["amount"]

        # Verify total
        updated_category = self.db.budget_categories.find_one(
            {"_id": self.category["_id"]}
        )
        assert updated_category["actual_spent"] == total_paid
        assert updated_category["remaining_amount"] == (
            updated_category["budgeted_amount"] - total_paid
        )


class TestPaymentHistory:
    """Test payment history retrieval"""

    @pytest.fixture(autouse=True)
    def setup(self, test_database, test_user_token):
        """Set up test environment"""
        self.db = test_database
        self.token = test_user_token
        self.wedding_id = "test_wedding_123"
        self._create_test_payments()

    def _create_test_payments(self):
        """Create test payment records"""
        self.test_payments = []
        for i in range(5):
            payment = PaymentRecord(
                category_id=f"category_{i}",
                vendor_name=f"Vendor {i}",
                amount=1000 * (i + 1),
                payment_method=["cash", "card", "check", "transfer", "cash"][i],
                payment_date=datetime.now() - timedelta(days=i),
                status="completed"
            )
            result = self.db.payment_records.insert_one(payment.dict())
            payment.id = str(result.inserted_id)
            self.test_payments.append(payment)

    def test_get_payment_history(self):
        """Test retrieving payment history for a wedding"""
        response = client.get(
            f"/admin/weddings/{self.wedding_id}/payments",
            headers={"Authorization": f"Bearer {self.token}"}
        )

        assert response.status_code == 200
        payments = response.json()
        assert isinstance(payments, list)
        assert len(payments) >= len(self.test_payments)

    def test_payment_history_sorting(self):
        """Test that payment history is sorted by date (newest first)"""
        response = client.get(
            f"/admin/weddings/{self.wedding_id}/payments",
            headers={"Authorization": f"Bearer {self.token}"}
        )

        payments = response.json()
        dates = [p["payment_date"] for p in payments]
        assert dates == sorted(dates, reverse=True)

    def test_payment_history_unauthorized(self):
        """Test retrieving payment history without authorization"""
        response = client.get(f"/admin/weddings/{self.wedding_id}/payments")
        assert response.status_code == 401

    def test_payment_history_with_filters(self):
        """Test filtering payment history"""
        # This would be implemented if the API supports query parameters
        # for filtering by date range, vendor, method, etc.
        pass


class TestBudgetAlerts:
    """Test budget alert generation from payments"""

    @pytest.fixture(autouse=True)
    def setup(self, test_database, test_user_token):
        """Set up test environment"""
        self.db = test_database
        self.token = test_user_token
        self.wedding_id = "test_wedding_123"

        # Create category with low budget
        self.category = self._create_test_category(budgeted_amount=1000)

    def _create_test_category(self, budgeted_amount=1000):
        """Create a test budget category"""
        category_data = {
            "wedding_id": self.wedding_id,
            "name": "Test Category",
            "budgeted_amount": budgeted_amount,
            "actual_spent": 0,
            "priority": 2
        }
        result = self.db.budget_categories.insert_one(category_data)
        category_data["_id"] = str(result.inserted_id)
        return category_data

    def test_over_budget_alert_generation(self):
        """Test that over-budget alerts are generated"""
        # Record payment that exceeds budget
        payment_data = {
            "amount": 1500,  # Exceeds budgeted 1000
            "payment_method": "card",
            "payment_date": datetime.now().isoformat()
        }

        response = client.post(
            f"/admin/budget/category/{self.category['_id']}/payment",
            json=payment_data,
            headers={"Authorization": f"Bearer {self.token}"}
        )

        assert response.status_code == 200

        # Check for alert
        alerts_response = client.get(
            f"/admin/weddings/{self.wedding_id}/budget/alerts",
            headers={"Authorization": f"Bearer {self.token}"}
        )

        alerts = alerts_response.json()
        over_budget_alerts = [
            a for a in alerts
            if a["alert_type"] == "over_budget"
            and a["category_id"] == self.category["_id"]
        ]
        assert len(over_budget_alerts) > 0

    def test_payment_milestone_alerts(self):
        """Test alerts at spending milestones (50%, 75%, 90%)"""
        milestones = [
            (500, 50),   # 50% of 1000
            (750, 75),   # 75% of 1000
            (900, 90)    # 90% of 1000
        ]

        for amount, percentage in milestones:
            # Reset category spending
            self.db.budget_categories.update_one(
                {"_id": self.category["_id"]},
                {"$set": {"actual_spent": 0}}
            )

            payment_data = {
                "amount": amount,
                "payment_method": "cash",
                "payment_date": datetime.now().isoformat()
            }

            response = client.post(
                f"/admin/budget/category/{self.category['_id']}/payment",
                json=payment_data,
                headers={"Authorization": f"Bearer {self.token}"}
            )

            assert response.status_code == 200
            # Additional assertions for milestone alerts would go here


class TestPaymentSecurity:
    """Test payment security and multi-tenancy"""

    @pytest.fixture(autouse=True)
    def setup(self, test_database):
        """Set up test environment"""
        self.db = test_database

        # Create two different wedding planners with separate weddings
        self.planner1_token = self._create_test_user("planner1@test.com")
        self.planner2_token = self._create_test_user("planner2@test.com")

        self.wedding1_id = "wedding_planner1"
        self.wedding2_id = "wedding_planner2"

        self.category1 = self._create_category_for_wedding(self.wedding1_id)
        self.category2 = self._create_category_for_wedding(self.wedding2_id)

    def _create_test_user(self, email):
        """Create test user and return token"""
        # Implementation would create user and return JWT token
        pass

    def _create_category_for_wedding(self, wedding_id):
        """Create budget category for specific wedding"""
        category_data = {
            "wedding_id": wedding_id,
            "name": "Test Category",
            "budgeted_amount": 5000,
            "actual_spent": 0
        }
        result = self.db.budget_categories.insert_one(category_data)
        category_data["_id"] = str(result.inserted_id)
        return category_data

    def test_cross_wedding_payment_prevented(self):
        """Test that planners cannot record payments for other weddings"""
        # Planner1 tries to record payment for Planner2's category
        payment_data = {
            "amount": 1000,
            "payment_method": "cash",
            "payment_date": datetime.now().isoformat()
        }

        response = client.post(
            f"/admin/budget/category/{self.category2['_id']}/payment",
            json=payment_data,
            headers={"Authorization": f"Bearer {self.planner1_token}"}
        )

        assert response.status_code == 403
        assert "Permission denied" in response.json()["detail"]

    def test_payment_isolation(self):
        """Test that payment history is isolated by wedding"""
        # Record payment for wedding1
        payment1 = {
            "amount": 1000,
            "vendor_name": "Wedding1 Vendor",
            "payment_method": "card",
            "payment_date": datetime.now().isoformat()
        }

        client.post(
            f"/admin/budget/category/{self.category1['_id']}/payment",
            json=payment1,
            headers={"Authorization": f"Bearer {self.planner1_token}"}
        )

        # Planner2 should not see Wedding1's payments
        response = client.get(
            f"/admin/weddings/{self.wedding2_id}/payments",
            headers={"Authorization": f"Bearer {self.planner2_token}"}
        )

        payments = response.json()
        wedding1_payments = [
            p for p in payments
            if p.get("vendor_name") == "Wedding1 Vendor"
        ]
        assert len(wedding1_payments) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Unit tests for SubscriptionService
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from bson import ObjectId

from app.services.subscription_service import SubscriptionService


class TestSubscriptionService:
    """Test cases for SubscriptionService"""
    
    @pytest.fixture
    def subscription_service(self):
        """Create SubscriptionService instance with mocked database"""
        with patch('app.services.subscription_service.mongo') as mock_mongo:
            mock_mongo.db = {
                "users": Mock(),
                "subscription_plans": Mock(),
                "ai_usage": Mock()
            }
            return SubscriptionService()
    
    @pytest.fixture
    def sample_user(self):
        """Sample user data"""
        return {
            "_id": ObjectId("60d5ec49f1a2c8b1f8e4d123"),
            "email": "user@test.com",
            "subscription": {
                "plan_id": ObjectId("60d5ec49f1a2c8b1f8e4d456"),
                "status": "active",
                "start_date": datetime.utcnow() - timedelta(days=10),
                "end_date": datetime.utcnow() + timedelta(days=20),
                "trial_end": None,
                "current_usage": {
                    "weddings": 2,
                    "ai_credits": 150,
                    "vendor_seats": 1,
                    "staff_seats": 3
                }
            }
        }
    
    @pytest.fixture
    def sample_plan(self):
        """Sample subscription plan"""
        return {
            "_id": ObjectId("60d5ec49f1a2c8b1f8e4d456"),
            "name": "Professional",
            "price": 49.99,
            "currency": "USD",
            "billing_period": "monthly",
            "limits": {
                "weddings": 10,
                "ai_credits": 1000,
                "vendor_seats": 5,
                "staff_seats": 10
            },
            "features": {
                "ai_tools": True,
                "advanced_reporting": True,
                "white_label": False,
                "custom_integrations": False,
                "multi_user_collaboration": True
            }
        }
    
    def test_get_user_subscription_success(self, subscription_service, sample_user):
        """Test getting user subscription successfully"""
        # Arrange
        user_id = str(sample_user["_id"])
        subscription_service.users_collection.find_one.return_value = sample_user
        
        # Act
        result = subscription_service.get_user_subscription(user_id)
        
        # Assert
        assert result == sample_user["subscription"]
        subscription_service.users_collection.find_one.assert_called_once_with(
            {"_id": ObjectId(user_id)}
        )
    
    def test_get_user_subscription_not_found(self, subscription_service):
        """Test getting subscription for non-existent user"""
        # Arrange
        subscription_service.users_collection.find_one.return_value = None
        
        # Act
        result = subscription_service.get_user_subscription("60d5ec49f1a2c8b1f8e4d123")
        
        # Assert
        assert result is None
    
    def test_get_plan_success(self, subscription_service, sample_plan):
        """Test getting subscription plan successfully"""
        # Arrange
        plan_id = str(sample_plan["_id"])
        subscription_service.subscription_plans_collection.find_one.return_value = sample_plan
        
        # Act
        result = subscription_service.get_plan(plan_id)
        
        # Assert
        assert result == sample_plan
        subscription_service.subscription_plans_collection.find_one.assert_called_once_with(
            {"_id": ObjectId(plan_id)}
        )
    
    def test_check_usage_limits_within_limit(self, subscription_service, sample_user, sample_plan):
        """Test usage limit check when within limits"""
        # Arrange
        user_id = str(sample_user["_id"])
        subscription_service.users_collection.find_one.return_value = sample_user
        subscription_service.subscription_plans_collection.find_one.return_value = sample_plan
        
        # Act
        result = subscription_service.check_usage_limits(user_id, "weddings", 1)
        
        # Assert
        assert result["allowed"] is True
        assert "within limit" in result["message"]
    
    def test_check_usage_limits_exceeds_limit(self, subscription_service, sample_user, sample_plan):
        """Test usage limit check when exceeding limits"""
        # Arrange
        user_id = str(sample_user["_id"])
        # Set current usage to near limit
        sample_user["subscription"]["current_usage"]["weddings"] = 10
        subscription_service.users_collection.find_one.return_value = sample_user
        subscription_service.subscription_plans_collection.find_one.return_value = sample_plan
        
        # Act
        result = subscription_service.check_usage_limits(user_id, "weddings", 1)
        
        # Assert
        assert result["allowed"] is False
        assert "limit exceeded" in result["message"].lower()
    
    def test_check_usage_limits_no_subscription(self, subscription_service):
        """Test usage limit check when user has no subscription"""
        # Arrange
        user_id = "60d5ec49f1a2c8b1f8e4d123"
        subscription_service.users_collection.find_one.return_value = {"_id": ObjectId(user_id)}
        
        # Act
        result = subscription_service.check_usage_limits(user_id, "weddings", 1)
        
        # Assert
        assert result["allowed"] is False
        assert "no active subscription" in result["message"].lower()
    
    def test_increment_usage_success(self, subscription_service, sample_user):
        """Test incrementing usage successfully"""
        # Arrange
        user_id = str(sample_user["_id"])
        subscription_service.users_collection.find_one.return_value = sample_user
        subscription_service.users_collection.update_one.return_value = Mock()
        
        # Act
        result = subscription_service.increment_usage(user_id, "weddings", 1)
        
        # Assert
        assert result is True
        subscription_service.users_collection.update_one.assert_called_once()
    
    def test_is_trial_expired_not_in_trial(self, subscription_service, sample_user):
        """Test trial expiration check when not in trial"""
        # Arrange
        user_id = str(sample_user["_id"])
        subscription_service.users_collection.find_one.return_value = sample_user
        
        # Act
        result = subscription_service.is_trial_expired(user_id)
        
        # Assert
        assert result is False
    
    def test_is_trial_expired_trial_active(self, subscription_service, sample_user):
        """Test trial expiration check when trial is active"""
        # Arrange
        user_id = str(sample_user["_id"])
        sample_user["subscription"]["trial_end"] = datetime.utcnow() + timedelta(days=5)
        subscription_service.users_collection.find_one.return_value = sample_user
        
        # Act
        result = subscription_service.is_trial_expired(user_id)
        
        # Assert
        assert result is False
    
    def test_is_trial_expired_trial_ended(self, subscription_service, sample_user):
        """Test trial expiration check when trial has ended"""
        # Arrange
        user_id = str(sample_user["_id"])
        sample_user["subscription"]["trial_end"] = datetime.utcnow() - timedelta(days=1)
        subscription_service.users_collection.find_one.return_value = sample_user
        
        # Act
        result = subscription_service.is_trial_expired(user_id)
        
        # Assert
        assert result is True
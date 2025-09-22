#!/usr/bin/env python3
"""
Unit tests for Pydantic v2 model validation and functionality.
Tests the updated models without requiring database connections.
"""
import sys
import os
from datetime import datetime
import pytest
from pydantic import ValidationError

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))


class TestPyObjectId:
    """Test the updated PyObjectId implementation."""
    
    def test_import_pydantic_objectid(self):
        """Test that PyObjectId utility can be imported."""
        from utils.pydantic_objectid import PyObjectId, generate_object_id, is_valid_object_id
        assert PyObjectId is not None
        assert generate_object_id is not None
        assert is_valid_object_id is not None
    
    def test_objectid_generation(self):
        """Test ObjectId generation works."""
        from utils.pydantic_objectid import generate_object_id, is_valid_object_id
        
        test_id = generate_object_id()
        assert test_id is not None
        assert is_valid_object_id(str(test_id)) == True
    
    def test_objectid_validation(self):
        """Test ObjectId validation logic."""
        from utils.pydantic_objectid import PyObjectId, is_valid_object_id
        
        # Valid ObjectId string
        valid_id = "507f1f77bcf86cd799439011"
        assert is_valid_object_id(valid_id) == True
        
        # Invalid ObjectId strings
        assert is_valid_object_id("invalid") == False
        assert is_valid_object_id("") == False
        assert is_valid_object_id(None) == False


class TestBudgetModels:
    """Test budget-related Pydantic models."""
    
    def test_budget_category_creation(self):
        """Test BudgetCategory model creation."""
        from models.budget import BudgetCategory
        from utils.pydantic_objectid import generate_object_id
        
        category = BudgetCategory(
            wedding_id=str(generate_object_id()),
            name="Test Venue",
            description="Test venue booking",
            budgeted_amount=5000.0,
            actual_spent=4500.0,
            payment_status="paid",
            priority=1
        )
        
        assert category.name == "Test Venue"
        assert category.budgeted_amount == 5000.0
        assert category.actual_spent == 4500.0
        assert category.priority == 1
        assert str(category.id)  # Should be convertible to string
    
    def test_budget_category_validation(self):
        """Test BudgetCategory field validation."""
        from models.budget import BudgetCategory
        from utils.pydantic_objectid import generate_object_id
        
        # Test negative budget validation
        with pytest.raises(ValidationError) as exc_info:
            BudgetCategory(
                wedding_id=str(generate_object_id()),
                name="Invalid Category",
                budgeted_amount=-100.0  # Should fail
            )
        
        errors = exc_info.value.errors()
        assert any("greater than or equal to 0" in str(error) for error in errors)
        
        # Test empty name validation  
        with pytest.raises(ValidationError) as exc_info:
            BudgetCategory(
                wedding_id=str(generate_object_id()),
                name="",  # Should fail
                budgeted_amount=100.0
            )
        
        errors = exc_info.value.errors()
        assert any("at least 1" in str(error) for error in errors)
    
    def test_vendor_quote_creation(self):
        """Test VendorQuote model creation."""
        from models.budget import VendorQuote
        from utils.pydantic_objectid import generate_object_id
        
        quote = VendorQuote(
            wedding_id=str(generate_object_id()),
            vendor_name="Test Photographer",
            service_category="photography",
            quote_amount=2500.0,
            includes=["8 hour coverage", "Edited photos"],
            status="pending"
        )
        
        assert quote.vendor_name == "Test Photographer"
        assert quote.service_category == "photography"
        assert quote.quote_amount == 2500.0
        assert len(quote.includes) == 2
        assert quote.status == "pending"
    
    def test_budget_alert_creation(self):
        """Test BudgetAlert model creation."""
        from models.budget import BudgetAlert
        from utils.pydantic_objectid import generate_object_id
        
        alert = BudgetAlert(
            wedding_id=str(generate_object_id()),
            alert_type="over_budget",
            title="Budget exceeded",
            message="Venue costs exceeded budget by 10%",
            severity="medium"
        )
        
        assert alert.alert_type == "over_budget"
        assert alert.title == "Budget exceeded"
        assert alert.severity == "medium"


class TestModelSerialization:
    """Test model serialization and JSON schema generation."""
    
    def test_model_dump(self):
        """Test model_dump functionality."""
        from models.budget import BudgetCategory
        from utils.pydantic_objectid import generate_object_id
        
        category = BudgetCategory(
            wedding_id=str(generate_object_id()),
            name="Test Serialization",
            budgeted_amount=1000.0
        )
        
        # Test model_dump
        data_dict = category.model_dump()
        assert isinstance(data_dict, dict)
        assert data_dict['name'] == "Test Serialization"
        assert data_dict['budgeted_amount'] == 1000.0
    
    def test_model_dump_json(self):
        """Test model_dump_json functionality."""
        from models.budget import BudgetCategory
        from utils.pydantic_objectid import generate_object_id
        import json
        
        category = BudgetCategory(
            wedding_id=str(generate_object_id()),
            name="Test JSON",
            budgeted_amount=1500.0
        )
        
        # Test model_dump_json
        json_str = category.model_dump_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0
        
        # Parse JSON and verify ObjectId is serialized as string
        parsed = json.loads(json_str)
        assert isinstance(parsed['_id'], str)
        assert parsed['name'] == "Test JSON"
    
    def test_json_schema_generation(self):
        """Test JSON schema generation."""
        from models.budget import BudgetCategory
        
        schema = BudgetCategory.model_json_schema()
        assert isinstance(schema, dict)
        assert 'properties' in schema
        assert 'required' in schema
        
        # Check that required fields are in schema
        required_fields = schema.get('required', [])
        assert 'wedding_id' in required_fields
        assert 'name' in required_fields
        assert 'budgeted_amount' in required_fields


class TestFormModels:
    """Test form-related Pydantic models."""
    
    def test_form_field_creation(self):
        """Test FormField model creation.""" 
        from models.form import FormField
        
        field = FormField(
            id="test_field",
            label="Test Label", 
            type="text",
            placeholder="Enter text here",
            required=True,
            description="A test field"
        )
        
        assert field.id == "test_field"
        assert field.label == "Test Label"
        assert field.type == "text"
        assert field.required == True
    
    def test_form_field_validation(self):
        """Test FormField validation."""
        from models.form import FormField
        
        # Test invalid field ID
        with pytest.raises(ValidationError):
            FormField(
                id="invalid@field!",  # Should fail - invalid characters
                label="Test",
                type="text"
            )
        
        # Test empty label
        with pytest.raises(ValidationError):
            FormField(
                id="test_field",
                label="",  # Should fail - empty label
                type="text"
            )


class TestModelConfig:
    """Test that model configurations are properly updated to v2."""
    
    def test_model_config_exists(self):
        """Test that models use model_config instead of Config class."""
        from models.budget import BudgetCategory
        
        # Check that model_config exists
        assert hasattr(BudgetCategory, 'model_config')
        
        # Check that old Config class doesn't exist
        assert not hasattr(BudgetCategory, 'Config')
        
        # Check model_config properties
        config = BudgetCategory.model_config
        assert config.get('populate_by_name') == True
        assert config.get('arbitrary_types_allowed') == True
        assert config.get('str_strip_whitespace') == True
    
    def test_field_serializers_exist(self):
        """Test that field serializers are properly defined."""
        from models.budget import BudgetCategory
        
        # Check that serializer methods exist
        category = BudgetCategory(
            wedding_id="507f1f77bcf86cd799439011",
            name="Test",
            budgeted_amount=1000.0
        )
        
        # Test that serialization method exists
        assert hasattr(category, 'serialize_id')


class TestWeddingModels:
    """Test wedding-related Pydantic models."""
    
    def test_wedding_model_import(self):
        """Test that wedding models can be imported."""
        from models.wedding import WeddingModel, EventModel
        assert WeddingModel is not None
        assert EventModel is not None


class TestSubscriptionModels:
    """Test subscription-related Pydantic models."""
    
    def test_subscription_models_import(self):
        """Test that subscription models can be imported."""
        from models.subscription import SubscriptionPlanModel, UserSubscriptionModel
        assert SubscriptionPlanModel is not None
        assert UserSubscriptionModel is not None
    
    def test_subscription_enums(self):
        """Test that subscription enums work correctly."""
        from models.subscription import SubscriptionStatus, BillingInterval
        
        # Test enum values
        assert SubscriptionStatus.TRIAL == "trial"
        assert SubscriptionStatus.ACTIVE == "active"
        assert BillingInterval.MONTHLY == "monthly"
        assert BillingInterval.YEARLY == "yearly"


if __name__ == "__main__":
    # Run tests if called directly
    pytest.main([__file__, "-v"])
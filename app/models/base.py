"""
Base model classes and utilities for Pydantic v2 models.
Provides common functionality and optimizations for all models.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer, computed_field
from app.utils.pydantic_objectid import PyObjectId, generate_object_id


class TimestampedModel(BaseModel):
    """
    Base model with automatic timestamp management.
    Provides created_at and updated_at fields for all models.
    """
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Record creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Record last update timestamp"
    )

    model_config = ConfigDict(
        # Performance optimizations
        validate_assignment=True,        # Validate on field assignment
        use_enum_values=True,           # Use enum values directly
        str_strip_whitespace=True,      # Auto-strip string whitespace
        populate_by_name=True,          # Support field aliases
        arbitrary_types_allowed=True,   # Allow custom types like ObjectId

        # JSON serialization optimizations
        ser_json_timedelta='iso8601',   # Serialize timedeltas as ISO format
        ser_json_bytes='base64',        # Serialize bytes as base64

        # Validation optimizations
        extra='ignore',                 # Ignore extra fields for performance
        frozen=False                    # Allow mutations for better performance
    )

    def refresh_updated_at(self):
        """Manually update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()

    @computed_field
    @property
    def age_minutes(self) -> float:
        """Get the age of this record in minutes."""
        delta = datetime.utcnow() - self.created_at
        return delta.total_seconds() / 60
    @field_serializer('created_at', 'updated_at', when_used='json')
    def serialize_datetime(self, dt: datetime) -> str:
        """Serialize datetime fields to ISO format for JSON."""
        return dt.isoformat() if dt else None


class MongoModel(TimestampedModel):
    """
    Base model for MongoDB documents with ObjectId support.
    Extends TimestampedModel with MongoDB-specific functionality.
    """
    id: PyObjectId = Field(
        default_factory=generate_object_id,
        alias="_id",
        description="MongoDB ObjectId"
    )
    @field_serializer('id', when_used='json')
    def serialize_id(self, value: PyObjectId) -> str:
        """Serialize ObjectId to string for JSON output."""
        return str(value) if value else None
    @classmethod
    def create_with_id(cls, object_id: str, **kwargs):
        """Create instance with specific ObjectId."""
        from ..utils.pydantic_objectid import PyObjectId
        return cls(id=PyObjectId(object_id), **kwargs)
    def to_mongo_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB-ready dictionary."""
        data = self.model_dump(by_alias=True, exclude_unset=True)
        return data
    @classmethod
    def from_mongo_dict(cls, data: Dict[str, Any]):
        """Create instance from MongoDB dictionary."""
        return cls.model_validate(data)


class WeddingRelatedModel(MongoModel):
    """
    Base model for entities related to a specific wedding.
    Provides common wedding_id field and related functionality.
    """
    wedding_id: str = Field(
        ...,
        description="ID of the wedding this record belongs to",
        min_length=24,  # MongoDB ObjectId length
        max_length=24
    )
    @field_serializer('wedding_id', when_used='json')
    def serialize_wedding_id(self, value: str) -> str:
        """Ensure wedding_id is always a string."""
        return str(value) if value else None


class UserRelatedModel(MongoModel):
    """
    Base model for entities related to a specific user.
    Provides common user identification fields.
    """
    created_by: str = Field(
        ...,
        description="Email of the user who created this record",
        max_length=254  # RFC 5321 email length limit
    )
    updated_by: Optional[str] = Field(
        None,
        description="Email of the user who last updated this record",
        max_length=254
    )
    def mark_updated_by(self, user_email: str):
        """Mark record as updated by specific user."""
        self.updated_by = user_email
        self.refresh_updated_at()


class ValidatedModel(BaseModel):
    """
    Enhanced base model with additional validation and security features.
    Use for models requiring strict input validation and security.
    """
    model_config = ConfigDict(
        # Strict validation for security
        validate_assignment=True,
        str_strict=False,           # Allow string coercion
        str_strip_whitespace=True,  # Auto-strip whitespace
        str_to_lower=False,         # Don't auto-lowercase
        str_to_upper=False,         # Don't auto-uppercase
        # Security settings
        extra='forbid',             # Reject extra fields for security
        frozen=False,               # Allow updates
        populate_by_name=True,      # Support aliases
        # Performance settings
        use_enum_values=True,
        arbitrary_types_allowed=True
    )
    def model_dump_safe(self, exclude_sensitive: bool = True) -> Dict[str, Any]:
        """
        Safe model dump that can exclude sensitive fields.
        Override in subclasses to define sensitive fields.
        """
        exclude_fields = set()
        if exclude_sensitive:
            # Add common sensitive fields
            sensitive_fields = getattr(self, '_sensitive_fields', set())
            exclude_fields.update(sensitive_fields)

        return self.model_dump(exclude=exclude_fields)

    @classmethod
    def get_example_data(cls) -> Dict[str, Any]:
        """
        Get example data for this model.
        Override in subclasses to provide model-specific examples.
        """
        try:
            return cls.model_json_schema().get('example', {})
        except Exception:
            return {}


# Utility functions for common model operations
def create_model_example_schema(model_class: type[BaseModel], example_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a JSON schema with example data for a model class.

    Args:
        model_class: The Pydantic model class
        example_data: Example data dictionary

    Returns:
        JSON schema with example included
    """
    schema = model_class.model_json_schema()
    schema['example'] = example_data
    return schema


def validate_multiple_models(models_data: list[tuple[type[BaseModel], Dict[str, Any]]]) -> list[BaseModel]:
    """
    Validate multiple models at once.

    Args:
        models_data: List of tuples (model_class, data_dict)

    Returns:
        List of validated model instances

    Raises:
        ValidationError: If any model validation fails
    """
    validated_models = []

    for model_class, data in models_data:
        validated_model = model_class.model_validate(data)
        validated_models.append(validated_model)

    return validated_models
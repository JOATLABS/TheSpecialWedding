"""
Pydantic v2 compatible ObjectId implementation for MongoDB integration.
This replaces the deprecated v1 style validators with modern core schema approach.
"""

from typing import Any, Dict

from bson import ObjectId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """
    Pydantic v2 compatible ObjectId that works with MongoDB BSON ObjectIds.
    Features:
    - Validates string representations of ObjectIds
    - Converts to ObjectId instances automatically
    - Serializes to string for JSON responses
    - Full Pydantic v2 core schema support
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """
        Generate the core schema for Pydantic v2 validation.
        This replaces the deprecated __get_validators__ method from v1.
        """
        return core_schema.with_info_before_validator_function(
            cls._validate_object_id,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _validate_object_id(cls, value: Any) -> "PyObjectId":
        """
        Validate and convert input to ObjectId.

        Args:
            value: Input value (string, ObjectId, or other)

        Returns:
            PyObjectId: Validated ObjectId instance

        Raises:
            ValueError: If value cannot be converted to valid ObjectId
        """
        if isinstance(value, ObjectId):
            return cls(value)

        if isinstance(value, cls):
            return value

        if isinstance(value, str):
            if ObjectId.is_valid(value):
                return cls(value)
            else:
                raise ValueError(f"Invalid ObjectId format: {value}")
        # Handle other types that might be convertible
        try:
            if hasattr(value, "__str__"):
                str_value = str(value)
                if ObjectId.is_valid(str_value):
                    return cls(str_value)
        except Exception:
            pass

        raise ValueError(f"Cannot convert {type(value).__name__} to ObjectId: {value}")

    @classmethod
    def __get_pydantic_json_schema__(
        cls, field_schema: Dict[str, Any], handler
    ) -> Dict[str, Any]:
        """
        Generate JSON schema for OpenAPI documentation.
        This replaces the deprecated __modify_schema__ method from v1.
        """
        field_schema.update(
            {
                "type": "string",
                "format": "objectid",
                "description": "MongoDB ObjectId as a 24-character hexadecimal string",
                "pattern": "^[0-9a-fA-F]{24}$",
                "example": "507f1f77bcf86cd799439011",
            }
        )
        return field_schema

    def __str__(self) -> str:
        """String representation for serialization."""
        return str(super())

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"PyObjectId('{str(self)}')"

    @property
    def hex_string(self) -> str:
        """Get the hexadecimal string representation."""
        return str(self)

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for serialization."""
        return {"$oid": str(self)}


# Utility functions for common ObjectId operations
def generate_object_id() -> PyObjectId:
    """Generate a new ObjectId."""
    return PyObjectId()


def is_valid_object_id(value: Any) -> bool:
    """Check if a value can be converted to a valid ObjectId."""
    try:
        PyObjectId._validate_object_id(value)
        return True
    except ValueError:
        return False


def str_to_object_id(value: str) -> PyObjectId:
    """Convert string to ObjectId with validation."""
    return PyObjectId._validate_object_id(value)


# Type alias for easier imports
ObjectIdType = PyObjectId

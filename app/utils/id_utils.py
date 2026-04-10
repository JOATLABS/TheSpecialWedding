"""
ID Type Utilities

Standardizes MongoDB ID handling across the codebase.
All IDs should be strings at the API boundary and ObjectIds only when querying MongoDB.

Pattern: Use to_object_id() when querying, to_str_id() when returning to API.
"""

import logging
from typing import Any, Optional, Union

from bson import ObjectId
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def to_object_id(id_str: Union[str, ObjectId], field_name: str = "id") -> ObjectId:
    """
    Convert a string ID to ObjectId for MongoDB queries.

    Args:
        id_str: String representation of ObjectId or already-ObjectId
        field_name: Field name for error reporting

    Returns:
        ObjectId instance for database queries

    Raises:
        HTTPException: 400 if invalid format
    """
    # If already ObjectId, return as-is
    if isinstance(id_str, ObjectId):
        return id_str

    # Convert string to ObjectId
    if isinstance(id_str, str):
        try:
            return ObjectId(id_str)
        except Exception as e:
            logger.error(
                f"Failed to convert {field_name} to ObjectId: {id_str}, error: {e}"
            )
            raise HTTPException(
                status_code=400, detail=f"Invalid {field_name}: {id_str}"
            )

    # Unexpected type
    raise HTTPException(
        status_code=400, detail=f"Invalid {field_name} type: {type(id_str).__name__}"
    )


def to_str_id(obj: Union[ObjectId, str, dict, Any]) -> str:
    """
    Convert an ObjectId, dict with _id field, or any object to string ID.

    Args:
        obj: ObjectId, string, dict with '_id' key, or object with '_id' attribute

    Returns:
        String representation of ID
    """
    if isinstance(obj, dict):
        # Try _id first (MongoDB standard), then id (custom field)
        _id = obj.get("_id") or obj.get("id")
        return str(_id) if _id else ""

    if isinstance(obj, str):
        return obj

    if isinstance(obj, ObjectId):
        return str(obj)

    # Try to get _id attribute
    if hasattr(obj, "_id"):
        return str(obj._id)

    # Fallback: convert to string
    return str(obj) if obj else ""


def normalize_doc_id(doc: dict) -> dict:
    """
    Normalize MongoDB document ID format.

    Converts _id ObjectId to string 'id' field for API responses.
    Keeps _id unchanged for backward compatibility with any code that relies on it.

    Args:
        doc: MongoDB document dict

    Returns:
        Document with 'id' field set to string representation of _id
    """
    if not doc:
        return doc

    if "_id" in doc:
        # Add string version as 'id' field
        doc["id"] = str(doc["_id"])

    return doc


def normalize_list_doc_ids(docs: list) -> list:
    """
    Normalize IDs for a list of MongoDB documents.

    Args:
        docs: List of MongoDB document dicts

    Returns:
        List of documents with normalized IDs
    """
    return [normalize_doc_id(doc) for doc in docs]


def validate_object_id(id_str: str, field_name: str = "id") -> bool:
    """
    Validate if a string is a valid ObjectId format without raising exception.

    Args:
        id_str: String to validate
        field_name: Field name for logging (optional)

    Returns:
        True if valid ObjectId format, False otherwise
    """
    try:
        ObjectId(id_str)
        return True
    except Exception:
        return False


def extract_id_from_doc(doc: dict) -> Optional[str]:
    """
    Safely extract string ID from a document, trying multiple key names.

    Args:
        doc: Document dict

    Returns:
        String ID or None if not found
    """
    if not doc:
        return None

    # Try common ID field names in order
    for key in ["_id", "id", "Id", "ID"]:
        if key in doc:
            value = doc[key]
            if value:
                return str(value)

    return None


def compare_ids(id1: Union[str, ObjectId], id2: Union[str, ObjectId]) -> bool:
    """
    Safely compare two IDs regardless of their types.

    Normalizes both to strings for comparison to avoid ObjectId vs str mismatches.

    Args:
        id1: First ID (string or ObjectId)
        id2: Second ID (string or ObjectId)

    Returns:
        True if IDs represent the same value, False otherwise
    """
    try:
        str1 = str(id1)
        str2 = str(id2)
        return str1 == str2
    except Exception:
        return False

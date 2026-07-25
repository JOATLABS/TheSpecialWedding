"""
Utility functions for serializing MongoDB documents and other data structures
"""

from datetime import datetime
from typing import Any

from bson import ObjectId


def serialize_mongo_doc(doc: Any) -> Any:
    """
    Recursively serialize MongoDB documents to JSON-compatible format

    Args:
        doc: MongoDB document or any data structure

    Returns:
        JSON-serializable version of the document
    """
    if doc is None:
        return None

    if isinstance(doc, ObjectId):
        return str(doc)

    if isinstance(doc, datetime):
        return doc.isoformat()

    if isinstance(doc, dict):
        return {key: serialize_mongo_doc(value) for key, value in doc.items()}

    if isinstance(doc, list):
        return [serialize_mongo_doc(item) for item in doc]

    if isinstance(doc, tuple):
        return tuple(serialize_mongo_doc(item) for item in doc)

    # For all other types (str, int, float, bool, etc.), return as-is
    return doc


def serialize_mongo_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Serialize a list of MongoDB documents

    Args:
        docs: List of MongoDB documents

    Returns:
        List of JSON-serializable documents
    """
    return [serialize_mongo_doc(doc) for doc in docs]


def prepare_for_json_response(data: Any) -> Any:
    """
    Prepare any data structure for JSON response
    This is an alias for serialize_mongo_doc for better readability

    Args:
        data: Any data structure that might contain MongoDB ObjectIds or datetime objects

    Returns:
        JSON-serializable version of the data
    """
    return serialize_mongo_doc(data)

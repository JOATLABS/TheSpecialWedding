"""
Unit tests for ID standardization utilities.

Tests the core functions in app/utils/id_utils.py to ensure
consistent ObjectId ↔ string conversion across the platform.
"""

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.utils.id_utils import (
    to_object_id,
    to_str_id,
    normalize_doc_id,
    normalize_list_doc_ids,
    validate_object_id,
    extract_id_from_doc,
    compare_ids,
)


class TestToObjectId:
    """Tests for to_object_id() function."""

    def test_valid_string_to_object_id(self):
        """Valid 24-char hex string converts to ObjectId."""
        id_str = "507f1f77bcf86cd799439011"
        result = to_object_id(id_str, "test_id")
        assert isinstance(result, ObjectId)
        assert str(result) == id_str

    def test_object_id_returns_unchanged(self):
        """ObjectId input returns as-is."""
        obj_id = ObjectId()
        result = to_object_id(obj_id, "test_id")
        assert result == obj_id

    def test_invalid_string_raises_400(self):
        """Invalid ID string raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            to_object_id("not_valid", "test_id")
        assert exc_info.value.status_code == 400
        assert "Invalid test_id" in exc_info.value.detail

    def test_empty_string_raises_400(self):
        """Empty string raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            to_object_id("", "test_id")
        assert exc_info.value.status_code == 400

    def test_wrong_length_string_raises_400(self):
        """String of wrong length raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            to_object_id("507f1f77bcf86cd", "test_id")
        assert exc_info.value.status_code == 400

    def test_non_hex_chars_raises_400(self):
        """String with non-hex characters raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            to_object_id("507f1f77bcf86cd799439zz0", "test_id")
        assert exc_info.value.status_code == 400


class TestToStrId:
    """Tests for to_str_id() function."""

    def test_object_id_to_string(self):
        """ObjectId converts to 24-char hex string."""
        obj_id = ObjectId("507f1f77bcf86cd799439011")
        result = to_str_id(obj_id)
        assert result == "507f1f77bcf86cd799439011"
        assert isinstance(result, str)

    def test_string_returns_unchanged(self):
        """String input returns as-is."""
        id_str = "507f1f77bcf86cd799439011"
        result = to_str_id(id_str)
        assert result == id_str

    def test_dict_with_underscore_id(self):
        """Dict with _id key extracts ID as string."""
        obj_id = ObjectId()
        doc = {"_id": obj_id, "name": "test"}
        result = to_str_id(doc)
        assert result == str(obj_id)

    def test_dict_with_id_key(self):
        """Dict with id key (fallback) extracts ID as string."""
        doc = {"id": "507f1f77bcf86cd799439011"}
        result = to_str_id(doc)
        assert result == "507f1f77bcf86cd799439011"

    def test_dict_with_both_keys_prefers_underscore(self):
        """Dict with both _id and id prefers _id."""
        doc = {"_id": ObjectId("507f1f77bcf86cd799439011"), "id": "different"}
        result = to_str_id(doc)
        assert result == "507f1f77bcf86cd799439011"

    def test_empty_dict_returns_empty_string(self):
        """Empty dict returns empty string."""
        result = to_str_id({})
        assert result == ""

    def test_none_returns_empty_string(self):
        """None input returns empty string."""
        result = to_str_id(None)
        assert result == ""


class TestNormalizeDocId:
    """Tests for normalize_doc_id() function."""

    def test_adds_id_field_from_underscore_id(self):
        """Adds 'id' field as string from '_id' ObjectId."""
        obj_id = ObjectId("507f1f77bcf86cd799439011")
        doc = {"_id": obj_id, "name": "test"}
        result = normalize_doc_id(doc)
        assert result["id"] == "507f1f77bcf86cd799439011"
        assert isinstance(result["id"], str)

    def test_preserves_original_underscore_id(self):
        """Keeps original _id ObjectId unchanged."""
        obj_id = ObjectId("507f1f77bcf86cd799439011")
        doc = {"_id": obj_id, "name": "test"}
        normalize_doc_id(doc)
        assert doc["_id"] == obj_id

    def test_overwrites_existing_id_field(self):
        """Overwrites existing 'id' field if different."""
        obj_id = ObjectId("507f1f77bcf86cd799439011")
        doc = {"_id": obj_id, "id": "old_value"}
        normalize_doc_id(doc)
        assert doc["id"] == "507f1f77bcf86cd799439011"

    def test_none_input_returns_none(self):
        """None input returns None safely."""
        result = normalize_doc_id(None)
        assert result is None


class TestNormalizeListDocIds:
    """Tests for normalize_list_doc_ids() function."""

    def test_normalizes_multiple_documents(self):
        """Normalizes multiple documents in a list."""
        docs = [
            {"_id": ObjectId("507f1f77bcf86cd799439011"), "name": "test1"},
            {"_id": ObjectId("507f1f77bcf86cd799439012"), "name": "test2"},
        ]
        result = normalize_list_doc_ids(docs)
        assert result[0]["id"] == "507f1f77bcf86cd799439011"
        assert result[1]["id"] == "507f1f77bcf86cd799439012"

    def test_empty_list_returns_empty_list(self):
        """Empty list returns empty list."""
        result = normalize_list_doc_ids([])
        assert result == []


class TestValidateObjectId:
    """Tests for validate_object_id() function."""

    def test_valid_string_returns_true(self):
        """Valid ObjectId string returns True."""
        assert validate_object_id("507f1f77bcf86cd799439011") is True

    def test_invalid_string_returns_false(self):
        """Invalid string returns False (no exception)."""
        assert validate_object_id("not_valid") is False

    def test_empty_string_returns_false(self):
        """Empty string returns False."""
        assert validate_object_id("") is False

    def test_wrong_length_returns_false(self):
        """String of wrong length returns False."""
        assert validate_object_id("507f1f77bcf86cd") is False


class TestExtractIdFromDoc:
    """Tests for extract_id_from_doc() function."""

    def test_extracts_from_underscore_id(self):
        """Extracts ID from _id field."""
        doc = {"_id": ObjectId("507f1f77bcf86cd799439011")}
        result = extract_id_from_doc(doc)
        assert result == "507f1f77bcf86cd799439011"

    def test_extracts_from_id(self):
        """Extracts ID from id field if _id missing."""
        doc = {"id": "507f1f77bcf86cd799439011"}
        result = extract_id_from_doc(doc)
        assert result == "507f1f77bcf86cd799439011"

    def test_prefers_underscore_id(self):
        """Prefers _id over other variants."""
        doc = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "id": "different",
            "Id": "also_different",
        }
        result = extract_id_from_doc(doc)
        assert result == "507f1f77bcf86cd799439011"

    def test_none_input_returns_none(self):
        """None input returns None."""
        result = extract_id_from_doc(None)
        assert result is None

    def test_no_id_field_returns_none(self):
        """Document with no ID field returns None."""
        result = extract_id_from_doc({"name": "test"})
        assert result is None


class TestCompareIds:
    """Tests for compare_ids() function."""

    def test_equal_string_and_object_id(self):
        """Comparing string and ObjectId returns True if equal."""
        id_str = "507f1f77bcf86cd799439011"
        obj_id = ObjectId(id_str)
        assert compare_ids(id_str, obj_id) is True

    def test_equal_strings(self):
        """Comparing equal strings returns True."""
        id_str = "507f1f77bcf86cd799439011"
        assert compare_ids(id_str, id_str) is True

    def test_equal_object_ids(self):
        """Comparing equal ObjectIds returns True."""
        obj_id = ObjectId("507f1f77bcf86cd799439011")
        assert compare_ids(obj_id, obj_id) is True

    def test_different_ids_returns_false(self):
        """Different IDs return False."""
        id_str1 = "507f1f77bcf86cd799439011"
        id_str2 = "507f1f77bcf86cd799439012"
        assert compare_ids(id_str1, id_str2) is False

    def test_invalid_id_returns_false(self):
        """Invalid ID returns False (no exception)."""
        assert compare_ids("507f1f77bcf86cd799439011", "not_valid") is False

    def test_none_values_return_false(self):
        """None values return False gracefully."""
        assert compare_ids(None, "507f1f77bcf86cd799439011") is False
        assert compare_ids("507f1f77bcf86cd799439011", None) is False


class TestIntegrationScenarios:
    """Integration tests for common real-world scenarios."""

    def test_insert_and_retrieve_cycle(self):
        """Test insert ID → convert to string → normalize → compare."""
        # Simulate insert_one() return
        inserted_id = ObjectId()

        # Convert to string for API response
        id_str = to_str_id(inserted_id)

        # Create document with ObjectId
        doc = {"_id": inserted_id, "name": "test"}

        # Normalize for API response
        normalize_doc_id(doc)
        doc.pop("_id")

        # Verify the API response has string ID
        assert doc["id"] == id_str
        assert isinstance(doc["id"], str)

    def test_query_with_comparison(self):
        """Test converting API input ID for query + comparison."""
        # API receives string ID
        api_input_id = "507f1f77bcf86cd799439011"

        # Convert for MongoDB query
        query_id = to_object_id(api_input_id, "user_id")

        # Simulate database document
        doc = {"_id": ObjectId(api_input_id), "name": "user"}

        # Compare IDs regardless of type
        assert compare_ids(doc["_id"], api_input_id) is True

    def test_batch_list_response(self):
        """Test normalizing list of documents for API response."""
        # Simulate MongoDB result
        docs = [
            {"_id": ObjectId(), "name": "user1", "email": "user1@example.com"},
            {"_id": ObjectId(), "name": "user2", "email": "user2@example.com"},
        ]

        # Normalize all for API response
        normalized = normalize_list_doc_ids(docs)
        for doc in normalized:
            doc.pop("_id")

        # Verify all have string IDs
        assert all(isinstance(doc["id"], str) for doc in normalized)
        assert len(normalized) == 2

# ID Utils - Developer Quick Reference

## Import
```python
from app.utils.id_utils import to_object_id, to_str_id, normalize_doc_id, compare_ids
```

## Common Patterns

### 1. Converting String ID to ObjectId (for MongoDB queries)
```python
# When receiving ID from API
user_id_str = request.user_id  # "507f1f77bcf86cd799439011"

# Convert for MongoDB query
user_id = to_object_id(user_id_str, "user_id")  # ObjectId('507f1f77bcf86cd799439011')
user = await users_collection.find_one({"_id": user_id})
```

**Why?** MongoDB `_id` fields are ObjectId type. Passing string causes silent failures.

### 2. Returning Document with String ID (for API responses)
```python
# After fetching from MongoDB
user = await users_collection.find_one({"_id": user_id})
# user["_id"] is ObjectId('507f1f77bcf86cd799439011')

# Normalize for JSON response
normalize_doc_id(user)
# user now has: "id": "507f1f77bcf86cd799439011", "_id": ObjectId(...)

user.pop("_id", None)  # Remove MongoDB's _id
return user  # API gets {"id": "507f1f77bcf86cd799439011", ...}
```

**Why?** API clients expect string IDs in JSON, not serialized ObjectIds.

### 3. Batch Normalizing List Results
```python
guests = await guests_collection.find({"wedding_id": wedding_id}).to_list(length=None)

# Option A: Normalize each individually
for guest in guests:
    normalize_doc_id(guest)
    guest.pop("_id", None)

# Option B: Use batch function
from app.utils.id_utils import normalize_list_doc_ids
guests = normalize_list_doc_ids(guests)
```

### 4. Safe ID Comparison
```python
# Bad (can fail if types differ):
if guest["_id"] == user_id_str:
    # This silently fails if guest["_id"] is ObjectId and user_id_str is str

# Good:
if compare_ids(guest["_id"], user_id_str):
    # Always works, safe type handling
```

### 5. Extracting ID from Document (flexible field names)
```python
# Works even if you don't know field name:
id_str = extract_id_from_doc(doc)  # Tries "_id", "id", "Id", "ID"

# Useful for:
# - Migrating data with inconsistent ID fields
# - Working with responses from different APIs
# - Generic document processing
```

### 6. Validating ID Format (without exception)
```python
# For optional validation or logging:
if validate_object_id(user_id):
    # ID is valid format
    user = await users_collection.find_one({"_id": to_object_id(user_id, "user_id")})
else:
    # ID format invalid, log instead of crashing
    logger.warning(f"Invalid user_id format: {user_id}")
```

## Error Handling

### to_object_id Errors
```python
try:
    obj_id = to_object_id(user_id, "user_id")
except HTTPException as e:
    # e.status_code = 400
    # e.detail = "Invalid user_id: invalid_string"
    # Already formatted for FastAPI response
    raise
```

### to_str_id Error Handling
```python
# to_str_id never raises exceptions
# Returns "" for None/missing values
id_str = to_str_id(doc["_id"])  # Always safe
id_str = to_str_id(None)  # Returns ""
```

## Common Mistakes to Avoid

### ❌ Wrong: Mixing types in queries
```python
# This fails silently if guest_id is str:
guests = await guests_collection.find({"guest_id": guest_id})  # May be ObjectId or str

# Right:
guest_id = to_object_id(guest_id, "guest_id")
guests = await guests_collection.find({"guest_id": guest_id})
```

### ❌ Wrong: Returning ObjectId to API
```python
return {"guest_id": guest["_id"]}  # ObjectId doesn't JSON serialize well

# Right:
normalize_doc_id(guest)
return {"guest_id": guest["id"]}  # String serializes cleanly
```

### ❌ Wrong: Forgetting to convert after insert
```python
result = await guests_collection.insert_one(doc)
return {"id": result.inserted_id}  # Returns ObjectId representation

# Right:
result = await guests_collection.insert_one(doc)
return {"id": to_str_id(result.inserted_id)}  # Returns "507f1f77bcf86cd799439011"
```

## PyObjectId Compatibility

If using PyObjectId (in budget_service, etc.):

```python
from app.utils.pydantic_objectid import PyObjectId

# to_object_id returns standard bson.ObjectId
obj_id = to_object_id(id_str, "category_id")

# Convert to PyObjectId if needed
py_obj_id = PyObjectId(obj_id)
```

## Testing Examples

```python
import pytest
from bson import ObjectId
from app.utils.id_utils import to_object_id, to_str_id, normalize_doc_id

def test_to_object_id_valid():
    id_str = "507f1f77bcf86cd799439011"
    obj_id = to_object_id(id_str, "test_id")
    assert isinstance(obj_id, ObjectId)
    assert str(obj_id) == id_str

def test_to_object_id_invalid():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        to_object_id("not_a_valid_id", "test_id")
    assert exc_info.value.status_code == 400

def test_normalize_doc_id():
    obj_id = ObjectId()
    doc = {"_id": obj_id, "name": "test"}
    normalize_doc_id(doc)
    assert doc["id"] == str(obj_id)
    assert doc["_id"] == obj_id  # Keeps original
```

## Performance Notes

- `to_object_id()`: O(1) - simple string validation and conversion
- `to_str_id()`: O(1) - simple string conversion
- `normalize_doc_id()`: O(1) - dictionary key assignment
- `compare_ids()`: O(1) - string comparison
- No database queries performed
- Safe for hot paths (no N+1 concerns)

## Related Files

- **Main utility**: `/app/utils/id_utils.py`
- **Usage examples**: `/app/services/guest_service.py` (best practices)
- **Full documentation**: `/ID_STANDARDIZATION_SUMMARY.md`

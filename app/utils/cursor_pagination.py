"""
Cursor-Based Pagination Utility for MongoDB

Provides a scalable cursor-based pagination system that uses MongoDB document IDs
and sort field values as cursor markers. This avoids the performance issues of
offset-based pagination at large dataset sizes.

Cursors are Base64-encoded JSON containing both _id and the sort field value,
allowing the server to reconstruct exact position in the result set without
scanning skipped documents.

Usage:
    from app.utils.cursor_pagination import cursor_paginate, CursorPage

    @app.get("/items", response_model=CursorPage[ItemSchema])
    async def list_items(
        db: Motor,
        cursor: Optional[str] = validated_cursor(),
        limit: int = validated_cursor_limit(),
        sort_direction: int = 1
    ):
        results, next_cursor, has_more = await cursor_paginate(
            collection=db.items,
            filter_dict={},
            sort_field="created_at",
            limit=limit,
            cursor=cursor,
            sort_direction=sort_direction
        )
        return CursorPage(
            items=results,
            cursor=next_cursor,
            has_more=has_more
        )
"""

import base64
import logging
from datetime import datetime
from typing import Any, Generic, List, Optional, Tuple, TypeVar

from bson import ObjectId
from fastapi import HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    """
    Standardized cursor-based paginated response.

    Attributes:
        items: List of result items
        cursor: Next cursor for fetching the next page (None if no more items)
        has_more: Boolean indicating if more items exist beyond this page
    """

    items: List[T]
    cursor: Optional[str] = None
    has_more: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CursorData(BaseModel):
    """Internal model for cursor payload."""

    id: str  # MongoDB ObjectId as string
    ts: str  # Sort field value as string (ISO format for dates, or value as string)


def encode_cursor(object_id: ObjectId, sort_value: Any) -> str:
    """
    Encode a cursor from MongoDB ObjectId and sort field value.

    Args:
        object_id: MongoDB document _id
        sort_value: Value of the sort field (will be converted to string)

    Returns:
        Base64-encoded cursor string

    Raises:
        ValueError: If encoding fails
    """
    try:
        # Convert sort_value to string representation
        if isinstance(sort_value, datetime):
            ts = sort_value.isoformat()
        elif isinstance(sort_value, ObjectId):
            ts = str(sort_value)
        else:
            ts = str(sort_value)

        cursor_data = CursorData(id=str(object_id), ts=ts)

        cursor_json = cursor_data.model_dump_json()
        cursor_bytes = cursor_json.encode("utf-8")
        encoded = base64.b64encode(cursor_bytes).decode("utf-8")

        logger.debug(f"Encoded cursor: {encoded}")
        return encoded
    except Exception as e:
        logger.error(f"Failed to encode cursor: {e}")
        raise ValueError(f"Cursor encoding failed: {e}")


def decode_cursor(cursor: str) -> CursorData:
    """
    Decode a Base64-encoded cursor string.

    Args:
        cursor: Base64-encoded cursor string from client

    Returns:
        CursorData with id and ts fields

    Raises:
        ValueError: If cursor is invalid or decoding fails
    """
    try:
        cursor_bytes = base64.b64decode(cursor.encode("utf-8"))
        cursor_json = cursor_bytes.decode("utf-8")
        cursor_data = CursorData.model_validate_json(cursor_json)
        logger.debug(f"Decoded cursor: id={cursor_data.id}, ts={cursor_data.ts}")
        return cursor_data
    except Exception as e:
        logger.error(f"Failed to decode cursor: {e}")
        raise ValueError(f"Invalid cursor format: {e}")


def build_cursor_query(
    cursor_data: CursorData, sort_field: str, sort_direction: int = 1
) -> dict:
    """
    Build a MongoDB query filter from decoded cursor data.

    For ascending sort (sort_direction=1): Returns {sort_field: {$gt: value}, _id: {$gt: id}}
    For descending sort (sort_direction=-1): Returns {sort_field: {$lt: value}, _id: {$lt: id}}

    The compound query ensures consistent pagination even if sort_field values are duplicated.

    Args:
        cursor_data: Decoded cursor data
        sort_field: Name of the sort field
        sort_direction: 1 for ascending, -1 for descending

    Returns:
        MongoDB filter dict
    """
    # Reconstruct the sort value - try to detect type
    sort_value = cursor_data.ts

    # Try to parse as ObjectId if it looks like one
    try:
        if len(sort_value) == 24 and all(
            c in "0123456789abcdef" for c in sort_value.lower()
        ):
            sort_value = ObjectId(sort_value)
    except Exception:
        pass

    # Try to parse as ISO datetime if it contains T
    if isinstance(sort_value, str) and "T" in sort_value:
        try:
            sort_value = datetime.fromisoformat(sort_value.replace("Z", "+00:00"))
        except Exception:
            pass

    object_id = ObjectId(cursor_data.id)

    if sort_direction == 1:
        # Ascending: get items where sort_field > cursor value
        return {
            "$or": [
                {sort_field: {"$gt": sort_value}},
                {sort_field: sort_value, "_id": {"$gt": object_id}},
            ]
        }
    else:
        # Descending: get items where sort_field < cursor value
        return {
            "$or": [
                {sort_field: {"$lt": sort_value}},
                {sort_field: sort_value, "_id": {"$lt": object_id}},
            ]
        }


async def cursor_paginate(
    collection: AsyncIOMotorCollection,
    filter_dict: dict,
    sort_field: str,
    limit: int,
    cursor: Optional[str] = None,
    sort_direction: int = 1,
) -> Tuple[List[dict], Optional[str], bool]:
    """
    Perform cursor-based pagination on a MongoDB collection.

    This function:
    1. Decodes the cursor (if provided) to get the last seen document
    2. Builds a query filter that selects documents after the cursor
    3. Fetches limit+1 documents to determine if more exist
    4. Encodes the next cursor from the last fetched document
    5. Returns results, next_cursor, and has_more flag

    Args:
        collection: Motor AsyncIOMotorCollection instance
        filter_dict: Base MongoDB query filter (will be merged with cursor filter)
        sort_field: Field to sort by (must be indexed for good performance)
        limit: Number of items to return (max 100)
        cursor: Optional cursor from previous page
        sort_direction: 1 for ascending (default), -1 for descending

    Returns:
        Tuple of (results, next_cursor, has_more)
        - results: List of documents for this page
        - next_cursor: Cursor string for next page, or None if no more items
        - has_more: Boolean indicating if more items exist

    Raises:
        ValueError: If cursor is invalid or limit exceeds max
    """
    if limit > 100:
        raise ValueError("Limit cannot exceed 100")

    if limit < 1:
        raise ValueError("Limit must be at least 1")

    # Build the query filter
    query_filter = {**filter_dict}

    if cursor:
        try:
            cursor_data = decode_cursor(cursor)
            cursor_query = build_cursor_query(cursor_data, sort_field, sort_direction)
            # Use $and to safely merge cursor query with existing filter.
            # dict.update() would overwrite $or keys if filter_dict already
            # contained a $or clause, silently dropping the cursor condition.
            query_filter = {"$and": [query_filter, cursor_query]}
        except ValueError as e:
            logger.error(f"Invalid cursor: {e}")
            raise HTTPException(status_code=400, detail="Invalid cursor format")

    # Fetch limit + 1 to detect if more items exist
    fetch_limit = limit + 1

    sort_order = [(sort_field, sort_direction), ("_id", sort_direction)]

    results = (
        await collection.find(query_filter)
        .sort(sort_order)
        .limit(fetch_limit)
        .to_list(fetch_limit)
    )

    # Determine if more items exist
    has_more = len(results) > limit
    if has_more:
        results = results[:limit]

    next_cursor = None
    if results:
        last_doc = results[-1]
        last_id = last_doc.get("_id")
        last_sort_value = last_doc.get(sort_field)

        if last_id is not None and last_sort_value is not None:
            try:
                next_cursor = encode_cursor(last_id, last_sort_value)
            except ValueError as e:
                logger.error(f"Failed to encode next cursor: {e}")

    return results, next_cursor, has_more


def validated_cursor(
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
) -> Optional[str]:
    """
    FastAPI dependency to validate and sanitize cursor parameter.

    Performs basic format validation without decoding (to avoid exposing
    decoding errors to clients). Full validation happens in cursor_paginate().

    Args:
        cursor: Optional cursor string from query parameter

    Returns:
        Validated cursor string or None

    Raises:
        HTTPException: If cursor format is obviously invalid
    """
    if cursor is None:
        return None

    if not isinstance(cursor, str):
        raise HTTPException(status_code=400, detail="Cursor must be a string")

    # Basic length check - Base64 encoded cursors should be reasonable length
    if len(cursor) > 500:
        raise HTTPException(status_code=400, detail="Cursor string too long")

    if len(cursor) < 10:
        raise HTTPException(status_code=400, detail="Cursor string too short")

    try:
        base64.b64decode(cursor, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Cursor must be valid Base64")

    return cursor


def validated_cursor_limit(
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
) -> int:
    """
    FastAPI dependency to validate cursor pagination limit.

    Args:
        limit: Items per page (default 20, min 1, max 100)

    Returns:
        Validated limit

    Raises:
        HTTPException: If limit is out of valid range (though FastAPI Query validates this)
    """
    return limit

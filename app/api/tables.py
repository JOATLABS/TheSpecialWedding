from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any
from datetime import datetime
from bson import ObjectId

from app.models.table import TableModel
from app.core.database import mongo
from app.dependencies.auth import get_current_user

router = APIRouter()

@router.get("/tables/{wedding_id}", response_model=List[Dict[str, Any]])
async def get_tables(wedding_id: str, current_user: dict = Depends(get_current_user)):
    db = mongo.db
    tables = await db.tables.find({"wedding_id": wedding_id}).to_list(length=100)

    # Convert ObjectId to string
    for table in tables:
        table["id"] = str(table["_id"])
        del table["_id"]

    return tables

@router.post("/tables", response_model=Dict[str, Any])
async def create_table(table: TableModel, current_user: dict = Depends(get_current_user)):
    db = mongo.db

    table_dict = table.model_dump()
    table_dict["created_at"] = datetime.utcnow()
    table_dict["updated_at"] = datetime.utcnow()

    result = await db.tables.insert_one(table_dict)
    table_dict["id"] = str(result.inserted_id)
    del table_dict["_id"]

    return table_dict

@router.put("/tables/{table_id}", response_model=Dict[str, Any])
async def update_table(table_id: str, table_update: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    db = mongo.db

    # Remove immutable fields if present
    if "_id" in table_update:
        del table_update["_id"]
    if "wedding_id" in table_update:
        del table_update["wedding_id"]

    table_update["updated_at"] = datetime.utcnow()

    try:
        result = await db.tables.update_one(
            {"_id": ObjectId(table_id)},
            {"$set": table_update}
        )
    except Exception:
         raise HTTPException(status_code=400, detail="Invalid table ID format")

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Table not found")

    updated_table = await db.tables.find_one({"_id": ObjectId(table_id)})
    updated_table["id"] = str(updated_table["_id"])
    del updated_table["_id"]

    return updated_table

@router.delete("/tables/{table_id}")
async def delete_table(table_id: str, current_user: dict = Depends(get_current_user)):
    db = mongo.db

    try:
        # First, unassign guests from this table
        await db.guests.update_many(
            {"table_id": table_id},
            {"$set": {"table_id": None}}
        )

        # Then delete the table
        result = await db.tables.delete_one({"_id": ObjectId(table_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid table ID format")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Table not found")

    return {"message": "Table deleted successfully"}

@router.post("/tables/assign")
async def assign_guests(
    assignment: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Bulk assign guests to a table.
    Body format: {"table_id": "xyz", "guest_ids": ["abc", "def"]}
    To unassign, send table_id as null.
    """
    db = mongo.db

    table_id = assignment.get("table_id")
    guest_ids = assignment.get("guest_ids", [])

    if not guest_ids:
        return {"message": "No guests provided"}

    # Convert string IDs to ObjectIds if necessary (depending on how guest IDs are stored)
    # Based on other files, guest IDs seem to be strings (often ObjectId strings)
    # We'll treat them as strings for the query filter if they are stored as strings in guest collection
    # Looking at GuestModel, id is usually _id which is ObjectId.

    # Let's check how guest IDs are usually handled.
    # In admin/guests/page.tsx, we see guests have _id.

    try:
        object_ids = [ObjectId(gid) for gid in guest_ids]

        await db.guests.update_many(
            {"_id": {"$in": object_ids}},
            {"$set": {"table_id": table_id}}
        )
    except Exception:
        # Fallback if IDs are stored as strings or invalid ObjectId
        await db.guests.update_many(
            {"_id": {"$in": guest_ids}},
            {"$set": {"table_id": table_id}}
        )

    return {"message": "Guests assigned successfully"}

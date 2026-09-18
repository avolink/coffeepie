from bson import ObjectId
from datetime import datetime
from pymongo import ReturnDocument
from app.services.db import db

terminals = db.get_collection("terminals")

async def create_terminal(data: dict) -> dict:
    # Ensure multi-assignment lists exist
    data.setdefault("userIDs", [])
    data.setdefault("companyIDs", [])
    data.setdefault("status", "inactive")
    data.setdefault("createdAt", datetime.utcnow())
    data.setdefault("updatedAt", datetime.utcnow())
    result = await terminals.insert_one(data)
    data["_id"] = result.inserted_id
    return data

async def get_terminal(terminal_id: str) -> dict | None:
    return await terminals.find_one({"_id": ObjectId(terminal_id)})

async def list_terminals() -> list[dict]:
    cursor = terminals.find({})
    return await cursor.to_list(length=None)

async def update_terminal(terminal_id: str, update_data: dict) -> dict | None:
    update_data["updatedAt"] = datetime.utcnow()
    return await terminals.find_one_and_update(
        {"_id": ObjectId(terminal_id)},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )

async def delete_terminal(terminal_id: str) -> bool:
    result = await terminals.delete_one({"_id": ObjectId(terminal_id)})
    return result.deleted_count == 1

async def get_terminal_by_deviceID(deviceID: str) -> dict | None:
    """Fetch a terminal document using its unique deviceID."""
    return await terminals.find_one({"deviceID": deviceID})

async def update_terminal_by_deviceID(deviceID: str, update_data: dict) -> dict | None:
    """Update terminal fields based on its deviceID."""
    update_data["updatedAt"] = datetime.utcnow()
    return await terminals.find_one_and_update(
        {"deviceID": deviceID},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )

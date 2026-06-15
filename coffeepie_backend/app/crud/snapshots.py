from bson import ObjectId
from datetime import datetime
from pymongo import ReturnDocument
from app.services.db import db

snapshots = db.get_collection("snapshots")

async def create_snapshot(snapshot_data: dict) -> dict:
    snapshot_data.setdefault("createdAt", datetime.utcnow())
    result = await snapshots.insert_one(snapshot_data)
    snapshot_data["_id"] = result.inserted_id
    return snapshot_data

async def get_snapshot(snapshot_id: str) -> dict | None:
    return await snapshots.find_one({"_id": ObjectId(snapshot_id)})

async def list_snapshots() -> list[dict]:
    cursor = snapshots.find({})
    return await cursor.to_list(length=None)

async def update_snapshot(snapshot_id: str, update_data: dict) -> dict | None:
    return await snapshots.find_one_and_update(
        {"_id": ObjectId(snapshot_id)},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )

async def delete_snapshot(snapshot_id: str) -> bool:
    result = await snapshots.delete_one({"_id": ObjectId(snapshot_id)})
    return result.deleted_count == 1

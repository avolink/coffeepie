from bson import ObjectId
from datetime import datetime
from pymongo import ReturnDocument
from app.services.db import db

actions = db.get_collection("actions_history")

async def create_action(action_data: dict) -> dict:
    action_data.setdefault("timestamp", datetime.utcnow())
    result = await actions.insert_one(action_data)
    action_data["_id"] = result.inserted_id
    return action_data

async def get_action(action_id: str) -> dict | None:
    return await actions.find_one({"_id": ObjectId(action_id)})

async def list_actions() -> list[dict]:
    cursor = actions.find({})
    return await cursor.to_list(length=None)

async def update_action(action_id: str, update_data: dict) -> dict | None:
    update_data["timestamp"] = datetime.utcnow()
    return await actions.find_one_and_update(
        {"_id": ObjectId(action_id)},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )

async def delete_action(action_id: str) -> bool:
    result = await actions.delete_one({"_id": ObjectId(action_id)})
    return result.deleted_count == 1

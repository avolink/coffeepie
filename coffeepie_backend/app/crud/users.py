from bson import ObjectId
from datetime import datetime
from pymongo import ReturnDocument
from app.services.db import db

users = db.get_collection("users")

async def get_user(user_id: str) -> dict | None:
    return await users.find_one({"_id": ObjectId(user_id)})

async def list_users() -> list[dict]:
    cursor = users.find({})
    return await cursor.to_list(length=None)

async def update_user(user_id: str, update_data: dict) -> dict | None:
    update_data["updatedAt"] = datetime.utcnow()
    # allow new fields including createdVMs and portions
    fields = ["name", "email", "type", "companyID", "age", "city", "occupation", "createdVMs", "portions", "updatedAt"]
    to_update = {k: update_data[k] for k in fields if k in update_data}
    
    updated = await users.find_one_and_update(
        {"_id": ObjectId(user_id)}, {"$set": to_update}, return_document=ReturnDocument.AFTER
    )
    return updated

async def delete_user(user_id: str) -> bool:
    result = await users.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count == 1

async def list_users_by_company(company_id: str) -> list[dict]:
    """Return all users belonging to a specific company."""
    cursor = users.find({"companyID": company_id})
    return await cursor.to_list(length=None)

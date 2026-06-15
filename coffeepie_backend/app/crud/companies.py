from bson import ObjectId
from datetime import datetime
from pymongo import ReturnDocument
from app.services.db import db

companies = db.get_collection("companies")

async def create_company(company_data: dict) -> dict:
    # Ensure uniqueness of name, email, phone
    existing = await companies.find_one({
        "$or": [
            {"name": company_data.get("name")},
            {"email": company_data.get("email")},
            {"phone": company_data.get("phone")}
        ]
    })
    if existing:
        raise RuntimeError("Company name, email, or phone already in use")
    # set defaults for arrays and new fields
    company_data.setdefault("users", [])
    company_data.setdefault("address", None)
    company_data.setdefault("city", None)
    company_data.setdefault("numberOfterminals", 0)
    company_data.setdefault("country", None)
    company_data.setdefault("industry", None)
    company_data.setdefault("description", None)
    company_data.setdefault("location", None)
    # serialize HttpUrl fields
    if company_data.get("website") is not None:
        company_data["website"] = str(company_data["website"])
    company_data.setdefault("createdAt", datetime.utcnow())
    company_data.setdefault("updatedAt", datetime.utcnow())
    result = await companies.insert_one(company_data)
    company_data["_id"] = result.inserted_id
    return company_data

async def get_company(company_id: str) -> dict | None:
    return await companies.find_one({"_id": ObjectId(company_id)})

async def list_companies() -> list[dict]:
    cursor = companies.find({})
    return await cursor.to_list(length=None)

async def update_company(company_id: str, update_data: dict) -> dict | None:
    # serialize HttpUrl fields
    if update_data.get("website") is not None:
        update_data["website"] = str(update_data["website"])
    update_data["updatedAt"] = datetime.utcnow()
    return await companies.find_one_and_update(
        {"_id": ObjectId(company_id)},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )

async def delete_company(company_id: str) -> bool:
    result = await companies.delete_one({"_id": ObjectId(company_id)})
    return result.deleted_count == 1

async def add_user_to_company(company_id: str, user_id: str) -> dict | None:
    """Append a user ID to the company's users array and update timestamp."""
    return await companies.find_one_and_update(
        {"_id": ObjectId(company_id)},
        {"$push": {"users": user_id}, "$set": {"updatedAt": datetime.utcnow()}},
        return_document=ReturnDocument.AFTER
    )

from bson import ObjectId
from datetime import datetime
from pymongo import ReturnDocument
from app.services.db import db

vms = db.get_collection("vms")

async def create_vm(vm_data: dict) -> dict:
    vm_data.setdefault("status", "stopped")
    vm_data.setdefault("createdAt", datetime.utcnow())
    vm_data.setdefault("updatedAt", datetime.utcnow())
    result = await vms.insert_one(vm_data)
    vm_data["_id"] = result.inserted_id
    return vm_data

async def get_vm(vm_id: str) -> dict | None:
    return await vms.find_one({"_id": ObjectId(vm_id)})

async def list_vms() -> list[dict]:
    cursor = vms.find({})
    return await cursor.to_list(length=None)

async def update_vm(vm_id: str, update_data: dict) -> dict | None:
    update_data["updatedAt"] = datetime.utcnow()
    return await vms.find_one_and_update(
        {"_id": ObjectId(vm_id)},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )

async def delete_vm(vm_id: str) -> bool:
    result = await vms.delete_one({"_id": ObjectId(vm_id)})
    return result.deleted_count == 1

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.crud.companies import create_company as crud_create, get_company as crud_get, list_companies as crud_list, update_company as crud_update, delete_company as crud_delete
from app.models.company_models import CompanyCreate, CompanyUpdate, CompanyOut
from app.models.user_models import UserOut
from app.crud.users import list_users_by_company
from app.core.security import get_current_user
from datetime import datetime
from app.crud.companies import update_company as crud_update_company
router = APIRouter(prefix="/companies", tags=["companies"])

@router.post("/", response_model=CompanyOut)
async def create_company(company: CompanyCreate):
    try:
        data = company.dict(exclude_unset=True)
        result = await crud_create(data)
        return CompanyOut(**result, id=str(result["_id"]))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[CompanyOut])
async def read_companies():
    items = await crud_list()
    return [CompanyOut(**c, id=str(c["_id"])) for c in items]

@router.get("/{company_id}", response_model=CompanyOut)
async def read_company(company_id: str):
    c = await crud_get(company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    return CompanyOut(**c, id=str(c["_id"]))

@router.put("/{company_id}", response_model=CompanyOut)
async def update_company(company_id: str, company: CompanyUpdate):
    try:
        updated = await crud_update(company_id, company.dict(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=404, detail="Company not found or no changes")
        return CompanyOut(**updated, id=str(updated["_id"]))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{company_id}", response_model=CompanyOut)
async def patch_company(
    company_id: str,
    company: CompanyUpdate
):
    """Partial update of company fields."""
    try:
        data = company.dict(exclude_unset=True)
        updated = await crud_update(company_id, data)
        if not updated:
            raise HTTPException(status_code=404, detail="Company not found or no changes")
        return CompanyOut(**updated, id=str(updated["_id"]))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{company_id}")
async def delete_company(company_id: str):
    deleted = await crud_delete(company_id)
    if not deleted:
        raise HTTPException(404, "Company not found")
    return {"deleted": True}

@router.get("/{company_id}/users", response_model=List[UserOut])
async def read_company_users(company_id: str):
    # ensure the company exists
    company = await crud_get(company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    # fetch users belonging to this company
    users = await list_users_by_company(company_id)
    # default missing names
    output = []
    for u in users:
        u.setdefault("name", "")
        # ensure fields required by UserOut
        u.setdefault("createdVMs", [])
        u.setdefault("createdAt", datetime.utcnow())
        u.setdefault("updatedAt", datetime.utcnow())
        output.append(UserOut(**u, id=str(u["_id"])) )
    return output
@router.patch("/company/{company_id}/portions")
async def update_company_portions(company_id: str, portions: float):
    """Add the given 'portions' value to the company's current portions."""
    company = await crud_get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    new_portions = float(company.get("portions", 0)) + float(portions)
    updated = await crud_update_company(company_id, {"portions": new_portions})
    return {"id": str(updated["_id"]), "portions": updated["portions"]}
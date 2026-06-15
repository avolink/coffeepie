from fastapi import APIRouter, Depends, HTTPException
from typing import List
from bson import ObjectId
from app.services.auth_service import create_user as auth_create_user
from app.crud.users import get_user as crud_get_user, list_users as crud_list_users, update_user as crud_update_user, delete_user as crud_delete_user
from app.models.user_models import UserCreate, UserUpdate, UserOut
from app.crud.companies import add_user_to_company, get_company
from app.core.security import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserOut)
async def create_user(user: UserCreate):
    try:
        # Create user and hash password
        result = await auth_create_user(user.name, user.email, user.password)
        update_fields = {}
        # Determine type based on companyID validity
        if user.companyID:
            company = await get_company(user.companyID)
            if company:
                update_fields["companyID"] = user.companyID
                update_fields["type"] = "company"
            else:
                # invalid companyID, treat as individual
                update_fields["type"] = "individual"
        else:
            update_fields["type"] = "individual"
        # Persist additional optional fields
        if user.age is not None:
            update_fields["age"] = user.age
        if user.city is not None:
            update_fields["city"] = user.city
        if user.occupation is not None:
            update_fields["occupation"] = user.occupation
        # Update user document if any fields to set
        if update_fields:
            updated = await crud_update_user(str(result["_id"]), update_fields)
            result.update(update_fields)
        # If user belongs to a valid company, add to company users
        if update_fields.get("companyID"):
            await add_user_to_company(update_fields["companyID"], str(result["_id"]))
        return UserOut(**result, id=str(result["_id"]))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[UserOut])
async def read_users():
    users = await crud_list_users()
    out = []
    for u in users:
        u.setdefault("name", "")
        u.setdefault("createdVMs", [])
        out.append(UserOut(**u, id=str(u["_id"])) )
    return out

@router.get("/me", response_model=UserOut)
async def read_user(current_user: dict = Depends(get_current_user)):
    user = await crud_get_user(str(current_user["_id"]))
    if not user:
        raise HTTPException(404, "User not found")
    user.setdefault("name", "")
    user.setdefault("createdVMs", [])
    return UserOut(**user, id=str(user["_id"]))

@router.put("/{user_id}", response_model=UserOut)
async def update_user(user_id: str, user: UserUpdate, current=Depends(get_current_user)):
    updated = await crud_update_user(user_id, user.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(404, "User not found or no changes")
    return UserOut(**updated, id=str(updated["_id"]))

@router.delete("/{user_id}")
async def delete_user(user_id: str, current=Depends(get_current_user)):
    deleted = await crud_delete_user(user_id)
    if not deleted:
        raise HTTPException(404, "User not found")
    return {"deleted": True}

@router.get("/me/credits")
async def get_my_credits(current_user: dict = Depends(get_current_user)):
    """Get the current credits (portions) for the authenticated user or their company."""
    # If user is in a company, get company portions
    if current_user.get("companyID"):
        from app.crud.companies import get_company
        company = await get_company(current_user["companyID"])
        if not company:
            raise HTTPException(404, "Compañía no encontrada")
        return {"credits": company.get("portions", 0)}
    # Otherwise, get user's own portions
    return {"credits": current_user.get("portions", 0)}

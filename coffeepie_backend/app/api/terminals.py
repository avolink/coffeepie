from fastapi import APIRouter, HTTPException, Header
from typing import List
from app.crud.terminals import (
    create_terminal as crud_create_terminal,
    get_terminal as crud_get_terminal,
    list_terminals as crud_list_terminals,
    update_terminal as crud_update_terminal,
    delete_terminal as crud_delete_terminal,
    get_terminal_by_deviceID
)
from app.models.terminal_models import TerminalCreate, TerminalUpdate, TerminalOut
from app.services.auth_service import get_user_by_id
from app.core.security import get_current_user  


router = APIRouter(prefix="/terminals", tags=["terminals"])

@router.post("/", response_model=TerminalOut)
async def create_terminal(
    terminal: TerminalCreate,
    terminalID: str = Header(...)
):
    # derive current user from terminal device
    term = await get_terminal_by_deviceID(terminalID)
    if not term or not term.get("currentUser"):
        raise HTTPException(status_code=401, detail="Unauthorized terminal")
    user = await get_user_by_id(term["currentUser"])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user on terminal")
    data = terminal.dict(exclude_unset=True)
    # ensure only current user in userIDs
    if "userIDs" in data:
        if any(uid != str(user["_id"]) for uid in data["userIDs"]):
            raise HTTPException(403, "Cannot assign terminal to other users")
    # ensure only current company in companyIDs
    if "companyIDs" in data and user.get("companyID"):
        if any(cid != user["companyID"] for cid in data["companyIDs"]):
            raise HTTPException(403, "Cannot assign terminal to other companies")
    result = await crud_create_terminal(data)
    return TerminalOut(**result, id=str(result["_id"]))

@router.get("/", response_model=List[TerminalOut])
async def read_terminals():
  
    
    items = await crud_list_terminals()
   
    return  [TerminalOut(**c, id=str(c["_id"])) for c in items]

@router.get("/{terminal_id}", response_model=TerminalOut)
async def read_terminal(
    terminal_id: str,
    terminalID: str = Header(...)
):
    term = await get_terminal_by_deviceID(terminalID)
    if not term or not term.get("currentUser"):
        raise HTTPException(status_code=401, detail="Unauthorized terminal")
    user = await get_user_by_id(term["currentUser"])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user on terminal")
    t = await crud_get_terminal(terminal_id)
    if not t:
        raise HTTPException(404, "Terminal not found")
    # permission check
    if str(user["_id"]) not in t.get("userIDs", []) and (
       not user.get("companyID") or user["companyID"] not in t.get("companyIDs", [])
    ):
        raise HTTPException(403, "Not permitted to access this terminal")
    return TerminalOut(**t, id=str(t["_id"]))

@router.put("/{terminal_id}", response_model=TerminalOut)
async def update_terminal(
    terminal_id: str,
    terminal: TerminalUpdate,
    terminalID: str = Header(...)
):
    term = await get_terminal_by_deviceID(terminalID)
    if not term or not term.get("currentUser"):
        raise HTTPException(status_code=401, detail="Unauthorized terminal")
    user = await get_user_by_id(term["currentUser"])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user on terminal")
    t = await crud_get_terminal(terminal_id)
    if not t:
        raise HTTPException(404, "Terminal not found")
    # ownership check
    if str(user["_id"]) not in t.get("userIDs", []) and (
       not user.get("companyID") or user["companyID"] not in t.get("companyIDs", [])
    ):
        raise HTTPException(403, "Not permitted to update this terminal")
    updated = await crud_update_terminal(terminal_id, terminal.dict(exclude_unset=True))
    return TerminalOut(**updated, id=str(updated["_id"]))

@router.delete("/{terminal_id}")
async def delete_terminal(
    terminal_id: str,
    terminalID: str = Header(...)
):
    term = await get_terminal_by_deviceID(terminalID)
    if not term or not term.get("currentUser"):
        raise HTTPException(status_code=401, detail="Unauthorized terminal")
    user = await get_user_by_id(term["currentUser"])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user on terminal")
    t = await crud_get_terminal(terminal_id)
    if not t:
        raise HTTPException(404, "Terminal not found")
    if str(user["_id"]) not in t.get("userIDs", []) and (
       not user.get("companyID") or user["companyID"] not in t.get("companyIDs", [])
    ):
        raise HTTPException(403, "Not permitted to delete this terminal")
    deleted = await crud_delete_terminal(terminal_id)
    if not deleted:
        raise HTTPException(404, "Terminal not found")
    return {"deleted": True}

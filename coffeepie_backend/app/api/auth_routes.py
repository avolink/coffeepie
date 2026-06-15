from fastapi import APIRouter, HTTPException
from app.models.auth_models import CreateUserRequest, LoginRequest, ForgotPasswordRequest, Token
from app.services import auth_service
from app.services.auth_service import authenticate_user, create_access_token
from app.crud.terminals import get_terminal_by_deviceID, update_terminal_by_deviceID, create_terminal as crud_create_terminal

router = APIRouter()

@router.post("/auth/create-user")
async def create_user(request: CreateUserRequest):
    try:
        # name, email, password args
        user = await auth_service.create_user(request.name, request.email, request.password)
        return {"message": "User created successfully", "user_id": str(user["_id"]) }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/login", response_model=Token)
async def login(request: LoginRequest):
    user = await auth_service.authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access_token = create_access_token({"sub": str(user["_id"])})
    # If login came from a terminal device, mark terminal active and in use
    if request.terminalID:
        term = await get_terminal_by_deviceID(request.terminalID)
        # verify user's company for existing terminal
        cid = user.get("companyID")
        if term and cid and term.get("companyIDs") and cid not in term.get("companyIDs", []):
            raise HTTPException(status_code=403, detail="Terminal not assigned to this company")
        # prepare fields for both create and update
        user_id_str = str(user["_id"])
        update_data = {"currentUser": user_id_str, "status": "active"}
        # ensure userIDs list includes this user
        uids = term.get("userIDs", []) if term else []
        if str(user["_id"]) not in uids:
            uids.append(str(user["_id"]))
            update_data["userIDs"] = uids
        # ensure companyIDs list includes user's company
        if cid:
            # on update, retain only this user's company
            update_data["companyIDs"] = [cid]
        if term:
            # existing terminal - update
            await update_terminal_by_deviceID(request.terminalID, update_data)
        else:
            # not found - create a new terminal record
            create_data = {
                "deviceID": request.terminalID,
                "name": request.terminalID,
                **update_data
            }
            # ensure created terminal is assigned to user's company
            if cid:
                create_data["companyIDs"] = [cid]
            await crud_create_terminal(create_data)
    return {"access_token": access_token, "token_type": "bearer", "user_id": str(user["_id"])}

@router.post("/auth/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    try:
        reset_link = auth_service.generate_password_reset_link(request.email)
        return {"message": "Password reset link sent successfully", "reset_link": reset_link}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
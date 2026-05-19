from fastapi import APIRouter, HTTPException
from app.models.auth_models import CreateUserRequest, LoginRequest, ForgotPasswordRequest
from app.services import auth_service

router = APIRouter()

@router.post("/auth/create-user")
def create_user(request: CreateUserRequest):
    try:
        user = auth_service.create_user(request.email, request.password)
        return {"message": "User created successfully", "user_id": user["uid"]}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/login")
def login(request: LoginRequest):
    try:
        user = auth_service.get_user_by_email(request.email)
        if user:
            custom_token = auth_service.create_custom_token(user.uid)
            return {"message": "Login successful", "custom_token": custom_token}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    try:
        reset_link = auth_service.generate_password_reset_link(request.email)
        return {"message": "Password reset link sent successfully", "reset_link": reset_link}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
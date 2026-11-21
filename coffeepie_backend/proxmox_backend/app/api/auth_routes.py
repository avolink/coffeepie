import logging

from fastapi import APIRouter, Depends, HTTPException
from app.services.ratelimit import rate_limit
from app.models.auth_models import CreateUserRequest, LoginRequest, ForgotPasswordRequest
from app.services import auth_service

logger = logging.getLogger("coffeepie.auth")

router = APIRouter()

@router.post("/auth/create-user", dependencies=[Depends(rate_limit("register", 3, 3600))])
def create_user(request: CreateUserRequest):
    try:
        user = auth_service.create_user(request.email, request.password)
        return {"message": "User created successfully", "user_id": user["uid"]}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/login", dependencies=[Depends(rate_limit("login", 5, 60))])
def login(request: LoginRequest):
    """Verify email + password against Firebase, then mint a custom token.

    The password is checked by Firebase Auth; a token is only issued for the
    account that just proved it. Every failure returns the same 401 so the
    endpoint cannot be used to find out which emails are registered.
    """
    try:
        uid = auth_service.verify_password(request.email, request.password)
    except auth_service.AuthUnavailable:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        custom_token = auth_service.create_custom_token(uid)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    return {"message": "Login successful", "custom_token": custom_token}

@router.post("/auth/forgot-password", dependencies=[Depends(rate_limit("reset", 3, 900))])
def forgot_password(request: ForgotPasswordRequest):
    """Ask Firebase to e-mail a reset link. The link never appears in the response.

    The reply is identical whether or not the address is registered.
    """
    try:
        auth_service.send_password_reset_email(request.email)
    except Exception:
        logger.warning("password reset e-mail request failed", exc_info=True)
    return {"message": "If that address is registered, a reset link has been sent"}

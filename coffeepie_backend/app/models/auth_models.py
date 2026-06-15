from pydantic import BaseModel
from typing import Optional

class CreateUserRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str
    terminalID: Optional[str] = None  # ID of the device terminal from which user logs in

class ForgotPasswordRequest(BaseModel):
    email: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
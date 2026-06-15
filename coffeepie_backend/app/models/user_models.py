from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: EmailStr
    type: str  # "individual" | "company"
    companyID: Optional[str] = None
    age: Optional[int] = None
    city: Optional[str] = None
    occupation: Optional[str] = None
    portions: float = 0.0  # credits per minute for individual users

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    type: Optional[str]
    companyID: Optional[str]
    age: Optional[int]
    city: Optional[str]
    occupation: Optional[str]
    portions: Optional[float] = None

class UserOut(UserBase):
    id: str
    createdVMs: List[str]
    createdAt: datetime
    updatedAt: datetime

    class Config:
        orm_mode = True

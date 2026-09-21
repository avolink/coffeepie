from pydantic import BaseModel, EmailStr, HttpUrl
from typing import List, Optional
from datetime import datetime

class CompanyBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    users: List[str] = []
    address: Optional[str] = None  # physical address of the company
    city: Optional[str] = None
    numberOfterminals: int = 0  # number of terminals assigned to the company
    country: Optional[str] = None
    industry: Optional[str] = None  # industry sector
    website: Optional[HttpUrl] = None  # company website URL
    description: Optional[str] = None  # brief overview of company
    location: Optional[str] = None  # geographical location, e.g. "New York, USA"
    portions: float = 0.0  # credits per minute allocated to company users
class CompanyCreate(CompanyBase):
    # inherits all fields including new ones
    pass

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    users: Optional[List[str]] = None
    address: Optional[str] = None
    city: Optional[str] = None
    numberOfterminals: Optional[int] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[HttpUrl] = None
    description: Optional[str] = None
    location: Optional[str] = None
    portions: Optional[float] = None
class CompanyOut(CompanyBase):
    id: str
    createdAt: datetime
    updatedAt: datetime

    class Config:
        orm_mode = True

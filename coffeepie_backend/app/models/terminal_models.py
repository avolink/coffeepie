from pydantic import BaseModel
from typing import Optional, Literal, List
from datetime import datetime

class TerminalBase(BaseModel):
    deviceID: str  # unique device identifier, e.g. MAC or IP
    name: str
    userIDs: List[str] = []  # terminal assigned to multiple users
    companyIDs: List[str] = []  # terminal accessible by multiple companies
  
    status: Literal["active", "inactive"] = "inactive"
    currentUser: Optional[str] = None  # ID of user currently using the terminal

class TerminalCreate(TerminalBase):
    # inherits deviceID, name, userIDs, companyIDs, vmID, status, currentUser
    pass

class TerminalUpdate(BaseModel):
    name: Optional[str]
    userIDs: Optional[List[str]]
    companyIDs: Optional[List[str]]
 
    status: Optional[Literal["active", "inactive"]]
    currentUser: Optional[str]

class TerminalOut(TerminalBase):
    id: str
    createdAt: datetime
    updatedAt: datetime

    class Config:
        orm_mode = True

from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class ActionBase(BaseModel):
    userID: str
    vmID: str
    action: Literal["start", "stop", "reboot", "shutdown"]

class ActionCreate(ActionBase):
    pass

class ActionUpdate(BaseModel):
    action: Literal["start", "stop", "reboot", "shutdown"]

class ActionOut(ActionBase):
    id: str
    timestamp: datetime

    class Config:
        orm_mode = True

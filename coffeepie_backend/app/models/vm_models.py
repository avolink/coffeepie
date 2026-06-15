from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class Specs(BaseModel):
    cpu: int
    memory: int
    storage: int
    so: Optional[str] = None

class VMBase(BaseModel):
    name: str
    ownerID: str
    companyID: Optional[str]
    node: str  # Proxmox node where the VM resides
    status: Optional[str] = "stopped"
    specs: Specs = Specs(cpu=0, memory=0, storage=0)
    credits_for_minutes: float = 0.0  # credit rate (per minute) assigned when VM is created
    last_start_time: Optional[datetime] = None  # timestamp when VM was last started

class VMCreate(VMBase):
    pass

class VMUpdate(BaseModel):
    name: Optional[str]
    status: Optional[str]

    specs: Optional[Dict]

class VMOut(VMBase):
    id: str
    vmid: int  # include Proxmox VM ID in API output
    createdAt: datetime
    updatedAt: datetime

    class Config:
        orm_mode = True

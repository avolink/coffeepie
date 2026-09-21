from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SnapshotBase(BaseModel):
    vmid: int
    name: str
    description: Optional[str] = None
    createdAt: Optional[datetime] = None
    status: Optional[str] = "created"  # created, deleted, etc.
    node: Optional[str] = None  # Proxmox node where the VM resides
class SnapshotCreate(SnapshotBase):
    pass

class SnapshotUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class SnapshotOut(SnapshotBase):
    id: str
    class Config:
        orm_mode = True

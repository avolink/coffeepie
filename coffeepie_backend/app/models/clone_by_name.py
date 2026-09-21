from pydantic import BaseModel
from typing import Optional

class CloneByNameRequest(BaseModel):
    source_name: str
    newid: int
    name: str
    node: str
    storage: str = "local-lvm"
    full: int = 0
    ipconfig0: str = None  # New field for IP configuration
    # Optional specs to apply after clone
    cores: Optional[int] = None
    sockets: Optional[int] = None
    memory: Optional[int] = None  # in MB
    disk: Optional[str] = None   # e.g., 'ide0', 'scsi0'
    disk_size: Optional[str] = None  # e.g., '+20G' to resize disk
    credits_for_minutes: float = 0.0  # credit rate (per minute) assigned when VM is created

class CloneWithSpecsRequest(BaseModel):
    namevm: str
    source_name: str
    node: str
    storage: str = "local-lvm"
    full: int = 0
    ipconfig0: Optional[str] = None  # New field for IP configuration
    # Optional specs to apply after clone
    cores: Optional[int] = None
    sockets: Optional[int] = None
    memory: Optional[int] = None  # in MB
    disk: Optional[str] = None   # e.g., 'ide0', 'scsi0'
    disk_size: Optional[str] = None  # e.g., '+20G' to resize disk
    credits_for_minutes: float = 0.0  # credit rate (per minute) assigned when VM is created
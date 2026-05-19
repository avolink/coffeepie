from pydantic import BaseModel
from typing import Optional

class VMCreateRequest(BaseModel):
    vmid: int
    name: str
    memory: int
    net0: str
    disk: str
    ostype: str = "l26"
    storage: str
    cdrom: Optional[str] = None
    iso_path: Optional[str] = None

class CTCreateRequest(BaseModel):
    vmid: int
    template: str
    hostname: str
    rootfs: str
    net0: str
    ip_address: str
    gateway: str

class VMUpdateRequest(BaseModel):
    vmid: int
    memory: int
    cpus: int
    description: Optional[str] = None

class VMIDRequest(BaseModel):
    vmid: int

from pydantic import BaseModel

class CloneByNameRequest(BaseModel):
    source_name: str
    newid: int
    name: str
    node: str
    storage: str = "local-lvm"
    full: int = 0

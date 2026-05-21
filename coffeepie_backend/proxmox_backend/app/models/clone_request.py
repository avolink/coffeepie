from pydantic import BaseModel

class CloneRequest(BaseModel):
    template_vmid: int
    newid: int
    name: str
    full: int = 1

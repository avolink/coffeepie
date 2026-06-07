from pydantic import BaseModel
class SunshineRequest(BaseModel):
    ip: str
    pin: str
    client_name: str
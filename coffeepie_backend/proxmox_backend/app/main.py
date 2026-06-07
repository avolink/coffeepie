from fastapi import FastAPI
from app.api import proxmox_routes, auth_routes  

app = FastAPI(title="Proxmox API Proxy")

app.include_router(proxmox_routes.router)
app.include_router(auth_routes.router) 

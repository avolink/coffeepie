from fastapi import FastAPI
from app.controllers.proxmox_controller import router

app = FastAPI()

app.include_router(router)

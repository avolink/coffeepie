from fastapi import APIRouter, Depends, HTTPException
import asyncio, re
from typing import List
from app.core.security import get_current_user
from app.crud.vms import create_vm as crud_create_vm, get_vm as crud_get_vm, list_vms as crud_list_vms, update_vm as crud_update_vm, delete_vm as crud_delete_vm
from app.api.proxmox_routes import get_auth_headers
from app.services.proxmox_service import (
    validate_clone_request,
    clone_vm,
    get_vm_status,
    get_vmid_by_name,
    get_vm_config,
    stop_vm as prox_stop_vm,
    start_vm as prox_start_vm,
    shutdown_vm as prox_shutdown_vm,
    reboot_vm as prox_reboot_vm,
    delete_vm as prox_delete_vm,
    set_vm_config,
    resize_disk
)
from app.models.clone_by_name import CloneByNameRequest,CloneWithSpecsRequest
from app.models.vm_models import VMCreate, VMUpdate, VMOut
from app.crud.users import update_user as crud_update_user
from app.crud.users import get_user as _get_u, update_user as _upd_u
from app.config import PROXMOX_IP  # add PROXMOX_IP for console URL construction
import asyncio
import re
from datetime import datetime
from app.crud.companies import get_company as _get_c, update_company as _upd_c
from app.utilities.vms.vms import ensure_vm_owned, clone_vm_with_specs, update_vm_with_credits
from app.utilities.vms.create_vm import create_vm as util_create_vm
from app.utilities.vms.stop_vm import stop_vm as util_stop_vm
from app.utilities.vms.get_console_url import get_console_url as util_get_console_url
from app.utilities.vms.start_vm_route import start_vm_route as util_start_vm_route
from app.utilities.vms.delete_vm import delete_vm as util_delete_vm
from app.utilities.vms.get_vm_status_route import get_vm_status_route as util_get_vm_status_route
from app.utilities.vms.shutdown_vm_route import shutdown_vm_route as util_shutdown_vm_route
from app.utilities.vms.reboot_vm_route import reboot_vm_route as util_reboot_vm_route
from app.utilities.vms.read_my_vms import read_my_vms as util_read_my_vms

from app.utilities.vms.clone_vm import clone_vm_endpoint as util_clone_vm_endpoint
router = APIRouter(prefix="/vms", tags=["vms"])

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@router.post("/", response_model=VMOut)
async def create_vm(
    request: CloneByNameRequest,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    created = await util_create_vm(request, current_user, auth)
    return VMOut(**created, id=str(created["_id"]))

@router.get("/", response_model=List[VMOut])
async def read_vms(current=Depends(get_current_user)):
    items = await crud_list_vms()
    return [VMOut(**v, id=str(v["_id"])) for v in items]

@router.get("/me", response_model=List[VMOut])
async def read_my_vms(
    current_user: dict = Depends(get_current_user)
):
    return await util_read_my_vms(current_user)

@router.get("/{vm_id}", response_model=VMOut)
async def read_vm(vm_id: str, current=Depends(get_current_user)):
    v = await crud_get_vm(vm_id)
    if not v:
        raise HTTPException(404, "VM not found")
    return VMOut(**v, id=str(v["_id"]))

@router.put("/{vm_id}", response_model=VMOut)
async def update_vm(vm_id: str, vm: VMUpdate, current=Depends(get_current_user), auth=Depends(get_auth_headers)):
    updated = await update_vm_with_credits(vm_id, current, auth, vm.dict(exclude_unset=True), ensure_vm_owned  )
    if not updated:
        raise HTTPException(404, "VM not found or no changes")
    return VMOut(**updated, id=str(updated["_id"]))

@router.delete("/{vm_id}")
async def delete_vm(
    vm_id: str,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    result = await util_delete_vm(vm_id, current_user, auth, ensure_vm_owned)
    return result

@router.get("/{vm_id}/console-url")
async def get_console_url(
    vm_id: str,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    result = await util_get_console_url(vm_id, current_user, auth, ensure_vm_owned)
    return result

@router.get("/{vm_id}/status")
async def get_vm_status_route(
    vm_id: str,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    result = await util_get_vm_status_route(vm_id, current_user, auth, ensure_vm_owned)
    return result

@router.post("/{vm_id}/stop", response_model=VMOut)
async def stop_vm_route(
    vm_id: str,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    """Stop a VM via Proxmox if owned by the current user"""
    updated = await util_stop_vm(vm_id, current_user, auth, ensure_vm_owned)
    return VMOut(**updated, id=str(updated["_id"]))

@router.post("/{vm_id}/start", response_model=VMOut)
async def start_vm_route(
    vm_id: str,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    updated = await util_start_vm_route(vm_id, current_user, auth, ensure_vm_owned)
    return VMOut(**updated, id=str(updated["_id"]))

@router.post("/{vm_id}/shutdown", response_model=VMOut)
async def shutdown_vm_route(
    vm_id: str,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    updated = await util_shutdown_vm_route(vm_id, current_user, auth, ensure_vm_owned)
    return VMOut(**updated, id=str(updated["_id"]))

@router.post("/{vm_id}/reboot", response_model=VMOut)
async def reboot_vm_route(
    vm_id: str,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    updated = await util_reboot_vm_route(vm_id, current_user, auth, ensure_vm_owned)
    return VMOut(**updated, id=str(updated["_id"]))

@router.post("/clone-with-specs", response_model=VMOut)
async def clone_with_specs(
    request: CloneWithSpecsRequest,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    """Clone a VM by name and apply custom specs (CPU, memory, sockets, disk size)"""
    created = await clone_vm_with_specs(request, current_user, auth)
    return VMOut(**created, id=str(created["_id"]))

@router.post("/clone/{vm_id}")
async def clone_vm_endpoint(
    vm_id: str,
    current_user: dict = Depends(get_current_user),
    auth=Depends(get_auth_headers)
):
    return await util_clone_vm_endpoint(vm_id, current_user, auth)



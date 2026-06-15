import asyncio
import re
from fastapi import HTTPException
from app.services.proxmox_service import validate_clone_request, clone_vm, get_vmid_by_name, get_vm_status, get_vm_config
from app.crud.vms import create_vm as crud_create_vm
from app.crud.users import update_user as crud_update_user

def parse_disk_size(ide0):
    m = re.search(r"size=(\d+)([KMG])", ide0)
    if m:
        size = int(m.group(1))
        unit = m.group(2)
        if unit == 'G':
            return size * 1024
        elif unit == 'M':
            return size
    return 0

async def create_vm(request, current_user, auth):
    try:
        validate_clone_request(
            node=request.node,
            source_name=request.source_name,
            new_name=request.name,
            newid=request.newid,
            headers=auth["headers"],
            cookies=auth["cookies"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    template_vmid = get_vmid_by_name(request.node, request.source_name, auth["headers"], auth["cookies"])
    payload = {"newid": request.newid, "name": request.name, "full": request.full, "storage": request.storage}
    if request.full == 0:
        payload.pop("storage", None)
    try:
        proxmox_resp = clone_vm(
            request.node,
            template_vmid,
            payload,
            auth["headers"],
            auth["cookies"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxmox clone failed: {e}")
    try:
        vmid = proxmox_resp.get("data", {}).get("vmid", request.newid)
    except AttributeError:
        vmid = request.newid
    status = get_vm_status(request.node, vmid, auth["headers"], auth["cookies"])
    config = {}
    for _ in range(10):
        config = get_vm_config(request.node, vmid, auth["headers"], auth["cookies"])
        if config.get("cores") is not None and config.get("memory") is not None:
            break
        await asyncio.sleep(2)
    cpu = config.get("cores", 0)
    memory = config.get("memory", 0)
    storage = parse_disk_size(config.get("ide0", ""))
    so = config.get("ostype", None)
    vm_data = {
        "name": request.name,
        "ownerID": str(current_user["_id"]),
        "companyID": current_user.get("companyID"),
        "node": request.node,
        "status": status,
        "vmid": vmid,
        "specs": {"cpu": cpu, "memory": memory, "storage": storage, "so": so},
    }
    created = await crud_create_vm(vm_data)
    vms_list = current_user.get("createdVMs", [])
    vms_list.append(str(created["_id"]))
    await crud_update_user(str(current_user["_id"]), {"createdVMs": vms_list})
    return created

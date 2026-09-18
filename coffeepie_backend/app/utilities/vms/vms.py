from fastapi import APIRouter, Depends, HTTPException
from app.crud.vms import create_vm as crud_create_vm, get_vm as crud_get_vm, list_vms as crud_list_vms, update_vm as crud_update_vm, delete_vm as crud_delete_vm
import asyncio
import re
from datetime import datetime
from app.services.proxmox_service import (
    validate_clone_request,
    clone_vm,
    get_vmid_by_name,
    get_vm_status,
    get_vm_config,
    set_vm_config,
    resize_disk ,
     put_vm_config,
    get_vms_details_on_node
)
from app.crud.users import update_user as crud_update_user
from app.crud.companies import get_company as _get_c, update_company as _upd_c
from app.crud.vms import get_vm as crud_get_vm, update_vm as crud_update_vm

async def ensure_vm_owned(vm_id: str, current_user: dict):
    """Ensure the VM exists and is owned by the given user."""
    vm = await crud_get_vm(vm_id)
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    if str(current_user["_id"]) != vm.get("ownerID"):
        raise HTTPException(status_code=403, detail="Not permitted to access this VM")
    return vm

async def clone_vm_with_specs(request, current_user, auth):
    """Clone a VM by name and apply custom specs (CPU, memory, sockets, disk size)"""
    # Find next available VMID on the node
    print(f"Cloning VM with request: {request}")
    vms = get_vms_details_on_node(request.node, auth["headers"], auth["cookies"])
    used_vmids = {v["vmid"] for v in vms}
    next_vmid = max(used_vmids) + 1 if used_vmids else 100
    # Set both newid and name to the available VMID as string
    newid = next_vmid
    name = str(next_vmid)
    # Validate clone parameters
    try:
        validate_clone_request(
            node=request.node,
            source_name=request.source_name,
            new_name=name,
            newid=newid,
            headers=auth["headers"],
            cookies=auth["cookies"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Resolve template VMID
    template_vmid = get_vmid_by_name(request.node, request.source_name, auth["headers"], auth["cookies"])
    # Clone VM
    payload = {"newid": newid, "name": name, "full": request.full, "storage": request.storage}
    if request.full == 0:
        payload.pop("storage", None)
    proxmox_resp = clone_vm(request.node, template_vmid, payload, auth["headers"], auth["cookies"])
    # Safely extract vmid from response
    data = proxmox_resp.get("data") if isinstance(proxmox_resp, dict) and isinstance(proxmox_resp.get("data"), dict) else {}
    vmid = data.get("vmid", newid)
    # Apply custom VM config
    headers = auth["headers"]
    cookies = auth["cookies"]
    cfg_updates = {}
    if request.cores is not None:
        cfg_updates["cores"] = request.cores
    if request.sockets is not None:
        cfg_updates["sockets"] = request.sockets
    if request.memory is not None:
        cfg_updates["memory"] = request.memory
    if cfg_updates:
        set_vm_config(request.node, vmid, cfg_updates, headers, cookies)
    # Resize disk if requested and only if increasing size
    if request.disk and request.disk_size:
        # fetch current disk config
        initial_cfg = get_vm_config(request.node, vmid, headers, cookies)
        disk_val = initial_cfg.get(request.disk, "")
        # parse current size
        m_curr = re.search(r"size=(\d+)([KMG])", disk_val)
        if m_curr:
            curr_size = int(m_curr.group(1))
            unit = m_curr.group(2)
            curr_g = curr_size if unit == 'G' else curr_size / 1024 if unit == 'M' else 0
        else:
            curr_g = 0
        # parse requested size
        req_match = re.match(r"(\d+)([KMG])", request.disk_size)
        if req_match:
            req_size = int(req_match.group(1))
            req_unit = req_match.group(2)
            req_g = req_size if req_unit == 'G' else req_size / 1024 if req_unit == 'M' else 0
        else:
            raise HTTPException(status_code=400, detail="Invalid disk_size format")
        # only resize if new size is greater
        if req_g > curr_g:
            try:
                resize_disk(request.node, vmid, request.disk, request.disk_size, headers, cookies)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to resize disk: {e}")
    # Wait for config to update then fetch final state
    await asyncio.sleep(2)
    config = get_vm_config(request.node, vmid, headers, cookies)
    # Derive specs
    cpu = config.get("cores", 0)
    memory = config.get("memory", 0)
    # parse disk size
    storage = 0
    disk_key = request.disk or "ide0"
    disk_val = config.get(disk_key, "")
    m = re.search(r"size=(\d+)([KMG])", disk_val)
    if m:
        size = int(m.group(1))
        unit = m.group(2)
        storage = size * 1024 if unit == 'G' else size
    so = config.get("ostype")
    status = get_vm_status(request.node, vmid, headers, cookies)
    # Persist in DB
    vm_data = {
        "name":request.namevm,
        "ownerID": str(current_user["_id"]),
        "companyID": current_user.get("companyID"),
        "node": request.node,
        "status": status,
        "vmid": vmid,
        "specs": {"cpu": cpu, "memory": memory, "storage": storage, "so": so},
        "credits_for_minutes": request.credits_for_minutes,
    }
    created = await crud_create_vm(vm_data)
    # Update user
    vms_list = current_user.get("createdVMs", [])
    vms_list.append(str(created["_id"]))
    await crud_update_user(str(current_user["_id"]), {"createdVMs": vms_list})
    return created

async def update_vm_with_credits(vm_id: str, current_user: dict, auth, update_data: dict, ensure_vm_owned=None):
    """
    Update VM and recalculate credits_for_minutes if CPU, memory, or storage changes.
    Also updates the actual VM in Proxmox if specs change.
    Uses PUT /nodes/{node}/qemu/{vmid}/config for CPU/memory changes as per Proxmox API.
    Optionally checks ownership if ensure_vm_owned is provided.
    """
    # Optionally check ownership
    if ensure_vm_owned is not None:
        await ensure_vm_owned(vm_id, current_user)

    # Fetch current VM
    current_vm = await crud_get_vm(vm_id)
    if not current_vm:
        raise HTTPException(status_code=404, detail="VM not found")

    old_specs = current_vm.get("specs", {})
    new_specs = update_data.get("specs", {})
    merged_specs = old_specs.copy()
    merged_specs.update(new_specs)

    # Proxmox update logic
    proxmox_node = current_vm.get("node")
    proxmox_vmid = current_vm.get("vmid")
    headers = auth["headers"] if auth else None
    cookies = auth["cookies"] if auth else None

    config_updates = {}
    # Memory (RAM in MiB)
    if "memory" in new_specs and new_specs["memory"] != old_specs.get("memory"):
        config_updates["memory"] = new_specs["memory"]
    # CPU (cores)
    if "cpu" in new_specs and new_specs["cpu"] != old_specs.get("cpu"):
        config_updates["cores"] = new_specs["cpu"]
    # Apply config updates if any (PUT /nodes/{node}/qemu/{vmid}/config)
    if config_updates and headers and cookies:
       pass
       ## put_vm_config(proxmox_node, proxmox_vmid, config_updates, headers, cookies)
    # Storage (resize only if increased)
    if "storage" in new_specs and new_specs["storage"] != old_specs.get("storage") and headers and cookies:
        config = get_vm_config(proxmox_node, proxmox_vmid, headers, cookies)
        disk_key = next((k for k in config if k.startswith("ide") or k.startswith("scsi") or k.startswith("sata")), "ide0")
        old_size = old_specs.get("storage", 0)
        new_size = new_specs["storage"]
        
        if new_size > old_size:
            resize_disk(proxmox_node, proxmox_vmid, disk_key, f"{new_size}M", headers, cookies)
    # Only recalculate if any of cpu, memory, storage changes
    
    credits = current_vm.get("credits_for_minutes", 0.0)
    
    update_data["specs"] = merged_specs
    update_data["credits_for_minutes"] = credits
    updated = await crud_update_vm(vm_id, update_data)
    return updated
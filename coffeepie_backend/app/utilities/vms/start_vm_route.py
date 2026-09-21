from datetime import datetime
from fastapi import HTTPException
from app.services.proxmox_service import start_vm as prox_start_vm
from app.crud.vms import get_vm as crud_get_vm, update_vm as crud_update_vm

async def start_vm_route(vm_id, current_user, auth, ensure_vm_owned):
    """Start a VM via Proxmox if owned by the current user"""
    vm = await ensure_vm_owned(vm_id, current_user)
    node = vm.get("node")
    try:
        prox_start_vm(node, vm.get("vmid"), auth["headers"], auth["cookies"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxmox start failed: {e}")
    # record start timestamp on VM
    updated = await crud_update_vm(vm_id, {"status": "running", "last_start_time": datetime.utcnow()})
    return updated

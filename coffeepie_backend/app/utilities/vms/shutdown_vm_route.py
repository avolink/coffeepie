from fastapi import HTTPException
from app.services.proxmox_service import shutdown_vm as prox_shutdown_vm
from app.crud.vms import update_vm as crud_update_vm

async def shutdown_vm_route(vm_id, current_user, auth, ensure_vm_owned):
    vm = await ensure_vm_owned(vm_id, current_user)
    node = vm.get("node")
    try:
        prox_shutdown_vm(node, vm.get("vmid"), auth["headers"], auth["cookies"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxmox shutdown failed: {e}")
    updated = await crud_update_vm(vm_id, {"status": "stopped"})
    return updated

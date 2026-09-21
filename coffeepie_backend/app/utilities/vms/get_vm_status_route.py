from fastapi import HTTPException
from app.services.proxmox_service import get_vm_status
from app.crud.vms import update_vm as crud_update_vm

async def get_vm_status_route(vm_id, current_user, auth, ensure_vm_owned):
    vm = await ensure_vm_owned(vm_id, current_user)
    node = vm.get("node")
    try:
        status = get_vm_status(node, vm.get("vmid"), auth["headers"], auth["cookies"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxmox status fetch failed: {e}")
    await crud_update_vm(vm_id, {"status": status})
    return {"status": status}

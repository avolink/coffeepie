from fastapi import HTTPException
from app.services.proxmox_service import delete_vm as prox_delete_vm
from app.crud.vms import delete_vm as crud_delete_vm

async def delete_vm(vm_id, current_user, auth, ensure_vm_owned):
    vm = await ensure_vm_owned(vm_id, current_user)
    node = vm.get("node")
    try:
        prox_delete_vm(node, vm.get("vmid"), auth["headers"], auth["cookies"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxmox deletion failed: {e}")
    deleted = await crud_delete_vm(vm_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="VM not found")
    return {"deleted": True}

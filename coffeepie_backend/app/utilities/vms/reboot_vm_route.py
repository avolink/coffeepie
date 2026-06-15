from fastapi import HTTPException
from app.services.proxmox_service import reboot_vm as prox_reboot_vm
from app.crud.vms import update_vm as crud_update_vm

async def reboot_vm_route(vm_id, current_user, auth, ensure_vm_owned):
    vm = await ensure_vm_owned(vm_id, current_user)
    node = vm.get("node")
    if vm.get("status") != "running":
        raise HTTPException(status_code=400, detail="La máquina debe estar encendida para reiniciar.")
    try:
        prox_reboot_vm(node, vm.get("vmid"), auth["headers"], auth["cookies"])
    except Exception as e:
        # Check for specific Proxmox error about VM not running
        if "not running" in str(e).lower():
            raise HTTPException(status_code=400, detail="La máquina debe estar encendida para reiniciar.")
        raise HTTPException(status_code=500, detail=f"Proxmox reboot failed: {e}")
    updated = await crud_update_vm(vm_id, {"status": "running"})
    return updated

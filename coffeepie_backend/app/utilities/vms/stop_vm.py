from datetime import datetime
from fastapi import HTTPException
from app.services.proxmox_service import stop_vm as prox_stop_vm
from app.crud.vms import get_vm as crud_get_vm, update_vm as crud_update_vm
from app.crud.companies import get_company as _get_c, update_company as _upd_c
from app.crud.users import get_user as _get_u, update_user as _upd_u

async def stop_vm(vm_id, current_user, auth, ensure_vm_owned):
    vm = await ensure_vm_owned(vm_id, current_user)
    node = vm.get("node")
    try:
        prox_stop_vm(node, vm.get("vmid"), auth["headers"], auth["cookies"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxmox stop failed: {e}")
    # calculate credits usage
    vm_rec = await crud_get_vm(vm_id)
    start_time = vm_rec.get("last_start_time")
    credits_rate = vm_rec.get("credits_for_minutes", 0)
    credits_used = 0
    if start_time:
        minutes_used = (datetime.utcnow() - start_time).total_seconds() / 60
        credits_used = round(minutes_used * credits_rate, 2)
        if vm_rec.get("companyID"):
            comp = await _get_c(vm_rec["companyID"])
            new_portions = round(comp.get("portions", 0) - credits_used, 2)
            await _upd_c(vm_rec["companyID"], {"portions": new_portions})
        else:
            user = await _get_u(str(vm_rec.get("ownerID")))
            new_portions = user.get("portions", 0) - credits_used
            await _upd_u(str(vm_rec.get("ownerID")), {"portions": new_portions})
    updated = await crud_update_vm(vm_id, {"status": "stopped", "last_start_time": None})
    return updated

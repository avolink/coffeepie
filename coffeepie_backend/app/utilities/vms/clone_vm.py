from fastapi import APIRouter, Depends, HTTPException
from app.core.security import get_current_user
from app.api.proxmox_routes import get_auth_headers
from app.crud.vms import get_vm as crud_get_vm, create_vm as crud_create_vm
from app.services.proxmox_service import clone_vm, get_vms_details_on_node
from datetime import datetime
from bson import ObjectId




async def clone_vm_endpoint(vm_id: str, current_user: dict = Depends(get_current_user), auth=Depends(get_auth_headers)):
    # Get the original VM
    vm = await crud_get_vm(vm_id)
    if not vm:
        raise HTTPException(404, "VM no encontrada")
    # Only owner can clone
    if str(current_user["_id"]) != vm.get("ownerID"):
        raise HTTPException(403, "No tienes permiso para clonar esta máquina virtual.")
    node = vm["node"]
    template_vmid = vm["vmid"]
    # Find next available VMID in Proxmox
    try:
        vms = get_vms_details_on_node(node, auth["headers"], auth["cookies"])
        used_vmids = {v["vmid"] for v in vms}
        newid = max(used_vmids) + 1
        # Prepare payload for clone
        new_name = f"clone-{template_vmid}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        payload = {"newid": newid, "name": new_name, "full": 1}
        # Call Proxmox clone
        result = clone_vm(node, template_vmid, payload, auth["headers"], auth["cookies"])
    except Exception as e:
        msg = str(e)
        if "cannot clone TPM state while VM is running" in msg:
            raise HTTPException(400, "No se puede clonar la máquina porque está encendida y tiene TPM. Apágala antes de clonar.")
        raise HTTPException(500, f"Error al clonar la máquina: {msg}")
    # Save new VM in DB (with same owner)
    vm_data = {
        "name": new_name,
        "ownerID": vm["ownerID"],
        "companyID": vm.get("companyID"),
        "node": node,
        "status": "cloning",
        "vmid": newid,
        "specs": vm.get("specs", {}),
        "credits_for_minutes": vm.get("credits_for_minutes", 0.0),
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    created = await crud_create_vm(vm_data)
    # Convert ObjectId to string for JSON serialization
    if isinstance(created.get("_id"), ObjectId):
        created["_id"] = str(created["_id"])
    return {"proxmox": result, "db": created}

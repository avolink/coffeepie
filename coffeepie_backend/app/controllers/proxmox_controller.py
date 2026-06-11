from fastapi import APIRouter, HTTPException
from app.models.proxmox_models import VMCreateRequest, CTCreateRequest, VMUpdateRequest, VMIDRequest
from app.services.proxmox_service import clone_vm, clone_ct, create_vm, create_ct, list_vms, list_cts, update_vm, delete_vm, control_vm, control_ct, get_vm_config,get_vm_network_info

router = APIRouter()

# CRUD operations for VM and CT

@router.post("/clone-vm",description="Clone an existing VM by specifying the source VM ID, new VM ID, and name.")
def clone_vm_endpoint(vmid: int, new_vmid: int, name: str):
    try:
        result = clone_vm(vmid, new_vmid, name)
        return {"message": "VM cloned successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clone-ct", description="Clone an existing CT by specifying the source CT ID, new CT ID, and name.")
def clone_ct_endpoint(vmid: int, new_vmid: int, name: str):
    try:
        result = clone_ct(vmid, new_vmid, name)
        return {"message": "CT cloned successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-vm", description="Create a new VM with the specified configuration.")
def create_vm_endpoint(request: VMCreateRequest):
    try:
        result = create_vm(request)
        return {"message": "VM created successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-ct",description="Create a new CT with the specified configuration.")
def create_ct_endpoint(request: CTCreateRequest):
    try:
        result = create_ct(request)
        return {"message": "CT created successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vms", description="List all existing VMs.")
def list_vms_endpoint():
    try:
        return {"vms": list_vms()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cts", description="List all existing CTs.")
def list_cts_endpoint():
    try:
        return {"cts": list_cts()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update-vm", description="Update the configuration of an existing VM.")
def update_vm_endpoint(request: VMUpdateRequest):
    try:
        result = update_vm(request)
        return {"message": "VM updated successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete-vm", description="Delete an existing VM by specifying its VM ID.")
def delete_vm_endpoint(vmid: int):
    try:
        result = delete_vm(vmid)
        return {"message": "VM deleted successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/control-vm/{action}", description="Control a VM by performing actions like start, stop, shutdown, or reboot.")
def control_vm_endpoint(vmid: int, action: str):
    if action not in ["start", "stop", "shutdown", "reboot"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    try:
        result = control_vm(vmid, action)
        return {"message": f"VM {action}ed successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/control-ct/{action}", description="Control a CT by performing actions like start, stop, shutdown, or reboot.")
def control_ct_endpoint(vmid: int, action: str):
    if action not in ["start", "stop", "shutdown", "reboot"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    try:
        result = control_ct(vmid, action)
        return {"message": f"CT {action}ed successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/vm/{vmid}/config", description="Get general configuration of a VM.")
def get_vm_config_endpoint(vmid: int):
    try:
        result = get_vm_config(vmid)
        return {"message": "VM configuration retrieved successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vm/{vmid}/network", description="Get network information of a VM.")
def get_vm_network_info_endpoint(vmid: int):
    try:
        result = get_vm_network_info(vmid)
        return {"message": "VM network information retrieved successfully", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
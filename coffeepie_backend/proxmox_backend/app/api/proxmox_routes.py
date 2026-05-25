from fastapi import APIRouter, Depends, HTTPException, Security
from app.dependencies import get_proxmox_auth_headers, verify_bearer_token
from app.services.proxmox_service import get_nodes, clone_vm
from fastapi import Body
from app.services.sunshine_service import send_pin
from app.models.clone_request import CloneRequest  # importa el modelo


from app.services.proxmox_service import (
    clone_vm,
    get_vmid_by_name,
    validate_clone_request,
    get_vm_ip_address,
    get_vm_status,
    delete_vm,
    stop_vm,
     start_vm,get_vnc_ticket
    ,  get_spice_ticket

)
from app.models.clone_by_name import CloneByNameRequest
from app.models.sunshine_request import SunshineRequest  # Import SunshineRequest

router = APIRouter()

@router.get("/nodes")
def fetch_nodes(auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    return get_nodes(auth["headers"], auth["cookies"])
from app.services.proxmox_service import get_nodes, get_vms_on_node

@router.get("/nodes/{node}/vms")
def fetch_vms(node: str, auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    return {"vms": get_vms_on_node(node, auth["headers"], auth["cookies"])}
@router.post("/clone-by-name")
def clone_by_name(request: CloneByNameRequest, auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    try:
        # Validaciones
        validate_clone_request(
            node=request.node,
            source_name=request.source_name,
            new_name=request.name,
            newid=request.newid,
            headers=auth["headers"],
            cookies=auth["cookies"]
        )

        # Obtener VMID desde el nombre
        template_vmid = get_vmid_by_name(request.node, request.source_name, auth["headers"], auth["cookies"])

        # Construir payload para clonación
        payload = {
            "newid": request.newid,
            "name": request.name,
            "target": request.node,
            "full": request.full,
            "storage": request.storage
        }
        if request.full == 0:
            payload.pop("storage", None)
        else:
            payload["storage"] = request.storage
        return clone_vm(request.node, template_vmid, payload, auth["headers"], auth["cookies"])

    except ValueError as ve:
        return {"error": str(ve)}
    except Exception as e:
        return {"error": f"Failed to clone VM: {str(e)}"}
@router.get("/nodes/{node}/vms/{vm_name}/ip")
def get_vm_ip(node: str, vm_name: str, auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    try:
        vmid = get_vmid_by_name(node, vm_name, auth["headers"], auth["cookies"])
        ip_list = get_vm_ip_address(node, vmid, auth["headers"], auth["cookies"])
        return {"vm": vm_name, "ip_addresses": ip_list}
    except Exception as e:
        return {"error": str(e)}
    
    
@router.delete("/nodes/{node}/vms/{vm_name}")
def delete_vm_by_name(node: str, vm_name: str, auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    try:
        vmid = get_vmid_by_name(node, vm_name, auth["headers"], auth["cookies"])
        status = get_vm_status(node, vmid, auth["headers"], auth["cookies"])

        if status != "stopped":
            return {
                "error": f"Cannot delete VM '{vm_name}' because it is currently '{status}'. Please shut it down first."
            }

        return delete_vm(node, vmid, auth["headers"], auth["cookies"])

    except ValueError as ve:
        return {"error": str(ve)}
    except Exception as e:
        return {"error": f"Failed to delete VM: {str(e)}"}
@router.post("/nodes/{node}/vms/{vm_name}/stop")
def stop_vm_by_name(node: str, vm_name: str, auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    try:
        vmid = get_vmid_by_name(node, vm_name, auth["headers"], auth["cookies"])
        status = get_vm_status(node, vmid, auth["headers"], auth["cookies"])

        if status == "stopped":
            return {
                "error": f"VM '{vm_name}' is already stopped."
            }

        return stop_vm(node, vmid, auth["headers"], auth["cookies"])

    except ValueError as ve:
        return {"error": str(ve)}
    except Exception as e:
        return {"error": f"Failed to stop VM: {str(e)}"}

@router.post("/nodes/{node}/vms/{vm_name}/start")
def start_vm_by_name(node: str, vm_name: str, auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    try:
        vmid = get_vmid_by_name(node, vm_name, auth["headers"], auth["cookies"])
        status = get_vm_status(node, vmid, auth["headers"], auth["cookies"])

        if status == "running":
            return {
                "error": f"VM '{vm_name}' is already running."
            }

        return start_vm(node, vmid, auth["headers"], auth["cookies"])

    except ValueError as ve:
        return {"error": str(ve)}
    except Exception as e:
        return {"error": f"Failed to start VM: {str(e)}"}
@router.get("/nodes/{node}/vms/{vm_name}/vnc")
def get_vnc_console(node: str, vm_name: str, auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    try:
        # Get the VMID from the VM name
        vmid = get_vmid_by_name(node, vm_name, auth["headers"], auth["cookies"])
        
        # Get the VNC Proxy ticket and port
        vnc_info = get_vnc_ticket(node, vmid, auth["headers"], auth["cookies"])
        
        # Construct the WebSocket URL
        return {
            "ticket": vnc_info["ticket"],
            "host": vnc_info["host"],
            "port": vnc_info["port"],
            "url": f"wss://{vnc_info['host']}:{vnc_info['port']}/api2/json/nodes/{node}/qemu/{vmid}/vncwebsocket?port={vnc_info['port']}&vncticket={vnc_info['ticket']}"
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/nodes/{node}/vms/{vm_name}/spice")
def get_spice_console(node: str, vm_name: str, auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    try:
        # Get the VMID from the VM name
        vmid = get_vmid_by_name(node, vm_name, auth["headers"], auth["cookies"])
        
        # Get the SPICE Proxy ticket for the console
        spice_info = get_spice_ticket(node, vmid, auth["headers"], auth["cookies"])
        
        # Return the SPICE connection details
        return {
            "ticket": spice_info["ticket"],
            "host": spice_info["host"],
            "port": spice_info["port"],
            "url": f"https://{spice_info['host']}:{spice_info['port']}/api2/json/nodes/{node}/qemu/{vmid}/spiceproxy"
        }
    except Exception as e:
        return {"error": str(e)}
    

@router.post("/sunshine/send-pin")
def sunshine_send_pin(request: SunshineRequest, auth=Depends(get_proxmox_auth_headers), token=Security(verify_bearer_token)):
    """
    Endpoint to send a PIN to the Sunshine API.

    Args:
        request (SunshineRequest): Contains the IP, PIN, and client name.

    Returns:
        dict: The response from the Sunshine API.
    """
    try:
        # Construct the Sunshine URL dynamically based on the provided IP
        sunshine_url = f"https://{request.ip}:47990/api/pin"
        response = send_pin(sunshine_url, request.pin, request.client_name)
        return {"message": "PIN sent successfully", "response": response}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_auth_headers
from app.services.proxmox_service import get_nodes, clone_vm, get_vm_config
from fastapi import Body
from app.services.sunshine_service import send_pin
from app.models.clone_request import CloneRequest  # importa el modelo
from app.config import PROXMOX_URL, PROXMOX_USER, PROXMOX_PASSWORD,PROXMOX_IP
from app.services.proxmox_service import get_nodes, get_vms_on_node
from app.services.proxmox_service import (
    clone_vm,
    get_vmid_by_name,
    validate_clone_request,
    get_vm_ip_address,
    get_vm_status,
    delete_vm,
    stop_vm,
     start_vm,get_vnc_ticket
    ,  get_spice_ticket, authenticate

)
from app.models.clone_by_name import CloneByNameRequest
from app.models.sunshine_request import SunshineRequest  # Import SunshineRequest

router = APIRouter()

@router.get("/nodes")
def fetch_nodes(auth=Depends(get_auth_headers)):
    return get_nodes(auth["headers"], auth["cookies"])


@router.get("/nodes/{node}/vms")
def fetch_vms(node: str, auth=Depends(get_auth_headers)):
    return {"vms": get_vms_on_node(node, auth["headers"], auth["cookies"])}
@router.post("/clone-by-name")
def clone_by_name(request: CloneByNameRequest, auth=Depends(get_auth_headers)):
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

          # Add storage only if it's a full clone
        if request.full == 1:
            payload["storage"] = request.storage


        return clone_vm(request.node, template_vmid, payload, auth["headers"], auth["cookies"])

    except ValueError as ve:
        return {"error": str(ve)}
    except Exception as e:
        return {"error": f"Failed to clone VM: {str(e)}"}
@router.get("/nodes/{node}/vms/{vm_name}/ip")
def get_vm_ip(node: str, vm_name: str, auth=Depends(get_auth_headers)):
    try:
        vmid = get_vmid_by_name(node, vm_name, auth["headers"], auth["cookies"])
        ip_list = get_vm_ip_address(node, vmid, auth["headers"], auth["cookies"])
        return {"vm": vm_name, "ip_addresses": ip_list}
    except Exception as e:
        return {"error": str(e)}
    
    
@router.delete("/nodes/{node}/vms/{vm_name}")
def delete_vm_by_name(node: str, vm_name: str, auth=Depends(get_auth_headers)):
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
def stop_vm_by_name(node: str, vm_name: str, auth=Depends(get_auth_headers)):
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
def start_vm_by_name(node: str, vm_name: str, auth=Depends(get_auth_headers)):
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
def get_vnc_console(node: str, vm_name: str, auth=Depends(get_auth_headers)):
    try:
        # Get the VMID from the VM name
        vmid = get_vmid_by_name(node, vm_name, auth["headers"], auth["cookies"])
        
        # Get the VNC Proxy ticket and port
        vnc_info = get_vnc_ticket(node, vmid, auth["headers"], auth["cookies"])
        print(vnc_info)
          # Construct the noVNC URL

        websocket_url = f"wss://{vnc_info['host']}:{vnc_info['port']}/api2/json/nodes/{node}/qemu/{vmid}/vncwebsocket?port={ vnc_info['port']}&vncticket={ vnc_info['ticket']}"
        novnc_url = f"https://7ac7-179-1-219-94.ngrok-free.app//vnc.html?host={vnc_info['host']}&port={vnc_info['port']}&path={websocket_url}"
           # Construct the WebSocket URL for the VNC connection
        
          # Target VNC server details
        target_vnc = f"{vnc_info['host']}:{vnc_info['port']}"
         # Construct the CLI command for websockify
        cli_command = f"python -m websockify 6080 {target_vnc}"
        
        #websocket_url = "ws://127.0.0.1:6080"  # noVNC WebSocket proxy running locally on port 6080
        
        # Construct the noVNC URL
        #novnc_url = f"http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080&path={websocket_url}"
        
        
        # Construct the WebSocket URL
        return {
            "ticket": vnc_info["ticket"],
            "host": vnc_info["host"],
            "port": vnc_info["port"],
            
            "novnc_url": novnc_url,
            "websocket_url": websocket_url,
            "cli_command": cli_command ,
            "url": f"wss://{vnc_info['host']}:{vnc_info['port']}/api2/json/nodes/{node}/qemu/{vmid}/vncwebsocket?port={vnc_info['port']}&vncticket={vnc_info['ticket']}",
           
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/nodes/{node}/vms/{vm_name}/spice")
def get_spice_console(node: str, vm_name: str, auth=Depends(get_auth_headers)):
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
def sunshine_send_pin(request: SunshineRequest):
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
@router.get("/console-url")
def get_console_url(node: str, vmname: str, vmid: int = None, auth=Depends(get_auth_headers)):
    try:

        headers = auth["headers"]
        cookies = auth["cookies"]
        ticket = cookies["PVEAuthCookie"]
        csrf_token = headers["CSRFPreventionToken"]
        # Si no envían vmid, lo buscamos por vmname
        if vmid is None:
            vvmid = get_vmid_by_name(node, vmname, headers, cookies)
        
        # Construir la URL de la consola novnc
        url = (f"{PROXMOX_IP}/?console=kvm&novnc=1"
               f"&vmid={vmid}&vmname={vmname}&node={node}&resize=off&cmd=")
        
        return {"console_url": url,
                "ticket": ticket,
            "csrf_token": csrf_token
                
                }

    except Exception as e:
        return {"error": str(e)}
@router.get("/nodes/{node}/vms/{vmid}/config")
def fetch_vm_config(node: str, vmid: int, auth=Depends(get_auth_headers)):
     """Fetch full VM configuration from Proxmox via service."""
     try:
         cfg = get_vm_config(node, vmid, auth["headers"], auth["cookies"])
         return cfg
     except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to fetch VM config: {e}")
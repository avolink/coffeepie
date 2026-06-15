import requests
from app.config import PROXMOX_URL, PROXMOX_USER, PROXMOX_PASSWORD

def authenticate():
    url = f"{PROXMOX_URL}/access/ticket"
    data = {"username": PROXMOX_USER, "password": PROXMOX_PASSWORD}
    response = requests.post(url, data=data, verify=False)
    response.raise_for_status()
    data = response.json()["data"]
    return data["ticket"], data["CSRFPreventionToken"]

def get_nodes(headers, cookies):
    url = f"{PROXMOX_URL}/nodes"
    response = requests.get(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return response.json()

def get_vms_on_node(node: str, headers, cookies):
    url = f"{PROXMOX_URL}/nodes/{node}/qemu"
    response = requests.get(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    vms = response.json()["data"]
    names = [vm["name"] for vm in vms if "name" in vm]
    return names

def get_vms_details_on_node(node: str, headers, cookies):
    url = f"{PROXMOX_URL}/nodes/{node}/qemu"
    response = requests.get(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return response.json()["data"]

def get_vmid_by_name(node: str, vm_name: str, headers, cookies):
    vms = get_vms_details_on_node(node, headers, cookies)
    for vm in vms:
        if vm.get("name") == vm_name:
            return vm["vmid"]
    raise ValueError(f"VM with name '{vm_name}' not found on node '{node}'")

def validate_clone_request(node: str, source_name: str, new_name: str, newid: int, headers, cookies):
    vms = get_vms_details_on_node(node, headers, cookies)
    source_exists = False
    name_exists = False
    id_exists = False

    for vm in vms:
        if vm.get("name") == source_name:
            source_exists = True
        if vm.get("name") == new_name:
            name_exists = True
        if vm.get("vmid") == newid:
            id_exists = True

    if not source_exists:
        raise ValueError(f"Source VM '{source_name}' not found on node '{node}'")
    if name_exists:
        raise ValueError(f"VM name '{new_name}' already exists on node '{node}'")
    if id_exists:
        raise ValueError(f"VM ID '{newid}' is already in use on node '{node}'")

def clone_vm(node: str, template_vmid: int, payload: dict, headers, cookies):
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{template_vmid}/clone"
    response = requests.post(url, data=payload, headers=headers, cookies=cookies, verify=False)

    print("Clone response", response.status_code, response.text)  # para debug
    response.raise_for_status()
    return response.json()

def get_vm_ip_address(node: str, vmid: int, headers, cookies):
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces"
    response = requests.get(url, headers=headers, cookies=cookies, verify=False)
    
    # Algunos errores comunes si el agente no está disponible
    if response.status_code == 500 and "QEMU guest agent is not running" in response.text:
        raise RuntimeError("QEMU Guest Agent is not running in the VM.")
    
    response.raise_for_status()
    interfaces = response.json()["data"]["result"]

    ip_list = []
    for iface in interfaces:
        for ip_data in iface.get("ip-addresses", []):
            ip = ip_data.get("ip-address")
            if ip and not ip.startswith("127.") and ":" not in ip:
                ip_list.append(ip)

    return ip_list or ["No IP found"]
def get_vm_status(node: str, vmid: int, headers, cookies):
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/status/current"
    response = requests.get(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return response.json()["data"]["status"]  # 'running', 'stopped', etc.

def delete_vm(node: str, vmid: int, headers, cookies):
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}"
    response = requests.delete(url, headers=headers, cookies=cookies, verify=False)
    print("Delete response", response.status_code, response.text)
    response.raise_for_status()
    return {"message": f"VM {vmid} deleted successfully"}
def stop_vm(node: str, vmid: int, headers, cookies):
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/status/stop"
    response = requests.post(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return {"message": f"VM {vmid} stopped successfully"}

def start_vm(node: str, vmid: int, headers, cookies):
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/status/start"
    response = requests.post(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return {"message": f"VM {vmid} started successfully"}
def get_vnc_ticket(node: str, vmid: int, headers, cookies):
    # Step 1: Call the /vncproxy endpoint to get the ticket and port
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/vncproxy"
    response = requests.post(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    vnc_data = response.json()["data"]
# Step 2: Construct the WebSocket URL
    #websocket_url = f"wss://{vnc_data['host']}:{vnc_data['port']}/api2/json/nodes/{node}/qemu/{vmid}/vncwebsocket?port={vnc_data['port']}&vncticket={vnc_data['ticket']}"
    # Step 2: Return the ticket and port for the WebSocket connection
    return {
       
       # "websocket_url": websocket_url,
        "ticket": vnc_data["ticket"],
        "port": vnc_data["port"],
        "host": vnc_data.get("host", "127.0.0.1")  # Default to localhost if host is not provided
    }

def get_spice_ticket(node: str, vmid: int, headers, cookies):
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/spiceproxy"
    response = requests.get(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return response.json()

def get_vm_config(node: str, vmid: int, headers, cookies):
    """
    Fetch the full configuration for a VM from Proxmox.
    GET /nodes/{node}/qemu/{vmid}/config
    """
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/config"
    response = requests.get(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return response.json().get("data", {})

def shutdown_vm(node: str, vmid: int, headers, cookies):
    """Gracefully shut down a VM"""
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/status/shutdown"
    response = requests.post(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return {"message": f"VM {vmid} shutdown initiated"}

def reboot_vm(node: str, vmid: int, headers, cookies):
    """Reboot a VM"""
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/status/reboot"
    response = requests.post(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return {"message": f"VM {vmid} reboot initiated"}
def set_vm_config(node: str, vmid: int, config: dict, headers, cookies):
    """Update VM CPU, memory, sockets via Proxmox API"""
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/config"
    response = requests.post(url, data=config, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return response.json().get("data", {})

def put_vm_config(node: str, vmid: int, config: dict, headers, cookies):
    """
    Update VM CPU, memory, sockets via Proxmox API using PUT as required by Proxmox docs.
    PUT /nodes/{node}/qemu/{vmid}/config
    Example config: {"cores": 4, "memory": 8192}
    """
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/config"
    try:
        response = requests.put(url, data=config, headers=headers, cookies=cookies)
        response.raise_for_status()
        return response.json().get("data", {})
    except requests.RequestException as e:
        # Log or handle the error as needed
        raise RuntimeError(f"Failed to update VM config in Proxmox: {e}")

def resize_disk(node: str, vmid: int, disk: str, size: str, headers, cookies):
    """Resize a VM disk via Proxmox API"""
    # Proxmox requires query parameters and PUT method for resize
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/resize"
    params = {"disk": disk, "size": size}
    response = requests.put(url, params=params, headers=headers, cookies=cookies, verify=False)
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        # Proxmox does not support shrinking disks (message may be in exception text)
        err_msg = str(e).lower()
        if response.status_code == 500 and "shrinking disks is not supported" in err_msg:
            raise ValueError("Cannot shrink disk: Proxmox does not support shrinking disks") from e
        # propagate other errors
        raise
    return response.json().get("data", {})

def create_snapshot(node: str, vmid: int, snapname: str, description: str, headers, cookies, vmstate: bool = False):
    """Create a snapshot for a VM in Proxmox."""
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/snapshot"
    # Proxmox expects 'snapname', 'description', and 'vmstate' as a boolean (must be sent as JSON, not form data)
    data = {
        "snapname": snapname,
        "description": description,
        "vmstate": vmstate
    }
    response = requests.post(url, json=data, headers=headers, cookies=cookies, verify=False)
    if response.status_code != 200:
        print("Proxmox snapshot error:", response.status_code, response.text)
    response.raise_for_status()
    return response.json()

def list_snapshots(node: str, vmid: int, headers, cookies):
    """List all snapshots for a VM in Proxmox."""
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/snapshot"
    response = requests.get(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return response.json().get("data", [])

def delete_snapshot(node: str, vmid: int, snapname: str, headers, cookies):
    """Delete a snapshot for a VM in Proxmox."""
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/snapshot/{snapname}"
    response = requests.delete(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return {"message": f"Snapshot {snapname} deleted"}

def rollback_snapshot(node: str, vmid: int, snapname: str, headers, cookies):
    """Rollback a VM to a snapshot in Proxmox."""
    url = f"{PROXMOX_URL}/nodes/{node}/qemu/{vmid}/snapshot/{snapname}/rollback"
    response = requests.post(url, headers=headers, cookies=cookies, verify=False)
    response.raise_for_status()
    return {"message": f"VM {vmid} rolled back to snapshot {snapname}"}


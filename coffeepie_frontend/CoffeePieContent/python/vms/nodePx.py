import requests

BASE_URL = "http://127.0.0.1:8000"  # Default, can be overridden by argument

def fetch_vm_ip(node, vmId, base_url=BASE_URL):
    """
    Fetches the IP address of a VM using the provided node and VM ID.
    Args:
        node (str): The node where the VM is located.
        vmId (str): The ID of the VM to fetch the IP address for.
        base_url (str): The base URL of the backend API.
    Returns:
        str: The first IP address found, or an empty string if not found or error.
    """
    if not vmId:
        print("Error: vmId is empty. Cannot fetch IP address.")
        return ""
    url = f"{base_url}/nodes/{node}/vms/{vmId}/ip"
    try:
        print(url)
        print(f"Fetching IP address for VM {vmId} on node {node}...")
        response = requests.get(url, headers={"accept": "application/json"})
        if response.status_code == 200:
            data = response.json()
            ip_addresses = data.get("ip_addresses", [])
            if ip_addresses:
                ip_address = ip_addresses[0]
                print(f"IP address for VM {vmId}: {ip_address}")
                return ip_address
            else:
                print(f"No IP addresses found for VM {vmId}.")
                return ""
        else:
            print(f"Failed to fetch IP address for VM {vmId}: {response.status_code}, {response.text}")
            return ""
    except Exception as e:
        print(f"Error fetching IP address for VM {vmId}: {e}")
        return ""

def start_vm(node, vmId, base_url=BASE_URL):
    """
    Starts a VM using the provided node and VM ID.
    Args:
        node (str): The node where the VM is located.
        vmId (str): The ID of the VM to start.
        base_url (str): The base URL of the backend API.
    Returns:
        bool: True if started successfully, False otherwise.
    """
    url = f"{base_url}/nodes/{node}/vms/{vmId}/start"
    try:
        print(f"Starting VM {vmId} on node {node}...")
        response = requests.post(url, headers={"accept": "application/json"}, data="")
        if response.status_code == 200:
            print(f"VM {vmId} started successfully.")
            return True
        else:
            print(f"Failed to start VM {vmId}: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        print(f"Error starting VM {vmId}: {e}")
        return False

def fetch_vm_list(node, base_url=BASE_URL):
    """
    Fetches the list of VMs from the endpoint and filters numeric IDs.
    Args:
        node (str): The node to fetch VMs from.
        base_url (str): The base URL of the backend API.
    Returns:
        list: List of numeric VM IDs as strings.
    """
    url = f"{base_url}/nodes/{node}/vms"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            vms = response.json().get("vms", [])
            print(vms)
            numeric_vms = [vm for vm in vms if vm.isdigit()]
            print(numeric_vms)
            return numeric_vms
        else:
            print(f"Failed to fetch VM list: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        print(f"Error fetching VM list: {e}")
        return []

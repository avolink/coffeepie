import requests
from novncutils.chromeDriver import get_console_data, open_console_with_tokens
def fetch_my_vms(token: str, base_url: str ):
    """
    Fetches the VMs for the current user using the provided access token.
    Args:
        token (str): The access token (JWT).
        base_url (str): The base URL of the backend API.
    Returns:
        dict or None: The response JSON if successful, or None if failed.
    """
    url = f"{base_url}/vms/me?token={token}"
    headers = {
        "accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    
    
    except requests.RequestException as e:
        print(f"Failed to fetch VMs: {e}")
        return None
def get_console_url(token, vmid, base_url: str ):
    """
    Fetch the console URL and tokens for a VM using the user's access token.
    Args:
        token (str): The user's JWT access token.
        vmid (str or int): The VM ID.
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: {"success": True, ...} on success, {"success": False, "detail": ...} on error.
    """
    url = f"{base_url}/vms/{vmid}/console-url?token={token}"
    print(url)
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        open_console_with_tokens(data["console_url"], data["ticket"], data["csrf_token"])
        return {"success": True}
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (400, 403):
            try:
                detail = response.json().get("detail")
                print(detail, type(detail))

            except Exception:
                detail = str(e)
            return {"success": False, "detail": detail, "status_code": e.response.status_code}
        return {"success": False, "detail": str(e), "status_code": getattr(e.response, 'status_code', None)}
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}

def delete_vm(token, vmid, base_url: str):
    """
    Delete a VM instance.
    Args:
        token (str): The user's JWT access token.
        vmid (str or int): The VM ID.
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: The response JSON.
    """
    url = f"{base_url}/vms/{vmid}?token={token}"
    headers = {"accept": "application/json"}
    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}

def get_vm_status(token, vmid, base_url: str):
    """
    Get the status of a VM instance.
    Args:
        token (str): The user's JWT access token.
        vmid (str or int): The VM ID.
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: The response JSON.
    """
    url = f"{base_url}/vms/{vmid}/status?token={token}"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}

def stop_vm(token, vmid, base_url: str):
    """
    Stop a running VM instance.
    Args:
        token (str): The user's JWT access token.
        vmid (str or int): The VM ID.
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: The response JSON.
    """
    url = f"{base_url}/vms/{vmid}/stop?token={token}"
    headers = {"accept": "application/json"}
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}

def start_my_vm(token, vmid, base_url: str):
    """
    Start a stopped VM instance.
    Args:
        token (str): The user's JWT access token.
        vmid (str or int): The VM ID.
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: The response JSON.
    """
    url = f"{base_url}/vms/{vmid}/start?token={token}"
    headers = {"accept": "application/json"}
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        print(response.text)
        return True
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}

def shutdown_vm(token, vmid, base_url: str):
    """
    Shutdown a VM instance.
    Args:
        token (str): The user's JWT access token.
        vmid (str or int): The VM ID.
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: The response JSON.
    """
    url = f"{base_url}/vms/{vmid}/shutdown?token={token}"
    headers = {"accept": "application/json"}
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}

def reboot_vm(token, vmid, base_url: str):
    """
    Reboot a VM instance.
    Args:
        token (str): The user's JWT access token.
        vmid (str or int): The VM ID.
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: The response JSON.
    """
    url = f"{base_url}/vms/{vmid}/reboot?token={token}"
    headers = {"accept": "application/json"}
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}

def clone_vm(token, vmid, base_url: str):
    """
    Clone a VM instance.
    Args:
        token (str): The user's JWT access token.
        vmid (str or int): The VM ID.
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: The response JSON.
    """
    url = f"{base_url}/vms/clone/{vmid}?token={token}"
    headers = {"accept": "application/json"}
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}

def clone_vm_with_specs(token, specs, base_url: str):
    """
    Clone a VM with custom specs.
    Args:
        token (str): The user's JWT access token.
        specs (dict): The specs for the new VM (see API docs).
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: The response JSON from the backend.
    """
    url = f"{base_url}/vms/clone-with-specs?token={token}"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, headers=headers, json=specs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}
def create_snapshot(token, vm_id, description, base_url: str):
    """
    Create a snapshot for a VM.
    Args:
        token (str): The user's JWT access token.
        vm_id (str): The VM ID.
        description (str): Description for the snapshot.
        base_url (str): The FastAPI backend base URL.
    Returns:
        dict: The response JSON from the backend.
    """
    url = f"{base_url}/snapshots/Snapshot/create?vm_id={vm_id}&description={description}&token={token}"
    headers = {
        "accept": "application/json"
    }
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}
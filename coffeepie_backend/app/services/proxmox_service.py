import subprocess

def run_command(command: list) -> str:
    result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
   
    return result.stdout

# Clone a VM or CT
def clone_vm(vmid: int, new_vmid: int, name: str) -> str:
    command = ["qm", "clone", str(vmid), str(new_vmid), "--name", name]
    return run_command(command)

def clone_ct(vmid: int, new_vmid: int, name: str) -> str:
    command = ["pct", "clone", str(vmid), str(new_vmid), "--name", name]
    return run_command(command)

# Create VM
def create_vm(request) -> str:
    command = [
        "qm", "create", str(request.vmid), "--name", request.name, "--memory", str(request.memory),
        "--net0", request.net0, "--disk", f"{request.storage}:{request.disk}", "--ostype", request.ostype,
        "--storage", request.storage
    ]
    if request.cdrom and request.iso_path:
        command += ["--cdrom", request.iso_path]
    return run_command(command)

# Create CT
def create_ct(request) -> str:
    command = [
        "pct", "create", str(request.vmid), request.template, "--hostname", request.hostname,
        "--rootfs", f"{request.rootfs}:50G", "--net0", f"ip={request.ip_address}/24,gw={request.gateway}"
    ]
    return run_command(command)

# List VMs and CTs
def list_vms() -> str:
    return run_command(["qm", "list"])

def list_cts() -> str:
    return run_command(["pct", "list"])

# Update VM
def update_vm(request) -> str:
    command = ["qm", "set", str(request.vmid), "--memory", str(request.memory), "--cpus", str(request.cpus)]
    if request.description:
        command += ["--description", request.description]
    return run_command(command)

# Delete VM
def delete_vm(vmid: int) -> str:
    return run_command(["qm", "destroy", str(vmid)])

# Start, stop, shutdown, reboot actions
def control_vm(vmid: int, action: str) -> str:
    command = ["qm", action, str(vmid)]
    return run_command(command)

def control_ct(vmid: int, action: str) -> str:
    command = ["pct", action, str(vmid)]
    return run_command(command)


# Get general configuration of a VM
def get_vm_config(vmid: int) -> str:
    command = ["qm", "config", str(vmid)]
    return run_command(command)

# Get network information of a VM
def get_vm_network_info(vmid: int) -> str:
    command = ["qm", "agent", str(vmid), "network-get-interfaces"]
    return run_command(command)
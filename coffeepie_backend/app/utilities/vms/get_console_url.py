from app.crud.companies import get_company as _get_c
from app.crud.users import get_user as _get_u
from fastapi import HTTPException
from app.config import PROXMOX_IP

async def get_console_url(vm_id, current_user, auth, ensure_vm_owned):
    """Return novnc console URL, ticket and CSRF token for a VM owned by the current user"""
    # Ensure VM exists and is owned by current user
    vm = await ensure_vm_owned(vm_id, current_user)
    node = vm.get("node")
    # Check credits
    credits = 0
    if vm.get("companyID"):
        comp = await _get_c(vm["companyID"])
        credits = comp.get("portions", 0)
    else:
        user = await _get_u(str(vm.get("ownerID")))
        credits = user.get("portions", 0)
    if credits <= 0:
        raise HTTPException(status_code=403, detail="No tienes créditos suficientes para acceder a la consola.")
    # Check VM status
    if vm.get("status") != "running":
        raise HTTPException(status_code=400, detail="La máquina virtual debe estar encendida para acceder a la consola.")
    # Grab Proxmox auth details
    headers = auth["headers"]
    cookies = auth["cookies"]
    ticket = cookies.get("PVEAuthCookie")
    csrf_token = headers.get("CSRFPreventionToken")
    # Construct novnc console URL
    url = (
        f"{PROXMOX_IP}/?console=kvm&novnc=1"
        f"&vmid={vm.get('vmid')}&vmname={vm.get('name')}&node={node}&resize=off&cmd="
    )
    return {"console_url": url, "ticket": ticket, "csrf_token": csrf_token}

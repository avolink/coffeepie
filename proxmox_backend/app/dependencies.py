from app.services.proxmox_service import authenticate

def get_auth_headers():
    ticket, csrf = authenticate()
    return {
        "headers": {"CSRFPreventionToken": csrf},
        "cookies": {"PVEAuthCookie": ticket}
    }

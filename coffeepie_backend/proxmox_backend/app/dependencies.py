from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.proxmox_service import authenticate
from app.services.auth_service import verify_id_token
from app import config

security_scheme = HTTPBearer()


def get_proxmox_auth_headers():
    ticket, csrf = authenticate()
    return {
        "headers": {"CSRFPreventionToken": csrf},
        "cookies": {"PVEAuthCookie": ticket}
    }


def get_auth_headers():
    return get_proxmox_auth_headers()


def verify_bearer_token(credentials: HTTPAuthorizationCredentials = Security(security_scheme)):
    """
    Validates a Firebase ID token from the Authorization: Bearer header.
    Only allows access if the token is valid and the caller is authenticated.
    Used as FastAPI dependency on all proxmox management endpoints.
    """
    try:
        decoded = verify_id_token(credentials.credentials)
        return decoded
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

"""Role-based access control for the Coffee Pie panel.

Roles ride on the user's token from whichever IdP is configured (Supabase in
production, Firebase in prototype) and are normalized by the identity layer. A
user may hold several roles at once (e.g. a Provider who also advertises).
"""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Role and roles_of live in the framework-free identity module; re-exported here
# so existing imports (`from app.auth.rbac import Role`) keep working.
from app.auth.identity import AuthenticatedUser, IdentityError, Role, roles_of
from app.config import get_identity_provider

__all__ = ["Role", "roles_of", "verify_bearer_token", "require_roles"]

security_scheme = HTTPBearer()


def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> AuthenticatedUser:
    """Validate the bearer token via the configured IdP → AuthenticatedUser."""
    try:
        return get_identity_provider().verify(credentials.credentials)
    except IdentityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_roles(*allowed: Role, require_all: bool = False):
    """FastAPI dependency factory gating an endpoint by role.

    require_roles(Role.PROVIDER)                    → must be a Provider
    require_roles(Role.PROVIDER, Role.CONTRIBUTOR)  → either (OR)
    require_roles(..., require_all=True)            → all (AND)

    Admins always pass. Returns the AuthenticatedUser so handlers read uid/email.
    """
    allowed_set = set(allowed)

    def dependency(user: AuthenticatedUser = Depends(verify_bearer_token)) -> AuthenticatedUser:
        held = roles_of(user)
        if Role.ADMIN in held:
            return user
        ok = held.issuperset(allowed_set) if require_all else bool(held & allowed_set)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing required role(s): "
                + ", ".join(sorted(r.value for r in allowed_set)),
            )
        return user

    return dependency

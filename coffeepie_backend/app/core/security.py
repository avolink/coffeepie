import hmac
import os
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.config import JWT_SECRET_KEY, JWT_ALGORITHM
from app.services.auth_service import get_user_by_id

# Refuse to start with a missing or guessable signing key: anyone who knows the
# key can mint a token for any user.
_WEAK_SECRETS = {"", "secret", "changeme", "change-me", "your-secret-key", "supersecret"}
if (not JWT_SECRET_KEY or JWT_SECRET_KEY.lower() in _WEAK_SECRETS or len(JWT_SECRET_KEY) < 32
        or "change" in JWT_SECRET_KEY.lower() or JWT_SECRET_KEY.lower().startswith("your")):
    raise RuntimeError(
        "JWT_SECRET_KEY must be set to a random value of at least 32 characters "
        "(generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    )

# auto_error=False so a request may authenticate with either the standard
# Authorization header or the legacy ?token= query parameter the Qt terminal
# still uses. Prefer the header: URLs end up in access logs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise credentials_exception
        return sub
    except JWTError:
        raise credentials_exception

async def get_current_user(
    bearer: Optional[str] = Depends(oauth2_scheme),
    token: Optional[str] = Query(None, include_in_schema=False),
):
    raw = bearer or token
    if not raw:
        raise credentials_exception
    user_id = decode_token(raw)
    try:
        user = await get_user_by_id(user_id)
    except Exception:
        # malformed ObjectId in the subject, etc.
        raise credentials_exception
    if not user:
        raise credentials_exception
    return user


async def get_optional_user(
    bearer: Optional[str] = Depends(oauth2_scheme),
    token: Optional[str] = Query(None, include_in_schema=False),
):
    """The caller if they sent a valid token, else None (never raises)."""
    raw = bearer or token
    if not raw:
        return None
    try:
        return await get_current_user(bearer=raw, token=None)
    except HTTPException:
        return None


def is_admin(user: dict) -> bool:
    """Administrators are listed in ADMIN_USER_IDS / ADMIN_EMAILS (comma-separated)."""
    ids = {s.strip() for s in os.getenv("ADMIN_USER_IDS", "").split(",") if s.strip()}
    emails = {s.strip().lower() for s in os.getenv("ADMIN_EMAILS", "").split(",") if s.strip()}
    return str(user.get("_id")) in ids or str(user.get("email", "")).lower() in emails


async def require_admin(user: dict = Depends(get_current_user)):
    if not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user


def same_company(user: dict, company_id: str) -> bool:
    cid = user.get("companyID")
    return bool(cid) and hmac.compare_digest(str(cid), str(company_id))

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.config import JWT_SECRET_KEY, JWT_ALGORITHM
from app.services.auth_service import get_user_by_id


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

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

async def get_current_user(token):
    user_id = decode_token(token)
    user = await get_user_by_id(user_id)
    if not user:
        raise credentials_exception
    return user

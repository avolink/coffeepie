import requests
import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin import exceptions
from app import config
import os

# Initialize Firebase Admin SDK
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
cred_path = os.path.join(base_dir, config.FIREBASE_ADMIN_SDK_JSON)

try:
    cred = credentials.Certificate(cred_path)
except FileNotFoundError:
    raise RuntimeError(
        f"Firebase Admin SDK JSON not found at {cred_path}. "
        "Place your service account key at app/secrets/firebase-adminsdk.json "
        "or set FIREBASE_ADMIN_SDK_JSON in your .env file."
    )

try:
    firebase_admin.initialize_app(cred, {
        'projectId': config.FIREBASE_PROJECT_ID,
    })
except ValueError as e:
    print(f"Firebase already initialized: {e}")

def create_user(email, password):
    try:
        user = auth.create_user(
            email=email,
            password=password,
        )
        return {"uid": user.uid}
    except exceptions.FirebaseError as e:
        raise RuntimeError(f"Failed to create user: {e}")

def get_user_by_email(email: str):
    try:
        user = auth.get_user_by_email(email)
        return user
    except exceptions.FirebaseError as e:
        raise RuntimeError(f"Failed to get user: {e}")

def create_custom_token(uid: str):
    try:
        custom_token = auth.create_custom_token(uid)
        return custom_token.decode()

    except exceptions.FirebaseError as e:
        raise RuntimeError(f"Failed to create custom token: {e}")

class AuthUnavailable(RuntimeError):
    """Firebase Auth could not be reached or is not configured."""


_IDENTITY_TOOLKIT = "https://identitytoolkit.googleapis.com/v1/accounts"


def verify_password(email: str, password: str):
    """Check email + password with Firebase Auth. Returns the uid, or None.

    None means the credentials are wrong (or the account does not exist) - the
    caller must not distinguish the two. AuthUnavailable means we could not
    ask, which is not the same as "wrong password".
    """
    if not config.FIREBASE_API_KEY:
        raise AuthUnavailable("FIREBASE_API_KEY is not configured")
    try:
        res = requests.post(
            f"{_IDENTITY_TOOLKIT}:signInWithPassword",
            params={"key": config.FIREBASE_API_KEY},
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=10,
        )
    except requests.RequestException as e:
        raise AuthUnavailable(str(e))
    if res.status_code == 200:
        return res.json().get("localId")
    if res.status_code == 400:
        return None
    raise AuthUnavailable(f"Firebase Auth returned HTTP {res.status_code}")


def send_password_reset_email(email: str):
    """Have Firebase e-mail a reset link. The link itself never reaches us."""
    if not config.FIREBASE_API_KEY:
        raise AuthUnavailable("FIREBASE_API_KEY is not configured")
    res = requests.post(
        f"{_IDENTITY_TOOLKIT}:sendOobCode",
        params={"key": config.FIREBASE_API_KEY},
        json={"requestType": "PASSWORD_RESET", "email": email},
        timeout=10,
    )
    res.raise_for_status()

def verify_id_token(id_token: str):
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except exceptions.FirebaseError as e:
        raise RuntimeError(f"Invalid or expired token: {e}")
    except ValueError as e:
        raise RuntimeError(f"Invalid token format: {e}")
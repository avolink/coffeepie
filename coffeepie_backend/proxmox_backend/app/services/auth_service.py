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

def generate_password_reset_link(email: str):
    try:
        link = auth.generate_password_reset_link(email)
        return link
    except exceptions.FirebaseError as e:
        raise RuntimeError(f"Failed to generate password reset link: {e}")

def verify_id_token(id_token: str):
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except exceptions.FirebaseError as e:
        raise RuntimeError(f"Invalid or expired token: {e}")
    except ValueError as e:
        raise RuntimeError(f"Invalid token format: {e}")
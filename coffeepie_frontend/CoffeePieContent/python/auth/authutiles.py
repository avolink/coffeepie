import requests
import socket

def login_user(email: str, password: str, terminalID: str = None, base_url: str = None):
    """
    Logs in a user by sending a POST request to the FastAPI backend.
    Args:
        email (str): User's email address.
        password (str): User's password.
        terminalID (str): Terminal identifier. If None, uses the system hostname.
        base_url (str): Base URL of the backend API.
    Returns:
        dict: Response JSON if successful, or None if failed.
    Raises:
        requests.RequestException: If the request fails.
    """
    if terminalID is None:
        terminalID = socket.gethostname()
    url = f"{base_url}/auth/login"
    payload = {
        "email": email,
        "password": password,
        "terminalID": terminalID
    }
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Login failed: {e}")
        return None

def create_user(userData, base_url: str ):
    """
    Creates a user by sending a POST request to the FastAPI backend.
    Args:
        userData (dict): Dictionary with user fields (name, email, etc.)
        base_url (str): Base URL of the backend API.
    Returns:
        (success: bool, message: str): Tuple indicating result and message.
    """
    url = f"{base_url}/users/"
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=userData, headers=headers)
        if response.status_code in (200, 201):
            return True, "El usuario ha sido creado."
        else:
            if response.status_code == 400 and 'Email already registered' in response.text:
                return False, "El email ya está registrado."
            else:
                return False, "Error al crear el usuario."
    except Exception as e:
        print(f"Error creating user: {e}")
        return False, "Error al crear el usuario."

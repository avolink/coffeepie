import base64
import requests
from app.config import SUNSHINE_USERNAME, SUNSHINE_PASSWORD

def send_pin(sunshine_url: str, pin: str, client_name: str):
    """
    Sends a PIN to the Sunshine API for pairing with Moonlight.

    Args:
        sunshine_url (str): The Sunshine API URL.
        pin (str): The 4-digit PIN to send.
        client_name (str): A friendly name for the client.

    Returns:
        dict: The response from the Sunshine API.
    """
    # Encode credentials in Base64 for Basic Authentication
    credentials = f"{SUNSHINE_USERNAME}:{SUNSHINE_PASSWORD}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    # Prepare headers and payload
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    payload = {
        "pin": pin,
        "name": client_name
    }

    # Send POST request to Sunshine API
    try:
        response = requests.post(sunshine_url, json=payload, headers=headers, verify=True)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to send PIN: {e}")
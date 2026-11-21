import base64
from urllib.parse import urlsplit

import requests
from app.config import SUNSHINE_USERNAME, SUNSHINE_PASSWORD
from app.services.net_guard import require_allowed_target, TargetNotAllowed

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
    # SSRF guard, enforced here so no caller can bypass it: only literal IPs
    # inside SUNSHINE_ALLOWED_NETWORKS are ever contacted.
    try:
        require_allowed_target(urlsplit(sunshine_url).hostname or "")
    except TargetNotAllowed as e:
        raise RuntimeError(f"Target rejected: {e}")

    if not SUNSHINE_USERNAME or not SUNSHINE_PASSWORD:
        raise RuntimeError("Sunshine credentials are not configured")

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

    # Send POST request to Sunshine API. No redirects (a redirect would walk
    # past the guard), and a timeout so a dead host cannot hang a worker.
    try:
        response = requests.post(sunshine_url, json=payload, headers=headers,
                                 verify=True, timeout=10, allow_redirects=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to send PIN: {e}")

import base64
import requests
import json
import requests
from requests.auth import HTTPBasicAuth
USERNAME = "sunshine"  # Replace with your Sunshine username
#PASSWORD = "sunshine"  # Replace with your Sunshine password
PASSWORD = "sunshine"  # Replace with your Sunshine password
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
    credentials = f"{USERNAME}:{PASSWORD}"

    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    print(f"Encoded credentials: {encoded_credentials}")
    # Prepare headers and payload
    headers = {
        #"Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}",
         "Content-Type": "text/plain;charset=UTF-8",
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0"
    }
    payload = {
        "pin": pin,
    "name": client_name
    }

    # Send POST request to Sunshine API
    try:
        print(sunshine_url)
        response = requests.post(sunshine_url, data=payload, headers=headers, verify=False)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        print(f"Response Body: {response.text}")
        response.raise_for_status()
      
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to send PIN: {e}")
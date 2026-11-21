import base64
import os
from urllib.parse import urlsplit

import requests
from app.services.net_guard import require_allowed_target, TargetNotAllowed


def send_pin(sunshine_url: str, pin: str, client_name: str):
    """
    Sends a PIN to the Sunshine API for pairing with Moonlight.

    Credentials come from SUNSHINE_USERNAME / SUNSHINE_PASSWORD and must be
    unique per deployment. The target must be a literal IP inside
    SUNSHINE_ALLOWED_NETWORKS (SSRF guard, enforced here so no caller can skip
    it). Sunshine ships a self-signed certificate: set SUNSHINE_CA_BUNDLE to
    its CA/cert file to get real TLS verification; without it verification is
    off, which is only tolerable because the target is pinned to those networks.
    """
    try:
        require_allowed_target(urlsplit(sunshine_url).hostname or "")
    except TargetNotAllowed as e:
        raise RuntimeError(f"Target rejected: {e}")

    username = os.getenv("SUNSHINE_USERNAME", "")
    password = os.getenv("SUNSHINE_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("Sunshine credentials are not configured")

    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "text/plain;charset=UTF-8",
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0",
    }
    payload = {"pin": pin, "name": client_name}
    verify = os.getenv("SUNSHINE_CA_BUNDLE") or False

    try:
        # No redirects (they would walk past the guard) and a timeout so a
        # dead host cannot hang a worker. Nothing about the request or the
        # response is printed: they carry credentials and PINs.
        response = requests.post(sunshine_url, data=payload, headers=headers,
                                 verify=verify, timeout=10, allow_redirects=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to send PIN: {e}")

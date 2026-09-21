#!/usr/bin/env python3
"""
generate-openapi.py — Generate OpenAPI spec from the FastAPI proxmox_backend.

Usage:
    python3 scripts/generate-openapi.py

Requires FastAPI and project dependencies installed.
Output: coffeepie_backend/proxmox_backend/openapi.json

Run this after changing any route, model, or schema in the proxmox_backend.
The generated spec is checked into git so it's always available without
running the server. CI validates it hasn't drifted.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "coffeepie_backend" / "proxmox_backend"

def main():
    os.chdir(str(BACKEND))
    sys.path.insert(0, str(BACKEND))

    try:
        from app.main import app
    except ImportError as e:
        print(f"ERROR: Cannot import FastAPI app. Install dependencies first:")
        print(f"  pip install -r {BACKEND}/requirements.txt")
        print(f"  ({e})")
        sys.exit(1)

    spec = app.openapi()
    spec["info"]["description"] = (
        "Proxy for Proxmox VE API with Firebase authentication "
        "and Sunshine streaming integration. All /nodes/ endpoints "
        "require Bearer token authentication."
    )
    spec["info"]["version"] = "0.1.0"
    spec["info"]["contact"] = {
        "name": "Coffee Pie Engineering",
        "email": "security@coffeepie.co",
        "url": "https://coffeepie.co",
    }

    output_path = BACKEND / "openapi.json"
    with open(output_path, "w") as f:
        json.dump(spec, f, indent=2)

    print(f"✓ OpenAPI spec written to {output_path}")
    print(f"  {len(spec['paths'])} endpoints across {len(spec['tags'])} tag groups")


if __name__ == "__main__":
    main()

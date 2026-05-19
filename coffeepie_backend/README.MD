# Proxmox Management API

This project provides a FastAPI-based RESTful API for managing Proxmox Virtual Machines (VMs) and Containers (CTs). It includes endpoints for creating, cloning, updating, listing, and controlling VMs and CTs.

## Features

- Clone VMs and CTs
- Create new VMs and CTs
- List all VMs and CTs
- Update VM configurations
- Delete VMs
- Start, stop, shutdown, and reboot VMs and CTs

## Project Structure


app/ __init__.py main.py controllers/ proxmox_controller.py models/ proxmox_models.py services/ proxmox_service.py README.MD

## API Endpoints
VM Operations
Clone VM: POST /clone-vm
Create VM: POST /create-vm
List VMs: GET /vms
Update VM: POST /update-vm
Delete VM: POST /delete-vm
Control VM: POST /control-vm/{action}
CT Operations
Clone CT: POST /clone-ct
Create CT: POST /create-ct
List CTs: GET /cts
Control CT: POST /control-ct/{action}
Requirements
Python 3.8+
Proxmox CLI tools (qm, pct) installed and accessible
Contributing
Contributions are welcome! Please fork the repository and submit a pull request.

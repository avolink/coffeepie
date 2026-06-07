# OpenUDS — Universal Desktop Service (Coffee Pie® Orchestrator)

OpenUDS (Universal Desktop Service) is the Coffee Pie® orchestrator — a FastAPI-based backend that brokers user sessions to virtual desktops (VMs and Containers), manages pool provisioning, and coordinates with the hypervisor layer. It replaces Guacamole with Sunshine/Moonlight for ultra-low latency streaming over UDP.

## Architecture

The orchestrator sits between the Coffee Pie® Frontend (Codec Terminals) and the hypervisor infrastructure, brokering connections without proxying media streams. Video/audio flows direct P2P between VM and terminal via Sunshine → Moonlight over UDP.

```
Codec Terminal → [TCP: Orchestrator API] → Proxmox Backend → Proxmox Hosts
                 [UDP: Sunshine/Moonlight direct P2P stream]
```

## Features

- VM and Container lifecycle management (create, clone, delete, start, stop, reboot)
- User session brokering — authenticated desktop assignment
- Pool provisioning and resource scheduling (via QFDM)
- Direct UDP streaming handoff (Sunshine ↔ Moonlight)
- Integrated payment processing (PSE, Bancolombia QR, Bre-B)
- Provider-tier settlement and COFP token economics

## Project Structure

```
coffeepie_backend/
├── app/                        # OpenUDS orchestrator (FastAPI)
│   ├── main.py                 # FastAPI app entry point
│   ├── controllers/            # API route handlers
│   │   └── proxmox_controller.py
│   ├── models/                 # Pydantic request/response models
│   │   └── proxmox_models.py
│   └── services/               # Business logic (VM/CT operations)
│       └── proxmox_service.py
├── proxmox_backend/            # Proxmox hypervisor connector
│   └── README.md
├── payments/                   # Payment processing
│   ├── services.py
│   ├── webhook.py
│   ├── models.py
│   └── backends/
│       ├── pse.py              # PSE (Colombia ACH)
│       ├── bancolombia.py      # Bancolombia QR
│       └── breb.py             # Bre-B instant transfers
├── sunshine/                   # Sunshine streaming server (forked)
├── requirements.txt
└── README.md
```

## API Endpoints

### VM Operations
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/clone-vm` | Clone an existing VM |
| POST | `/create-vm` | Create a new VM |
| GET  | `/vms` | List all VMs |
| POST | `/update-vm` | Update VM configuration |
| POST | `/delete-vm` | Delete a VM |
| POST | `/control-vm/{action}` | Start, stop, shutdown, reboot a VM |
| GET  | `/vm/{vmid}/network` | Get VM network information |

### CT Operations
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/clone-ct` | Clone an existing Container |
| POST | `/create-ct` | Create a new Container |
| GET  | `/cts` | List all Containers |
| POST | `/control-ct/{action}` | Start, stop, shutdown, reboot a CT |

## Requirements

- Python 3.8+
- Proxmox CLI tools (`qm`, `pct`) installed and accessible on the host
- Sunshine streaming server (included in `sunshine/`)
- uvicorn for ASGI serving

## Running

```bash
cd coffeepie_backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Related Components

- **Proxmox Backend** (`proxmox_backend/`): Refactored FastAPI backend with Firebase auth, Sunshine integration, and extended Proxmox operations.
- **DC Agent** (`coffeepie_orchestrator/dc-agent/`): Rust Axum server for hypervisor abstraction and Slice management at datacenter scale.
- **Coffee Pie® Qt Frontend**: Kiosk-mode GUI running on Codec Terminals, connecting to this orchestrator via TCP credentials + UDP streaming.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request. See the main [LICENSE](/LICENSE) for licensing terms.

Coffee Pie® — Democratizing computing power.

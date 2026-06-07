# Coffee Pie API Reference

Base URLs depend on deployment. Development defaults:

| Service | Base URL | Auth |
|---------|----------|------|
| Orchestrator (Django) | `http://localhost:8000` | Session (CSRF) / Bearer token |
| DC Agent (Rust) | `http://localhost:9090` | `Authorization: Bearer <token>` for mutations |
| Actor (Rust) | `ws://localhost:43910` | Login via WebSocket message |
| Proxmox Backend (FastAPI) | `http://localhost:8001` | Firebase Bearer token |

---

## 1. Orchestrator API (Django REST)

OpenUDS-forked orchestrator. Manages users, services, transports, and sessions.

### 1.1 Authentication

```
POST /uds/rest/auth/login
Content-Type: application/json

{
    "username": "admin",
    "password": "***"
}

Response 200:
{
    "result": "ok",
    "user": { "id": 1, "name": "admin", "role": "admin" }
}
```

Session cookies are set automatically. For API tokens, use Django REST framework token auth.

### 1.2 Transports

Transports are auto-discovered Python modules under `server/src/uds/transports/<Name>/`.

```
GET /uds/rest/transports/

Response 200:
[
    {
        "id": "TSunshine",
        "name": "Sunshine RDP Transport",
        "type": "sunshine",
        "protocol": "sunshine",
        "is_base": false,
        "own_link": false,
        "description": "Hardware-accelerated streaming via Sunshine/Moonlight"
    },
    {
        "id": "TGuacamole",
        "name": "Guacamole HTML5 Transport",
        "type": "guacamole",
        "protocol": "guacamole",
        "is_base": false,
        "own_link": false,
        "description": "HTML5 fallback transport (deprecated for new deployments)"
    }
]
```

### 1.3 Services

```
GET /uds/rest/services/

Response 200:
[
    {
        "id": 1,
        "name": "Coffee Pie Basic Desktop",
        "pool_id": 1,
        "state": "active",
        "slices": 4,
        "os": "debian-12-coffeepie"
    }
]
```

### 1.4 Sessions

```
GET /uds/rest/sessions/
Authorization: Bearer <token>

Response 200:
[
    {
        "id": 101,
        "user": "avolink",
        "service": "Coffee Pie Basic Desktop",
        "state": "active",
        "transport": "TSunshine",
        "ip": "10.0.0.50",
        "started_at": "2026-05-30T14:00:00Z"
    }
]
```

### 1.5 Session Lifecycle

```
POST /uds/rest/sessions/
Content-Type: application/json

{
    "service_id": 1,
    "transport_id": "TSunshine"
}

Response 201:
{
    "id": 102,
    "state": "preparing",
    "ticket": "abc123def456",
    "connection_params": {
        "host": "10.0.0.50",
        "port": 47989,
        "pin": "1234"
    }
}
```

```
DELETE /uds/rest/sessions/102/

Response 200:
{ "result": "ok", "state": "removed" }
```

### 1.6 Users & Providers

```
GET  /uds/rest/users/           # List users
POST /uds/rest/users/           # Create user
GET  /uds/rest/providers/       # List registered providers
POST /uds/rest/providers/       # Register new provider
```

---

## 2. DC Agent API (Rust — axum)

Hypervisor abstraction layer. Queries real (or mock) Proxmox for capacity, node lists, and VM operations.

**Auth:** `Authorization: Bearer <DC_AGENT_AUTH_TOKEN>` required on mutation endpoints (POST/PUT/DELETE). GET endpoints are read-only and may not require auth in internal L2/L3 networks.

### 2.1 Health

```
GET /health

Response 200:
{
    "status": "ok",
    "agent_id": "dc-agent-us-east-1",
    "timestamp": 1717000000,
    "hypervisor": "proxmox",
    "version": "0.1.0"
}
```

### 2.2 Capacity

```
GET /capacity

Response 200:
{
    "result": {
        "total_slices": 1024,
        "available_slices": 856,
        "total_nodes": 4,
        "online_nodes": 4,
        "total_vms": 64,
        "running_vms": 42
    }
}
```

### 2.3 Nodes

```
GET /api/v1/nodes

Response 200:
{
    "nodes": [
        { "name": "pve-A", "status": "online", "cpu_threads": 64, "ram_gb": 256 },
        { "name": "pve-B", "status": "online", "cpu_threads": 64, "ram_gb": 256 }
    ]
}
```

### 2.4 VM Operations

```
GET    /api/v1/nodes/{node}/vms              # List all VMs on node
POST   /api/v1/nodes/{node}/vms              # Create VM (requires auth)
GET    /api/v1/nodes/{node}/vms/{vmid}        # Get VM details
POST   /api/v1/nodes/{node}/vms/{vmid}/start  # Start VM (requires auth)
POST   /api/v1/nodes/{node}/vms/{vmid}/stop   # Stop VM (requires auth)
DELETE /api/v1/nodes/{node}/vms/{vmid}        # Destroy VM (requires auth)
```

**Create VM:**
```
POST /api/v1/nodes/pve-A/vms
Authorization: Bearer <token>
Content-Type: application/json

{
    "template": "debian-12-coffeepie",
    "slices": 4,
    "vmid": 200
}

Response 201:
{
    "result": { "vmid": 200, "status": "created" }
}
```

**Start VM:**
```
POST /api/v1/nodes/pve-A/vms/200/start
Authorization: Bearer <token>

Response 200:
{
    "result": { "vmid": 200, "status": "running" }
}
```

### 2.5 Error Responses

All errors follow a consistent format:

```
{
    "error": {
        "code": "VM_NOT_FOUND",
        "message": "VM 999 not found on node pve-A"
    }
}
```

Error codes: `INVALID_INPUT`, `VM_NOT_FOUND`, `NODE_NOT_FOUND`, `UNAUTHORIZED`, `HYPERVISOR_ERROR`, `INTERNAL_ERROR`.

---

## 3. Actor WebSocket Protocol (Rust)

The Actor runs on each VM, connecting to the orchestrator via WebSocket.
It manages Sunshine streaming lifecycle: start, stop, screenshot, ping.

### 3.1 Connection

```
ws://<orchestrator>:8000/ws/actor/
```

The actor authenticates via a `LoginRequest` message containing credentials.

### 3.2 Message Types

All messages are JSON over WebSocket. Message envelope:

```json
{
    "type": "RpcMessage",
    "id": 1,
    "payload": { ... }
}
```

| Type | Direction | Description |
|------|-----------|-------------|
| `LoginRequest` | Actor → Orch | Authenticate with credentials |
| `Ping` | Orch → Actor | Health check (actor echoes back as `Pong`) |
| `Pong` | Actor → Orch | Response to Ping |
| `ScreenshotRequest` | Orch → Actor | Request a VM screenshot |
| `ScreenshotResponse` | Actor → Orch | Screenshot bytes (base64) |
| `LogoffRequest` | Orch → Actor | Graceful user session termination |
| `ScriptExecRequest` | Orch → Actor | Execute a script/command on VM |
| `ScriptExecResponse` | Actor → Orch | Script output |
| `MessageRequest` | Orch → Actor | Display message to user |
| `PreConnect` | Orch → Actor | Prepare Sunshine for incoming connection |
| `Close` | Either | Close WebSocket connection |

### 3.3 Login

```json
{
    "type": "RpcMessage",
    "id": 1,
    "payload": {
        "type": "LoginRequest",
        "username": "vm-agent-001",
        "password": "***",
        "vm_id": 200
    }
}
```

### 3.4 Screenshot Flow

```
Orch → Actor:  {"type": "ScreenshotRequest", "id": 42}
Actor → Orch:  {"type": "ScreenshotResponse", "id": 42, "image": "<base64>", "format": "png"}
```

### 3.5 Health Ping

```
Orch → Actor:  {"type": "Ping", "id": 0, "payload": [0x01, 0x02, 0x03]}
Actor → Orch:  {"type": "Pong", "id": 0, "payload": [0x01, 0x02, 0x03]}
```

Actor must respond within 5 seconds. Three consecutive timeouts → session marked as dead.

---

## 4. Proxmox Backend API (FastAPI)

Internal service between DC Agent and real Proxmox hypervisor.

**Auth:** Firebase Bearer token (`Authorization: Bearer <firebase_id_token>`).

```
GET  /api2/json/nodes                         # List Proxmox nodes
GET  /api2/json/nodes/{node}/qemu              # List VMs on node
GET  /api2/json/nodes/{node}/qemu/{vmid}/status/current  # VM status
POST /api2/json/nodes/{node}/qemu/{vmid}/status/start    # Start VM
POST /api2/json/nodes/{node}/qemu/{vmid}/status/stop     # Stop VM
POST /api2/json/nodes/{node}/qemu/{vmid}/status/reset    # Reset VM
POST /api2/json/nodes/{node}/qemu              # Create VM
DELETE /api2/json/nodes/{node}/qemu/{vmid}     # Destroy VM
```

---

## 5. Port Map

| Port | Protocol | Service | Required |
|------|----------|---------|----------|
| 22 | TCP | SSH | Yes |
| 443 | TCP | Orchestrator HTTPS | Yes |
| 8000 | TCP | Orchestrator (dev) | Dev only |
| 9090 | TCP | DC Agent | Yes |
| 43910 | TCP | Actor | Yes |
| 47984 | TCP | Sunshine HTTPS/WS | Yes |
| 47989 | TCP | Sunshine HTTP/Control | Yes |
| 47990 | TCP | Sunshine Streaming | Yes |
| 47998-48002 | UDP | Moonlight Streaming | Yes |
| 48010 | TCP+UDP | Sunshine GameStream | Yes |
| 5432 | TCP | PostgreSQL | Internal |
| 6379 | TCP | Redis | Internal |

---

## 6. Versioning & Compatibility

- API versioning: URL-prefix based (`/api/v1/`, `/api/v2/`)
- Backward compatibility: V1 endpoints preserved for 12 months after V2 release
- Breaking changes: announced 90 days in advance via `AGENTS.md` changelog
- Deprecation header: `X-API-Deprecated: true` on sunset endpoints

---

*Last updated: 2026-05-30*
*Maintainer: Coffee Pie Contributors*

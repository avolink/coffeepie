# Coffee Pie DC Agent

Hypervisor-agnostic datacenter orchestration agent. Runs at each datacenter, abstracts the hypervisor behind a uniform REST API, and reports capacity to the central QFDM broker via heartbeat.

## Architecture

```
  QFDM Broker                   DC Agent (this)                 Hypervisor
  ┌──────────┐     heartbeat     ┌──────────────┐     REST      ┌────────────┐
  │  Django  │◄─────────────────│  axum HTTP    │──────────────►│ proxmox_   │
  │  orch.   │   GET /capacity   │  server :9090 │               │ backend    │
  │          │──►POST /instances │  adapter      │               │ FastAPI    │
  └──────────┘                   └──────────────┘               └─────┬──────┘
                                                                      │
                                                               ┌──────▼──────┐
                                                               │  Proxmox VE │
                                                               │  VMware     │
                                                               │  KVM/QEMU   │
                                                               │  ...        │
                                                               └─────────────┘
```

The DC Agent never talks to hypervisors directly. It calls the hypervisor management API (e.g., proxmox_backend FastAPI) which handles authentication and hypervisor-specific logic. Adding a new hypervisor type means implementing the `HypervisorAdapter` trait — the REST API and broker integration stay identical.

## Prerequisites

- Rust 1.85+ (edition 2024)
- A running hypervisor management API:
  - **Proxmox**: [proxmox_backend](../proxmox_backend/) FastAPI service
  - **KVM/QEMU**: (adapter coming soon)
  - **VMware**: (adapter coming soon)
- (Optional) A QFDM broker to receive heartbeat reports

## Quick Start

```bash
# 1. Clone and enter the dc-agent directory
cd coffeepie_orchestrator/dc-agent

# 2. Copy and fill in the environment config
cp .env.example .env
# Edit .env with your tokens and URLs

# 3. Build
cargo build --release

# 4. Run
./target/release/coffeepie-dc-agent
```

## Configuration

All configuration is via environment variables (or a `.env` file):

| Variable | Required | Default | Description |
|---|---|---|---|
| `DC_AGENT_BIND` | No | `0.0.0.0:9090` | Bind address for the HTTP server |
| `DC_AGENT_HYPERVISOR` | No | `proxmox` | Hypervisor type (`proxmox`, `vmware`, `qemu-kvm`, etc.) |
| `DC_AGENT_BACKEND_URL` | Yes | `https://proxmox-api.dc1.lan` | Base URL of the hypervisor management API |
| `DC_AGENT_BEARER_TOKEN` | Yes | (none) | Firebase ID token or API key for the management API |
| `DC_AGENT_ID` | No | `dc-agent-<uuid>` | Unique identifier for this agent instance |
| `QFDM_BROKER_URL` | No | (none) | Central QFDM broker URL for heartbeat; omit for standalone mode |
| `RUST_LOG` | No | `coffeepie_dc_agent=info` | Tracing log filter |

## REST API

### `GET /health`
Liveness check. Returns service version.

```bash
curl http://localhost:9090/health
# {"status":"ok","service":"coffeepie-dc-agent","version":"0.1.0"}
```

### `GET /capacity`
Current datacenter capacity. Called by the QFDM broker to decide where to place slices.

```bash
curl http://localhost:9090/capacity
# {"result":{"agent_id":"dc-agent-us-east-1","timestamp":1717000000,...}}
```

### `GET /templates`
Available OS templates for provisioning.

```bash
curl http://localhost:9090/templates
# {"result":["windows-11@node1","ubuntu-24.04@node1"]}
```

### `POST /instances`
Create a new VM slice. Returns a `SliceHandle` with streaming credentials.

```bash
curl -X POST http://localhost:9090/instances \
  -H "Content-Type: application/json" \
  -d '{
    "spec": {"cpu_cores": 4, "ram_gb": 8, "ssd_gb": 32, "hdd_gb": 500, "net_mbps": 32, "gpu_mb": 500, "res_vmpx_s": 60, "ai_tops": 12},
    "user_id": "user-abc-123",
    "template": "ubuntu-24.04@node1"
  }'
# {"result":{"handle":{"instance_id":"a1b2c3d4-...","provider_vm_id":"cp-a1b2c3d4-...","sunshine_endpoint":{"ip":"10.0.0.55","api_port":47990,...}}}}
```

### `DELETE /instances/{instance_id}`
Destroy a VM slice. Requires `provider_vm_id` and `node` in the JSON body.

```bash
curl -X DELETE http://localhost:9090/instances/a1b2c3d4 \
  -H "Content-Type: application/json" \
  -d '{"provider_vm_id": "cp-a1b2c3d4", "node": "node1"}'
# {"result":"Instance destroyed"}
```

### `POST /instances/{instance_id}/start`
Start a stopped instance.

### `POST /instances/{instance_id}/stop`
Stop a running instance.

## Production Deployment

### systemd

```bash
# Copy binary and config
sudo mkdir -p /opt/coffeepie/dc-agent
sudo cp target/release/coffeepie-dc-agent /opt/coffeepie/dc-agent/
sudo cp .env /opt/coffeepie/dc-agent/

# Install and start the service
sudo cp coffeepie-dc-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now coffeepie-dc-agent

# Check status
sudo systemctl status coffeepie-dc-agent
journalctl -u coffeepie-dc-agent -f
```

## Adding a New Hypervisor Adapter

1. Create `src/adapters/vmware.rs` (or `kvm.rs`, `xcpng.rs`, etc.)
2. Implement the `HypervisorAdapter` trait:

```rust
#[async_trait]
impl HypervisorAdapter for VMwareAdapter {
    fn adapter_type(&self) -> &str { "vmware" }
    async fn list_templates(&self) -> Result<Vec<String>> { ... }
    async fn get_capacity(&self) -> Result<CapacityReport> { ... }
    async fn create_instance(&self, request: CreateSliceRequest) -> Result<SliceHandle> { ... }
    async fn destroy_instance(&self, instance_id: &str, provider_vm_id: &str, node: &str) -> Result<()> { ... }
    async fn start_instance(&self, provider_vm_id: &str, node: &str) -> Result<()> { ... }
    async fn stop_instance(&self, provider_vm_id: &str, node: &str) -> Result<()> { ... }
    async fn get_instance_state(&self, provider_vm_id: &str, node: &str) -> Result<InstanceState> { ... }
    async fn get_instance_ip(&self, provider_vm_id: &str, node: &str) -> Result<String> { ... }
    async fn get_sunshine_endpoint(&self, handle: &SliceHandle) -> Result<SunshineEndpoint> { ... }
}
```

3. Register it in `src/adapters/mod.rs`:

```rust
"vmware" => Ok(Box::new(vmware::VMwareAdapter::new(...))),
```

4. Set `DC_AGENT_HYPERVISOR=vmware` and restart.

The REST API, heartbeat, and broker integration stay identical — the adapter is a drop-in implementation detail.

## License

BSD-3-Clause. See the license header in each source file.

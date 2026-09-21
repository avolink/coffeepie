# Coffee Pie Tools

Command-line tools for the Coffee Pie QFDM Ecosystem, organized by category.

Each category is a standalone Cargo workspace. Build individually:

```bash
cd tools/benchmark  && cargo build --release
cd tools/security   && cargo build --release
cd tools/dev        && cargo build --release
```

## Categories

### `benchmark/` — Performance & Capacity Testing
Tools for measuring latency, bandwidth, storage, and streaming capacity.
Essential for datacenter operators before joining the QFDM Network.

| Tool | Purpose |
|------|---------|
| `latency-test` | RTT, jitter, packet loss, QFDM grading |
| `coffeepie-slices-calc` | Max slices from hardware specs, bottleneck detection |
| `storage-sync-speed` | File sync speed estimates (cloud → terminal) |
| `bandwidth-bench` | TCP throughput (client/server) |
| `network-health` | DNS, TCP, MTU, hops, QFDM readiness assessment |
| `disk-iops-bench` | Random/sequential I/O, VM capacity planning |
| `streaming-capacity` | GPU encode sessions (NVENC/VAAPI/AMF) |

### `security/` — Cryptography & Hardening
Key generation, audit helpers, and security configuration tools.

| Tool | Purpose |
|------|---------|
| `coffeepie-keygen` | Ed25519 + ML-KEM-768 key generation for deployments |
| `coffeepie-harden` | CIS-inspired hardening for Debian nodes (kernel, SSH, firewall, audit) |
| `coffeepie-audit` | Security posture scanner — CVEs, open ports, misconfigs, scoring |

### `dev/` — Development & Quality
| Tool | Purpose |
|------|---------|
| `translations-validator` | Validate translations.json (completeness, corruption, identifiers) |
| `product-sync` | Sync Avo store catalog ↔ productos.json |
| `schema-gen` | Generate JSON Schema from Rust types for API validation |

### `admin/` — Deployment & Operations
| Tool | Purpose |
|------|---------|
| `coffeepie-deploy` | One-command orchestrator + actor + Sunshine bootstrap |
| `coffeepie-billing` | Credit calculator, invoice preview, COFP conversion, revenue projection |
| `coffeepie-payment-test` | Simulate & validate Bre-B, PSE, Bancolombia QR payment flows |
| `coffeepie-provider-onboard` | Interactive wizard for new datacenter providers — capacity calc + registration |

### `monitoring/` — Daemons & Alerts
| Tool | Purpose |
|------|---------|
| `coffeepie-healthd` | Health check daemon (6 services, Prometheus metrics, alerting) |
| `coffeepie-loadgen` | Simulate N concurrent QFDM users — full pipeline stress test |
| `coffeepie-stream-monitor` | Real-time Sunshine stream quality: FPS, bitrate, drops, latency |

## Conventions

- All tools support `--json` for machine-readable output
- `--help` on any tool shows full usage
- Output designed for both human readability and pipeline processing (`| jq`)
- ARM64 cross-compilation supported (`--target aarch64-unknown-linux-gnu`)

## Adding a new tool

1. Choose or create the right category folder
2. Add `[[bin]]` entry to the category's `Cargo.toml`
3. Create `src/bin/<tool-name>.rs`
4. Follow existing patterns: `clap` for CLI, `--json` flag, clear output sections
5. Update this README

## License

MIT OR Apache-2.0 — same as Coffee Pie project.

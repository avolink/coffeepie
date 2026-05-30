# Coffee Pie Benchmark Tools

Diagnostic and capacity-planning tools for the Coffee Pie QFDM Ecosystem.
Built in Rust for speed and zero-dependency deployment on any Linux system.

## Quick Start

```bash
cd benchmark-tools
cargo build --release

# Run any tool:
./target/release/latency-test coffeepie.co
./target/release/coffeepie-slices-calc --cpu-threads 256 --ram-gb 1024 --ssd-gb 4096
./target/release/storage-sync-speed --size-mb 1024
./target/release/bandwidth-bench --server &
./target/release/network-health coffeepie.co
./target/release/disk-iops-bench --size-mb 1024
./target/release/streaming-capacity --vendor nvidia --model A4000
```

All tools support `--json` for machine-readable output.

---

## Tools

### `latency-test` — Network Latency & Jitter

Measures RTT, jitter, packet loss, and percentile latency to any endpoint.
Determines QFDM grade (Excellent → Unusable) based on Coffee Pie thresholds.

```bash
latency-test <target> [--count 100] [--interval 100] [--size 64]
latency-test orchestrator.coffeepie.co:43910 --count 200 --json
```

**QFDM Grades:**
| Grade | Latency | Jitter | Use Case |
|-------|---------|--------|----------|
| Excellent | <5ms | <2ms | L2 direct connection |
| Great | <15ms | <5ms | 4K60 gaming/streaming |
| Good | <50ms | <15ms | 1080p60 desktop |
| Acceptable | <100ms | — | Office/productivity |
| Poor | >100ms | — | Not recommended |

### `coffeepie-slices-calc` — Datacenter Slice Calculator

Core planning tool for datacenter operators. Given hardware specs, calculates
maximum simultaneous Coffee Pie slices and identifies the primary bottleneck.

```bash
coffeepie-slices-calc \
  --cpu-threads 512 --ram-gb 2048 \
  --ssd-gb 8192 --hdd-gb 65536 \
  --gpu-vram-mb 65536 --net-mbps 40960 \
  --overcommit-cpu 4 --overcommit-ram 1.5 \
  --vmp-res 0 --ai-tops 0
```

**Coffee Pie Slice Specs (reference):**
| Resource | Per Slice |
|----------|-----------|
| CPU | 1 vCore |
| RAM | 1 GB |
| SSD | 8 GB |
| HDD | 125 GB |
| GPU VRAM | 125 MB |
| Network | 8 Mbps |
| Render | 15 vMPX/s |
| AI | 3 TOPS (INT8) |

### `storage-sync-speed` — File Sync Benchmark

Measures read, write, and random I/O speeds to estimate real-world sync times
between cloud VM instances and codec terminals. Simulates multi-file project
syncs.

```bash
storage-sync-speed --size-mb 1024 --bandwidth-mbps 100
storage-sync-speed --size-mb 512 --iterations 5 --json
```

Outputs estimated sync times for:
- 1 GB document
- 10 GB media project
- 100 GB backup
- 1 TB full system sync

### `bandwidth-bench` — TCP Throughput Test

Measures raw TCP throughput between two points. Helps validate network capacity
for planned slice counts (each slice = 8 Mbps).

**Server mode:**
```bash
bandwidth-bench --server --bind 0.0.0.0:9090 --duration 30
```

**Client mode:**
```bash
bandwidth-bench --target 192.168.1.10:9090 --duration 30
```

### `network-health` — Comprehensive Network Diagnostic

All-in-one network health check for QFDM readiness. Tests:
1. DNS resolution time
2. TCP connectivity to orchestrator port
3. MTU discovery
4. Network path (hop count)
5. Packet loss and jitter

```bash
network-health coffeepie.co --port 443 --count 50
network-health 192.168.1.100:43910 --json
```

### `disk-iops-bench` — Storage IOPS Benchmark

Measures random read/write IOPS and sequential throughput for VM storage
provisioning. Estimates how many VMs a storage subsystem can support.

```bash
disk-iops-bench --size-mb 1024 --block-kb 4 --io-count 10000
disk-iops-bench --dir /mnt/nvme --size-mb 4096 --json
```

**IOPS per VM (estimated):**
| Workload | IOPS/VM |
|----------|---------|
| Light (office) | 50 |
| Medium (dev) | 200 |
| Heavy (gaming) | 500+ |

### `streaming-capacity` — GPU Encode Capacity

Calculates how many simultaneous Sunshine/Moonlight streams a GPU can encode.
Considers hardware encoder session limits (NVENC/VAAPI/AMF) and resolution.

```bash
streaming-capacity --vendor nvidia --model A4000
streaming-capacity --vendor amd --model MI300X --codec av1 --resolution 4K
streaming-capacity --vendor intel --model "Arc A770"
```

**Supported Vendors:** nvidia, amd, intel, apple, qualcomm

---

## Integration with QFDM Backend

All tools output JSON (`--json` flag) for integration into:
- Datacenter provisioning dashboards
- CI/CD pipeline validation
- Automated capacity planning
- Monitoring/alerting systems

Example parsing:
```bash
# Get max slices
coffeepie-slices-calc --cpu 512 --ram 2048 --json | jq '.max_slices'

# Check if network is QFDM-ready
network-health coffeepie.co --json | jq '.qfdm_readiness'
```

---

## Building for Codec Terminals (ARM64)

```bash
rustup target add aarch64-unknown-linux-gnu
cargo build --release --target aarch64-unknown-linux-gnu
```

---

## License

MIT OR Apache-2.0 — same as Coffee Pie project.

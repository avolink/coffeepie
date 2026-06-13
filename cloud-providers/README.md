# Cloud Providers — QFDM Network

## Overview

Cloud Providers supply computing resources (CPU, GPU, RAM, storage, bandwidth)
to the QFDM Network. These resources are quantized into "Slices" and delivered
to end users via Codec Terminals with ultra-low-latency streaming (Sunshine →
Moonlight over UDP). Patent: NC2025/0012723.

If you operate a datacenter, server farm, gaming cafe, university lab, or
even a single high-powered workstation, you can contribute capacity to the
network and earn COFP tokens in return.

## Why Become a Provider?

| Benefit | Detail |
|---|---|
| Monetize idle hardware | Turn spare GPU/CPU cycles into revenue |
| Predictable settlement | Burn COFP for fiat via bank transfer (24–72 h) |
| No burning cap | Providers sell real resources — unlimited settlement |
| Governance rights | Vote on regional pricing (slice cost, electricity rates, labor costs) |
| Circular economy aligned | Contribute to reducing global electronic waste |
| Flexible scale | From a single node to thousands — you decide |

## Hardware Requirements

### Minimum Node Specifications

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 4 vCores (x86-64 or ARM64) | 8 vCores |
| RAM | 8 GB | 16 GB per GPU |
| GPU | 2 GB VRAM, NVENC/VAAPI/AMF encode | 6+ GB VRAM |
| Storage (VM) | 64 GB SSD (OS + user data) | 128 GB NVMe |
| Network | 100 Mbps symmetric | 1 Gbps symmetric |
| OS | Linux (Debian/Ubuntu preferred) | Debian 12 |

### GPU Encoding Support

| Vendor | Technology | Notes |
|---|---|---|
| NVIDIA | NVENC (Kepler+) | Best quality, lowest latency. GTX 1050+ or Tesla T4+ |
| Intel | QSV (Quick Sync) | Broadwell+ iGPUs. Good for density |
| AMD | AMF/VCE | Supported via VAAPI. RX 500+ series |
| Huawei Ascend | VAAPI fallback | Verify Sunshine compatibility before deploying |

### Network Requirements

- Static private IP within the QFDM network (stretched VLAN)
- UDP ports 47984–48010 open to codec terminals (Sunshine streaming)
- TCP port 43910 (Actor daemon) reachable by orchestrator
- Outbound HTTPS to orchestrator
- No NAT traversal needed (all hosts directly reachable at private IPs)

## How It Works

```
Your Server (GPU node)
  ├── Proxmox VE (hypervisor)
  ├── VMs (Windows/Linux desktops, one per user slice)
  ├── Sunshine (GPU-accelerated streaming host, per VM)
  └── Coffee Pie Actor (Rust daemon, port 43910)
        └── Connects to Orchestrator (Django)
              └── Brokers sessions: Codec Terminal ↔ VM
```

1. You provision VM templates on your Proxmox host
2. Install the Coffee Pie Actor (Rust daemon) — handles VM lifecycle
   (start, stop, snapshot, health check)
3. Register your node with the Coffee Pie Orchestrator
4. The Orchestrator routes users to VMs on your host based on latency
   (nearest node wins)
5. Streaming goes direct P2P between VM and Codec Terminal (UDP) — the
   orchestrator does NOT proxy the stream
6. You earn **1 COFP per Slice per minute** of verified compute delivered (e.g., 4 Slices active for 60 minutes = 240 COFP)

## Slice Economics

A "Slice" is the base unit of compute in QFDM:

| Resource | Per Slice |
|---|---|
| CPU | 1 vCore |
| RAM | 1 GB |
| SSD | 8 GB |
| Network | 8 Mbps |
| HDD | 125 GB |
| GPU | 125 MB VRAM |
| Resolution | 15 vMPX/s |
| AI | 3 TOPS (INT8) |
| Power | 1 Wh/hour max |

One physical server typically hosts **dozens to hundreds** of slices.
A server with 32 vCores, 128 GB RAM, and 2 GPUs can serve ~25 concurrent
mid-tier users or ~50 basic users.

## Revenue Model

### Earning COFP

Providers earn COFP at a rate of **1 COFP per Slice per minute** of verified capacity delivered. Example: a node serving 10 Slices for 8 hours earns 10 × 8 × 60 = 4,800 COFP. The rate in fiat equivalent is set by community governance (providers vote on regional pricing considering electricity costs, labor costs, and market rates). Note: end users (consumers) never interact with COFP — they pay for Slices using Coffee Pie® Credits (Cr), obtained via Ads or Credit Package purchases.

### Settling to Fiat

1. COFP accumulates in your provider wallet (on-chain, TRC-20)
2. Request fiat withdrawal via the Coffee Pie backend
3. Tokens are burned via `burnFrom()` — supply decreases
4. Fiat is transferred to your registered bank account within 24–72 hours
5. **No burning cap** — providers are selling real resources, not speculating

### Important: Token Rights

- Provider-earned COFP is linked to your registered provider account
- If you transfer COFP to a secondary wallet and sell on the open market,
  those tokens **permanently lose** voting and burn-for-fiat rights
- The buyer receives an Investor-class token (economic rights only, no
  governance vote)

## Getting Started

### 1. Apply

Visit https://www.coffeepie.co/panel (Provider Tab) and submit your
infrastructure details:
- Node count and specs (CPU, RAM, GPU, storage)
- Network capacity and latency profile
- Location (city, country)
- Expected availability (24/7 vs. scheduled windows)

### 2. Onboarding

After approval, you receive:
- Coffee Pie Actor binary and configuration
- Proxmox VM template (pre-configured Windows/Linux with Sunshine)
- API credentials for the Orchestrator
- Region assignment and IP range allocation

### 3. Integration

```bash
# Install Coffee Pie Actor on each Proxmox host
curl -sSL https://api.coffeepie.co/v1/actor/install | bash

# Configure
coffeepie-actor init \
  --orchestrator https://orchestrator.coffeepie.co \
  --region latam-bog \
  --api-key YOUR_API_KEY

# Start
systemctl enable --now coffeepie-actor
```

### 4. Verification

Once connected, your node appears in the Orchestrator dashboard. The system
runs automated health checks (GPU encoding test, latency benchmark, VM
provisioning test) before routing production traffic.

## Monitoring

- Real-time dashboard: https://www.coffeepie.co/panel
- Metrics: slice-hours, active users, GPU utilization, encoding latency,
  power consumption, COFP earnings
- Alerts: node offline, GPU encoding failure, capacity threshold reached,
  unusual power draw (potential cryptomining abuse)

## Compliance

- **No cryptomining**: mining cryptocurrency on QFDM infrastructure is
  strictly prohibited. Automated power draw monitoring flags abuse within
  minutes. Violators are permanently suspended.
- **No malicious content**: spamming, DDoS, or serving illegal content
  results in immediate suspension.
- **Data sovereignty**: user VMs are routed to region-locked nodes
  (GDPR, LGPD, etc.). You must disclose your node's jurisdiction.
- **Power ceiling**: if an instance draws >1 Wh/hour per slice, warnings
  trigger. Repeated violations lead to account suspension.

## Provider Governance

As a provider, you vote on:
- Regional slice pricing (average cost per slice-hour)
- Electricity rate assumptions
- Labor cost baselines
- New region activation
- Technical standards (minimum node specs, GPU requirements)

Voting weight is proportional to verified slice-hours contributed.

## Provider Tiers & Fiat Settlement Margins

The fiat amount received when burning COFP = **base COFP price × (1 + tier margin)**. Higher tiers reward greater infrastructure quality, reliability, and environmental responsibility.

| Tier | Margin | Requirements | Settlement |
|---|---|---|---|
| **Tier I** | +8% | Basic connectivity, ≥99% uptime SLA | 24–72 h |
| **Tier II** | +10% | Redundant network, ≥99.5% uptime, UPS | 24–72 h |
| **Tier III** | +12% | N+1 power redundancy, ≥99.9% uptime, dedicated cooling | 24–48 h |
| **Tier IV** | +15% | 2N power redundancy, ≥99.95% uptime, physical security | 24 h |
| **Tier V** | +18% | All Tier IV requirements **+** dedicated SAN storage **+** ≥90% Renewable and/or Alternative Energy sources (solar, wind, nuclear, geothermal, etc.) | Priority (same-day) |

> Tier classification is validated by the Coffee Pie® Onboarding Team and re-audited annually. Misrepresenting energy or infrastructure certifications results in immediate tier downgrade and potential suspension.

## Contact

- Provider registration: https://www.coffeepie.co/panel
- Technical docs: https://docs.coffeepie.co (coming soon)
- Provider community: https://discord.gg/coffeepie (coming soon)
- Email: cloud-providers@coffeepie.co

Join the QFDM Network and help democratize computing power worldwide.

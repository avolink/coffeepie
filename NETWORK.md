# Coffee Pie Network Architecture

Canonical networking specification for the Coffee Pie QFDM Network.
All other documentation references this file for network addressing, topology,
and protocol standards.

## Current Standard: IPv4

Coffee Pie currently operates on **IPv4** across its L2/L3/L4 stretched VLAN
architecture. All hosts are directly reachable at private IPv4 addresses, with
no NAT traversal needed. mDNS provides service discovery across the domain.

## Roadmap: IPv8 (target 2035 or RFC maturity)

Coffee Pie has **IPv8** (IETF draft-thain-ipv8-02, published 17 April 2026)
on the roadmap for early adoption. Target: **2035**, or when the draft reaches
RFC maturity — whichever comes first.

IPv8 is currently an IETF Internet-Draft, not a ratified standard. Until it
matures, Coffee Pie continues on IPv4 with no changes. The addressing plan
and topology described below represent the **target architecture** for when
IPv8 adoption becomes viable.

### Why IPv8 (when mature)

| Feature | Future benefit to Coffee Pie |
|---------|------------------------------|
| 64-bit addressing (32-bit ASN prefix + 32-bit host) | 2^32 hosts per datacenter under a single private prefix — no collision risk |
| `127.0.0.0/8` private zones | Standardized internal addressing across all datacenters without coordination |
| IPv4 is a proper subset (prefix `0.0.0.0`) | Zero migration cost — existing infrastructure, codec terminals, and hypervisors continue working unchanged |
| Zone Server model (DHCP8, DNS8, NTP8, OAuth8, ACL8, XLATE8) | Unifies services Coffee Pie currently implements at the application layer |
| Even/odd redundancy (gateways at `.253`/`.254`) | Aligns with Coffee Pie's L2 failover assumptions |
| Integrated security (OAuth8 JWT, ACL8) | Defense-in-depth at the network layer, complementing application-layer PKI |

## Target Addressing Plan (IPv8, post-adoption)

### Private Zone: `127.0.0.0/8`

When adopted, all Coffee Pie internal infrastructure would use the IPv8
`127.0.0.0/8` private zone. This provides 2^32 host addresses per ASN —
sufficient for every VM slice, codec terminal, orchestrator instance, and
infrastructure node across all datacenters.

```
IPv8 address format:  r.r.r.r.n.n.n.n
                       └──┬───┘ └──┬───┘
                  ASN prefix    Host address
                  (32 bits)     (32 bits)

Private zone:       127.x.x.x.n.n.n.n
                     └──┬──┘ └──┬───┘
               Zone ID    Host within zone
```

### Zone Allocation (per Datacenter)

Each datacenter would get a unique Zone ID within `127.0.0.0/8`:

| Datacenter | Zone ID | IPv8 Prefix | Description |
|-----------|---------|-------------|-------------|
| DC1 (Bogotá) | `127.1` | `127.1.0.0.n.n.n.n` | Primary Colombian datacenter |
| DC2 (Medellín) | `127.2` | `127.2.0.0.n.n.n.n` | Secondary Colombian datacenter |
| DC3..N | `127.N` | `127.N.0.0.n.n.n.n` | Future expansion |

### Host Subnetting (within a Zone)

Each Zone would be subnetted by function using the third octet:

| Subnet | Range | Purpose |
|--------|-------|---------|
| Infrastructure | `127.N.0.x.x.x.x` | Orchestrator, DC Agent, Zone Servers, PostgreSQL, Redis |
| Hypervisors | `127.N.1.x.x.x.x` | Proxmox VE nodes, VMware ESXi hosts |
| VM Slices | `127.N.2.x.x.x.x` | User VM instances (Sunshine GameStream hosts) |
| Codec Terminals | `127.N.3.x.x.x.x` | Thin-client devices (SBC ARM terminals) |
| Reserved | `127.N.4-254.x.x.x.x` | Future expansion |
| Broadcast | `127.N.255.x.x.x.x` | Subnet broadcast |

### Infrastructure Address Assignments (target)

```
Zone Servers (even/odd redundancy):
  127.N.0.0.254.0.0  — Zone Server Even (gateway .254)
  127.N.0.0.253.0.0  — Zone Server Odd  (gateway .253)

Orchestrator:
  127.N.0.0.10.0.0   — Django orchestrator (primary)

DC Agent:
  127.N.0.0.20.0.0   — DC Agent (axum HTTP :9090)

Proxmox Backend:
  127.N.0.0.30.0.0   — FastAPI proxmox_backend

Tunnel Server:
  127.N.0.0.40.0.0   — UDS Tunnel Server (Rust, :4443)

PostgreSQL:
  127.N.0.0.50.0.0   — Primary database
  127.N.0.0.51.0.0   — Streaming replica

Redis:
  127.N.0.0.60.0.0   — Cache / session store
```

## Zone Server Topology (target)

Each datacenter would deploy two Zone Servers in active/active configuration:

```
┌──────────────────────────────────────────────────┐
│              DC1 (Zone 127.1)                     │
│                                                   │
│  Zone Server Even (.254)    Zone Server Odd (.253)│
│  ┌─────────────────────┐   ┌─────────────────────┐│
│  │ DHCP8  DNS8  NTP8   │   │ DHCP8  DNS8  NTP8   ││
│  │ OAuth8 ACL8 XLATE8  │   │ OAuth8 ACL8 XLATE8  ││
│  │ WHOIS8 NetLog8      │   │ WHOIS8 NetLog8      ││
│  └─────────┬───────────┘   └──────────┬──────────┘│
│            │                          │           │
│  ┌─────────▼──────────────────────────▼─────────┐ │
│  │         L2/L3/L4 Stretched VLAN              │ │
│  │  ┌────────┐ ┌────────┐ ┌────────┐           │ │
│  │  │ Orch.  │ │DC Agent│ │Tunnel  │  ...      │ │
│  │  │ :8000  │ │ :9090  │ │ :4443  │           │ │
│  │  └────────┘ └────────┘ └────────┘           │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### Zone Server Services

| Service | Function | Coffee Pie Relevance |
|---------|----------|---------------------|
| DHCP8 | Address assignment | Automatic IP allocation for VMs and terminals |
| DNS8 | Name resolution (A8 records) | Internal `.coffeepie.lan` domain resolution |
| NTP8 | Time synchronisation | Consistent timestamps for COFP ledger entries |
| OAuth8 | JWT token authentication caching | Network-layer identity, complements PKI mTLS |
| ACL8 | Access control enforcement | Free Tier vs Pay-As-You-Go network isolation |
| XLATE8 | IPv4/IPv8 translation | Backward compatibility with IPv4-only devices |
| WHOIS8 | Route validation | Prevent route hijacking on the stretched VLAN |
| NetLog8 | Telemetry collection | Network performance monitoring for provider tiers |

### Even/Odd Redundancy

- Each subnet would have two Zone Servers at `.254` (even) and `.253` (odd)
- Hosts assigned addresses matching their gateway affinity:
  - Even hosts → even gateway (`.254`)
  - Odd hosts → odd gateway (`.253`)
- Dual-NIC hosts get one even and one odd address
- **Result:** Full redundancy with zero configuration on endpoints

## IPv4 Coexistence (during and after migration)

### Backward Compatibility

IPv8 defines IPv4 as a proper subset:

```
IPv8 address with r.r.r.r = 0.0.0.0  →  IPv4 address (route on n.n.n.n)
```

- Packets with prefix `0.0.0.0` are routed using standard IPv4 rules
- No changes to existing IPv4 devices, applications, or networks
- Codec Terminals, hypervisors, and legacy infrastructure continue working

### ARP8-Driven Version Selection

An IPv8 device discovers neighbor capabilities via parallel ARP8/ARP4 probes:

1. At first contact, probe with both ARP8 and ARP4
2. Record the neighbor's protocol version in the ARP8 cache
3. **An IPv8 host MUST transmit only IPv4 packets to an IPv4-only neighbor**
4. An IPv4 device never receives a packet with version 8

### Router Downgrade

For an IPv4-only next-hop, the router downgrades at the outgoing interface:

```
Inbound:  version 8, r.r.r.r.n.n.n.n
Outbound: version 4, n.n.n.n
```

The `r.r.r.r` prefix is stripped; return traffic is reconstructed by XLATE8
on the Zone Server.

## Inter-Datacenter Communication (target)

### Cross-Zone Routing

Datacenters in different zones (e.g., DC1 `127.1` and DC2 `127.2`) would
communicate via the RINE peering prefix (`100.0.0.0/8`) or public ASN unicast
if routed over the public internet.

### Inter-Company DMZ

For Coffee Pie ↔ Provider/Partner interconnects, the standard interop prefix
`127.127.0.0` would provide a dual XLATE8 DMZ engine — both sides run their
own translation, no shared trust required.

## Migration Path

### Phase 1: Documentation (current — 2026)
- All technical docs reference IPv8 as a roadmap item, not current standard
- `NETWORK.md` established as canonical networking spec with target architecture
- Current operations continue unchanged on IPv4

### Phase 2: Standards Tracking (ongoing)
- Monitor IETF draft-thain-ipv8 progress toward RFC
- Evaluate Zone Server implementations as they emerge
- No infrastructure changes until the standard is stable

### Phase 3: Lab Prototyping (TBD, when draft stabilizes)
- Deploy Zone Server appliances in lab environment (DC1)
- Validate DHCP8 + DNS8 for infrastructure nodes
- Test OAuth8 JWT integration with existing PKI

### Phase 4: Hybrid Operation (TBD)
- Zone Servers operate alongside existing IPv4 DHCP/DNS
- Infrastructure nodes dual-addressed (IPv4 + IPv8 127.1.x.x.n.n.n.n)
- Codec Terminals remain IPv4-only (ARP8 downgrade)

### Phase 5: Full IPv8 (target: 2035 or RFC maturity)
- Zone Servers become authoritative for DHCP/DNS
- All new VM slices receive IPv8 addresses
- Legacy IPv4 infrastructure continues via XLATE8

## References

- IPv8 IETF Internet-Draft: [draft-thain-ipv8-02](https://www.ietf.org/archive/id/draft-thain-ipv8-02.html)
- IPv8 Wiki: [ipv8.wiki](https://ipv8.wiki/start/overview/)
- AGENTS.md § Core Principle 3: L2/L3/L4 Private Networks (IPv4 current, IPv8 roadmap)
- AGENTS.md § Architectural Decisions: IPv8 on roadmap for early adoption by 2035
- PKI.md: Certificate lifecycle for internal network communication
- API.md: Service endpoints and base URLs

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-06-12 | 1.0 | Initial specification (IPv8 as roadmap, IPv4 current) |

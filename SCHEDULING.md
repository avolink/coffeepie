# Coffee Pie® — Service Classes & Tier Placement

How user demand (service classes) is mapped onto provider supply (infrastructure
tiers), and how the QFDM broker decides where a Slice runs.

---

## Two axes — keep them distinct

- **Tier (supply):** a property of the *provider/datacenter* — infrastructure
  quality/redundancy/energy. Tiers I–V with settlement margins (see `PROVIDERS.md`).
  **Assigned and verified by Coffee Pie at onboarding — never self-reported** (a
  higher tier earns a higher margin, so self-declaration would be a fraud vector).
- **Service Class (demand):** a property of the *account*, derived from its plan /
  credit package. Best-effort → paid → government.

A Slice stays a deterministic quanto (1 vCore @4× overcommit, 1 GB RAM, 8 GB SSD,
125 MB GPU) regardless of tier — tiering adds a **placement/QoS dimension**, not a
bigger Slice.

## Consumer visibility — region + ping only

Tier is a **supply-side internal signal**. Consumers never see the tier (or the node
identity) of where their machines run — only the **approximate region** (e.g.
Sabaneta, Medellín, Bogotá) and the **latency/ping** (typically 10–80 ms). Which tier
serves a given workload is the offer side's concern, adapting to demand and market
conditions. No consumer-facing API or UI exposes `Tier`; the broker's consumer-facing
response carries `{ region, ping_ms }`, never `{ tier, node }`.

## Class → Tier preference (governance-tunable)

Placement is **graceful degradation**, not rigid binding: each class has a
*preference order over all tiers*, and a Slice lands on its most-preferred tier that
is available within a comparable latency band. Demand is never denied just because its
ideal tier is scarce, and supply/demand self-regulate (providers build higher tiers
because premium gravitates there; nobody is stranded when it's scarce).

| Service Class | Plan | Tier preference (best → worst) | Preemptible |
|---|---|---|---|
| `Free` | Ad-funded free tier | I › II › III › IV › V | **Yes** |
| `Standard` | Small / medium packages | IV › III › V › II › I | No |
| `Priority` | Large packages | V › IV › III › II › I | No |
| `Sovereign` | Government (B2G) / large dedicated | V › IV › III › II › I | No |

Premium degrades downward (V→IV→III→…); Free climbs only as a last resort (and is
preemptible, so it won't squat expensive nodes). This table is the policy knob —
tuned by the same governance vote as `avgSliceCost`; encoded in `coffeepie-scheduler`.

> **Open product decision:** `Sovereign` (B2G) may need a *hard* tier floor for
> data-residency/compliance (deny rather than degrade onto a low tier). Today it
> degrades like the others; add a floor when the compliance requirements are known.

## Scheduler rules

1. **Latency-first across bands; tier preference within a band.** Rank by
   `(latency band, tier preference, exact ping)`. A nearer node beats a farther one
   regardless of tier (latency is the AGENTS.md #1 priority); among comparably-close
   nodes (within `LATENCY_BUCKET_MS`), the class's tier preference decides. The band
   width is the lever — smaller = latency dominates more.
2. **Graceful degradation.** No class is fenced out of a tier — premium degrades
   V→IV→III→…, so a Slice is placed as long as any node has capacity, instead of
   being denied when its ideal tier is scarce. (Premium *features* — HA / Live
   Migration — still track the actual node: unavailable on a low-tier fallback.)
3. **Preemption order.** Only a preemptible occupant (Free) may be evicted, and only
   by a strictly higher class: B2G ⟫ Priority ⟫ Standard ⟫ Free.
4. **Last resort.** No node with capacity ⇒ the broker preempts (rule 3) or queues.

## Demand-based pricing (shares the utilization signal)

The same **live regional utilization** the broker computes from heartbeats
(`free_slices` vs total) feeds **Rush Hour Balancing Rates** — a demand-based load
shaper on the *billing* side (not placement). During peak windows the **Free tier**
compute rate scales from off-peak `30 Cr/slice·min` up to `~1'000 Cr/slice·min`
(Free Credits are earned via Ads — and expire 1 h after grant — so peak use costs
more Ads); **paid tiers are not surged**, and basic access is never denied
(Free degrades gracefully). It's
customer-side only — provider COFP earning (1 COFP/slice·min) is unchanged.
Governance/region-tunable, like `avgSliceCost`. Full description in `README.md`
(Monetization). Note it lives in the billing layer, not the scheduler — the scheduler
just places what's admitted.

## Architecture & status

```
account/plan ──▶ service_class ──▶ ticket ──▶ CreateSliceRequest.service_class
                                                       │
 provider registry (verified Tier) ──┐                 ▼
 DC heartbeats (free capacity) ──────┼──▶ [DC-selection broker] ──▶ dc-agent placement.rs (node within DC)
 client ping probes ─────────────────┘         uses coffeepie-scheduler
```

| Piece | Status |
|---|---|
| **Decision core** — `coffeepie-scheduler` crate (`ServiceClass`, `Tier`, tier-preference + latency-band `rank_candidates`, graceful degradation, `can_preempt`) | ✅ built + unit-tested (8 tests) |
| **`service_class` plumbing** — added to dc-agent `CreateSliceRequest` (`serde(default)`, backward-compatible) | ✅ |
| **Provider registry tier** — verified tier per provider/DC, set at onboarding | ⬜ pending (needs the broker + DB) |
| **DC-selection broker service** — receives `/api/v1/dc-agents/heartbeat`, holds the registry, calls `coffeepie-scheduler`, issues tickets | ⬜ pending (this is the unbuilt heart) |
| **Preemption execution** — evict/drain/replace Free sessions (`stop_instance` exists; the *orchestration* does not) | ⬜ pending |
| **HA / Live Migration** (Priority/Sovereign) — Proxmox migrate + failover orchestration; needs shared storage / fast interconnect (why it maps to Tier III+) | ⬜ pending (largest lift) |

**Phasing:** Phase 1 = the two ✅ rows above (additive, no behavior change). Phase 2
= the broker service wired to the decision core. Phase 3 = preemption execution and
HA/Live-Migration (their own PRs with real cluster testing).

See `PROVIDERS.md` (tiers/margins) and the `coffeepie_orchestrator/scheduler` crate.

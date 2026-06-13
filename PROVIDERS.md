# Coffee Pie® — Cloud Providers

Becoming a Trusted Provider on the QFDM Network. Full requirements at `coffeepie.co/cloud-providers`.

---

## How Providers Earn

Trusted Providers (datacenter operators) earn COFP by supplying computing resources to the QFDM Network at a rate of **1 COFP per Slice per minute**. Earnings scale linearly: hosting 4 Slices for 60 minutes = 4 × 60 = 240 COFP.

Providers may burn earned COFP for **fiat currency** transferred to their registered bank accounts within 24–72 hours. There is no burning cap — providers are selling real resources and need unrestricted cash flow. Provider settlement is an internal ledger operation; provider-earned COFP is not publicly tradeable.

> **Important:** If a provider transfers COFP to a secondary wallet and sells on the open market, those tokens permanently lose all voting and burning-for-fiat rights. The buyer receives an Investor-class token with economic rights only.

**Provider rights:**
- Vote on regional pricing (average slice cost, electricity rates, labor costs)
- Burn tokens for fiat currency (registered bank account, 24–72h settlement)
- No burning cap — proportional to real compute resources served

---

## Fiat Settlement Tiers

When Providers burn COFP for fiat, the amount received = base COFP price × (1 + tier margin). The global base cost is 0.29 COP/COFP (approx 0.000069 USD) per governance vote; all regional pricing derivatives are tracked in `avgSliceCost.json`. Tiers reward infrastructure quality, reliability, and environmental responsibility — the higher the Tier, the better the margin.

| Tier | Margin | Key Requirements |
|---|---|---|
| Tier I | +8% | Basic connectivity, ≥99% uptime SLA |
| Tier II | +10% | Redundant network, ≥99.5% uptime, UPS |
| Tier III | +12% | N+1 power redundancy, ≥99.9% uptime, dedicated cooling |
| Tier IV | +15% | 2N power redundancy, ≥99.95% uptime, physical security |
| Tier V | +18% | All Tier IV + dedicated SAN + ≥90% Renewable/Alternative Energy (solar, wind, nuclear, geothermal, etc.) |

---

## Getting Started

1. Review requirements at `coffeepie.co/cloud-providers`
2. Prepare infrastructure: Proxmox VE nodes (recommended), stretched VLAN connectivity, TLS certificates (see `PKI.md`)
3. Run provider onboarding: `tools/admin/provider-onboard`
4. Register bank account for fiat settlement (currently Colombian accounts only)
5. Deploy DC Agent and connect to the orchestrator

---

## References

- `NETWORK.md` — Network architecture and addressing
- `PKI.md` — Certificate lifecycle for internal communication
- `CONSTITUTION.md` — Governance and revenue distribution
- `README.md` — Full ecosystem overview

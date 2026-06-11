# Coffee Pie® — Screening Life Cycle Assessment (LCA)

**Status:** Screening study (v0.3, 2026-06) — NOT yet suitable for public comparative claims.
**Model:** [`scripts/lca_screening.py`](scripts/lca_screening.py) (single source of truth for all numbers below — rerun it after changing any parameter).
**Standard targeted:** ISO 14040/14044. A screening LCA is the first phase: same structure, placeholder data, no independent critical review yet.
**v0.2 change:** models the ISP lease-and-return loop (set-top-box model) with component-level modularity: decoder module, aluminum MC-PCB keyboard/chassis, PSU.
**v0.3 change:** adds Scenario D (new desktop tower), always-on persistent storage energy, electricity breakdown, and §4 on the per-user physics floor.

---

## 1. Why this document exists

The README claims Coffee Pie reduces e-waste and democratizes computing. A claim
about environmental impact is only worth what its numbers can defend. This study
quantifies the claim, states the conditions under which it is FALSE, and defines
the path to an audit-grade result. Per ISO 14044, **no comparative assertion from
this document may be published (website, marketing, investor decks) until the
data is cited and the study has passed independent critical review** — publishing
earlier is a greenwashing and legal risk, not a shortcut.

## 2. Goal and scope

- **Functional unit:** one user-year of standard productivity computing
  (4 h/day, office/web/dev workload, 1080p display).
- **Scenarios compared:**
  - **A.** Coffee Pie Codec Terminal + remote Slices. The terminal is **leased
    by the ISP within the internet subscription and returned at end of
    contract** — the classic TV set-top-box custody model. It is modular:
    - *decoder module* (Radxa Zero 3E / Odroid-C5 class SBC): 5 W
      hardware-accelerated encode/decode, low thermal stress, purpose-stable —
      service life limited by codec evolution rather than wear;
    - *keyboard/chassis*: aluminum-core MC-PCB + copper, ~99% recyclable,
      modular and repairable, serves multiple users across lease cycles;
    - *PSU + cables*.
    Burdens include the allocated share of datacenter server, datacenter
    electricity, network transmission, and reverse logistics between leases.
  - **B.** New mid-range laptop replaced every 4 years, consumer disposal
    (typical formal e-waste collection rates).
  - **C.** Refurbished laptop (cut-off allocation: the second life carries only
    refurbishment burdens). Included deliberately — it is the strongest
    competitor and any reviewer would add it if we omitted it.
  - **D.** New desktop tower PC (no monitor), replaced every 5 years, consumer
    disposal. This is the comparator behind the "~30% of standalone PC energy"
    intuition — desktops are where Coffee Pie's use-phase advantage is real.
- **System boundary:** cradle-to-grave for devices; use-phase electricity
  including datacenter PUE, **always-on persistent storage** (each
  subscriber's 125 GB/slice exists 24/7/365 even while they are offline —
  oversubscription does not apply to storage), and network transmission
  energy; reverse logistics for the leased terminal. The display/monitor is
  excluded (common to all scenarios). Software development burdens excluded.
- **Oversubscription:** compute is shared — a 256-slice node serves ~64
  concurrent 4-slice sessions, and at 4 h/day usage one node can serve several
  hundred *subscribers* (the README's rush-hour concurrency is the hard
  ceiling, exactly as QFDM frames it). The model captures this through
  `server_utilization` (allocated burden = server burden x user's slice-hours
  / total delivered slice-hours). Raising utilization from 0.5 to 0.9 cuts the
  server share from ~2.1 to ~1.2 kg CO2e/user-yr — real, but a second-order
  effect, because the server is NOT the dominant term (see §4).
- **Impact categories:** climate change (kg CO2e) and a two-part e-waste
  indicator:
  - **mass throughput** — hardware mass consumed per user-year (mass / life);
  - **mass lost** — mass NOT recovered into the circular loop per user-year.
    For the leased terminal, recovery = return rate x component recyclable
    fraction (custody makes recovery enforceable). For laptops, recovery =
    formal collection x material recovery (owner-dependent, typically low).
  The "lost" figure is the honest headline; throughput keeps us from hiding
  material consumption behind recycling claims.
- **Allocation:** server burdens are allocated over delivered slice-hours
  across server lifetime at assumed utilization. NOTE: this is *attributional*
  accounting. The stronger Coffee Pie argument — that we monetize *existing
  underutilized* hardware, so marginal embodied burden is near zero — is a
  *consequential* argument and must be kept separate and clearly labeled when
  communicating, or reviewers will reject the study.

## 3. Base-case results (screening, placeholder data)

Grid: 200 g CO2e/kWh (Colombia). Network: 0.01 kWh/GB. Terminal return rate: 95%.

| Per user-year | Embodied kg CO2e | Use-phase kg CO2e | **Total kg CO2e** | Electricity kWh | Mass throughput g | **E-waste lost g** |
|---|---|---|---|---|---|---|
| A. Codec Terminal + Slices (leased, returned) | 5.3 | 11.5 | **16.8** | 57.6 | 111 | **15** |
| B. New laptop | 57.5 | 8.8 | **66.3** | 43.8 | 450 | **360** |
| C. Refurbished laptop | 8.3 | 10.2 | **18.6** | 51.1 | 257 | **206** |
| D. New desktop tower | 60.0 | 29.2 | **89.2** | 146.0 | 1200 | **960** |

Scenario A electricity breakdown (kWh/user-year):

| terminal (5 W) | datacenter compute | persistent storage (24/7) | network | total |
|---|---|---|---|---|
| 7.3 | 8.8 | 2.1 | 39.4 | 57.6 |

Terminal hardware breakdown (per user-year):

| Component | Embodied kg CO2e | Mass kg | Life yr | Recyclable | kg CO2e/user-yr | Lost g/user-yr |
|---|---|---|---|---|---|---|
| decoder module | 12.0 | 0.1 | 12 | 70% | 1.00 | 2.8 |
| keyboard/chassis (Al MC-PCB) | 15.0 | 1.0 | 20 | 99% | 0.75 | 3.0 |
| PSU + cables | 5.0 | 0.3 | 10 | 80% | 0.50 | 7.2 |
| server share | — | — | — | 90% | 2.08 | 2.3 |
| reverse logistics | — | — | — | — | 1.00 | — |

Headline (if the placeholders survive validation): **~81% lower CO2e and ~98%
less e-waste lost than a new desktop; ~75% lower CO2e and ~96% less e-waste
lost than a new laptop (~93% less than refurbished)**. Versus the desktop,
Scenario A consumes **39% of the electricity** — consistent with the project's
"~30% of a standalone PC" design intuition. The lease-and-return custody model
is what turns "recyclable" into "recycled": the same 99%-recyclable keyboard
in consumer hands would mostly end up in the ~20% formal-collection stream
like any other device.

Two things the breakdown exposes:

1. **The humble PSU is now the largest hardware loss term** (7.2 g/user-yr) —
   worth designing the return/recycling flow to include it, not just the unit.
2. **The aluminum keyboard is a long-game bet:** primary aluminum is
   embodied-carbon-intensive (~8–16 kg CO2e/kg), so the chassis only pays off
   because the 20-year multi-user service life amortizes it and the closed
   loop recovers the metal. Building the first production run from recycled
   aluminum would cut its embodied figure several-fold — likely the single
   cheapest carbon win available in the hardware design.

## 4. The physics floor — why per-user CO2e is kilograms, not grams

A natural intuition: servers are hyper-efficient and shared by hundreds of
users, so per-user emissions should collapse toward grams or milligrams. The
sharing intuition is correct — and it is already in the model — but the
conclusion doesn't follow, because **the server is not the dominant term.**
Look at the electricity breakdown in §3: of 57.6 kWh/user-year, datacenter
compute is only 8.8 kWh. The floor is set by things sharing cannot dilute:

1. **The terminal in the user's hands.** 5 W x 4 h/day x 365 = 7.3 kWh/yr.
   At the Colombian grid that is ~1.5 kg CO2e/yr from the terminal alone —
   already a thousand times above "grams", before any datacenter exists.
2. **The network.** Streaming 6 Mbps for 1460 h moves ~3.9 TB/yr through
   access and core networks. Even at optimistic marginal intensity this is
   the largest single energy term (39.4 kWh at 0.01 kWh/GB).
3. **Persistent storage.** Each subscriber's slices of storage exist
   24/7/365 whether or not they are logged in. Small per user (~2.1 kWh/yr)
   but it cannot be oversubscribed away.

What sharing DOES achieve is visible in the comparison: the desktop burns
146 kWh/yr to deliver the same user-year that Scenario A delivers with 57.6
(39%), and embodies 60 kg CO2e/yr of manufacturing against A's 5.3. The
honest claim is therefore "**~3-5x better, with ~98% less e-waste**" — which
is an enormous, defensible win. "Milligrams per user" would be off by five to
six orders of magnitude, and publishing it would hand critics an easy kill.

Fleet-scale framings ("if 300M people bought PCs instead...") are
*consequential* arguments: legitimate for vision documents, but they must
never be mixed into this attributional study, and absolute-reduction claims
must additionally survive the rebound effect (§6.7).

## 5. Sensitivity — where the result flips

**CO2e** is dominated by **network transmission energy intensity** (kWh/GB),
the most uncertain factor in the model (literature spans 0.001–0.06 kWh/GB
depending on methodology and which network layers are counted).

| grid g/kWh | A @ 0.005 kWh/GB | A @ 0.01 | A @ 0.03 | A @ 0.06 | B new laptop | C refurb | D desktop |
|---|---|---|---|---|---|---|---|
| 100 (clean) | 9.1 | 11.1 | 19.0 | 30.8 | 61.9 | 13.4 | 74.6 |
| 200 (Colombia) | 12.9 | 16.8 | 32.6 | 56.3 | 66.3 | 18.6 | 89.2 |
| 480 (world avg) | 23.5 | 33.0 | 70.8 | 127.6 | 78.5 | 32.9 | 130.1 |

Break-even network intensity (A's total equals the comparator's):

| grid g/kWh | A beats NEW laptop below | A beats REFURB laptop below | A beats DESKTOP below |
|---|---|---|---|
| 100 | 0.139 kWh/GB | 0.016 kWh/GB | 0.171 kWh/GB |
| 200 | 0.073 kWh/GB | 0.012 kWh/GB | 0.102 kWh/GB |
| 480 | 0.034 kWh/GB | 0.010 kWh/GB | 0.061 kWh/GB |

Against the desktop the win is robust: the break-even (0.061–0.171 kWh/GB)
sits above the entire plausible network-intensity range, so Scenario A beats
a new desktop under essentially any accounting. The laptop and refurb
comparisons remain network-sensitive as before.

**E-waste lost** is dominated by the **return rate** — the custody assumption,
not the recyclability assumption:

| return rate | A lost g/user-yr | B new laptop | C refurb |
|---|---|---|---|
| 60% | 43 | 360 | 206 |
| 80% | 27 | 360 | 206 |
| 95% | 15 | 360 | 206 |

Even at a poor 60% return rate the terminal still wins on e-waste by ~5x —
the advantage is robust, but the *size* of the claim depends on contract
design (deposits, swap-on-upgrade, ISP pickup) more than on materials.

## 6. Conditions under which we LOSE (read this first)

Honesty section — these are the claims critics will make, and when they are right:

1. **Against a refurbished laptop on CO2e, we win only narrowly and only if
   marginal network energy is low (≲0.012 kWh/GB at Colombian grid).** If one
   uses average (not marginal) network energy accounting, the refurb laptop
   likely wins on carbon. Our defensible advantages against refurb are e-waste
   (~93% less lost mass) and service quality, not CO2e.
2. **On a world-average grid with pessimistic network accounting
   (0.03–0.06 kWh/GB), scenario A can be WORSE than even a new laptop.**
   The carbon case is strongest where grids are clean (Colombia is) and
   weakest in coal-heavy regions. Expansion claims must be region-specific.
3. **If real slice power exceeds the 1 Wh/slice-hour spec** (typical VDI
   deployments measure 10–30 W per active user, far above 4 slices x 1 Wh),
   the datacenter term grows accordingly. The PWR spec must be validated with
   wall-power measurements, not assumed.
4. **The decoder's enemy is codec evolution, not wear.** A 5 W
   hardware-decode block is only useful while the network streams codecs it
   supports. If the ecosystem moves Basic terminals off H.264 before ~12
   years, decoder life shortens and its burdens grow. Mitigations that are in
   our control: keep H.264 as the guaranteed floor (as the roadmap already
   does), and make the decoder module field-swappable inside the same chassis
   so codec upgrades don't retire the aluminum.
5. **The e-waste claim is a custody claim.** If lease contracts, deposits, and
   reverse logistics don't actually achieve high return rates, the advantage
   shrinks (see §5). "99% recyclable" without returns is marketing; returns
   without recycling partners is a warehouse. The claim must be backed by
   measured return rates from pilots and named recycling partners.
6. **Primary aluminum cuts both ways.** The keyboard/chassis embodied figure
   assumes the long service life materializes. A design change, lease churn
   damage, or early obsolescence that retires chassis in ~5 years would make
   the aluminum a liability, not an asset.
7. **Jevons/rebound:** making compute cheaper increases total consumption.
   A per-user-year win does not guarantee an absolute reduction. Do not claim
   absolute global reductions from a per-functional-unit study.

## 7. Validation roadmap (screening → audit-grade)

| # | Task | Output |
|---|---|---|
| 1 | Measure terminal wall power (idle/stream) and real per-session server power on a reference node | replaces `terminal_power`, `slice_power`, `pue` |
| 2 | Weigh and BOM the reference terminal per component (decoder, keyboard/chassis, PSU); obtain SBC vendor PCF or model in openLCA; get the Al alloy + recycled-content figure from the keyboard supplier | replaces `COMPONENTS` table |
| 3 | Cite laptop PCFs (Dell/Lenovo/Apple publish per-model PDFs) and the Colombian grid factor (XM/UPME) | replaces `laptop_embodied`, `grid_intensity` |
| 4 | Pick and justify a network energy intensity method (marginal vs average), cite peer-reviewed source | replaces `network_intensity` — the CO2e swing variable |
| 5 | Measure real average stream bitrate and session hours from Sunshine/Moonlight logs | replaces `stream_bitrate`, `hours_per_year` |
| 6 | Measure terminal return rates in ISP pilots; document the contractual return mechanism (deposit, swap, pickup) and name recycling partners with their recovery certificates | replaces `return_rate`, component recyclable fractions — the e-waste swing variables |
| 7 | Rebuild in openLCA (free) or Brightway2 (Python) with ecoinvent or free datasets (US LCI, EU PEF) | full LCIA, more impact categories |
| 8 | Independent critical review (ISO 14044 §6) by an LCA practitioner | unlocks public comparative claims |

## 8. Reproducing the numbers

```bash
python3 scripts/lca_screening.py          # markdown report
python3 scripts/lca_screening.py --json   # machine-readable
```

All parameters live in two tables at the top of the script (`P` and
`COMPONENTS`), each tagged with its source or `TODO-cite`/`MEASURE`. Change a
value, rerun, and update §3–§5 of this file. Do not edit the result tables
here by hand without rerunning the model.

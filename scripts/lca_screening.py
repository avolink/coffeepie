#!/usr/bin/env python3
"""Coffee Pie screening LCA model.

Compares the climate impact (kg CO2e) and e-waste generation (g) of delivering
one user-year of standard productivity computing via three scenarios:

  A. Coffee Pie Codec Terminal + remote Slices. The terminal is LEASED by the
     ISP with the internet subscription (set-top-box model) and RETURNED at end
     of contract: closed-loop recovery, component-level modularity:
       - decoder module (Radxa Zero 3E / Odroid-C5 class SBC, 5 W hw decode)
       - keyboard/chassis (aluminum-core MC-PCB + copper, ~99% recyclable,
         modular and repairable, long service life across multiple users)
       - PSU + cables
  B. New mid-range laptop, replaced every `laptop_life_years`, consumer
     disposal (typical formal e-waste collection rates apply).
  C. Refurbished laptop (cut-off allocation: second life carries only the
     refurbishment burden, not the original manufacturing burden).
  D. New desktop tower PC (no monitor — display excluded in all scenarios),
     consumer disposal.

E-waste indicator (two numbers, do not conflate them):
  - "throughput": hardware mass consumed per user-year (mass / service life)
  - "lost":      mass NOT recovered into the circular loop per user-year
                 = throughput x (1 - recovery), where recovery for the leased
                 terminal = return_rate x component recyclable fraction, and
                 for laptops = formal collection x material recovery.

This is a SCREENING model (ISO 14040 terminology: not a full LCA, no critical
review). Every factor below is a placeholder estimate that MUST be replaced
with a cited source before any public comparative claim is made. See LCA.md.

Run:  python3 scripts/lca_screening.py            # markdown report to stdout
      python3 scripts/lca_screening.py --json     # machine-readable output
"""

import argparse
import json

# ---------------------------------------------------------------------------
# Parameters. Each entry: (value, unit, source).
# "TODO-cite" = order-of-magnitude estimate from public LCA literature and
# vendor PCF reports; replace with a specific citation. "MEASURE" = obtain
# empirically from reference hardware / pilot deployments.
# ---------------------------------------------------------------------------

P = {
    # --- Usage profile ---
    "hours_per_year":        (1460,  "h/yr",      "4 h/day x 365; TODO-cite usage study"),
    "slices_per_session":    (4,     "slices",    "typical productivity VM (4 vCore/4 GB); project assumption"),

    # --- Scenario A: terminal use-phase + datacenter + network ---
    "terminal_power":        (5.0,   "W",         "hardware-accelerated decode, design figure; MEASURE at wall"),
    "slice_power":           (1.0,   "Wh/h",      "PWR spec = 1 Wh per slice-hour (README slice table); MEASURE real average"),
    "pue":                   (1.5,   "ratio",     "datacenter power usage effectiveness; TODO-cite provider data"),
    "server_embodied":       (1800.0,"kg CO2e",   "2U rack server manufacturing; TODO-cite vendor PCF (Dell/HPE ~1300-2500)"),
    "server_mass":           (20.0,  "kg",        "2U server; TODO-cite"),
    "server_slices":         (192,   "slices",    "slices hosted per server; project assumption"),
    "server_life_years":     (6,     "yr",        "datacenter refresh cycle; TODO-cite"),
    "server_utilization":    (0.5,   "ratio",     "average sold/occupied fraction of slice capacity over server life; oversubscription raises this (rush-hour concurrency is the ceiling)"),
    "storage_power_per_slice":(0.04, "W",         "always-on share of persistent storage (125 GB of a ~20 TB/6 W HDD + SSD share) per slice, 24/7/365; TODO-cite"),
    "server_recovery":       (0.90,  "ratio",     "datacenter ITAD material recovery; TODO-cite"),
    "stream_bitrate":        (6.0,   "Mbps",      "average 1080p H.264 session; MEASURE (spec guarantees 8)"),
    "network_intensity":     (0.01,  "kWh/GB",    "transmission energy; literature range 0.001-0.06, TODO-cite (dominant uncertainty)"),

    # --- Scenario A: lease-and-return loop ---
    "return_rate":           (0.95,  "ratio",     "fraction of leased terminals actually returned to ISP; set-top-box benchmark, MEASURE in pilots"),
    "refurb_logistics":      (1.0,   "kg CO2e/yr","reverse logistics + cleaning/repair between lease cycles; TODO-cite"),

    # --- Scenario B: New laptop ---
    "laptop_embodied":       (230.0, "kg CO2e",   "mid-range 14in laptop manufacturing+transport; TODO-cite vendor PCFs (~200-350)"),
    "laptop_life_years":     (4,     "yr",        "typical replacement cycle; TODO-cite"),
    "laptop_mass":           (1.8,   "kg",        "typical 14in laptop"),
    "laptop_power":          (30.0,  "W",         "active productivity use incl. charging losses; TODO-cite"),
    "laptop_eol_recovery":   (0.20,  "ratio",     "formal collection x material recovery for consumer devices; TODO-cite Global E-waste Monitor (~17% collected)"),

    # --- Scenario D: New desktop tower (no monitor) ---
    "desktop_embodied":      (300.0, "kg CO2e",   "tower manufacturing+transport, no monitor; TODO-cite vendor PCFs"),
    "desktop_life_years":    (5,     "yr",        "desktops outlast laptops; TODO-cite"),
    "desktop_mass":          (6.0,   "kg",        "typical mini/mid tower"),
    "desktop_power":         (100.0, "W",         "active productivity use, average desktop; TODO-cite"),

    # --- Scenario C: Refurbished laptop (cut-off allocation) ---
    "refurb_embodied":       (25.0,  "kg CO2e",   "refurbishment process + parts + logistics; TODO-cite"),
    "refurb_life_years":     (3,     "yr",        "second-life duration; TODO-cite"),
    "refurb_power":          (35.0,  "W",         "older hardware, slightly less efficient"),

    # --- Grid ---
    "grid_intensity":        (200.0, "g CO2e/kWh","Colombia (hydro-dominated); TODO-cite UPME/XM factor (~150-230)"),
}

# Codec Terminal components: name -> (embodied kg CO2e, mass kg, service life
# yr, recyclable fraction, source note). Embodied is cradle-to-gate for ONE
# unit; service life spans multiple lease cycles/users (modular repair).
COMPONENTS = {
    "decoder_module": (12.0, 0.10, 12, 0.70,
        "Radxa Zero 3E / Odroid-C5 class SBC; PCB+SoC recovery is partial; "
        "life limited by codec evolution, not wear; TODO-cite"),
    "keyboard_chassis": (15.0, 1.00, 20, 0.99,
        "aluminum-core MC-PCB + copper + chassis; primary Al is embodied-"
        "intensive (~8-16 kg CO2e/kg) but ~99% recyclable in closed loop; "
        "modular/repairable; TODO-cite, switch to recycled-Al figure when known"),
    "psu_cables": (5.0, 0.30, 10, 0.80,
        "external PSU + cabling; TODO-cite"),
}

GRID_SENSITIVITY = [100.0, 200.0, 480.0]          # g CO2e/kWh
NETWORK_SENSITIVITY = [0.005, 0.01, 0.03, 0.06]   # kWh/GB
RETURN_RATE_SENSITIVITY = [0.60, 0.80, 0.95]      # leased-terminal return rate


def v(key):
    return P[key][0]


def _server_alloc():
    """(embodied kg CO2e, mass kg) allocated to one user-year."""
    server_slice_hours = (v("server_slices") * v("server_life_years")
                          * 8760 * v("server_utilization"))
    user_slice_hours = v("slices_per_session") * v("hours_per_year")
    share = user_slice_hours / server_slice_hours
    return v("server_embodied") * share, v("server_mass") * share


def scenario_terminal(grid=None, net_int=None, return_rate=None):
    """Scenario A: per user-year."""
    grid = grid if grid is not None else v("grid_intensity")
    net_int = net_int if net_int is not None else v("network_intensity")
    rr = return_rate if return_rate is not None else v("return_rate")
    hours = v("hours_per_year")

    embodied = v("refurb_logistics")
    throughput = 0.0
    lost = 0.0
    for (emb, mass, life, recyclable, _src) in COMPONENTS.values():
        embodied += emb / life
        thr = mass / life
        throughput += thr
        lost += thr * (1.0 - rr * recyclable)

    srv_emb, srv_mass = _server_alloc()
    embodied += srv_emb
    throughput += srv_mass
    lost += srv_mass * (1.0 - v("server_recovery"))

    kwh_terminal = v("terminal_power") * hours / 1000.0
    kwh_dc = v("slice_power") * v("slices_per_session") * hours * v("pue") / 1000.0
    # Persistent storage exists 24/7/365 regardless of session hours.
    kwh_storage = (v("storage_power_per_slice") * v("slices_per_session")
                   * 8760 * v("pue") / 1000.0)
    gb_streamed = v("stream_bitrate") / 8.0 * 3600.0 * hours / 1000.0  # Mbps -> GB
    kwh_network = gb_streamed * net_int
    use = (kwh_terminal + kwh_dc + kwh_storage + kwh_network) * grid / 1000.0

    return {
        "embodied": embodied,
        "use": use,
        "total": embodied + use,
        "kwh": kwh_terminal + kwh_dc + kwh_storage + kwh_network,
        "kwh_breakdown": {"terminal": kwh_terminal, "datacenter": kwh_dc,
                          "storage": kwh_storage, "network": kwh_network},
        "ewaste_throughput_g": throughput * 1000.0,
        "ewaste_lost_g": lost * 1000.0,
    }


def scenario_laptop(grid=None, embodied_key="laptop_embodied", life_key="laptop_life_years",
                    power_key="laptop_power", mass_amortized=None):
    grid = grid if grid is not None else v("grid_intensity")
    hours = v("hours_per_year")
    embodied = v(embodied_key) / v(life_key)
    kwh = v(power_key) * hours / 1000.0
    use = kwh * grid / 1000.0
    if mass_amortized is None:
        mass_amortized = v("laptop_mass") / v(life_key)
    lost = mass_amortized * (1.0 - v("laptop_eol_recovery"))
    return {
        "embodied": embodied,
        "use": use,
        "total": embodied + use,
        "kwh": kwh,
        "ewaste_throughput_g": mass_amortized * 1000.0,
        "ewaste_lost_g": lost * 1000.0,
    }


def scenario_desktop(grid=None):
    return scenario_laptop(grid, "desktop_embodied", "desktop_life_years",
                           "desktop_power",
                           v("desktop_mass") / v("desktop_life_years"))


def scenario_refurb(grid=None):
    # Cut-off: original manufacturing belongs to the first life. The second
    # life also defers disposal, so mass is spread over both lives combined.
    mass_amortized = v("laptop_mass") / (v("laptop_life_years") + v("refurb_life_years"))
    return scenario_laptop(grid, "refurb_embodied", "refurb_life_years",
                           "refurb_power", mass_amortized)


def fmt(x, nd=1):
    return f"{x:.{nd}f}"


def report():
    out = []
    a, b, c, d = (scenario_terminal(), scenario_laptop(),
                  scenario_refurb(), scenario_desktop())

    out.append("## Results — base case "
               f"(grid {fmt(v('grid_intensity'),0)} g CO2e/kWh, "
               f"network {v('network_intensity')} kWh/GB, "
               f"return rate {fmt(v('return_rate')*100,0)}%)\n")
    out.append("| Per user-year | Embodied kg CO2e | Use-phase kg CO2e | **Total kg CO2e** | Electricity kWh | Mass throughput g | **E-waste lost g** |")
    out.append("|---|---|---|---|---|---|---|")
    for name, s in (("A. Codec Terminal + Slices (leased, returned)", a),
                    ("B. New laptop", b),
                    ("C. Refurbished laptop", c),
                    ("D. New desktop tower", d)):
        out.append(f"| {name} | {fmt(s['embodied'])} | {fmt(s['use'])} | "
                   f"**{fmt(s['total'])}** | {fmt(s['kwh'])} | "
                   f"{fmt(s['ewaste_throughput_g'],0)} | **{fmt(s['ewaste_lost_g'],0)}** |")

    out.append("\n## Terminal component breakdown (Scenario A hardware)\n")
    out.append("| Component | Embodied kg CO2e | Mass kg | Life yr | Recyclable | kg CO2e/user-yr | Lost g/user-yr |")
    out.append("|---|---|---|---|---|---|---|")
    rr = v("return_rate")
    for name, (emb, mass, life, rec, _src) in COMPONENTS.items():
        out.append(f"| {name} | {emb} | {mass} | {life} | {fmt(rec*100,0)}% | "
                   f"{fmt(emb/life,2)} | {fmt(mass/life*(1-rr*rec)*1000,1)} |")
    srv_emb, srv_mass = _server_alloc()
    out.append(f"| server share | — | — | — | {fmt(v('server_recovery')*100,0)}% | "
               f"{fmt(srv_emb,2)} | {fmt(srv_mass*(1-v('server_recovery'))*1000,1)} |")
    out.append(f"| refurb logistics | — | — | — | — | {fmt(v('refurb_logistics'),2)} | — |")

    out.append("\n## Scenario A electricity breakdown (kWh/user-year)\n")
    kb = a["kwh_breakdown"]
    out.append("| terminal | datacenter compute | persistent storage (24/7) | network | total |")
    out.append("|---|---|---|---|---|")
    out.append(f"| {fmt(kb['terminal'])} | {fmt(kb['datacenter'])} | "
               f"{fmt(kb['storage'])} | {fmt(kb['network'])} | {fmt(a['kwh'])} |")

    out.append("\n## Sensitivity — total kg CO2e/user-year for Scenario A "
               "(vs B and C, which only vary with grid)\n")
    header = ("| grid g/kWh | " + " | ".join(f"A @ {n} kWh/GB" for n in NETWORK_SENSITIVITY)
              + " | B new laptop | C refurb | D desktop |")
    out.append(header)
    out.append("|" + "---|" * (len(NETWORK_SENSITIVITY) + 4))
    for g in GRID_SENSITIVITY:
        row = [f"| {fmt(g,0)} "]
        for n in NETWORK_SENSITIVITY:
            t = scenario_terminal(grid=g, net_int=n)["total"]
            row.append(f"| {fmt(t)} ")
        row.append(f"| {fmt(scenario_laptop(grid=g)['total'])} ")
        row.append(f"| {fmt(scenario_refurb(grid=g)['total'])} ")
        row.append(f"| {fmt(scenario_desktop(grid=g)['total'])} |")
        out.append("".join(row))

    out.append("\n## Sensitivity — e-waste lost (g/user-year) vs terminal return rate\n")
    out.append("| return rate | A lost g/user-yr | B new laptop | C refurb |")
    out.append("|---|---|---|---|")
    for rr_s in RETURN_RATE_SENSITIVITY:
        a_rr = scenario_terminal(return_rate=rr_s)["ewaste_lost_g"]
        out.append(f"| {fmt(rr_s*100,0)}% | {fmt(a_rr,0)} | {fmt(b['ewaste_lost_g'],0)} | {fmt(c['ewaste_lost_g'],0)} |")

    out.append("\n## Break-even network intensity (Scenario A total == comparator total)\n")
    out.append("| grid g/kWh | A beats B (new laptop) below | A beats C (refurb) below | A beats D (desktop) below |")
    out.append("|---|---|---|---|")
    hours = v("hours_per_year")
    gb = v("stream_bitrate") / 8.0 * 3600.0 * hours / 1000.0
    for g in GRID_SENSITIVITY:
        base = scenario_terminal(grid=g, net_int=0.0)["total"]
        slope = gb * g / 1000.0  # kg CO2e per (kWh/GB)
        be_b = (scenario_laptop(grid=g)["total"] - base) / slope
        be_c = (scenario_refurb(grid=g)["total"] - base) / slope
        be_d = (scenario_desktop(grid=g)["total"] - base) / slope
        out.append(f"| {fmt(g,0)} | {fmt(be_b,3)} kWh/GB | {fmt(be_c,3)} kWh/GB | {fmt(be_d,3)} kWh/GB |")

    out.append("\n## Parameters (replace TODO-cite / MEASURE before public use)\n")
    out.append("| Parameter | Value | Unit | Source |")
    out.append("|---|---|---|---|")
    for k, (val, unit, src) in P.items():
        out.append(f"| {k} | {val} | {unit} | {src} |")
    out.append("\n| Component | Embodied | Mass | Life | Recyclable | Source |")
    out.append("|---|---|---|---|---|---|")
    for name, (emb, mass, life, rec, src) in COMPONENTS.items():
        out.append(f"| {name} | {emb} kg CO2e | {mass} kg | {life} yr | {rec} | {src} |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Coffee Pie screening LCA")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    if args.json:
        print(json.dumps({
            "base_case": {
                "terminal_plus_slices": scenario_terminal(),
                "new_laptop": scenario_laptop(),
                "refurbished_laptop": scenario_refurb(),
                "new_desktop": scenario_desktop(),
            },
            "parameters": {k: {"value": x[0], "unit": x[1], "source": x[2]} for k, x in P.items()},
            "components": {k: {"embodied_kgco2e": x[0], "mass_kg": x[1],
                               "life_years": x[2], "recyclable_fraction": x[3],
                               "source": x[4]} for k, x in COMPONENTS.items()},
        }, indent=2))
    else:
        print(report())


if __name__ == "__main__":
    main()

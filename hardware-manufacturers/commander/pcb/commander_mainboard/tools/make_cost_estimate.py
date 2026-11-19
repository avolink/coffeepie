#!/usr/bin/env python3
"""Estimated cost and availability of the Commander mainboard -> commander/fabrication/estimated-cost.csv

    python tools/make_cost_estimate.py

Reads the generated parts list and prices every line for 5, 10, 100, 1,000, 10,000 and 100,000 boards.
The prices and stock figures in this file were collected on 2026-11-13 from distributor pages as they
appeared in web search results; they are snapshots of unknown age, several of them contradict each other,
and the volume prices above 100 pieces are mostly estimates.  Treat the result as a budget, not a quotation.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpmodel      # noqa: E402

COMMANDER = os.path.normpath(os.path.join(cpmodel.ROOT, "..", ".."))
QTY = [5, 10, 100, 1000, 10000, 100000]
GEN = [1.5, 1.5, 1.0, 0.8, 0.7, 0.6]         # price ladder of a commodity part relative to its 100-piece price
NC = "not checked"


def ladder(base):
    return [round(base * f, 5) for f in GEN]


# value -> (suggested part, manufacturer, LCSC no., availability, stock LCSC/JLCPCB, stock elsewhere, prices[6], basis, note)
KEY = {
    "RK3566": ("RK3566", "Rockchip", "C2943786", "LIMITED", "102 - 505 (three snapshots)", "246 at one broker",
               [10.9, 10.9, 8.2, 7.4, 6.6, 6.0], "LCSC quoted at 1 and 100; above that estimated",
               "LCSC holds a few trays only. For production buy through a Rockchip authorised agent, which is also how the price above 1,000 is set."),
    "LPDDR4_200": ("K4F6E3S4HM-MGCJ / RS512M32LM4D2BDS-53BT / CXDB4CBAM-MK-A", "Samsung / Rayson / CXMT", "C2842431 / C2840158 / C20598565", "RISK",
                   "Samsung 814 (one snapshot); Rayson 0; CXMT not available", "18,000 at one broker (unverified)",
                   [9.0, 9.0, 6.5, 5.6, 5.0, 4.6], "LCSC snapshots between 5.4 and 12 at 1-100, contradictory; above that estimated",
                   "The Samsung part is reported discontinued and the two Chinese alternatives were out of stock. DRAM prices are volatile. Qualify at least two 200-ball LPDDR4 / LPDDR4X parts and buy on contract."),
    "EMMC153": ("FEMDNN016G-58A43 / KLMAG1JETD-B041 / EMMC16G-TB29", "FORESEE / Samsung / Kingston", "C719489 / C499919 / C6944849", "OK",
                "Samsung 12 - 5,100 (snapshots disagree); FORESEE and Kingston 0 on some pages", "32,000 at one broker (Samsung part)",
                [6.9, 6.1, 4.7, 4.6, 4.2, 3.9], "LCSC quoted (FORESEE ladder); 10k and 100k estimated",
                "Standard 153-ball eMMC 5.1: FORESEE, Samsung, Kingston, SanDisk and Kioxia all fit the same footprint, which is what makes it safe."),
    "RK817": ("RK817-5", "Rockchip", "C5179490", "LIMITED", "1", NC,
              [1.6, 1.6, 1.27, 1.1, 1.0, 0.9], "LCSC reference price; rest estimated", "Rockchip-only part: buy with the RK3566 from the same agent."),
    "RK860": ("RK860-0", "Rockchip", "C19188628", "OK", "about 361", "10,304 / 907 / 5,000 at three brokers",
              [0.65, 0.53, 0.45, 0.40, 0.36, 0.33], "LCSC quoted at 1 and 10; rest estimated", "Rockchip-only part."),
    "RTL8211F": ("RTL8211F-CG", "Realtek", "C187932", "GOOD", "9,865 - 24,086", NC,
                 [1.35, 1.35, 0.97, 0.73, 0.66, 0.60], "LCSC quoted to 490 pcs; rest estimated", ""),
    "USB5744": ("USB5744-I/2G", "Microchip", "C633621", "LIMITED", "3 - 301 (three snapshots)", NC,
                [5.26, 5.26, 3.35, 3.0, 2.8, 2.6], "LCSC quoted at 1 and 100; rest estimated",
                "Thin stock at LCSC. Microchip sells direct and through every major distributor; plan the volume buy there."),
    "USB2517": ("USB2517-JZX", "Microchip", "C1521556", "GOOD", "3,864 (and 3,349 of the -I version)", NC,
                [4.16, 4.16, 2.9, 2.76, 2.5, 2.3], "LCSC quoted at 1 and 260; rest estimated", ""),
    "HD3SS3220": ("HD3SS3220IRNHR", "Texas Instruments", "C701817", "OK", "1,348 (plus 179 of the RNHT reel)", NC,
                  [1.99, 1.99, 1.5, 1.3, 1.15, 1.05], "LCSC quoted at 1; rest estimated", "Four per board."),
    "TPS23754": ("TPS23754PWPR", "Texas Instruments", "C181651", "GOOD", "2,764 - 6,457", "Mouser 1,911",
                 [1.82, 1.62, 1.2, 0.85, 0.80, 0.75], "LCSC quoted to 1,000 pcs", ""),
    "TPS2121": ("TPS2121RUXR", "Texas Instruments", "C485916", "GOOD", "518 - 16,216 (snapshots disagree)", NC,
                [0.94, 0.94, 0.66, 0.60, 0.55, 0.50], "LCSC quoted at 1 and 30; rest estimated", ""),
    "FUSB302B": ("FUSB302BMPX", "onsemi", "C132291", "GOOD", "24,079", NC,
                 [0.71, 0.71, 0.47, 0.42, 0.38, 0.35], "LCSC quoted at 1 and 100; rest estimated", ""),
    "PLN060-ER20A05S": ("PLN060-ER20A05S", "Bourns", "C24570980", "RISK", "3", "32 at one distributor; 0 with a 20-week lead time at another",
                        [12.0, 12.0, 9.4, 6.5, 5.0, 4.5], "LCSC 9.40 at 100; Farnell 6.45 at 800; one distributor 4.98 at 5,600",
                        "Single source, almost no stock anywhere, long lead time. It is the only transformer found that fits the 10 mm under the board, so order samples now and ask Bourns for a production lead time."),
    "USBC16": ("TYPE-C-31-M-12", "Korean Hroparts (HRO)", "C165948", "GOOD", "71,350 - 295,625", NC,
               [0.19, 0.19, 0.13, 0.10, 0.09, 0.08], "LCSC quoted at 5, 50, 150; rest estimated", "Eight per board; one of the most common USB-C receptacles there is."),
    "USBC24": ("DX07S024WJ1R350", "JAE", "C5246837", "RISK", "0", "DigiKey 2,083 in one region, out of stock with 15 weeks in another; 3,971 at one broker",
               [3.3, 3.3, 2.3, 1.9, 1.6, 1.4], "broker 3.28 at 1 and 2.29 at 350; rest estimated",
               "Expensive and not stocked at LCSC. A mainstream Chinese 24-pin mid-mount USB 3 receptacle costs about a tenth and is stocked in the hundreds of thousands: worth changing the footprint for (four per board)."),
    "HDMI_MICRO_D": ("46765-1001 (or equivalent micro HDMI type D)", "Molex", "", "CHECK", NC, NC,
                     [1.3, 1.3, 0.9, 0.7, 0.6, 0.55], "estimate", "Not looked up. Chinese equivalents with the same land pattern are common."),
    "RJ45_8P": ("HR6042S-1188N15B-1R (sunk, no magnetics)", "HanRun", "", "CHECK", "not found by part number", NC,
                [0.9, 0.9, 0.6, 0.5, 0.45, 0.4], "estimate", "The exact Radxa part was not found at LCSC and its footprint here is provisional. Pick a sunk RJ45 that LCSC stocks and redraw the footprint to it."),
    "GB020G00": ("GB020G00 (as on the Radxa board)", "?", "", "CHECK", "not found by part number", "alternative Pulse H5007NL: DigiKey 2,499",
                 [0.45, 0.45, 0.30, 0.25, 0.22, 0.20], "estimate",
                 "Four single-channel transformers. Not found. The usual alternative is one 24-pin gigabit PoE module (Pulse H5007NL class, about 5.6 at 1,000; Chinese equivalents far less), which would mean redrawing the Ethernet head."),
    "UM3204H": ("UM3204H", "Union Semiconductor", "", "CHECK", NC, NC, ladder(0.08), "estimate", "HDMI level shifter from the Radxa design; not looked up."),
    "TPD4E05U06": ("TPD4E05U06DQAR", "Texas Instruments", "", "GOOD", NC + " (very common, many pin-compatible parts)", NC, ladder(0.15), "estimate", "Ten per board."),
    "USBLC6-2SC6": ("USBLC6-2SC6", "STMicroelectronics", "", "GOOD", NC + " (JLCPCB preferred-class part)", NC, ladder(0.06), "estimate", "Eleven per board."),
    "AP22804AW5": ("AP22804AW5-7", "Diodes Inc.", "", "GOOD", NC, NC, ladder(0.13), "estimate", "Ten per board."),
    "TLV62569": ("TLV62569DBVR", "Texas Instruments", "", "GOOD", NC, NC, ladder(0.15), "estimate", ""),
    "TLP291": ("TLP291 (or EL3H7 / LTV-217)", "Toshiba / Everlight / Lite-On", "", "GOOD", NC + " (three interchangeable makers)", NC, ladder(0.12), "estimate", ""),
    "TL431": ("TL431 SOT-23", "many", "", "GOOD", NC + " (JLCPCB basic-class part)", NC, ladder(0.03), "estimate", ""),
    "AT24C02": ("AT24C02 SOT-23-5", "Microchip and compatibles", "", "GOOD", NC, NC, ladder(0.05), "estimate", ""),
    "150V_60mR": ("150 V, about 60 mOhm N-MOSFET, PowerPAK 1212-8", "Vishay and compatibles", "", "CHECK", NC, NC, ladder(0.40), "estimate", "No part number chosen yet."),
    "PDS1040": ("PDS1040-13", "Diodes Inc.", "", "GOOD", NC, NC, ladder(0.30), "estimate", ""),
    "1uH_5A": ("XAL4020-102ME (or a 4 x 4 x 2 mm equivalent)", "Coilcraft", "", "CHECK", NC, NC, [1.6, 1.6, 1.1, 0.9, 0.75, 0.65], "estimate",
               "Coilcraft is rarely stocked at LCSC; equivalent 4020 moulded inductors from Chinese makers cost about 0.12."),
    "220uF_6.3V_POLY": ("T520V227M006 (7343-20 polymer)", "Kemet and compatibles", "", "GOOD", NC, NC, ladder(0.40), "estimate", ""),
    "22uF_100V_ALU": ("22 uF 100 V, 6.3 x 7.7 mm", "many", "", "GOOD", NC, NC, ladder(0.10), "estimate", ""),
    "MICROSD": ("microSD push-push socket", "Molex 104031-0811 and compatibles", "", "GOOD", NC, NC, ladder(0.30), "estimate", "Footprint-compatible Chinese sockets are common."),
    "JST_SH4_UART": ("SM04B-SRSS-TB", "JST", "", "GOOD", NC, NC, ladder(0.08), "estimate", ""),
    "JST_SH6_KBD": ("SM06B-SRSS-TB", "JST", "", "GOOD", NC, NC, ladder(0.10), "estimate", ""),
    "JST_PH4_BTN": ("S4B-PH-SM4-TB", "JST", "", "GOOD", NC, NC, ladder(0.10), "estimate", ""),
}


def generic(row):
    v, fp, ref = row["value"].upper(), row["footprint"], row["references"].split()[0]
    pre = "".join(c for c in ref if c.isalpha())
    hi = "very high (commodity part, JLCPCB basic / preferred class)"
    size = fp.split("_")[1] if fp.count("_") >= 2 else ""      # the imperial size code: C_0201_0603Metric is an 0201
    if pre == "C" or pre == "CAPS":
        if size == "1808":
            return ("2 kV safety / isolation capacitor 1808", 0.10, "GOOD", NC)
        if size == "1210":
            return ("2.2 uF 100 V 1210 X7R", 0.12, "GOOD", NC)
        if size == "1206":
            return ("47 uF 1206 X5R", 0.06, "GOOD", hi)
        if size == "0805":
            return ("22 uF 0805 X5R", 0.025, "GOOD", hi)
        if size == "0603":
            return ("ceramic capacitor 0603", 0.012, "GOOD", hi)
        big = v.startswith(("4.7UF", "10UF", "22UF", "2.2UF"))
        return ("ceramic capacitor " + size + (" (high value for its size)" if big else ""), (0.012 if big else 0.004 if size == "0402" else 0.003), "GOOD", hi)
    if pre == "R":
        if size == "2512":
            return ("1 W resistor 2512", 0.03, "GOOD", hi)
        if fp.startswith("L_"):
            return ("ferrite bead", 0.015, "GOOD", hi)
        return ("chip resistor " + size, 0.0015, "GOOD", hi)
    if pre == "FB":
        return ("ferrite bead 0603", 0.015, "GOOD", hi)
    if pre in ("D", "ED"):
        if "SMA" in fp:
            return ("SMA diode (" + row["value"] + ")", 0.03, "GOOD", hi)
        if "0402" in fp:
            return ("ESD diode 0402 (" + row["value"] + ")", 0.02, "GOOD", NC)
        return ("small-signal / TVS diode (" + row["value"] + ")", 0.03, "GOOD", NC)
    if pre == "LED":
        return ("LED 0603", 0.01, "GOOD", hi)
    if pre == "F":
        return ("resettable fuse 1206", 0.05, "GOOD", NC)
    if pre == "L":
        if "CommonMode" in fp or "CMC" in fp:
            return ("common-mode choke (" + row["value"] + ")", 0.05, "CHECK", NC)
        return ("power inductor (" + row["value"] + ")", 0.05, "GOOD", NC)
    if pre == "Q":
        return ("small MOSFET SOT-23 (" + row["value"] + ")", 0.03, "GOOD", NC)
    if pre == "SW":
        return ("tactile switch", 0.04, "GOOD", NC)
    if pre == "Y":
        return ("crystal " + row["value"], 0.09, "GOOD", NC)
    return (row["value"], 0.05, "CHECK", NC)


def main():
    bom = os.path.join(COMMANDER, "fabrication", "bom", f"{cpmodel.PRJ}_{cpmodel.REV}_bom.csv")
    rows = [r for r in csv.DictReader(open(bom, encoding="utf-8")) if (r.get("populate") or "").upper() != "DNP"]
    detail, total = [], [0.0] * 6
    nparts = 0
    for n, r in enumerate(rows, 1):
        q = int(r["qty"])
        nparts += q
        if r["value"] in KEY:
            part, mfr, lcsc, avail, s1, s2, prices, basis, note = KEY[r["value"]]
        else:
            part, base, avail, s1 = generic(r)
            mfr, lcsc, s2, prices, basis, note = "any", "", NC, ladder(base), "estimate (typical LCSC price for the part class)", ""
        ext = [round(q * p, 4) for p in prices]
        total = [t + e for t, e in zip(total, ext)]
        detail.append([n, q, r["value"], r["footprint"], r["references"], part, mfr, lcsc, avail, s1, s2] + prices + ext + [basis, note])

    # ---- board, assembly, test: estimates, see the notes in the file ----
    pcb = [38.0, 24.0, 9.5, 6.5, 5.2, 4.5]
    assy = [70.0, 40.0, 11.0, 6.5, 5.0, 4.2]
    test = [10.0, 8.0, 4.0, 2.0, 1.5, 1.2]
    per_board = [c + p + a + t for c, p, a, t in zip(total, pcb, assy, test)]
    order = [pb * q for pb, q in zip(per_board, QTY)]

    out = os.path.join(COMMANDER, "fabrication", "estimated-cost.csv")
    head_q = [f"{q:,} boards".replace(",", " ") for q in QTY]
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["COMMANDER MAINBOARD rev A1 - ESTIMATED COST AND PART AVAILABILITY (US dollars)"])
        w.writerow(["Prepared 2026-11-13. A BUDGET, NOT A QUOTATION: prices and stock are snapshots found on distributor pages through web search, of unknown age;"
                    " several contradict each other; prices above 100 pieces are mostly estimates. The board is not finished, so the parts list can still change."])
        w.writerow(["Not included: shipping, import duties and taxes, tooling / engineering charges, the case, the keyboard, the battery module, yield losses."])
        w.writerow([])
        w.writerow(["1. SUMMARY - cost per board"] + head_q)
        for name, vals in (("Components (" + str(nparts) + " parts on " + str(len(rows)) + " lines)", total), ("Bare board (6 layers, 1.2 mm, ENIG, via-in-pad, impedance control)", pcb),
                           ("Assembly (both sides, 0.4 mm BGA, X-ray)", assy), ("Programming and functional test", test), ("TOTAL PER BOARD", per_board)):
            w.writerow([name] + [f"{v:.2f}" for v in vals])
        w.writerow(["TOTAL FOR THE ORDER"] + [f"{v:.0f}" for v in order])
        w.writerow([])
        w.writerow(["How the three non-component lines were estimated"])
        w.writerow(["Bare board", "The outline fits a 325 x 138 mm rectangle (0.045 m2) although the L shape itself is only about 0.011 m2; the price assumes the rectangle is paid for."
                    " Sharing the panel with the keyboard, as planned, lowers it. Low quantities are dominated by the set-up charge for a 6-layer impedance board."])
        w.writerow(["Assembly", "About 640 parts and 3,000 solder joints on two sides. At 5 and 10 boards the cost is mostly set-up, two stencils and the per-part loading fee"
                    " for parts outside the assembler's standard library (about 70 different ones)."])
        w.writerow(["Test", "Flashing the eMMC and a power-up / PoE / USB check. By hand at low quantity, on a fixture from 1,000."])
        w.writerow([])
        w.writerow(["2. AVAILABILITY WATCH-LIST - parts that need a decision before production"])
        w.writerow(["Rating", "Value", "Suggested part", "Stock at LCSC / JLCPCB (snapshot)", "Stock at other distributors (snapshot)", "What to do"])
        order_r = {"RISK": 0, "LIMITED": 1, "CHECK": 2}
        for d in sorted([d for d in detail if d[8] in order_r], key=lambda d: (order_r[d[8]], -d[11 + 6 + 2])):
            w.writerow([d[8], d[2], d[5], d[9], d[10], d[-1]])
        w.writerow(["Ratings", "GOOD = thousands in stock or many interchangeable makers.  OK = stocked, fewer sources.  LIMITED = stocked in small numbers; needs a planned purchase."
                    "  RISK = out of stock, single source or discontinued.  CHECK = not looked up or no part chosen yet."])
        w.writerow(["PCBWay", "PCBWay does not keep its own parts library the way JLCPCB / LCSC does; it buys from distributors (DigiKey, Mouser, LCSC and others), so the same stock figures apply."])
        w.writerow([])
        w.writerow(["3. DETAIL - every line of the parts list"])
        w.writerow(["Line", "Qty per board", "Value", "Package", "References", "Suggested part", "Manufacturer", "LCSC part no.", "Availability",
                    "Stock at LCSC / JLCPCB (snapshot)", "Stock at other distributors (snapshot)"]
                   + ["Unit price @ " + h for h in head_q] + ["Cost per board @ " + h for h in head_q] + ["Price basis", "Notes"])
        for d in detail:
            w.writerow(d[:11] + [f"{v:.4f}" for v in d[11:17]] + [f"{v:.3f}" for v in d[17:23]] + d[23:])
        w.writerow(["", "", "", "", "", "", "", "", "", "", "COMPONENTS, per board"] + [""] * 6 + [f"{v:.2f}" for v in total])
    print("wrote", out)
    print("per board:", "  ".join(f"{q}: {v:.2f}" for q, v in zip(QTY, per_board)))
    print("components:", "  ".join(f"{v:.2f}" for v in total))
    top = sorted(detail, key=lambda d: -d[19])[:12]
    print("largest lines at 100 boards:", "; ".join(f"{d[2]} {d[19]:.2f}" for d in top))
    print("watch-list:", ", ".join(f"{d[2]} ({d[8]})" for d in detail if d[8] in ("RISK", "LIMITED")))


if __name__ == "__main__":
    main()

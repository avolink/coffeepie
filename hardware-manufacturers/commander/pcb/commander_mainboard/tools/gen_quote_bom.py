#!/usr/bin/env python3
"""gen_quote_bom.py - bills of materials for a supplier's quotation, from the design model of every production board.

    python tools/gen_quote_bom.py            (any Python 3 with openpyxl; KiCad is not needed)

Writes to fabrication/bom/quote/:
    commander_quote_bom.xlsx          one workbook: "Read me", "Boards" (board specs for the PCB / assembly quote),
                                      "Kit" (every part once, quantity per board and per kit, with the number of
                                      boards per kit and of kits editable - the totals are formulas), and one sheet per
                                      board; the price / MOQ / lead-time columns are left empty for the supplier
    <project>_<rev>_quote.csv         the same per-board lists as plain CSV

The build BOMs (fabrication/bom/<project>_<rev>_bom.csv, written by gen_bom.py) stay what they are: lists by value
for the assembler.  Here every line carries a full purchasing spec (resistance, tolerance, power, size; capacitance,
voltage, dielectric, size; ...), and a manufacturer part number where the design names one.  Generic passives carry
a spec only: any brand meeting it may be quoted (that is how a local distributor quotes them best).

Not in these lists: parts that are only copper (cell pads, card-edge fingers, solder joints between boards), test
pads, DNP positions, and the boards themselves (their specs are on the "Boards" sheet).
"""
import csv
import json
import os
import re
import subprocess
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.normpath(os.path.join(HERE, "..", ".."))
FAB = os.path.normpath(os.path.join(PCB, "..", "fabrication"))
OUT = os.path.join(FAB, "bom", "quote")

# project folder, name in the workbook, boards per kit (editable in the workbook), finish if the design needs one
BOARDS = [
    ("commander_mainboard", "Mainboard", 1, "ENIG (0.4-0.65 mm BGA / QFN pitch)"),
    ("commander_hub", "Hub", 1, "ENIG + 20 deg bevelled M.2 gold fingers"),
    ("commander_keyboard", "Keyboard", 1, ""),
    ("commander_battery", "Battery module", 1, ""),
    ("commander_tray", "Tray carrier", 1, "ENIG (pogo / magnet contact pads)"),
    ("commander_numpad", "Numpad module", 1, "ENIG (snap-dome pads)"),
    ("commander_touchpad", "Touchpad module", 1, ""),
    ("commander_bar_bms", "Battery bar BMS", 0, "ENIG"),
    ("commander_bar_contacts", "Battery bar contacts", 0, "ENIG (cell contact pads), castellated edge"),
]
NO_PART = {"BATT_PAD", "BARJOINT", "BARJOINT_C", "M2_EDGE_M"}       # copper only, nothing to buy

# ------------------------------------------------------------------------------------------------ dump (per project)


def dump():
    sys.path.insert(0, HERE)
    import cpmodel
    import gen_bom
    d = cpmodel.load()
    onboard = gen_bom.board_footprints()
    comps = []
    for c in d.comps.values():
        part = getattr(c, "part", None)
        comps.append(dict(ref=c.ref, kind=c.kind, part=part, value=c.value, fp=onboard.get(c.ref, c.fp), model_fp=c.fp, desc=c.desc,
                          dnp=bool(c.dnp), lcsc=cpmodel.PARTS.get(part, {}).get("lcsc", "") if part else ""))
    print(json.dumps(dict(prj=cpmodel.PRJ, rev=cpmodel.REV, comps=comps)))


# ------------------------------------------------------------------------------------------------ purchasing specs

SIZE = {"0201": "0201 (0603 metric)", "0402": "0402 (1005 metric)", "0603": "0603 (1608 metric)",
        "0805": "0805 (2012 metric)", "1206": "1206 (3216 metric)", "1210": "1210 (3225 metric)",
        "1808": "1808 (4520 metric)", "2512": "2512 (6332 metric)"}
R_POWER = {"0201": "1/20 W", "0402": "1/16 W", "0603": "1/10 W", "0805": "1/8 W", "1206": "1/4 W", "2512": "1 W"}


def pkg_of(fp, c=None):
    """Chip size: from the footprint on the board, else from the value (10K_0805), else from the model's footprint
    (the keyboard's board came from Altium and names its footprints its own way)."""
    pat = r"_(0201|0402|0603|0805|1206|1210|1808|2512)(?=_|$)"
    for s in ([fp] + ([c["value"], c.get("model_fp", "")] if c else [])):
        m = re.search(pat, "_" + (s or ""))
        if m:
            return m.group(1)
    return ""


def ohms(tok):
    t = tok.upper().replace("Ω", "")
    m = re.match(r"^(\d+)R(\d+)$", t)                     # 0R02 = 0.02 ohm
    if m:
        return float(m.group(1) + "." + m.group(2))
    m = re.match(r"^([\d.]+)([RKM]?)$", t)
    if not m:
        return None
    return float(m.group(1)) * {"": 1, "R": 1, "K": 1e3, "M": 1e6}[m.group(2)]


def fmt_ohm(v):
    if v == 0:
        return "0 Ω"
    for div, unit in ((1e6, "MΩ"), (1e3, "kΩ"), (1, "Ω"), (1e-3, "mΩ")):
        if v >= div:
            return ("%g " % round(v / div, 4)) + unit
    return "%g Ω" % v


def farads(tok):
    m = re.match(r"^([\d.]+)(p|n|u|µ)F$", tok, re.I)
    if not m:
        return None
    return float(m.group(1)) * {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6}[m.group(2).lower()]


def fmt_f(v):
    for div, unit in ((1e-6, "µF"), (1e-9, "nF"), (1e-12, "pF")):
        if v >= div * 0.999:
            return ("%g " % round(v / div, 4)) + unit
    return "%g F" % v


def resistor(c):
    toks = c["value"].split("_")
    pkg = pkg_of(c["fp"], c) or "0402"
    v = ohms(toks[0])
    if toks[0].upper().startswith("NTC"):
        m = re.match(r"NTC(\d+)K_B(\d+)", c["value"].upper())
        return dict(cat="Thermistor", spec="NTC thermistor %s kΩ ±1 %% at 25 °C, B25/50 = %s K ±1 %%, %s"
                    % (m.group(1), m.group(2), SIZE[pkg]), value=c["value"], pkg=pkg)
    if toks[0].upper().startswith("FB"):
        return ferrite(c)
    if v is None:
        return dict(cat="Resistor", spec="resistor %s, %s (CHECK value)" % (c["value"], SIZE.get(pkg, pkg)), value=c["value"], pkg=pkg)
    if v == 0:
        return dict(cat="Resistor", spec="0 Ω jumper, %s" % SIZE.get(pkg, pkg), value="0R", pkg=pkg)
    sense = v < 1.0
    power = next((t for t in toks if t.upper().endswith("W")), None)
    power = power.replace("W", " W") if power else (
        {"0805": "1/4 W", "1206": "1/2 W"}.get(pkg, R_POWER.get(pkg, "")) if sense else R_POWER.get(pkg, ""))
    tol = "±1 %"
    spec = "%sresistor %s %s %s, %s%s" % ("current-sense " if sense else "chip ", fmt_ohm(v), tol, power, SIZE.get(pkg, pkg),
                                          ", thick film" if not sense else ", metal / low-TCR")
    return dict(cat="Resistor", spec=spec, value=c["value"], pkg=pkg)


def ferrite(c):
    v = c["value"].upper()
    pkg = pkg_of(c["fp"], c) or "0402"
    m = re.match(r"^(?:FB)?(\d+)R", v)
    cur = re.search(r"_(\d+(?:\.\d+)?)A", v)
    spec = "ferrite bead %s Ω at 100 MHz%s, %s" % (m.group(1) if m else "?", ", rated >= %s A" % cur.group(1) if cur else "", SIZE.get(pkg, pkg))
    return dict(cat="Ferrite bead", spec=spec, value=c["value"], pkg=pkg)


def capacitor(c):
    toks = c["value"].split("_")
    pkg = pkg_of(c["fp"], c)
    v = farads(toks[0])
    if toks[0].upper() == "0R":
        return dict(cat="Resistor", spec="0 Ω jumper, %s" % SIZE.get(pkg, pkg), value="0R", pkg=pkg)
    if v is None:
        return dict(cat="Capacitor", spec="capacitor %s (CHECK value)" % c["value"], value=c["value"], pkg=pkg)
    volt = next((t for t in toks[1:] if re.match(r"^[\d.]+k?V$", t, re.I)), None)
    if volt:
        volt = re.sub(r"^([\d.]+)(k?)V$", lambda m: m.group(1) + " " + m.group(2) + "V", volt, flags=re.I)
    up = [t.upper() for t in toks[1:]]
    if "POLY" in up:
        return dict(cat="Capacitor", spec="polymer tantalum capacitor %s %s, EIA 7343 (D case), max 2.0 mm tall, low ESR"
                    % (fmt_f(v), volt or "6.3 V"), value=c["value"], pkg="7343")
    if "ALU" in up:
        return dict(cat="Capacitor", spec="aluminium electrolytic capacitor %s %s, SMD 6.3 x 7.7 mm, 105 °C"
                    % (fmt_f(v), volt), value=c["value"], pkg="6.3x7.7")
    if "Y" in up:
        return dict(cat="Capacitor", spec="safety capacitor class Y2 (or Y1) %s, %s rated, SMD %s"
                    % (fmt_f(v), volt, SIZE.get(pkg, pkg)), value=c["value"], pkg=pkg)
    if volt is None:            # the design marks a rating only where the rail is above 5 V
        volt = "50 V" if v < 1e-7 else "16 V" if v <= 1e-6 + 1e-12 else "10 V"
    if v <= 1.0e-9 + 1e-15:
        diel = "C0G / NP0"
    elif v < 1e-6 - 1e-12:
        diel = "X7R"
    else:
        diel = "X5R or X7R"
    if volt.upper().endswith("KV"):
        diel = "X7R, high voltage"
    return dict(cat="Capacitor", spec="MLCC %s %s %s ±10 %%, %s" % (fmt_f(v), volt, diel, SIZE.get(pkg, pkg)),
                value=c["value"], pkg=pkg)


def inductor(c):
    toks = c["value"].split("_")
    m = re.match(r"^([\d.]+)(u|n)H$", toks[0], re.I)
    val = (float(m.group(1)) * (1 if m.group(2).lower() == "u" else 1e-3)) if m else None
    cur = next((t for t in toks[1:] if t.upper().endswith("A")), None)
    fp = c["fp"].split(":")[-1]
    size = {"L_Sunlord_SWPA4030S": "4.0 x 4.0 x 3.0 mm, shielded", "L_Coilcraft_XAL4020-XXX": "4.0 x 4.0 x 2.1 mm max, shielded, molded",
            "L_1008_2520Metric": "2.5 x 2.0 mm (1008), shielded", "L_0805_2012Metric": "0805 (2012 metric)"}.get(fp, fp)
    vtxt = ("%g µH" % val) if val is not None and val >= 1 else ("%g nH" % (val * 1000)) if val is not None else c["value"]
    spec = "power inductor %s ±20 %%%s, %s" % (vtxt, ", Isat >= %s" % cur.replace("A", " A") if cur else "", size)
    note = ""
    if val and val >= 10 and cur and float(cur[:-1]) >= 5 and "XAL4020" in fp:
        note = "CHECK: 4 x 4 mm parts at 10 µH saturate at about 2-3 A; the 3 A buck needs Isat >= 3.5 A - a 5 x 5 mm part or a lower value"
    return dict(cat="Inductor", spec=spec, value=c["value"], pkg=size, note=note)


def fuse(c):
    v = c["value"]
    m = re.match(r"^PTC(\d{4})?:([\d.]+m?A)(?:_(\d+)V)?", v)
    pkg = pkg_of(c["fp"], c) or "1206"
    hold = m.group(2) if m else v
    spec = "PTC resettable fuse, hold %s%s, %s" % (re.sub(r"(m?A)$", r" \1", hold),
                                                    ", Vmax >= %s V" % m.group(3) if m and m.group(3) else ", Vmax >= 6 V", SIZE.get(pkg, pkg))
    note = ""
    if m and m.group(1) and m.group(1) != pkg:
        note = "CHECK: value says a %s part, the board has a %s footprint (a 2 A PTC at 30 V is an 1812 part)" % (m.group(1), pkg)
    return dict(cat="Fuse", spec=spec, value=v, pkg=pkg, note=note)


# Named parts: (manufacturer, manufacturer part number, note).  "multi-source" = a generic part made by many.
MPN = {
    "SS34": ("multi-source (MDD, MCC, onsemi, ...)", "SS34", "Schottky 40 V 3 A"),
    "SS110": ("multi-source", "SS110", "Schottky 100 V 1 A"),
    "B5819W": ("multi-source", "B5819W", "Schottky 40 V 1 A"),
    "1N5819WT": ("multi-source", "1N5819WT", "Schottky 40 V 1 A, SOD-523"),
    "BAV21W": ("multi-source (Diodes Inc. BAV21W-7-F)", "BAV21W", "switching diode 200 V"),
    "ES1D": ("multi-source", "ES1D", "fast rectifier 200 V 1 A"),
    "PDS1040": ("Diodes Inc.", "PDS1040-13", "Schottky 40 V 10 A, PowerDI-5"),
    "PMEG4030ER": ("Nexperia", "PMEG4030ER-QX", "Schottky 40 V 3 A, SOD-123W"),
    "BAT54C": ("multi-source", "BAT54C", "dual Schottky, common cathode"),
    "SMF24CA": ("multi-source (Littelfuse, ...)", "SMF24CA", "TVS 24 V bidirectional, SOD-123F"),
    "SMF5.0CA": ("multi-source", "SMF5.0CA", "TVS 5 V bidirectional, SOD-123F"),
    "SMAJ58A": ("multi-source", "SMAJ58A", "TVS 58 V unidirectional, SMA"),
    "AZ5825-01F": ("Amazing Microelectronic", "AZ5825-01F.R7GR", "TVS / ESD 0402"),
    "BTR04G02": ("(see LCSC listing)", "BTR04G02", "ESD diode bidirectional 0402"),
    "AO3401A": ("Alpha & Omega", "AO3401A", "P-MOSFET 30 V"),
    "AO3407A": ("Alpha & Omega", "AO3407A", "P-MOSFET 30 V"),
    "WPM2341": ("WillSemi", "WPM2341-3/TR", "P-MOSFET 20 V"),
    "WPM3407": ("WillSemi", "WPM3407-3/TR", "P-MOSFET 30 V"),
    "2N7002": ("multi-source", "2N7002", "N-MOSFET 60 V"),
    "2SK3018": ("multi-source (Rohm origin)", "2SK3018", "N-MOSFET 30 V"),
    "MMBT2222A": ("multi-source", "MMBT2222A", "NPN"),
    "150V_60mR": ("(to be chosen: e.g. Vishay SiS 150 V series)", "", "N-MOSFET 150 V, 60 mΩ, PowerPAK 1212-8"),
    "TL431": ("multi-source", "TL431 (SOT-23, DBZ pinout: 1 = REF, 2 = K, 3 = A)", ""),
    "TLP291": ("Toshiba", "TLP291(GB-TP,SE", "alternatives: Everlight EL3H7, Lite-On LTV-217"),
    "AP22804AW5": ("Diodes Inc.", "AP22804AW5-7", ""),
    "SY6280AAC": ("Silergy", "SY6280AAC", ""),
    "TLV62569": ("Texas Instruments", "TLV62569DBVR", ""),
    "HT7333": ("Holtek", "HT7333-A (SOT-89)", ""),
    "ME6211C33M5G": ("Microne", "ME6211C33M5G-N", ""),
    "MT3608": ("Aerosemi", "MT3608", ""),
    "INA181A1": ("Texas Instruments", "INA181A1IDBVR", ""),
    "TPS54302": ("Texas Instruments", "TPS54302DDCR", ""),
    "TPS563201": ("Texas Instruments", "TPS563201DDCR", ""),
    "TPS709": ("Texas Instruments", "TPS70933DBVR", ""),
    "TPS2121": ("Texas Instruments", "TPS2121RUXR", ""),
    "TPS23754": ("Texas Instruments", "TPS23754PWP", ""),
    "HD3SS3220": ("Texas Instruments", "HD3SS3220RNHR", ""),
    "TPD4E05U06": ("Texas Instruments", "TPD4E05U06DQAR", ""),
    "FUSB302B": ("onsemi", "FUSB302BMPX", "alternative: Etek ET7301B"),
    "USB5744": ("Microchip", "USB5744-I/2G", ""),
    "USB2517": ("Microchip", "USB2517-JZX", ""),
    "CH334P": ("WCH", "CH334P", ""),
    "IQS550": ("Azoteq", "IQS550-B000-QNR", ""),
    "STC8H8K64U": ("STC Micro", "STC8H8K64U-45I-LQFP32", ""),
    "ATmega32U4-AU": ("Microchip", "ATMEGA32U4-AU", ""),
    "AT24C02": ("multi-source (Microchip AT24C02, ...)", "AT24C02 SOT-23-5", ""),
    "USBLC6-2SC6": ("STMicroelectronics", "USBLC6-2SC6", ""),
    "RK3566": ("Rockchip", "RK3566", ""),
    "RK817": ("Rockchip", "RK817-5", ""),
    "RK860": ("Rockchip", "RK860-0", ""),
    "RTL8211F": ("Realtek", "RTL8211F-CG", ""),
    "UM3204H": ("Union Semiconductor", "UM3204H", ""),
    "EMMC153": ("Samsung", "KLM8G1GETF-B041", "8 GB; KLMAG1JETD-B041 (16 GB) fits the same footprint"),
    "LPDDR4_200": ("Samsung", "K4F8E3S4HD-MGCL", "1 GB; K4F6E3S4HM (2 GB) fits the same footprint"),
    "M2_SOCKET_M": ("LOTES", "APCI0107-P001A", "M.2 Key M, H4.2"),
    "PLN060-ER20A05S": ("Bourns", "PLN060-ER20A05S", ""),
    "GB020G00": ("(Radxa's part; see LCSC listing)", "GB020G00", "LAN transformer 1:1 with centre taps"),
    "RJ45_8P": ("HanRun", "HR6042S-1188N15B-1R", ""),
    "HDMI_MICRO_D": ("Molex", "46765-2xxx (see footprint)", "micro HDMI type D receptacle"),
    "MICROSD": ("Molex", "104031-0811", ""),
    "USBC16": ("HOAUC", "HYCW498-USBC16-735B", "alternative: HRO TYPE-C-31-M-12"),
    "USBC24": ("HOAUC", "HYCW275-USBC24-050B", ""),
    "USBC24_SINK": ("Amphenol", "12402072E512A", "not stocked at LCSC: from Amphenol's distributors"),
    "JST_PH2": ("JST", "B2B-PH-K-S(LF)(SN)", ""),
    "JST_PH4": ("JST", "B4B-PH-K-S(LF)(SN)", ""),
    "JST_PH5": ("JST", "B5B-PH-K-S(LF)(SN)", ""),
    "JST_SH4_UART": ("JST", "SM04B-SRSS-TB(LF)(SN)", ""),
    "TACT": ("C&K", "KMR221GLFS", "or equivalent 4.2 x 2.8 mm tact switch"),
    "TACT_SIDE": ("Panasonic", "EVQ-P7A01P", "side-operated, 3.5 x 2.9 x 1.35 mm"),
    "POGO_FW8": ("CFE", "BP33242-08200H0-FS", ""),
    "KEYSW_OPT": ("Keychron", "low-profile optical switch", "plug-in (not soldered)"),
    "DOME12": ("(dome sheet supplier)", "12 mm four-leg metal snap dome", "on a dome sheet, not soldered"),
    "BCMF062P120T": ("(see LCSC listing)", "BCMF062P120T", "common-mode choke, 0504"),
    "BCMF122P900H": ("(see LCSC listing)", "BCMF122P900H", "common-mode choke, 0805"),
    "CC2012A-801": ("(see LCSC listing)", "CC2012A-801", "common-mode choke, 0805"),
}


def named(c):
    part, value = c["part"], c["value"]
    key = value if value in MPN else part if part in MPN else None
    if part == "STC8H_LQFP32":
        key = "STC8H8K64U"
    if part == "ATMEGA32U4":
        key = "ATmega32U4-AU"
    fp = c["fp"].split(":")[-1]
    desc = c["desc"]
    cat = {"SCHOTTKY": "Diode", "SCHOTTKY_123W": "Diode", "SCHOTTKY_PWR": "Diode", "DIODE": "Diode", "TVS": "Diode",
           "TVS_UNI": "Diode", "ESD": "Diode", "BAT54C": "Diode", "NMOS_GSD": "Transistor", "PMOS_GSD": "Transistor",
           "NMOS_PWR": "Transistor", "NPN_BEC": "Transistor", "LED": "LED", "CMC": "Inductor", "XTAL2": "Crystal",
           "XTAL4": "Crystal", "OPTO": "IC"}.get(part)
    if cat is None:
        cat = ("Connector" if re.match(r"^(USBC|JST|HDR|ISP|JUMPER|RJ45|HDMI|MICROSD|M2_|POGO)", part)
               else "Switch" if part.startswith(("TACT", "KEYSW", "DOME")) else "Transformer" if part.startswith("XFMR") else "IC")
    if part == "LED":
        return dict(cat=cat, spec="LED %s, 0603, 20 mA class" % value.lower(), value=value, pkg="0603",
                    mfr="multi-source", mpn="", note="")
    if part in ("XTAL2", "XTAL4"):
        return dict(cat=cat, spec="crystal %s, %s, ±20 ppm, load capacitance to suit the board's capacitors (see schematic)"
                    % (value, "3.2 x 1.5 mm" if part == "XTAL2" else "3.2 x 2.5 mm 4-pad"), value=value, pkg=fp,
                    mfr="multi-source", mpn="", note="")
    if part.startswith(("HDR", "ISP", "JUMPER")):
        return dict(cat=cat, spec=desc, value=value, pkg=fp, mfr="multi-source", mpn="", note="")
    mfr, mpn, note = MPN.get(key, ("", "", ""))
    if key == "PLN060-ER20A05S" or part == "XFMR_FLYBACK":
        mfr, mpn, note = MPN["PLN060-ER20A05S"]
    if not desc:
        desc = value
    return dict(cat=cat, spec=desc, value=value, pkg=fp, mfr=mfr, mpn=mpn, note=note)


def line_of(c):
    k = c["kind"]
    if k == "R":
        d = resistor(c)
    elif k == "C":
        d = capacitor(c)
    elif k == "L":
        d = inductor(c)
    elif k == "FB":
        d = ferrite(c)
    elif k == "F":
        d = fuse(c)
    else:
        d = named(c)
    d.setdefault("mfr", "any (to spec)" if k in ("R", "C", "L", "FB", "F") else "")
    d.setdefault("mpn", "")
    d.setdefault("note", "")
    d["lcsc"] = c.get("lcsc", "")
    return d


def natural(ref):
    m = re.match(r"^([A-Z]+)(\d+)$", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def board_lines(data):
    groups = OrderedDict()
    for c in data["comps"]:
        if c["kind"] == "TP" or c["dnp"] or c["part"] in NO_PART or c["value"].upper() == "DNP":
            continue
        d = line_of(c)
        key = (d["cat"], d["spec"], d["mfr"], d["mpn"])
        g = groups.setdefault(key, dict(d, refs=[]))
        g["refs"].append(c["ref"])
        if c.get("lcsc") and not g.get("lcsc"):
            g["lcsc"] = c["lcsc"]
    order = ["IC", "Transistor", "Diode", "LED", "Crystal", "Transformer", "Inductor", "Ferrite bead", "Fuse", "Thermistor",
             "Capacitor", "Resistor", "Connector", "Switch"]
    rows = sorted(groups.values(), key=lambda g: (order.index(g["cat"]) if g["cat"] in order else 99, g["spec"]))
    for g in rows:
        g["refs"].sort(key=natural)
    return rows


# ------------------------------------------------------------------------------------------------ board specs


def board_specs(prj):
    path = os.path.join(PCB, prj, prj + ".kicad_pcb")
    if not os.path.exists(path):
        return {}
    txt = open(path, encoding="utf-8").read()
    th = re.search(r"\(general\s*\(thickness ([\d.]+)\)", txt)
    lay = re.search(r"\(layers(.*?)\n\t\)", txt, re.S)
    ncu = len(re.findall(r'"[A-Za-z0-9.]*\.Cu"\s+(?:signal|power|mixed|jumper)', lay.group(1))) if lay else 0
    xs, ys = [], []
    for item in re.split(r"\n\t\(", txt):           # the board's top-level items, one at a time
        if not item.startswith(("gr_line", "gr_arc", "gr_rect", "gr_circle", "gr_poly")) or '(layer "Edge.Cuts")' not in item:
            continue
        for p in re.finditer(r"\((?:start|end|mid|xy) ([\-\d.]+) ([\-\d.]+)\)", item):
            xs.append(float(p.group(1)))
            ys.append(float(p.group(2)))
    size = "%.1f x %.1f mm" % (max(xs) - min(xs), max(ys) - min(ys)) if xs else ""
    return dict(thickness=th.group(1) + " mm" if th else "", layers=ncu, size=size)


def placement_counts(prj, rev, refs):
    """Fitted parts per side (the placement file also lists DNP positions: only the BOM's references count)."""
    path = os.path.join(FAB, "position", "%s_%s_placement.csv" % (prj, rev))
    top = bot = 0
    if os.path.exists(path):
        for r in csv.DictReader(open(path, encoding="utf-8")):
            if r.get("Ref") not in refs:
                continue
            if r.get("Side") == "top":
                top += 1
            elif r.get("Side") == "bottom":
                bot += 1
    return top, bot


# ------------------------------------------------------------------------------------------------ main


def main():
    datas = []
    for prj, name, per_kit, finish in BOARDS:
        env = dict(os.environ, CP_ROOT=os.path.join(PCB, prj))
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--dump"], env=env, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise SystemExit("%s: %s" % (prj, r.stderr[-2000:]))
        data = json.loads(r.stdout.strip().splitlines()[-1])
        datas.append((prj, name, per_kit, finish, data, board_lines(data)))
    os.makedirs(OUT, exist_ok=True)
    head = ["line", "category", "description / purchasing spec", "design value", "package", "manufacturer",
            "manufacturer part number", "notes", "LCSC reference", "qty per board", "designators"]
    for prj, name, per_kit, finish, data, rows in datas:
        with open(os.path.join(OUT, "%s_%s_quote.csv" % (prj, data["rev"])), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(head)
            for i, g in enumerate(rows, 1):
                w.writerow([i, g["cat"], g["spec"], g["value"], g["pkg"], g["mfr"], g["mpn"], g["note"], g["lcsc"],
                            len(g["refs"]), " ".join(g["refs"])])
    try:
        import openpyxl
    except ImportError:
        print("openpyxl not installed: CSV files only (pip install openpyxl for the workbook)")
        return
    write_xlsx(datas)


def write_xlsx(datas):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter as col
    wb = openpyxl.Workbook()
    bold = Font(bold=True)
    fill = PatternFill("solid", fgColor="DDEBF7")
    edit = PatternFill("solid", fgColor="FFF2CC")
    wrap = Alignment(wrap_text=True, vertical="top")

    def header(ws, row, names, widths=None):
        for i, n in enumerate(names, 1):
            c = ws.cell(row=row, column=i, value=n)
            c.font, c.fill, c.alignment = bold, fill, wrap
        if widths:
            for i, wdt in enumerate(widths, 1):
                ws.column_dimensions[col(i)].width = wdt
        ws.freeze_panes = ws.cell(row=row + 1, column=1)

    ws = wb.active
    ws.title = "Read me"
    lines = [
        ("Commander terminal - bill of materials for quotation", bold),
        ("Generated from the design model by tools/gen_quote_bom.py; do not edit by hand - regenerate.", None),
        ("", None),
        ("Sheets", bold),
        ("Boards: the printed circuit boards (size, layers, thickness, finish) and the number of parts to place per side.", None),
        ("Kit: every part once, with its quantity on each board and per kit. Yellow cells are editable: the number of each "
         "board per kit (battery bar = optional accessory, 0 by default) and the number of kits to quote; the totals follow.", None),
        ("One sheet per board: the same lines with their designators.", None),
        ("", None),
        ("How to read a line", bold),
        ("Generic passives (resistors, capacitors, inductors, ferrite beads, fuses) carry a full spec and 'any (to spec)': "
         "any brand meeting the spec may be quoted; please state the part number offered.", None),
        ("Named parts carry the manufacturer part number the design uses. 'multi-source' = a standard part made by several "
         "manufacturers; any of them may be quoted.", None),
        ("LCSC reference: a catalogue number where one is known, for identification only.", None),
        ("Lines marked CHECK in the notes are open design questions - quote the spec as written and say if it cannot be met.", None),
        ("Columns for the supplier (Kit sheet): unit price, MOQ, lead time, offered part number, remarks.", None),
        ("", None),
        ("Not included", bold),
        ("Parts that are only copper on the board (cell contact pads, M.2 card-edge fingers, the solder joint between the "
         "two battery-bar boards), test pads and positions marked DNP (not fitted).", None),
        ("The 42 + 6 AAA NiMH cells, the solar panel, enclosure, cables, key caps and screws.", None),
    ]
    for i, (t, f) in enumerate(lines, 1):
        c = ws.cell(row=i, column=1, value=t)
        c.alignment = Alignment(wrap_text=True)
        if f:
            c.font = f
    ws.column_dimensions["A"].width = 130

    ws = wb.create_sheet("Boards")
    header(ws, 1, ["board", "project / revision", "size (outline)", "copper layers", "thickness", "finish / special",
                   "parts placed top", "parts placed bottom", "BOM lines", "boards per kit"],
           [22, 30, 18, 10, 10, 44, 12, 12, 10, 10])
    for i, (prj, name, per_kit, finish, data, rows) in enumerate(datas, 2):
        s = board_specs(prj)
        top, bot = placement_counts(prj, data["rev"], {r for g in rows for r in g["refs"]})
        for j, v in enumerate([name, "%s %s" % (prj, data["rev"]), s.get("size", ""), s.get("layers", ""), s.get("thickness", ""),
                               finish or "HASL lead-free or ENIG", top, bot, len(rows), per_kit], 1):
            ws.cell(row=i, column=j, value=v)
        ws.cell(row=i, column=10).fill = edit

    # the kit: one row per distinct part
    kit = OrderedDict()
    for bi, (prj, name, per_kit, finish, data, rows) in enumerate(datas):
        for g in rows:
            key = (g["cat"], g["spec"], g["mfr"], g["mpn"])
            k = kit.setdefault(key, dict(g, per=[0] * len(datas)))
            k["per"][bi] += len(g["refs"])
            if g["note"] and g["note"] not in k["note"]:
                k["note"] = (k["note"] + "; " if k["note"] else "") + g["note"]
    ws = wb.create_sheet("Kit")
    nb = len(datas)
    ws.cell(row=1, column=1, value="kits to quote").font = bold
    kc = ws.cell(row=1, column=3, value=1000)
    kc.fill = edit
    ws.cell(row=2, column=1, value="boards per kit").font = bold
    first_q = 9
    for bi, (prj, name, per_kit, finish, data, rows) in enumerate(datas):
        c = ws.cell(row=2, column=first_q + bi, value=per_kit)
        c.fill = edit
    names = ["line", "category", "description / purchasing spec", "package", "manufacturer", "manufacturer part number",
             "notes", "LCSC reference"] + [d[1] for d in datas] + ["qty per kit", "qty to quote",
             "unit price", "currency", "MOQ", "lead time", "offered part number", "remarks"]
    header(ws, 3, names, [6, 12, 60, 18, 22, 26, 30, 12] + [9] * nb + [10, 12, 10, 9, 8, 10, 24, 30])
    order = ["IC", "Transistor", "Diode", "LED", "Crystal", "Transformer", "Inductor", "Ferrite bead", "Fuse", "Thermistor",
             "Capacitor", "Resistor", "Connector", "Switch"]
    items = sorted(kit.values(), key=lambda g: (order.index(g["cat"]) if g["cat"] in order else 99, g["spec"]))
    q0, q1 = col(first_q), col(first_q + nb - 1)
    for i, g in enumerate(items, 1):
        r = 3 + i
        vals = [i, g["cat"], g["spec"], g["pkg"], g["mfr"], g["mpn"], g["note"], g["lcsc"]] + [n or None for n in g["per"]]
        for j, v in enumerate(vals, 1):
            ws.cell(row=r, column=j, value=v).alignment = wrap if j in (3, 7) else Alignment(vertical="top")
        ws.cell(row=r, column=first_q + nb, value="=SUMPRODUCT(%s%d:%s%d,$%s$2:$%s$2)" % (q0, r, q1, r, q0, q1))
        ws.cell(row=r, column=first_q + nb + 1, value="=%s%d*$C$1" % (col(first_q + nb), r))
    ws.auto_filter.ref = "A3:%s%d" % (col(len(names)), 3 + len(items))

    for prj, name, per_kit, finish, data, rows in datas:
        ws = wb.create_sheet(name[:31])
        ws.cell(row=1, column=1, value="%s - %s %s, per board" % (name, prj, data["rev"])).font = bold
        header(ws, 2, ["line", "category", "description / purchasing spec", "design value", "package", "manufacturer",
                       "manufacturer part number", "notes", "LCSC reference", "qty per board", "designators"],
               [6, 12, 60, 16, 18, 22, 26, 30, 12, 9, 60])
        for i, g in enumerate(rows, 1):
            for j, v in enumerate([i, g["cat"], g["spec"], g["value"], g["pkg"], g["mfr"], g["mpn"], g["note"], g["lcsc"],
                                   len(g["refs"]), " ".join(g["refs"])], 1):
                ws.cell(row=2 + i, column=j, value=v).alignment = wrap if j in (3, 8, 11) else Alignment(vertical="top")
    path = os.path.join(OUT, "commander_quote_bom.xlsx")
    wb.save(path)
    print("  %s: %d boards, %d distinct parts in the kit" % (os.path.relpath(path, FAB), len(datas), len(items)))
    for prj, name, per_kit, finish, data, rows in datas:
        print("  %-24s %-6s %3d lines, %4d parts" % (prj, data["rev"], len(rows), sum(len(g["refs"]) for g in rows)))


if __name__ == "__main__":
    if "--dump" in sys.argv:
        dump()
    else:
        main()

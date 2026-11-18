#!/usr/bin/env python3
"""Writes commander_mainboard.kicad_pro: net classes, their assignment patterns and the ERC/DRC
severities that suit a generated, not-yet-routed design.

Net-class dimensions are starting points for a 6-layer 1.2 mm stack-up (JLC06121H-3313 class);
the impedance-controlled widths must be re-derived with the fabricator's calculator once the
stack-up is frozen.
"""
import json
import os

import cpmodel

OUT = os.path.join(cpmodel.ROOT, cpmodel.PRJ + ".kicad_pro")


def cls(name, clearance, width, via_d=0.45, via_drill=0.2, dp_w=None, dp_gap=None, color=None):
    c = {
        "name": name, "clearance": clearance, "track_width": width,
        "via_diameter": via_d, "via_drill": via_drill,
        "microvia_diameter": 0.3, "microvia_drill": 0.1,
        "diff_pair_width": dp_w or width, "diff_pair_gap": dp_gap or 0.1, "diff_pair_via_gap": 0.25,
        "bus_width": 12, "wire_width": 6, "line_style": 0,
        "pcb_color": color or "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 0,
    }
    return c


CLASSES = [
    cls("Default", 0.09, 0.10),
    cls("DDR", 0.09, 0.09, dp_w=0.09, dp_gap=0.10, color="rgb(0, 132, 132)"),          # 40 ohm SE / 80 ohm diff nominal
    cls("USB3_SS", 0.10, 0.10, dp_w=0.10, dp_gap=0.12, color="rgb(194, 0, 194)"),      # 90 ohm diff
    cls("USB2", 0.10, 0.11, dp_w=0.11, dp_gap=0.13, color="rgb(132, 0, 132)"),         # 90 ohm diff
    cls("HDMI", 0.10, 0.10, dp_w=0.10, dp_gap=0.11, color="rgb(0, 132, 0)"),           # 100 ohm diff
    cls("ETH_MDI", 0.15, 0.11, dp_w=0.11, dp_gap=0.15, color="rgb(0, 0, 194)"),        # 100 ohm diff
    cls("RGMII", 0.10, 0.10, color="rgb(132, 132, 0)"),                                 # 50 ohm SE
    cls("PWR", 0.10, 0.30, via_d=0.6, via_drill=0.3, color="rgb(194, 0, 0)"),
    cls("PWR_5V", 0.15, 0.40, via_d=0.7, via_drill=0.35, color="rgb(255, 80, 0)"),
    # 57 V between the nets of this class: 0.20 mm under solder mask (IPC-2221B asks 0.13 mm for coated conductors up
    # to 100 V; the TPS23754 itself has 0.20 mm between its pins).  2 mm to anything that is not POE_PRIMARY is a
    # separate rule, checked by tools/check_isolation.py.
    cls("POE_PRIMARY", 0.20, 0.40, via_d=0.8, via_drill=0.4, color="rgb(255, 0, 0)"),
]

PATTERNS = [
    ("LPDDR4_*", "DDR"),
    ("USB3_HOST1_SS*", "USB3_SS"), ("HUB3_UP_*", "USB3_SS"), ("HUB3_TX*", "USB3_SS"), ("HUB3_RX*", "USB3_SS"),
    ("SSTX*", "USB3_SS"), ("SSRX*", "USB3_SS"),
    ("USB*_DP", "USB2"), ("USB*_DM", "USB2"), ("SVC_DP", "USB2"), ("SVC_DM", "USB2"),
    ("HDMI_TX*", "HDMI"),
    ("MDI*", "ETH_MDI"), ("PHY_MDI*", "ETH_MDI"),
    ("GMAC1_*", "RGMII"), ("PHY1_RX*", "RGMII"),
    ("VDD_*", "PWR"), ("VCC_DDR", "PWR"), ("VCC0V6_DDR", "PWR"), ("VCC3V3_SYS", "PWR"), ("VCC_3V3", "PWR"),
    ("VCC3V3_HUB", "PWR"), ("VCC1V2_HUB", "PWR"), ("PMIC_SW?", "PWR"), ("RK860_SW", "PWR"), ("HUB_SW??", "PWR"),
    ("VCC_SYS", "PWR_5V"), ("VOUT_5V*", "PWR_5V"), ("VBUS_*", "PWR_5V"), ("VCC5V*", "PWR_5V"), ("SVC_VBUS", "PWR_5V"),
    ("POE_SEC", "PWR_5V"), ("POE_SNUB", "PWR"),          # secondary side of the flyback
    ("POE_A*", "POE_PRIMARY"), ("POE_C*", "POE_PRIMARY"), ("POE_D*", "POE_PRIMARY"), ("POE_F*", "POE_PRIMARY"),
    ("POE_G*", "POE_PRIMARY"), ("POE_I*", "POE_PRIMARY"), ("POE_R*", "POE_PRIMARY"), ("POE_SW", "POE_PRIMARY"),
    ("POE_V*", "POE_PRIMARY"), ("TR?_48V", "POE_PRIMARY"),
]

# ---- the keyboard: a 2-layer board, the copper of the Altium design (0.25 mm and wider) plus the ATmega32U4 circuit ----
KBD_CLASSES = [
    cls("Default", 0.15, 0.15, via_d=0.6, via_drill=0.3),
    cls("PWR", 0.15, 0.40, via_d=0.8, via_drill=0.4, color="rgb(194, 0, 0)"),
]
KBD_PATTERNS = [("VCC5", "PWR"), ("VBUS_USB", "PWR")]
# the two-layer module boards (battery, numpad, touchpad): the keyboard's rules; the battery's power path is wide
SMALL_CLASSES = KBD_CLASSES + [cls("HIPWR", 0.2, 1.0, via_d=0.8, via_drill=0.4, color="rgb(255, 120, 0)")]     # 2-3 A of the battery
SMALL_PATTERNS = KBD_PATTERNS + [("VBUS", "HIPWR"), ("VBAT", "HIPWR"), ("B_*", "HIPWR"), ("*_SW", "HIPWR"), ("VCC3V3", "PWR"),
                                 ("LDO_IN", "PWR"), ("VCC5_M*", "PWR"), ("VCC3V3_M*", "PWR"),
                                 # the front battery bar: strings and charger 0.4 mm (up to 1.2 A), charger input wide
                                 ("STR?_P", "PWR"), ("CHG?_D", "PWR"), ("VCHG*", "PWR"), ("SOLAR", "PWR"),
                                 ("CHG_IN", "HIPWR"), ("VUSB_SW", "HIPWR")]
KBD_RULES = {
    "min_clearance": 0.15, "min_copper_edge_clearance": 0.2, "min_track_width": 0.15,
    "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3, "min_via_annular_width": 0.1,      # the vias beside the chip's pins are 0.5 / 0.3
    "min_hole_clearance": 0.2, "min_hole_to_hole": 0.25, "min_silk_clearance": 0.0,
    "solder_mask_to_copper_clearance": 0.0, "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1,
}

ERC_OFF = ["footprint_link_issues", "lib_symbol_issues", "lib_symbol_mismatch", "simulation_model_issue",
           "unannotated", "similar_labels", "global_label_dangling", "endpoint_off_grid", "pin_not_driven",
           "power_pin_not_driven", "unconnected_wire_endpoint"]


def main():
    kbd = cpmodel.VARIANT == "kbd" or cpmodel.SMALL
    classes, patterns = ((SMALL_CLASSES, SMALL_PATTERNS) if cpmodel.SMALL else (KBD_CLASSES, KBD_PATTERNS)) if kbd else (CLASSES, PATTERNS)
    pro = {
        "board": {
            "design_settings": {
                "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.15, "silk_line_width": 0.12},
                "rules": {
                    "min_clearance": 0.09, "min_copper_edge_clearance": 0.25, "min_track_width": 0.09,
                    "min_via_diameter": 0.25, "min_through_hole_diameter": 0.15, "min_via_annular_width": 0.05,      # the vias in the BGA pads (0.25 / 0.15, filled and capped); everything else uses 0.45 / 0.20 or larger
                    "min_hole_clearance": 0.195,     # 0.20 nominal; a via in a 0.4 mm-pitch ball is exactly 0.200 from the next ball
                    "min_hole_to_hole": 0.25, "min_silk_clearance": 0.0,     # (were inside the comment above until 2026-11-18; same as KiCad's defaults)
                    "solder_mask_to_copper_clearance": 0.0, "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1,
                },
                "rule_severities": {
                    "lib_footprint_mismatch": "ignore", "lib_footprint_issues": "ignore",
                    "silk_overlap": "ignore", "silk_over_copper": "ignore", "silk_edge_clearance": "ignore",
                    "text_height": "ignore", "text_thickness": "ignore",
                },
            },
            "layer_presets": [], "viewports": [],
        },
        "boards": [],
        "erc": {"rule_severities": {k: "ignore" for k in ERC_OFF + (["isolated_pin_label"] if cpmodel.VARIANT == "touch" else [])}},
        "libraries": {"pinned_footprint_libs": ["commander"], "pinned_symbol_libs": ["commander"]},
        "meta": {"filename": cpmodel.PRJ + ".kicad_pro", "version": 1},
        "net_settings": {
            "classes": classes,
            "meta": {"version": 3},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [{"netclass": c, "pattern": p} for p, c in patterns],
        },
        "pcbnew": {"page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": [],
                      "drawing": {"default_text_size": 50.0, "pin_symbol_size": 25.0}},
        "sheets": [],
        "text_variables": {},
    }
    if kbd:
        pro["board"]["design_settings"]["rules"] = dict(KBD_RULES)
    if cpmodel.SMALL:
        # the module boards' feed lanes and electrode bridges use 0.5 / 0.25 vias (tools/small_board.py), JLCPCB's
        # standard 2-layer process (0.15 mm hole min; no surcharge for a 0.25 hole with a 0.45 mm or larger via)
        pro["board"]["design_settings"]["rules"]["min_through_hole_diameter"] = 0.25
    if cpmodel.VARIANT == "cpuram":
        # commander_cpu_ram (2026-11-18): its router (tools/cpu_ram_board.py) keeps 0.09 mm between all nets; 0.15 mm
        # around 5 V and 0.10 mm around the USB / HDMI / supply classes buy nothing at these voltages (the pairs keep
        # their own pair gap), so the classes here say 0.09 too
        for c in pro["net_settings"]["classes"]:
            if c["name"] not in ("POE_PRIMARY", "ETH_MDI"):
                c["clearance"] = 0.09
    if cpmodel.VARIANT == "touch":      # the electrode diamonds hang on necks and bridges, not on pads: by design
        pro["board"]["design_settings"]["rule_severities"]["isolated_copper"] = "ignore"
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")
    print("  %s.kicad_pro  (%d net classes, %d patterns)" % (cpmodel.PRJ, len(classes), len(patterns)))


if __name__ == "__main__":
    main()

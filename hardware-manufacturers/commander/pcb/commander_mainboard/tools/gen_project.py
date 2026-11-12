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

OUT = os.path.join(cpmodel.ROOT, "commander_mainboard.kicad_pro")


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
    cls("USB3_SS", 0.12, 0.10, dp_w=0.10, dp_gap=0.12, color="rgb(194, 0, 194)"),      # 90 ohm diff
    cls("USB2", 0.12, 0.11, dp_w=0.11, dp_gap=0.13, color="rgb(132, 0, 132)"),         # 90 ohm diff
    cls("HDMI", 0.12, 0.10, dp_w=0.10, dp_gap=0.11, color="rgb(0, 132, 0)"),           # 100 ohm diff
    cls("ETH_MDI", 0.15, 0.11, dp_w=0.11, dp_gap=0.15, color="rgb(0, 0, 194)"),        # 100 ohm diff
    cls("RGMII", 0.10, 0.10, color="rgb(132, 132, 0)"),                                 # 50 ohm SE
    cls("PWR", 0.15, 0.40, via_d=0.6, via_drill=0.3, color="rgb(194, 0, 0)"),
    cls("PWR_5V", 0.20, 0.80, via_d=0.7, via_drill=0.35, color="rgb(255, 80, 0)"),
    cls("POE_PRIMARY", 0.60, 0.50, via_d=0.8, via_drill=0.4, color="rgb(255, 0, 0)"),  # 57 V; 2 mm to anything not POE_PRIMARY
]

PATTERNS = [
    ("LPDDR4_*", "DDR"),
    ("USB3_HOST1_SS*", "USB3_SS"), ("HUB3_UP_*", "USB3_SS"), ("HUB3_TX*", "USB3_SS"), ("HUB3_RX*", "USB3_SS"),
    ("SSTX*", "USB3_SS"), ("SSRX*", "USB3_SS"),
    ("USB_P?_D?", "USB2"), ("USB*_D[PM]", "USB2"), ("SVC_D[PM]", "USB2"),
    ("HDMI_TX*", "HDMI"),
    ("MDI*", "ETH_MDI"), ("PHY_MDI*", "ETH_MDI"),
    ("GMAC1_*", "RGMII"), ("PHY1_RX*", "RGMII"),
    ("VDD_*", "PWR"), ("VCC_DDR", "PWR"), ("VCC0V6_DDR", "PWR"), ("VCC3V3_SYS", "PWR"), ("VCC_3V3", "PWR"),
    ("VCC3V3_HUB", "PWR"), ("VCC1V2_HUB", "PWR"), ("PMIC_SW?", "PWR"), ("RK860_SW", "PWR"), ("HUB_SW??", "PWR"),
    ("VCC_SYS", "PWR_5V"), ("VOUT_5V*", "PWR_5V"), ("VBUS_*", "PWR_5V"), ("VCC5V*", "PWR_5V"), ("SVC_VBUS", "PWR_5V"),
    ("POE_*", "POE_PRIMARY"), ("TR?_48V", "POE_PRIMARY"),
]

ERC_OFF = ["footprint_link_issues", "lib_symbol_issues", "lib_symbol_mismatch", "simulation_model_issue",
           "unannotated", "similar_labels", "global_label_dangling", "endpoint_off_grid", "pin_not_driven",
           "power_pin_not_driven", "unconnected_wire_endpoint"]


def main():
    pro = {
        "board": {
            "design_settings": {
                "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.15, "silk_line_width": 0.12},
                "rules": {
                    "min_clearance": 0.09, "min_copper_edge_clearance": 0.25, "min_track_width": 0.09,
                    "min_via_diameter": 0.4, "min_through_hole_diameter": 0.2, "min_via_annular_width": 0.1,
                    "min_hole_clearance": 0.2, "min_hole_to_hole": 0.25, "min_silk_clearance": 0.0,
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
        "erc": {"rule_severities": {k: "ignore" for k in ERC_OFF}},
        "libraries": {"pinned_footprint_libs": ["commander"], "pinned_symbol_libs": ["commander"]},
        "meta": {"filename": "commander_mainboard.kicad_pro", "version": 1},
        "net_settings": {
            "classes": CLASSES,
            "meta": {"version": 3},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [{"netclass": c, "pattern": p} for p, c in PATTERNS],
        },
        "pcbnew": {"page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": [],
                      "drawing": {"default_text_size": 50.0, "pin_symbol_size": 25.0}},
        "sheets": [],
        "text_variables": {},
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")
    print("  commander_mainboard.kicad_pro  (%d net classes, %d patterns)" % (len(CLASSES), len(PATTERNS)))


if __name__ == "__main__":
    main()

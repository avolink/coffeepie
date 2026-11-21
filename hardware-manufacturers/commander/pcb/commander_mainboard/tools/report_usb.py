#!/usr/bin/env python
"""The USB links, one line per net: are all its pads joined, how long is it, how well do the two wires of a pair match.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/report_usb.py [board.kicad_pcb]      -> build/usb_report.txt
"""
import os
import sys

import pcbnew
from pcbnew import ToMM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                                  # noqa: E402
import report_open                              # noqa: E402
from route import pair_partner                  # noqa: E402

NL = chr(10)
LINKS = [   # title, net name patterns (prefix match)
    ("RK3566 <-> USB 3 hub (U40), SuperSpeed", ("USB3_HOST1_SS", "HUB3_UP_")),
    ("RK3566 <-> USB 3 hub (U40), USB 2.0 lane", ("USB3_HOST1_D",)),
    ("RK3566 <-> USB 2 hub (U50)", ("USB2_HOST2_",)),
    ("RK3566 <-> keyboard port (J20)", ("USB2_HOST3_",)),
    ("RK3566 <-> service port (J2)", ("USB_OTG0_D", "SVC_D")),
    ("USB 2 hub <-> battery port (J40)", ("USB_AUX_",)),
    ("USB 3 hub <-> bays 1-4, USB 2.0", ("USB_P1_", "USB_P2_", "USB_P3_", "USB_P4_")),
    ("USB 2 hub <-> bays 5-9, USB 2.0", ("USB_P5_", "USB_P6_", "USB_P7_", "USB_P8_", "USB_P9_")),
    ("USB 3 hub <-> bays 1-4, SuperSpeed (hub - capacitor - mux - socket)", ("HUB3_TX", "HUB3_RX", "SSTX", "SSRX")),
]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(cpmodel.ROOT, cpmodel.PRJ + ".kicad_pcb")
    board = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    isl = report_open.islands(board)
    length, vias = {}, {}
    for t in board.GetTracks():
        n = t.GetNetname()
        if t.GetClass() == "PCB_VIA":
            vias[n] = vias.get(n, 0) + 1
        else:
            length[n] = length.get(n, 0.0) + ToMM(t.GetLength())
    info = {}
    for code, groups in isl.items():
        name = board.FindNet(code).GetNetname()
        info[name] = (max(len(g) for g in groups), sum(len(g) for g in groups), len(groups))
    names = set(info)
    lines = ["USB links of " + os.path.basename(path), "",
             "Each line: net, pads joined / pads, routed length, vias; for the P wire of a pair also the length difference to its N wire.",
             "A net is COMPLETE when all its pads are one piece of copper.", ""]
    tot = done = 0
    for title, pats in LINKS:
        if cpmodel.VARIANT == "strip":                      # the test board has no processor: these nets end on its upstream connectors
            title = title.replace("RK3566", "upstream connector (to the Radxa ZERO 3E)")
        nets = sorted(n for n in names if n.startswith(pats))
        if not nets:
            continue
        ok = sum(1 for n in nets if info[n][2] == 1)
        tot += len(nets)
        done += ok
        lines.append(f"{title}: {ok} of {len(nets)} nets complete")
        for n in nets:
            big, pads, groups = info[n]
            other = pair_partner(n, names)
            diff = "   pair difference %5.2f mm" % abs(length.get(n, 0) - length.get(other, 0)) if other and info[n][2] == 1 and info[other][2] == 1 else ""
            lines.append("  %-22s %-10s %d/%d pads  %7.1f mm  %2d vias%s" % (n, "COMPLETE" if groups == 1 else "OPEN", big, pads, length.get(n, 0.0), vias.get(n, 0), diff))
        lines.append("")
    lines.insert(2, f"{done} of {tot} USB nets are complete end to end.")
    os.makedirs(os.path.join(cpmodel.ROOT, "build"), exist_ok=True)
    open(os.path.join(cpmodel.ROOT, "build", "usb_report.txt"), "w", encoding="utf-8").write(NL.join(lines) + NL)
    print(NL.join(l for l in lines if not l.startswith("  ")))


if __name__ == "__main__":
    main()

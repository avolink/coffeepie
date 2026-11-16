#!/usr/bin/env python
"""The memory bus (RK3566 <-> LPDDR4), routed group by group, each group on a layer of its own.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/route_ddr_groups.py [passes]

Works on a COPY: build/ddr_groups.kicad_pcb (the project's board is not touched).  The method is the usual one for a
memory interface (as in Robert Feranec's DDR3 lessons, and the Rockchip / JEDEC layout guides):

  * the bus is split into groups that are matched among themselves: per channel the command / address / control
    group (with its clock pair), data byte 0 (DQ0-7, DM0, DQS0 pair) and data byte 1 (DQ8-15, DM1, DQS1 pair);
  * every group runs on ONE signal layer next to a solid ground plane, so all its members see the same
    impedance and the same propagation speed, and have the same number of layer changes (one via at the processor
    end, one at the memory end, or none);
  * the two channels sit side by side (channel A left, B right), so they share layers without crossing;
  * lengths are matched afterwards, inside each group (to its strobe / its clock): see the report.

Layer plan (6-layer board: F sig / In1 GND / In2 sig / In3 power / In4 GND / B sig):
  data byte 0   B.Cu   (the chips' own face; the bytes that land on the memory's near rows)  reference In4 GND
  command       In2.Cu                                                                        reference In1 GND
  data byte 1   In3.Cu (the power layer is opened for it inside the memory area)              reference In4 GND
"""
import collections
import json
import os
import re
import shutil
import sys

os.environ.setdefault("CP_GRID", "0.025")
import pcbnew                                   # noqa: E402
from pcbnew import ToMM                         # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                                  # noqa: E402
import route                                    # noqa: E402

NL = chr(10)
ROOT = cpmodel.ROOT
SRC = os.environ.get("CP_DDR_SRC") or os.path.join(ROOT, cpmodel.PRJ + ".kicad_pcb")
DST = os.environ.get("CP_DDR_DST") or os.path.join(ROOT, "build", "ddr_groups.kicad_pcb")
REPORT = DST.replace(".kicad_pcb", "_report.txt")
REGION = ("ddr",) + tuple(float(v) for v in (os.environ.get("CP_DDR_REGION") or "4.5,60.8,27.0,90.6").split(","))
                                                # the two packages and the gap between them (design mm)
F, MID, B = 0, 1, 2


def group_of(n):
    """('A'|'B'|'-', 'cmd'|'data0'|'data1'|other)"""
    s = n[len("LPDDR4_"):]
    ch = s[-1] if s[-2:] in ("_A", "_B") else "-"
    base = s[:-2] if ch != "-" else s
    m = re.match(r"DQ(\d+)$", base)
    if m:
        return ch, "data%d" % (int(m.group(1)) // 8)
    m = re.match(r"(DQS\d[NP]|DM\d)$", base)
    if m:
        return ch, "data" + re.search(r"\d", base).group(0)
    if base.startswith(("A", "CS", "CKE", "CLK", "ODT")):
        return ch, "cmd"
    return ch, base


# (title, kinds, layer the router's middle layer stands for, layers the group may use)
PLAN_OPEN = [           # with the top face over the memory field cleared: four signal layers, one group each
    ("data byte 0 on F.Cu (via in the ball, both ends)", ("data0",), pcbnew.In2_Cu, {F, B}),
    ("command / address / clock on In2.Cu", ("cmd",), pcbnew.In2_Cu, {MID, B}),
    ("data byte 1 on In3.Cu", ("data1",), pcbnew.In3_Cu, {MID, B}),
    ("the rest (reset, ZQ) on any layer", ("RESETN", "ZQ0", "ZQ1"), pcbnew.In2_Cu, {F, MID, B}),
]
PLAN_BLIND = [          # blind vias from B.Cu: the top face over the field stays as it is (HDI fabrication)
    ("data byte 0 on In3.Cu (blind via B-In3)", ("data0",), pcbnew.In3_Cu, {MID, B}),
    ("command / address / clock on In2.Cu (blind via B-In2)", ("cmd",), pcbnew.In2_Cu, {MID, B}),
    ("data byte 1 on In3.Cu (blind via B-In3)", ("data1",), pcbnew.In3_Cu, {MID, B}),
    ("the rest (reset, ZQ) on In2.Cu (blind via B-In2)", ("RESETN", "ZQ0", "ZQ1"), pcbnew.In2_Cu, {MID, B}),
]
PLAN_BLIND1 = [         # one layer per group, blind vias: byte 0 on the chips' own face, no via at all
    ("data byte 0 on B.Cu (no via)", ("data0",), pcbnew.In2_Cu, {B}),
    ("command / address / clock on In2.Cu (blind via B-In2)", ("cmd",), pcbnew.In2_Cu, {MID, B}),
    ("data byte 1 on In3.Cu (blind via B-In3)", ("data1",), pcbnew.In3_Cu, {MID, B}),
    ("the rest (reset, ZQ) on In2.Cu (blind via B-In2)", ("RESETN", "ZQ0", "ZQ1"), pcbnew.In2_Cu, {MID, B}),
]
PLAN_BLIND2 = [         # the far-row byte first on its own layer, then the command group; byte 0 (short) fits in after
    ("data byte 1 on In3.Cu (blind via B-In3)", ("data1",), pcbnew.In3_Cu, {MID, B}),
    ("command / address / clock on In2.Cu (blind via B-In2)", ("cmd",), pcbnew.In2_Cu, {MID, B}),
    ("data byte 0 on In3.Cu (blind via B-In3)", ("data0",), pcbnew.In3_Cu, {MID, B}),
    ("data byte 0, the rest, on In2.Cu (blind via B-In2)", ("data0",), pcbnew.In2_Cu, {MID, B}),
    ("the rest (reset, ZQ) on In2.Cu (blind via B-In2)", ("RESETN", "ZQ0", "ZQ1"), pcbnew.In2_Cu, {MID, B}),
]
PLAN_BLIND8 = [         # 8 layers (tools/to_8_layers.py): every group on an inner layer of its own, blind vias from B.Cu
    ("data byte 0 on In5.Cu (blind via B-In5)", ("data0",), pcbnew.In5_Cu, {MID, B}),
    ("data byte 1 on In3.Cu (blind via B-In3)", ("data1",), pcbnew.In3_Cu, {MID, B}),
    ("command / address / clock on In2.Cu (blind via B-In2)", ("cmd",), pcbnew.In2_Cu, {MID, B}),
    ("the rest (reset, ZQ) on In2.Cu (blind via B-In2)", ("RESETN", "ZQ0", "ZQ1"), pcbnew.In2_Cu, {MID, B}),
]
PLAN_THROUGH8 = [       # the same layers with plain through vias (no HDI): a via blocks every layer
    ("data byte 0 on In5.Cu (through vias)", ("data0",), pcbnew.In5_Cu, {MID, B}),
    ("data byte 1 on In3.Cu (through vias)", ("data1",), pcbnew.In3_Cu, {MID, B}),
    ("command / address / clock on In2.Cu (through vias)", ("cmd",), pcbnew.In2_Cu, {MID, B}),
    ("the rest (reset, ZQ) on In2.Cu (through vias)", ("RESETN", "ZQ0", "ZQ1"), pcbnew.In2_Cu, {MID, B}),
]
PLAN = [
    ("data byte 0 on B.Cu", ("data0",), pcbnew.In2_Cu, {B}),
    ("command / address / clock on In2.Cu", ("cmd",), pcbnew.In2_Cu, {MID, B}),
    ("data byte 1 on In3.Cu", ("data1",), pcbnew.In3_Cu, {MID, B}),
    ("the rest (reset, ZQ) on any layer", ("RESETN", "ZQ0", "ZQ1"), pcbnew.In2_Cu, {F, MID, B}),
]


def main():
    passes = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    shutil.copyfile(SRC, DST)
    pro = json.load(open(os.path.join(ROOT, cpmodel.PRJ + ".kicad_pro"), encoding="utf-8"))
    pro["board"]["design_settings"]["rules"].update(min_via_diameter=0.25, min_through_hole_diameter=0.15,
                                                    min_via_annular_width=0.05, min_hole_to_hole=0.25)
    json.dump(pro, open(DST.replace(".kicad_pcb", ".kicad_pro"), "w", encoding="utf-8"), indent=2)
    route.REGIONS[:] = [REGION]
    route.SKIP_CLASSES.discard("DDR")
    log = []
    mode = os.environ.get("CP_DDR_PLAN", "")
    plans = {"open": PLAN_OPEN, "blind": PLAN_BLIND, "blind1": PLAN_BLIND1, "blind2": PLAN_BLIND2,
             "blind8": PLAN_BLIND8, "through8": PLAN_THROUGH8}
    for title, kinds, middle, allowed in plans.get(mode, PLAN):
        board = pcbnew.LoadBoard(DST)
        if mode.startswith("blind"):            # a via joins the middle layer and B.Cu only
            route.VIA_L = [1, 2]
            route.VIA_KIND = (pcbnew.VIATYPE_BLIND, middle, pcbnew.B_Cu)
        members = {str(n) for n in board.GetNetsByName().keys() if str(n).startswith("LPDDR4_") and group_of(str(n))[1] in kinds}
        route.RLAYERS[1] = middle

        class Only:                             # the router's net filter, for this group only
            @staticmethod
            def fnmatch(name, pattern):
                return name in members
        route.fnmatch = Only
        r = route.Router(board)
        r.only, r.bga = "LPDDR4_*", True
        orig = r.window

        def window(reg, net, rc, box, margin, orig=orig):
            i0, j0, W, H, ok, vok = orig(reg, net, rc, box, margin)
            own = {(c[0], c[1], c[2]) for pd in reg.pads.get(net, []) for c in pd["cells"]}
            for l in range(3):
                if l in allowed:
                    continue
                keep = ok[l].copy()
                ok[l] = False
                for (cl, ci, cj) in own:        # (the net's own pads stay usable as start and goal)
                    if cl == l and i0 <= ci < i0 + W and j0 <= cj < j0 + H:
                        ok[l, cj - j0, ci - i0] = keep[cj - j0, ci - i0]
            if allowed == {B}:
                vok[...] = False                # one layer, no via at all
            return i0, j0, W, H, ok, vok
        r.window = window
        # the strobe / clock pairs first, P then N straight after it: routed among the others, the second half of a
        # pair finds its way taken
        pairs = sorted((n for n in members if re.search(r"(DQS\d|CLK)[PN]_", n)), key=lambda n: (n.replace("N_", "P_"), n[-3] == "N"))
        orig_rr = r.run_region

        def run_region(reg, prio_nets, prio_fan, orig_rr=orig_rr, pairs=pairs):
            prio_nets[:] = pairs + [n for n in prio_nets if n not in pairs]
            return orig_rr(reg, prio_nets, prio_fan)
        r.run_region = run_region
        nets_done, nets_part, fan_ok, fan_bad = r.run(passes=passes)
        pcbnew.SaveBoard(DST, board)
        log.append("%-40s %2d nets: %2d complete, %2d not" % (title, len(members), len(nets_done), len(nets_part)))
        print(log[-1], flush=True)
        del board

    # ---- what came out, group by group ----
    board = pcbnew.LoadBoard(DST)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    length, vias, layers = collections.Counter(), collections.Counter(), collections.defaultdict(set)
    for t in board.GetTracks():
        n = t.GetNetname()
        if not n.startswith("LPDDR4_"):
            continue
        if t.GetClass() == "PCB_VIA":
            vias[n] += 1
        else:
            length[n] += ToMM(t.GetLength())
            layers[n].add(board.GetLayerName(t.GetLayer()))
    open_by_net = collections.Counter()
    for n in {str(x) for x in board.GetNetsByName().keys() if str(x).startswith("LPDDR4_")}:
        ni = board.FindNet(n)
        open_by_net[n] = conn.GetUnconnectedCount(False) * 0       # placeholder, replaced below
    pads = collections.defaultdict(list)
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname().startswith("LPDDR4_"):
                pads[p.GetNetname()].append(p)
    complete = set()
    for n, ps in pads.items():
        items = {x.m_Uuid.AsString() for x in conn.GetConnectedItems(ps[0], 0)} | {ps[0].m_Uuid.AsString()}
        if all(p.m_Uuid.AsString() in items for p in ps):
            complete.add(n)
    groups = collections.defaultdict(list)
    for n in pads:
        groups[group_of(n)].append(n)
    lines = ["Memory bus, routed group by group (" + cpmodel.PRJ + ") - on a copy: " + DST, ""] + log + [""]
    lines.append("nets complete end to end (KiCad's connectivity): %d of %d" % (len(complete), len(pads)))
    lines.append("")
    lines.append("group                         complete   length of the complete nets      spread   vias  layers")
    for key in sorted(groups):
        ns = groups[key]
        ok = [n for n in ns if n in complete]
        ls = [length[n] for n in ok]
        lay = sorted({l for n in ok for l in layers[n]})
        lines.append("  %s %-8s                  %2d / %2d   %s   %s  %s" % (
            key[0], key[1], len(ok), len(ns),
            ("%6.2f .. %6.2f mm" % (min(ls), max(ls))) if ls else "        -         ",
            ("%5.2f" % (max(ls) - min(ls))) if ls else "  -  ",
            ("%d-%d" % (min(vias[n] for n in ok), max(vias[n] for n in ok))) if ok else "-",) + "  " + " ".join(lay))
    lines.append("")
    for key in sorted(groups):
        for n in sorted(groups[key]):
            lines.append("  %-22s %-9s %7.2f mm  %d via  %s%s" % (n, key[1], length[n], vias[n], " ".join(sorted(layers[n])),
                                                              "" if n in complete else "   NOT COMPLETE"))
    open(REPORT, "w", encoding="utf-8").write(NL.join(lines) + NL)
    print(NL.join(lines[:24]))


if __name__ == "__main__":
    main()

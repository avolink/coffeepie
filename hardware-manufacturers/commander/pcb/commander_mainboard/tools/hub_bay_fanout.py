"""hub_bay_fanout.py SRC DST [BOXES.json]   (KiCad's Python)

The fan-out of the hub's bay receptacles (Amphenol 12402072E512A, 24 pins in two rows on the top face, 0.75 mm
between the rows).  Row B (next to the board edge) can only leave through that gap: no track fits between the pads of
row A (0.23 mm), so the gap must not be spent on anything else.  Drawn here, the same for every bay:

  - a pin of row B whose twin of row A stands diagonally below it (GND B1-A12 / B12-A1, VBUS B4-A9 / B9-A4,
    D+ B6-A6) gets a short diagonal track to it on the top face;
  - every other connected pin of row B (D- B7, CC2 B5, the SuperSpeed pairs B2 / B3 and B10 / B11) gets a short stub
    to a 0.40 / 0.20 via in the gap, placed with the clearances to the diagonals and 0.5 mm from its neighbour's via;

and whatever copper lay between the rows before is taken out (it is what trapped the pins).  The router then joins
the vias onward (D- to A7 under the rows, the pairs to their mux).  BOXES.json: the rectangles of the fan-outs, for
pf_route.py's rip ("hold": copper in there stays fixed)."""
import json
import math
import os
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

FP = "USB_C_Receptacle_Amphenol_12402072E512A"
VIA_D, VIA_H = 0.40, 0.20
W = {"GND": 0.15}                # width of a diagonal by net; default by class below


def width(net):
    if net.startswith(("VBUS", "VCC5V")):
        return 0.20
    if net == "GND":
        return 0.15
    if net.startswith("USB") and net.endswith(("DP", "DM")):
        return 0.11
    return 0.10


def cl(net):
    return 0.15 if net.startswith(("VBUS", "VCC5V")) else 0.10


def main():
    src, dst = sys.argv[1:3]
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    board = pcbnew.LoadBoard(src)
    nets = board.GetNetsByName()
    boxes, gone, plan = [], [], []
    for fp in board.GetFootprints():
        if fp.GetFPID().GetLibItemName().wx_str() != FP:
            continue
        pad = {p.GetNumber(): p for p in fp.Pads() if p.GetNumber() and p.GetNumber()[0] in "AB" and p.GetNumber()[1:].isdigit()}

        def xy(p):
            return (ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))
        b1, b12, a1 = xy(pad["B1"]), xy(pad["B12"]), xy(pad["A1"])
        ux, uy = b12[0] - b1[0], b12[1] - b1[1]
        ul = math.hypot(ux, uy)
        ux, uy = ux / ul, uy / ul                       # along the rows, B1 -> B12
        vx, vy = -uy, ux                                # across, from row B ...
        if (a1[0] - b1[0]) * vx + (a1[1] - b1[1]) * vy < 0:
            vx, vy = -vx, -vy                           # ... towards row A

        def loc(q):
            return ((q[0] - b1[0]) * ux + (q[1] - b1[1]) * uy, (q[0] - b1[0]) * vx + (q[1] - b1[1]) * vy)

        def glob(s, t):
            return (b1[0] + s * ux + t * vx, b1[1] + s * uy + t * vy)
        size_b = max(ToMM(pad["B1"].GetSize().x), ToMM(pad["B1"].GetSize().y)) / 2
        size_a = max(ToMM(pad["A1"].GetSize().x), ToMM(pad["A1"].GetSize().y)) / 2
        ta = loc(a1)[1]                                 # row A's centre line (row B's is t = 0)
        tg = (size_b + ta - size_a) / 2                 # the middle of the gap
        gap = ta - size_a - size_b
        if not 0.6 < gap < 0.9:
            raise SystemExit("%s: %.2f mm between the rows - not the receptacle this pattern was made for" % (fp.GetReference(), gap))
        s_all = [loc(xy(p))[0] for p in pad.values()]
        s0, s1 = min(s_all) - 0.45, max(s_all) + 0.45
        t0, t1 = -size_b - 0.05, ta + size_a + 0.02
        corners = [glob(s0, t0), glob(s1, t0), glob(s1, t1), glob(s0, t1)]
        bx = [min(c[0] for c in corners), min(c[1] for c in corners), max(c[0] for c in corners), max(c[1] for c in corners)]
        boxes.append(bx)

        def inside(q):
            s, t = loc(q)
            return s0 <= s <= s1 and t0 <= t <= t1
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                if inside((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y))):
                    gone.append(t)
            elif inside((ToMM(t.GetStart().x), ToMM(t.GetStart().y))) and inside((ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))):
                gone.append(t)
        # the pattern
        diags, vias = [], []
        row_a = {n: p for n, p in pad.items() if n[0] == "A"}
        for k in range(1, 13):
            p = pad.get("B%d" % k)
            if p is None or not p.GetNetname():
                continue
            net = p.GetNetname()
            sb = loc(xy(p))[0]
            twin = next((q for q in row_a.values() if q.GetNetname() == net and abs(loc(xy(q))[0] - sb) < 0.4), None)
            if twin is not None:
                diags.append((net, sb, loc(xy(twin))[0]))
            else:
                vias.append([net, sb, sb])              # net, the pad's place, the via's place along the row

        def line_s(d, t):
            """Where a diagonal (net, s at row B, s at row A) is, along the row, at height t."""
            return d[1] + (d[2] - d[1]) * t / ta
        slope = math.hypot(1.0, 0.25 / ta)              # (distance along the row) / (distance square to a diagonal)
        lo, hi = {}, {}
        for v in vias:
            lo[v[1]], hi[v[1]] = -1e9, 1e9
            for d in diags:
                if d[0] == v[0]:
                    continue
                need = (VIA_D / 2 + width(d[0]) / 2 + max(cl(d[0]), cl(v[0])) + 0.02) * slope
                ls = line_s(d, tg)
                if ls < v[1]:
                    lo[v[1]] = max(lo[v[1]], ls + need)
                else:
                    hi[v[1]] = min(hi[v[1]], ls - need)
        vias.sort(key=lambda v: v[1])
        for v in vias:
            v[2] = min(max(v[1], lo[v[1]]), hi[v[1]])
        pitch = VIA_D + 0.10                            # two vias side by side: 0.10 mm of space, holes 0.30 apart
        for k in range(1, len(vias)):                   # push right, then back left
            if vias[k][2] - vias[k - 1][2] < pitch:
                vias[k][2] = min(vias[k - 1][2] + pitch, hi[vias[k][1]])
        for k in range(len(vias) - 2, -1, -1):
            if vias[k + 1][2] - vias[k][2] < pitch - 1e-9:
                vias[k][2] = vias[k + 1][2] - pitch
        for v in vias:
            if v[2] < lo[v[1]] - 1e-6 or abs(v[2] - v[1]) > 0.3:
                raise SystemExit("%s: no room for the via of %s (pad at %.3f, via at %.3f)" % (fp.GetReference(), v[0], v[1], v[2]))
        for net, sb, sa in diags:
            plan.append(("trk", net, glob(sb, 0.0), glob(sa, ta), width(net)))
        for net, sb, sv in vias:
            plan.append(("trk", net, glob(sb, 0.0), glob(sv, tg), width(net)))
            plan.append(("via", net, glob(sv, tg)))
        print("  %s: %d diagonals (%s), %d vias in the gap (%s)" % (fp.GetReference(), len(diags), " ".join(d[0] for d in diags),
                                                                 len(vias), " ".join("%s%+.2f" % (v[0], v[2] - v[1]) for v in vias)), flush=True)
    for kind, net, *rest in plan:
        if kind == "trk":
            a, b, w = rest
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(VECTOR2I(FromMM(a[0]), FromMM(a[1])))
            t.SetEnd(VECTOR2I(FromMM(b[0]), FromMM(b[1])))
            t.SetWidth(FromMM(w))
            t.SetLayer(pcbnew.F_Cu)
            t.SetNet(nets[net])
            board.Add(t)
        else:
            v = pcbnew.PCB_VIA(board)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetPosition(VECTOR2I(FromMM(rest[0][0]), FromMM(rest[0][1])))
            v.SetDrill(FromMM(VIA_H))
            v.SetWidth(pcbnew.F_Cu, FromMM(VIA_D))
            v.SetNet(nets[net])
            board.Add(v)
    n = len(gone)
    for t in gone:
        board.Remove(t)
    pcbnew.SaveBoard(dst, board)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        with open(stem + ".kicad_pro", "w", encoding="utf-8", newline="") as f:
            f.write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    if len(sys.argv) > 3:
        with open(sys.argv[3], "w", encoding="utf-8") as f:
            json.dump(boxes, f)
    print("  %d receptacles, %d old tracks / vias between their rows taken out, %d tracks and vias drawn -> %s" % (len(boxes), n, len(plan), dst))


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""j41_fanout.py BOARD - fan out the signal row of socket J41 (branch m2-hub), in place.

Run with KiCad's Python.  J41's back row (odd positions: every signal and some grounds) is a single row of 0.3 mm pads
at 0.5 mm pitch, its outer end 2 mm from the PoE primary zone: the only way out is inwards, under the socket body.
Each signal pad gets a straight top-face stub towards the front row and a 0.45 / 0.25 mm via at the first place,
in three staggered columns, that clears every other net's copper; the router (route.py CP_LINK=1) then joins the
via to the rest of the net on the inner layers or the bottom face.  Pads already joined by copper are left alone.
"""
import sys

import pcbnew
from pcbnew import FromMM, ToMM

VIA_D, VIA_DRILL, STUB_W, CLR = 0.45, 0.25, 0.12, 0.15


def dseg(px, py, s):
    x1, y1, x2, y2 = s[:4]
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
    u = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L))
    return ((px - x1 - u * dx) ** 2 + (py - y1 - u * dy) ** 2) ** 0.5


def seg_seg(a, b):
    """distance between two segments (sampled finely enough for this short-stub use)"""
    best = 1e9
    for k in range(0, 21):
        t = k / 20.0
        px, py = a[0] + (a[2] - a[0]) * t, a[1] + (a[3] - a[1]) * t
        best = min(best, dseg(px, py, b))
        px, py = b[0] + (b[2] - b[0]) * t, b[1] + (b[3] - b[1]) * t
        best = min(best, dseg(px, py, a))
    return best


def main():
    path = sys.argv[1]
    b = pcbnew.LoadBoard(path)
    j41 = b.FindFootprintByReference("J41")
    pads = [p for p in j41.Pads() if p.GetNumber().isdigit() and int(p.GetNumber()) % 2 == 1]
    # copper of other nets: tracks / vias as (x1, y1, x2, y2, half width, net, is_via, layers) and pads as boxes
    items = []
    for t in b.GetTracks():
        is_via = t.GetClass() == "PCB_VIA"
        w = ToMM(t.GetWidth(pcbnew.F_Cu)) if is_via else ToMM(t.GetWidth())
        items.append((ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y), w / 2,
                      t.GetNetname(), is_via, None if is_via else t.GetLayer()))
    pad_boxes = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            pad_boxes.append(((ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())),
                              p.GetNetname(), p.IsOnLayer(pcbnew.F_Cu), p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH))
    added = 0
    for col_i, p in enumerate(sorted(pads, key=lambda q: q.GetPosition().y)):
        net = p.GetNetname()
        if net == "GND" or not net:
            continue
        bb = p.GetBoundingBox()
        box = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
        if any(it[5] == net and any(box[0] <= x <= box[2] and box[1] <= yy <= box[3] for x, yy in ((it[0], it[1]), (it[2], it[3])))
               for it in items):
            continue                             # a track of its own net already ends on the pad
        x_in, y = ToMM(bb.GetRight()), ToMM(p.GetPosition().y)          # the pad's inner end (towards the front row)
        start_x = ToMM(p.GetPosition().x)
        placed = None
        cols = [66.35, 67.05, 67.75, 68.45, 69.15]
        order = cols[col_i % 3:] + cols[:col_i % 3]
        for vx in order:
            stub = (start_x, y, vx, y)
            ok = True
            for it in items:
                if it[5] == net:
                    continue
                gap_needed_via = VIA_D / 2 + it[4] + CLR
                if dseg(vx, y, it) < gap_needed_via:
                    ok = False
                    break
                if (it[6] or it[7] == pcbnew.F_Cu) and seg_seg(stub, it) < STUB_W / 2 + it[4] + CLR:
                    ok = False
                    break
            if not ok:
                continue
            for (l, t, r, bt), pn, onF, npth in pad_boxes:
                if pn == net and not npth:
                    continue
                gx = max(l - vx, vx - r, 0)
                gy = max(t - y, y - bt, 0)
                if (gx * gx + gy * gy) ** 0.5 < VIA_D / 2 + CLR + (0.2 if npth else 0):
                    ok = False
                    break
                if onF and not npth and pn != net:
                    # the stub runs on the top face along y: keep it off other top-face pads
                    sx0, sx1 = min(start_x, vx), max(start_x, vx)
                    if l - CLR - STUB_W / 2 < sx1 and r + CLR + STUB_W / 2 > sx0 and t - CLR - STUB_W / 2 < y < bt + CLR + STUB_W / 2:
                        ok = False
                        break
            if ok:
                placed = vx
                break
        if placed is None:
            print("no fan-out room for J41.%s [%s]" % (p.GetNumber(), net))
            continue
        tr = pcbnew.PCB_TRACK(b)
        tr.SetStart(p.GetPosition())
        tr.SetEnd(pcbnew.VECTOR2I(FromMM(placed), p.GetPosition().y))
        tr.SetWidth(FromMM(STUB_W))
        tr.SetLayer(pcbnew.F_Cu)
        tr.SetNet(p.GetNet())
        b.Add(tr)
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(FromMM(placed), p.GetPosition().y))
        v.SetWidth(FromMM(VIA_D))
        v.SetDrill(FromMM(VIA_DRILL))
        v.SetNet(p.GetNet())
        b.Add(v)
        items.append((start_x, y, placed, y, STUB_W / 2, net, False, pcbnew.F_Cu))
        items.append((placed, y, placed, y, VIA_D / 2, net, True, None))
        added += 1
        print("J41.%-3s %-18s via at x %.2f" % (p.GetNumber(), net, placed))
    pcbnew.SaveBoard(path, b)
    print("%d signal pads fanned out" % added)


if __name__ == "__main__":
    main()

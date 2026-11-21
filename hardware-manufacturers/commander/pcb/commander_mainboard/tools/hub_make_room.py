#!/usr/bin/env python
"""hub_make_room.py SRC DST - after tools/hub_midmount_swap.py: the parts that the deeper sink-mount receptacles (or
their board notches) now sit on are moved to the nearest free spot of their bay, and their tracks are removed for the
router to redo.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/hub_make_room.py build/hub_sink.kicad_pcb build/hub_sink_room.kicad_pcb

Free = the part's courtyard bounding box, grown by 0.25 mm, meets no other courtyard on its face, stays inside the
strip (y 81.30-103.02, 0.3 mm from the edges), off every notch, and within the bay's 32.45 mm slice.  Searched on a
spiral of 0.25 mm steps round the old position, both rotations kept as they were.
"""
import math
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

REFS = ["J%d" % i for i in range(31, 40)]
Y_TOP, Y_BOT = 81.30, 103.02
MOUTH_Y, NOTCH_HW, NOTCH_END, RELIEF = 81.045, 4.71, 7.60, 0.5
PITCH = 32.45


def bbox(f, flipped=None):
    lay = pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd
    c = f.GetCourtyard(lay)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return [ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())]


def overl(a, b, m=0.0):
    return not (a[2] + m <= b[0] or b[2] + m <= a[0] or a[3] + m <= b[1] or b[3] + m <= a[1])


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    bays = {r: ToMM(b.FindFootprintByReference(r).GetPosition().x) for r in REFS}
    notches = [(cx - NOTCH_HW - RELIEF, Y_TOP - 1, cx + NOTCH_HW + RELIEF, MOUTH_Y + NOTCH_END + 0.3) for cx in bays.values()]
    # the receptacles' shell slots and holes go through the board: no bottom-face part over them either
    holes = []
    for r in REFS:
        for p in b.FindFootprintByReference(r).Pads():
            if p.HasHole():
                bb = p.GetBoundingBox()
                holes.append([ToMM(bb.GetLeft()) - 0.3, ToMM(bb.GetTop()) - 0.3, ToMM(bb.GetRight()) + 0.3, ToMM(bb.GetBottom()) + 0.3])
    fps = list(b.GetFootprints())
    boxes = {f.GetReference(): bbox(f) for f in fps}
    face = {f.GetReference(): f.IsFlipped() for f in fps}
    victims = []
    for f in fps:
        r = f.GetReference()
        if r in REFS or r.startswith("J9"):
            continue
        bb = boxes[r]
        hit_rc = any((not face[r]) and overl(bb, boxes[j]) for j in REFS)
        hit_notch = any(overl(bb, n) for n in notches)
        hit_hole = face[r] and any(overl(bb, h) for h in holes)
        if hit_rc or hit_notch or hit_hole:
            victims.append(f)
    moved, failed = [], []
    for f in victims:
        r = f.GetReference()
        bb0 = boxes[r]
        cx0, cy0 = (bb0[0] + bb0[2]) / 2, (bb0[1] + bb0[3]) / 2
        hw, hh = (bb0[2] - bb0[0]) / 2, (bb0[3] - bb0[1]) / 2
        bay = min(bays.values(), key=lambda x: abs(x - cx0))
        lo, hi = bay - PITCH / 2, bay + PITCH / 2
        others = [boxes[o] for o in boxes if o != r and face[o] == face[r]]
        best = None
        for ring in range(1, 200):
            rr = ring * 0.25
            n = max(8, int(2 * math.pi * rr / 0.25))
            for k in range(n):
                a = 2 * math.pi * k / n
                x, y = cx0 + rr * math.cos(a), cy0 + rr * math.sin(a)
                nb = [x - hw, y - hh, x + hw, y + hh]
                if nb[1] < Y_TOP + 0.3 or nb[3] > Y_BOT - 0.3 or nb[0] < lo or nb[2] > hi:
                    continue
                if any(overl(nb, o, 0.25) for o in others) or any(overl(nb, nn) for nn in notches)                         or (face[r] and any(overl(nb, h) for h in holes)):
                    continue
                best = (x, y)
                break
            if best:
                break
        if not best:
            failed.append(r)
            continue
        dx, dy = best[0] - cx0, best[1] - cy0
        p = f.GetPosition()
        f.SetPosition(VECTOR2I(p.x + FromMM(dx), p.y + FromMM(dy)))
        boxes[r] = bbox(f)
        moved.append((r, round(dx, 2), round(dy, 2)))
    # tracks / vias touching a moved part's pads are removed (the router redoes them)
    pads = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), p.GetNetname())
            for f in victims if f.GetReference() not in failed for p in f.Pads()]
    kill = []
    for t in b.GetTracks():
        n = t.GetNetname()
        ends = [(ToMM(t.GetStart().x), ToMM(t.GetStart().y)), (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))]
        if any(n == pn and any(abs(ex - px) < 2.0 and abs(ey - py) < 2.0 for ex, ey in ends) for px, py, pn in pads):
            kill.append(t)
    for t in kill:
        b.Remove(t)
    pcbnew.SaveBoard(dst, b)
    print("moved %d parts: %s" % (len(moved), " ".join("%s(%+.2f,%+.2f)" % m for m in moved)))
    print("no room for: %s; tracks / vias removed: %d" % (" ".join(failed) or "none", len(kill)))


if __name__ == "__main__":
    main()

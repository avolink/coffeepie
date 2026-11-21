"""cap_align.py SRC DST [--radius 1.6] [--chips U1,U10] [--report FILE]   (KiCad's Python)

The 0201 capacitors and resistors on the face opposite a BGA are set down exactly over a pair of neighbouring balls
that carry their two nets (pad pitch 0.64 mm, ball pitch 0.65 mm): one through via then joins ball, capacitor pad and
the plane in between - the usual decoupling under a BGA, and the only way a supply ball inside the field gets out at
all.  Before, the parts stood wherever a free spot was: the via of a ball came up inside a foreign capacitor's pad
and the capacitor's own via came down on a foreign ball, so neither could be set (most of the open supply links of
the core).

  - parts: two-pad parts with pad pitch 0.60 .. 0.68 on the face opposite the chip, inside the ball field's outline,
    both pads on a net that has balls on that chip;
  - places: pairs of neighbouring balls (0.65 apart) with those two nets, nearest first, at most --radius away, each
    ball used once; a place is refused if a pad of a part that stays would touch the new pads;
  - a part that stays but is hit by a newly placed one is reported (seat it with seat_part.py).

Tracks are not touched here: padclear.py for the moved parts, force_vias.py --pads for the vias, then the router.
The report (JSON) lists the moved parts, their pads ([ref, pad] for force_vias.py --pads) and the ones left."""
import json
import math
import os
import re
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I


def main():
    src, dst = sys.argv[1:3]
    opt = sys.argv[3:]
    radius = float(opt[opt.index("--radius") + 1]) if "--radius" in opt else 1.6
    chips = (opt[opt.index("--chips") + 1] if "--chips" in opt else "U1,U10").split(",")
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    balls = {}                                   # chip -> [(num, net, x, y)]
    field = {}
    face = {}
    for c in chips:
        f = b.FindFootprintByReference(c)
        bl = [(p.GetNumber(), p.GetNetname(), ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in f.Pads() if p.GetNumber()]
        balls[c] = bl
        field[c] = (min(q[2] for q in bl) - 0.4, min(q[3] for q in bl) - 0.4, max(q[2] for q in bl) + 0.4, max(q[3] for q in bl) + 0.4)
        face[c] = pcbnew.B_Cu if f.GetLayer() == pcbnew.F_Cu else pcbnew.F_Cu
    parts = []                                   # (ref, chip, x, y, net1, net2, footprint)
    static = []                                  # pads of everything else on those faces: (layer, rect, net, ref)
    movable = set()
    for f in b.GetFootprints():
        ref = f.GetReference()
        pads = [p for p in f.Pads() if p.GetNumber()]
        x, y = ToMM(f.GetPosition().x), ToMM(f.GetPosition().y)
        if re.fullmatch(r"[CR]\d+", ref) and len(pads) == 2 and pads[0].GetNetname() and pads[1].GetNetname():
            pitch = math.hypot(ToMM(pads[0].GetPosition().x - pads[1].GetPosition().x), ToMM(pads[0].GetPosition().y - pads[1].GetPosition().y))
            for c in chips:
                r = field[c]
                if f.GetLayer() == face[c] and r[0] <= x <= r[2] and r[1] <= y <= r[3] and 0.60 <= pitch <= 0.68:
                    nets = {q[1] for q in balls[c]}
                    if pads[0].GetNetname() in nets and pads[1].GetNetname() in nets:
                        parts.append((ref, c, x, y, pads[0].GetNumber(), pads[0].GetNetname(), pads[1].GetNumber(), pads[1].GetNetname(), f))
                        movable.add(ref)
                    break
    for f in b.GetFootprints():
        if f.GetReference() in chips:
            continue
        for p in f.Pads():
            if not p.GetNumber() and not p.HasHole():
                continue
            bb = p.GetBoundingBox()
            rect = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
            for l in (pcbnew.F_Cu, pcbnew.B_Cu):
                if p.IsOnLayer(l):
                    static.append((l, rect, p.GetNetname(), f.GetReference()))
    # candidate places
    cands = []
    for (ref, c, x, y, k1, n1, k2, n2, f) in parts:
        for (a_num, a_net, ax, ay) in balls[c]:
            if a_net != n1 or abs(ax - x) > radius + 1 or abs(ay - y) > radius + 1:
                continue
            for (g_num, g_net, gx, gy) in balls[c]:
                if g_net != n2 or g_num == a_num:
                    continue
                d = math.hypot(gx - ax, gy - ay)
                if abs(d - 0.65) > 0.03:
                    continue
                dist = math.hypot((ax + gx) / 2 - x, (ay + gy) / 2 - y)
                if dist <= radius:
                    cands.append((dist, ref, c, a_num, g_num, ax, ay, gx, gy))
    cands.sort()
    used, placed = set(), {}                     # balls taken; ref -> (c, a, g, ax, ay, gx, gy)
    new_pads = []                                # (layer, rect, net, ref) of the placed parts
    by_ref = {p[0]: p for p in parts}
    half = 0.17                                  # half a 0201 pad (0.32 x 0.34) plus nothing: clearance is added below

    def hits(layer, rect, net, ref, pool, cl):
        for (l, r, n, rf) in pool:
            if l != layer or rf == ref:
                continue
            if rect[0] - cl < r[2] and r[0] - cl < rect[2] and rect[1] - cl < r[3] and r[1] - cl < rect[3] and n != net:
                return rf
        return None
    stat_fixed = [s for s in static if s[3] not in movable]
    for (dist, ref, c, a_num, g_num, ax, ay, gx, gy) in cands:
        if ref in placed or (c, a_num) in used or (c, g_num) in used:
            continue
        (_r, _c, _x, _y, k1, n1, k2, n2, f) = by_ref[ref]
        l = face[c]
        r1 = (ax - half, ay - half, ax + half, ay + half)
        r2 = (gx - half, gy - half, gx + half, gy + half)
        if hits(l, r1, n1, ref, stat_fixed, 0.1) or hits(l, r2, n2, ref, stat_fixed, 0.1) or \
                hits(l, r1, n1, ref, new_pads, 0.1) or hits(l, r2, n2, ref, new_pads, 0.1):
            continue
        placed[ref] = (c, a_num, g_num, ax, ay, gx, gy, dist)
        used.add((c, a_num))
        used.add((c, g_num))
        new_pads.append((l, r1, n1, ref))
        new_pads.append((l, r2, n2, ref))
    # move
    out_pads = []
    for ref, (c, a_num, g_num, ax, ay, gx, gy, dist) in sorted(placed.items()):
        (_r, _c, _x, _y, k1, n1, k2, n2, f) = by_ref[ref]
        f.SetPosition(VECTOR2I(FromMM((ax + gx) / 2), FromMM((ay + gy) / 2)))
        best = None
        for rot in (0, 90, 180, 270):
            f.SetOrientationDegrees(rot)
            p1 = [q for q in f.Pads() if q.GetNumber() == k1][0].GetPosition()
            err = math.hypot(ToMM(p1.x) - ax, ToMM(p1.y) - ay)
            if best is None or err < best[0]:
                best = (err, rot)
        f.SetOrientationDegrees(best[1])
        out_pads += [[ref, k1], [ref, k2]]
        print("%-5s %-16s %-6s -> %s %s / %s  (%.2f, %.2f) rot %3d, moved %.2f" % (ref, n1[:16], n2[:6], c, a_num, g_num,
                                                                                 (ax + gx) / 2, (ay + gy) / 2, best[1], dist))
    # the parts that stay: does a placed one sit on them now?
    left, hit_list = [], []
    for (ref, c, x, y, k1, n1, k2, n2, f) in parts:
        if ref in placed:
            continue
        left.append(ref)
        for p in f.Pads():
            if not p.GetNumber():
                continue
            bb = p.GetBoundingBox()
            rect = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
            h = hits(face[c], rect, p.GetNetname(), ref, new_pads, 0.1)
            if h:
                hit_list.append(ref)
                break
    print("%d parts set over a ball pair, %d left where they were (%s)" % (len(placed), len(left), " ".join(sorted(left))))
    if hit_list:
        print("left AND now under a placed part - seat them again:", " ".join(sorted(set(hit_list))))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    if "--report" in opt:
        json.dump({"moved": {r: [v[0], v[1], v[2], round(v[7], 2)] for r, v in placed.items()}, "pads": out_pads, "left": sorted(left),
                   "reseat": sorted(set(hit_list))}, open(opt[opt.index("--report") + 1], "w", encoding="utf-8"), indent=1)
    print("written", dst)


main()

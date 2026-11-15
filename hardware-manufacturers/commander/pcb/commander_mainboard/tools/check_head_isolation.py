#!/usr/bin/env python
"""check_head_isolation.py [BOARD] - the Ethernet head's line side against everything else, copper shape to copper
shape, on every copper layer, zones filled first.  Line side = the RJ45 pairs up to the transformers (PHY_MDI*), the
centre taps (TR?_48V), the Bob Smith node (BS) and the PoE primary (POE_* but POE_SEC / POE_SNUB): the domain that
must stand 1.5 kV off the low-voltage side and the chassis.  Parts that bridge the gap by design (the four
transformers, the 2 kV Bob Smith cap) are not judged against themselves.  Exit code 1 below 2.0 mm.
Run with KiCad's Python."""
import fnmatch
import os
import sys

import pcbnew
from pcbnew import FromMM, ToMM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                      # noqa: E402

OX, OY = 40.0, 70.0
LIMIT = 2.0
BOX = (-1.0, -21.0, 31.0, 17.0)                 # the head and the top of the PoE block (design mm)
BRIDGES = {"L15", "L23", "L25", "L27", "C60"}


def line(n):
    return bool(n) and (fnmatch.fnmatch(n, "PHY_MDI?_[PN]") or fnmatch.fnmatch(n, "TR?_48V") or n == "BS"
                        or fnmatch.fnmatch(n, "BS?") or (n.startswith("POE_") and n not in ("POE_SEC", "POE_SNUB")))


def bbox(bb):
    return (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)


def inside(r):
    return r[2] >= BOX[0] and r[0] <= BOX[2] and r[3] >= BOX[1] and r[1] <= BOX[3]


def near(a, b, m):
    return a[0] - m <= b[2] and b[0] - m <= a[2] and a[1] - m <= b[3] and b[1] - m <= a[3]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(cpmodel.ROOT, cpmodel.PRJ + ".kicad_pcb")
    b = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    cu = list(b.GetEnabledLayers().CuStack())
    items = {l: ([], []) for l in cu}           # layer -> (line items, other items): (bbox, shape, label, footprint ref)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            r = bbox(p.GetBoundingBox())
            if not inside(r) or not p.GetNetname():
                continue
            for l in cu:
                if p.IsOnLayer(l):
                    items[l][0 if line(p.GetNetname()) else 1].append(
                        (r, p.GetEffectiveShape(l), "pad %s.%s [%s]" % (fp.GetReference(), p.GetNumber(), p.GetNetname()),
                         fp.GetReference()))
    for t in b.GetTracks():
        r = bbox(t.GetBoundingBox())
        if not inside(r):
            continue
        kind = "via" if t.GetClass() == "PCB_VIA" else "track"
        for l in cu:
            if t.IsOnLayer(l):
                items[l][0 if line(t.GetNetname()) else 1].append(
                    (r, t.GetEffectiveShape(l), "%s [%s] %s" % (kind, t.GetNetname(), b.GetLayerName(l)), ""))
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for l in cu:
            if z.IsOnLayer(l) and z.HasFilledPolysForLayer(l):
                polys = z.GetFilledPolysList(l)
                if polys.OutlineCount() == 0:
                    continue
                r = bbox(polys.BBox())
                if inside(r):
                    items[l][0 if line(z.GetNetname()) else 1].append(
                        (r, polys, "zone [%s] %s" % (z.GetNetname(), b.GetLayerName(l)), ""))
    bad = []
    for l in cu:
        lines, others = items[l]
        for ra, sa, na, fa in lines:
            for rb, sb, nb, fb in others:
                if not near(ra, rb, LIMIT):
                    continue
                if fa and fa == fb and fa in BRIDGES:
                    continue
                if sa.Collide(sb, FromMM(LIMIT)):
                    lo, hi = 0.0, LIMIT                 # bisect the gap to 0.05 mm
                    while hi - lo > 0.05:
                        mid = (lo + hi) / 2
                        if sa.Collide(sb, FromMM(mid)):
                            hi = mid
                        else:
                            lo = mid
                    x = (max(ra[0], rb[0]) + min(ra[2], rb[2])) / 2
                    y = (max(ra[1], rb[1]) + min(ra[3], rb[3])) / 2
                    bad.append((lo, na, nb, x, y))
    bad.sort()
    seen = set()
    for g, na, nb, x, y in bad:
        k = (na, nb)
        if k in seen:
            continue
        seen.add(k)
        print("%.2f mm  %-40s <-> %-40s near (%.1f, %.1f)" % (g, na[:40], nb[:40], x, y))
    print("%d line-side / other pairs closer than %.1f mm in the head" % (len(seen), LIMIT))
    return 1 if seen else 0


if __name__ == "__main__":
    sys.exit(main())

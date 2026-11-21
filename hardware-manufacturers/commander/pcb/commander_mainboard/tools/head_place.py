"""head_place.py SRC DST - the isolation fix-up of the hand-placed Ethernet head (2026-11-14).

The user arranged the head by hand (PHY in the middle, chokes under it, transformers above).  This keeps that
arrangement and moves only what broke the 1.5 kV line / low-voltage gap (2 mm):
  * the four transformers in one row on the bottom face, line pins up (towards the jack), chip pins down
    (L23 was turned sideways, L27's pad touched the board edge);
  * the Bob Smith network: the four 75R in a row on the bottom face under the jack's pads, ONE common node and
    ONE 1 nF / 2 kV cap (C60) by the left shield pin (C65, C59, C16 are gone: the netlist joins BS0..BS3 into BS);
  * the 4.7 nF / 2 kV and 1 M from chassis to ground (C400, R400) by the left shield pin;
  * the centre-tap capacitors next to the transformers' chip-side centre pins;
  * the PHY's top row of straps / decoupling 0.65 mm down (2 mm from the jack's pads), L7 0.2 mm down, the row
    under the PHY 0.1 mm up and R84 / C114 under the PHY (2 mm from the PoE bridges);
  * the eight unpopulated line-side TVS (D9..D23) are deleted: their pads put line and chassis 0.38 mm apart.
Then the head's ground pours (In1, In4) with keep-outs 2 mm around the line areas of route.py (HEAD_LINE_AREA).
Design mm (board - (40, 70))."""
import os
import sys
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OX, OY = 40.0, 70.0
src, dst = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
F, B = pcbnew.F_Cu, pcbnew.B_Cu


def fp(ref):
    f = b.FindFootprintByReference(ref)
    if f is None:
        raise SystemExit("no " + ref)
    return f


def pos(f):
    p = f.GetPosition()
    return ToMM(p.x) - OX, ToMM(p.y) - OY


def put(ref, x, y, rot, side):
    f = fp(ref)
    if f.IsFlipped() != (side == "B"):
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot)
    f.SetPosition(VECTOR2I(FromMM(OX + x), FromMM(OY + y)))
    return f


def pad(ref, num):
    p = next(p_ for p_ in fp(ref).Pads() if p_.GetNumber() == num)
    q = p.GetPosition()
    return ToMM(q.x) - OX, ToMM(q.y) - OY


def place(ref, x, y, side, rots, test=lambda: True):
    for r in rots:
        put(ref, x, y, r, side)
        if test():
            return r
    raise SystemExit("no orientation fits " + ref)


log = []
# ---- deletions (done last, just before saving: KiCad's Python objects do not survive many removals)
gone = ["D9", "D10", "D11", "D12", "D20", "D21", "D22", "D23", "C65", "C59", "C16"]

# ---- R22 came over from the 3E as an 0201: its pads are 0.18 mm apart at 48 V (class clearance 0.20).  The
# schematic says 0402 (cpmodel's choice for a plain resistor), so it gets that.
old22 = fp("R22")
if "0201" in old22.GetFPIDAsString():
    lib = os.path.join(os.environ.get("KICAD10_FOOTPRINT_DIR", "C:/Program Files/KiCad/10.0/share/kicad/footprints"),
                       "Resistor_SMD.pretty")
    new22 = pcbnew.FootprintLoad(lib, "R_0402_1005Metric")
    new22.SetFPID(pcbnew.LIB_ID("Resistor_SMD", "R_0402_1005Metric"))
    new22.SetPath(old22.GetPath())
    new22.SetAttributes(old22.GetAttributes())
    new22.SetValue(old22.GetValue())
    new22.SetPosition(old22.GetPosition())
    for p_ in new22.Pads():
        p_.SetNet(next(q for q in old22.Pads() if q.GetNumber() == p_.GetNumber()).GetNet())
    old22.SetReference("R22_OLD")
    new22.SetReference("R22")
    b.Add(new22)
    gone.append("R22_OLD")
    log.append("R22: 0201 -> 0402")

# ---- one Bob Smith node
bs = b.FindNet("BS")
if bs is None:
    bs = pcbnew.NETINFO_ITEM(b, "BS")
    b.Add(bs)
for ref, num in (("R9", "2"), ("R17", "2"), ("R22", "2"), ("R23", "2"), ("C60", "1")):
    next(p_ for p_ in fp(ref).Pads() if p_.GetNumber() == num).SetNet(bs)

# ---- transformers: bottom face, row at y -1.0, line pins (3 4 5) up
for ref, x in (("L15", 15.2), ("L23", 19.3), ("L25", 23.4), ("L27", 27.5)):
    place(ref, x, -1.0, "B", (90, 270, 0, 180), lambda r=ref: pad(r, "3")[1] < pad(r, "6")[1] - 1.0)
# ---- Bob Smith: resistors under the jack (bottom face), C60 vertical by the left shield pin, chassis pad up
for ref, x in (("R9", 16.5), ("R17", 19.55), ("R22", 22.6), ("R23", 25.65)):
    place(ref, x, -7.0, "B", (0,))
place("C60", 11.7, -6.5, "B", (90, 270), lambda: pad("C60", "2")[1] < pad("C60", "1")[1])   # (2.3 mm wide pads: 0.25 from the notch)
# ---- chassis to ground, by the left shield pin (bottom face, HDMI tab)
place("C400", 8.65, -12.5, "B", (0, 180), lambda: pad("C400", "1")[0] > pad("C400", "2")[0])
place("R400", 9.5, -10.4, "B", (0, 180), lambda: pad("R400", "1")[0] > pad("R400", "2")[0])
# ---- top-face shifts
for ref in ("R76", "R77", "R88", "C113", "R100", "C106", "C107", "R97", "R98", "R99"):
    x, y = pos(fp(ref))
    put(ref, x, y + 0.65, fp(ref).GetOrientationDegrees(), "F")
x, y = pos(fp("L7"))
put("L7", x, y + 0.2, fp("L7").GetOrientationDegrees(), "F")
for ref in ("C105", "C119", "R31", "C112"):
    x, y = pos(fp(ref))
    put(ref, x, 7.85, fp(ref).GetOrientationDegrees(), "F")


# ---- small parts: nearest free spot (courtyards, board edge, existing copper, 2 mm from the line areas)
def cy_box(f):
    lay = pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd
    bb = f.GetCourtyard(lay).BBox()
    return (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)


def overlap(a, c, m=0.0):
    return a[0] < c[2] + m and c[0] < a[2] + m and a[1] < c[3] + m and c[1] < a[3] + m


import route  # noqa: E402  (the line areas)
AREAS = [a for a in route.HEAD_LINE_AREA]
LAYER_IX = {F: 0, B: 2}
EDGE = b.GetBoardEdgesBoundingBox()
outline = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outline, True)


def seg_dist(px, py, ax, ay, bx_, by_):
    dx, dy = bx_ - ax, by_ - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


tracks = [(t, ToMM(t.GetStart().x) - OX, ToMM(t.GetStart().y) - OY, ToMM(t.GetEnd().x) - OX, ToMM(t.GetEnd().y) - OY)
          for t in b.GetTracks()]


def legal(ref):
    f = fp(ref)
    box = cy_box(f)
    for g in b.GetFootprints():
        if g.GetReference() in gone or g.GetReference() == ref or g.IsFlipped() != f.IsFlipped():
            continue
        if overlap(box, cy_box(g)):
            return False
    lay = B if f.IsFlipped() else F
    for p in f.Pads():
        bb = p.GetBoundingBox()
        pb = (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)
        for cx, cyy in ((pb[0] - 0.3, pb[1] - 0.3), (pb[2] + 0.3, pb[1] - 0.3), (pb[0] - 0.3, pb[3] + 0.3),
                        (pb[2] + 0.3, pb[3] + 0.3)):          # (0.25 mm copper to edge, and a little)
            if not outline.Contains(VECTOR2I(FromMM(OX + cx), FromMM(OY + cyy))):
                return False
        for a in AREAS:
            if LAYER_IX[lay] in a[4] and overlap(pb, a[:4], 2.3):
                return False
        mx, my = (pb[0] + pb[2]) / 2, (pb[1] + pb[3]) / 2
        r = max(pb[2] - pb[0], pb[3] - pb[1]) / 2
        for t, ax, ay, bx_, by_ in tracks:
            if t.GetNetname() == p.GetNetname():
                continue
            if t.GetClass() == "PCB_VIA" or t.GetLayer() == lay:
                w = ToMM(t.GetWidth(lay) if t.GetClass() == "PCB_VIA" else t.GetWidth()) / 2
                if seg_dist(mx, my, ax, ay, bx_, by_) < r + w + 0.25:
                    return False
    return True


def find_spot(ref, x0, y0, side, rots=(0, 90), radius=3.0, step=0.1):
    cands = []
    n = int(radius / step)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            d = (i * i + j * j) ** 0.5 * step
            if d <= radius:
                cands.append((d, x0 + i * step, y0 + j * step))
    cands.sort()
    for d, x, y in cands:
        for r in rots:
            put(ref, x, y, r, side)
            if legal(ref):
                return x, y, r
    raise SystemExit("no free spot for %s near (%.1f, %.1f)" % (ref, x0, y0))


for ref, tx in (("C98", 15.2), ("C95", 19.3), ("C97", 23.4), ("C94", 27.5)):
    log.append("%s at (%.2f, %.2f) r%d" % ((ref,) + find_spot(ref, tx, 1.6, "B")))
log.append("R84 at (%.2f, %.2f) r%d" % find_spot("R84", 19.6, 4.9, "B"))
log.append("C114 at (%.2f, %.2f) r%d" % find_spot("C114", 22.5, 5.4, "B"))
x, y = pos(fp("R72"))       # (the shifted row reached R72's courtyard; C106 / C107 overlapped already)
log.append("R72 at (%.2f, %.2f) r%d" % find_spot("R72", x, y, "F", (90, 0, 270, 180)))
x, y = pos(fp("R102"))      # (its ground pad was inside the 2 mm band below the jack)
log.append("R102 at (%.2f, %.2f) r%d" % find_spot("R102", x, y + 0.3, "F", (90, 270, 0, 180)))
x, y = pos(fp("C232"))      # (out of C60's way)
log.append("C232 at (%.2f, %.2f) r%d" % find_spot("C232", x - 1.0, y, "B", (0, 90, 180, 270)))
x, y = pos(fp("C107"))
log.append("C107 at (%.2f, %.2f) r%d" % find_spot("C107", x, y, "F", (0, 90, 180, 270)))

# ---- ground vias in the PHY's exposed pad (the chokes sit under it on the bottom face: only where that face is free)
ep = next(p_ for p_ in fp("U2").Pads() if p_.GetNumber() == "41")
eb = ep.GetBoundingBox()
ex0, ey0, ex1, ey1 = ToMM(eb.GetLeft()) - OX, ToMM(eb.GetTop()) - OY, ToMM(eb.GetRight()) - OX, ToMM(eb.GetBottom()) - OY
bpads = []
for g in b.GetFootprints():
    if g.GetReference() in gone:
        continue
    for p_ in g.Pads():
        if p_.IsOnLayer(B) and p_.GetNetname() != "GND":
            bb = p_.GetBoundingBox()
            bpads.append((ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY))
nv = 0
yy = ey0 + 0.5
while yy <= ey1 - 0.5 + 1e-6:
    xx = ex0 + 0.5
    while xx <= ex1 - 0.5 + 1e-6:
        if not any(overlap((xx - 0.3, yy - 0.3, xx + 0.3, yy + 0.3), q, 0.2) for q in bpads):
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(VECTOR2I(FromMM(OX + xx), FromMM(OY + yy)))
            v.SetWidth(FromMM(0.6))
            v.SetDrill(FromMM(0.3))
            v.SetNet(b.FindNet("GND"))
            b.Add(v)
            nv += 1
        xx += 0.95
    yy += 0.95
log.append("U2: %d ground vias in the exposed pad" % nv)

# ---- the jack's two shield pins are one piece of metal
j12 = fp("J12")
if hasattr(j12, "SetDuplicatePadNumbersAreJumpers"):
    j12.SetDuplicatePadNumbersAreJumpers(True)
    log.append("J12: pads with the same number are joined (the shield)")


# ---- ground pours of the head (In1, In4), cut back 2 mm from every line area
def pts(poly):
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in poly:
        ch.Append(FromMM(OX + x), FromMM(OY + y))
    ch.SetClosed(True)
    return ch


# The ground planes (In1, In4) used to leave the whole head bare: now they cover it, and the PoE primary zone
# becomes a closed hole in them (same outline as route.py's PLANE_GND below the head).
OUTER = [(-1.0, -21.0), (31.0, -21.0), (31.0, 10.3), (326.0, 10.3), (326.0, 34.1), (31.0, 34.1), (31.0, 120.0), (-1.0, 120.0)]
HOLE = [(5.8, 8.2), (24.2, 8.2), (24.2, 32.65), (25.9, 32.65), (25.9, 38.9), (24.2, 38.9), (24.2, 46.0), (5.8, 46.0),
        (5.8, 38.9), (4.1, 38.9), (4.1, 32.65), (5.8, 32.65)]
for z in b.Zones():
    if z.GetNetname() == "GND" and z.GetZoneName() in ("GND plane L2", "GND plane L5"):
        z.Outline().RemoveAllContours()
        z.Outline().AddOutline(pts(OUTER))
        z.Outline().AddHole(pts(HOLE))
        log.append("%s: now covers the head" % z.GetZoneName())
for k, a in enumerate(AREAS):
    x0, y0, x1, y1 = a[0] - 2.0, a[1] - 2.0, a[2] + 2.0, a[3] + 2.0
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowTracks(False)
    z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.In1_Cu)
    ls.AddLayer(pcbnew.In4_Cu)
    z.SetLayerSet(ls)
    z.SetZoneName("line area %d + 2 mm (no ground pour)" % k)
    z.Outline().AddOutline(pts([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
    b.Add(z)
for f in [g for g in b.GetFootprints() if g.GetReference() in gone]:
    b.Remove(f)
log.append("deleted " + " ".join(gone))
pcbnew.SaveBoard(dst, b)
print("\n".join(log))

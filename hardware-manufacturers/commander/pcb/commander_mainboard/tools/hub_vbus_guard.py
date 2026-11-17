#!/usr/bin/env python
"""hub_vbus_guard.py SRC DST - brings the hub board up to the bays' back-feed guard (gen_usb_netlists.vbus_guard,
2026-11-16): every pad gets the net the netlist source now gives it (switch outputs, bulk capacitors, ESD supply pins
and Rp resistors moved to the supply side), the new parts (a Schottky and a TVS per bay) are added beside each bay's
power switch, and copper left on a pad that changed net is removed for the router.

    set CP_ROOT=...\\commander_hub
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/hub_vbus_guard.py commander_hub.kicad_pcb commander_hub.kicad_pcb

Free spot for a new part: its courtyard grown by 0.25 mm meets no courtyard on the top face, stays in the strip
(y 81.30-103.02, 0.3 mm from the edges), off the receptacles' notches and within its bay's 32.45 mm slice; searched
on a spiral round the bay's power switch.  Then run tools/hub_clean_copper.py and the router.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpmodel                                  # noqa: E402
import gen_pcb as GP                            # noqa: E402
import pcbnew                                   # noqa: E402
from pcbnew import FromMM, ToMM, VECTOR2I       # noqa: E402
from gen_schematic import uid                   # noqa: E402
from hub_make_room import REFS, Y_TOP, Y_BOT, MOUTH_Y, NOTCH_HW, NOTCH_END, RELIEF, PITCH, bbox, overl   # noqa: E402


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = cpmodel.load()
    b = pcbnew.LoadBoard(src)
    nets = dict(b.GetNetsByName().items())

    def net(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(b, name)
            b.Add(ni)
            nets[name] = ni
        return nets[name]

    changed, revalued, new = [], [], []
    for c in d.comps.values():
        f = b.FindFootprintByReference(c.ref)
        if f is None:
            new.append(c)
            continue
        for pin, n in c.pins.items():
            if not n:
                continue
            for pad in cpmodel.pads_for(c, pin):
                for p in f.Pads():
                    if p.GetNumber() == pad and p.GetNetname() != n:
                        bb = p.GetBoundingBox()
                        changed.append((c.ref, pad, p.GetNetname(), n,
                                        (ToMM(bb.GetLeft()) - 0.1, ToMM(bb.GetTop()) - 0.1, ToMM(bb.GetRight()) + 0.1, ToMM(bb.GetBottom()) + 0.1)))
                        p.SetNet(net(n))
        if f.GetValue() != c.value:
            f.SetValue(c.value)
            revalued.append(c.ref)
    # copper of the old net on a pad that changed net
    kill = []
    for t in b.GetTracks():
        pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
        for ref, pad, old, nn, (x0, y0, x1, y1) in changed:
            if t.GetNetname() == old and any(x0 <= ToMM(q.x) <= x1 and y0 <= ToMM(q.y) <= y1 for q in pts):
                kill.append(t)
                break
    for t in kill:
        b.Remove(t)

    # new parts beside their bay's power switch
    bays = {r: ToMM(b.FindFootprintByReference(r).GetPosition().x) for r in REFS}
    notches = [(cx - NOTCH_HW - RELIEF, Y_TOP - 1, cx + NOTCH_HW + RELIEF, MOUTH_Y + NOTCH_END + 0.3) for cx in bays.values()]
    boxes = [bbox(f) for f in b.GetFootprints() if not f.IsFlipped()]
    placed, failed = [], []
    for c in sorted(new, key=lambda c: c.ref):
        fp = GP.load_fp(c.fp)
        fp.SetReference(c.ref)
        fp.SetValue(c.value)
        fp.SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
        fp.SetSheetname("/" + c.sheet + "/")
        fp.SetSheetfile(f"sheets/{c.sheet}.kicad_sch")
        if c.desc and hasattr(fp, "SetLibDescription"):
            fp.SetLibDescription(c.desc)
        for pin, n in c.pins.items():
            for pad in cpmodel.pads_for(c, pin):
                for p in fp.Pads():
                    if p.GetNumber() == pad and n:
                        p.SetNet(net(n))
        b.Add(fp)
        # anchor: the bay's power switch (U<block>3): D641 -> U643, D751 -> U753
        sw = b.FindFootprintByReference("U%d3" % (int(c.ref[1:]) // 10))
        a = bbox(sw)
        cx0, cy0 = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
        bay = min(bays.values(), key=lambda x: abs(x - cx0))
        lo, hi = bay - PITCH / 2, bay + PITCH / 2
        best = None
        for rot in (0, 90):
            GP.set_pose(fp, 0, 0, rot, False)
            GP.centre_on(fp, 0, 0)
            c0 = bbox(fp)
            hw, hh = (c0[2] - c0[0]) / 2, (c0[3] - c0[1]) / 2
            for ring in range(0, 240):
                rr = ring * 0.25
                n_ = max(1, int(2 * math.pi * rr / 0.25)) if ring else 1
                hit = None
                for k in range(n_):
                    ang = 2 * math.pi * k / n_
                    x, y = cx0 + rr * math.cos(ang), cy0 + rr * math.sin(ang)
                    nb = [x - hw, y - hh, x + hw, y + hh]
                    if nb[1] < Y_TOP + 0.3 or nb[3] > Y_BOT - 0.3 or nb[0] < lo or nb[2] > hi:
                        continue
                    if any(overl(nb, o, 0.25) for o in boxes) or any(overl(nb, nn) for nn in notches):
                        continue
                    hit = (rr, x, y, rot)
                    break
                if hit:
                    if best is None or hit[0] < best[0]:
                        best = hit
                    break
        if best is None:
            failed.append(c.ref)
            GP.set_pose(fp, 0, 0, 0, False)
            GP.centre_on(fp, ToMM(sw.GetPosition().x) - GP.OX, 110.0 - GP.OY)
            continue
        GP.set_pose(fp, 0, 0, best[3], False)
        # (gen_pcb's centre_on works in page-offset coordinates)
        GP.centre_on(fp, best[1] - GP.OX, best[2] - GP.OY)
        boxes.append(bbox(fp))
        placed.append("%s(%.1f,%.1f)" % (c.ref, best[1], best[2]))
    pcbnew.SaveBoard(dst, b)
    print("pads moved to their new net: %d (%s)" % (len(changed), " ".join("%s.%s" % (r, p) for r, p, *_ in changed)))
    print("values changed: %s" % (" ".join(revalued) or "none"))
    print("copper removed from those pads: %d tracks / vias" % len(kill))
    print("new parts placed: %s" % " ".join(placed))
    print("NO ROOM for: %s" % (" ".join(failed) or "none"))


if __name__ == "__main__":
    main()

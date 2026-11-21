"""prune_dangling.py SRC DST DRC.json   (KiCad's Python)

Takes out the dead-end copper KiCad's DRC reports (track_dangling / via_dangling in the JSON report of SRC): a track
whose one end touches nothing is removed, or cut back to the last point where something of its net joins it; a via
that joins nothing on a second layer is removed.  KiCad's report decides WHICH items; which end is loose is worked
out here from the copper around it, and an item this script cannot explain is left alone.  The open-link count is
checked: if it would rise, nothing is written (exit code 2).

Run it in rounds (DRC, prune, DRC ...): removing a stub can leave the piece behind it dangling."""
import json
import math
import os
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I


def main():
    src, dst, rep = sys.argv[1:4]
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    d = json.load(open(rep, encoding="utf-8"))
    want = {}
    for v in d.get("violations", []):
        if v["type"] in ("track_dangling", "via_dangling"):
            for it in v["items"]:
                want[it["uuid"]] = v["type"]
    board = pcbnew.LoadBoard(src)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    before = board.GetConnectivity().GetUnconnectedCount(True)
    tracks = list(board.GetTracks())
    bynet = {}
    for t in tracks:
        bynet.setdefault(t.GetNetCode(), []).append(t)
    pads = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            pads.setdefault(p.GetNetCode(), []).append(p)
    zones = {}
    for z in board.Zones():
        if not z.GetIsRuleArea():
            zones.setdefault(z.GetNetCode(), []).append(z)

    def mm(v):
        return (ToMM(v.x), ToMM(v.y))

    def seg_dist(p, a, b):
        vx, vy = b[0] - a[0], b[1] - a[1]
        ll = vx * vx + vy * vy
        t = 0.0 if ll == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / ll))
        return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy), t

    def on_layer(o, layer):
        if o.GetClass() == "PCB_VIA":
            return o.IsOnLayer(layer)
        return o.GetLayer() == layer

    def attached(t, q, layer):
        """Does something else of the net touch point q (an end of track t) on this layer?"""
        nc = t.GetNetCode()
        pt = VECTOR2I(FromMM(q[0]), FromMM(q[1]))
        out = set()
        for p in pads.get(nc, []):
            if p.IsOnLayer(layer) and p.HitTest(pt):
                out.add(p.m_Uuid.AsString())
        for o in bynet.get(nc, []):
            if o is t or o.m_Uuid == t.m_Uuid or not on_layer(o, layer) or o.m_Uuid.AsString() in gone:
                continue
            if o.GetClass() == "PCB_VIA":
                if math.hypot(q[0] - ToMM(o.GetPosition().x), q[1] - ToMM(o.GetPosition().y)) <= via_d(o) / 2:
                    out.add(o.m_Uuid.AsString())
            elif o.GetClass() == "PCB_TRACK":
                dd, _ = seg_dist(q, mm(o.GetStart()), mm(o.GetEnd()))
                if dd <= ToMM(o.GetWidth()) / 2 + 0.001:
                    out.add(o.m_Uuid.AsString())
            else:                               # an arc: its ends
                if min(math.hypot(q[0] - e[0], q[1] - e[1]) for e in (mm(o.GetStart()), mm(o.GetEnd()))) <= ToMM(o.GetWidth()) / 2:
                    out.add(o.m_Uuid.AsString())
        for z in zones.get(nc, []):
            if z.IsOnLayer(layer) and z.HitTestFilledArea(layer, pt):
                out.add("zone")
        return out

    def via_d(v):
        try:
            return ToMM(v.GetWidth(pcbnew.F_Cu))
        except TypeError:
            return ToMM(v.GetWidth())

    def joints(t, a, b):
        """Parameters (0 at a .. 1 at b) where other copper of the net meets the inside of track t."""
        out = []
        layer = t.GetLayer()
        w = ToMM(t.GetWidth())
        pts = []
        for o in bynet.get(t.GetNetCode(), []):
            if o.m_Uuid == t.m_Uuid or o.m_Uuid.AsString() in gone or not on_layer(o, layer):
                continue
            if o.GetClass() == "PCB_VIA":
                pts.append(mm(o.GetPosition()))
            else:
                pts += [mm(o.GetStart()), mm(o.GetEnd())]
        for p in pads.get(t.GetNetCode(), []):
            if p.IsOnLayer(layer):
                pts.append(mm(p.GetPosition()))
        for q in pts:
            dd, tt = seg_dist(q, a, b)
            if dd <= w / 2 + 0.001:
                out.append(tt)
        return out

    # PRUNE_KEEP_REFS=J90,J41: the lead-out stubs of these parts' pads stay (card-edge fingers, a socket's fan-out)
    keep_refs = set(filter(None, os.environ.get("PRUNE_KEEP_REFS", "").split(",")))
    keep_pads = [p for fp in board.GetFootprints() if fp.GetReference() in keep_refs for p in fp.Pads()]

    def kept(t):
        if not keep_pads or t.GetClass() == "PCB_VIA":
            return False
        for e in (t.GetStart(), t.GetEnd()):
            for p in keep_pads:
                if p.GetNetCode() == t.GetNetCode() and p.IsOnLayer(t.GetLayer()) and p.HitTest(e):
                    return True
        return False

    debug = bool(os.environ.get("PRUNE_DEBUG"))
    why = {}

    def note(t, reason):
        if debug:
            why.setdefault(reason, []).append("%s %s (%.2f, %.2f)-(%.2f, %.2f)" % (t.GetNetname(), board.GetLayerName(t.GetLayer()),
                                                                                    ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)))

    gone = set()
    removed, trimmed, skipped = [], 0, 0
    for t in tracks:
        u = t.m_Uuid.AsString()
        kind = want.get(u)
        if not kind:
            continue
        if kept(t):
            skipped += 1
            note(t, "kept (lead-out)")
            continue
        if t.GetClass() == "PCB_VIA":
            if kind == "via_dangling":
                removed.append(t)
                gone.add(u)
            continue
        if t.GetClass() != "PCB_TRACK":
            skipped += 1
            continue
        a, b = mm(t.GetStart()), mm(t.GetEnd())
        layer = t.GetLayer()
        fa, fb = attached(t, a, layer), attached(t, b, layer)
        if fa and fb:
            # a speck of track whose two ends touch one and the same other item (KiCad's own test) joins nothing: out
            both = fa | fb
            if len(both) == 1 and "zone" not in both:
                removed.append(t)
                gone.add(u)
                continue
            skipped += 1                        # KiCad says dangling, the copper says joined at both ends: leave it
            note(t, "both ends joined")
            continue
        if not fa and not fb:
            js = joints(t, a, b)
            if not js:
                removed.append(t)
                gone.add(u)
            else:
                skipped += 1
                note(t, "no end joined, joints inside")
            continue
        if fb:                                # make a the joined end, b the loose one
            a, b = b, a
        js = [x if not fb else 1.0 - x for x in joints(t, mm(t.GetStart()), mm(t.GetEnd()))]
        far = max(js) if js else 0.0
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if far * length < 0.02:
            removed.append(t)
            gone.add(u)
        elif far < 1.0 - 1e-6:
            c = (a[0] + (b[0] - a[0]) * far, a[1] + (b[1] - a[1]) * far)
            if fb:
                t.SetStart(VECTOR2I(FromMM(c[0]), FromMM(c[1])))
            else:
                t.SetEnd(VECTOR2I(FromMM(c[0]), FromMM(c[1])))
            trimmed += 1
        else:
            skipped += 1
            note(t, "joint at the loose end")
    for k, v in why.items():
        print("  prune: %s: %d, e.g. %s" % (k, len(v), " | ".join(v[:6])), flush=True)
    n = len(removed)
    for t in removed:
        board.Remove(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    after = board.GetConnectivity().GetUnconnectedCount(True)
    print("  prune: %d reported, %d removed, %d cut back, %d left alone; open links %d -> %d"
          % (len(want), n, trimmed, skipped, before, after), flush=True)
    if after > before:
        print("  prune: the open-link count rose - nothing written", flush=True)
        sys.exit(2)
    pcbnew.SaveBoard(dst, board)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        with open(stem + ".kicad_pro", "w", encoding="utf-8", newline="") as f:
            f.write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    sys.exit(0 if (n or trimmed) else 3)        # 3: nothing left to do


if __name__ == "__main__":
    main()

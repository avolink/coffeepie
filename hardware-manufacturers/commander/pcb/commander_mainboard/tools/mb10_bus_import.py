"""mb10_bus_import.py VARIANT MB_SRC DST [--nets REGEX] [--report FILE]   (KiCad's Python)

The memory bus of a commander_cpu_ram board (routed by cpu_ram_board.py: 5 signal layers, through vias, vias in the
balls) carried over to the 10-layer mainboard.

The cpu_ram board has the processor on its top face, the mainboard on its bottom face: the cpu_ram board mirrored in y
about the processor's centre lands ball for ball on the mainboard's processor (checked here), with the layers in the
opposite order (F <-> B, In1 <-> In8, In2 <-> In7, In3 <-> In6, In4 <-> In5).

  1. the mainboard's memory U10 goes where the variant's memory lands; the decoupling parts under it (other face,
     only memory / DDR supply nets) move with it; if it moved, every track and via inside the old and the new outline
     is taken out (they belonged to the old place);
  2. the mainboard's own copper of the bus nets is taken out; the variant's is put in;
  3. parts whose pads the new copper runs into (a via through a capacitor of another net) are set down again at the
     nearest spot that is free of other parts, of every via and of the bus tracks (their old copper stays behind as
     stubs for the prune);
  4. tracks / vias of other nets that the new copper touches are left for KiCad's DRC + drc_remove.py --keep <bus>.
"""
import json
import math
import os
import re
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

OK_GROUP = re.compile(r"LPDDR4_.*|DDR_.*|VCC_DDR|VCC0V6_DDR|VCC1V8_DDR|GND")


def main():
    var_path, src, dst = sys.argv[1:4]
    opt = sys.argv[4:]
    bus = re.compile(opt[opt.index("--nets") + 1] if "--nets" in opt else r"LPDDR4_.*|DDR_.*")
    a = pcbnew.LoadBoard(var_path)
    m = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    assert m.GetCopperLayerCount() == 10 and a.GetCopperLayerCount() == 10
    ua, um = a.FindFootprintByReference("U1"), m.FindFootprintByReference("U1")
    ax, ay, mx, my = ua.GetPosition().x, ua.GetPosition().y, um.GetPosition().x, um.GetPosition().y

    def T(p):
        return VECTOR2I(mx + (p.x - ax), my - (p.y - ay))
    inner = [pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.In5_Cu, pcbnew.In6_Cu, pcbnew.In7_Cu, pcbnew.In8_Cu]
    LM = {pcbnew.F_Cu: pcbnew.B_Cu, pcbnew.B_Cu: pcbnew.F_Cu}
    for i, l in enumerate(inner):
        LM[l] = inner[7 - i]
    # the processors must coincide
    pm = {p.GetNumber(): p for p in um.Pads() if p.GetNumber()}
    worst = 0
    for p in ua.Pads():
        if p.GetNumber():
            q = T(p.GetPosition())
            worst = max(worst, math.hypot(q.x - pm[p.GetNumber()].GetPosition().x, q.y - pm[p.GetNumber()].GetPosition().y))
            if bus.fullmatch(p.GetNetname()):
                assert pm[p.GetNumber()].GetNetname() == p.GetNetname(), "U1.%s: %s / %s" % (p.GetNumber(), p.GetNetname(), pm[p.GetNumber()].GetNetname())
    print("processor: worst ball offset %.4f mm" % ToMM(worst))
    assert ToMM(worst) < 0.005

    # the variant's bus copper as plain numbers, and the mainboard's vias - read before anything is taken out of the
    # mainboard (KiCad's Python objects do not survive removals)
    var_items = []
    for t in a.GetTracks():
        n = t.GetNetname()
        if not bus.fullmatch(n):
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            q = T(t.GetPosition())
            var_items.append(("via", n, q.x, q.y, t.GetWidth(pcbnew.F_Cu), t.GetDrillValue()))
        elif t.Type() == pcbnew.PCB_ARC_T:
            raise SystemExit("an arc in the bus copper - not handled")
        else:
            q0, q1 = T(t.GetStart()), T(t.GetEnd())
            var_items.append(("seg", n, q0.x, q0.y, q1.x, q1.y, LM[t.GetLayer()], t.GetWidth()))
    doomed = []

    # ---- 1: the memory
    va, vm = a.FindFootprintByReference("U10"), m.FindFootprintByReference("U10")
    old = vm.GetPosition()
    old_box = vm.GetCourtyard(vm.GetLayer()).BBox()
    new = T(va.GetPosition())
    dx, dy = new.x - old.x, new.y - old.y
    print("memory: (%.3f, %.3f) -> (%.3f, %.3f), moved by (%.3f, %.3f)" % (ToMM(old.x), ToMM(old.y), ToMM(new.x), ToMM(new.y), ToMM(dx), ToMM(dy)))
    under = []
    if dx or dy:
        other = pcbnew.F_Cu if vm.GetLayer() == pcbnew.B_Cu else pcbnew.B_Cu
        for f in m.GetFootprints():
            if f.GetLayer() != other or f.GetReference() in ("U1", "U10"):
                continue
            nets = {p.GetNetname() for p in f.Pads() if p.GetNumber()}
            if nets and all(OK_GROUP.fullmatch(n) for n in nets) and old_box.Contains(f.GetPosition()):
                under.append(f)
        vm.SetPosition(new)
        for f in under:
            f.SetPosition(VECTOR2I(f.GetPosition().x + dx, f.GetPosition().y + dy))
    pmem = {p.GetNumber(): p for p in vm.Pads() if p.GetNumber()}
    worst = 0
    for p in va.Pads():
        if p.GetNumber():
            q = T(p.GetPosition())
            worst = max(worst, math.hypot(q.x - pmem[p.GetNumber()].GetPosition().x, q.y - pmem[p.GetNumber()].GetPosition().y))
            assert pmem[p.GetNumber()].GetNetname() == p.GetNetname()
    print("memory: worst ball offset after the move %.4f mm; %d parts under it moved along" % (ToMM(worst), len(under)))
    assert ToMM(worst) < 0.005
    gone = 0
    if abs(ToMM(dx)) > 0.03 or abs(ToMM(dy)) > 0.03:
        nb = vm.GetCourtyard(vm.GetLayer()).BBox()
        boxes = [old_box, nb]
        for t in list(m.GetTracks()):
            pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
            if any(bx.Contains(q) for bx in boxes for q in pts):
                doomed.append(t)
                gone += 1
        print("memory moved: %d tracks / vias inside its old and new outline taken out" % gone)

    # ---- 2: the bus copper
    out = 0
    doomed_ids = {id(t) for t in doomed}
    all_vias = []
    for t in list(m.GetTracks()):
        if bus.fullmatch(t.GetNetname()):
            if id(t) not in doomed_ids:
                doomed.append(t)
            out += 1
        elif t.Type() == pcbnew.PCB_VIA_T and id(t) not in doomed_ids:
            all_vias.append((t.GetPosition().x, t.GetPosition().y, t.GetWidth(pcbnew.F_Cu) // 2, t.GetNetname()))
    put_t = put_v = 0
    new_vias, new_segs = [], []         # (x, y, r, net) / (layer, ax, ay, bx, by, halfwidth, net)
    for it in var_items:
        net = m.FindNet(it[1])
        assert net is not None, it[1]
        if it[0] == "via":
            v = pcbnew.PCB_VIA(m)
            v.SetPosition(VECTOR2I(it[2], it[3]))
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetWidth(pcbnew.F_Cu, it[4])
            v.SetDrill(it[5])
            v.SetNet(net)
            m.Add(v)
            put_v += 1
            new_vias.append((it[2], it[3], it[4] // 2, it[1]))
            all_vias.append((it[2], it[3], it[4] // 2, it[1]))
        else:
            sg = pcbnew.PCB_TRACK(m)
            sg.SetStart(VECTOR2I(it[2], it[3]))
            sg.SetEnd(VECTOR2I(it[4], it[5]))
            sg.SetLayer(it[6])
            sg.SetWidth(it[7])
            sg.SetNet(net)
            m.Add(sg)
            put_t += 1
            new_segs.append((it[6], it[2], it[3], it[4], it[5], it[7] // 2, it[1]))
    print("bus: %d of the mainboard's tracks / vias out, %d tracks + %d vias in" % (out, put_t, put_v))

    # ---- 3: parts the new copper runs into
    CL = FromMM(0.1)
    CLV = FromMM(0.17)                          # a via: its hole keeps 0.2 mm from other copper

    def seg_box_hit(seg, bx, grow):
        l, x0, y0, x1, y1, hw, n = seg
        g = grow + hw
        left, top, right, bottom = bx.GetLeft() - g, bx.GetTop() - g, bx.GetRight() + g, bx.GetBottom() + g
        if max(x0, x1) < left or min(x0, x1) > right or max(y0, y1) < top or min(y0, y1) > bottom:
            return False
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / FromMM(0.05)))
        for k in range(steps + 1):
            x, y = x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps
            if left <= x <= right and top <= y <= bottom:
                return True
        return False

    def pad_hits(p):
        """does the new copper touch this pad (another net)"""
        n = p.GetNetname()
        bx = p.GetBoundingBox()
        for (x, y, r, vn) in new_vias:
            if vn != n and bx.GetLeft() - r - CLV <= x <= bx.GetRight() + r + CLV and bx.GetTop() - r - CLV <= y <= bx.GetBottom() + r + CLV:
                return True
        for seg in new_segs:
            if seg[6] != n and p.IsOnLayer(seg[0]) and seg_box_hit(seg, bx, CL):
                return True
        return False
    hit = []
    for f in m.GetFootprints():
        if f.GetReference() in ("U1", "U10"):
            continue
        if any(pad_hits(p) for p in f.Pads() if p.GetNumber() and (p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.B_Cu))):
            hit.append(f)
    print("parts in the way of the bus copper:", len(hit), " ".join(sorted(f.GetReference() for f in hit)))
    fixed = [f for f in hit if len([p for p in f.Pads() if p.GetNumber()]) > 2 or any(p.HasHole() for p in f.Pads())]
    if fixed:
        print("  NOT moved (not a two-pad part):", " ".join(f.GetReference() for f in fixed))
    movable = [f for f in hit if f not in fixed]
    bb = m.GetBoardEdgesBoundingBox()

    def court(f):
        c = f.GetCourtyard(f.GetLayer())
        return c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    courts = {f.GetReference(): (f.GetLayer(), court(f), any(p.HasHole() for p in f.Pads())) for f in m.GetFootprints()}

    near = {"vias": all_vias, "segs": new_segs}

    def free(f):
        cb = court(f)
        if cb.GetLeft() < bb.GetLeft() + FromMM(0.4) or cb.GetRight() > bb.GetRight() - FromMM(0.4) or \
                cb.GetTop() < bb.GetTop() + FromMM(0.4) or cb.GetBottom() > bb.GetBottom() - FromMM(0.4):
            return False
        for r, (lay, ob, th) in courts.items():
            if r == f.GetReference() or (lay != f.GetLayer() and not th):
                continue
            if cb.GetLeft() < ob.GetRight() and ob.GetLeft() < cb.GetRight() and cb.GetTop() < ob.GetBottom() and ob.GetTop() < cb.GetBottom():
                return False
        for p in f.Pads():
            if not p.GetNumber():
                continue
            n = p.GetNetname()
            bx = p.GetBoundingBox()
            for (x, y, r, vn) in near["vias"]:
                if vn != n and bx.GetLeft() - r - CLV <= x <= bx.GetRight() + r + CLV and bx.GetTop() - r - CLV <= y <= bx.GetBottom() + r + CLV:
                    return False
            for seg in near["segs"]:
                if seg[6] != n and p.IsOnLayer(seg[0]) and seg_box_hit(seg, bx, CL):
                    return False
        return True
    moved, stuck = [], []
    def search(f, o, rot0, rings):
        R = FromMM(rings * 0.1 + 3.0)
        near["vias"] = [v for v in all_vias if abs(v[0] - o.x) < R and abs(v[1] - o.y) < R]
        near["segs"] = [g for g in new_segs if min(abs(g[1] - o.x), abs(g[3] - o.x)) < R and min(abs(g[2] - o.y), abs(g[4] - o.y)) < R]
        for ring in range(1, rings + 1):        # rings of 0.1 mm
            r = ring * 0.1
            n = max(8, int(2 * math.pi * r / 0.1))
            for k in range(n):
                ang = 2 * math.pi * k / n
                x, y = o.x + FromMM(r * math.cos(ang)), o.y + FromMM(r * math.sin(ang))
                for rot in (rot0, rot0 + 90, rot0 + 45, rot0 + 135):
                    f.SetPosition(VECTOR2I(int(x), int(y)))
                    f.SetOrientationDegrees(rot)
                    if free(f):
                        return (x, y, rot)
        return None
    for f in sorted(movable, key=lambda f_: f_.GetReference()):
        o = f.GetPosition()
        rot0 = f.GetOrientationDegrees()
        best = search(f, o, rot0, 80)
        note = ""
        if best is None:                        # nothing within 8 mm on its face: the other face, out to 14 mm
            f.SetPosition(o)
            f.Flip(o, pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            best = search(f, o, f.GetOrientationDegrees(), 140)
            note = "(other face)"
            if best is None:
                f.Flip(o, pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if best:
            courts[f.GetReference()] = (f.GetLayer(), court(f), False)
            moved.append("%s %.2f%s" % (f.GetReference(), math.hypot(ToMM(best[0] - o.x), ToMM(best[1] - o.y)), note))
        else:
            f.SetPosition(o)
            f.SetOrientationDegrees(rot0)
            stuck.append(f.GetReference())
    print("set down again (ref, distance mm):", " ".join(moved))
    if stuck:
        print("NO free spot within 8 mm for:", " ".join(stuck))
    if "--report" in opt:
        json.dump({"moved": moved, "stuck": stuck, "fixed": [f.GetReference() for f in fixed], "under": [f.GetReference() for f in under],
                   "memory_shift": [ToMM(dx), ToMM(dy)]}, open(opt[opt.index("--report") + 1], "w", encoding="utf-8"), indent=1)
    for t in doomed:                            # last: nothing is read from the board after this
        m.Remove(t)
    pcbnew.ZONE_FILLER(m).Fill(m.Zones())
    pcbnew.SaveBoard(dst, m)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    print("written", dst)


main()

#!/usr/bin/env python
"""Keyboard board = the Altium board (Teclado_V2), converted to KiCad, with the Arduino Micro module replaced by an
ATmega32U4 circuit soldered on the board.  Run with the Python that comes with KiCad (CP_ROOT = commander_keyboard):

    kbd_board.py                 all stages
    kbd_board.py --stage X       one of: import, prepare, route, repair, ground

  import    kicad-cli converts ../../Teclado_V2/Teclado_V2.PcbDoc                     -> src/altium_import.kicad_pcb
  prepare   nets renamed to the names of the netlist source, values and schematic links set, the new parts of
            sheet kbd_mcu added and placed on the bottom face, the module U1 removed   -> build/kbd_prepared.kicad_pcb
  route     the new parts are connected (tools/route.py, two layers), ground vias, zones refilled
  repair    for a net that is still open: the router's tracks round its stuck end are taken out, it is routed first,
            then the ones taken out (a round that makes things worse is undone)
  ground    every ground pad that the pours no longer reach gets a track or via to them
                                                                                      -> commander_keyboard.kicad_pcb

Nothing of the Altium layout is moved or re-routed: switches, resistors, their tracks and the copper zones stay
exactly where the working prototype has them.  Only the copper that the new parts need is added.
"""
import json
import math
import os
import subprocess
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                                  # noqa: E402

ROOT, PRJ = cpmodel.ROOT, cpmodel.PRJ
NL = chr(10)
ALTIUM = os.path.normpath(os.path.join(ROOT, "..", "..", "Teclado_V2", "Teclado_V2.PcbDoc"))
IMPORTED = os.path.join(ROOT, "src", "altium_import.kicad_pcb")        # (kept with the sources: the project builds without Altium files)
PREPARED = os.path.join(ROOT, "build", "kbd_prepared.kicad_pcb")
FINAL = os.path.join(ROOT, PRJ + ".kicad_pcb")
KBIN = os.environ.get("KICAD_BIN", r"C:/Program Files/KiCad/10.0/bin")
THICKNESS = 1.6             # mm - ASSUMED: the Altium file carries only its default stack-up (see the README)

# ---- where the new parts go (board mm, as in the Altium file; all on the BOTTOM face, where the module was) ----
MODULE = (106.0, 136.0, 152.5, 154.2)       # the footprint of the Arduino Micro module
USB_Y = 160.0                               # USB-C receptacle on the left edge, in the bay beside the codec column
USB_OVERHANG = 0.9                          # how far its front stands out over the board edge
# The chip sits in the right half of the module's area, the only place where the TOP layer carries no matrix tracks
# (x 134..146.4, y 142..157), so its pins can change layer right beside it.  It is turned so that
#   north: A0..A5          (their lines end at the old upper pin row, to the north-west)
#   west : D4..D13         (lower pin row, to the west)
#   south: D0, D2, D3, crystal, reset
#   east : USB, SPI        (the SPI lines end at the east end of both rows; the ISP pads sit east of the chip)
# FIXED: reference -> (x, y, rotation): exactly there (planned by hand; the prepare stage reports any overlap).
FIXED = {
    "U201": (140.7, 147.4, 180),
    "Y201": (140.95, 154.55, 0), "C208": (138.0, 154.4, 270), "C209": (145.2, 152.9, 0),
    "C204": (149.0, 142.8, 0), "R204": (149.0, 144.4, 180), "R203": (149.0, 146.0, 180), "C201": (149.0, 147.6, 0),
    "J202": (154.0, 147.4, 0), "R206": (149.2, 150.6, 0), "SW201": (152.8, 153.3, 0),
    "C203": (136.3, 142.4, 180), "C205": (133.1, 142.4, 180), "R207": (133.4, 144.3, 180),
    "C206": (142.4, 139.2, 180),
}
# Old copper that is removed besides the module's own stubs: (net, box) - the tracks with both ends in the box and the
# vias in it.  Here: the top-layer piece that brought +5 V from the module's supply pin to R156; R156 is fed from the
# chip's supply pin next to it instead.
REMOVE_BOX = [("VCC5", (136.9, 141.4, 140.0, 143.7))]
# Old copper that is cut back: (net, layer, one end, other end, new position of the FIRST end).  The +5 V feed ran from the
# module's supply pin eastwards along what is now the chip's north side; from x = 151.5 on it stays.
TRIM = [("VCC5", "B", (139.85, 141.54), (161.07, 141.54), (151.5, 141.54))]
# TARGETS: reference -> (target x, target y): the part is put on the free spot nearest to its target
RING = 0.0
ROT = {"U202": 180}                         # (its supply pad towards the receptacle, its ground pad towards the open board)
TARGETS = {
    "U202": (11.4, 160.0), "C210": (8.6, 154.6), "F201": (12.2, 155.0), "R201": (11.0, 164.6), "R202": (13.2, 164.6),
}
# the chip's pins: a straight piece of track outwards and a via at its end, in two staggered rows (measured from the
# chip's centre), on the three sides where the top layer is free.  Not on these nets (they stay on the bottom layer):
FAN_SHORT, FAN_LONG = 4.45, 5.15
FAN_NO_VIA = ("XTAL1", "XTAL2")
EARLY_PINS = ("24",)                        # chip pins linked right after the escape, before every other net (see route_pass)
KBD_W, KBD_CL = 0.15, 0.15                  # new copper: tracks and gaps (0.127 gains nothing on the router's 0.05 mm grid)
USB_LOOP = 1.1                              # mm from the middle of the receptacle's data pads to the loops that join them
WISH_K = 4                                  # cells either side of a net's trial route that others pay to enter (0.2 mm)
FAN_STRIP = 2.5                             # mm in front of each of these pieces where other nets pay extra to pass
ROUTE_BOX = (-2.0, 126.0, 162.0, 173.5)     # the window the router works in (board mm)


def kpath(name):
    return os.path.join(KBIN, name + (".exe" if os.name == "nt" else ""))


# --------------------------------------------------------------------------
def stage_import():
    os.makedirs(os.path.dirname(IMPORTED), exist_ok=True)
    if not os.path.exists(ALTIUM):
        raise SystemExit("Altium source not found: " + ALTIUM)
    r = subprocess.run([kpath("kicad-cli"), "pcb", "import", "--format", "altium", "-o", IMPORTED, ALTIUM], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(IMPORTED):
        raise SystemExit("kicad-cli pcb import failed: " + (r.stdout + r.stderr)[-600:])
    print("imported  %s" % os.path.relpath(ALTIUM, ROOT))


# --------------------------------------------------------------------------
def bottom_obstacles(board, box, res, skip_ref, skip_tracks=()):
    """Occupancy of the bottom face inside 'box' (True = taken): copper of the bottom layer, every hole and cut-out,
    and a margin along the board edge.  Ground pours are not obstacles (they close in again round a new part)."""
    import numpy as np
    x0, y0, x1, y1 = box
    nx, ny = int(round((x1 - x0) / res)) + 1, int(round((y1 - y0) / res)) + 1
    occ = np.zeros((ny, nx), bool)

    def mark(ax, ay, bx, by, m=0.0):
        ia, ib = int(math.floor((min(ax, bx) - m - x0) / res)), int(math.ceil((max(ax, bx) + m - x0) / res))
        ja, jb = int(math.floor((min(ay, by) - m - y0) / res)), int(math.ceil((max(ay, by) + m - y0) / res))
        if ib < 0 or jb < 0 or ia >= nx or ja >= ny:
            return
        occ[max(ja, 0):jb + 1, max(ia, 0):ib + 1] = True
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps, True)
    o = ps.Outline(0)
    pts = [(ToMM(o.CPoint(i).x), ToMM(o.CPoint(i).y)) for i in range(o.PointCount())]
    for j in range(ny):                             # outside the outline, and 0.5 mm inside it
        y = y0 + j * res + 1e-6
        xs = sorted(ax + (y - ay) * (bx - ax) / (by - ay) for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]) if (ay > y) != (by > y))
        inside = np.zeros(nx, bool)
        xr = x0 + np.arange(nx) * res
        for a, b in zip(xs[0::2], xs[1::2]):
            inside |= (xr >= a + 0.5) & (xr <= b - 0.5)
        occ[j, ~inside] = True
    for h in range(ps.HoleCount(0)):                # cut-outs (switch slots)
        bb = ps.Hole(0, h).BBox()
        mark(ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()), 0.5)
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            r = max(ToMM(t.GetWidth(pcbnew.F_Cu)), ToMM(t.GetDrillValue())) / 2
            x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
            mark(x - r, y - r, x + r, y + r, 0.3)
        elif t.GetLayer() == pcbnew.B_Cu and t.m_Uuid.AsString() not in skip_tracks:
            mark(ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y), ToMM(t.GetWidth()) / 2 + 0.3)
    for fp in board.GetFootprints():
        if fp.GetReference() == skip_ref:
            continue
        for p in fp.Pads():
            if p.IsOnLayer(pcbnew.B_Cu) or p.HasHole():
                bb = p.GetBoundingBox()
                mark(ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()), 0.35)
    return occ, (x0, y0, res)


def stage_prepare():
    import numpy as np
    import kbd_extract
    from gen_pcb import load_fp
    from gen_schematic import uid
    board = pcbnew.LoadBoard(IMPORTED)
    d = cpmodel.load()
    if d.errors:
        raise SystemExit("design model has errors - run tools/cpmodel.py")
    report = []

    # ---- nets: the names of the netlist source ----
    m = kbd_extract.net_map(board)
    nets = {}
    for name, ni in list(board.GetNetsByName().items()):
        name = str(name)
        if name:
            ni.SetNetname(m[name])
            nets[m[name]] = ni
    for name in sorted(d.nets()):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni

    # ---- the parts that were there: value and schematic link from the model; their pads must already agree ----
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    new = []
    for c in d.comps.values():
        if c.ref not in fps:
            new.append(c)
            continue
        fp = fps[c.ref]
        fp.SetValue(c.value)
        fp.SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
        fp.SetSheetname("/" + c.sheet + "/")
        fp.SetSheetfile(f"sheets/{c.sheet}.kicad_sch")
        for pin, net in c.pins.items():
            for pad in cpmodel.pads_for(c, pin):
                got = [p.GetNetname() for p in fp.Pads() if p.GetNumber() == pad]
                if not got or any(g != (net or "") for g in got):
                    report.append("MISMATCH %s pad %s: board %s, model %s" % (c.ref, pad, got, net))
    extra = [r for r in fps if r not in d.comps and r != "U1"]
    if extra:
        report.append("on the Altium board but not in the model: " + " ".join(sorted(extra)))

    # ---- the mechanical holes of the switches: Altium had them as free pads without a copper ring, the import turned
    # them into vias (pad = hole), and 43 of them carry the net of a track that passes close by.  They become what
    # they are: non-plated holes, without a net.
    holes = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and ToMM(t.GetDrillValue()) >= 1.9
             and ToMM(t.GetWidth(pcbnew.F_Cu)) <= ToMM(t.GetDrillValue()) + 0.01]
    for n, v in enumerate(sorted(holes, key=lambda v_: (v_.GetPosition().y, v_.GetPosition().x)), 1):
        dia = v.GetDrillValue()
        hfp = pcbnew.FOOTPRINT(board)
        hfp.SetReference("H%d" % n)
        hfp.SetValue("hole %.1f mm" % ToMM(dia))
        hfp.Reference().SetVisible(False)
        hfp.Value().SetVisible(False)
        hfp.SetPosition(v.GetPosition())
        hfp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)
        pad = pcbnew.PAD(hfp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        try:
            pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(pcbnew.F_Cu, VECTOR2I(dia, dia))
        except TypeError:
            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(VECTOR2I(dia, dia))
        pad.SetDrillSize(VECTOR2I(dia, dia))
        pad.SetLayerSet(pad.UnplatedHoleMask())
        pad.SetPosition(v.GetPosition())
        hfp.Add(pad)
        board.Add(hfp)

    # ---- the fan-out of the module goes with it: from each of its pads the bottom-layer track is followed and removed
    # up to the first via, pad of another part or branch.  Nothing else of the old copper is touched; whatever those
    # tracks connected is joined to the new chip by the router.
    def key(pt):
        return (round(ToMM(pt.x), 2), round(ToMM(pt.y), 2))
    bt = [t for t in board.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetLayer() == pcbnew.B_Cu]
    ends = {}
    for t in bt:
        for e in (t.GetStart(), t.GetEnd()):
            ends.setdefault((t.GetNetname(), key(e)), []).append(t)
    vias = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias.setdefault(t.GetNetname(), []).append((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)))
    others = [(p.GetNetname(), p.GetBoundingBox()) for fp in board.GetFootprints() if fp.GetReference() != "U1"
              for p in fp.Pads() if p.IsOnLayer(pcbnew.B_Cu)]
    kill, killed = [], set()
    for pad in fps["U1"].Pads():
        net = pad.GetNetname()
        if net in ("", "GND"):
            continue
        bb = pad.GetBoundingBox()
        for t in [t for t in bt if t.GetNetname() == net and (bb.Contains(t.GetStart()) or bb.Contains(t.GetEnd()))]:
            cur, at = t, (t.GetEnd() if bb.Contains(t.GetStart()) else t.GetStart())
            while cur.m_Uuid.AsString() not in killed:
                killed.add(cur.m_Uuid.AsString())
                kill.append(cur)
                ax, ay = ToMM(at.x), ToMM(at.y)
                if any(math.hypot(ax - vx, ay - vy) < 0.1 for vx, vy in vias.get(net, ())) or any(n == net and b_.Contains(at) for n, b_ in others):
                    break
                if bb.Contains(at):
                    nxt = [x for x in ends.get((net, key(at)), []) if x.m_Uuid.AsString() not in killed]
                    if not nxt:
                        break
                    nxt = nxt[:1]
                else:
                    nxt = [x for x in ends.get((net, key(at)), []) if x.m_Uuid.AsString() not in killed]
                    if len(nxt) != 1:
                        break                       # an open end, or a branch: the rest is somebody else's connection
                cur = nxt[0]
                at = cur.GetEnd() if key(cur.GetStart()) == key(at) else cur.GetStart()
    extra = []
    for net, (bx0, by0, bx1, by1) in REMOVE_BOX:
        def inbox(pt):
            return bx0 <= ToMM(pt.x) <= bx1 and by0 <= ToMM(pt.y) <= by1
        for t in board.GetTracks():
            if t.GetNetname() == net and t.m_Uuid.AsString() not in killed and (
                    inbox(t.GetPosition()) if t.GetClass() == "PCB_VIA" else (inbox(t.GetStart()) and inbox(t.GetEnd()))):
                extra.append(t)
    kill_len = sum(ToMM(t.GetLength()) for t in kill)
    for net, lay_, e1, e2, to_ in TRIM:
        hit = [t for t in board.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == net
               and t.GetLayer() == (pcbnew.B_Cu if lay_ == "B" else pcbnew.F_Cu)
               and {(round(ToMM(t.GetStart().x), 1), round(ToMM(t.GetStart().y), 1)), (round(ToMM(t.GetEnd().x), 1), round(ToMM(t.GetEnd().y), 1))}
               == {(round(e1[0], 1), round(e1[1], 1)), (round(e2[0], 1), round(e2[1], 1))}]
        if len(hit) != 1:
            report.append("MISMATCH: the %s track to cut back at (%.2f, %.2f) was not found" % (net, e1[0], e1[1]))
            continue
        t = hit[0]
        first_is_start = abs(ToMM(t.GetStart().x) - e1[0]) < 0.06 and abs(ToMM(t.GetStart().y) - e1[1]) < 0.06
        (t.SetStart if first_is_start else t.SetEnd)(VECTOR2I(FromMM(to_[0]), FromMM(to_[1])))

    # ---- the new parts, on the bottom face ----
    occ, (ox, oy, res) = bottom_obstacles(board, (-2.0, 126.0, 162.0, 173.5), 0.1, "U1", {t.m_Uuid.AsString() for t in kill})
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps, True)
    edge_x = min(ToMM(ps.Outline(0).CPoint(i).x) for i in range(ps.Outline(0).PointCount())
                 if abs(ToMM(ps.Outline(0).CPoint(i).y) - USB_Y) < 60 and ToMM(ps.Outline(0).CPoint(i).y) > USB_Y - 40)

    def crt(fp):
        c = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
        bb = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False)
        return ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())

    def free(x0, y0, x1, y1):
        ia, ib = int(round((x0 - ox) / res)), int(round((x1 - ox) / res))
        ja, jb = int(round((y0 - oy) / res)), int(round((y1 - oy) / res))
        if ia < 0 or ja < 0 or ib >= occ.shape[1] or jb >= occ.shape[0]:
            return False
        return not occ[ja:jb + 1, ia:ib + 1].any()

    def take(x0, y0, x1, y1):
        ia, ib = max(0, int(round((x0 - ox) / res))), int(round((x1 - ox) / res))
        ja, jb = max(0, int(round((y0 - oy) / res))), int(round((y1 - oy) / res))
        occ[ja:jb + 1, ia:ib + 1] = True

    placed = {}
    courts = {}
    order = list(FIXED) + list(TARGETS)
    for c in sorted(new, key=lambda c_: order.index(c_.ref) if c_.ref in order else -1):
        fp = load_fp(c.fp)
        fp.SetReference(c.ref)
        fp.SetValue(c.value)
        if c.dnp:
            fp.SetDNP(True)
        fp.SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
        fp.SetSheetname("/" + c.sheet + "/")
        fp.SetSheetfile(f"sheets/{c.sheet}.kicad_sch")
        padnames = {p.GetNumber() for p in fp.Pads()}
        for pin, net in c.pins.items():
            for pad in cpmodel.pads_for(c, pin):
                if pad not in padnames:
                    report.append("PAD-MISSING %s (%s): pin %s -> pad %s" % (c.ref, c.fp, pin, pad))
                elif net is not None:
                    for p in fp.Pads():
                        if p.GetNumber() == pad:
                            p.SetNet(nets[net])
        if c.ref in ("U201", "U202", "J201"):        # fine pitch: the opening is the pad, not pad + 0.1 mm (imported board setting)
            for p_ in fp.Pads():
                try:
                    p_.SetLocalSolderMaskMargin(0)
                except Exception:                   # noqa: BLE001  (older bindings)
                    pass
        fp.SetPosition(VECTOR2I(0, 0))
        board.Add(fp)                               # (a footprint is flipped only once it belongs to a board)
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if c.ref == "J201":                          # on the left edge, mating face outwards
            best = None
            for rot in (0, 90, 180, 270):
                fp.SetOrientationDegrees(rot)
                x0, y0, x1, y1 = crt(fp)
                pads = [p for p in fp.Pads() if p.GetNumber()[:1] in ("A", "B")]
                px = sum(ToMM(p.GetPosition().x) for p in pads) / len(pads)
                if best is None or px - (x0 + x1) / 2 > best[0]:
                    best = (px - (x0 + x1) / 2, rot)
            fp.SetOrientationDegrees(best[1])
            x0, y0, x1, y1 = crt(fp)
            pos = fp.GetPosition()
            # 0.05 mm grid, so that the pads fall on the router's grid
            nx_ = round((ToMM(pos.x) + (edge_x - USB_OVERHANG) - x0) * 20) / 20
            ny_ = round((ToMM(pos.y) + USB_Y - (y0 + y1) / 2) * 20) / 20
            fp.SetPosition(VECTOR2I(FromMM(nx_), FromMM(ny_)))
            x0, y0, x1, y1 = crt(fp)
            take(x0, y0 - 0.3, x1 + 0.3, y1 + 0.3)
            placed[c.ref] = (round(ToMM(fp.GetPosition().x), 2), round(ToMM(fp.GetPosition().y), 2), best[1])
            continue
        if c.ref in FIXED:
            fx, fy, rot = FIXED[c.ref]
            fp.SetOrientationDegrees(rot)
            fp.SetPosition(VECTOR2I(FromMM(fx), FromMM(fy)))
            x0, y0, x1, y1 = crt(fp)
            for o_ref, (a0, b0, a1, b1) in courts.items():
                if x0 < a1 - 0.01 and a0 < x1 - 0.01 and y0 < b1 - 0.01 and b0 < y1 - 0.01:
                    report.append("overlap: the courtyards of %s and %s" % (c.ref, o_ref))
            courts[c.ref] = (x0, y0, x1, y1)
            take(x0, y0, x1, y1)
            placed[c.ref] = (fx, fy, rot, 0.0)
            if os.environ.get("CP_VERBOSE"):
                print("   %-6s" % c.ref, "  ".join("%s=%s (%.2f, %.2f)" % (p.GetNumber(), p.GetNetname(), ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))
                                                 for p in list(fp.Pads())[:6 if c.ref != "U201" else 0]),
                      "court (%.2f, %.2f)-(%.2f, %.2f)" % (x0, y0, x1, y1))
            continue
        if c.ref not in TARGETS:
            report.append("no target position for %s" % c.ref)
            continue
        tx, ty = TARGETS[c.ref]
        best = None
        for rot in ((ROT[c.ref],) if c.ref in ROT else (0, 90)):
            fp.SetOrientationDegrees(rot)
            fp.SetPosition(VECTOR2I(0, 0))
            x0, y0, x1, y1 = crt(fp)
            w, h, cx, cy = x1 - x0, y1 - y0, (x0 + x1) / 2, (y0 + y1) / 2
            for ring in range(0, 121):               # nearest free spot, on a 0.25 mm lattice, up to 30 mm away
                cands = [(dx * 0.25, dy * 0.25) for dx in range(-ring, ring + 1) for dy in range(-ring, ring + 1) if max(abs(dx), abs(dy)) == ring]
                hit = [(math.hypot(dx, dy), dx, dy) for dx, dy in cands
                       if free(tx + dx - w / 2 - 0.15, ty + dy - h / 2 - 0.15, tx + dx + w / 2 + 0.15, ty + dy + h / 2 + 0.15)]
                if hit:
                    dist, dx, dy = min(hit)
                    if best is None or dist < best[0]:
                        best = (dist, rot, tx + dx - cx, ty + dy - cy, w, h, tx + dx, ty + dy)
                    break
        if best is None:
            report.append("NO ROOM for %s near (%.1f, %.1f)" % (c.ref, tx, ty))
            continue
        dist, rot, px, py, w, h, ccx, ccy = best
        if dist > 1.0 and os.environ.get("CP_VERBOSE"):     # what is in the way at the target (0.2 mm per character)
            print("   %s: target (%.1f, %.1f), put at (%.1f, %.1f); the bottom face round the target:" % (c.ref, tx, ty, ccx, ccy))
            for yy in range(-20, 21):
                print("      " + "".join("#" if occ[int(round((ty + yy * 0.2 - oy) / res)), int(round((tx + xx * 0.2 - ox) / res))] else
                                         ("+" if abs(xx * 0.2) <= w / 2 and abs(yy * 0.2) <= h / 2 else ".") for xx in range(-30, 31)))
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(VECTOR2I(FromMM(round(px * 20) / 20), FromMM(round(py * 20) / 20)))
        m_ = RING if c.ref == "U201" else 0.0
        take(ccx - w / 2 - m_, ccy - h / 2 - m_, ccx + w / 2 + m_, ccy + h / 2 + m_)
        placed[c.ref] = (round(px, 2), round(py, 2), rot, round(dist, 2))

    ds = board.GetDesignSettings()
    ds.SetBoardThickness(FromMM(THICKNESS))
    ds.m_SolderMaskMinWidth = 0                 # (the import set a minimum web; the fine-pitch pads of the new parts share one opening)
    json.dump(dict(placed=placed, report=report, removed_tracks=len(kill), removed_mm=round(kill_len, 1), holes=len(holes)), open(os.path.join(ROOT, "build", "kbd_prepare.json"), "w", encoding="utf-8"), indent=1)
    print("prepared  %d parts kept, %d new parts placed on the bottom face, module U1 removed with %d fan-out tracks (%.0f mm), "
          "%d mechanical holes made non-plated" % (len(fps) - 1, len(placed), len(kill), kill_len, len(holes)))
    for ref, v in placed.items():
        if len(v) == 4 and v[3] > 3.0:
            print("   %s sits %.1f mm from its target" % (ref, v[3]))
    for line in report:
        print("  ", line)
    # last: the module goes (KiCad's Python objects are not reliable after an item has been removed)
    for t in kill + extra + holes:
        board.Remove(t)
    board.Remove(fps["U1"])
    pcbnew.SaveBoard(PREPARED, board)
    if any(x.startswith(("MISMATCH", "PAD-MISSING", "NO ROOM", "no target")) for x in report):
        raise SystemExit(1)


# --------------------------------------------------------------------------
def make_router(board):
    """The mainboard's grid router, set up for this board (two layers, its own widths), with one window that covers
    the new parts; returns (router, window, net code by name)."""
    import numpy as np
    import route
    from gen_pcb import OX, OY
    R = route

    # ---- the router, set up for this board: two layers, its own widths ----
    R.STRIP = True                              # no middle routing layer
    R.VIA_L = [0, 2]
    R.BASE_CL = KBD_CL                          # every class of this board has the same clearance: nothing is marked fatter
    R.RCS.clear()
    R.RCS.update({"Default": R.RC("Default", KBD_W, KBD_CL, 0.60, 0.30), "PWR": R.RC("PWR", 0.40, KBD_CL, 0.80, 0.40),
                  "FAN": R.RC("FAN", KBD_W, KBD_CL, 0.50, 0.30)})        # (the vias beside the chip's pins)
    R.THIN.clear()
    R.THIN.update({"PWR": R.RC("PWR_thin", 0.25, 0.15, 0.80, 0.40)})
    R.PAIRS.clear()
    R.LANE = 0.0                                # (the chip's pins get real pieces of track instead: escape_chip)
    # A 0.15 mm track that passes between two of the 0.5 / 0.3 vias beside the chip (1 mm apart) is 0.175 mm from their
    # copper and 0.275 mm from their holes: allowed.  The router's extra margin round small holes is written for the
    # 0.09 mm classes of the mainboard and would close that gap.
    R.RCS["FAN"].hx = 0
    R.PAIR_CLASSES = ()
    R.KSET = sorted({rc.Kt for rc in list(R.RCS.values()) + list(R.THIN.values())} | {rc.Kv for rc in R.RCS.values()})
    R.VIA_ONLY_K = set()
    R.PLANES.clear()
    R.PLANES.update({"GND": ("kbd",)})
    R.SKIP_CLASSES.clear()
    R.SKIP_NETS.clear()
    R.PRIMARY_AREA[:] = []
    R.CFG["PRI_X1"] = R.CFG["PRI_Y1"] = -1e6
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps, True)
    o = ps.Outline(0)
    outline = [(ToMM(o.CPoint(i).x) - OX, ToMM(o.CPoint(i).y) - OY) for i in range(o.PointCount())]
    R.outline_pts = lambda: outline
    G = R.G

    r = R.Router(board)
    code = {v: k for k, v in r.name_of.items()}
    for n in ("VBUS_USB", "VCC5"):
        r.rc_of[code[n]] = R.RCS["PWR"]
    reg = R.Region("kbd", ROUTE_BOX[0] - OX, ROUTE_BOX[1] - OY, ROUTE_BOX[2] - OX, ROUTE_BOX[3] - OY)
    r.regs = [reg]
    r.build()
    r.items, r.failed = [], []

    # ---- obstacles the router does not know from the mainboard: cut-outs, bare holes, copper zones ----
    def cellbox(xa, ya, xb, yb, m):
        i0, j0 = max(0, int((xa - m - OX - reg.x0) / G)), max(0, int((ya - m - OY - reg.y0) / G))
        i1, j1 = min(reg.nx - 1, R.ceil_((xb + m - OX - reg.x0) / G)), min(reg.ny - 1, R.ceil_((yb + m - OY - reg.y0) / G))
        return i0, j0, i1, j1
    nhole = 0
    for h in range(ps.HoleCount(0)):
        bb = ps.Hole(0, h).BBox()
        i0, j0, i1, j1 = cellbox(ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()), 0.30)
        if i0 <= i1 and j0 <= j1:
            for l in (0, 2):
                reg.stamp(l, i0, j0, np.ones((j1 - j0 + 1, i1 - i0 + 1), bool), R.MULTI)
            reg.novia[max(0, j0 - 8):j1 + 9, max(0, i0 - 8):i1 + 9] = True
            nhole += 1
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetCode() <= 0:           # the holes of the switches came over as net-less vias
            rad = max(ToMM(t.GetWidth(pcbnew.F_Cu)), ToMM(t.GetDrillValue())) / 2 + 0.30
            x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
            i, j = int(round((x - OX - reg.x0) / G)), int(round((y - OY - reg.y0) / G))
            k = R.ceil_(rad / G)
            if -k <= i < reg.nx + k and -k <= j < reg.ny + k:
                for l in (0, 2):
                    reg.stamp(l, i - k, j - k, R.disc(k), R.MULTI)
                reg.novia[max(0, j - k - 8):j + k + 9, max(0, i - k - 8):i + k + 9] = True
                nhole += 1
    nzone = 0
    for z in board.Zones():
        if z.GetNetname() == "GND" or z.GetIsRuleArea():
            continue                                # the ground pours close in again; every other zone is a connection
        l = 0 if z.GetLayer() == pcbnew.F_Cu else 2
        fill = z.GetFilledPolysList(z.GetLayer())
        mask = np.zeros((reg.ny, reg.nx), bool)
        xs = reg.x0 + np.arange(reg.nx) * G
        for k in range(fill.OutlineCount()):
            rings = [fill.Outline(k)] + [fill.Hole(k, h) for h in range(fill.HoleCount(k))]
            edges = []
            for ring in rings:
                pts = [(ToMM(ring.CPoint(i).x) - OX, ToMM(ring.CPoint(i).y) - OY) for i in range(ring.PointCount())]
                edges += list(zip(pts, pts[1:] + pts[:1]))
            edges = [e for e in edges if max(e[0][1], e[1][1]) >= reg.y0 and min(e[0][1], e[1][1]) <= reg.y1]
            if not edges:
                continue
            for j in range(reg.ny):
                y = reg.y0 + j * G + 1e-6
                xc = sorted(ax + (y - ay) * (bx - ax) / (by - ay) for (ax, ay), (bx, by) in edges if (ay > y) != (by > y))
                for a, b in zip(xc[0::2], xc[1::2]):
                    mask[j, (xs >= a - G / 2) & (xs <= b + G / 2)] = True
        if mask.any():
            net = z.GetNetCode()
            reg.stamp(l, 0, 0, mask, net)
            # ... and for its own net it IS a connection: whatever of the net lies in the fill is one island with it,
            # and a new pad of that net may be joined to the fill itself (a sparse set of its cells becomes a target)
            zn = reg.node()
            for c_, nd in list(reg.tree.get(net, {}).items()):
                if c_[0] == l and mask[c_[2], c_[1]]:
                    reg.union(nd, zn)
            for pd in reg.pads.get(net, []):
                if any(c_[0] == l and mask[c_[2], c_[1]] for c_ in pd["cells"]):
                    reg.union(pd["node"], zn)
            inner = ~R.dilate(~mask, R.ceil_(0.5 / G))              # well inside the fill
            js, is_ = np.nonzero(inner[::6, ::6])
            reg.assign(net, [(l, int(i) * 6, int(j) * 6) for i, j in zip(is_, js)], zn)
            nzone += 1
    # ---- what is connected already - by copper outside the window, by a zone - is ONE island: KiCad knows ----
    conn = board.GetConnectivity()
    lay = {pcbnew.F_Cu: 0, pcbnew.B_Cu: 2}
    item_node = {}
    for net, pads in reg.pads.items():
        for pd in pads:
            item_node[pd["pad"].m_Uuid.AsString()] = (net, pd["node"])
    for t in board.GetTracks():
        net = t.GetNetCode()
        tr = reg.tree.get(net)
        if not tr:
            continue
        if t.GetClass() == "PCB_VIA":
            ends = [(ToMM(t.GetPosition().x), ToMM(t.GetPosition().y))]
        else:                                       # (a track may start and end outside the window: points along it)
            (ax, ay), (bx, by) = [(ToMM(q.x), ToMM(q.y)) for q in (t.GetStart(), t.GetEnd())]
            ends = [(ax + (bx - ax) * k / 24.0, ay + (by - ay) * k / 24.0) for k in range(25)]
        ls = (0, 2) if t.GetClass() == "PCB_VIA" else (lay.get(t.GetLayer(), 0),)
        for ex, ey in ends:
            i, j = int(round((ex - OX - reg.x0) / G)), int(round((ey - OY - reg.y0) / G))
            nd = next((tr[(l, i + di, j + dj)] for l in ls for di in (0, -1, 1) for dj in (0, -1, 1) if (l, i + di, j + dj) in tr), None)
            if nd is not None:
                item_node[t.m_Uuid.AsString()] = (net, nd)
                break
    done_, njoin = set(), 0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            u = pad.m_Uuid.AsString()
            if u in done_ or u not in item_node or pad.GetNetname() == "GND":
                continue
            net, nd = item_node[u]
            for it in conn.GetConnectedItems(pad, 0):
                v = it.m_Uuid.AsString()
                done_.add(v)
                if v in item_node and item_node[v][0] == net and reg.find(item_node[v][1]) != reg.find(nd):
                    reg.union(item_node[v][1], nd)
                    njoin += 1
    for t in board.GetTracks():                     # (copper that hangs on no pad inside the window)
        u = t.m_Uuid.AsString()
        if u in done_ or u not in item_node or t.GetNetname() == "GND":
            continue
        net, nd = item_node[u]
        for it in conn.GetConnectedItems(t, 0):
            v = it.m_Uuid.AsString()
            done_.add(v)
            if v in item_node and item_node[v][0] == net and reg.find(item_node[v][1]) != reg.find(nd):
                reg.union(item_node[v][1], nd)
                njoin += 1
    print("router window %d x %d cells; %d cut-outs and holes, %d copper zones added as obstacles; %d islands joined by copper elsewhere"
          % (reg.nx, reg.ny, nhole, nzone, njoin), flush=True)
    return r, reg, code


def escape_chip(board, r, reg, code, ref="U201"):
    """Before anything is routed: every signal pin of the chip gets a straight piece of track outwards with a via at
    its end - two staggered rows, so that neighbours 0.5 mm apart all fit - and every ground pin a track inwards to the
    exposed pad.  Afterwards no pin can be fenced in by its neighbour's track, and every pin can leave on either layer.
    The crystal pins get the piece of track only (they stay on the bottom layer)."""
    import route as R
    from gen_pcb import OX, OY
    G = R.G
    fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
    cx, cy = ToMM(fp.GetPosition().x) - OX, ToMM(fp.GetPosition().y) - OY
    rc = R.RCS["FAN"]
    gnd = code["GND"]
    Dv = reg.D[rc.Kv]
    plan, notes, ngnd = [], [], 0
    for net, pads in reg.pads.items():
        for pd in pads:
            if pd["ref"] != ref:
                continue
            dx, dy = pd["cx"] - cx, pd["cy"] - cy
            if max(abs(dx), abs(dy)) < 3.0:
                continue                                    # the exposed pad
            ux, uy = ((1 if dx > 0 else -1), 0) if abs(dx) > abs(dy) else (0, (1 if dy > 0 else -1))
            if net == gnd:
                r.add_track(reg, net, 2, (pd["cx"], pd["cy"]), (pd["cx"] - ux * 1.2, pd["cy"] - uy * 1.2), 0.2)
                pd["fanned"] = True
                ngnd += 1
                continue
            dist = FAN_SHORT if int(pd["num"]) % 2 else FAN_LONG
            vx, vy = (cx + ux * dist, pd["cy"]) if ux else (pd["cx"], cy + uy * dist)
            i, j = int(round((vx - reg.x0) / G)), int(round((vy - reg.y0) / G))
            via = r.name_of[net] not in FAN_NO_VIA
            if via and not (all(int(Dv[l, j, i]) in (R.FREE, net) for l in (0, 2)) and not reg.novia[j, i]):
                via = False                                 # (judged against what was there before: the two rows fit each other)
                notes.append("%s.%s (%s): no room for its via" % (ref, pd["num"], r.name_of[net]))
            if not via:                                     # a short piece of track only
                vx, vy = (cx + ux * FAN_SHORT, pd["cy"]) if ux else (pd["cx"], cy + uy * FAN_SHORT)
                i, j = int(round((vx - reg.x0) / G)), int(round((vy - reg.y0) / G))
            plan.append((net, pd, i, j, via, ux, uy))
    nvia = 0
    n_, k_ = int(round(FAN_STRIP / G)), 4
    for net, pd, i, j, via, ux, uy in plan:                 # the way on from the end of each piece: others pay to cross it
        for l in ((0, 2) if via else (2,)):
            i0, i1 = ((i, i + n_) if ux > 0 else (i - n_, i)) if ux else (i - k_, i + k_)
            j0, j1 = ((j, j + n_) if uy > 0 else (j - n_, j)) if uy else (j - k_, j + k_)
            v = reg.soft[l, max(0, j0):j1 + 1, max(0, i0):i1 + 1]
            other = (v != R.FREE) & (v != net)
            v[v == R.FREE] = net
            v[other] = R.MULTI
    for net, pd, i, j, via, ux, uy in plan:
        a, b = (pd["cx"], pd["cy"]), reg.xy(i, j)
        r.add_track(reg, net, 2, a, b, rc.w)
        cells, _ = reg.seg_cells(a, b)
        reg.stamp_cells(2, cells, rc.mt, net)
        reg.assign(net, [(2, ci, cj) for ci, cj in cells], pd["node"])
        if via:
            r.add_via(reg, net, i, j, rc, pd["node"])
            nvia += 1
    # the supply pins 2 (UVCC), 7 (VBUS) and 14 (VCC): linked on the TOP face under the chip, 0.9 mm inside the east
    # row of vias - fixed, thin (the chip's own current), before the signals fill the space round the chip.  Pin 34
    # and the capacitors are reached by the supply net later.
    v = {pd["num"]: (i, j) for net, pd, i, j, via, ux, uy in plan if via and r.name_of[net] == "VCC5"}
    if all(k in v for k in ("2", "7", "14")) and all(pd["cx"] > cx + 3 for net, pd, *_ in plan if pd["num"] in ("2", "7")):
        vcc = code["VCC5"]
        node = next(pd["node"] for net, pd, *_ in plan if pd["num"] == "2")
        xi = int(round((cx + FAN_SHORT - 0.85 - reg.x0) / G))          # the column the link runs in
        yj = int(round((cy + FAN_SHORT - 0.85 - reg.y0) / G))          # ... and the row, for pin 14
        (i2, j2), (i7, j7), (i14, j14) = v["2"], v["7"], v["14"]
        for pts in ([(i2, j2), (xi, j2), (xi, j7), (i7, j7)], [(i14, j14), (i14, yj), (xi, yj), (xi, j7)]):
            for (ia, ja), (ib, jb) in zip(pts, pts[1:]):
                a, b = reg.xy(ia, ja), reg.xy(ib, jb)
                r.add_track(reg, vcc, 0, a, b, rc.w)
                cells, _ = reg.seg_cells(a, b)
                reg.stamp_cells(0, cells, rc.mt, vcc)
                reg.assign(vcc, [(0, ci, cj) for ci, cj in cells], node)
        for net, pd, *_ in plan:
            if pd["num"] in ("7", "14") and r.name_of[net] == "VCC5":
                reg.union(pd["node"], node)
    else:
        notes.append("the supply pins 2, 7, 14 were not linked under the chip")
    # the exposed pad: the ground pour of the bottom face cannot get inside the ring of pins, so a via in the pad and
    # a track on the top face out through the gap that the unconnected pin 42 and the ground pin 43 leave in the north
    # row, to a second via where both pours are open
    ep = next((pd for pd in reg.pads.get(gnd, []) if pd["ref"] == ref and max(abs(pd["cx"] - cx), abs(pd["cy"] - cy)) < 3.0), None)
    p43 = next((pd_ for pads in reg.pads.values() for pd_ in pads if pd_["ref"] == ref and pd_["num"] == "43"), None)
    p44 = next((pd_ for pads in reg.pads.values() for pd_ in pads if pd_["ref"] == ref and pd_["num"] == "44"), None)
    if ep is not None and p43 and p44 and p43["cy"] < cy - 3.0 and abs(p43["cy"] - p44["cy"]) < 0.01:      # (that row is the north one)
        gx = p43["cx"] - (p44["cx"] - p43["cx"]) / 2            # half-way between pin 42 and pin 43
        rc0 = R.RCS["Default"]
        i = int(round((gx - reg.x0) / G))
        j_in, j_out = int(round((cy - 1.4 - reg.y0) / G)), int(round((cy - FAN_LONG - 1.0 - reg.y0) / G))
        a, b = reg.xy(i, j_in), reg.xy(i, j_out)
        r.add_track(reg, gnd, 0, a, b, 0.3)
        cells, _ = reg.seg_cells(a, b)
        reg.stamp_cells(0, cells, R.ceil_((0.15 - R.TOL) / G), gnd)
        reg.assign(gnd, [(0, ci, cj) for ci, cj in cells], ep["node"])
        r.add_via(reg, gnd, i, j_in, rc0, ep["node"])
        r.add_via(reg, gnd, i, j_out, rc0, ep["node"])
        ep["fanned"] = True
    print("chip escape: %d pins with a via, %d with a piece of track only, %d ground pins tied to the exposed pad"
          % (nvia, len(plan) - nvia, ngnd), flush=True)
    for n_ in notes:
        print("  ", n_, flush=True)
    return nvia


def plan_wishes(r, reg, nets):
    """Routes every net alone on the board as it is now, notes where it went, and puts everything back.  Returns
    {net: cells} and the names of the nets that cannot be routed even alone."""
    import numpy as np
    base = {k: D.copy() for k, D in reg.D.items()}
    novia0, uf0, nitems = reg.novia.copy(), list(reg.uf), len(r.items)
    wish, alone_bad = {}, []
    for net in nets:
        tree0, exact0 = dict(reg.tree.get(net, {})), dict(reg.exact.get(net, {}))
        nfail = len(r.failed)
        _, bad = r.route_net(reg, net)
        if bad:
            alone_bad.append(r.name_of[net])
        wish[net] = [c for c in reg.tree.get(net, {}) if c not in tree0]
        for k, D in reg.D.items():                  # put everything back
            np.copyto(D, base[k])
        np.copyto(reg.novia, novia0)
        reg.uf[:] = uf0
        reg.tree[net] = tree0
        if exact0 or net in reg.exact:
            reg.exact[net] = exact0
        del r.items[nitems:]
        del r.failed[nfail:]
    return wish, alone_bad


def soften(reg, net, cells, k):
    """The cells (grown by k) become a corridor of 'net' in the penalty map: other nets pay to pass there."""
    import numpy as np
    import route as R
    by = {}
    for l, i, j in cells:
        by.setdefault(l, []).append((i, j))
    for l, ij in by.items():
        i0, i1 = max(0, min(i for i, _ in ij) - k), min(reg.nx - 1, max(i for i, _ in ij) + k)
        j0, j1 = max(0, min(j for _, j in ij) - k), min(reg.ny - 1, max(j for _, j in ij) + k)
        m = np.zeros((j1 - j0 + 1, i1 - i0 + 1), bool)
        for i, j in ij:
            m[j - j0, i - i0] = True
        m = R.dilate(m, k)
        v = reg.soft[l, j0:j1 + 1, i0:i1 + 1]
        other = m & (v != R.FREE) & (v != net)
        free = m & (v == R.FREE)
        v[free] = net
        v[other] = R.MULTI


def show_blockers(r, reg, net, bad):
    """Who owns the cells round the chip pin (or other pad) that a net could not reach: both layers, 0.05 mm per character."""
    import route as R
    D = reg.D[r.rc_of[net].Kt]
    for b in bad:
        ref_num = b.split(" ")[0]
        pd = next((q for q in reg.pads.get(net, []) if q["ref"] + "." + q["num"] == ref_num), None)
        if pd is None:
            continue
        ci, cj = int(round((pd["cx"] - reg.x0) / R.G)), int(round((pd["cy"] - reg.y0) / R.G))
        names = {}
        print("   %s at %s: '.' free, 'o' own, '#' shared / forbidden, letters = other nets" % (r.name_of[net], ref_num))
        for l in (2, 0):
            print("   layer", "bottom" if l == 2 else "top")
            for j in range(max(0, cj - 30), min(reg.ny, cj + 31)):
                row = ""
                for i in range(max(0, ci - 60), min(reg.nx, ci + 61)):
                    v = int(D[l, j, i])
                    row += "." if v == R.FREE else "o" if v == net else "#" if v == R.MULTI else names.setdefault(v, chr(ord("a") + len(names) % 26))
                print("      " + row)
        print("     ", {ch: r.name_of.get(v, v) for v, ch in names.items()}, flush=True)


def link_first(r, reg, net, pd, rc):
    """A thin track from the island that pad 'pd' belongs to, to any other island of its net (searched, not fixed)."""
    import numpy as np
    import route as R
    root = reg.find(pd["node"])
    pads = reg.pads.get(net, [])
    own = [c for q in pads if reg.find(q["node"]) == root for c in q["cells"]] +           [c for c, nd in reg.tree.get(net, {}).items() if reg.find(nd) == root]
    other = [c for q in pads if reg.find(q["node"]) != root for c in q["cells"]] +             [c for c, nd in reg.tree.get(net, {}).items() if reg.find(nd) != root]
    if not own or not other:
        return False
    # the window reaches from the pad to the nearest copper of the rest of the net (plus a margin to go round things)
    near = min(other, key=lambda c: (reg.xy(c[1], c[2])[0] - pd["cx"]) ** 2 + (reg.xy(c[1], c[2])[1] - pd["cy"]) ** 2)
    nx_, ny_ = reg.xy(near[1], near[2])
    for margin in (60, 200):
        box = (min(pd["cx"], nx_) - 2, min(pd["cy"], ny_) - 2, max(pd["cx"], nx_) + 2, max(pd["cy"], ny_) + 2)
        i0, j0, W, H, ok, vok = r.window(reg, net, rc, box, margin)
        goal = np.zeros((3, H, W), bool)
        for c in other:
            if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H:
                goal[c[0], c[2] - j0, c[1] - i0] = True
        goal &= ok
        starts = [(c[0] * H + (c[2] - j0)) * W + (c[1] - i0) for c in own
                  if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H and ok[c[0], c[2] - j0, c[1] - i0]]
        if not starts or not goal.any():
            continue
        gl, gy, gx = np.nonzero(goal)
        res, _ = R.search([ok[l].tobytes() for l in range(3)], vok.tobytes(), [goal[l].tobytes() for l in range(3)], W, H, starts,
                          (int(gx.min()), int(gy.min()), int(gx.max()), int(gy.max())), max_exp=1500000, penb=r.pen)
        if res:
            cells = r.commit(reg, net, rc, res, W, H, i0, j0)
            for c in (cells[0], cells[-1]):
                n = reg.padcell.get(net, {}).get(c)
                if n is not None:
                    r.stub(reg, net, rc, c, pads[n])
            return True
    return False


def route_pass(prio, variant=0):
    """One attempt on a fresh copy of the prepared board; 'prio': nets that go first (they failed before);
    'variant': the order of the chip's lines - 0 shortest first, 1 longest first, 2 / 3 round the chip clockwise /
    anticlockwise, 4 and up shuffled."""
    board = pcbnew.LoadBoard(PREPARED)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())           # (the fills still show the module; the islands are read from them)
    board.BuildConnectivity()
    before = board.GetConnectivity().GetUnconnectedCount(True)
    r, reg, code = make_router(board)

    # 1. at the USB-C receptacle each data line has two pads (A and B row) with the other line between them: join those
    #    first, while nothing else is there;  2. the chip's pins get their escape;  3. every net that has a pin on the
    #    chip, the short ones first;  4. the supply;  5. last the two long data lines from the receptacle to the chip.
    def pad_of(net, ref, num):
        return next((pd for pd in reg.pads.get(net, []) if pd["ref"] == ref and pd["num"] == num), None)
    notes = []
    # The four data pads lie in the order D+ D- D+ D-.  The inner two cannot both leave on the same side, so:
    #   D- (A7, B7): a loop round the end of A6 under the receptacle's body;
    #   D+ (B6, A6): a loop round the other end of A7;   the lines go on from the D+ loop and from B7.
    fp = next(f for f in board.GetFootprints() if f.GetReference() == "J201")
    from gen_pcb import OX
    body = -1 if ToMM(fp.GetBoundingBox(False).Centre().x) - OX < pad_of(code["USB_CON_DP"], "J201", "A6")["cx"] else 1
    rc = r.rc_of[code["USB_CON_DP"]]
    for name, a, b, side in (("USB_CON_DM", "A7", "B7", body), ("USB_CON_DP", "B6", "A6", -body)):
        net = code[name]
        pa, pb = pad_of(net, "J201", a), pad_of(net, "J201", b)
        x = pa["cx"] + side * USB_LOOP
        pts = [(pa["cx"], pa["cy"]), (x, pa["cy"]), (x, pb["cy"]), (pb["cx"], pb["cy"])]
        for p1, p2 in zip(pts, pts[1:]):
            r.add_track(reg, net, 2, p1, p2, rc.w)
            cells, _ = reg.seg_cells(p1, p2)
            reg.stamp_cells(2, cells, rc.mt, net)
            reg.assign(net, [(2, ci, cj) for ci, cj in cells], pa["node"])
        reg.union(pa["node"], pb["node"])
    escape_chip(board, r, reg, code)
    # Pins whose way out crosses everybody else's go in now, while the area is open (each alone always routes):
    #   24  AVCC on +5 V, in the south-west corner where the D lines fan out westwards (thin: it draws next to nothing)
    #   20  D0 (LED enable), at the west end of the south row, to the jumper J1 east of the chip: it has to cross the
    #       south row's other lines (D11 at the east end goes west), so it goes first, under the chip on the top face
    import route as R
    for pin in EARLY_PINS:
        pd_ = next((q for net_, pads_ in reg.pads.items() for q in pads_ if q["ref"] == "U201" and q["num"] == pin), None)
        if pd_ is None:
            continue
        net_ = next(n_ for n_, pads_ in reg.pads.items() if pd_ in pads_)
        if len(r.groups(reg, net_)) > 1 and not link_first(r, reg, net_, pd_, R.RCS["Default"]):
            notes.append("%s: chip pin %s could not be linked before the others" % (r.name_of[net_], pin))
    # ---- ground: a via next to every ground pad of the new parts, NOW, while there is room beside them (the pours on
    # both faces do the rest; what they do not reach in the end is the business of the ground stage) ----
    gnd = code["GND"]
    new_refs = {c.ref for c in cpmodel.load().comps.values() if c.sheet == "kbd_mcu"}
    only = {pd["ref"] + "." + pd["num"] for pd in reg.pads.get(gnd, []) if pd["ref"] in new_refs}
    fan_ok, fan_bad = r.fanout(reg, gnd, only=only)
    chip = {c_ for c_, pads in reg.pads.items() if any(pd["ref"] == "U201" for pd in pads)}
    first = ("XTAL1", "XTAL2", "UCAP", "USB_MCU_DP", "USB_MCU_DM", "SCK")        # short, or easily cut off by the others
    import random
    rnd = random.Random(variant)
    ufp = next(f for f in board.GetFootprints() if f.GetReference() == "U201")
    from gen_pcb import OY
    chip_xy = (ToMM(ufp.GetPosition().x) - OX, ToMM(ufp.GetPosition().y) - OY)
    todo = []
    for net in sorted(set(reg.pads) | set(reg.tree)):
        name = r.name_of[net]
        if name == "GND" or len(r.groups(reg, net)) < 2:
            continue
        pads = reg.pads.get(net, [])
        span = (max(q["cx"] for q in pads) - min(q["cx"] for q in pads) + max(q["cy"] for q in pads) - min(q["cy"] for q in pads)) if pads else 0.0
        rank = (-2 if name in first else -1 if name in prio else 3 if name.startswith("USB_CON") else 2 if r.rc_of[net].name == "PWR"
                else 0 if net in chip else 1)
        key = span
        if rank == 0 and variant:
            pin = next(pd for pd in pads if pd["ref"] == "U201")
            ang = math.atan2(pin["cy"] - chip_xy[1], pin["cx"] - chip_xy[0])
            key = -span if variant == 1 else ang if variant == 2 else -ang if variant == 3 else rnd.random()
        todo.append((rank, -prio.get(name, 0) if rank == -1 else key if rank == 0 else 0.0, name, net))
    # where every net would go if it were alone: the others then keep out of that corridor where they can
    wish, alone_bad = plan_wishes(r, reg, [t[3] for t in sorted(todo)])
    for name in alone_bad:
        notes.append("%s: cannot be completed even on the otherwise untouched board" % name)
    for net, cells in wish.items():
        soften(reg, net, cells, WISH_K)
    print("planned: %d nets tried alone, %d of them complete" % (len(wish), len(wish) - len(alone_bad)), flush=True)
    done, part = [], []
    for rank, span, name, net in sorted(todo):
        okp, bad = r.route_net(reg, net)
        (part if bad else done).append(name)
        r.failed += ["%s: could not reach %s" % (name, b) for b in bad]
        if bad and os.environ.get("CP_VERBOSE"):
            show_blockers(r, reg, net, bad)
    return dict(board=board, r=r, before=before, done=done, part=part, notes=notes, fan_ok=fan_ok, fan_bad=fan_bad)


def stage_route():
    passes = int(os.environ.get("CP_PASSES", "12"))      # each pass takes the chip's lines in another order; the best is kept
    prio, best = {}, None
    for n in range(passes):
        res = route_pass({}, n + int(os.environ.get("CP_VARIANT_FROM", "0")))      # (later runs can try further orders)
        bad = len(res["r"].failed) + len(res["fan_bad"])
        print("pass %d: %d nets complete, %d not (%s)" % (n + 1, len(res["done"]), len(res["part"]), " ".join(res["part"]) or "-"), flush=True)
        if best is None or (len(res["part"]), bad) < (len(best["part"]), len(best["r"].failed) + len(best["fan_bad"])):
            best = res
        if not res["part"]:
            break
        for name in res["part"]:
            prio[name] = prio.get(name, 0) + 1
    board, r = best["board"], best["r"]
    r.flush(r.items)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    after = board.GetConnectivity().GetUnconnectedCount(True)
    pcbnew.SaveBoard(FINAL, board, True)        # (True: the project file with the rules and classes is not touched)
    out = dict(before=best["before"], after=after, done=best["done"], part=best["part"], failed=r.failed + best["notes"],
               gnd_vias=best["fan_ok"], gnd_no_via=best["fan_bad"],
               tracks=r.stats["tracks"], vias=r.stats["vias"], length=round(r.stats["length"], 1))
    json.dump(out, open(os.path.join(ROOT, "build", "kbd_route.json"), "w", encoding="utf-8"), indent=1)
    print("routed    %d nets complete, %d not; %d tracks, %d vias, %.0f mm added; ground vias %d (none for %d)"
          % (len(out["done"]), len(out["part"]), out["tracks"], out["vias"], out["length"], out["gnd_vias"], len(out["gnd_no_via"])))
    print("open connections: %d before the new parts were connected -> %d after" % (out["before"], after))
    for f in out["failed"] + ["GND: no via for " + b for b in out["gnd_no_via"]]:
        print("  ", f)


RIP_R = 1.6             # mm round the stuck end of an open net: the router's tracks of other nets inside this circle are taken out
REPAIR = os.path.join(ROOT, "build", "kbd_repair.json")


def split_nets(r, reg):
    return [net for net in sorted(set(reg.pads) | set(reg.tree)) if r.name_of[net] != "GND" and len(r.groups(reg, net)) >= 2]


def repair_rip():
    """Step 1 of a repair round.  Exit code 0: nothing is open; 3: open nets were completed without taking anything
    out; 5: tracks were taken out, step 2 has to route; 4: nothing more can be done."""
    from gen_pcb import OX, OY
    board = pcbnew.LoadBoard(FINAL)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    r, reg, code = make_router(board)
    r.items, r.failed = [], []
    todo = split_nets(r, reg)
    if not todo:
        return 0
    stuck = {}                                      # net name -> [(x, y)] board mm of the ends that could not be reached
    for net in todo:
        _, bad = r.route_net(reg, net)
        for b in bad:
            ref_num = b.split(" ")[0]
            pd = next((q for q in reg.pads.get(net, []) if q["ref"] + "." + q["num"] == ref_num), None)
            if pd is not None:
                stuck.setdefault(r.name_of[net], []).append((pd["cx"] + OX, pd["cy"] + OY))
            else:
                stuck.setdefault(r.name_of[net], [])
    if not stuck:
        r.flush(r.items)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(FINAL, board, True)
        print("repair: %d open nets completed on the board as it was" % len(todo), flush=True)
        return 3
    # what the router drew (not on the prepared board), without the chip's fixed escape: these may be taken out
    old = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(PREPARED).GetTracks()}
    chip = next(f for f in board.GetFootprints() if f.GetReference() == "U201")
    cxy = (ToMM(chip.GetPosition().x), ToMM(chip.GetPosition().y))
    chip_pads = [p_.GetBoundingBox() for p_ in chip.Pads()]

    def fixed(t):
        if t.GetNetname() in ("GND", "VCC5", "VBUS_USB", "XTAL1", "XTAL2"):
            return True
        if t.GetClass() == "PCB_VIA":
            dx, dy = abs(ToMM(t.GetPosition().x) - cxy[0]), abs(ToMM(t.GetPosition().y) - cxy[1])
            return any(abs(max(dx, dy) - d) < 0.03 for d in (FAN_SHORT, FAN_LONG)) and min(dx, dy) < 2.6
        return any(b_.Contains(t.GetStart()) or b_.Contains(t.GetEnd()) for b_ in chip_pads)
    new = [t for t in board.GetTracks() if t.m_Uuid.AsString() not in old and not fixed(t)]
    victims = set()
    for name, ends in stuck.items():
        for ex, ey in ends:
            for t in new:
                if t.GetNetname() == name:
                    continue
                pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
                (ax, ay), (bx, by) = [(ToMM(q.x), ToMM(q.y)) for q in (pts[0], pts[-1])]
                L2 = (bx - ax) ** 2 + (by - ay) ** 2
                u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((ex - ax) * (bx - ax) + (ey - ay) * (by - ay)) / L2))
                if math.hypot(ax + u * (bx - ax) - ex, ay + u * (by - ay) - ey) < RIP_R:
                    victims.add(t.GetNetname())
    done_before = json.load(open(REPAIR, encoding="utf-8")).get("ripped", []) if os.path.exists(REPAIR) else []
    victims -= set(stuck)
    if not victims or sorted(victims) in done_before:
        print("repair: still open and nothing new to take out: %s" % " ".join(sorted(stuck)), flush=True)
        json.dump(sorted(stuck), open(STUCK, "w", encoding="utf-8"))
        return 4
    kill = [t for t in new if t.GetNetname() in victims or t.GetNetname() in stuck]
    json.dump(dict(first=sorted(stuck), then=sorted(victims), ripped=done_before + [sorted(victims)]), open(REPAIR, "w", encoding="utf-8"), indent=1)
    print("repair: open: %s; taking out the router's tracks of %s (%d pieces)" % (" ".join(sorted(stuck)), " ".join(sorted(victims)), len(kill)), flush=True)
    for t in kill:
        board.Remove(t)
    pcbnew.SaveBoard(FINAL, board, True)
    return 5


STUCK = os.path.join(ROOT, "build", "kbd_stuck.json")
REPAIR_ORDERS = 6                           # orders tried for the nets of one repair round (in memory, the best is kept)
CORRIDOR = os.path.join(ROOT, "build", "kbd_corridor.json")
CLEAN = os.path.join(ROOT, "build", "kbd_corridor_board.kicad_pcb")


def movable_tracks(board):
    """The tracks and vias the router drew (not on the prepared board), without the chip's fixed escape and without
    the supply / ground / crystal copper: these may be taken out again."""
    old = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(PREPARED).GetTracks()}
    chip = next(f for f in board.GetFootprints() if f.GetReference() == "U201")
    cxy = (ToMM(chip.GetPosition().x), ToMM(chip.GetPosition().y))
    chip_pads = [p_.GetBoundingBox() for p_ in chip.Pads()]

    def fixed(t):
        if t.GetNetname() in ("GND", "VBUS_USB", "XTAL1", "XTAL2"):
            return True
        if t.GetNetname() == "VCC5":                # the thin links under the chip stay; the router's wide supply tracks may go
            return (ToMM(t.GetWidth(pcbnew.F_Cu)) <= 0.55) if t.GetClass() == "PCB_VIA" else ToMM(t.GetWidth()) <= 0.2
        if t.GetClass() == "PCB_VIA":
            dx, dy = abs(ToMM(t.GetPosition().x) - cxy[0]), abs(ToMM(t.GetPosition().y) - cxy[1])
            return any(abs(max(dx, dy) - d) < 0.03 for d in (FAN_SHORT, FAN_LONG)) and min(dx, dy) < 2.6
        return any(b_.Contains(t.GetStart()) or b_.Contains(t.GetEnd()) for b_ in chip_pads)
    return [t for t in board.GetTracks() if t.m_Uuid.AsString() not in old and not fixed(t)]


def corridor_strip():
    """A copy of the board without the movable tracks of every net that is not stuck."""
    import shutil
    stuck = set(json.load(open(STUCK, encoding="utf-8")))
    board = pcbnew.LoadBoard(FINAL)
    kill = [t for t in movable_tracks(board) if t.GetNetname() not in stuck]
    for t in kill:
        board.Remove(t)
    pcbnew.SaveBoard(CLEAN, board, True)
    shutil.copyfile(os.path.join(ROOT, PRJ + ".kicad_pro"), CLEAN[:-len(".kicad_pcb")] + ".kicad_pro")
    return 0


def corridor_route():
    """Each stuck net routed alone on that copy; where it went is written down (board mm, layer)."""
    from gen_pcb import OX, OY
    stuck = json.load(open(STUCK, encoding="utf-8"))
    board = pcbnew.LoadBoard(CLEAN)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    r, reg, code = make_router(board)
    r.items, r.failed = [], []
    # the tracks that were taken out for this trial are not free: crossing one costs as much as a long detour, so the
    # trial path crosses as few of them as it can (only those are taken out for real afterwards)
    import numpy as np
    import route as R
    G = R.G
    fb = pcbnew.LoadBoard(FINAL)
    for t in movable_tracks(fb):
        if t.GetNetname() in stuck:
            continue
        if t.GetClass() == "PCB_VIA":
            segs, layers, half = [(t.GetPosition(), t.GetPosition())], (0, 2), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
        else:
            segs, layers, half = [(t.GetStart(), t.GetEnd())], ((0 if t.GetLayer() == pcbnew.F_Cu else 2),), ToMM(t.GetWidth()) / 2
        k = R.ceil_((half + 0.15 + 0.075) / G)
        for a_, b_ in segs:
            cells, _ = reg.seg_cells((ToMM(a_.x) - OX, ToMM(a_.y) - OY), (ToMM(b_.x) - OX, ToMM(b_.y) - OY))
            for l in layers:
                for ci, cj in cells:
                    reg.soft[l, max(0, cj - k):cj + k + 1, max(0, ci - k):ci + k + 1] = R.MULTI
    out = {}
    for name in stuck:
        net = code[name]
        before = set(reg.tree.get(net, {}))
        _, bad = r.route_net(reg, net)
        cells = [c for c in reg.tree.get(net, {}) if c not in before]
        out[name] = [(reg.xy(i, j)[0] + OX, reg.xy(i, j)[1] + OY, l) for l, i, j in cells]
        print("repair: %s alone on the board without the others: %s, %d cells" % (name, "complete" if not bad else "still open", len(cells)), flush=True)
    json.dump(out, open(CORRIDOR, "w", encoding="utf-8"))
    return 0 if any(out.values()) else 4


def corridor_rip():
    """The nets whose movable tracks lie in the corridors are taken out, together with the stuck nets' own."""
    corr = json.load(open(CORRIDOR, encoding="utf-8"))
    stuck = set(corr)
    board = pcbnew.LoadBoard(FINAL)
    movable = movable_tracks(board)
    pts = [(x, y, l) for v in corr.values() for x, y, l in v]
    victims = set()
    for t in movable:
        name = t.GetNetname()
        if name in stuck or name in victims:
            continue
        if t.GetClass() == "PCB_VIA":
            segs, layers, half = [(t.GetPosition(), t.GetPosition())], (0, 2), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
        else:
            segs, layers, half = [(t.GetStart(), t.GetEnd())], (0 if t.GetLayer() == pcbnew.F_Cu else 2,), ToMM(t.GetWidth()) / 2
        for a, b in segs:
            (ax, ay), (bx, by) = (ToMM(a.x), ToMM(a.y)), (ToMM(b.x), ToMM(b.y))
            L2 = (bx - ax) ** 2 + (by - ay) ** 2
            for x, y, l in pts:
                if l not in layers and l != 1:
                    continue
                reach = 0.30 if l == 1 else 0.075        # a via of the trial path (layer 1 = where it changes layer) needs more room
                u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
                if math.hypot(ax + u * (bx - ax) - x, ay + u * (by - ay) - y) < half + reach + 0.15 + 0.05:
                    victims.add(name)
                    break
    if not victims:
        print("repair: nothing of the others lies in the way of %s" % " ".join(sorted(stuck)), flush=True)
        return 4
    kill = [t for t in movable if t.GetNetname() in victims or t.GetNetname() in stuck]
    json.dump(dict(first=sorted(stuck), then=sorted(victims), ripped=[]), open(REPAIR, "w", encoding="utf-8"), indent=1)
    print("repair: in the way of %s: %s - taken out (%d pieces), the stuck net goes first" % (" ".join(sorted(stuck)), " ".join(sorted(victims)), len(kill)), flush=True)
    for t in kill:
        board.Remove(t)
    pcbnew.SaveBoard(FINAL, board, True)
    return 5


def repair_route():
    """Step 2 of a repair round: the nets that were open first, then the ones that were taken out, then whatever else is open."""
    plan = json.load(open(REPAIR, encoding="utf-8"))
    board = pcbnew.LoadBoard(FINAL)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    r, reg, code = make_router(board)
    r.items, r.failed = [], []
    todo = split_nets(r, reg)
    first = [code[n] for n in plan["first"] if code.get(n) in todo]
    then = [code[n] for n in plan["then"] if code.get(n) in todo]
    rest = [n for n in todo if n not in first and n not in then]
    # several orders, tried in memory: the first that leaves nothing open is kept, else the one that leaves least
    import random
    snap_D = {k: D.copy() for k, D in reg.D.items()}
    snap = (reg.novia.copy(), list(reg.uf), {n: dict(v) for n, v in reg.tree.items()}, {n: dict(v) for n, v in reg.exact.items()},
            len(r.items), len(r.failed))
    rnd = random.Random(1)
    best = None
    for attempt in range(REPAIR_ORDERS):
        if attempt:
            for k, D in reg.D.items():
                D[...] = snap_D[k]
            reg.novia[...] = snap[0]
            reg.uf[:] = snap[1]
            reg.tree.clear()
            reg.tree.update({n: dict(v) for n, v in snap[2].items()})
            reg.exact.clear()
            reg.exact.update({n: dict(v) for n, v in snap[3].items()})
            del r.items[snap[4]:]
            del r.failed[snap[5]:]
        f_, t_ = list(first), list(then)
        if attempt:
            rnd.shuffle(f_)
            rnd.shuffle(t_)
        if attempt % 2 == 1:
            f_, t_ = t_, f_                         # (every other try: the ones taken out go first)
        left = []
        for net in f_ + t_ + rest:
            _, bad = r.route_net(reg, net)
            if bad:
                left.append(r.name_of[net])
        if best is None or len(left) < len(best[0]):
            best = (left, attempt, list(r.items[snap[4]:]))
        if not left:
            break
    if best[1] != attempt:                          # the best try was an earlier one: put its copper back
        del r.items[snap[4]:]
        r.items.extend(best[2])
    left = best[0]
    print("repair: %d order(s) tried, the best (no. %d) leaves %d open" % (attempt + 1, best[1] + 1, len(left)), flush=True)
    r.flush(r.items)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    n_open = board.GetConnectivity().GetUnconnectedCount(True)
    pcbnew.SaveBoard(FINAL, board, True)
    print("repair: routed again; still open: %s; open connections on the board now: %d" % (" ".join(left) or "-", n_open), flush=True)
    return 0


def open_count():
    board = pcbnew.LoadBoard(FINAL)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(True)


def stage_repair():
    """Rip-up and retry, each step in a process of its own.  A round that leaves more open than before is undone."""
    import shutil
    if "--rip" in sys.argv:
        raise SystemExit(repair_rip())
    if "--reroute" in sys.argv:
        raise SystemExit(repair_route())
    if "--count" in sys.argv:
        raise SystemExit(min(250, open_count()))
    for flag, fn in (("--corridor-strip", corridor_strip), ("--corridor-route", corridor_route), ("--corridor-rip", corridor_rip)):
        if flag in sys.argv:
            raise SystemExit(fn())
    if os.path.exists(REPAIR):
        os.remove(REPAIR)
    me = [sys.executable, os.path.abspath(__file__), "--stage", "repair"]
    tried = set()
    for f_ in (STUCK, CORRIDOR):
        if os.path.exists(f_):
            os.remove(f_)
    best = subprocess.run(me + ["--count"], stderr=subprocess.DEVNULL).returncode
    for n in range(int(os.environ.get("CP_REPAIR_ROUNDS", "6"))):
        if best == 0:
            break
        backup = FINAL + ".before_repair"
        shutil.copyfile(FINAL, backup)
        rc = subprocess.run(me + ["--rip"], stderr=subprocess.DEVNULL).returncode
        if rc == 4 and os.path.exists(STUCK):
            key = tuple(json.load(open(STUCK, encoding="utf-8")))
            if key not in tried:
                tried.add(key)
                ok = all(subprocess.run(me + [f], stderr=subprocess.DEVNULL).returncode == 0 for f in ("--corridor-strip", "--corridor-route"))
                rc = subprocess.run(me + ["--corridor-rip"], stderr=subprocess.DEVNULL).returncode if ok else 4
        if rc in (0, 4):
            break
        if rc == 5:
            subprocess.run(me + ["--reroute"], stderr=subprocess.DEVNULL)
        elif rc != 3:
            raise SystemExit("repair stage failed")
        now = subprocess.run(me + ["--count"], stderr=subprocess.DEVNULL).returncode
        if now > best:
            shutil.copyfile(backup, FINAL)
            print("repair: round %d left %d open connections (before: %d) - undone" % (n + 1, now, best), flush=True)
        else:
            best = now
            print("repair: round %d: %d open connections" % (n + 1, now), flush=True)
    if os.path.exists(FINAL + ".before_repair"):
        os.remove(FINAL + ".before_repair")
    print("repair: %d open connections left (ground pads off the pours are the ground stage's business)" % best, flush=True)


def ground_round():
    """One round of ground stitching on the routed board.  Returns (ground pads not on the main ground before, joined now)."""
    import numpy as np
    import route as R
    from gen_pcb import OX, OY
    board = pcbnew.LoadBoard(FINAL)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    clusters, seen = [], set()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            u = pad.m_Uuid.AsString()
            if pad.GetNetname() != "GND" or u in seen:
                continue
            items = list(conn.GetConnectedItems(pad, 0))
            ids = {x.m_Uuid.AsString() for x in items} | {u}
            seen |= ids
            clusters.append((ids, items + [pad]))
    for t in board.GetTracks():                     # (a piece of pour that hangs on vias only)
        u = t.m_Uuid.AsString()
        if t.GetNetname() != "GND" or t.GetClass() != "PCB_VIA" or u in seen:
            continue
        items = list(conn.GetConnectedItems(t, 0))
        ids = {x.m_Uuid.AsString() for x in items} | {u}
        seen |= ids
        clusters.append((ids, items + [t]))
    main_ids, main_items = max(clusters, key=lambda c: len(c[0]))
    lost = [c for c in clusters if c[0] is not main_ids]
    if not lost:
        return 0, 0
    r, reg, code = make_router(board)
    G = R.G
    gnd = code["GND"]
    r.items, r.failed = [], []
    # the pour of the main ground, well inside its edge, is where a lost pad may land
    pts = {0: [], 2: []}
    for it in main_items:
        if it.GetClass() == "PCB_VIA":
            for l in (0, 2):
                pts[l].append(it.GetPosition())
        elif it.GetClass() == "PAD":
            for l, layer in ((0, pcbnew.F_Cu), (2, pcbnew.B_Cu)):
                if it.IsOnLayer(layer):
                    pts[l].append(it.GetPosition())
    zn = reg.node()
    xs = reg.x0 + np.arange(reg.nx) * G
    for z in board.Zones():
        if z.GetNetname() != "GND" or z.GetIsRuleArea():
            continue
        l = 0 if z.GetLayer() == pcbnew.F_Cu else 2
        fill = z.GetFilledPolysList(z.GetLayer())
        mask = np.zeros((reg.ny, reg.nx), bool)
        for k in range(fill.OutlineCount()):
            o = fill.Outline(k)
            bb = o.BBox()
            if (ToMM(bb.GetRight()) - OX < reg.x0 or ToMM(bb.GetLeft()) - OX > reg.x1 or
                    ToMM(bb.GetBottom()) - OY < reg.y0 or ToMM(bb.GetTop()) - OY > reg.y1):
                continue
            if not any(bb.Contains(q) and o.PointInside(q) for q in pts[l]):
                continue                            # (a piece of pour that hangs on a lost pad only)
            rings = [o] + [fill.Hole(k, h) for h in range(fill.HoleCount(k))]
            edges = []
            for ring in rings:
                pp = [(ToMM(ring.CPoint(i).x) - OX, ToMM(ring.CPoint(i).y) - OY) for i in range(ring.PointCount())]
                edges += list(zip(pp, pp[1:] + pp[:1]))
            edges = [e for e in edges if max(e[0][1], e[1][1]) >= reg.y0 and min(e[0][1], e[1][1]) <= reg.y1]
            for j in range(reg.ny):
                y = reg.y0 + j * G + 1e-6
                xc = sorted(ax + (y - ay) * (bx - ax) / (by - ay) for (ax, ay), (bx, by) in edges if (ay > y) != (by > y))
                for a, b in zip(xc[0::2], xc[1::2]):
                    mask[j, (xs >= a) & (xs <= b)] = True
        inner = ~R.dilate(~mask, R.ceil_(0.4 / G))
        js, is_ = np.nonzero(inner[::4, ::4])
        reg.assign(gnd, [(l, int(i) * 4, int(j) * 4) for i, j in zip(is_, js)], zn)
    # ... and so are the pads and vias of the main ground, wherever they are (a pour may be too narrow to reach)
    for pd in reg.pads.get(gnd, []):
        if pd["pad"].m_Uuid.AsString() in main_ids:
            reg.assign(gnd, list(pd["cells"]), zn)
    for it in main_items:
        if it.GetClass() == "PCB_VIA":
            i, j = int(round((ToMM(it.GetPosition().x) - OX - reg.x0) / G)), int(round((ToMM(it.GetPosition().y) - OY - reg.y0) / G))
            if 0 <= i < reg.nx and 0 <= j < reg.ny:
                reg.assign(gnd, [(0, i, j), (2, i, j)], zn)
    joined = 0
    names = []
    for ids, items in lost:
        pads = [pd for pd in reg.pads.get(gnd, []) if pd["pad"].m_Uuid.AsString() in ids]
        if not pads:                                # no pad: start from its vias
            for it in items:
                if it.GetClass() == "PCB_VIA":
                    i, j = int(round((ToMM(it.GetPosition().x) - OX - reg.x0) / G)), int(round((ToMM(it.GetPosition().y) - OY - reg.y0) / G))
                    if 0 <= i < reg.nx and 0 <= j < reg.ny:
                        nd = reg.tree.get(gnd, {}).get((0, i, j), reg.node())
                        pads.append(dict(ref="via", num="%.1f/%.1f" % (ToMM(it.GetPosition().x), ToMM(it.GetPosition().y)), node=nd, area=0.3,
                                         cells=[(0, i, j), (2, i, j)], cx=reg.xy(i, j)[0], cy=reg.xy(i, j)[1], minw=0.3))
        if not pads:
            continue                                # (outside the window)
        for pd in pads[1:]:
            reg.union(pd["node"], pads[0]["node"])
        ok = False
        rc = r.rc_of[gnd]
        root = reg.find(zn)
        for pd in sorted(pads, key=lambda q: -q["area"]):
            i0, j0, W, H, okm, vok = r.window(reg, gnd, rc, (pd["cx"] - 10, pd["cy"] - 10, pd["cx"] + 10, pd["cy"] + 10), 0)
            goal = np.zeros((3, H, W), bool)
            for c, nd in reg.tree.get(gnd, {}).items():
                if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H and reg.find(nd) == root:
                    goal[c[0], c[2] - j0, c[1] - i0] = True
            goal &= okm
            starts = [(c[0] * H + (c[2] - j0)) * W + (c[1] - i0) for c in pd["cells"]
                      if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H and okm[c[0], c[2] - j0, c[1] - i0]]
            res = None
            if starts and goal.any():
                gl, gy, gx = np.nonzero(goal)
                res, _ = R.search([okm[l].tobytes() for l in range(3)], vok.tobytes(), [goal[l].tobytes() for l in range(3)], W, H, starts,
                                  (int(gx.min()), int(gy.min()), int(gx.max()), int(gy.max())), max_exp=600000, penb=r.pen)
            if res:
                cells = r.commit(reg, gnd, rc, res, W, H, i0, j0)
                r.stub(reg, gnd, rc, cells[0], pd)
                ok = True
                break
            if os.environ.get("CP_VERBOSE"):
                print("   %s.%s: %d of its %d cells free to start from, %d pour cells within 10 mm" % (pd["ref"], pd["num"], len(starts), len(pd["cells"]), int(goal.sum())), flush=True)
        joined += ok
        names.append("%s.%s%s" % (pads[0]["ref"], pads[0]["num"], "" if ok else " (NOT joined)"))
    r.flush(r.items)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(FINAL, board, True)
    print("ground: %d pieces of ground were off the pours (%s); %d joined with a track or via" % (len(lost), ", ".join(names), joined), flush=True)
    return len(lost), joined


def tidy_vias():
    """Vias that the router drew but that join nothing on one of the two layers (a chip escape whose line stayed on the
    same layer): taken out when every track at the via is on one layer - the tracks still meet there."""
    board = pcbnew.LoadBoard(FINAL)
    old = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(PREPARED).GetTracks()}
    ends = {}
    for t in board.GetTracks():
        if t.GetClass() != "PCB_VIA":
            for e in (t.GetStart(), t.GetEnd()):
                ends.setdefault((t.GetNetname(), e.x, e.y), set()).add(t.GetLayer())
    pads = {(p.GetNetname(), p.GetPosition().x, p.GetPosition().y) for f in board.GetFootprints() for p in f.Pads()}
    kill = []
    for v in board.GetTracks():
        if v.GetClass() != "PCB_VIA" or v.m_Uuid.AsString() in old or v.GetNetname() == "GND":
            continue
        key = (v.GetNetname(), v.GetPosition().x, v.GetPosition().y)
        layers = ends.get(key, set())
        if len(layers) == 1 and key not in pads:
            kill.append(v)
    for v in kill:
        board.Remove(v)
    pcbnew.SaveBoard(FINAL, board, True)
    print("tidy: %d vias that joined nothing on one layer taken out" % len(kill), flush=True)


def stage_ground():
    """Ground stitching, each round in a process of its own (the pours are refilled in between); then the tidy-up."""
    if "--tidy" in sys.argv:
        tidy_vias()
        return
    if "--round" in sys.argv:
        lost, joined = ground_round()
        raise SystemExit(0 if lost == 0 else 3 if joined else 4)
    for n in range(4):
        rc = subprocess.run([sys.executable, os.path.abspath(__file__), "--stage", "ground", "--round"]).returncode
        if rc == 0:
            print("ground: every ground pad is on the pours")
            break
        if rc == 4:
            print("ground: some ground pads could not be joined (see above)")
            break
        if rc != 3:
            raise SystemExit("ground stage failed")
    # (the tidy-up of one-sided vias, --tidy, is not run: judged by exact track ends it took out vias that do join the
    # two layers - a track can end anywhere inside a via)


def main():
    if "--stage" in sys.argv:
        {"import": stage_import, "prepare": stage_prepare, "route": stage_route, "repair": stage_repair,
         "ground": stage_ground}[sys.argv[sys.argv.index("--stage") + 1]]()
        return
    for st in ("import", "prepare", "route", "repair", "ground"):       # each in a process of its own (see the note in stage_prepare)
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--stage", st], stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            raise SystemExit("stage %s failed (run it alone to see why)" % st)


if __name__ == "__main__":
    main()

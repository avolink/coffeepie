#!/usr/bin/env python
"""The two-layer module boards of the Commander: battery (commander_battery), numpad (commander_numpad), touchpad
(commander_touchpad) and the tray carrier for two Framework input modules (commander_tray).  Run with the Python that comes with KiCad, CP_ROOT = the project folder:

    small_board.py [--stage place|route|all]           (default all)

  place   outline (sized to the module in the chassis model COMMANDER_Z3E.skp), footprints and nets from the netlist
          source, the large parts where SPEC puts them, the small ones packed next to the part they connect to;
          on the touchpad the electrode pattern (diamonds on the top copper, bridges on the bottom) and its feed lines
                                                                                 -> build/<project>_placed.kicad_pcb
  route   everything but ground with tools/route.py (two layers, the classes of the project), a ground via beside every
          ground pad, ground pours on both faces (outside the touch area)                -> <project>.kicad_pcb

Board coordinates are mm from the board's top-left corner (KiCad's view of the top face).  In the chassis model the board
lies top face up with x along the chassis' X (rear -> front) and y AGAINST its Y: a point (x, y) of the board is at
chassis (X0 + x, Y0 + h - y), with X0 / Y0 in SPEC (the module's corner of smallest X and Y) - a plain translation of
the boards' 3D export (tools/glb_to_dae.py writes Y = -y).
"""
import fnmatch
import json
import math
import os
import re
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpmodel                                  # noqa: E402
import gen_pcb as GP                            # noqa: E402  (footprint loading, poses, page offset)
from gen_schematic import uid                   # noqa: E402

ROOT, PRJ, V = cpmodel.ROOT, cpmodel.PRJ, cpmodel.VARIANT
OX, OY, P = GP.OX, GP.OY, GP.P
PLACED = os.path.join(ROOT, "build", PRJ + "_placed.kicad_pcb")
FINAL = os.path.join(ROOT, PRJ + ".kicad_pcb")

# ---- the touchpad's sensing area and electrode pattern ----
TP_AREA = (0.6, 0.6, 112.0, 62.6)       # x0, y0, x1, y1: 15 Tx columns of 7.43 mm, 10 Rx rows of 6.20 mm
# (the model's touch surface is 117.8 mm wide; 5.8 mm of it went to the electronics strip, which needs 18 mm)
TP_NTX, TP_NRX = 15, 10
TP_GAP = 0.30                           # copper-free gap between a Tx and an Rx diamond
TP_NECK = 0.40                          # width of the top-copper neck that joins two Tx diamonds
TP_BRIDGE_D = 1.55                      # the two vias of an Rx bridge sit this far either side of the crossing
TP_LANE_X = 116.0                       # where the first Tx feed line hands over to the router (then every 0.9 mm)
TP_RX_LANE0 = 113.25                    # the Rx feed lanes: x of the lowest row's lane (0.3 mm pitch to the right) ...
TP_RX_END = 47.0                        # ... and where the lowest row's lane ends (the others 0.6 mm higher each)
KEYS_X = [19.27, 36.29, 53.28, 70.27, 87.27, 104.27]     # numpad key centres, from the chassis model (NUMPAD_MODULE)
KEYS_Y = [60.42, 42.96, 25.49, 7.49]      # row 1 = nearest the touchpad (chassis Y 259.0)

# SPEC: size, corner radius, mounting holes, where it sits in the chassis model (X0, Y0, z of the board's bottom face),
# the parts placed by hand: ref -> (x, y, rotation, face) with x, y the courtyard centre; or ("edge", side, along,
# overhang) for a connector whose mouth faces that board edge; keep-outs for the packer (x0, y0, x1, y1).
SPEC = {
    "batt": dict(
        w=48.0, h=88.8, r=1.5, holes=[(3.2, 3.2), (44.8, 3.2), (44.8, 85.6), (3.2, 85.6)], X0=93.3, Y0=77.3, Z0=8.1,
        # top band: the port and the 5 V converters; middle: the microcontroller beside the port, LEDs and button on
        # the right edge; bottom: the cells' path (connector, fuse, polarity FET, shunt, sense amplifier)
        fixed={
            "J3": ("edge", "bottom", 34.0, 0.0),        # USB-C to the mainboard's J40: board y = 88.8 is chassis Y 77.3
            "U2": (34.0, 76.3, 0, "F"),
            "U5": (16.0, 79.8, 0, "F"), "L2": (24.0, 79.8, 0, "F"),
            "U4": (12.0, 67.8, 0, "F"), "L1": (5.5, 67.8, 0, "F"), "D1": (12.0, 60.8, 0, "F"),
            "U1": (31.0, 56.8, 0, "F"),
            "D50": (44.8, 62.8, 90, "F"), "D51": (44.8, 58.8, 90, "F"), "D52": (44.8, 54.8, 90, "F"), "SW1": (42.0, 44.8, 0, "F"),
            "U6": (24.0, 40.8, 0, "F"), "U7": (31.0, 40.8, 0, "F"),
            "J1": (4.6, 26.8, 90, "F"), "J2": (4.6, 8.8, 90, "F"),
            "F1": (13.0, 36.8, 90, "F"), "Q1": (13.0, 43.8, 0, "F"), "R2": (13.0, 20.8, 90, "F"),
            "U3": (21.0, 20.8, 0, "F"),
        },
        keepout=[]),
    # numpad and touchpad, 2026-11-17: Framework B-size outline (131.02 x 67.95) and seat (rear edge at chassis X 8.95,
    # under the tray's rear rail), with Framework's contact pads J40 on the underside (7.0 mm from the front edge,
    # 16.96 mm from the left edge seen from the front: board (124.02, 50.99)), so they drop into the tray like a
    # Framework module.  Y0 = the tray pogo array's centre (closed drawer) - 16.96.  The module needs 1.5 mm feet under
    # its body (Framework's contact zone is 1.5 mm above the floor) and a thin steel plate for the tray's magnets.
    "numpad": dict(
        w=131.02, h=67.95, r=1.5, holes=[(3.0, 3.0), (3.0, 64.95), (128.02, 3.0), (128.02, 64.95)], X0=8.95, Y0=251.40, Z0=8.0,
        # J1 since 2026-11-18: the mid-mount HCTL receptacle, centred on the front edge, in a notch (usbc_mid_fp.py)
        fixed=dict({"J1": ("edge", "right", 67.95 / 2, 0.0), "U1": (119.5, 16.0, 0, "F"), "D1": (126.0, 60.0, 0, "F"),
                    "J40": (124.02, 50.99, 0, "F")},
                   **{"SW_%d_%d" % (r + 1, c + 1): (KEYS_X[c], KEYS_Y[r], 0, "F") for r in range(4) for c in range(6)}),
        notch=[(67.95 / 2, 4.75, 6.60, 0.5)],
        keepout=[]),
    "touch": dict(
        w=131.02, h=67.95, r=1.5, holes=[(129.0, 2.0), (129.0, 65.95)], X0=8.95, Y0=179.95, Z0=9.24,
        # strip, top to bottom: button, regulator, microcontroller, the USB-C (since 2026-11-18 the mid-mount HCTL
        # receptacle, centred on the front edge in a notch), then the IQS550 right above the Tx lanes (turned 180 deg:
        # its Tx pins face down to them, its Rx pins face the Rx lanes' ends on the left / top)
        fixed={"J1": ("edge", "right", 67.95 / 2, 0.0), "U1": (123.0, 45.9, 0, "F"), "U3": (126.0, 10.5, 0, "F"),
               "SW1": (124.5, 4.6, 0, "F"), "U4": (122.8, 55.6, 180, "F"), "J40": (124.02, 50.99, 0, "F")},
        notch=[(67.95 / 2, 4.75, 6.60, 0.5)],
        # (2026-11-18: U4 tried 1.7 mm lower, off J40's bottom-copper pads: 12 nets open instead of 10 - kept here)
        # parts stay out of the touch area and off the Rx feed lanes (bottom copper, x 113.25-115.95, y 3-47)
        keepout=[(-1.0, -1.0, 113.0, 69.0), (-1.0, -1.0, 117.8, 48.0), (115.0, 61.5, 124.0, 69.0)]),
    # the tray carrier: an 18 mm strip, 0.8 mm thick, in a channel of the tray floor under the two module bays'
    # contact edge, which is the bays' FRONT end (the modules lie as in the laptop: contacts toward the user, chassis
    # X 129.9-143.9); parts only in the 12 mm under the contact edge (x 6-18), tracks in the 6 mm under the modules' body
    # (x 0-6).  The model's tray is pulled out (TRAY at Y 322.3-491.9); the strip is placed for that position.
    # 2026-11-17: 12 mm longer at the inner end (154.2 -> 166.2 mm, chassis Y 310.3 instead of 322.3; the outer end and
    # every part but the USB-C stay where they were): in the model the USB-C hit the tray's dust barrier, now it sits
    # past it.  Only J1 moved (it follows the inner edge); positions here are measured from the outer end (y = 0).
    # Framework B-size modules (67.95 x 131.02 x 3.75 mm) in the bays at chassis Y 335.0-402.95 (bay 1) and
    # 406.45-474.4 (bay 2); contact block 16.91 mm from the module's left edge seen from the front and 7.0 mm from its
    # contact edge (X 136.9); magnets (5 x 2 mm discs, glued into the holes, resting on the channel floor) under both
    # halves of each module's steel contact plate, 7.9 mm either side of the half's centre; two M2 screws hold the strip.
    # 2026-11-17 (later): the strip sits 3.93 mm further back (X0 123.0 -> 119.07; board positions unchanged).  A
    # Framework module rests with its rear lip under the tray's rear rail (module X 8.95-139.97; the floor ends at the
    # front ramp, X 141.5), so its contact block is at X 132.97, not 136.9 (Framework's STEP / drawing: 7.0 mm from the
    # contact edge, 16.96 mm from the left edge).  Checked in COMMANDER_Z3E.skp against the module models.
    "tray": dict(
        w=18.0, h=166.2, r=1.0, t=0.8, X0=119.07, Y0=310.3, Z0=7.5,
        holes=[(13.9, y_, 2.6) for y_ in (132.49, 116.69, 98.66, 82.86, 61.04, 45.24, 27.21, 11.41)]
              + [(8.7, 71.8, 1.1), (13.9, 2.0, 1.1)],
        # the free stretches between magnets, from the inner end: USB-C and its fuse / ESD (y 135-146), bay 1's
        # switches and presence detector (101-114), the hub and its crystal (85-96), the 3.3 V regulator (73-80),
        # bay 2's detector (64-70), bay 2's switches (30-42).  Contacts turned 90 deg: pin 1 on the row nearer the
        # module's edge, on the module's left (chassis +X / -Y)
        fixed={"J1": ("edge", "bottom", 12.6, 0.0), "J2": (13.9, 124.59, 90, "F"), "J3": (13.9, 53.14, 90, "F"),
               "U4": (15.1, 110.9, 0, "F"), "U5": (15.1, 104.6, 0, "F"), "U6": (10.1, 111.2, 0, "F"), "Q1": (10.1, 104.8, 0, "F"),
               # U1 turned 270 deg: XI / XO face the crystal above it, the USB pins face bay 1 and the USB-C
               "U1": (14.5, 91.6, 270, "F"), "Y1": (14.5, 87.3, 0, "F"),
               "U3": (14.1, 76.8, 0, "F"), "Q2": (14.1, 66.6, 0, "F"),
               "U7": (15.1, 39.2, 0, "F"), "U8": (15.1, 32.9, 0, "F"), "U9": (10.1, 39.2, 0, "F"),
               "U2": (15.1, 140.6, 0, "F"), "F1": (9.5, 140.6, 90, "F")},
        # x < 6 (chassis X < 129) lies under the modules' body, which rests on the tray floor: tracks only, no parts;
        # (passives keep 1 mm from the magnet holes and the edges, so their pads can be reached)
        keepout=[(-1.0, -1.0, 6.0, 167.2)], gap=0.45, hole_gap=1.0, edge_gap=0.9,
        # the two supplies run the strip's length on the bottom face, in the lane under the modules' body
        trunks=[("VCC5", "B", 1.4, 33.0, 141.0, 0.5), ("VCC3V3", "B", 3.2, 33.0, 106.0, 0.5)]),
    # the front battery bar's BMS board: flat on the floor plate of the bar's LEFT end cap (chassis Y 2.2-32.2), in front
    # of the cells (they start at Y 23.6).  Board X 160.6-236.4, Y 3.6-22.0, bottom face at z 5.1 (floor 3.6), top
    # face at z 6.7; the cap leaves about 8.5 mm above it (less under the grub screw at X 152-165, Y 6-9: 5 mm).
    # Board y = 0 is the rear edge (toward the cells): the cell-contact board stands there on joint J3; y = 18.4 is the
    # bar's left end face (wall Y 2.2-3.2), where the USB-C port, the button and the LEDs are.
    # (Raised 1.5 mm on spacers at its two screws: that clears the floor's step, so the board spans X 160.6-236.4, and
    # leaves 1.5 mm under it for passives, SOT-23 and SOD-123 parts on the bottom face - one face was not enough.)
    "bar": dict(
        w=75.8, h=18.4, r=1.0, t=1.6, X0=160.6, Y0=3.6, Z0=5.1, bottom=True, layers=4,      # F, In1 GND, In2, B
        keepout_b=[(70.0, -1.0, 77.0, 19.4)],                  # (under the board: no parts over the floor step)
        holes=[(2.4, 9.5, 1.1), (73.4, 15.6, 1.1)],             # M2 self-tapping screws into the cap's floor plate
        fixed={"J3": (36.835, 1.6, 0, "F"),
               "J1": ("edge", "bottom", 42.0, 1.2),            # mouth 0.2 mm inside the end face
               "U2": (42.0, 7.6, 0, "F"),
               "J4": (10.0, 6.4, 0, "F"),                      # dock harness, toward the bar's rear face (terminal side)
               "U1": (22.0, 11.2, 0, "F"),
               "U5": (33.5, 15.4, 0, "F"), "L2": (33.5, 9.4, 0, "F"),
               "U4": (52.0, 13.6, 0, "F"), "L1": (52.0, 8.0, 0, "F"), "D1": (57.6, 10.6, 90, "F"),
               "J5": (64.4, 7.6, 90, "F"),                     # solar panel lead
               "SW1": (60.0, 16.9, 0, "F"),
               "D50": (64.6, 17.5, 0, "F"), "D51": (67.7, 17.5, 0, "F"), "D52": (70.8, 17.5, 0, "F")},
        keepout=[], gap=0.45, hole_gap=0.4, edge_gap=0.4),
    # the cell-contact board: stands upright on the BMS board's rear edge (chassis Y 21.0-22.0, its face toward the
    # cells at Y 22.0; cells from Y 23.6, pushed forward by the rear springs), X 160.6-236.4, z 6.7-15.3.  Board x
    # along chassis X, board y DOWN from its top edge (y = 8.6 = the castellated bottom edge on the BMS board).  The
    # lane pads sit on the cells' axes (the extrusion tilts them: z 11.45 at lane 1 to 9.96 at lane 6).  No copper
    # pour on the face toward the cells: a cell can with a damaged wrapper must not find ground there.  With board x
    # along +X (the joint must match the BMS board), the F face looks FORWARD (-Y, at the BMS board) and the B face at
    # the cells: so the lane pads and the thermistors are on B, the ground pour on F only.
    "barcon": dict(
        w=75.8, h=8.6, r=0.5, t=1.0, X0=160.6, Y0=21.0, Z0=6.7, holes=[],
        fixed=dict({"J1": (36.835, 8.6, 0, "F"),
                    "R1": (13.9, 7.4, 90, "B"), "R2": (39.9, 7.4, 90, "B"), "R3": (65.9, 7.4, 90, "B")},
                   **{"BT%d" % (k + 1): (x_, y_, 0, "B") for k, (x_, y_) in enumerate(
                       [(5.17, 3.85), (18.16, 4.12), (31.16, 4.40), (44.16, 4.79), (57.16, 5.06), (70.16, 5.34)])}),
        keepout=[], pours="F"),
}[V]


# --------------------------------------------------------------------------------------------- placement helpers
def court(fp):
    return GP.court(fp)


def overlaps(a, b, m=0.0):
    return not (a[2] + m <= b[0] or b[2] + m <= a[0] or a[3] + m <= b[1] or b[3] + m <= a[1])


def put(fp, x, y, rot, face):
    GP.set_pose(fp, 0, 0, rot, face == "B")
    GP.centre_on(fp, x, y)


def edge_mount(fp, side, along, overhang):
    """Connector with its mouth on a board edge: 'top' (y = 0), 'bottom', 'left' (x = 0), 'right'."""
    d = {"top": (0, -1), "bottom": (0, 1), "left": (-1, 0), "right": (1, 0)}[side]
    GP.set_pose(fp, 0, 0)
    GP.face_towards(fp, *d)
    if d[0]:
        GP.centre_on(fp, 0, along)
        c = court(fp)
        dx = (SPEC["w"] + overhang) - c[2] if d[0] > 0 else -overhang - c[0]
        fp.SetPosition(VECTOR2I(fp.GetPosition().x + FromMM(dx), fp.GetPosition().y))
    else:
        GP.centre_on(fp, along, 0)
        c = court(fp)
        dy = (SPEC["h"] + overhang) - c[3] if d[1] > 0 else -overhang - c[1]
        fp.SetPosition(VECTOR2I(fp.GetPosition().x, fp.GetPosition().y + FromMM(dy)))


def pad_xy(pad):
    return ToMM(pad.GetPosition().x) - OX, ToMM(pad.GetPosition().y) - OY


def outline(board):
    w, h, r = SPEC["w"], SPEC["h"], SPEC["r"]

    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a))
        s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FromMM(0.1))
        board.Add(s)

    def arc(c, a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        k = math.sqrt(0.5)
        mid = (c[0] + ((a[0] + b[0]) / 2 - c[0]) / math.hypot((a[0] + b[0]) / 2 - c[0], (a[1] + b[1]) / 2 - c[1]) * r,
               c[1] + ((a[1] + b[1]) / 2 - c[1]) / math.hypot((a[0] + b[0]) / 2 - c[0], (a[1] + b[1]) / 2 - c[1]) * r)
        del k
        s.SetArcGeometry(P(*a), P(*mid), P(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FromMM(0.1))
        board.Add(s)

    def arc3(a, m, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(P(*a), P(*m), P(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FromMM(0.1))
        board.Add(s)

    seg((r, 0), (w - r, 0))
    arc((w - r, r), (w - r, 0), (w, r))
    # the right edge, with the notches of mid-mount connectors (SPEC "notch": (along, half width, depth, inner corner
    # radius), walls square to the edge, rounded inner corners as the router leaves them)
    y = r
    k = 1 - math.sqrt(0.5)
    for (a, hw, d, rr) in sorted(SPEC.get("notch", [])):
        seg((w, y), (w, a - hw))
        seg((w, a - hw), (w - d + rr, a - hw))
        arc3((w - d + rr, a - hw), (w - d + rr * k, a - hw + rr * k), (w - d, a - hw + rr))
        seg((w - d, a - hw + rr), (w - d, a + hw - rr))
        arc3((w - d, a + hw - rr), (w - d + rr * k, a + hw - rr * k), (w - d + rr, a + hw))
        seg((w - d + rr, a + hw), (w, a + hw))
        y = a + hw
    seg((w, y), (w, h - r))
    arc((w - r, h - r), (w, h - r), (w - r, h))
    seg((w - r, h), (r, h))
    arc((r, h - r), (r, h), (0, h - r))
    seg((0, h - r), (0, r))
    arc((r, r), (0, r), (r, 0))
    for hole in SPEC["holes"]:                     # M2.5 clearance holes (or (x, y, radius)), non-plated (part of the outline)
        x, y, hr = hole if len(hole) == 3 else (hole[0], hole[1], 1.35)
        c = pcbnew.PCB_SHAPE(board)
        c.SetShape(pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(P(x, y))
        c.SetEnd(P(x + hr, y))
        c.SetLayer(pcbnew.Edge_Cuts)
        c.SetWidth(FromMM(0.1))
        board.Add(c)


def note(board, txt, x, y, size=1.0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetPosition(P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    if layer in (pcbnew.B_SilkS, pcbnew.B_Fab):
        t.SetMirrored(True)
    board.Add(t)


# --------------------------------------------------------------------------------------------- touchpad electrodes
def poly(board, pts, net, layer=pcbnew.F_Cu):
    """One electrode diamond: a copper zone of its own (KiCad's connectivity joins tracks and vias to zones, not to
    filled graphic shapes), kept whole (no island removal), above the ground pours in priority."""
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(5)
    z.SetLocalClearance(FromMM(0.15))
    z.SetMinThickness(FromMM(0.15))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(FromMM(OX + x), FromMM(OY + y))
    board.Add(z)


def track(board, a, b, w, net, layer):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b))
    t.SetWidth(FromMM(w))
    t.SetLayer(layer)
    t.SetNet(net)
    board.Add(t)


def via(board, xy, net, d=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetPosition(P(*xy))
    v.SetDrill(FromMM(drill))
    try:
        v.SetWidth(pcbnew.F_Cu, FromMM(d))
    except TypeError:
        v.SetWidth(FromMM(d))
    v.SetNet(net)
    board.Add(v)


def clip_poly(pts, x0, y0, x1, y1):
    """Sutherland-Hodgman clip of a convex polygon to a rectangle."""
    def clip(ps, inside, cut):
        out = []
        for i in range(len(ps)):
            a, b = ps[i - 1], ps[i]
            ia, ib = inside(a), inside(b)
            if ib:
                if not ia:
                    out.append(cut(a, b))
                out.append(b)
            elif ia:
                out.append(cut(a, b))
        return out

    def cx(v):
        return lambda a, b: (v, a[1] + (b[1] - a[1]) * (v - a[0]) / (b[0] - a[0]))

    def cy(v):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (v - a[1]) / (b[1] - a[1]), v)
    for inside, cut in ((lambda p: p[0] >= x0, cx(x0)), (lambda p: p[0] <= x1, cx(x1)),
                        (lambda p: p[1] >= y0, cy(y0)), (lambda p: p[1] <= y1, cy(y1))):
        pts = clip(pts, inside, cut)
        if not pts:
            return []
    return pts


def electrodes(board, nets):
    """Diamond pattern: Tx diamonds centred on (column centre, row boundary), Rx diamonds on (column boundary, row
    centre); both shrunk by half the gap.  Tx diamonds of a column touch at the row centres (joined by a neck on the top
    copper); Rx diamonds of a row touch at the column centres (joined by a bridge on the bottom copper, two vias)."""
    x0, y0, x1, y1 = TP_AREA
    px, py = (x1 - x0) / TP_NTX, (y1 - y0) / TP_NRX
    # inset of a rhombus with half-diagonals a (x), b (y) by distance g: the half-diagonals shrink by g / sin(angle)
    a, b = px / 2, py / 2
    hyp = math.hypot(a, b)
    da, db = TP_GAP / 2 * hyp / b, TP_GAP / 2 * hyp / a

    def rhombus(cx, cy):
        return [(cx - (a - da), cy), (cx, cy - (b - db)), (cx + (a - da), cy), (cx, cy + (b - db))]
    n = 0
    for j in range(TP_NTX):
        net = nets["TX%d" % j]
        cx = x0 + px * (j + 0.5)
        for k in range(TP_NRX + 1):
            pts = clip_poly(rhombus(cx, y0 + py * k), x0, y0, x1, y1)
            if len(pts) >= 3:
                poly(board, pts, net)
                n += 1
        for k in range(TP_NRX):                     # necks at the row centres
            cy = y0 + py * (k + 0.5)
            track(board, (cx, cy - db - 0.3), (cx, cy + db + 0.3), TP_NECK, net, pcbnew.F_Cu)
    for k in range(TP_NRX):
        net = nets["RX%d" % k]
        cy = y0 + py * (k + 0.5)
        for j in range(TP_NTX + 1):
            pts = clip_poly(rhombus(x0 + px * j, cy), x0, y0, x1, y1)
            if len(pts) >= 3:
                poly(board, pts, net)
                n += 1
        for j in range(TP_NTX):                     # bridges under the Tx necks at the column centres
            cx = x0 + px * (j + 0.5)
            va, vb = (cx - TP_BRIDGE_D, cy), (cx + TP_BRIDGE_D, cy)
            via(board, va, net, 0.5, 0.25)
            via(board, vb, net, 0.5, 0.25)
            track(board, va, vb, 0.25, net, pcbnew.B_Cu)
        # feed: out of the area along the row centre line, down a via, then a lane of its own on the bottom copper
        # down the strip's left edge (the upper rows take the lanes further right, so no two cross), ending in a
        # staggered row just above the controller
        # the rows below the lane ends (their lane runs UP to its end) take the leftmost lanes, lowest row furthest
        # right: so neither their entry nor their exit crosses another lane (2026-11-18: rows 7-9 had the lanes in
        # the down-rows' order and RX7's entry crossed RX8's and RX9's lanes - a short)
        up = [kk for kk in range(TP_NRX) if y0 + py * (kk + 0.5) > TP_RX_END - 0.6 * (TP_NRX - 1 - kk)]
        lx = TP_RX_LANE0 + 0.30 * (up.index(k) if k in up else TP_NRX - 1 - k)
        vx = x1 + 0.65
        track(board, (x1 - 1.0, cy), (vx, cy), 0.2, net, pcbnew.F_Cu)
        via(board, (vx, cy), net, 0.5, 0.25)
        track(board, (vx, cy), (lx, cy), 0.15, net, pcbnew.B_Cu)
        # the lane turns right out of the bundle (the lanes to its right ended higher up) and ends in a via, the vias
        # in two staggered columns - a clean end for the router to start from
        ye = TP_RX_END - 0.6 * (TP_NRX - 1 - k)
        vx2 = TP_RX_LANE0 + 0.30 * TP_NRX + 0.35 + 0.70 * (k % 2)
        track(board, (lx, cy), (lx, ye), 0.15, net, pcbnew.B_Cu)
        track(board, (lx, ye), (vx2, ye), 0.15, net, pcbnew.B_Cu)
        via(board, (vx2, ye), net, 0.5, 0.25)
    # Tx feeds: from the bottom end of each column into a lane below the touch area, then to the strip.  Even columns on
    # the bottom copper, odd ones on the top; on each copper the leftmost column takes the lowest lane, so no two cross.
    lanes = {0: [j for j in range(TP_NTX) if j % 2 == 0], 1: [j for j in range(TP_NTX) if j % 2 == 1]}
    for side, cols in lanes.items():
        layer = pcbnew.B_Cu if side == 0 else pcbnew.F_Cu
        for i, j in enumerate(cols):
            net = nets["TX%d" % j]
            cx = x0 + px * (j + 0.5)
            # bottom-copper lanes y 67.6 .. 65.5, top-copper lanes y 65.25 .. 63.45 (each band: leftmost column lowest);
            # the bottom ones' vias sit above the top band
            ly = (67.60 if side == 0 else 65.25) - 0.30 * i
            top = y1 - 0.8
            if side == 0:
                via(board, (cx, y1 + 0.35), net, 0.5, 0.25)
                track(board, (cx, top), (cx, y1 + 0.35), 0.2, net, pcbnew.F_Cu)
                track(board, (cx, y1 + 0.35), (cx, ly), 0.15, net, layer)
            else:
                track(board, (cx, top), (cx, ly), 0.15, net, layer)
            # the lane ends 1.0 mm right of the one above it (top copper 0.5 mm further), turns up out of the band
            # (everything above it ended further left) and ends in a via just under the touch area's level
            xe = TP_LANE_X + 1.0 * (len(cols) - 1 - i) + (0.5 if side else 0.0)
            vy = y1 + (0.2 if side == 0 else -0.4)
            track(board, (cx, ly), (xe, ly), 0.15, net, layer)
            track(board, (xe, ly), (xe, vy), 0.15, net, layer)
            via(board, (xe, vy), net, 0.5, 0.25)
    return n


# --------------------------------------------------------------------------------------------- stage: place
def stage_place():
    d = cpmodel.load()
    if d.errors:
        raise SystemExit("\n".join(d.errors))
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(SPEC.get("layers", 2))
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = FromMM(0.15)
    ds.m_MinClearance = FromMM(0.15)
    ds.m_ViasMinSize = FromMM(0.5)
    ds.m_MinThroughDrill = FromMM(0.25)
    ds.m_CopperEdgeClearance = FromMM(0.2)
    ds.SetBoardThickness(FromMM(SPEC.get("t", 1.6)))
    outline(board)
    nets = {}
    for name in sorted(d.nets()):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    fps = {}
    for c in d.comps.values():
        fp = GP.load_fp(c.fp)
        fp.SetReference(c.ref)
        fp.SetValue(c.value)
        fp.SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
        fp.SetSheetname("/" + c.sheet + "/")
        fp.SetSheetfile(f"sheets/{c.sheet}.kicad_sch")
        if c.desc and hasattr(fp, "SetLibDescription"):
            fp.SetLibDescription(c.desc)
        names = {p.GetNumber() for p in fp.Pads()}
        for pin, net in c.pins.items():
            for pad in cpmodel.pads_for(c, pin):
                if pad not in names:
                    raise SystemExit(f"{c.ref} ({c.fp}): pin {pin} -> pad {pad} not on the footprint")
                if net is not None:
                    for p in fp.Pads():
                        if p.GetNumber() == pad:
                            p.SetNet(nets[net])
        if c.part in ("TACT12", "DOME12"):                    # (the key's name sits under its cap on the assembly drawing only)
            fp.Reference().SetLayer(pcbnew.F_Fab)
        board.Add(fp)
        fps[c.ref] = fp

    boxes = []
    for ref, how in SPEC["fixed"].items():
        if ref not in fps:
            continue
        if how[0] == "edge":
            edge_mount(fps[ref], how[1], how[2], how[3])
        else:
            put(fps[ref], *how)
        boxes.append(court(fps[ref]))
    # ---- the packer: every other part next to what it connects to (its first non-ground, non-supply net) ----
    big = set(SPEC["fixed"])
    supply = ("GND", "VCC5", "VCC3V3", "VBUS", "VBUS_USB", "VBAT")
    w, h = SPEC["w"], SPEC["h"]
    keep = [tuple(k) for k in SPEC["keepout"]]
    keep_b = [tuple(k) for k in SPEC.get("keepout_b", [])]
    rest = sorted((c for c in d.comps.values() if c.ref not in big),
                  key=lambda c: (-len(c.pins), c.ref))
    unplaced = []
    placed = set(r_ for r_ in SPEC["fixed"] if r_ in fps)
    # bottom-face obstacles: the fixed parts with through-hole pads (their pins come out there)
    boxes_b = [court(fps[r_]) for r_ in placed if any(p.HasHole() for p in fps[r_].Pads())]
    for c in rest:
        fp = fps[c.ref]
        targets = []                                # (x, y, weight): pads of placed parts on this part's nets
        for pin, net in c.pins.items():
            if not net or net == "GND":
                continue
            wt = 0.15 if net in supply else 1.0
            for ref2 in placed:
                for p in fps[ref2].Pads():
                    if p.GetNetname() == net:
                        x_, y_ = pad_xy(p)
                        targets.append((x_, y_, wt))
        if targets:
            sw = sum(t[2] for t in targets)
            tx = sum(t[0] * t[2] for t in targets) / sw
            ty = sum(t[1] * t[2] for t in targets) / sw
        else:
            tx, ty = w / 2, h / 2
        def search(face, obstacles):
            best = None
            for rot in (0, 90):
                put(fp, 0, 0, rot, face)
                c0 = court(fp)
                hw, hh = (c0[2] - c0[0]) / 2, (c0[3] - c0[1]) / 2
                step = 0.25
                for ring in range(0, 160):
                    found = False
                    rr = ring * step
                    n = max(1, int(2 * math.pi * rr / step)) if ring else 1
                    for k in range(n):
                        ang = 2 * math.pi * k / n
                        x, y = tx + rr * math.cos(ang), ty + rr * math.sin(ang)
                        bb = (x - hw, y - hh, x + hw, y + hh)
                        em = SPEC.get("edge_gap", 0.5)
                        if bb[0] < em or bb[1] < em or bb[2] > w - em or bb[3] > h - em:
                            continue
                        if any(overlaps(bb, k_) for k_ in (keep if face == "F" else keep + keep_b)):
                            continue
                        if any(math.hypot(x - ho[0], y - ho[1]) < (ho[2] if len(ho) == 3 else 1.35) + max(hw, hh) + SPEC.get("hole_gap", 0.3)
                               for ho in SPEC["holes"]):
                            continue
                        if any(overlaps(bb, b_, SPEC.get("gap", 0.25)) for b_ in obstacles):
                            continue
                        if best is None or rr < best[0]:
                            best = (rr, x, y, rot)
                        found = True
                        break
                    if found:
                        break
            return best
        best, face = search("F", boxes), "F"
        # boards with room under them (SPEC bottom=True: the bar BMS board, 1.5 mm): small resistors and capacitors,
        # SOT-23 transistors and SOD-123 diodes may go on the bottom face when that puts them nearer their connections
        low = (c.kind in ("R", "C") and any(s in c.fp for s in ("0402", "0603", "0805"))) or c.fp.endswith(("SOT-23", "D_SOD-123"))
        if SPEC.get("bottom") and low:
            bb_ = search("B", boxes_b)
            if bb_ is not None and (best is None or bb_[0] + 0.5 < best[0]):
                best, face = bb_, "B"
        if best is None:
            unplaced.append(c.ref)
            put(fp, w + 10, h / 2, 0, "F")
            continue
        put(fp, best[1], best[2], best[3], face)
        (boxes if face == "F" else boxes_b).append(court(fp))
        placed.add(c.ref)
    # pre-drawn supply trunks (net, layer, x, y0, y1, width): the router only has to reach them
    for tn, tl, tx, ty0, ty1, tw in SPEC.get("trunks", []):
        track(board, (tx, ty0), (tx, ty1), tw, nets[tn], {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}[tl])
    n_el = 0
    if V == "touch":
        n_el = electrodes(board, nets)
        x0, y0, x1, y1 = TP_AREA
        note(board, "touch area: no parts, no pours", 2.0, y1 + 1.4, 0.8, pcbnew.Cmts_User)
    nx_, ny_, nl_ = {"batt": (8.0, SPEC["h"] - 2.5, pcbnew.F_SilkS), "numpad": (111.5, SPEC["h"] - 1.8, pcbnew.F_SilkS),
                     "touch": (119.0, 1.6, pcbnew.B_SilkS), "tray": (6.6, 19.0, pcbnew.F_SilkS),
                     "bar": (40.0, 9.0, pcbnew.B_SilkS), "barcon": (40.0, 3.0, pcbnew.F_SilkS)}[V]
    note(board, "Commander %s %s" % (PRJ.split("_", 1)[1], cpmodel.REV), nx_, ny_, {"numpad": 0.8, "tray": 0.7}.get(V, 1.0), nl_)
    os.makedirs(os.path.dirname(PLACED), exist_ok=True)
    pcbnew.SaveBoard(PLACED, board)
    print("placed: %d footprints, %d by hand, %d packed%s; %d electrode diamonds"
          % (len(fps), len([r for r in SPEC["fixed"] if r in fps]), len(rest) - len(unplaced),
             (", NOT placed: " + " ".join(unplaced)) if unplaced else "", n_el))
    # overlaps report
    bb = {r: court(f) for r, f in fps.items()}
    bad = [(a, b) for a in bb for b in bb if a < b and fps[a].IsFlipped() == fps[b].IsFlipped() and overlaps(bb[a], bb[b], -0.05)]
    for a, b in bad:
        print("  courtyards overlap: %s %s" % (a, b))
    return board


# --------------------------------------------------------------------------------------------- stage: route
_OUTLINE = []


def make_router(board):
    import numpy as np
    import route as R
    import gen_project
    R.STRIP = True
    R.VIA_L = [0, 1, 2] if SPEC.get("layers", 2) == 4 else [0, 2]      # (4 layers: In2 routes, In1 is a ground plane)
    R.BASE_CL = 0.15
    R.RCS.clear()
    R.RCS.update({"Default": R.RC("Default", 0.15, 0.15, 0.60, 0.30), "PWR": R.RC("PWR", 0.40, 0.15, 0.80, 0.40),
                  "HIPWR": R.RC("HIPWR", 1.00, 0.20, 0.80, 0.40)})
    R.THIN.clear()
    R.THIN.update({"PWR": R.RC("PWR_thin", 0.25, 0.15, 0.80, 0.40), "HIPWR": R.RC("HIPWR_thin", 0.40, 0.20, 0.80, 0.40)})
    R.PAIRS.clear()
    R.LANE = 0.0
    R.PAIR_CLASSES = ()
    R.KSET = sorted({rc.Kt for rc in list(R.RCS.values()) + list(R.THIN.values())} | {rc.Kv for rc in R.RCS.values()})
    R.VIA_ONLY_K = set()
    R.PLANES.clear()
    R.PLANES.update({"GND": ("small",)})
    R.SKIP_CLASSES.clear()
    R.SKIP_NETS.clear()
    R.PRIMARY_AREA[:] = []
    R.CFG["PRI_X1"] = R.CFG["PRI_Y1"] = -1e6
    # the outline and its holes never change: read once (pcbnew's wrappers can come back broken after many edits)
    if not _OUTLINE:
        ps = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(ps, True)
        o = ps.Outline(0)
        _OUTLINE.append([(ToMM(o.CPoint(i).x) - OX, ToMM(o.CPoint(i).y) - OY) for i in range(o.PointCount())])
        hb = []
        for h_ in range(ps.HoleCount(0)):
            bb = ps.Hole(0, h_).BBox()
            hb.append((ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY))
        _OUTLINE.append(hb)
    pts, holes = _OUTLINE
    R.outline_pts = lambda: pts
    r = R.Router(board)
    code = {v_: k for k, v_ in r.name_of.items()}
    for net, name in r.name_of.items():
        for pat, cls in gen_project.SMALL_PATTERNS:
            if fnmatch.fnmatchcase(name, pat):
                r.rc_of[net] = R.RCS[cls]
                r.cls_of[net] = cls
                break
    x0 = TP_AREA[2] + 0.4 if V == "touch" else -1.0
    reg = R.Region("small", x0, -1.0, SPEC["w"] + 1.0, SPEC["h"] + 1.0)
    if SPEC.get("layers", 2) == 4:                  # the router keeps its middle layer (In2) for routing here
        for D_ in reg.D.values():
            D_[1] = R.FREE
    r.regs = [reg]
    r.build()
    r.items, r.failed = [], []
    # holes of the outline (mounting holes) are obstacles
    G = R.G
    for hx0, hy0, hx1, hy1 in holes:
        xa, ya, xb, yb = hx0 - 0.3, hy0 - 0.3, hx1 + 0.3, hy1 + 0.3
        i0, j0 = max(0, int((xa - reg.x0) / G)), max(0, int((ya - reg.y0) / G))
        i1, j1 = min(reg.nx - 1, R.ceil_((xb - reg.x0) / G)), min(reg.ny - 1, R.ceil_((yb - reg.y0) / G))
        if i0 <= i1 and j0 <= j1:
            for l in ((0, 1, 2) if SPEC.get("layers", 2) == 4 else (0, 2)):
                reg.stamp(l, i0, j0, np.ones((j1 - j0 + 1, i1 - i0 + 1), bool), R.MULTI)
            reg.novia[max(0, j0 - 8):j1 + 9, max(0, i0 - 8):i1 + 9] = True
    return r, reg, code


def pour_layers():
    """The faces that get a ground pour: both, unless SPEC says otherwise (the bar's contact board: the back only)."""
    out = [{"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}[c] for c in SPEC.get("pours", "FB")]
    return out + ([pcbnew.In1_Cu] if SPEC.get("layers", 2) == 4 else [])      # 4 layers: In1 = ground plane


def add_zone(board, net, layer, pts, prio=0):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(FromMM(0.25))
    z.SetMinThickness(FromMM(0.2))
    z.SetThermalReliefGap(FromMM(0.3))
    z.SetThermalReliefSpokeWidth(FromMM(0.4))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(FromMM(OX + x), FromMM(OY + y))
    board.Add(z)
    return z


def route_pass(prio, variant):
    """One attempt on a fresh copy of the placed board.  Order: the nets that failed before (prio), the wide supply
    nets, then the rest shortest first (variant 0), longest first (1), or shuffled (2 and up)."""
    import random
    board = pcbnew.LoadBoard(PLACED)
    board.BuildConnectivity()
    r, reg, code = make_router(board)
    gnd = code.get("GND")
    rnd = random.Random(variant)
    order = []
    for net in sorted(set(reg.pads) | set(reg.tree)):
        name = r.name_of[net]
        if name == "GND" or len(r.groups(reg, net)) < 2:
            continue
        pads = reg.pads.get(net, [])
        span = (max(q["cx"] for q in pads) - min(q["cx"] for q in pads) + max(q["cy"] for q in pads) - min(q["cy"] for q in pads)) if pads else 0.0
        hi = r.rc_of[net].name in (("HIPWR", "PWR") if V in ("tray", "bar") else ("HIPWR",))     # (tray, bar: supplies first)
        key = span if variant == 0 else -span if variant == 1 else rnd.random()
        order.append((-prio.get(name, 0), 0 if hi else 1, key, name, net))
    done, part = [], []
    for _, _, _, name, net in sorted(order):
        ok, bad = r.route_net(reg, net)
        (part if bad else done).append(name)
    fan_ok, fan_bad = (r.fanout(reg, gnd) if gnd else (0, []))
    return dict(board=board, r=r, done=done, part=part, fan_ok=fan_ok, fan_bad=fan_bad)


def open_nets(board):
    """Names of the nets (ground aside) whose pads are not all joined by copper (zones are not filled yet)."""
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    out = set()
    for net, name in ((ni.GetNetCode(), str(ni.GetNetname())) for ni in board.GetNetsByName().values()):
        if name in ("", "GND"):
            continue
        pads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == net]
        if V == "touch" and re.fullmatch(r"[TR]X\d+", name) and len(pads) == 1:
            # an electrode net has one pad (the IQS550's): it is joined when that pad reaches copper of its net in the
            # touch area (the electrodes, their necks / bridges and the pre-drawn feed)
            xa = FromMM(OX + TP_AREA[2])
            if not any(it.GetBoundingBox().GetCenter().x < xa for it in conn.GetConnectedItems(pads[0], 0)):
                out.add(name)
            continue
        if len(pads) < 2:
            continue
        first = pads[0]
        reach = {it.m_Uuid.AsString() for it in conn.GetConnectedItems(first, 0)} | {first.m_Uuid.AsString()}
        if any(p.m_Uuid.AsString() not in reach for p in pads[1:]):
            out.add(name)
    return out


ROUTED = os.path.join(ROOT, "build", PRJ + "_routed.kicad_pcb")


def repair_round(k):
    """One round of rip-up and retry on build/<project>_routed.kicad_pcb, in a process of its own (pcbnew's wrappers
    break after a board is edited and reloaded in the same process): for a net that is still open, the copper of every
    other net within a circle round its pads is taken out, the open net is routed first, then the nets taken out.  The
    file is overwritten only when the round left fewer nets open (or the same number without that net).
    Exit code 0: nothing open (any more), 1: still open."""
    # the copper drawn before routing (supply trunks, the touchpad's electrodes and feed lanes) is never taken out:
    # the router does not draw it again (2026-11-18: rip-ups had removed 15 of the touchpad's 25 sensor feeds)
    def key(t):
        a, b = t.GetStart(), t.GetEnd()
        return (t.GetLayer(), t.GetClass(), tuple(sorted(((a.x, a.y), (b.x, b.y)))))
    predrawn = {key(t) for t in pcbnew.LoadBoard(PLACED).GetTracks()}
    board = pcbnew.LoadBoard(ROUTED)
    openn = open_nets(board)
    if not openn:
        raise SystemExit(0)
    order = sorted(openn)
    name = order[k % len(order)]
    rip_r = 2.5 + 1.5 * (k // len(order))          # the same net again: a wider circle
    code = board.FindNet(name).GetNetCode()
    pts = [pad_xy(p) for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == code]
    rip = set()
    for t in board.GetTracks():
        n = t.GetNetname()
        if n in ("GND", name) or not n:
            continue
        if t.GetClass() == "PCB_VIA":
            segs = [(pad_xy(t), pad_xy(t))]
        else:
            segs = [((ToMM(t.GetStart().x) - OX, ToMM(t.GetStart().y) - OY), (ToMM(t.GetEnd().x) - OX, ToMM(t.GetEnd().y) - OY))]
        for (ax, ay), (bx, by) in segs:
            for (px_, py_) in pts:
                vx, vy = bx - ax, by - ay
                L2 = vx * vx + vy * vy
                u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px_ - ax) * vx + (py_ - ay) * vy) / L2))
                if math.hypot(ax + u * vx - px_, ay + u * vy - py_) < rip_r:
                    rip.add(n)
    kill = [t for t in board.GetTracks() if (t.GetNetname() in rip or t.GetNetname() == name) and key(t) not in predrawn]
    for t in kill:
        board.Remove(t)
    r, reg, code_of = make_router(board)
    for n in [name] + sorted(rip):
        net = code_of[n]
        if len(r.groups(reg, net)) >= 2:
            r.route_net(reg, net)
    r.flush(r.items)
    after = open_nets(board)
    if len(after) > len(openn) or (len(after) == len(openn) and name in after):
        print("repair %d: %s (circle %.1f mm) - no better (%d open), not kept" % (k + 1, name, rip_r, len(after)), flush=True)
    else:
        pcbnew.SaveBoard(ROUTED, board)
        print("repair %d: %s (circle %.1f mm) - %d nets taken out and re-routed; open now: %s"
              % (k + 1, name, rip_r, len(rip), " ".join(sorted(after)) or "none"), flush=True)
        if not after:
            raise SystemExit(0)
    raise SystemExit(1)


def repair(board, part, rounds=None):
    """Rounds of repair_round, each in a process of its own; returns the board reloaded from the file."""
    import subprocess
    rounds = rounds if rounds is not None else int(os.environ.get("CP_REPAIR", "8"))
    pcbnew.SaveBoard(ROUTED, board)
    if part:
        for k in range(rounds):
            rc = subprocess.run([sys.executable, os.path.abspath(__file__), "--stage", "repair1", str(k)]).returncode
            if rc == 0:
                break
            if rc != 1:
                print("repair %d: the round failed (exit %d), board kept as it was" % (k + 1, rc), flush=True)
    board = pcbnew.LoadBoard(ROUTED)
    still = open_nets(board)
    fixed = [n for n in part if n not in still]
    return board, sorted(still), fixed


def stitch(board, pitch=6.0, r=0.6):
    """Ground vias (0.6 / 0.3) on a 'pitch' grid wherever the filled ground pours of BOTH faces cover a disc of radius r
    round the point - so every piece of pour that tracks have cut off gets joined to the other face."""
    gnd = board.FindNet("GND")
    fills = {}
    for z in board.Zones():
        if z.GetNetname() == "GND" and not z.GetIsRuleArea():
            fills[z.GetLayer()] = z.GetFilledPolysList(z.GetLayer())
    if pcbnew.F_Cu not in fills or pcbnew.B_Cu not in fills:
        return 0
    ring = [(r * math.cos(a * math.pi / 4), r * math.sin(a * math.pi / 4)) for a in range(8)] + [(0.0, 0.0)]

    holes = [pad_xy(t) for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    holes += [pad_xy(p) for fp in board.GetFootprints() for p in fp.Pads() if p.HasHole()]

    def free(x, y):
        return all((x - hx) ** 2 + (y - hy) ** 2 > 1.1 ** 2 for hx, hy in holes)

    def covered(fp_, x, y):
        return all(fp_.Contains(VECTOR2I(FromMM(OX + x + dx), FromMM(OY + y + dy))) for dx, dy in ring)
    n = 0
    y = 1.5
    while y < SPEC["h"] - 1.0:
        x = 1.5
        while x < SPEC["w"] - 1.0:
            if free(x, y) and covered(fills[pcbnew.F_Cu], x, y) and covered(fills[pcbnew.B_Cu], x, y):
                via(board, (x, y), gnd, 0.6, 0.3)
                holes.append((x, y))
                n += 1
            x += pitch
        y += pitch
    # every smaller piece of pour (cut off by tracks) gets up to two vias of its own, searched on a fine grid
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        fl = fills[layer]
        other = fills[pcbnew.B_Cu if layer == pcbnew.F_Cu else pcbnew.F_Cu]
        areas = [(fl.Outline(k).Area(), k) for k in range(fl.OutlineCount())]
        if not areas:
            continue
        big = max(areas)[1]
        for _, k in areas:
            if k == big:
                continue
            o = fl.Outline(k)
            bb = o.BBox()
            x0_, y0_ = ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY
            x1_, y1_ = ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY
            got, last = 0, None
            yy = y0_ + r
            while yy < y1_ - r and got < 2:
                xx = x0_ + r
                while xx < x1_ - r and got < 2:
                    if (all(o.PointInside(VECTOR2I(FromMM(OX + xx + dx), FromMM(OY + yy + dy))) for dx, dy in ring)
                            and free(xx, yy) and covered(other, xx, yy)
                            and (last is None or math.hypot(xx - last[0], yy - last[1]) > 3.0)):
                        via(board, (xx, yy), gnd, 0.6, 0.3)
                        holes.append((xx, yy))
                        n += 1
                        got += 1
                        last = (xx, yy)
                    xx += 0.4
                yy += 0.4
    return n


def stitch_pours(board):
    """Fill the ground pours keeping every island, stitch the two faces together, refill dropping what is still
    unconnected."""
    zs = [z for z in board.Zones() if z.GetNetname() == "GND" and not z.GetIsRuleArea()]
    for z in zs:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    n = stitch(board)
    for z in zs:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return n


def stage_stitch():
    """Only the ground stitching, on the finished board (after a routing run)."""
    board = pcbnew.LoadBoard(FINAL)
    # (the stitching of an earlier run: ground vias with no track ending on them - taken out first)
    ends = set()
    for t in board.GetTracks():
        if t.GetClass() != "PCB_VIA" and t.GetNetname() == "GND":
            for q in (t.GetStart(), t.GetEnd()):
                ends.add((round(ToMM(q.x), 3), round(ToMM(q.y), 3)))
    old = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"
           and (round(ToMM(t.GetPosition().x), 3), round(ToMM(t.GetPosition().y), 3)) not in ends]
    for t in old:
        board.Remove(t)
    before = None
    board.BuildConnectivity()
    before = board.GetConnectivity().GetUnconnectedCount(True)
    n = stitch_pours(board)
    board.BuildConnectivity()
    after = board.GetConnectivity().GetUnconnectedCount(True)
    pcbnew.SaveBoard(FINAL, board, True)
    print("ground stitching: %d vias; unconnected %d -> %d" % (n, before, after))


def stage_finish():
    """The routed board (build/<project>_routed.kicad_pcb, e.g. after further repair1 rounds) -> ground pours, stitching,
    <project>.kicad_pcb."""
    board = pcbnew.LoadBoard(ROUTED)
    w, h = SPEC["w"], SPEC["h"]
    area = [(0, 0), (w, 0), (w, h), (0, h)] if V != "touch" else [(TP_AREA[2] + 0.9, 0), (w, 0), (w, h), (TP_AREA[2] + 0.9, h)]
    for layer in pour_layers():
        add_zone(board, board.FindNet("GND"), layer, area)
    nst = stitch_pours(board)
    board.BuildConnectivity()
    after = board.GetConnectivity().GetUnconnectedCount(True)
    pcbnew.SaveBoard(FINAL, board, True)
    print("finish: open nets %s; ground stitching %d vias; unconnected after the pours: %d"
          % (" ".join(sorted(open_nets(board))) or "none", nst, after))


def stage_route():
    passes = int(os.environ.get("CP_PASSES", "6"))
    prio, best = {}, None
    for n in range(passes):
        res = route_pass(prio, n)
        print("pass %d: %d nets complete, %d not (%s); ground pads without a via: %d"
              % (n + 1, len(res["done"]), len(res["part"]), " ".join(res["part"]) or "-", len(res["fan_bad"])), flush=True)
        if best is None or (len(res["part"]), len(res["fan_bad"])) < (len(best["part"]), len(best["fan_bad"])):
            best = res
        if not res["part"] and len(res["fan_bad"]) <= 6:     # (a ground pad without a via usually meets a pour anyway)
            break
        for name in res["part"]:
            prio[name] = prio.get(name, 0) + 1
    board, r, done, part, fan_ok, fan_bad = (best[k] for k in ("board", "r", "done", "part", "fan_ok", "fan_bad"))
    r.flush(r.items)
    failed = list(r.failed)
    board, part, fixed = repair(board, part)
    done += fixed
    r.failed = [f for f in failed if not any(f.startswith(n + ":") for n in fixed)]
    # ground pours, both faces; on the touchpad only in the electronics strip
    w, h = SPEC["w"], SPEC["h"]
    area = [(0, 0), (w, 0), (w, h), (0, h)] if V != "touch" else [(TP_AREA[2] + 0.9, 0), (w, 0), (w, h), (TP_AREA[2] + 0.9, h)]
    for layer in pour_layers():
        add_zone(board, board.FindNet("GND"), layer, area)
    nst = stitch_pours(board)
    print("ground stitching: %d vias" % nst, flush=True)
    board.BuildConnectivity()
    after = board.GetConnectivity().GetUnconnectedCount(True)
    pcbnew.SaveBoard(FINAL, board, True)
    out = dict(done=done, part=part, failed=r.failed, gnd_vias=fan_ok, gnd_no_via=fan_bad, unconnected=after,
               tracks=r.stats["tracks"], vias=r.stats["vias"], length=round(r.stats["length"], 1))
    json.dump(out, open(os.path.join(ROOT, "build", "route.json"), "w", encoding="utf-8"), indent=1)
    print("routed: %d nets complete, %d not (%s); %d tracks, %d vias, %.0f mm; ground vias %d (none for %d); "
          "unconnected after the pours: %d" % (len(done), len(part), " ".join(part) or "-", out["tracks"], out["vias"],
                                               out["length"], fan_ok, len(fan_bad), after))
    for f in r.failed:
        print("  ", f)


def main():
    stage = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "all"
    if stage in ("place", "all"):
        stage_place()
    if stage in ("route", "all"):
        stage_route()
    if stage == "stitch":
        stage_stitch()
    if stage == "finish":                           # after extra repair1 rounds on the routed board: pours + stitching again
        stage_finish()
    if stage == "repair1":
        repair_round(int(sys.argv[sys.argv.index("--stage") + 2]))


if __name__ == "__main__":
    main()

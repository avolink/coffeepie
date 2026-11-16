#!/usr/bin/env python
"""export_3d.py BOARD OUTDIR NAME [glb] [step] [stl] - the board in 3D, for fit checks in the chassis model.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/export_3d.py ../commander_hub/commander_hub.kicad_pcb \
        ../../3d-models/pcb_exports commander_hub glb step

KiCad's own 3D library has no model for many of this project's footprints (the custom ones, the 200 / 153-ball
BGAs, the HRO USB-C, a few QFN / CSP packages).  Those get a plain box here - the footprint's fab outline and pads,
at the part's real height above the board (HEIGHT below; flagged ESTIMATE where no datasheet height was used) - so
that what stands up from the board is there in the chassis check.  The boxes are written as VRML into OUTDIR/_boxes
and added to a COPY of the board (OUTDIR/_<name>_3d.kicad_pcb); the project's board is not touched.
"""
import os
import re
import subprocess
import sys

import pcbnew
from pcbnew import ToMM, VECTOR2I

KICAD = "C:/Program Files/KiCad/10.0"
MODELS = KICAD + "/share/kicad/3dmodels"
CLI = KICAD + "/bin/kicad-cli.exe"
# (regex on the footprint name, height above the board in mm, colour, note)
HEIGHT = [
    (r"RK3566|FCCSP", 1.0, (0.15, 0.15, 0.15), ""),
    (r"BGA-200", 1.0, (0.15, 0.15, 0.15), ""),
    (r"LFBGA-153|BGA-153", 1.2, (0.15, 0.15, 0.15), ""),
    (r"USB_C_Receptacle", 3.26, (0.75, 0.75, 0.78), ""),
    (r"RJ45", 8.0, (0.75, 0.75, 0.78), "ESTIMATE (sunk RJ45, height above the board)"),
    (r"XFMR_Bourns_PLN", 8.0, (0.1, 0.1, 0.1), ""),
    (r"XFMR_LAN", 2.2, (0.1, 0.1, 0.1), "ESTIMATE"),
    (r"M2_Socket", 2.06, (0.1, 0.1, 0.1), ""),
    (r"M2_CardEdge", 0.0, None, ""),
    (r"HDMI_Micro", 3.0, (0.75, 0.75, 0.78), "ESTIMATE"),
    (r"WLCSP|_CSP", 0.6, (0.15, 0.15, 0.15), ""),
    (r"QFN|DFN|SON", 0.85, (0.15, 0.15, 0.15), ""),
    (r"PowerPAK|PowerDI", 1.1, (0.15, 0.15, 0.15), ""),
    (r"^D_0402|0402", 0.5, (0.2, 0.2, 0.2), ""),
    (r"SW_PUSH-12mm", 4.3, (0.25, 0.25, 0.28), "12 x 12 x 4.3 mm tact switch body (numpad), cap not included"),
    (r"JST_PH_B\dB-PH-K", 6.0, (0.9, 0.9, 0.85), ""),
    (r"SOT-89", 1.5, (0.15, 0.15, 0.15), ""),
    (r"Pogo_CFE_BP33242", 2.25, (0.08, 0.08, 0.08), "pogo connector, plungers free (1.6 mm when a module sits on them)"),
    (r"KeySwitch|Keychron", 6.0, (0.35, 0.35, 0.4), "ESTIMATE (switch housing over its optical sensor)"),
    (r"ISP_|Pads|TestPoint|MountingHole|Fiducial", 0.0, None, ""),
    (r"CMC_0504", 0.5, (0.2, 0.2, 0.2), ""),
]
DEFAULT = (1.0, (0.3, 0.3, 0.3), "ESTIMATE (default)")


def expand(path):
    p = path.replace("${KICAD10_3DMODEL_DIR}", MODELS).replace("${KICAD9_3DMODEL_DIR}", MODELS) \
            .replace("${KICAD8_3DMODEL_DIR}", MODELS).replace("${KISYS3DMOD}", MODELS)
    return p


def model_ok(path):
    p = expand(path)
    if "${" in p:
        return False
    if os.path.exists(p):
        return True
    base = os.path.splitext(p)[0]
    return any(os.path.exists(base + e) for e in (".step", ".stp", ".wrl"))


def rule(name):
    for rx, h, col, note in HEIGHT:
        if re.search(rx, name):
            return h, col, note
    return DEFAULT


def local_bbox(fp):
    """The footprint's fab outline + pads, in its own (unrotated, top-side) coordinates, mm."""
    c = pcbnew.FOOTPRINT(fp)
    b = pcbnew.BOARD()
    b.Add(c)
    if c.IsFlipped():
        c.Flip(c.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    c.SetOrientationDegrees(0)
    c.SetPosition(VECTOR2I(0, 0))
    xs, ys = [], []
    for g in c.GraphicalItems():
        if g.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab) and g.GetClass() in ("PCB_SHAPE", "FP_SHAPE"):
            bb = g.GetBoundingBox()
            xs += [ToMM(bb.GetLeft()), ToMM(bb.GetRight())]
            ys += [ToMM(bb.GetTop()), ToMM(bb.GetBottom())]
    for p in c.Pads():
        bb = p.GetBoundingBox()
        xs += [ToMM(bb.GetLeft()), ToMM(bb.GetRight())]
        ys += [ToMM(bb.GetTop()), ToMM(bb.GetBottom())]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def box_wrl(path, x0, y0, x1, y1, h, col):
    """VRML box; KiCad reads VRML in units of 0.1 inch, X right, Y up (footprint y is down), Z up."""
    u = 1 / 2.54
    sx, sy, sz = (x1 - x0) * u, (y1 - y0) * u, h * u
    tx, ty, tz = (x0 + x1) / 2 * u, -(y0 + y1) / 2 * u, h / 2 * u
    with open(path, "w", encoding="ascii") as f:
        f.write("#VRML V2.0 utf8\nTransform { translation %.5f %.5f %.5f children [ Shape { appearance Appearance { "
                "material Material { diffuseColor %.2f %.2f %.2f } } geometry Box { size %.5f %.5f %.5f } } ] }\n"
                % (tx, ty, tz, col[0], col[1], col[2], sx, sy, sz))


def main():
    board_path, outdir, name = sys.argv[1], sys.argv[2], sys.argv[3]
    fmts = [a for a in sys.argv[4:] if a in ("glb", "step", "stl")] or ["glb"]
    os.makedirs(os.path.join(outdir, "_boxes"), exist_ok=True)
    b = pcbnew.LoadBoard(board_path)
    nbox, nkept, notes = 0, 0, set()
    for fp in b.GetFootprints():
        fpname = fp.GetFPID().GetLibItemName().wx_str() if hasattr(fp.GetFPID().GetLibItemName(), "wx_str") else str(fp.GetFPID().GetLibItemName())
        models = fp.Models()
        good = [m for m in models if model_ok(m.m_Filename)]
        if good:
            for m in good:
                m.m_Filename = expand(m.m_Filename)
            # drop the unresolvable ones
            keep = [m for m in models if model_ok(m.m_Filename)]
            while models.size():
                models.pop_back()
            for m in keep:
                models.push_back(m)
            nkept += 1
            continue
        h, col, note = rule(fpname)
        while models.size():
            models.pop_back()
        if h <= 0:
            continue
        bb = local_bbox(fp)
        if bb is None:
            continue
        wrl = os.path.join(outdir, "_boxes", re.sub(r"[^A-Za-z0-9_.-]", "_", fpname) + ".wrl").replace("\\", "/")
        box_wrl(wrl, *bb, h, col)
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = wrl
        m.m_Show = True
        models.push_back(m)
        nbox += 1
        if note:
            notes.add("%s: %s" % (fpname, note))
    tmp = os.path.join(outdir, "_%s_3d.kicad_pcb" % name)
    pcbnew.SaveBoard(tmp, b)
    env = dict(os.environ, KICAD10_3DMODEL_DIR=MODELS)
    for fmt in fmts:
        out = os.path.join(outdir, "%s.%s" % (name, fmt))
        args = [CLI, "pcb", "export", fmt, "-f", "-o", out]
        if fmt in ("glb", "step"):
            args += ["--include-soldermask", "--include-silkscreen", "--include-pads"] if fmt == "glb" else ["--subst-models"]
        args.append(tmp)
        r = subprocess.run(args, env=env, capture_output=True, text=True)
        miss = sorted({l.split("/")[-1] for l in (r.stdout + r.stderr).splitlines() if "File not found" in l})
        print("%s: %s (%s)%s" % (fmt, out, "ok" if os.path.exists(out) else "FAILED", (" - still missing: " + ", ".join(miss)) if miss else ""))
    print("%d footprints keep their KiCad model, %d got a box" % (nkept, nbox))
    for n in sorted(notes):
        print("  box height", n)


if __name__ == "__main__":
    main()

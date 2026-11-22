"""drop_parts.py SRC DST --refs REF[,REF...] --nets REGEX   (KiCad's Python)

Takes parts off a routed board when they leave the netlist: the footprints named in --refs go, every track and via of
the nets matching --nets (full match) goes, and the pads other parts have on those nets become unconnected pads.
Tracks of other nets that only served the removed parts (a ground or supply stub to one of their pads) stay as stubs:
prune afterwards.  Removals last (KiCad's Python objects do not survive a Remove()).

Used on 2026-11-21 for the mainboard's eMMC:
    --refs U20,R401,R402,R403,R404,C401,C402,C403,C404,C405,TP3 --nets "EMMC_.*" """
import os
import re
import shutil
import sys

import pcbnew


def main():
    src, dst = sys.argv[1:3]
    opt = sys.argv[3:]
    refs = [r for r in opt[opt.index("--refs") + 1].split(",") if r]
    nets = re.compile(opt[opt.index("--nets") + 1])
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    fps, missing = [], []
    for r in refs:
        f = b.FindFootprintByReference(r)
        (fps if f is not None else missing).append(f if f is not None else r)
    doomed = [t for t in b.GetTracks() if nets.fullmatch(t.GetNetname())]
    names = sorted({t.GetNetname() for t in doomed})
    keep_refs = set(refs)
    freed = []
    for f in b.GetFootprints():
        if f.GetReference() in keep_refs:
            continue
        for p in f.Pads():
            if nets.fullmatch(p.GetNetname()):
                freed.append("%s.%s (%s)" % (f.GetReference(), p.GetNumber(), p.GetNetname()))
                p.SetNetCode(0)
    n_t, n_f = len(doomed), len(fps)
    for t in doomed:
        b.Remove(t)
    for f in fps:
        b.Remove(f)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    print("drop_parts: %d footprints and %d tracks / vias of %d nets taken out -> %s" % (n_f, n_t, len(names), dst))
    if missing:
        print("  not on the board:", " ".join(missing))
    print("  pads now unconnected:", " ".join(freed))


main()

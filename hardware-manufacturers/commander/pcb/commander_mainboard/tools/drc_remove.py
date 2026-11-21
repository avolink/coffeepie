"""drc_remove.py SRC DST DRC.json [--boxes BOXES.json] [--keep REGEX] [--strict] [--types a,b,c]   (KiCad's Python)

Takes out the tracks / vias that KiCad's DRC report (JSON, of SRC) names in shorts, clearance and crossing violations,
so that the router can lay them again.  Of the two items of a violation the one to go is the one that is NOT protected:
protected is copper inside one of the boxes (--boxes, e.g. the bay fan-outs of hub_bay_fanout.py) and copper of a net
matching --keep (e.g. the PoE primary: the low-voltage line that strayed into it is the one to move).  Pads never go.
When both are protected nothing is done; when neither is, the shorter track goes."""
import json
import os
import re
import shutil
import sys

import pcbnew
from pcbnew import ToMM


def main():
    src, dst, rep = sys.argv[1:4]
    opt = sys.argv[4:]
    boxes = json.load(open(opt[opt.index("--boxes") + 1], encoding="utf-8")) if "--boxes" in opt else []
    keep = re.compile(opt[opt.index("--keep") + 1]) if "--keep" in opt else None
    strict = "--strict" in opt             # kept copper never goes (e.g. against a pad: the part is to move, not the track)
    types = set((opt[opt.index("--types") + 1] if "--types" in opt else "shorting_items,clearance,tracks_crossing,hole_clearance").split(","))
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    d = json.load(open(rep, encoding="utf-8"))
    board = pcbnew.LoadBoard(src)
    tracks = {t.m_Uuid.AsString(): t for t in board.GetTracks()}

    def in_box(q):
        return any(b[0] <= q[0] <= b[2] and b[1] <= q[1] <= b[3] for b in boxes)

    def boxed(t):
        if t.GetClass() == "PCB_VIA":
            return in_box((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)))
        return in_box((ToMM(t.GetStart().x), ToMM(t.GetStart().y))) and in_box((ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)))

    def kept(t):
        return keep is not None and bool(keep.fullmatch(t.GetNetname()))
    gone = {}
    for v in d.get("violations", []):
        if v["type"] not in types:
            continue
        its = [tracks.get(it["uuid"]) for it in v["items"]]
        free = [t for t in its if t is not None and not boxed(t)]       # (copper in a box never goes)
        cand = [t for t in free if not kept(t)]
        if not cand and not strict:
            cand = free                                                 # two kept nets against each other: one of them
        if not cand:
            continue
        if len(cand) == 2:
            cand = [min(cand, key=lambda t: t.GetLength() if t.GetClass() != "PCB_VIA" else 0)]
        for t in cand:
            gone[t.m_Uuid.AsString()] = t
    names = sorted({t.GetNetname() for t in gone.values()})
    for t in gone.values():
        board.Remove(t)
    pcbnew.SaveBoard(dst, board)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        with open(stem + ".kicad_pro", "w", encoding="utf-8", newline="") as f:
            f.write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    print("  drc_remove: %d tracks / vias taken out (nets: %s) -> %s" % (len(gone), " ".join(names), dst), flush=True)


if __name__ == "__main__":
    main()

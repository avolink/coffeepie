"""iso_remove.py SRC DST [--gap 2.0] [--keepouts]   (KiCad's Python)

The isolation barrier of the mainboard (line side = the RJ45 pairs up to the transformers, the centre taps, the Bob
Smith node and the PoE primary; see check_head_isolation.py, whose definition of the line side this uses), enforced
on the copper that can be laid again:

  - every low-voltage TRACK or VIA closer than the gap to line-side copper on the same layer is taken out (the
    router, with its "isolation" setting, lays it again at a distance);
  - --keepouts: every line-side via / through pin gets a round copper-pour keep-out on the inner plane layers, so
    that the ground and supply planes stand the gap off it (keep-outs that are there already are left alone).

Pads are parts: a low-voltage PAD inside the gap is reported, not touched (that is a placement matter)."""
import fnmatch
import math
import os
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

BRIDGES = {"L15", "L23", "L25", "L27", "C60", "T1", "U31", "C518"}


def line(n):
    return bool(n) and (fnmatch.fnmatch(n, "PHY_MDI?_[PN]") or fnmatch.fnmatch(n, "TR?_48V") or n == "BS"
                        or fnmatch.fnmatch(n, "BS?") or (n.startswith("POE_") and n not in ("POE_SEC", "POE_SNUB")))


def main():
    src, dst = sys.argv[1:3]
    opt = sys.argv[3:]
    gap = float(opt[opt.index("--gap") + 1]) if "--gap" in opt else 2.0
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    b = pcbnew.LoadBoard(src)
    cu = list(b.GetEnabledLayers().CuStack())
    lines = {l: [] for l in cu}                 # layer -> [(bbox, shape, label, footprint ref)]
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if line(p.GetNetname()):
                for l in cu:
                    if p.IsOnLayer(l):
                        lines[l].append((p.GetBoundingBox(), p.GetEffectiveShape(l), fp.GetReference()))
    for t in b.GetTracks():
        if line(t.GetNetname()):
            for l in cu:
                if t.IsOnLayer(l):
                    lines[l].append((t.GetBoundingBox(), t.GetEffectiveShape(l), ""))
    g = FromMM(gap)

    def near(bb, shape, l, ref=""):
        for lb, ls, lref in lines[l]:
            if bb.GetRight() + g < lb.GetLeft() or lb.GetRight() + g < bb.GetLeft() or bb.GetBottom() + g < lb.GetTop() or lb.GetBottom() + g < bb.GetTop():
                continue
            if ref and ref == lref and ref in BRIDGES:
                continue
            if shape.Collide(ls, g - 1000):
                return True
        return False
    gone = []
    for t in b.GetTracks():
        if line(t.GetNetname()):
            continue
        for l in cu:
            if t.IsOnLayer(l) and near(t.GetBoundingBox(), t.GetEffectiveShape(l), l):
                gone.append(t)
                break
    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() and not line(p.GetNetname()):
                for l in cu:
                    if p.IsOnLayer(l) and near(p.GetBoundingBox(), p.GetEffectiveShape(l), l, fp.GetReference()):
                        pads.append("%s.%s [%s]" % (fp.GetReference(), p.GetNumber(), p.GetNetname()))
                        break
    nets = sorted({t.GetNetname() for t in gone})
    nk = 0
    if "--keepouts" in opt:
        inner = [l for l in cu if l not in (pcbnew.F_Cu, pcbnew.B_Cu)]
        have = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowZoneFills()]
        spots = []
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA" and line(t.GetNetname()):
                spots.append((t.GetPosition(), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.HasHole() and line(p.GetNetname()):
                    spots.append((p.GetPosition(), max(ToMM(p.GetSize().x), ToMM(p.GetSize().y)) / 2))
        for pos, r in spots:
            rr = r + gap + 0.05
            # already inside a keep-out that covers the circle's four ends?
            ends = [VECTOR2I(pos.x + FromMM(dx * rr), pos.y + FromMM(dy * rr)) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if any(all(z.Outline().Contains(e) for e in ends) for z in have):
                continue
            z = pcbnew.ZONE(b)
            z.SetIsRuleArea(True)
            z.SetDoNotAllowZoneFills(True)
            z.SetDoNotAllowTracks(False)
            z.SetDoNotAllowVias(False)
            z.SetDoNotAllowPads(False)
            z.SetDoNotAllowFootprints(False)
            ls = pcbnew.LSET()
            for l in inner:
                ls.AddLayer(l)
            z.SetLayerSet(ls)
            ol = z.Outline()
            ol.NewOutline()
            for k in range(24):
                a = 2 * math.pi * k / 24
                ol.Append(pos.x + FromMM(rr * math.cos(a) / math.cos(math.pi / 24)), pos.y + FromMM(rr * math.sin(a) / math.cos(math.pi / 24)))
            z.SetZoneName("isolation: line-side via / pin")
            b.Add(z)
            nk += 1
    for t in gone:
        b.Remove(t)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())          # the planes must stand off the new keep-outs in the saved file too
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        with open(stem + ".kicad_pro", "w", encoding="utf-8", newline="") as f:
            f.write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    print("  iso_remove: %d low-voltage tracks / vias inside the %.1f mm gap taken out (nets: %s); %d plane keep-outs added"
          % (len(gone), gap, " ".join(nets), nk), flush=True)
    if pads:
        print("  iso_remove: low-voltage PADS inside the gap (placement): " + ", ".join(sorted(set(pads))), flush=True)


if __name__ == "__main__":
    main()

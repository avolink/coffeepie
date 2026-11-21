"""mb10_convert.py SRC DST - the mainboard from 6 to 10 copper layers, the stack-up of the commander_cpu_ram board seen
from the other face (its processor is on the top, ours on the bottom):

    F.Cu   signal                       (was F.Cu)
    In1    GND                          (was In1)
    In2    signal                       (was In2)
    In3    supply planes                (was In3)
    In4    supply planes                new
    In5    signal                       new
    In6    GND                          new
    In7    signal                       new
    In8    GND (+ the old In4 tracks)   (was In4: the plane next to the bottom face stays next to it)
    B.Cu   signal                       (was B.Cu)

Tracks and zones of the old In4 go to In8; the keep-out rule areas that held every inner layer hold every inner layer
again, the ground-only ones (In1 + In4) the three ground layers; In6 gets a ground plane with In1's outline.  Nothing
else moves - the open links are the same as before.
"""
import os
import shutil
import sys
import pcbnew

src, dst = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
pro = os.path.splitext(src)[0] + ".kicad_pro"
pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
assert b.GetCopperLayerCount() == 6, "expected the 6-layer board"
b.SetCopperLayerCount(10)
I = [None, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.In5_Cu, pcbnew.In6_Cu, pcbnew.In7_Cu, pcbnew.In8_Cu]
ls = b.GetEnabledLayers()
for l in I[1:]:
    ls.AddLayer(l)
b.SetEnabledLayers(ls)
vis = b.GetVisibleLayers()
for l in I[1:]:
    vis.AddLayer(l)
b.SetVisibleLayers(vis)
moved = 0
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_VIA_T and t.GetLayer() == I[4]:
        t.SetLayer(I[8])
        moved += 1
print(moved, "tracks In4 -> In8")
gnd_src = None
for z in list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]:
    old = [int(l) for l in z.GetLayerSet().Seq()]
    inner = [l for l in old if l in I[1:5]]
    if not inner:
        continue
    new = pcbnew.LSET()
    for l in old:
        if l not in I[1:5]:
            new.AddLayer(l)
    if z.GetIsRuleArea():
        if set(inner) == set(I[1:5]):
            for l in I[1:]:
                new.AddLayer(l)
        elif set(inner) == {I[1], I[4]}:
            for l in (I[1], I[6], I[8]):
                new.AddLayer(l)
        else:
            for l in inner:
                new.AddLayer(I[8] if l == I[4] else l)
        z.SetLayerSet(new)
    else:
        if I[4] in inner:
            assert inner == [I[4]], "a pour on In4 and another layer"
            z.SetLayer(I[8])
            z.SetZoneName((z.GetZoneName() or "GND").replace("In4", "In8"))
        if inner == [I[1]] and z.GetNetname() == "GND":
            gnd_src = z
assert gnd_src is not None
z6 = gnd_src.Duplicate(False)
z6 = pcbnew.Cast_to_ZONE(z6) if hasattr(pcbnew, "Cast_to_ZONE") else z6
z6.SetLayer(I[6])
z6.SetZoneName("GND plane In6")
b.Add(z6)
for l, t in ((I[1], pcbnew.LT_POWER), (I[2], pcbnew.LT_SIGNAL), (I[3], pcbnew.LT_POWER), (I[4], pcbnew.LT_POWER),
             (I[5], pcbnew.LT_SIGNAL), (I[6], pcbnew.LT_POWER), (I[7], pcbnew.LT_SIGNAL), (I[8], pcbnew.LT_POWER)):
    b.SetLayerType(l, t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
stem = os.path.splitext(dst)[0]
if pro_text is not None:
    open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
dru = os.path.splitext(src)[0] + ".kicad_dru"
if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
    shutil.copyfile(dru, stem + ".kicad_dru")
print("written", dst, "-", b.GetCopperLayerCount(), "copper layers")

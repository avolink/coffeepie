"""mb12_convert.py SRC DST - the mainboard from 10 to 12 copper layers: a third supply-plane layer and a fourth ground
plane, both on the processor's side of the stack, where the supply balls are:

    F.Cu   signal
    In1    GND
    In2    signal
    In3    supply planes
    In4    supply planes
    In5    signal
    In6    GND
    In7    signal
    In8    GND (+ a few old tracks)
    In9    supply planes                new: two layers from the processor / memory / PMIC face
    In10   GND                          new: the reference of the bottom face
    B.Cu   signal (processor, memory, PMIC)

Nothing that exists moves: In1 .. In8 keep their copper.  The keep-out rule areas that hold every inner layer hold the
two new ones too, the ground-only ones (In1 / In6 / In8) also In10; In10 gets a ground plane with In8's outline.  The
open links are the same as before - the new layers are for plane_plan.py (33 rails on three layers instead of two)."""
import os
import shutil
import sys
import pcbnew

src, dst = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
pro = os.path.splitext(src)[0] + ".kicad_pro"
pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
assert b.GetCopperLayerCount() == 10, "expected the 10-layer board"
b.SetCopperLayerCount(12)
I = [None, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.In5_Cu, pcbnew.In6_Cu, pcbnew.In7_Cu, pcbnew.In8_Cu,
     pcbnew.In9_Cu, pcbnew.In10_Cu]
ls = b.GetEnabledLayers()
vis = b.GetVisibleLayers()
for l in I[9:]:
    ls.AddLayer(l)
    vis.AddLayer(l)
b.SetEnabledLayers(ls)
b.SetVisibleLayers(vis)
gnd_src = None
n_all = n_gnd = 0
for z in list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]:
    inner = [int(l) for l in z.GetLayerSet().Seq() if int(l) in [int(q) for q in I[1:9]]]
    if z.GetIsRuleArea():
        lset = z.GetLayerSet()
        if set(inner) == {int(q) for q in I[1:9]}:
            lset.AddLayer(I[9])
            lset.AddLayer(I[10])
            z.SetLayerSet(lset)
            n_all += 1
        elif set(inner) == {int(I[1]), int(I[6]), int(I[8])}:
            lset.AddLayer(I[10])
            z.SetLayerSet(lset)
            n_gnd += 1
    elif inner == [int(I[8])] and z.GetNetname() == "GND":
        gnd_src = z
assert gnd_src is not None, "no ground plane on In8"
z10 = gnd_src.Duplicate(False)
z10 = pcbnew.Cast_to_ZONE(z10) if hasattr(pcbnew, "Cast_to_ZONE") else z10
z10.SetLayer(I[10])
z10.SetZoneName("GND plane In10")
b.Add(z10)
b.SetLayerType(I[9], pcbnew.LT_POWER)
b.SetLayerType(I[10], pcbnew.LT_POWER)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
stem = os.path.splitext(dst)[0]
if pro_text is not None:
    open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
dru = os.path.splitext(src)[0] + ".kicad_dru"
if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
    shutil.copyfile(dru, stem + ".kicad_dru")
print("keep-outs: %d on every inner layer, %d ground-only extended" % (n_all, n_gnd))
print("written", dst, "-", b.GetCopperLayerCount(), "copper layers, thickness %.2f mm" % pcbnew.ToMM(b.GetDesignSettings().GetBoardThickness()))

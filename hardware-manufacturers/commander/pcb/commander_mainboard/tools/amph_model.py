"""Amphenol 12402072E512A STEP -> the footprint's 3D frame, written as STEP (for KiCad) and DAE (for SketchUp).
Frame (KiCad 3D model frame of the footprint): origin = centre of the receptacle's mouth at the height of the board's
top face; X along the mouth's width; Y = -(depth into the board) (KiCad's y down = into the board); Z up.
Read from the vendor STEP: x = width (centre at -3.05), y = DOWN (board top at y 0.20, axis at 0.30 = 0.10 below the
board top, shell bottom at 1.875), z = depth with the mouth at z +2.54.
usage: python amph_model.py C-12402072.stp ../../commander_hub/lib/3d/Amphenol_12402072E512A.step out.dae
(needs gmsh, numpy, trimesh: pip install gmsh trimesh scipy networkx fast_simplification)"""
import sys
import gmsh
import numpy as np
import trimesh

C, YT, ZM = -3.05, 0.20, 2.54
# X3 = x - C ; Y3 = z - ZM ; Z3 = YT - y      (a proper rotation: det = +1)
M = [1, 0, 0, -C,
     0, 0, 1, -ZM,
     0, -1, 0, YT,
     0, 0, 0, 1]
gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 0)
v = gmsh.model.occ.importShapes(sys.argv[1])
gmsh.model.occ.affineTransform(v, M)
gmsh.model.occ.synchronize()
b = gmsh.model.getBoundingBox(-1, -1)
print("bounds X %.2f..%.2f Y %.2f..%.2f Z %.2f..%.2f" % (b[0], b[3], b[1], b[4], b[2], b[5]))
gmsh.write(sys.argv[2])
gmsh.option.setNumber("Mesh.MeshSizeMax", 0.6)
gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 10)
gmsh.model.mesh.generate(2)
tags, coords, _ = gmsh.model.mesh.getNodes()
_, nodes = gmsh.model.mesh.getElementsByType(2)
gmsh.finalize()
idx = {int(t): i for i, t in enumerate(tags)}
V = np.asarray(coords).reshape(-1, 3)
F = np.vectorize(idx.get)(np.asarray(nodes, dtype=np.int64).reshape(-1, 3))
mesh = trimesh.Trimesh(V, F, process=True)
mesh.fix_normals()
if len(mesh.faces) > 40000:
    mesh = mesh.simplify_quadric_decimation(face_count=40000)
print("faces", len(mesh.faces))
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glb_to_dae import write_dae      # noqa: E402
write_dae(sys.argv[3], [mesh], [(0.80, 0.80, 0.82)])

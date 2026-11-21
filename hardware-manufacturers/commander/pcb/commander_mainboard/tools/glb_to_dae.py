#!/usr/bin/env python3
"""glb_to_dae.py IN.glb OUT.dae [OUT.stl] - KiCad's GLB export -> one Collada file SketchUp imports with colours.

Run with a Python that has trimesh + pycollada (e.g. a venv: pip install trimesh pycollada numpy networkx lxml).
KiCad writes glTF in metres, Y up, the board's y along +Z.  Written here: millimetres, right-handed, Z up:
    X = board x,  Y = -(board y),  Z = height above the board's middle plane
i.e. the board seen from above exactly as in KiCad, its own origin (KiCad's page origin) kept.  The tens of thousands
of part meshes are merged into one mesh per colour, so SketchUp gets a handful of objects instead of 30 000.
"""
import collections
import sys

import numpy as np
import trimesh


def color_of(m):
    try:
        mat = m.visual.material
        c = getattr(mat, "baseColorFactor", None)
        if c is None:
            c = getattr(mat, "main_color", None)
        c = np.array(c, dtype=float)
        if c.max() > 1.0:
            c = c / 255.0
        return tuple(np.round(c[:3], 2))
    except Exception:          # noqa: BLE001
        try:
            vc = m.visual.to_color().vertex_colors
            return tuple(np.round(np.array(vc[:, :3]).mean(axis=0) / 255.0, 2))
        except Exception:      # noqa: BLE001
            return (0.5, 0.5, 0.5)


def write_dae(path, meshes, cols):
    """A minimal COLLADA 1.4.1 file: millimetres, Z up, one coloured triangle mesh per colour group (SketchUp reads
    <unit> and <up_axis>; trimesh's own writer leaves the unit out and the colours black)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" '
                'version="1.4.1">\n<asset><unit name="millimeter" meter="0.001"/><up_axis>Z_UP</up_axis></asset>\n')
        f.write("<library_effects>\n")
        for i, c in enumerate(cols):
            f.write('<effect id="fx%d"><profile_COMMON><technique sid="t"><lambert><diffuse><color>%.3f %.3f %.3f 1'
                    '</color></diffuse></lambert></technique></profile_COMMON></effect>\n' % (i, c[0], c[1], c[2]))
        f.write("</library_effects>\n<library_materials>\n")
        for i, c in enumerate(cols):
            f.write('<material id="mat%d" name="kicad_%02x%02x%02x"><instance_effect url="#fx%d"/></material>\n'
                    % (i, int(c[0] * 255), int(c[1] * 255), int(c[2] * 255), i))
        f.write("</library_materials>\n<library_geometries>\n")
        for i, m in enumerate(meshes):
            v = np.asarray(m.vertices, dtype=float)
            t = np.asarray(m.faces, dtype=np.int64)
            f.write('<geometry id="g%d"><mesh><source id="g%dp"><float_array id="g%dpa" count="%d">' % (i, i, i, v.size))
            f.write(" ".join("%.4f" % x for x in v.ravel()))
            f.write('</float_array><technique_common><accessor source="#g%dpa" count="%d" stride="3"><param name="X" '
                    'type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor>'
                    '</technique_common></source><vertices id="g%dv"><input semantic="POSITION" source="#g%dp"/>'
                    '</vertices><triangles material="m%d" count="%d"><input semantic="VERTEX" source="#g%dv" offset="0"/><p>'
                    % (i, len(v), i, i, i, len(t), i))
            f.write(" ".join(map(str, t.ravel())))
            f.write("</p></triangles></mesh></geometry>\n")
        f.write('</library_geometries>\n<library_visual_scenes><visual_scene id="s">\n')
        for i in range(len(meshes)):
            f.write('<node id="n%d" name="part_%02d"><instance_geometry url="#g%d"><bind_material><technique_common>'
                    '<instance_material symbol="m%d" target="#mat%d"/></technique_common></bind_material>'
                    '</instance_geometry></node>\n' % (i, i, i, i, i))
        f.write('</visual_scene></library_visual_scenes>\n<scene><instance_visual_scene url="#s"/></scene>\n</COLLADA>\n')


def main():
    src, dst = sys.argv[1], sys.argv[2]
    scene = trimesh.load(src, force="scene")
    groups = collections.defaultdict(list)
    for m in scene.dump():
        if not isinstance(m, trimesh.Trimesh) or len(m.faces) == 0:
            continue
        groups[color_of(m)].append(m)
    R = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=float)      # (x, y, z) -> (x, -z, y)
    S = np.diag([1000.0, 1000.0, 1000.0, 1.0])
    out, cols = [], []
    for col, ms in sorted(groups.items()):
        m = trimesh.util.concatenate([trimesh.Trimesh(vertices=x.vertices, faces=x.faces, process=False) for x in ms])
        m.apply_transform(S @ R)
        m.merge_vertices()
        m.update_faces(m.nondegenerate_faces(height=1e-6))
        m.update_faces(m.unique_faces())
        m.remove_unreferenced_vertices()
        # SketchUp's COLLADA importer gives up on very large meshes: pieces of at most CHUNK triangles
        CHUNK = 20000                   # (keeps each piece under 65 535 vertices)
        for k in range(0, len(m.faces), CHUNK):
            part = trimesh.Trimesh(vertices=m.vertices, faces=m.faces[k:k + CHUNK], process=False)
            part.remove_unreferenced_vertices()
            out.append(part)
            cols.append(col)
    write_dae(dst, out, cols)
    allm = trimesh.util.concatenate(out)
    print("%s: %d colour groups, %d faces, bounds mm %s" % (dst, len(out), len(allm.faces), np.round(allm.bounds, 2).tolist()))
    if len(sys.argv) > 3:
        allm.export(sys.argv[3])
        print("stl:", sys.argv[3])


if __name__ == "__main__":
    main()

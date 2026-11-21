"""export_3d_text.py BOARD OUTDIR NAME - what tools/export_3d.py does, on the board file's text (KiCad's Python
segfaults on these boards): every footprint whose 3D model does not resolve gets OUTDIR/_boxes/<footprint>.wrl
(written by an earlier export_3d.py run; missing boxes are reported), the copy goes to OUTDIR/_<NAME>_3d.kicad_pcb,
then kicad-cli writes NAME.glb and NAME.step.  Run with any Python 3.
The keyboard's key footprint gets its three small parts from tools/kbd_optical_model.py (run that once on
OUTDIR/_boxes); footprints without a name (bare holes) get nothing."""
import os
import re
import subprocess
import sys

KICAD = "C:/Program Files/KiCad/10.0"
MODELS = KICAD + "/share/kicad/3dmodels"
CLI = KICAD + "/bin/kicad-cli.exe"
NO_BOX = re.compile(r"M2_CardEdge|ISP_|Pads|TestPoint|MountingHole|Fiducial|BarContacts_|BattContact_Pad|FW_InputModule_Pads")


def block_end(s, i):
    d = 0
    while True:
        c = s[i]
        if c == '"':
            i = s.index('"', i + 1)
            while s[i - 1] == "\\":
                i = s.index('"', i + 1)
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return i + 1
        i += 1


def main():
    src, outdir, name = sys.argv[1:4]
    prj = os.path.dirname(os.path.abspath(src)).replace("\\", "/")
    boxes = os.path.join(outdir, "_boxes").replace("\\", "/")

    def expand(p):
        for v in ("${KICAD10_3DMODEL_DIR}", "${KICAD9_3DMODEL_DIR}", "${KICAD8_3DMODEL_DIR}", "${KISYS3DMOD}"):
            p = p.replace(v, MODELS)
        return p.replace("${KIPRJMOD}", prj)

    def ok(p):
        p = expand(p)
        if "${" in p:
            return False
        if not os.path.isabs(p) and not re.match(r"^[A-Za-z]:", p):
            p = os.path.join(prj, p)
        base = os.path.splitext(p)[0]
        return os.path.exists(p) or any(os.path.exists(base + e) for e in (".step", ".stp", ".wrl"))

    s = open(src, encoding="utf-8").read()
    out, pos, nkeep, nbox, missing = [], 0, 0, 0, set()
    for m in re.finditer(r'\n\t\(footprint "([^"]*)"', s):
        a = m.start() + 1
        if a < pos:
            continue
        e = block_end(s, a)
        fp = s[a:e]
        fpname = m.group(1).split(":")[-1]
        models = []
        for mm in re.finditer(r'\(model "([^"]*)"', fp):
            models.append((mm.start(), block_end(fp, mm.start()), mm.group(1)))
        good = [x for x in models if ok(x[2])]
        new = fp
        for a2, e2, path in reversed(models):           # drop unresolvable model blocks, expand the good ones
            if (a2, e2, path) in good:
                new = new[:a2] + fp[a2:e2].replace(path, expand(path)) + new[e2:]
            else:
                new = new[:a2] + new[e2:]
        if good:
            nkeep += 1
        elif fpname and not NO_BOX.search(fpname):         # (a footprint without a name is a bare hole: no body)
            wrl = boxes + "/" + re.sub(r"[^A-Za-z0-9_.-]", "_", fpname) + ".wrl"
            if os.path.exists(wrl):
                k = new.rindex(")")
                new = new[:k] + '\t\t(model "%s"\n\t\t\t(offset (xyz 0 0 0))\n\t\t\t(scale (xyz 1 1 1))\n\t\t\t(rotate (xyz 0 0 0))\n\t\t)\n\t' % wrl + new[k:]
                nbox += 1
            else:
                missing.add(fpname)
        out.append(s[pos:a])
        out.append(new)
        pos = e
    out.append(s[pos:])
    tmp = os.path.join(outdir, "_%s_3d.kicad_pcb" % name)
    open(tmp, "w", encoding="utf-8").write("".join(out))
    print("%d footprints keep their model, %d get a box; no box for: %s" % (nkeep, nbox, ", ".join(sorted(missing)) or "-"))
    env = dict(os.environ, KICAD10_3DMODEL_DIR=MODELS)
    for fmt in ("glb", "step"):
        o = os.path.join(outdir, "%s.%s" % (name, fmt))
        args = [CLI, "pcb", "export", fmt, "-f", "-o", o]
        args += ["--include-soldermask", "--include-silkscreen", "--include-pads"] if fmt == "glb" else ["--subst-models"]
        args.append(tmp)
        r = subprocess.run(args, env=env, capture_output=True, text=True)
        miss = sorted({l.split("/")[-1] for l in (r.stdout + r.stderr).splitlines() if "not found" in l.lower()})
        print("%s: rc %d, %s%s" % (fmt, r.returncode, o, (" - missing: " + ", ".join(miss[:8])) if miss else ""))


if __name__ == "__main__":
    main()

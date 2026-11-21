"""report_pairs.py BOARD [OUT.txt]   (KiCad's Python)

The differential pairs of a board file (nets whose names differ only in P / N or DP / DM): routed length of each half,
the mismatch, the vias, and whether the pair is complete.  A check after automatic routing: the negotiating router
(pf_route.py) draws the halves of a pair side by side where it can but does not match their lengths."""
import collections
import sys

import pcbnew
from pcbnew import ToMM


def main():
    b = pcbnew.LoadBoard(sys.argv[1])
    out = open(sys.argv[2], "w", encoding="utf-8") if len(sys.argv) > 2 else sys.stdout
    length = collections.Counter()
    vias = collections.Counter()
    for t in b.GetTracks():
        n = t.GetNetname()
        if t.GetClass() == "PCB_VIA":
            vias[n] += 1
        else:
            length[n] += ToMM(t.GetLength())
    nets = {p.GetNetname() for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname()}
    pairs = {}
    for n in sorted(nets):
        for k, ch in enumerate(n):
            for a, c in (("P", "N"), ("P", "M")):
                if ch == a:
                    o = n[:k] + c + n[k + 1:]
                    if o in nets:
                        pairs[n] = o
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    open_nets = set()
    pads = collections.defaultdict(list)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                pads[p.GetNetname()].append(p)
    for n in set(pairs) | set(pairs.values()):
        ps = pads[n]
        first = {q.m_Uuid.AsString() for q in conn.GetConnectedItems(ps[0], 0)} | {ps[0].m_Uuid.AsString()}
        if not all(p.m_Uuid.AsString() in first for p in ps):
            open_nets.add(n)
    rows = []
    for p, n in sorted(pairs.items()):
        d = abs(length[p] - length[n])
        rows.append((d, p, n))
    print("%-22s %-22s %9s %9s %9s  vias  state" % ("P", "N", "len P", "len N", "mismatch"), file=out)
    for d, p, n in sorted(rows, reverse=True):
        print("%-22s %-22s %9.2f %9.2f %9.2f  %d / %d  %s" % (p, n, length[p], length[n], d, vias[p], vias[n],
                                                            "OPEN" if (p in open_nets or n in open_nets) else "complete"), file=out)
    print("%d pairs, %d not complete; mismatch over 1 mm: %d, over 3 mm: %d"
          % (len(rows), sum(1 for d, p, n in rows if p in open_nets or n in open_nets), sum(1 for r in rows if r[0] > 1), sum(1 for r in rows if r[0] > 3)), file=out)


if __name__ == "__main__":
    main()

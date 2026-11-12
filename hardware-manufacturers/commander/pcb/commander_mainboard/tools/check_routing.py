#!/usr/bin/env python3
"""Reads build/drc.json and separates what the routed copper is responsible for from what the
(still colliding) first placement causes.  Appends the verdict to build/routing_report.txt.

    python tools/check_routing.py            exit code 1 if a track, via or plane breaks a rule
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
NL = chr(10)
COPPER = ("Track", "Via", "Zone", "Arc")


def main():
    d = json.load(open(os.path.join(ROOT, "build", "drc.json"), encoding="utf-8"))
    mine, other = collections.Counter(), collections.Counter()
    examples = []
    for v in d.get("violations", []):
        descs = [i.get("description", "") for i in v.get("items", [])]
        if any(x.startswith(COPPER) for x in descs):
            mine[v["type"]] += 1
            if len(examples) < 25:
                pos = v["items"][0].get("pos", {}) if v.get("items") else {}
                examples.append(f'  {v["type"]}: {" | ".join(descs)[:150]} @ ({pos.get("x")}, {pos.get("y")})')
        else:
            other[v["type"]] += 1
    lines = ["", "DRC after routing (kicad-cli pcb drc):",
             f"  violations involving routed copper (tracks, vias, planes): {sum(mine.values())}  {dict(mine) if mine else ''}",
             f"  violations of the placement alone (pads / courtyards, as before routing): {sum(other.values())}  {dict(other)}",
             f"  unconnected items reported: {len(d.get('unconnected_items', []))}"] + examples
    print(NL.join(lines))
    with open(os.path.join(ROOT, "build", "routing_report.txt"), "a", encoding="utf-8") as f:
        f.write(NL.join(lines) + NL)
    return 1 if mine else 0


if __name__ == "__main__":
    sys.exit(main())

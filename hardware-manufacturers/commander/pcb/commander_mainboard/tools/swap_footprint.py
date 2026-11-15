#!/usr/bin/env python
"""swap_footprint.py BOARD REF LIBDIR NAME - replace a placed footprint by the current library version, in place.

Run with KiCad's Python.  Position, orientation, face, reference, value, symbol path and every pad's net are carried
over; tracks are not touched (they meet the new pads where the old ones were).  Used for J90 on the hub board after
its card-edge outline and courtyard were corrected in tools/gen_footprints.py.
"""
import sys

import pcbnew


def main():
    path, ref, libdir, name = sys.argv[1:5]
    b = pcbnew.LoadBoard(path)
    old = b.FindFootprintByReference(ref)
    new = pcbnew.FootprintLoad(libdir, name)
    new.SetReference(ref)
    new.SetValue(old.GetValue())
    new.SetFPID(old.GetFPID())
    b.Add(new)
    if old.IsFlipped():
        new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    new.SetPosition(old.GetPosition())
    new.SetOrientation(old.GetOrientation())
    new.SetPath(old.GetPath())
    nets = {p.GetNumber(): p.GetNet() for p in old.Pads()}
    for p in new.Pads():
        if p.GetNumber() in nets:
            p.SetNet(nets[p.GetNumber()])
    moved = max(abs(a.GetPosition().x - c.GetPosition().x) + abs(a.GetPosition().y - c.GetPosition().y)
                for a in old.Pads() for c in new.Pads() if a.GetNumber() == c.GetNumber() and a.GetNumber())
    b.Remove(old)
    pcbnew.SaveBoard(path, b)
    print("%s replaced by %s; largest pad displacement %d nm" % (ref, name, moved))


if __name__ == "__main__":
    main()

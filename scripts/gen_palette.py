#!/usr/bin/env python3
"""Build palette.json from the SysEx-verified table in the push-hack docs.

Usage: gen_palette.py path/to/ableton-push-hack/docs/push3-led-colors.md

The doc's "Full Hardware Palette" lists all 128 LED entries (R, G, B, W).
PTA's own palette only holds the 90 named entries, so many indices show the
wrong color on screen. Pad and button LEDs take the index directly.
"""

import json
import re
import sys

ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*`#([0-9A-Fa-f]{6})`\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.*?)\s*\|\s*$")
# Names the module code looks up with view.color(name).
NAMES = {"off": 0, "gray_mid": 118, "white": 120}


def main(path):
    entries = {}
    for line in open(path):
        m = ROW.match(line)
        if not m:
            continue
        i = int(m.group(1))
        r, g, b, w = (int(m.group(k)) for k in (3, 4, 5, 6))
        desc = re.sub(r"[*`]", "", m.group(7)).strip()
        entries[i] = {"index": i, "name": desc, "r": r, "g": g, "b": b, "a": 255, "w": w}
    assert sorted(entries) == list(range(128)), "palette table incomplete"
    doc = {"source": "ableton-push-hack docs/push3-led-colors.md (SysEx 0x04, Push 3 fw 2.4.5b8)",
           "byIndex": [entries[i] for i in range(128)], "byName": {n: entries[i] for n, i in NAMES.items()}}
    with open("palette.json", "w") as f:
        json.dump(doc, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])

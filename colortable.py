"""colortable.py - per-track-color dim pad shade and on-screen RGB.

The pad LEDs and the screen show the same palette index differently, so each
track color has two tuned values: the palette index of its dim pad shade and
the RGB the screen uses. The screen defaults are measured from the original
Push. colors.json holds overrides made on the device with the Color Lab
(Shift + Layout).
"""

import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "colors.json")
DEFAULT_DIM_PAD = 124  # dgray, for a color with no entry

# Dim variant of each TRACK_COLORS entry: the hardware palette's second "very
# dark" entry for the hue (docs/push3-led-colors.md in ableton-push-hack),
# chosen on the device. Index 2 keeps 68.
DEFAULT_DIM = {
    1: 66, 2: 68, 3: 70, 4: 72, 5: 74, 6: 76, 7: 78, 8: 80, 9: 82, 10: 84, 11: 86, 12: 88, 13: 90,
    14: 92, 15: 94, 16: 96, 17: 98, 18: 100, 19: 102, 20: 104, 21: 106, 22: 108, 23: 110, 24: 112,
    25: 114, 26: 116,
}

# Screen color of each track color, as the original Push draws it. Measured
# from screenshots in resources/ (track n was set to palette index n in Live;
# label text peaks at 96% of the real color, so each value is peak / 0.96, and
# the three selected tracks use their solid fill). They differ from the pad LED
# RGB, e.g. index 25 (crimson on the pads) is pink on the screen.
DEFAULT_RGB = {
    1: (237, 89, 56), 2: (211, 23, 9), 3: (251, 98, 0),
    4: (255, 51, 0), 5: (170, 115, 32), 6: (132, 73, 19),
    7: (247, 227, 62), 8: (225, 192, 0), 9: (147, 253, 23),
    10: (0, 235, 50), 11: (0, 159, 51), 12: (52, 160, 19),
    13: (0, 190, 86), 14: (0, 116, 80), 15: (0, 208, 140),
    16: (0, 187, 173), 17: (0, 114, 166), 18: (0, 108, 206),
    19: (74, 51, 182), 20: (0, 92, 100), 21: (83, 98, 225),
    22: (174, 81, 255), 23: (229, 89, 231), 24: (136, 66, 91),
    25: (255, 75, 153), 26: (255, 30, 51),
}

_dim = dict(DEFAULT_DIM)
_rgb = {}   # track color index -> (r, g, b) for the screen


def reset():
    _dim.clear()
    _dim.update(DEFAULT_DIM)
    _rgb.clear()


def load(path=PATH):
    reset()
    try:
        with open(path) as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(doc, dict) or doc.get("version") != 1:
        return False
    for key, entry in (doc.get("colors") or {}).items():
        try:
            c = int(key)
            if isinstance(entry.get("dim"), int) and 0 <= entry["dim"] <= 127:
                _dim[c] = entry["dim"]
            rgb = entry.get("rgb")
            if isinstance(rgb, list) and len(rgb) == 3:
                _rgb[c] = tuple(max(0, min(255, int(v))) for v in rgb)
        except (ValueError, AttributeError, TypeError):
            continue
    return True


def save(path=PATH):
    colors = {}
    for c in sorted(set(_dim) | set(_rgb)):
        entry = {"dim": _dim.get(c, DEFAULT_DIM_PAD)}
        if c in _rgb:
            entry["rgb"] = list(_rgb[c])
        colors[str(c)] = entry
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"version": 1, "colors": colors}, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def dim(color):
    return _dim.get(color, DEFAULT_DIM_PAD)


def screen_rgb(color):
    """RGB for the screen: a Color Lab override, else the measured default,
    else None to use the palette RGB."""
    return _rgb.get(color, DEFAULT_RGB.get(color))


def set_entry(color, dim_idx=None, rgb=None):
    if dim_idx is not None:
        _dim[color] = max(0, min(127, dim_idx))
    if rgb is not None:
        _rgb[color] = tuple(max(0, min(255, int(v))) for v in rgb)


def clear_rgb(color):
    _rgb.pop(color, None)


load()

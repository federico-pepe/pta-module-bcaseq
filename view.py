"""view.py - screen ops and LED colors for BCA Seq. No I/O, no state changes."""

import json
import os
import time

import engine as eng
import layouts

with open(os.path.join(os.path.dirname(__file__), "palette.json")) as _f:
    PALETTE = json.load(_f)


def color(name):
    e = PALETTE["byName"][name]
    return {"R": e["r"], "G": e["g"], "B": e["b"], "A": e["a"]}


def color_by_index(idx):
    e = PALETTE["byIndex"][idx]
    return {"R": e["r"], "G": e["g"], "B": e["b"], "A": e["a"]}


BTN_OFF, BTN_DIM, BTN_FULL, BTN_GREEN = 0, 118, 122, 126
PULSE_HZ = 1.0

BUTTON_CC = {
    "Play": 85, "Layout": 31, "Scale": 58, "Repeat": 56, "Accent": 57, "Shift": 49,
    "Delete": 118, "Add": 32, "Select (main)": 28, "Save": 82, "Set": 80,
    "Octave Up": 55, "Octave Down": 54, "Page Left": 62, "Page Right": 63,
    "D-Pad up": 46, "D-Pad down": 47, "D-Pad center": 91, "Jog press": 94,
    "Scene 1/4": 36, "Scene 1/4t": 37, "Scene 1/8": 38, "Scene 1/8t": 39,
    "Scene 1/16": 40, "Scene 1/16t": 41, "Scene 1/32": 42, "Scene 1/32t": 43,
}


def _pulse():
    return BTN_GREEN if int(time.time() * PULSE_HZ * 2) % 2 == 0 else BTN_OFF


def repeat_for_scene(name):
    """Top button = 1 repeat, bottom button = 8."""
    return eng.MAX_REPEAT - eng.DIVISION_NAMES.index(name)


def button_colors(state):
    e = state.engine
    held = state.button_held
    out = {}
    out["Play"] = BTN_GREEN if e.playing else BTN_FULL
    out["Layout"] = BTN_FULL if held.get("Layout") else BTN_DIM
    out["Scale"] = BTN_FULL if e.scale_menu else BTN_DIM
    out["Repeat"] = BTN_FULL if e.repeat_on else BTN_DIM
    out["Accent"] = BTN_FULL if e.accent_on else BTN_DIM
    out["Shift"] = BTN_FULL if e.shift else BTN_DIM
    out["Delete"] = BTN_FULL if e.delete else BTN_DIM
    out["Add"] = BTN_FULL if held.get("Add") else (BTN_DIM if len(e.tracks) < eng.MAX_TRACKS else BTN_OFF)
    out["Save"] = BTN_FULL if held.get("Save") else BTN_DIM
    out["Set"] = BTN_FULL if state.browser_active else BTN_DIM

    out["Page Left"] = BTN_DIM if e.track_page > 0 else BTN_OFF
    out["Page Right"] = BTN_DIM if layouts.can_page_right(e) else BTN_OFF
    if e.layout == 1:
        out["Octave Up"] = BTN_FULL if held.get("Octave Up") else BTN_DIM
        out["Octave Down"] = BTN_FULL if held.get("Octave Down") else BTN_DIM
    else:
        out["Octave Up"] = out["Octave Down"] = BTN_OFF

    out["D-Pad up"] = BTN_DIM if state.browser_active and state.browser_cursor > 0 else BTN_OFF
    out["D-Pad down"] = BTN_DIM if state.browser_active and \
        state.browser_cursor < len(state.browser_names) else BTN_OFF
    out["D-Pad center"] = out["Jog press"] = BTN_DIM if state.browser_active else BTN_OFF

    out["Select (main)"] = BTN_FULL if (e.edit_step() or e.scale_menu) else BTN_DIM

    rt = e.tracks[e.rate_track] if e.rate_track < len(e.tracks) else e.tracks[0]
    for name in eng.DIVISION_NAMES:
        if e.repeat_on:
            active = e.repeat_count == repeat_for_scene(name)
        else:
            active = rt["rate"] == name
        out[name] = _pulse() if active else BTN_DIM
    return out


def pad_colors(state):
    if state.browser_active:
        return [[0] * 8 for _ in range(8)]
    return layouts.pad_colors(state.engine)


# -- screen -------------------------------------------------------------------

W, H = 960, 160
LABEL_BASELINE = 16
VALUE_BASELINE = 46
VALUE_SCALE = 2
CHAR_W = 7
STRIP_Y, STRIP_H = 122, 36   # track strip with edit-mode corners
POPUP_Y, POPUP_H, POPUP_PAD = 8, 80, 20


def _text(x, baseline, s, c, scale=None):
    p = {"x": x, "baseline": baseline, "s": s, "c": c}
    if scale:
        p["scale"] = scale
    return {"kind": "text", "params": p}


def _rect(x, y, w, h, c):
    return {"kind": "rect", "params": {"x": x, "y": y, "w": w, "h": h, "c": c}}


def note_name(n):
    n = max(0, min(127, n))
    return "%s%d" % (["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][n % 12], n // 12 - 2)


def scale_label(name):
    return eng.SCALE_LABELS.get(name) or name.replace("_", " ").title()


def corners(x, y, w, h, c, arm=10, th=1):
    return [
        _rect(x, y, arm, th, c), _rect(x, y, th, arm, c),
        _rect(x + w - arm, y, arm, th, c), _rect(x + w - th, y, th, arm, c),
        _rect(x, y + h - th, arm, th, c), _rect(x, y + h - arm, th, arm, c),
        _rect(x + w - arm, y + h - th, arm, th, c), _rect(x + w - th, y + h - arm, th, arm, c),
    ]


def draw(state):
    e = state.engine
    black, white = color("off"), color("white")
    ops = [_rect(0, 0, W, H, black)]

    if state.browser_active:
        ops += _browser_ops(state, black, white)
    elif e.scale_menu:
        ops += _scale_ops(e, white)
    else:
        ops += _sequencer_ops(e)

    if state.popup_title is not None and time.monotonic() < state.popup_until:
        ops += _popup_ops(state.popup_title, state.popup_body, black, white)
    return {"ops": ops, "failed": 0}


def _scale_ops(e, white):
    p = e.pattern
    cells = [("Key", NOTE_NAMES[p["root"]]),
             ("Scale", scale_label(p["scale"])),
             ("In Key", "On" if p["in_key"] else "Off")]
    ops = []
    for i, (label, value) in enumerate(cells):
        x = i * (W // 8) + 4
        ops += [_text(x, LABEL_BASELINE, label, white), _text(x, VALUE_BASELINE, value, white, VALUE_SCALE)]
    return ops


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Edit-mode knobs: encoder index (1-7) -> short label. Encoder 0 is Pitch, drawn big.
KNOB_LABELS = ["VEL", "GATE", "PROB", "OFF", "MIDI", "REP", "LEN"]
KNOB_FIELD = {"VEL": "vel", "GATE": "gate", "PROB": "prob", "OFF": "offset",
              "MIDI": "channel", "REP": "repeat", "LEN": "length"}
KNOB_RANGE = {"VEL": (1, 127), "GATE": (2, 99), "PROB": (0, 100), "OFF": (-45, 45),
              "MIDI": (1, 16), "REP": (1, eng.MAX_REPEAT), "LEN": (1, eng.STEPS)}
KNOB_R = 11
KNOB_ROW_Y = (40, 88)
BAR_Y, BAR_H = 138, 6
DIVIDER = 124  # dgray palette index


def display_step(e, ti):
    """Step whose values a column shows: selected, else playing, else first."""
    t = e.tracks[ti]
    si = e.sel.get(ti)
    if si is None:
        si = t["_current_step"] if t["_current_step"] >= 0 else 0
    return t["steps"][si]


def knob_value(t, s, label):
    f = KNOB_FIELD[label]
    return t[f] if f in ("channel", "length") else s[f]


def rate_label(t):
    return t["rate"].replace("Scene ", "")


def _bar(x, w, c, frac):
    fill = max(2, int(round(w * max(0.0, min(1.0, frac)))))
    return [_rect(x, BAR_Y, w, BAR_H, color_by_index(124)), _rect(x, BAR_Y, fill, BAR_H, c)]


def _ring(cx, cy, r, c, frac):
    """Dim full ring plus a two-pixel sweep in the track color."""
    ops = [{"kind": "arc", "params": {"cx": cx, "cy": cy, "r": r, "frac": 1.0, "c": color_by_index(124)}}]
    if frac > 0:
        for rr in (r, r - 1):
            ops.append({"kind": "arc", "params": {"cx": cx, "cy": cy, "r": rr, "frac": frac, "c": c}})
    return ops


def _sequencer_ops(e):
    ops = []
    tracks = layouts.page_tracks(e)
    n = layouts.current(e).tracks_per_page
    col_w = W // n
    es = e.edit_step()
    editing = es is not None and es[0] in tracks
    now = time.monotonic()
    white = color("white")
    shown = e.active_param[0] if (e.active_param and now < e.active_param[1]) else None

    for slot, ti in enumerate(tracks):
        t = e.tracks[ti]
        x = slot * col_w
        hot = editing and ti == es[0]
        c = white if hot else color_by_index(t["color"])
        rate_x = x + col_w - 8 - CHAR_W * len(rate_label(t))
        ops.append(_text(x + 8, LABEL_BASELINE, t["name"], c))
        ops.append(_text(rate_x, LABEL_BASELINE, rate_label(t), white if hot else color("gray_mid")))

        if not editing:
            note = note_name(t["_last_note"]) if t["_last_note"] is not None else "-"
            ops.append(_text(x + 8, 76, note, c, 3))
            ops += _bar(x + 8, col_w - 24, c, t["_progress"])
            continue

        s = display_step(e, ti)
        ops.append(_text(x + 8, 66, note_name(s["pitch"]), c, 3))
        ops.append(_text(x + 8, 80, "PITCH", c))
        pitch_hot = hot and shown == 0
        if pitch_hot:
            ops.append(_rect(x + 8, 84, CHAR_W * 5, 2, c))
        spacing = (col_w - 132) // 3
        for j, label in enumerate(KNOB_LABELS):
            cx = x + 110 + (j % 4) * spacing
            cy = KNOB_ROW_Y[j // 4]
            lo, hi = KNOB_RANGE[label]
            val = knob_value(t, s, label)
            ops += _ring(cx, cy, KNOB_R, c, (val - lo) / float(hi - lo))
            text = str(val) if (hot and shown == j + 1) else label
            ops.append(_text(cx - CHAR_W * len(text) // 2, cy + KNOB_R + 14, text, c))
        ops += _bar(x + 8, col_w - 24, c, t["_progress"])
        if slot > 0 and not hot and tracks[slot - 1] != es[0]:
            ops.append(_rect(x, 8, 1, 144, color_by_index(DIVIDER)))
        if hot:
            ops += corners(x + 2, 1, col_w - 4, H - 3, white)

    if not editing:
        ops.append(_text(8, 154, _status_line(e), color("gray_mid")))
    return ops


def _status_line(e):
    p = e.pattern
    return "%d BPM   %s %s   %s" % (
        p["bpm"], NOTE_NAMES[p["root"]], scale_label(p["scale"]),
        "In Key" if p["in_key"] else "Chromatic")


def _browser_ops(state, black, white):
    items = ["New"] + state.browser_names
    cursor = max(0, min(len(items) - 1, state.browser_cursor))
    ops = [_text(20, LABEL_BASELINE, "SET: SEQUENCES", white)]
    start = max(0, min(cursor - 3, max(0, len(items) - 6)))
    for i in range(start, min(len(items), start + 6)):
        y = 30 + (i - start) * 20
        if i == cursor:
            ops += [_rect(20, y, 400, 20, white), _text(28, y + 15, items[i], black)]
        else:
            ops.append(_text(28, y + 15, items[i], white))
    return ops


def _popup_ops(title, body, black, white):
    title_w = CHAR_W * len(title)
    body_w = CHAR_W * VALUE_SCALE * len(body) if body else 0
    box_w = min(920, max(title_w, body_w) + POPUP_PAD * 2)
    box_x = (W - box_w) // 2
    ops = [_rect(box_x, POPUP_Y, box_w, POPUP_H, white),
           _text(box_x + (box_w - title_w) // 2, POPUP_Y + 22, title, black)]
    if body:
        ops.append(_text(box_x + (box_w - body_w) // 2, POPUP_Y + 62, body, black, VALUE_SCALE))
    return ops

"""layouts.py - pad grid and screen columns for each Layout.

A Layout only changes how state maps to pads. It never changes what the
sequencer does. Pads use (col, row) with row 0 at the bottom, like Push.
Each quadrant is 4x4. Slot 0 = top-left, 1 = top-right, 2 = bottom-left,
3 = bottom-right.
"""

import engine as eng

import time

OFF = 0
STEP_ON = 120       # white
PLAYHEAD = 126      # pure green
PITCH_WHITE = 120
BLINK_HZ = 2.0


def quadrant(col, row):
    """Slot (0-3) for a pad."""
    return (0 if row >= 4 else 2) + (0 if col < 4 else 1)


def step_index(col, row):
    """Step 0-15 inside a quadrant: left to right, then down."""
    return (3 - (row % 4)) * 4 + (col % 4)


def pitch_index(col, row):
    """Pitch pad 0-15 inside a quadrant: left to right, then up."""
    return (row % 4) * 4 + (col % 4)


def _pad_for_step(slot, i):
    """(col, row) of step i inside quadrant slot."""
    col0 = 0 if slot in (0, 2) else 4
    row0 = 4 if slot in (0, 1) else 0
    return col0 + i % 4, row0 + 3 - i // 4


class Layout1:
    name = "Layout 1"
    tracks_per_page = 4
    # slot -> track offset on the page
    seq_slots = {0: 0, 1: 1, 2: 2, 3: 3}


class Layout2:
    name = "Layout 2"
    tracks_per_page = 2
    seq_slots = {0: 0, 2: 1}   # TL = first track, BL = second
    pitch_slots = {1: 0, 3: 1}  # TR edits TL track, BR edits BL track


LAYOUTS = [Layout1, Layout2]


def current(e):
    return LAYOUTS[e.layout]


def first_track(e):
    return e.track_page * current(e).tracks_per_page


def page_tracks(e):
    """Track indices shown on the current page (may be fewer than a full page)."""
    lay = current(e)
    start = first_track(e)
    return [i for i in range(start, start + lay.tracks_per_page) if i < len(e.tracks)]


def can_page_right(e):
    return (e.track_page + 1) * current(e).tracks_per_page < len(e.tracks)


def switch_layout(e, new):
    """Keep the first visible track on screen when the page size changes."""
    first = first_track(e)
    e.layout = new % len(LAYOUTS)
    e.track_page = first // current(e).tracks_per_page


def track_for_slot(e, slot):
    lay = current(e)
    off = lay.seq_slots.get(slot)
    if off is None:
        return None
    idx = first_track(e) + off
    return idx if idx < len(e.tracks) else None


def pitch_track_for_slot(e, slot):
    lay = current(e)
    off = getattr(lay, "pitch_slots", {}).get(slot)
    if off is None:
        return None
    idx = first_track(e) + off
    return idx if idx < len(e.tracks) else None


def pad_press(e, col, row):
    """Handle a pad press. Shift selects without toggling."""
    slot = quadrant(col, row)
    ti = track_for_slot(e, slot)
    if ti is not None:
        si = step_index(col, row)
        if si >= e.tracks[ti]["length"]:
            return
        if e.shift:
            if e.sel.get(ti) == si:
                e.deselect(ti)
            else:
                e.select_step(ti, si)
        else:
            e.tap_step(ti, si)
        return
    pt = pitch_track_for_slot(e, slot)
    if pt is not None:
        si = e.sel.get(pt)
        if si is None:
            return
        p = e.pattern
        notes = eng.grid_pitches(p["root"], p["scale"], p["in_key"], e.octave)
        note = notes[pitch_index(col, row)]
        if note <= 127:
            e.set_pitch(pt, si, note)
            e.edit_track = pt
            e.rate_track = pt


def pad_colors(e):
    """8x8 palette indices, row 0 = bottom."""
    grid = [[OFF] * 8 for _ in range(8)]
    for slot in (0, 1, 2, 3):
        ti = track_for_slot(e, slot)
        if ti is not None:
            t = e.tracks[ti]
            for i in range(eng.STEPS):
                col, row = _pad_for_step(slot, i)
                if i >= t["length"]:
                    continue
                s = t["steps"][i]
                if t["_current_step"] == i:
                    color = PLAYHEAD
                elif e.sel.get(ti) == i:
                    # selected step blinks so it differs from other white steps
                    color = STEP_ON if int(time.monotonic() * BLINK_HZ) % 2 == 0 else t["color"]
                elif s["on"]:
                    color = STEP_ON
                else:
                    color = t["color"]
                grid[row][col] = color
            continue
        pt = pitch_track_for_slot(e, slot)
        if pt is not None:
            _paint_pitch(e, grid, slot, pt)
    return grid


def _paint_pitch(e, grid, slot, track_idx):
    p = e.pattern
    notes = eng.grid_pitches(p["root"], p["scale"], p["in_key"], e.octave)
    in_scale = set(eng.scale_notes(p["root"], p["scale"]))
    color = e.tracks[track_idx]["color"]
    col0 = 0 if slot in (0, 2) else 4
    row0 = 4 if slot in (0, 1) else 0
    for i, note in enumerate(notes):
        c, r = col0 + i % 4, row0 + i // 4
        if note > 127:
            grid[r][c] = OFF
        elif note % 12 == p["root"]:
            grid[r][c] = color
        elif p["in_key"] or note % 12 in in_scale:
            grid[r][c] = PITCH_WHITE
        else:
            grid[r][c] = OFF

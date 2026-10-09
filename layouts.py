"""layouts.py - pad grid and screen columns for each Layout.

A Layout only changes how state maps to pads. It never changes what the
sequencer does. Pads use (col, row) with row 0 at the bottom, like Push.
Each quadrant is 4x4. Slot 0 = top-left, 1 = top-right, 2 = bottom-left,
3 = bottom-right.
"""

import time

import colortable
import engine as eng

OFF = 0
STEP_SELECTED = 120  # white
PLAYHEAD = 126       # pure green
PITCH_WHITE = 120
STEP_DIM_WHITE = 118   # Layout 3 step grid, empty step. Check on the device.
ARMED = 120            # Layout 3 armed pitch pad: pure white, max brightness. Same as the in-scale pads, check on the device.


def dim(color):
    return colortable.dim(color)


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
    has_octave = False
    arm_mode = False


class Layout2:
    name = "Layout 2"
    tracks_per_page = 2
    seq_slots = {0: 0, 2: 1}   # TL = first track, BL = second
    pitch_slots = {1: 0, 3: 1}  # TR edits TL track, BR edits BL track
    has_octave = True
    arm_mode = False


class Layout3:
    name = "Layout 3"
    tracks_per_page = 3
    seq_slots = {}
    pitch_slots = {1: 0, 2: 1, 3: 2}   # TR, BL, BR edit the first, second, third track
    shared_grid_slot = 0               # TL: one step grid for grid_track()
    has_octave = True
    arm_mode = True                    # a pitch pad arms a note, a step pad adds it


LAYOUTS = [Layout1, Layout2, Layout3]


def current(e):
    return LAYOUTS[e.layout]


def has_octave(e):
    return current(e).has_octave


def first_track(e):
    return e.track_page * current(e).tracks_per_page


def page_tracks(e):
    """Track indices shown on the current page (may be fewer than a full page)."""
    lay = current(e)
    start = first_track(e)
    return [i for i in range(start, start + lay.tracks_per_page) if i < len(e.tracks)]


def grid_track(e):
    """Layout 3: the track shown on the step grid. Falls back to the first track on the page."""
    page = page_tracks(e)
    if e.grid_track in page:
        return e.grid_track
    return page[0] if page else 0


def can_page_right(e):
    return (e.track_page + 1) * current(e).tracks_per_page < len(e.tracks)


def switch_layout(e, new):
    """Keep the first visible track on screen when the page size changes."""
    first = first_track(e)
    e.layout = new % len(LAYOUTS)
    e.track_page = first // current(e).tracks_per_page
    e.armed = None


def track_for_slot(e, slot):
    lay = current(e)
    if getattr(lay, "shared_grid_slot", None) == slot:
        return grid_track(e) if page_tracks(e) else None
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


def editing(e):
    """True when the screen shows the edit view: a step of a track on this page is selected."""
    es = e.edit_step()
    return es is not None and es[0] in page_tracks(e)


def slen_track(e, enc_idx):
    """Main screen: each track owns 8 / tracks_per_page encoders. The second one
    is its S LEN knob. Returns the track index for that encoder, else None."""
    per = 8 // current(e).tracks_per_page
    slot, role = divmod(enc_idx, per)
    page = page_tracks(e)
    return page[slot] if role == 1 and slot < len(page) else None


def slen_encoder(e, slot):
    return slot * (8 // current(e).tracks_per_page) + 1


def pitch_ref_track(e):
    """Track whose pitch grid the octave OSD describes: the last touched track
    if it is on the page, else the first track on the page."""
    page = page_tracks(e)
    return e.rate_track if e.rate_track in page else (page[0] if page else 0)


def pad_press(e, col, row):
    """Handle a pad press. Shift selects without toggling."""
    if e.color_picker_track is not None:
        color = eng.color_picker_grid().get((row, col))
        if color is not None:
            e.set_track_color(e.color_picker_track, color)
        return
    slot = quadrant(col, row)
    ti = track_for_slot(e, slot)
    if ti is not None:
        si = step_index(col, row)
        if si >= e.tracks[ti]["length"]:
            return
        if e.accent_held or e.repeat_held:
            e.apply_hold(ti, si)
        elif e.shift:
            if e.sel.get(ti) == si:
                e.deselect(ti)
            else:
                e.select_step(ti, si)
        elif current(e).arm_mode and e.armed is not None:
            e.toggle_note(ti, si, e.armed[1], activate=True)
        else:
            e.tap_step(ti, si)
        return
    pt = pitch_track_for_slot(e, slot)
    if pt is not None:
        if current(e).arm_mode:
            root, scale = e.key_of(pt)
            note = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave)[pitch_index(col, row)]
            if note > 127:
                return
            e.armed = None if e.armed == (pt, note) else (pt, note)
            e.grid_track = pt
            e.rate_track = pt
            return
        si = e.sel.get(pt)
        if si is None:
            return
        root, scale = e.key_of(pt)
        notes = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave)
        note = notes[pitch_index(col, row)]
        if note <= 127:
            e.toggle_note(pt, si, note)
            e.edit_track = pt
            e.rate_track = pt


def pad_colors(e):
    """8x8 palette indices, row 0 = bottom."""
    grid = [[OFF] * 8 for _ in range(8)]
    if e.color_picker_track is not None:
        for (row, col), color in eng.color_picker_grid().items():
            grid[row][col] = color
        return grid
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
                    color = STEP_SELECTED
                elif s["on"]:
                    color = t["color"]
                elif current(e).arm_mode:
                    color = STEP_DIM_WHITE
                else:
                    color = dim(t["color"])
                grid[row][col] = color
            continue
        pt = pitch_track_for_slot(e, slot)
        if pt is not None:
            _paint_pitch(e, grid, slot, pt)
    return grid


def _paint_pitch(e, grid, slot, track_idx):
    in_key = e.pattern["in_key"]
    root, scale = e.key_of(track_idx)
    notes = eng.grid_pitches(root, scale, in_key, e.octave)
    in_scale = set(eng.scale_notes(root, scale))
    t = e.tracks[track_idx]
    color = t["color"]
    es = e.sel.get(track_idx)
    in_step = set(t["steps"][es]["pitches"]) if es is not None and t["steps"][es]["on"] else set()
    col0 = 0 if slot in (0, 2) else 4
    row0 = 4 if slot in (0, 1) else 0
    for i, note in enumerate(notes):
        c, r = col0 + i % 4, row0 + i // 4
        if note > 127:
            grid[r][c] = OFF
        elif note % 12 == root or note in in_step:
            grid[r][c] = color
        elif in_key or note % 12 in in_scale:
            grid[r][c] = PITCH_WHITE
        else:
            grid[r][c] = OFF
        if e.armed == (track_idx, note) and note <= 127:
            grid[r][c] = ARMED
    # the pad of a note that just sounded flashes green
    if time.monotonic() < t["_lit_until"]:
        for i, note in enumerate(notes):
            if note in t["_lit_notes"] and note <= 127:
                grid[row0 + i // 4][col0 + i % 4] = PLAYHEAD

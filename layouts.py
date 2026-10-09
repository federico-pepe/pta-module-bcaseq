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
STEP_DIM_WHITE = 119   # Layout 3 step grid, empty step. Check on the device.
PITCH_DIM_WHITE = 118  # pitch pad in key and not selected. Check on the device.
LONG_PRESS_DIM = 119   # dark gray: dimmed pads during a long press, darker than the dim white
SCREEN_TRACKS = 4      # tracks on the screen, in every layout
LONG_PRESS_S = 0.4     # a pad held this long shows a highlight and does not act


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
    pad_group = 4           # pad window = the screen page
    # slot -> track offset in the pad window
    seq_slots = {0: 0, 1: 1, 2: 2, 3: 3}
    has_octave = False
    arm_mode = False


class Layout2:
    name = "Layout 2"
    pad_group = 2           # the pair of tracks that holds the working track
    seq_slots = {0: 0, 2: 1}   # TL = first track, BL = second
    pitch_slots = {1: 0, 3: 1}  # TR edits TL track, BR edits BL track
    has_octave = True
    arm_mode = True


class Layout3:
    name = "Layout 3"
    pad_group = 3           # the triple of tracks that holds the working track
    seq_slots = {}
    pitch_slots = {1: 0, 2: 1, 3: 2}   # TR, BL, BR edit the first, second, third track
    shared_grid_slot = 0               # TL: one step grid for the working track
    has_octave = True
    arm_mode = True                    # a pitch pad arms a note, a step pad adds it


LAYOUTS = [Layout1, Layout2, Layout3]


def current(e):
    return LAYOUTS[e.layout]


def has_octave(e):
    return current(e).has_octave


def first_track(e):
    """First track on the pads. Layout 1: screen page. Others: group with the working track."""
    lay = current(e)
    if lay is Layout1:
        return e.track_page * SCREEN_TRACKS
    rt = max(0, min(e.rate_track, len(e.tracks) - 1))
    return rt // lay.pad_group * lay.pad_group


def pad_tracks(e):
    """Track indices on the pads (may be fewer than a full window)."""
    start = first_track(e)
    return [i for i in range(start, start + current(e).pad_group) if i < len(e.tracks)]


def screen_tracks(e):
    """Track indices on the screen: 4 per page, in every layout."""
    start = e.track_page * SCREEN_TRACKS
    return [i for i in range(start, start + SCREEN_TRACKS) if i < len(e.tracks)]


def can_page_right(e):
    return (e.track_page + 1) * SCREEN_TRACKS < len(e.tracks)


def page_screen(e, direction):
    """Page the screen by 4 tracks. First track of new page = working track, pads follow."""
    page = e.track_page + direction
    if page < 0 or (direction > 0 and not can_page_right(e)):
        return
    e.track_page = page
    e.rate_track = page * SCREEN_TRACKS


def switch_layout(e, new):
    e.layout = new % len(LAYOUTS)
    e.armed = set()
    e.pad_down = {}


def track_for_slot(e, slot):
    lay = current(e)
    if getattr(lay, "shared_grid_slot", None) == slot:
        return e.rate_track if e.rate_track in pad_tracks(e) else None
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
    return es is not None and es[0] in screen_tracks(e)


def slen_track(e, enc_idx):
    """Track whose S LEN knob is encoder enc_idx (2nd of 2 per track), else None."""
    slot, role = divmod(enc_idx, 2)
    page = screen_tracks(e)
    return page[slot] if role == 1 and slot < len(page) else None


def slen_encoder(e, slot):
    return slot * 2 + 1


def pitch_ref_track(e):
    """Track the octave popup describes: working track if on the pads, else first."""
    page = pad_tracks(e)
    return e.rate_track if e.rate_track in page else (page[0] if page else 0)


def _step_tap(e, ti, si):
    """Plain step press: add or remove the armed notes, else toggle the step."""
    if e.armed:
        e.toggle_notes(ti, si, sorted(e.armed), activate=True)
    else:
        e.tap_step(ti, si)


def pad_press(e, col, row, now=None):
    """Handle a pad press. Shift selects without toggling. In Layouts 2 and 3 a plain
    step press and a disarm wait for release, so a long press can show a highlight."""
    now = time.monotonic() if now is None else now
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
        rec = {"t0": now, "kind": "step", "track": ti, "step": si, "pending": None}
        e.pad_down[(col, row)] = rec
        if e.accent_held or e.repeat_held:
            e.apply_hold(ti, si)
        elif e.shift:
            if e.sel.get(ti) == si:
                e.deselect(ti)
            else:
                e.select_step(ti, si)
        elif current(e).arm_mode:
            rec["pending"] = "step"
        else:
            e.tap_step(ti, si)
        return
    pt = pitch_track_for_slot(e, slot)
    if pt is not None:
        root, scale = e.key_of(pt)
        note = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave)[pitch_index(col, row)]
        if note > 127:
            return
        rec = {"t0": now, "kind": "pitch", "track": pt, "note": note, "pending": None}
        if e.pitch_held:                       # other pad held: add to selection
            e.armed.add(note)
        elif e.armed == {note} and e.rate_track == pt:
            rec["pending"] = "disarm"
        else:
            e.armed = {note}
        e.pad_down[(col, row)] = rec
        e.rate_track = pt


def pad_release(e, col, row, now=None):
    now = time.monotonic() if now is None else now
    rec = e.pad_down.pop((col, row), None)
    if rec is None or rec["pending"] is None or now - rec["t0"] >= LONG_PRESS_S:
        return
    if rec["pending"] == "step":
        _step_tap(e, rec["track"], rec["step"])
    elif rec["pending"] == "disarm" and e.armed == {rec["note"]}:
        e.armed = set()


def _long_presses(e, now):
    """(step index, {track: notes}) for the pads held longer than LONG_PRESS_S."""
    step, notes = None, {}
    for rec in e.pad_down.values():
        if now - rec["t0"] < LONG_PRESS_S:
            continue
        if rec["kind"] == "step" and step is None:
            step = rec["step"]
        elif rec["kind"] == "pitch":
            notes.setdefault(rec["track"], set()).add(rec["note"])
    return step, notes


def pad_colors(e, now=None):
    """8x8 palette indices, row 0 = bottom."""
    now = time.monotonic() if now is None else now
    grid = [[OFF] * 8 for _ in range(8)]
    if e.color_picker_track is not None:
        for (row, col), color in eng.color_picker_grid().items():
            grid[row][col] = color
        return grid
    hl_step, hl_notes = _long_presses(e, now)
    for slot in (0, 1, 2, 3):
        ti = track_for_slot(e, slot)
        if ti is not None:
            t = e.tracks[ti]
            only = hl_notes.get(ti)             # long-pressed notes of this track: dim the rest
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
                if only and color != PLAYHEAD and not (s["on"] and only & set(s["pitches"])):
                    color = LONG_PRESS_DIM
                grid[row][col] = color
            continue
        pt = pitch_track_for_slot(e, slot)
        if pt is not None:
            _paint_pitch(e, grid, slot, pt, now, hl_step)
    return grid


def _paint_pitch(e, grid, slot, track_idx, now, hl_step=None):
    in_key = e.pattern["in_key"]
    root, scale = e.key_of(track_idx)
    notes = eng.grid_pitches(root, scale, in_key, e.octave)
    in_scale = set(eng.scale_notes(root, scale))
    t = e.tracks[track_idx]
    color = t["color"]
    # selected = armed (working track only) or in the selected step
    if hl_step is not None:                    # long press on a step: show only its notes
        st = t["steps"][hl_step] if hl_step < t["length"] else None
        selected = set(st["pitches"]) if st and st["on"] else set()
    else:
        es = e.sel.get(track_idx)
        selected = set(t["steps"][es]["pitches"]) if es is not None and t["steps"][es]["on"] else set()
        if track_idx == e.rate_track:
            selected |= e.armed
    col0 = 0 if slot in (0, 2) else 4
    row0 = 4 if slot in (0, 1) else 0
    for i, note in enumerate(notes):
        c, r = col0 + i % 4, row0 + i // 4
        sel = note in selected
        if note > 127:
            grid[r][c] = OFF
        elif note % 12 == root:
            grid[r][c] = color if sel else dim(color)
        elif sel:
            grid[r][c] = PITCH_WHITE
        elif in_key or note % 12 in in_scale:
            grid[r][c] = LONG_PRESS_DIM if hl_step is not None else PITCH_DIM_WHITE
        else:
            grid[r][c] = OFF
    # the pad of a note that just sounded flashes green
    if now < t["_lit_until"]:
        for i, note in enumerate(notes):
            if note in t["_lit_notes"] and note <= 127:
                grid[row0 + i // 4][col0 + i % 4] = PLAYHEAD

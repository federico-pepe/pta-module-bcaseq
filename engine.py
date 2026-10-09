"""engine.py - BCA Sequencer model: tracks, steps, per-track rate, timing, triggers.

No I/O here. run.py talks to the host. view.py and layouts.py draw.
Every track has 16 steps (one 4x4 pad quadrant) and its own rate.
"""

import random
import time

MAX_TRACKS = 32
DEFAULT_TRACK_COUNT = 4
STEPS = 16
MIN_BPM, MAX_BPM, DEFAULT_BPM = 40, 240, 120
TICKS_PER_QUARTER = 24
EXTERNAL_CLOCK_TIMEOUT = 2.0
FRICTION_THRESHOLD = 4

# Scene buttons, bottom (1/4) to top (1/32t), in beats per step.
DIVISION_NAMES = [
    "Scene 1/4", "Scene 1/4t", "Scene 1/8", "Scene 1/8t",
    "Scene 1/16", "Scene 1/16t", "Scene 1/32", "Scene 1/32t",
]
DIVISIONS = {
    "Scene 1/4": 1.0, "Scene 1/4t": 2.0 / 3.0,
    "Scene 1/8": 0.5, "Scene 1/8t": 1.0 / 3.0,
    "Scene 1/16": 0.25, "Scene 1/16t": 1.0 / 6.0,
    "Scene 1/32": 0.125, "Scene 1/32t": 1.0 / 12.0,
}
DEFAULT_RATE = "Scene 1/16"
MAX_REPEAT = 8

SCALES = {
    "chromatic": list(range(12)),
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "whole_tone": [0, 2, 4, 6, 8, 10],
    "half_whole_dim": [0, 1, 3, 4, 6, 7, 9, 10],
    "whole_half_dim": [0, 2, 3, 5, 6, 8, 9, 11],
    "minor_blues": [0, 3, 5, 6, 7, 10],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "major_pentatonic": [0, 2, 4, 7, 9],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "harmonic_major": [0, 2, 4, 5, 7, 8, 11],
    "dorian_sharp4": [0, 2, 3, 6, 7, 9, 10],
    "phrygian_dominant": [0, 1, 4, 5, 7, 8, 10],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "lydian_augmented": [0, 2, 4, 6, 8, 9, 11],
    "lydian_dominant": [0, 2, 4, 6, 7, 9, 10],
    "super_locrian": [0, 1, 3, 4, 6, 8, 10],
}
SCALE_NAMES = list(SCALES.keys())
DEFAULT_SCALE = "chromatic"
SCALE_LABELS = {
    "half_whole_dim": "Half-Whole Dim",
    "whole_half_dim": "Whole-Half Dim",
    "dorian_sharp4": "Dorian #4",
    "phrygian_dominant": "Phrygian Dom",
}

# Same hand-picked list as gridseq. Do not reorder without a hardware test.
TRACK_COLORS = [1, 2, 3, 4, 6, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 25]
TRACK_COLOR_STEP = 3  # coprime with len(TRACK_COLORS)

# Encoder index -> step parameter. "channel" belongs to the track. "note_length" is
# how many steps the note lasts. The length of the sequence is set on the main
# screen (nudge_track_length).
PARAMS = ["pitch", "velocity", "gate", "probability", "offset", "channel", "repeat", "note_length"]
STEP_FIELD = {"velocity": "vel", "probability": "prob", "note_length": "len"}
THROTTLED = ("pitch", "offset", "channel", "repeat", "note_length")
PARAM_RANGE = {
    "velocity": (1, 127), "gate": (2, 99), "probability": (0, 100),
    "offset": (-45, 45), "repeat": (1, MAX_REPEAT), "pitch": (0, 127),
    "channel": (1, 16), "note_length": (1, STEPS),
}
PARAM_DEFAULT = {"velocity": 100, "gate": 50, "probability": 100, "offset": 0, "repeat": 1,
                 "note_length": 1}

DEFAULT_VELOCITY, ACCENT_VELOCITY = 100, 127
DEFAULT_PITCH = 60  # C3 in Live numbering
FLASH_MIN_S = 0.12   # a triggered note lights its pitch pad at least this long
PARAM_SHOW_S = 1.5   # seconds a knob shows its value after a touch


# Color picker (Shift + track button): TRACK_COLORS around the border pads,
# (row, col) with row 0 at the bottom, walked clockwise from the bottom edge.
COLOR_PICKER_BORDER = [
    (0, 2), (0, 1), (0, 0),
    (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0),
    (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7),
    (6, 7), (5, 7), (4, 7), (3, 7), (2, 7), (1, 7), (0, 7),
    (0, 6), (0, 5), (0, 4), (0, 3),
]


def color_picker_grid():
    return {pos: TRACK_COLORS[i] for i, pos in enumerate(COLOR_PICKER_BORDER) if i < len(TRACK_COLORS)}


class Friction:
    """Turns raw encoder deltas into logical steps. Remainder carries over."""

    def __init__(self):
        self._acc = {}

    def feed(self, key, delta, threshold=FRICTION_THRESHOLD):
        if threshold <= 1:
            return delta
        acc = self._acc.get(key, 0) + delta
        steps = int(acc / threshold)
        self._acc[key] = acc - steps * threshold
        return steps

    def reset(self):
        self._acc = {}


def clean_pitches(v):
    """A valid note list from saved data: sorted, unique, 0-127, never empty."""
    if not isinstance(v, list):
        return [DEFAULT_PITCH]
    notes = {max(0, min(127, n)) for n in v if isinstance(n, int) and not isinstance(n, bool)}
    return sorted(notes) or [DEFAULT_PITCH]


def new_step():
    return {"on": False, "pitches": [DEFAULT_PITCH], "pitch_set": False, "vel": DEFAULT_VELOCITY,
            "gate": 50, "prob": 100, "offset": 0, "repeat": 1, "len": 1}


def new_track(index):
    return {
        "name": "Track %d" % (index + 1),
        "root": 0,              # used when pattern["scope_global"] is False
        "scale": DEFAULT_SCALE,
        "channel": 1,
        "length": STEPS,
        "rate": DEFAULT_RATE,
        "steps": [new_step() for _ in range(STEPS)],
        "color": TRACK_COLORS[(index * TRACK_COLOR_STEP) % len(TRACK_COLORS)],
        "_current_step": -1,
        "last_pitch": None,     # last note entered on this track. New steps start from it.
        "_lit_notes": [],       # notes that just sounded, for the pitch pad flash
        "_lit_until": 0.0,
        "_show_until": 0.0,     # the screen shows _lit_notes until this time
        "_progress": 0.0,       # 0-1 position inside the track's loop
    }


def default_pattern():
    return {
        "bpm": DEFAULT_BPM,
        "root": 0, "scale": DEFAULT_SCALE, "in_key": True,
        "scope_global": True,   # True: one key/scale for all tracks. False: each track has its own.
        "tracks": [new_track(i) for i in range(DEFAULT_TRACK_COUNT)],
    }


def scale_notes(root, scale):
    """Pitch classes (0-11) in the scale, ascending from the root."""
    return [(root + i) % 12 for i in SCALES[scale]]


def grid_pitches(root, scale, in_key, octave):
    """16 pitches for a 4x4 pitch quadrant. Index 0 is bottom-left, then
    right, then up. Octave 3 puts the root at C3 (MIDI 60) for root C."""
    base = root + 12 * (octave + 2)
    if in_key:
        ivals = SCALES[scale]
        n = len(ivals)
        notes = [base + ivals[i % n] + 12 * (i // n) for i in range(16)]
    else:
        notes = [base + i for i in range(16)]
    return notes


def max_octave(root, scale, in_key):
    o = 8
    while o > -2 and max(grid_pitches(root, scale, in_key, o)) > 127:
        o -= 1
    return o


class Engine:
    def __init__(self, send_note, note_off, send_cc=None, log=None):
        self._send_note = send_note
        self._note_off = note_off
        self._log = log or (lambda m: None)

        self.pattern = default_pattern()
        self.playing = False
        self.play_start = None
        self._ticks = 0.0               # shared clock: 24 ppqn ticks since Start. Every track reads it.
        self._last_tick = None          # time of the last internal-clock update
        self.pending = []            # (due, kind, ch, note, vel) kind "on" or "off"
        self.friction = Friction()

        self.rate_track = 0          # track the Scene buttons act on
        self.active_param = None     # (encoder idx, deadline) of the last touched/turned knob
        self.layout = 0
        self.track_page = 0          # page index in units of the layout's tracks per page
        self.octave = 3              # Layout 2 pitch grid octave
        self.edit_track = None       # track index being edited, or None
        self.sel = {}                # track index -> selected step index
        self.sel_note = 0            # index of the selected note inside the selected step
        self.armed = None            # Layout 3: (track, note) waiting for a step pad
        self.grid_track = 0          # Layout 3: track shown on the step grid

        self.accent_on = False
        self.repeat_on = False
        self.accent_held = False     # button currently down
        self.repeat_held = False
        self.accent_used = False     # a pad was pressed during this hold
        self.repeat_used = False
        self.color_picker_track = None
        self.repeat_count = 1
        self.shift = False
        self.delete = False
        self.scale_menu = False

        self.last_ext_clock = None

    # -- state helpers ---------------------------------------------------------

    @property
    def tracks(self):
        return self.pattern["tracks"]

    def set_rate(self, track_idx, name):
        if name in DIVISIONS and 0 <= track_idx < len(self.tracks):
            self.tracks[track_idx]["rate"] = name

    def step_duration(self, t):
        return (60.0 / max(1, self.pattern["bpm"])) * DIVISIONS[t["rate"]]

    def touch_param(self, idx):
        """Remember a knob so the screen shows its value for a moment."""
        self.active_param = (idx, time.monotonic() + PARAM_SHOW_S)

    def select_track(self, track_idx):
        """Track button: make it the rate target. In edit mode, edit it too."""
        if not (0 <= track_idx < len(self.tracks)):
            return
        self.rate_track = track_idx
        if self.edit_track is not None:
            if track_idx in self.sel:
                self.edit_track = track_idx
                self.friction.reset()
            else:
                self.select_step(track_idx, 0)

    def apply_hold(self, track_idx, step_idx):
        """Accent or Repeat held while a pad is pressed: change that step's
        value without toggling it on or off. Pressing again reverts it."""
        s = self.tracks[track_idx]["steps"][step_idx]
        if self.accent_held:
            self.accent_used = True
            s["vel"] = DEFAULT_VELOCITY if s["vel"] == ACCENT_VELOCITY else ACCENT_VELOCITY
        if self.repeat_held:
            self.repeat_used = True
            s["repeat"] = 1 if s["repeat"] == self.repeat_count else self.repeat_count
        self.select_step(track_idx, step_idx)

    def set_track_color(self, track_idx, color):
        if 0 <= track_idx < len(self.tracks) and color in TRACK_COLORS:
            self.tracks[track_idx]["color"] = color

    def clear_edit(self):
        """Back to the main screen: leave edit mode and the scale menu."""
        self.edit_track = None
        self.sel = {}
        self.scale_menu = False
        self.color_picker_track = None
        self.active_param = None
        self.armed = None
        self.sel_note = 0
        self.friction.reset()

    def edit_step(self):
        """(track_idx, step_idx) in edit mode, else None."""
        if self.edit_track is None:
            return None
        s = self.sel.get(self.edit_track)
        if s is None or self.edit_track >= len(self.tracks):
            return None
        return self.edit_track, s

    def add_track(self):
        if len(self.tracks) >= MAX_TRACKS:
            return False
        t = new_track(len(self.tracks))
        if self.playing:
            t["_current_step"] = self.step_at(t)   # join the shared clock without a late hit
        self.tracks.append(t)
        return True

    def key_of(self, track_idx):
        """(root, scale) that applies to a track."""
        p = self.pattern
        if p["scope_global"] or not (0 <= track_idx < len(self.tracks)):
            return p["root"], p["scale"]
        t = self.tracks[track_idx]
        return t["root"], t["scale"]

    def menu_track(self):
        """Track the Scale menu edits: the last touched track, or None when global."""
        if self.pattern["scope_global"]:
            return None
        return min(self.rate_track, len(self.tracks) - 1)

    def default_pitch(self, track_idx=0):
        return DEFAULT_PITCH + self.key_of(track_idx)[0]

    def max_octave(self):
        """Highest Layout 2 octave that keeps every pitch pad at or below 127."""
        p = self.pattern
        if p["scope_global"]:
            return max_octave(p["root"], p["scale"], p["in_key"])
        return min(max_octave(t["root"], t["scale"], p["in_key"]) for t in self.tracks)

    # -- persistence -----------------------------------------------------------

    def load(self, doc):
        if not isinstance(doc, dict) or doc.get("version") != 1:
            return False
        pat = doc.get("pattern")
        if not isinstance(pat, dict):
            return False
        out = default_pattern()
        out["bpm"] = max(MIN_BPM, min(MAX_BPM, int(pat.get("bpm", DEFAULT_BPM))))
        legacy_rate = pat.get("rate") if pat.get("rate") in DIVISIONS else DEFAULT_RATE
        out["root"] = max(0, min(11, int(pat.get("root", 0))))
        if pat.get("scale") in SCALES:
            out["scale"] = pat["scale"]
        out["in_key"] = bool(pat.get("in_key", True))
        out["scope_global"] = bool(pat.get("scope_global", True))
        tracks = []
        for i, saved in enumerate((pat.get("tracks") or [])[:MAX_TRACKS]):
            if not isinstance(saved, dict):
                continue
            t = new_track(i)
            for k in ("name", "color"):
                if k in saved:
                    t[k] = saved[k]
            t["root"] = max(0, min(11, int(saved.get("root", out["root"]))))
            t["scale"] = saved["scale"] if saved.get("scale") in SCALES else out["scale"]
            t["channel"] = max(1, min(16, int(saved.get("channel", 1))))
            t["length"] = max(1, min(STEPS, int(saved.get("length", STEPS))))
            r = saved.get("rate", legacy_rate)
            t["rate"] = r if r in DIVISIONS else DEFAULT_RATE
            lp = saved.get("last_pitch")
            t["last_pitch"] = max(0, min(127, lp)) if isinstance(lp, int) and not isinstance(lp, bool) else None
            saved_steps = saved.get("steps") or []
            for j in range(STEPS):
                if j < len(saved_steps) and isinstance(saved_steps[j], dict):
                    t["steps"][j].update({k: v for k, v in saved_steps[j].items() if k in t["steps"][j]})
                    st = t["steps"][j]
                    st["len"] = max(1, min(STEPS, int(st["len"]))) if isinstance(st["len"], int) else 1
                    st["pitches"] = clean_pitches(st["pitches"])
            tracks.append(t)
        out["tracks"] = tracks or [new_track(i) for i in range(DEFAULT_TRACK_COUNT)]
        self.stop()
        self.pattern = out
        self.edit_track, self.sel, self.track_page, self.rate_track = None, {}, 0, 0
        self.sel_note, self.armed, self.grid_track = 0, None, 0
        return True

    def new_pattern(self):
        self.stop()
        self.pattern = default_pattern()
        self.edit_track, self.sel, self.track_page, self.rate_track = None, {}, 0, 0
        self.sel_note, self.armed, self.grid_track = 0, None, 0

    def to_doc(self):
        p = self.pattern
        tracks = [{k: v for k, v in t.items() if not k.startswith("_")} for t in p["tracks"]]
        return {"version": 1, "pattern": {
            "bpm": p["bpm"], "root": p["root"], "scale": p["scale"],
            "in_key": p["in_key"], "scope_global": p["scope_global"], "tracks": tracks}}

    # -- step editing ----------------------------------------------------------

    def tap_step(self, track_idx, step_idx):
        """Toggle a step and select it. Turning a step off clears the selection."""
        t = self.tracks[track_idx]
        if not (0 <= step_idx < STEPS):
            return
        s = t["steps"][step_idx]
        s["on"] = not s["on"]
        if s["on"]:
            if not s["pitch_set"]:
                s["pitches"] = [self.entry_pitch(track_idx)]
                s["pitch_set"] = True
            self._entry_defaults(s)
            self.select_step(track_idx, step_idx)
        else:
            self.deselect(track_idx)

    def _entry_defaults(self, s):
        s["vel"] = ACCENT_VELOCITY if self.accent_on else DEFAULT_VELOCITY
        s["repeat"] = self.repeat_count if self.repeat_on else 1

    def select_step(self, track_idx, step_idx):
        self.sel[track_idx] = step_idx
        self.sel_note = 0
        self.edit_track = track_idx
        self.rate_track = track_idx
        self.friction.reset()

    def deselect(self, track_idx):
        self.rate_track = track_idx
        self.sel.pop(track_idx, None)
        if self.edit_track == track_idx:
            self.edit_track = None
        self.friction.reset()

    def entry_pitch(self, track_idx):
        """Pitch for a new step: the last note entered on this track."""
        last = self.tracks[track_idx]["last_pitch"]
        return last if last is not None else self.default_pitch(track_idx)

    def _remember_pitch(self, track_idx, step, note):
        step["pitch_set"] = True
        self.tracks[track_idx]["last_pitch"] = note

    def note_index(self, step):
        """Index of the selected note in a step, kept inside the list."""
        return max(0, min(self.sel_note, len(step["pitches"]) - 1))

    def toggle_note(self, track_idx, step_idx, note, activate=False):
        """Add a note to a step, or remove it when it is already there. Removing
        the last note turns the step off. An off step takes just this note;
        activate=True also turns it on with the Accent and Repeat defaults."""
        if not (0 <= step_idx < STEPS):
            return
        note = max(0, min(127, note))
        s = self.tracks[track_idx]["steps"][step_idx]
        at = 0
        if s["on"] and note in s["pitches"]:
            if len(s["pitches"]) == 1:
                s["on"] = False
                self.deselect(track_idx)
                return
            at = s["pitches"].index(note)
            s["pitches"].remove(note)
        else:
            if s["on"]:
                s["pitches"] = sorted(s["pitches"] + [note])
            else:
                s["pitches"] = [note]
                if activate:
                    s["on"] = True
                    self._entry_defaults(s)
            self._remember_pitch(track_idx, s, note)
        if s["on"]:
            self.select_step(track_idx, step_idx)
            self.sel_note = s["pitches"].index(note) if note in s["pitches"] else min(at, len(s["pitches"]) - 1)
        else:
            self.sel_note = 0

    def _free_step(self, note, direction, taken, track_idx):
        """Next pitch from `note` that is not in `taken`. Stays put at the range edge."""
        cur = note
        while True:
            nxt = self._step_pitch(cur, direction, track_idx)
            if nxt == cur:
                return note
            if nxt not in taken:
                return nxt
            cur = nxt

    def _set_selected_note(self, s, note):
        s["pitches"][self.note_index(s)] = note
        s["pitches"].sort()
        self.sel_note = s["pitches"].index(note)

    def _step_pitch(self, note, direction, track_idx=0):
        """One pitch step: next scale note when In Key is on, else a semitone."""
        if not self.pattern["in_key"]:
            return max(0, min(127, note + direction))
        pcs = set(scale_notes(*self.key_of(track_idx)))
        n = note
        while 0 <= n + direction <= 127:
            n += direction
            if n % 12 in pcs:
                return n
        return note

    def nudge(self, idx, delta):
        """Apply an encoder turn to the edit-mode step. Returns True if handled."""
        es = self.edit_step()
        if es is None or not (0 <= idx < len(PARAMS)) or delta == 0:
            return False
        ti, si = es
        t = self.tracks[ti]
        s = t["steps"][si]
        param = PARAMS[idx]
        self.touch_param(idx)
        thr = FRICTION_THRESHOLD if param in THROTTLED else 1
        n = self.friction.feed(param, delta, thr)
        if n == 0:
            return True
        lo, hi = PARAM_RANGE[param]
        if param == "pitch":
            note = s["pitches"][self.note_index(s)]
            taken = set(s["pitches"]) - {note}
            for _ in range(abs(n)):
                note = self._free_step(note, 1 if n > 0 else -1, taken, ti)
            self._set_selected_note(s, note)
            self._remember_pitch(ti, s, note)
        elif param == "channel":
            t["channel"] = max(lo, min(hi, t["channel"] + n))
        else:
            field = STEP_FIELD.get(param, param)
            s[field] = max(lo, min(hi, s[field] + n))
        return True

    def nudge_track_length(self, track_idx, delta, enc_idx):
        """Main screen S LEN knob: length of the sequence of one track."""
        if not (0 <= track_idx < len(self.tracks)) or delta == 0:
            return
        self.touch_param(enc_idx)
        n = self.friction.feed(("slen", track_idx), delta)
        t = self.tracks[track_idx]
        t["length"] = max(1, min(STEPS, t["length"] + n))

    def reset_track_length(self, track_idx, enc_idx):
        if 0 <= track_idx < len(self.tracks):
            self.touch_param(enc_idx)
            self.tracks[track_idx]["length"] = STEPS

    def reset_param(self, idx):
        es = self.edit_step()
        if es is None or not (0 <= idx < len(PARAMS)):
            return
        ti, si = es
        t, s, param = self.tracks[ti], self.tracks[ti]["steps"][es[1]], PARAMS[idx]
        if param == "pitch":
            note = self.default_pitch(ti)
            if note not in s["pitches"]:
                self._set_selected_note(s, note)
        elif param == "channel":
            t["channel"] = 1
        else:
            s[STEP_FIELD.get(param, param)] = PARAM_DEFAULT[param]

    # Scale menu encoders: 1 Key, 2 Scale, 4 In Key, 5 Scope. Encoder 3 is unused
    # because the Scale name needs two screen columns.
    def nudge_scale_menu(self, idx, delta):
        p = self.pattern
        if delta == 0:
            return
        target = p if p["scope_global"] else self.tracks[self.menu_track()]
        if idx == 0:
            n = self.friction.feed("root", delta)
            target["root"] = max(0, min(11, target["root"] + n))
        elif idx == 1:
            n = self.friction.feed("scale", delta)
            i = SCALE_NAMES.index(target["scale"])
            target["scale"] = SCALE_NAMES[max(0, min(len(SCALE_NAMES) - 1, i + n))]
        elif idx == 3:
            n = self.friction.feed("in_key", delta)
            if n:
                p["in_key"] = n > 0
        elif idx == 4:
            n = self.friction.feed("scope", delta)
            if n:
                self.set_scope_global(n > 0)
        self.octave = min(self.octave, self.max_octave())

    def set_scope_global(self, on):
        """Global: all tracks share the pattern key. Per track: each track keeps
        its own, starting from the current global key."""
        p = self.pattern
        if on == p["scope_global"]:
            return
        p["scope_global"] = on
        if not on:
            for t in self.tracks:
                t["root"], t["scale"] = p["root"], p["scale"]

    def toggle_scale_menu(self):
        self.scale_menu = not self.scale_menu
        self.friction.reset()

    def shift_octave(self, direction):
        self.octave = max(-2, min(self.max_octave(), self.octave + direction))

    # -- transport -------------------------------------------------------------

    def toggle_play(self):
        self.stop() if self.playing else self.start()

    def start(self):
        self.playing = True
        self.play_start = time.monotonic()
        self._last_tick = self.play_start
        self._ticks = 0.0
        for t in self.tracks:
            t["_current_step"] = -1
            t["_progress"] = 0.0

    def stop(self):
        self.playing = False
        self._release_all()
        for t in self.tracks:
            t["_current_step"] = -1
            t["_progress"] = 0.0
            t["_lit_notes"] = []
            t["_show_until"] = 0.0

    def is_externally_synced(self):
        return self.last_ext_clock is not None and \
            (time.monotonic() - self.last_ext_clock) < EXTERNAL_CLOCK_TIMEOUT

    @staticmethod
    def ticks_per_step(t):
        """Clock ticks in one step of a track. Whole number for all 8 rates."""
        return max(1, round(TICKS_PER_QUARTER * DIVISIONS[t["rate"]]))

    def step_at(self, t):
        """Step a track is on at the shared clock position. Every track reads the
        same clock, so equal lengths stay together, a new track joins in phase,
        and a length change keeps the track on the shared timeline."""
        return int(self._ticks / self.ticks_per_step(t) + 1e-6) % t["length"]

    def _advance(self, now):
        for idx, t in enumerate(self.tracks):
            pos = self._ticks / self.ticks_per_step(t)
            t["_progress"] = (pos % t["length"]) / t["length"]
            step_idx = int(pos + 1e-6) % t["length"]
            if step_idx != t["_current_step"]:
                t["_current_step"] = step_idx
                self._trigger(idx, step_idx, now)

    def on_external_clock_byte(self, b):
        now = time.monotonic()
        if b == 0xF8:
            self.last_ext_clock = now
            if not self.playing:
                return
            self._advance(now)          # the first tick after Start plays step 1
            self._ticks += 1
        elif b == 0xFA:
            self.start()
        elif b == 0xFB:
            self.playing = True
        elif b == 0xFC:
            self.stop()

    def tick(self, now=None):
        """Called on every draw. Advances steps (internal clock) and flushes notes."""
        now = now if now is not None else time.monotonic()
        self._flush(now)
        last, self._last_tick = self._last_tick, now
        if self.is_externally_synced():
            self.play_start = now
            return
        if not self.playing or last is None:
            return
        # Internal clock: add the ticks since the last call. A tempo change only
        # affects the future, so the tracks never jump.
        self._ticks += max(0.0, now - last) * self.pattern["bpm"] / 60.0 * TICKS_PER_QUARTER
        self._advance(now)

    # -- triggering ------------------------------------------------------------

    def _trigger(self, track_idx, step_idx, now):
        t = self.tracks[track_idx]
        s = t["steps"][step_idx]
        if not s["on"]:
            return
        if random.randint(1, 100) > s["prob"]:
            return
        dur = self.step_duration(t)
        repeats = max(1, s["repeat"])
        slot = dur / repeats
        off_at = now
        for r in range(repeats):
            fire_at = now + (s["offset"] / 100.0) * dur + r * slot
            off_at = fire_at + (s["gate"] / 100.0) * slot
            if r == repeats - 1:
                off_at += (s["len"] - 1) * dur     # note length: the last hit holds longer
            for note in s["pitches"]:
                self._schedule(t["channel"], note, s["vel"], fire_at, off_at, now)
        t["_lit_notes"] = list(s["pitches"])
        t["_lit_until"] = max(off_at, now + FLASH_MIN_S)
        t["_show_until"] = max(off_at, now + dur)

    def _schedule(self, ch, note, vel, fire_at, off_at, now):
        if fire_at <= now + 0.001:
            self._send_note(ch, note, vel)
        else:
            self.pending.append((fire_at, "on", ch, note, vel))
        self.pending.append((off_at, "off", ch, note, 0))

    def _flush(self, now):
        keep = []
        for item in sorted(self.pending, key=lambda x: (x[0], x[1] == "on")):
            due, kind, ch, note, vel = item
            if due > now:
                keep.append(item)
            elif kind == "on":
                self._send_note(ch, note, vel)
            else:
                self._note_off(ch, note)
        self.pending = keep

    def _release_all(self):
        for _, kind, ch, note, _v in self.pending:
            if kind == "off":
                self._note_off(ch, note)
        self.pending = []

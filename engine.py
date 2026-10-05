"""engine.py - BCA Seq model: tracks, steps, per-track rate, timing, triggers.

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
SCALE_LABELS = {
    "half_whole_dim": "Half-Whole Dim",
    "whole_half_dim": "Whole-Half Dim",
    "dorian_sharp4": "Dorian #4",
}

# Same hand-picked list as gridseq. Do not reorder without a hardware test.
TRACK_COLORS = [1, 2, 3, 4, 6, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 25]
TRACK_COLOR_STEP = 3  # coprime with len(TRACK_COLORS)

# Encoder index -> step parameter. "channel" and "length" belong to the track.
PARAMS = ["pitch", "velocity", "gate", "probability", "offset", "channel", "repeat", "length"]
THROTTLED = ("pitch", "offset", "channel", "repeat", "length")
PARAM_RANGE = {
    "velocity": (1, 127), "gate": (2, 99), "probability": (0, 100),
    "offset": (-45, 45), "repeat": (1, MAX_REPEAT), "pitch": (0, 127),
    "channel": (1, 16), "length": (1, STEPS),
}
PARAM_DEFAULT = {"velocity": 100, "gate": 50, "probability": 100, "offset": 0, "repeat": 1}

DEFAULT_VELOCITY, ACCENT_VELOCITY = 100, 127
DEFAULT_PITCH = 60  # C3 in Live numbering
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


def new_step():
    return {"on": False, "pitch": DEFAULT_PITCH, "vel": DEFAULT_VELOCITY, "gate": 50,
            "prob": 100, "offset": 0, "repeat": 1}


def new_track(index):
    return {
        "name": "Track %d" % (index + 1),
        "channel": 1,
        "length": STEPS,
        "rate": DEFAULT_RATE,
        "steps": [new_step() for _ in range(STEPS)],
        "color": TRACK_COLORS[(index * TRACK_COLOR_STEP) % len(TRACK_COLORS)],
        "_current_step": -1,
        "_last_note": None,
        "_progress": 0.0,       # 0-1 position inside the track's loop
        "_ext_acc": 0,
    }


def default_pattern():
    return {
        "bpm": DEFAULT_BPM,
        "root": 0, "scale": "major", "in_key": True,
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
        self.pending = []            # (due, kind, ch, note, vel) kind "on" or "off"
        self.friction = Friction()

        self.rate_track = 0          # track the Scene buttons act on
        self.active_param = None     # (encoder idx, deadline) of the last touched/turned knob
        self.layout = 0
        self.track_page = 0          # page index in units of the layout's tracks per page
        self.octave = 3              # Layout 2 pitch grid octave
        self.edit_track = None       # track index being edited, or None
        self.sel = {}                # track index -> selected step index

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
        self.tracks.append(new_track(len(self.tracks)))
        return True

    def default_pitch(self):
        return DEFAULT_PITCH + self.pattern["root"]

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
        tracks = []
        for i, saved in enumerate((pat.get("tracks") or [])[:MAX_TRACKS]):
            if not isinstance(saved, dict):
                continue
            t = new_track(i)
            for k in ("name", "color"):
                if k in saved:
                    t[k] = saved[k]
            t["channel"] = max(1, min(16, int(saved.get("channel", 1))))
            t["length"] = max(1, min(STEPS, int(saved.get("length", STEPS))))
            r = saved.get("rate", legacy_rate)
            t["rate"] = r if r in DIVISIONS else DEFAULT_RATE
            saved_steps = saved.get("steps") or []
            for j in range(STEPS):
                if j < len(saved_steps) and isinstance(saved_steps[j], dict):
                    t["steps"][j].update({k: v for k, v in saved_steps[j].items() if k in t["steps"][j]})
            tracks.append(t)
        out["tracks"] = tracks or [new_track(i) for i in range(DEFAULT_TRACK_COUNT)]
        self.stop()
        self.pattern = out
        self.edit_track, self.sel, self.track_page, self.rate_track = None, {}, 0, 0
        return True

    def new_pattern(self):
        self.stop()
        self.pattern = default_pattern()
        self.edit_track, self.sel, self.track_page, self.rate_track = None, {}, 0, 0

    def to_doc(self):
        p = self.pattern
        tracks = [{k: v for k, v in t.items() if not k.startswith("_")} for t in p["tracks"]]
        return {"version": 1, "pattern": {
            "bpm": p["bpm"], "root": p["root"], "scale": p["scale"],
            "in_key": p["in_key"], "tracks": tracks}}

    # -- step editing ----------------------------------------------------------

    def tap_step(self, track_idx, step_idx):
        """Toggle a step and select it. Turning a step off clears the selection."""
        t = self.tracks[track_idx]
        if not (0 <= step_idx < STEPS):
            return
        s = t["steps"][step_idx]
        s["on"] = not s["on"]
        if s["on"]:
            s["pitch"] = s["pitch"] if s["pitch"] != DEFAULT_PITCH else self.default_pitch()
            s["vel"] = ACCENT_VELOCITY if self.accent_on else DEFAULT_VELOCITY
            s["repeat"] = self.repeat_count if self.repeat_on else 1
            self.select_step(track_idx, step_idx)
        else:
            self.deselect(track_idx)

    def select_step(self, track_idx, step_idx):
        self.sel[track_idx] = step_idx
        self.edit_track = track_idx
        self.rate_track = track_idx
        self.friction.reset()

    def deselect(self, track_idx):
        self.rate_track = track_idx
        self.sel.pop(track_idx, None)
        if self.edit_track == track_idx:
            self.edit_track = None
        self.friction.reset()

    def set_pitch(self, track_idx, step_idx, note):
        self.tracks[track_idx]["steps"][step_idx]["pitch"] = max(0, min(127, note))

    def _step_pitch(self, note, direction):
        """One pitch step: next scale note when In Key is on, else a semitone."""
        if not self.pattern["in_key"]:
            return max(0, min(127, note + direction))
        pcs = set(scale_notes(self.pattern["root"], self.pattern["scale"]))
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
            for _ in range(abs(n)):
                s["pitch"] = self._step_pitch(s["pitch"], 1 if n > 0 else -1)
        elif param == "channel":
            t["channel"] = max(lo, min(hi, t["channel"] + n))
        elif param == "length":
            t["length"] = max(lo, min(hi, t["length"] + n))
        else:
            field = {"velocity": "vel", "probability": "prob"}.get(param, param)
            s[field] = max(lo, min(hi, s[field] + n))
        return True

    def reset_param(self, idx):
        es = self.edit_step()
        if es is None or not (0 <= idx < len(PARAMS)):
            return
        ti, si = es
        t, s, param = self.tracks[ti], self.tracks[ti]["steps"][es[1]], PARAMS[idx]
        if param == "pitch":
            s["pitch"] = self.default_pitch()
        elif param == "channel":
            t["channel"] = 1
        elif param == "length":
            t["length"] = STEPS
        else:
            field = {"velocity": "vel", "probability": "prob"}.get(param, param)
            s[field] = PARAM_DEFAULT[param]

    def nudge_scale_menu(self, idx, delta):
        p = self.pattern
        if delta == 0:
            return
        if idx == 0:
            n = self.friction.feed("root", delta)
            p["root"] = max(0, min(11, p["root"] + n))
        elif idx == 1:
            n = self.friction.feed("scale", delta)
            i = SCALE_NAMES.index(p["scale"])
            p["scale"] = SCALE_NAMES[max(0, min(len(SCALE_NAMES) - 1, i + n))]
        elif idx == 2:
            n = self.friction.feed("in_key", delta)
            if n:
                p["in_key"] = n > 0
        self.octave = min(self.octave, max_octave(p["root"], p["scale"], p["in_key"]))

    def toggle_scale_menu(self):
        self.scale_menu = not self.scale_menu
        self.friction.reset()

    def shift_octave(self, direction):
        p = self.pattern
        top = max_octave(p["root"], p["scale"], p["in_key"])
        self.octave = max(-2, min(top, self.octave + direction))

    # -- transport -------------------------------------------------------------

    def toggle_play(self):
        self.stop() if self.playing else self.start()

    def start(self):
        self.playing = True
        self.play_start = time.monotonic()
        for t in self.tracks:
            t["_current_step"] = -1
            t["_progress"] = 0.0
            t["_ext_acc"] = 0

    def stop(self):
        self.playing = False
        self._release_all()
        for t in self.tracks:
            t["_current_step"] = -1
            t["_progress"] = 0.0

    def is_externally_synced(self):
        return self.last_ext_clock is not None and \
            (time.monotonic() - self.last_ext_clock) < EXTERNAL_CLOCK_TIMEOUT

    def on_external_clock_byte(self, b):
        now = time.monotonic()
        if b == 0xF8:
            self.last_ext_clock = now
            if not self.playing:
                return
            for idx, t in enumerate(self.tracks):
                per_step = max(1, round(TICKS_PER_QUARTER * DIVISIONS[t["rate"]]))
                t["_ext_acc"] += 1
                if t["_ext_acc"] >= per_step:
                    t["_ext_acc"] = 0
                    t["_current_step"] = (t["_current_step"] + 1) % t["length"]
                    self._trigger(idx, t["_current_step"], now)
                t["_progress"] = (max(0, t["_current_step"]) + t["_ext_acc"] / per_step) / t["length"]
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
        if self.is_externally_synced():
            self.play_start = now
            return
        if not self.playing or self.play_start is None:
            return
        elapsed = now - self.play_start
        for idx, t in enumerate(self.tracks):
            dur = self.step_duration(t)
            pos = (elapsed / dur) % t["length"]
            t["_progress"] = pos / t["length"]
            step_idx = int(pos)
            if step_idx != t["_current_step"]:
                t["_current_step"] = step_idx
                self._trigger(idx, step_idx, now)

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
        for r in range(repeats):
            fire_at = now + (s["offset"] / 100.0) * dur + r * slot
            off_at = fire_at + (s["gate"] / 100.0) * slot
            self._schedule(t["channel"], s["pitch"], s["vel"], fire_at, off_at, now)
        t["_last_note"] = s["pitch"]

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

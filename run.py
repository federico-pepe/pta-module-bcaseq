#!/usr/bin/env python3
"""run.py - BCA Seq protocol loop.

Newline-delimited JSON on stdin/stdout, same envelope as the other PTA
process modules. This file does I/O and event dispatch only. The model is
in engine.py. Pad mapping is in layouts.py. Screen and LED colors are in
view.py. LEDs are re-sent from the diffed frame on each draw, and in full
once per LED_REFRESH_S because Push can drop LED writes.
"""

import base64
import copy
import json
import os
import re
import sys
import time

import colorlab
import colortable
import engine as eng
import layouts
import view

SEQUENCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sequences")
POPUP_DURATION = 1.5
LED_REFRESH_S = 1.0
LAYOUT_OSD = ["4 TRACKS", "2 TRACKS + PITCH"]


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def respond(id_, result):
    if id_ is not None:
        send({"id": id_, "result": result})


def respond_error(id_, message):
    send({"id": id_, "error": message})


def notify(method, params):
    send({"method": method, "params": params})


def pad_note(col, row):
    return 36 + row * 8 + col


class State:
    def __init__(self):
        self.engine = eng.Engine(send_note=self.send_note, note_off=self.note_off, log=self.log)
        self.last_pad_colors = None
        self.last_button_colors = None
        self.last_refresh = 0.0
        self.button_held = {}
        self.popup_title = None
        self.popup_body = None
        self.popup_until = 0.0
        self.active_sequence_name = None
        self.lab = None               # ColorLab while the Color Lab is open
        self.browser_active = False
        self.browser_names = []
        self.browser_cursor = 0
        self._next_id = 1000

    def show_popup(self, title, body=None):
        self.popup_title, self.popup_body = title, body
        self.popup_until = time.monotonic() + POPUP_DURATION

    def request(self, method, params):
        self._next_id += 1
        send({"id": self._next_id, "method": method, "params": params})

    def send_note(self, ch, note, vel):
        self.request("send_note", {"ch": ch, "note": note, "vel": vel})

    def note_off(self, ch, note):
        self.request("note_off", {"ch": ch, "note": note})

    def log(self, message):
        notify("log", {"message": message})


def relight(state):
    now = time.monotonic()
    if now - state.last_refresh >= LED_REFRESH_S:
        state.last_refresh = now
        state.last_pad_colors = None
        state.last_button_colors = None

    grid = view.pad_colors(state)
    if grid != state.last_pad_colors:
        state.last_pad_colors = copy.deepcopy(grid)
        for row in range(8):
            for col in range(8):
                notify("set_pad", {"note": pad_note(col, row), "colour": grid[row][col]})

    colors = view.button_colors(state)
    if colors != state.last_button_colors:
        state.last_button_colors = dict(colors)
        for name, idx in colors.items():
            cc = view.BUTTON_CC.get(name)
            if cc is not None:
                notify("set_button", {"cc": cc, "brightness": idx})


# -- events ---------------------------------------------------------------------

def handle_pad(state, data):
    if state.lab is not None or state.browser_active or not data.get("pressed"):
        return
    layouts.pad_press(state.engine, data.get("col"), data.get("row"))


def octave_range_label(e):
    p = e.pattern
    notes = [n for n in eng.grid_pitches(p["root"], p["scale"], p["in_key"], e.octave) if n <= 127]
    return "%s - %s" % (view.note_name(min(notes)), view.note_name(max(notes)))


def handle_button(state, data):
    e = state.engine
    name = data.get("name") or ""
    pressed = bool(data.get("pressed"))
    if name in view.BUTTON_CC:
        state.button_held[name] = pressed

    if name == "Shift":
        e.shift = pressed
        if not pressed:
            e.color_picker_track = None
        return
    if name == "Delete":
        e.delete = pressed
        return
    if state.lab is not None:
        if pressed:
            _lab_button(state, name)
        return
    if name in ("Accent", "Repeat"):
        _accent_repeat_button(e, name, pressed)
        return
    if not pressed:
        return

    if name == "Play":
        e.toggle_play()
    elif name == "Layout" and e.shift:
        state.lab = colorlab.ColorLab()
        state.last_pad_colors = None
    elif name == "Layout":
        layouts.switch_layout(e, e.layout + 1)
        state.show_popup("LAYOUT %d" % (e.layout + 1), LAYOUT_OSD[e.layout])
    elif name == "Scale":
        e.toggle_scale_menu()
    elif name == "Select (main)":
        e.clear_edit()
    elif name in SCREEN_BOTTOM:
        _track_button(e, SCREEN_BOTTOM[name])
    elif name in eng.DIVISIONS:
        if e.repeat_on or e.repeat_held:
            e.repeat_count = view.repeat_for_scene(name)
            state.show_popup("REPEAT", str(e.repeat_count))
        else:
            e.set_rate(e.rate_track, name)
            state.show_popup("RATE TRACK %d" % (e.rate_track + 1), name.replace("Scene ", ""))
    elif name in ("Octave Up", "Octave Down"):
        if e.layout == 1:
            e.shift_octave(1 if name == "Octave Up" else -1)
            state.show_popup("OCTAVE", octave_range_label(e))
    elif name == "Page Left":
        e.track_page = max(0, e.track_page - 1)
    elif name == "Page Right":
        if layouts.can_page_right(e):
            e.track_page += 1
    elif name == "Add":
        if e.add_track():
            state.show_popup("TRACK ADDED", str(len(e.tracks)))
        else:
            state.show_popup("MAX TRACKS", str(eng.MAX_TRACKS))
    elif name == "Save":
        if state.active_sequence_name is None:
            state.active_sequence_name = next_sequence_name()
        save_sequence(state, state.active_sequence_name)
        state.show_popup("SAVED", state.active_sequence_name)
    elif name == "Set":
        if state.browser_active:
            state.browser_active = False
        else:
            state.browser_active = True
            state.browser_names = list_sequences()
            state.browser_cursor = 0
    elif name == "D-Pad up" and state.browser_active:
        state.browser_cursor = max(0, state.browser_cursor - 1)
    elif name == "D-Pad down" and state.browser_active:
        state.browser_cursor = min(len(state.browser_names), state.browser_cursor + 1)
    elif name in ("Jog press", "D-Pad center") and state.browser_active:
        confirm_browser(state)


SCREEN_BOTTOM = {"Screen bottom %d" % n: n - 1 for n in range(1, 9)}


def _track_button(e, n):
    """Screen-bottom buttons: each track owns 8 / tracks_per_page buttons."""
    per = layouts.current(e).tracks_per_page
    slot = n // (8 // per)
    page = layouts.page_tracks(e)
    if slot >= len(page):
        return
    if e.shift:
        e.color_picker_track = page[slot]
    else:
        e.select_track(page[slot])


def _accent_repeat_button(e, name, pressed):
    """Tap toggles the mode. Hold plus a pad edits just that pad."""
    if name == "Accent":
        if pressed:
            e.accent_held, e.accent_used = True, False
        else:
            e.accent_held = False
            if not e.accent_used:
                e.accent_on = not e.accent_on
    else:
        if pressed:
            e.repeat_held, e.repeat_used = True, False
        else:
            e.repeat_held = False
            if not e.repeat_used:
                e.repeat_on = not e.repeat_on


def _lab_button(state, name):
    if name == "Save":
        colortable.save()
        state.show_popup("SAVED", "colors.json")
    elif name == "Select (main)" or (name == "Layout" and state.engine.shift):
        state.lab = None
        state.last_pad_colors = None


def handle_encoder(state, data):
    e = state.engine
    idx, delta = data.get("index"), data.get("delta") or 0
    name = data.get("name") or ""
    if delta == 0:
        return
    if state.lab is not None:
        if idx is not None and idx >= 0:
            state.lab.nudge(idx, delta, view.PALETTE)
        return
    if state.browser_active:
        if name == "Jog wheel turn":
            step = 1 if delta > 0 else -1
            state.browser_cursor = max(0, min(len(state.browser_names), state.browser_cursor + step))
        return
    if name == "Tempo wheel turn":
        bpm = e.pattern["bpm"] + delta
        e.pattern["bpm"] = max(eng.MIN_BPM, min(eng.MAX_BPM, bpm))
        state.show_popup("TEMPO", str(e.pattern["bpm"]))
        return
    if idx is None or idx < 0:
        return
    if e.scale_menu:
        e.nudge_scale_menu(idx, delta)
        return
    e.nudge(idx, delta)


_TOUCH_RE = re.compile(r"^Encoder (\d) touch$")


def handle_touch(state, data):
    e = state.engine
    if not data.get("touched") or state.browser_active or e.scale_menu:
        return
    m = _TOUCH_RE.match(data.get("name") or "")
    if not m:
        return
    idx = int(m.group(1)) - 1
    if e.edit_step() is not None:
        e.touch_param(idx)
        if e.delete:
            e.reset_param(idx)


def handle_external_midi(state, data):
    raw = base64.b64decode(data.get("raw", ""))
    if raw:
        state.engine.on_external_clock_byte(raw[0])


# -- sequences ------------------------------------------------------------------

def list_sequences():
    if not os.path.isdir(SEQUENCES_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(SEQUENCES_DIR) if f.endswith(".json"))


def save_sequence(state, name):
    os.makedirs(SEQUENCES_DIR, exist_ok=True)
    path = os.path.join(SEQUENCES_DIR, name + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state.engine.to_doc(), f)
    os.replace(tmp, path)


def load_sequence_doc(name):
    try:
        with open(os.path.join(SEQUENCES_DIR, name + ".json")) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def next_sequence_name():
    existing = set(list_sequences())
    n = 1
    while "Sequence %d" % n in existing:
        n += 1
    return "Sequence %d" % n


def confirm_browser(state):
    items = ["New"] + state.browser_names
    idx = state.browser_cursor
    if 0 <= idx < len(items):
        choice = items[idx]
        if choice == "New":
            state.engine.new_pattern()
            state.active_sequence_name = None
            state.show_popup("NEW", "Sequence")
        else:
            doc = load_sequence_doc(choice)
            if doc is not None and state.engine.load(doc):
                state.active_sequence_name = choice
                state.show_popup("LOADED", choice)
    state.browser_active = False
    state.last_pad_colors = None


# -- main loop ------------------------------------------------------------------

def main():
    state = State()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            env = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, id_ = env.get("method"), env.get("id")
        params = env.get("params") or {}

        if method is None and id_ is not None:
            if "error" in env:
                state.log("bcaseq: request %s failed: %s" % (id_, env["error"]))
            continue

        if method == "init":
            respond(id_, {})
        elif method == "handle":
            kind, data = params.get("kind"), params.get("data") or {}
            handler = {"pad": handle_pad, "button": handle_button, "encoder": handle_encoder,
                       "touch": handle_touch, "external_midi": handle_external_midi}.get(kind)
            if handler:
                handler(state, data)
        elif method == "draw":
            state.engine.tick()
            relight(state)
            respond(id_, view.draw(state))
        elif method == "close":
            state.engine.stop()
            for row in range(8):
                for col in range(8):
                    notify("set_pad", {"note": pad_note(col, row), "colour": 0})
            for cc in set(view.BUTTON_CC.values()):
                notify("set_button", {"cc": cc, "brightness": 0})
            respond(id_, {})
            break
        elif id_ is not None:
            respond_error(id_, "unknown method %r" % method)


if __name__ == "__main__":
    main()

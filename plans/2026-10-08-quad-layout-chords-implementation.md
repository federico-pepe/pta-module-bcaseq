# Layout 3 (Quad) and chord steps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Steps hold several notes (chords) in every layout, and a new Layout 3 enters notes by arming a pitch pad and tapping steps.

**Architecture:** `step["pitches"]` (sorted unique list) replaces `step["pitch"]`. The engine owns note editing (`toggle_note`, selected-note knob, trigger of every note). `layouts.py` maps pads: Layout 2 pitch pads toggle notes, Layout 3 adds a shared step grid plus an armed note. `view.py` shows the selected note and chord text.

**Tech Stack:** Python 3 stdlib only, `unittest`.

**Spec:** `plans/2026-10-08-quad-layout-chords.md`

## Global Constraints

- Python 3, stdlib only.
- Screen text is ASCII only.
- No backward compatibility with older save files (alpha). No `pitch` fallback on load.
- One shared clock `engine._ticks`. Do not add a per-track step counter.
- Do not `git commit` or `git push`. Leave work uncommitted. Land through a PR only when the user asks.
- Update README.md and CLAUDE.md when a control or behavior changes.
- Test command: `python3 -m unittest discover -s tests`.
- Hardware change: deploy, wait for the user to confirm on the device, then commit.

## Review Focus

- Chord with `repeat` > 1: every note repeats on every hit (test in Task 1).
- Removing the last note of a step turns the step off and deselects it; tapping again turns it on with that note (Task 1).
- Knob moving a note onto a note already in the step skips it; at the top or bottom of the range it stays (Task 1).
- Load with bad `pitches` (not a list, empty, strings, duplicates, out of range) never crashes and never gives an empty list (Task 1).
- Switching layout while a note is armed does not leave Layout 1 or 2 step pads adding the armed note (Task 3).
- Layout 3 with fewer than 3 tracks on the page (for example 4 tracks, page 2 has 1 track) leaves the missing pitch grids dark and does not crash (Task 3).

---

### Task 1: Step model, chord trigger, knob, persistence

**Files:**
- Modify: `engine.py` (new_step, load, to_doc, tap_step, `_remember_pitch`, remove `set_pitch`, nudge, reset_param, `_trigger`, stop, track dict)
- Modify: `layouts.py` (Layout 2 pitch pad, pad flash)
- Modify: `view.py` (`sounding_note`, edit view pitch)
- Modify: `tests/test_core.py`

**Interfaces:**
- Produces (engine):
  - `eng.clean_pitches(v) -> list[int]`
  - `Engine.sel_note: int`, `Engine.armed: tuple | None`, `Engine.grid_track: int`
  - `Engine.note_index(step) -> int`
  - `Engine.toggle_note(track_idx, step_idx, note, activate=False) -> None`
  - track keys `_lit_notes: list[int]` (replaces `_lit_note`); `_last_note` is removed.
  - `view.sounding_notes(t, now) -> list[int]` (replaces `sounding_note`)

- [ ] **Step 1: Write the failing tests**

Add this class to `tests/test_core.py` (after `LastNoteTest`):

```python
class ChordTest(unittest.TestCase):
    def step(self, e, ti=0, si=0):
        return e.tracks[ti]["steps"][si]

    def test_new_step_has_a_pitch_list(self):
        self.assertEqual(eng.new_step()["pitches"], [eng.DEFAULT_PITCH])

    def test_toggle_adds_sorted_and_removes(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)                      # step 0 on, [60]
        e.toggle_note(0, 0, 67)
        e.toggle_note(0, 0, 64)
        self.assertEqual(self.step(e)["pitches"], [60, 64, 67])
        self.assertEqual(e.sel.get(0), 0)
        self.assertEqual(e.sel_note, 1)                 # the note just added
        e.toggle_note(0, 0, 64)
        self.assertEqual(self.step(e)["pitches"], [60, 67])
        self.assertEqual(e.sel_note, 1)                 # clamped to a valid index

    def test_removing_last_note_turns_step_off(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 60)
        s = self.step(e)
        self.assertFalse(s["on"])
        self.assertEqual(s["pitches"], [60])
        self.assertNotIn(0, e.sel)
        e.toggle_note(0, 0, 62, activate=True)
        self.assertTrue(s["on"])
        self.assertEqual(s["pitches"], [62])

    def test_toggle_on_off_step_without_activate_keeps_it_off(self):
        e, _ = make()
        e.shift = True
        layouts.pad_press(e, 0, 7)                      # select only
        e.shift = False
        e.toggle_note(0, 0, 64)
        s = self.step(e)
        self.assertFalse(s["on"])
        self.assertEqual(s["pitches"], [64])
        self.assertEqual(e.tracks[0]["last_pitch"], 64)

    def test_activate_applies_accent_and_repeat_defaults(self):
        e, _ = make()
        e.accent_on = True
        e.repeat_on, e.repeat_count = True, 3
        e.toggle_note(0, 2, 64, activate=True)
        s = self.step(e, 0, 2)
        self.assertEqual((s["on"], s["vel"], s["repeat"]), (True, eng.ACCENT_VELOCITY, 3))

    def test_trigger_plays_every_note_with_shared_settings(self):
        e, notes = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 64)
        e.toggle_note(0, 0, 67)
        self.step(e)["repeat"] = 2
        e.start()
        e.tick(e.play_start + 0.001)
        ons = [n for n in notes if n[0] == "on"]
        self.assertEqual(sorted(n[2] for n in ons), [60, 64, 67])
        e.tick(e.play_start + e.step_duration(e.tracks[0]) * 0.6)    # second hit
        ons = [n for n in notes if n[0] == "on"]
        self.assertEqual(len(ons), 6)
        self.assertEqual(len({n[3] for n in ons}), 1)                # one velocity

    def test_knob_edits_selected_note_only(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 67)                         # [60, 67], selected = 67
        e.sel_note = 0
        e.nudge(0, 4)                                   # 60 -> 62
        self.assertEqual(self.step(e)["pitches"], [62, 67])
        e.nudge(0, 40)                                  # 62 up past 67: skip the taken note
        p = self.step(e)["pitches"]
        self.assertEqual(len(p), 2)
        self.assertIn(67, p)
        self.assertGreater(p[1], 67)
        self.assertEqual(e.sel_note, 1)                 # selection follows the moved note

    def test_knob_stays_at_range_edge(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        self.step(e)["pitches"] = [126, 127]
        e.sel_note = 0
        e.nudge(0, 40)
        self.assertEqual(self.step(e)["pitches"], [126, 127])

    def test_reset_param_resets_selected_note(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 67)
        e.reset_param(0)                                # selected 67 -> default C3, taken by 60: unchanged
        self.assertEqual(self.step(e)["pitches"], [60, 67])
        self.step(e)["pitches"] = [64, 67]
        e.sel_note = 0
        e.reset_param(0)
        self.assertEqual(self.step(e)["pitches"], [60, 67])

    def test_persist_pitches(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 67)
        e2, _ = make()
        self.assertTrue(e2.load(e.to_doc()))
        self.assertEqual(e2.tracks[0]["steps"][0]["pitches"], [60, 67])

    def test_load_cleans_bad_pitches(self):
        e, _ = make()
        for bad, want in ((None, [60]), ([], [60]), ("x", [60]), (["a", True], [60]),
                          ([64, 64, 300, -5], [0, 64, 127]), (5, [60])):
            doc = e.to_doc()
            doc["pattern"]["tracks"][0]["steps"][0]["pitches"] = bad
            e2, _ = make()
            self.assertTrue(e2.load(doc))
            self.assertEqual(e2.tracks[0]["steps"][0]["pitches"], want, bad)
```

Also update existing tests so they use the new model (mechanical):
- `tests/test_core.py:112`, `:317`, `:366`, `:372`: `["steps"][0]["pitch"]` becomes `["steps"][0]["pitches"]` compared to a list, for example `self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [62])`.
- `:309`: `self.assertEqual(e.tracks[1]["steps"][0]["pitches"][0] % 12, 7)`. This test now has Layout 2 pads toggling: the step starts as `[G]`? No: step 0 of track 2 starts as `[60]`, the pad adds G3, so the list is `[60, 67]`. Assert `sorted(p % 12 for p in e.tracks[1]["steps"][0]["pitches"]) == [0, 7]`.
- `:114-119` `test_pitch_pad_sets_step`: rename to `test_pitch_pad_toggles_note` and assert `[60, 62]`. Pressing the same pad again asserts `[60]`.
- `:347`, `:349`, `:356`, `:382`: compare `["pitches"]` to a one-item list. For `:347` the step-0 pad press now adds E3, so step 0 is `[60, 64]` and step 1 starts from `last_pitch` 64: assert step 1 `["pitches"] == [64]`.
- `:380-390` `test_memory_persists_and_old_files_load`: delete the `doc.pop(...)` block and the `e3` assertions. Keep the `e2` part. Rename the test to `test_memory_persists`.
- `:407`, `:415`, `:417`, `:427`, `:604`, `:608`, `:614`, `:631`: replace `t["_lit_note"] = N` with `t["_lit_notes"] = [N]`, and `assertEqual(t["_lit_note"], 60)` with `assertEqual(t["_lit_notes"], [60])`. Delete the `_last_note` line at `:608` and its assertion.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -15`
Expected: errors such as `KeyError: 'pitches'` or `AttributeError: ... toggle_note`.

- [ ] **Step 3: Implement the engine**

`engine.py`, near `new_step`:

```python
def clean_pitches(v):
    """A valid note list from saved data: sorted, unique, 0-127, never empty."""
    if not isinstance(v, list):
        return [DEFAULT_PITCH]
    notes = {max(0, min(127, n)) for n in v if isinstance(n, int) and not isinstance(n, bool)}
    return sorted(notes) or [DEFAULT_PITCH]


def new_step():
    return {"on": False, "pitches": [DEFAULT_PITCH], "pitch_set": False, "vel": DEFAULT_VELOCITY,
            "gate": 50, "prob": 100, "offset": 0, "repeat": 1, "len": 1}
```

`new_track`: delete `"_last_note": None,`; rename `"_lit_note": None,` to `"_lit_notes": [],` with the comment `# notes that just sounded, for the pitch pad flash`; update the `_show_until` comment to say `_lit_notes`.

`Engine.__init__`: after `self.sel = {}` add:

```python
        self.sel_note = 0            # index of the selected note inside the selected step
        self.armed = None            # Layout 3: (track, note) waiting for a step pad
        self.grid_track = 0          # Layout 3: track shown on the step grid
```

`clear_edit`: add `self.armed = None` and `self.sel_note = 0`. In `load` and `new_pattern` the line `self.edit_track, self.sel, self.track_page, self.rate_track = None, {}, 0, 0` is followed by `self.sel_note, self.armed, self.grid_track = 0, None, 0`.

`load`: replace the `pitch_set` legacy block (the `if "pitch_set" not in saved_steps[j]:` lines) with:

```python
                    st["pitches"] = clean_pitches(st["pitches"])
```

`select_step`: add `self.sel_note = 0` after `self.sel[track_idx] = step_idx`.

`tap_step`: replace `s["pitch"] = self.entry_pitch(track_idx)` with `s["pitches"] = [self.entry_pitch(track_idx)]`. Move the two default lines into a helper and call it:

```python
    def _entry_defaults(self, s):
        s["vel"] = ACCENT_VELOCITY if self.accent_on else DEFAULT_VELOCITY
        s["repeat"] = self.repeat_count if self.repeat_on else 1
```

In `tap_step` replace the `s["vel"] = ...` and `s["repeat"] = ...` lines with `self._entry_defaults(s)`.

Replace `_remember_pitch` and delete `set_pitch`:

```python
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
```

`nudge`, pitch branch:

```python
        if param == "pitch":
            note = s["pitches"][self.note_index(s)]
            taken = set(s["pitches"]) - {note}
            for _ in range(abs(n)):
                note = self._free_step(note, 1 if n > 0 else -1, taken, ti)
            self._set_selected_note(s, note)
            self._remember_pitch(ti, s, note)
```

`reset_param`, pitch branch:

```python
        if param == "pitch":
            note = self.default_pitch(ti)
            if note not in s["pitches"]:
                self._set_selected_note(s, note)
```

`_trigger`: inside the repeat loop replace the `_schedule` call with

```python
            for note in s["pitches"]:
                self._schedule(t["channel"], note, s["vel"], fire_at, off_at, now)
```

and replace the `_last_note` / `_lit_note` lines with `t["_lit_notes"] = list(s["pitches"])`. In `stop`, replace `t["_lit_note"] = None` with `t["_lit_notes"] = []`.

- [ ] **Step 4: Update layouts and view call sites**

`layouts.py` `pad_press`, pitch branch (Layout 2): replace the body after `si = e.sel.get(pt)` / `if si is None: return` with

```python
        root, scale = e.key_of(pt)
        notes = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave)
        note = notes[pitch_index(col, row)]
        if note <= 127:
            e.toggle_note(pt, si, note)
            e.edit_track = pt
            e.rate_track = pt
```

`layouts.py` `_paint_pitch`, flash block:

```python
    t = e.tracks[track_idx]
    if time.monotonic() < t["_lit_until"]:
        for i, note in enumerate(notes):
            if note in t["_lit_notes"] and note <= 127:
                grid[row0 + i // 4][col0 + i % 4] = PLAYHEAD
```

`view.py`: replace `sounding_note` with

```python
def sounding_notes(t, now):
    """Notes a track is playing right now. The screen shows no pitch for a
    note that is not triggered."""
    return t["_lit_notes"] if now < t["_show_until"] else []
```

Main screen (`playing = sounding_note(t, now)` block): `notes = sounding_notes(t, now)`; if `notes`, draw `note_name(notes[0])`. Edit view: `pitch = s["pitch"] if s["on"] else None` becomes `pitch = s["pitches"][e.note_index(s)] if s["on"] else None`; the other-track branch uses `notes = sounding_notes(t, now)`, `pitch = notes[0] if notes else None`. (Task 2 shows full chords.)

- [ ] **Step 5: Run the full suite**

Run: `python3 -m unittest discover -s tests`
Expected: all tests pass. Fix any remaining `"pitch"` references: `grep -n '"pitch"\]\|_lit_note\b\|_last_note' *.py tests/*.py` must show only `PARAMS`/`PARAM_RANGE` entries.

---

### Task 2: Chord display and pitch pad marking

**Files:**
- Modify: `view.py` (`fit_scale`, main-screen note text, edit-view note label)
- Modify: `layouts.py` (`_paint_pitch`: notes in the selected step)
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `view.sounding_notes`, `Engine.note_index`, `Engine.sel`.
- Produces: `view.fit_scale(text, width) -> int` (3, 2 or 1).

- [ ] **Step 1: Write the failing tests**

```python
class ChordDisplayTest(unittest.TestCase):
    def setUp(self):
        self.e, _ = make()
        self.st = _make_state(self.e)    # reuse the helper the existing screen tests use

    def texts(self):
        return [(o["params"]["s"], o["params"].get("scale"))
                for o in view.draw(self.st)["ops"] if o["kind"] == "text"]

    def test_fit_scale(self):
        self.assertEqual(view.fit_scale("C3", view.CHAR_W * 2 * 3), 3)
        self.assertEqual(view.fit_scale("x" * 10, view.CHAR_W * 10 * 2), 2)
        self.assertEqual(view.fit_scale("x" * 10, 1), 1)

    def test_main_screen_joins_sounding_notes(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_notes"], t["_show_until"] = [60, 64, 67], _t.monotonic() + 5
        self.assertIn("C3 E3 G3", [s for s, _ in self.texts()])

    def test_edit_view_shows_selected_note_and_position(self):
        layouts.pad_press(self.e, 0, 7)
        self.e.toggle_note(0, 0, 67)
        self.assertIn(("G3", 3), self.texts())
        self.assertIn("NOTE 2/2", [s for s, _ in self.texts()])
        self.e.sel_note = 0
        self.assertIn(("C3", 3), self.texts())

    def test_single_note_keeps_pitch_label(self):
        layouts.pad_press(self.e, 0, 7)
        self.assertIn("PITCH", [s for s, _ in self.texts()])

    def test_pitch_pads_mark_notes_of_the_selected_step(self):
        e = self.e
        e.layout = 1
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 64)                         # [60, 64]
        grid = layouts.pad_colors(e)
        notes = eng.grid_pitches(0, "major", True, e.octave)
        i = notes.index(64)
        self.assertEqual(grid[4 + i // 4][4 + i % 4], e.tracks[0]["color"])
        j = notes.index(62)
        self.assertEqual(grid[4 + j // 4][4 + j % 4], layouts.PITCH_WHITE)
```

Before writing `_make_state`, check how the existing screen tests in `tests/test_core.py` (class around line 590, the one with `big_notes`) build `self.st`; reuse that setup code verbatim in `setUp` instead of a new helper.

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest tests.test_core.ChordDisplayTest 2>&1 | tail -15`
Expected: FAIL (`fit_scale` missing, no "NOTE 2/2").

- [ ] **Step 3: Implement**

`view.py`, near `rate_label`:

```python
def fit_scale(text, width):
    """Biggest text scale (3, 2, 1) that fits the width."""
    for scale in (3, 2):
        if CHAR_W * scale * len(text) <= width:
            return scale
    return 1
```

Main screen: replace the single-note draw with

```python
            notes = sounding_notes(t, now)
            if notes:
                text = " ".join(note_name(n) for n in notes)
                ops.append(_text(x + 8, NOTE_BASELINE, text, c, fit_scale(text, col_w - 16)))
```

Edit view: the label block becomes

```python
        n_notes = len(s["pitches"])
        if pitch is not None:
            ops.append(_text(x + 8, 66, note_name(pitch), c, 3))
        if hot or pitch is not None:
            label = "PITCH" if not hot or n_notes == 1 else "NOTE %d/%d" % (e.note_index(s) + 1, n_notes)
            ops.append(_text(x + 8, 80, label, c))
```

Other tracks in the edit view show a joined chord at `fit_scale(text, 96)`: compute `text` from `sounding_notes` and draw it in place of `note_name(pitch)` with that scale; the hot track keeps the single selected note at scale 3. The width 96 is the space left of the knobs (`x + 8` to `x + 104`).

`layouts.py` `_paint_pitch`: after computing `color`, add

```python
    es = e.sel.get(track_idx)
    in_step = set(t["steps"][es]["pitches"]) if es is not None and t["steps"][es]["on"] else set()
```

(define `t = e.tracks[track_idx]` before it and drop the later duplicate `t =` line), and change the color chain to

```python
        elif note % 12 == root or note in in_step:
            grid[r][c] = color
```

- [ ] **Step 4: Run the suite**

Run: `python3 -m unittest discover -s tests`
Expected: all pass.

---

### Task 3: Layout 3

**Files:**
- Modify: `layouts.py` (Layout3, `LAYOUTS`, `switch_layout`, `track_for_slot`, `pad_press`, `pad_colors`, constants, `grid_track`)
- Modify: `run.py` (`LAYOUT_OSD`, octave buttons)
- Modify: `view.py` (octave button colors)
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `Engine.toggle_note`, `Engine.armed`, `Engine.grid_track`.
- Produces: `layouts.Layout3`, `layouts.grid_track(e) -> int`, `layouts.has_octave(e) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
class Layout3Test(unittest.TestCase):
    def setUp(self):
        self.e, _ = make()
        for _ in range(3):
            self.e.add_track()                           # 7 tracks? see note below
        layouts.switch_layout(self.e, 2)

    def pitch_pad(self, slot, note, ti_offset=0):
        e = self.e
        track = layouts.first_track(e) + (slot - 1)
        root, scale = e.key_of(track)
        i = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave).index(note)
        col0 = 0 if slot == 2 else 4
        row0 = 4 if slot == 1 else 0
        return col0 + i % 4, row0 + i // 4

    def test_three_tracks_per_page(self):
        self.assertEqual(layouts.current(self.e).tracks_per_page, 3)
        self.assertEqual(layouts.page_tracks(self.e), [0, 1, 2])

    def test_arm_then_step_adds_note_to_grid_track(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(2, 64))      # slot 2 = second track
        self.assertEqual(e.armed, (1, 64))
        self.assertEqual(e.grid_track, 1)
        layouts.pad_press(e, 0, 7)                        # step 0
        s = e.tracks[1]["steps"][0]
        self.assertEqual((s["on"], s["pitches"]), (True, [64]))
        layouts.pad_press(e, *self.pitch_pad(2, 67))
        layouts.pad_press(e, 0, 7)
        self.assertEqual(s["pitches"], [64, 67])
        layouts.pad_press(e, 0, 7)                        # armed 67 again: removes it
        self.assertEqual(s["pitches"], [64])
        self.assertEqual(e.tracks[0]["steps"][0]["on"], False)

    def test_pressing_armed_pad_disarms(self):
        e = self.e
        pad = self.pitch_pad(1, 64)
        layouts.pad_press(e, *pad)
        layouts.pad_press(e, *pad)
        self.assertIsNone(e.armed)
        layouts.pad_press(e, 0, 7)                        # nothing armed: plain tap
        self.assertEqual(e.tracks[e.grid_track]["steps"][0]["pitches"], [eng.DEFAULT_PITCH])

    def test_shift_selects_without_adding(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(1, 64))
        e.shift = True
        layouts.pad_press(e, 0, 7)
        self.assertFalse(e.tracks[0]["steps"][0]["on"])
        self.assertEqual(e.sel.get(0), 0)

    def test_switching_layout_clears_armed(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(1, 64))
        layouts.switch_layout(e, 0)
        self.assertIsNone(e.armed)
        layouts.pad_press(e, 0, 7)                        # Layout 1 TL: plain tap
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [eng.DEFAULT_PITCH])

    def test_step_grid_colors(self):
        e = self.e
        e.start()
        e.tick(e.play_start + 0.001)
        layouts.pad_press(e, 1, 7)                        # step 1 on, grid track 0
        grid = layouts.pad_colors(e)
        self.assertEqual(grid[7][0], layouts.PLAYHEAD)    # step 0 is playing
        self.assertEqual(grid[7][1], layouts.STEP_SELECTED)   # step 1 selected
        self.assertEqual(grid[7][2], layouts.STEP_DIM_WHITE)

    def test_grid_track_falls_back_when_off_page(self):
        e = self.e
        e.grid_track = 5
        self.assertEqual(layouts.grid_track(e), 0)

    def test_missing_tracks_leave_pitch_grid_dark(self):
        e, _ = make()                                     # 4 tracks
        layouts.switch_layout(e, 2)
        e.track_page = 1                                  # only track 4 on this page
        grid = layouts.pad_colors(e)
        for r in range(8):
            for c in range(4, 8):
                if r >= 4:
                    self.assertEqual(grid[r][c], layouts.OFF)
        layouts.pad_press(e, 4, 4)                        # empty grid: no crash
        self.assertIsNone(e.armed)

    def test_octave_buttons_active_in_layout_3(self):
        self.assertTrue(layouts.has_octave(self.e))
        layouts.switch_layout(self.e, 0)
        self.assertFalse(layouts.has_octave(self.e))
```

Notes for the implementer: `make()` creates `eng.DEFAULT_TRACK_COUNT` tracks. Read that constant first. If it is 4, drop the `add_track` loop in `setUp`. Fix slot 3's `pitch_pad` mapping (slot 3 = col0 4, row0 0) if a test needs it. Slot 1 = col0 4, row0 4. Slot 2 = col0 0, row0 0.

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest tests.test_core.Layout3Test 2>&1 | tail -15`
Expected: errors (`switch_layout` index out of range, `has_octave` missing).

- [ ] **Step 3: Implement**

`layouts.py` constants:

```python
STEP_DIM_WHITE = 118   # Layout 3 step grid, empty step. Check on the device.
ARMED = 120            # Layout 3 armed pitch pad (pure white, max brightness). Same as in-scale pads: check on the device.
```

Layout:

```python
class Layout3:
    name = "Layout 3"
    tracks_per_page = 3
    seq_slots = {}
    pitch_slots = {1: 0, 2: 1, 3: 2}   # TR, BL, BR edit the first, second, third track
    shared_grid_slot = 0               # TL: one step grid for grid_track
    arm_mode = True
    has_octave = True
```

Add `has_octave = True` and `arm_mode = False` to `Layout2`, and `has_octave = False` and `arm_mode = False` to `Layout1`. `LAYOUTS = [Layout1, Layout2, Layout3]`.

```python
def has_octave(e):
    return current(e).has_octave


def grid_track(e):
    """Layout 3: the track shown on the step grid. Falls back to the first track on the page."""
    page = page_tracks(e)
    if e.grid_track in page:
        return e.grid_track
    return page[0] if page else 0
```

`switch_layout`: add `e.armed = None` at the end.

`track_for_slot`: replace the first lines with

```python
def track_for_slot(e, slot):
    lay = current(e)
    if getattr(lay, "shared_grid_slot", None) == slot:
        return grid_track(e) if page_tracks(e) else None
    off = lay.seq_slots.get(slot)
```

(the rest unchanged).

`pad_press`, step branch: replace the final `else: e.tap_step(ti, si)` with

```python
        elif current(e).arm_mode and e.armed is not None:
            e.toggle_note(ti, si, e.armed[1], activate=True)
        else:
            e.tap_step(ti, si)
```

`pad_press`, pitch branch: after `pt = pitch_track_for_slot(e, slot)` / `if pt is not None:` insert, before `si = e.sel.get(pt)`:

```python
        if current(e).arm_mode:
            root, scale = e.key_of(pt)
            note = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave)[pitch_index(col, row)]
            if note > 127:
                return
            e.armed = None if e.armed == (pt, note) else (pt, note)
            e.grid_track = pt
            e.rate_track = pt
            return
```

`pad_colors`, step painting: inside the `if ti is not None:` loop, change the color choice to

```python
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
```

`_paint_pitch`: add `armed = e.armed` and, in the loop, after the existing color chain, mark the armed pad:

```python
        if e.armed == (track_idx, note) and note <= 127:
            grid[r][c] = ARMED
```

(Place it after the chain and before the flash block, so the green flash still wins.)

`run.py`: `LAYOUT_OSD = ["4 TRACKS", "2 TRACKS + PITCH", "3 TRACKS + STEPS"]`. The octave handler `if e.layout == 1:` becomes `if layouts.has_octave(e):`. `view.py` `button_colors`: `if e.layout == 1:` becomes `if layouts.has_octave(e):`.

- [ ] **Step 4: Run the suite**

Run: `python3 -m unittest discover -s tests`
Expected: all pass.

- [ ] **Step 5: Check the 3-track screen**

Run a draw smoke test in Python (no hardware): build an engine, `switch_layout(e, 2)`, add a step, call `view.draw` for the main screen and the edit screen, and confirm no exception. Add it as `test_layout3_screens_draw` in `Layout3Test` using the same state setup as `ChordDisplayTest`. Also confirm `layouts.slen_track(e, idx)` for idx 0-7 returns `None` or a page track without error (`8 // 3 = 2` encoders per track, so encoders 7 and 8 are unused).

---

### Task 4: Docs

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: README.md**
  - In the Layout 1 section: add that a step can hold several notes, all with the same VEL, GATE, PROB, OFF, REP and N LEN. The Pitch encoder edits the selected note. Layout 1 cannot add notes.
  - Replace the Layout 2 text about pitch pads: a pitch pad adds the note to the selected step. Press it again to remove it. Removing the last note turns the step off. The Pitch encoder edits the selected note. Notes in the selected step show in the track color.
  - Add a `### Layout 3` section: top-left quadrant is the step grid of one track (dim white, green playhead, track color for steps that are on, white for the selected step). The other quadrants are the pitch grids of the 3 tracks on the page (Page buttons move by 3, Octave buttons work). Tap a pitch pad to arm the note (pure white pad) and make its track the grid track. Tap a step to add the armed note, tap again to remove it. Tap the armed pad again to disarm. Shift + step selects without changing.
  - Main screen: say a chord shows all sounding notes joined, and the edit view shows the selected note with `NOTE i/n`.
  - Save files: remove nothing, but add one line that files from builds before this change do not load.

- [ ] **Step 2: CLAUDE.md**
  - Files section: no change. Under Rules or a new short "Notes" list add: `step["pitches"]` is a sorted unique list, never `step["pitch"]`. Use `engine.toggle_note` and `engine.note_index`. Layout 3 uses `engine.armed` and `engine.grid_track`.
  - Open questions for hardware: add the Layout 3 colors (`STEP_DIM_WHITE` 118, `ARMED` 120, marked in-step notes) and chord text on the screen.

- [ ] **Step 3: Final check**

Run: `python3 -m unittest discover -s tests`
Expected: all pass. Leave everything uncommitted. Tell the user the work is ready and list the hardware checks: Layout 3 step grid color, armed pad color, in-step note marking, chord text on the main and edit screens, and the 3-column screen layout.

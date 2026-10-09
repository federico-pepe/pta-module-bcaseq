# Layout 3 (Quad) and chord steps

Branch: `feat/quad-layout`. Status: draft, waiting for review.

## Goal
Add Layout 3. Top-left quadrant is one 16-step grid. The other three quadrants
are pitch grids for three tracks. The user arms a note on a pitch pad, then taps
steps to add that note. A step can hold several notes (a chord). Layouts 1 and 2
change too, because the step model changes for all layouts.

## Decisions (agreed with the user)
- A step holds a list of notes. The old single `pitch` is removed.
- One step grid. It shows one track: the track of the last armed or touched pitch pad.
- The pitch knob edits the selected note of the selected step, not the first note.
- Layout 2 pitch pads toggle a note in the selected step (add, press again to remove).
- Layout 1 has no way to add notes. It plays chords and the knob edits the selected note.
- Screen note text scaling for chords is a later task. For now the screen joins the note names.

## Model
- `step["pitches"]`: sorted list of ints 0-127, no duplicates, 1 or more items. `pitch_set` stays.
- `new_step()` starts with `pitches = [DEFAULT_PITCH]`.
- `engine.sel_note`: index of the selected note in the selected step. Reset to 0 when
  the selected step changes. Clamp after any add or remove.
- `engine.armed`: `(track, note)` or None. Layout 3 only. Cleared by `clear_edit()`.
- Helpers in engine: `add_note(track, step, note)`, `remove_note(track, step, note)`,
  `toggle_note(track, step, note)`. They keep the list sorted and unique.
  `remove_note` on the last note turns the step off and keeps `[note]` as its stored pitch.
- `set_pitch(track, step, note)` changes the selected note: replace `pitches[sel_note]`,
  then re-sort and fix `sel_note`. If `note` is already in the step, do nothing.
- `last_pitch` stays: the last note entered on the track. `entry_pitch` is unchanged.

## Trigger
`_trigger` loops over `s["pitches"]` inside the repeat loop and schedules each note
with the step's `vel`, `gate`, `prob`, `offset`, `repeat`, `len`. One probability
roll per step, not per note. `_last_note` and `_lit_note` become lists: `_last_notes`,
`_lit_notes`. The pad flash and the screen read the lists.

## Save and load
- Save writes `pitches`. Version stays 1.
- Load accepts `pitches` (validated: list of ints, clamped 0-127, de-duplicated, sorted,
  never empty). Bad data falls back to the default step.
- Alpha: no backward compatibility. Files saved by older builds are not supported. No `pitch` fallback.

## Knob
`nudge` for param `pitch` moves `pitches[sel_note]` with `_step_pitch`. It skips a
target that is already in the step. Then it re-sorts and updates `sel_note` to follow the note.
Reset on the pitch knob sets the selected note to `default_pitch`.

## Layouts
Layout 1: unchanged mapping. Reads and writes through the new helpers.

Layout 2: a pitch pad press toggles that note in the selected step of its track.
`sel_note` points to the pad's note after the press (or stays clamped after removal).
A pad whose note is in the selected step is marked on the grid (see Colors).

Layout 3 (`Layout3`, `tracks_per_page = 3`):
- Slot 0: step grid for `engine.edit_track_for_grid` (the grid track, see below).
- Slots 1, 2, 3: pitch grids for the 3 tracks on the page, in order. Page button scrolls by 3.
- Grid track: `engine.grid_track`, the last track touched by a pitch pad or a step pad.
  If it is not on the page, use the first track on the page.
- Pitch pad press: set `armed = (track, note)`, `grid_track = track`, `rate_track = track`.
  Pressing the armed pad again disarms it.
- Step pad press:
  - Armed and no Accent or Repeat held: `toggle_note(grid_track, step, armed note)`. Select the
    step and the note. A step that ends with no notes is off and deselected.
  - Accent or Repeat held: unchanged (`apply_hold`).
  - Shift: select without changing, as today.
  - Not armed: `tap_step`, as today.
- Steps past the track length are ignored, as today.

## Colors
- Layout 3 step grid: every pad dim white (`dim(PITCH_WHITE)`), playhead green (126),
  selected step bright white (120). A step that is on shows the track color.
  Open question: should "on" steps be visible as track color, or stay dim white so the
  grid is only a position view? Default in this plan: track color, so the user can see the pattern.
- Pitch grids: reuse `_paint_pitch`. Root = track color, in scale = white, out of scale and
  In Key off = off. The armed pad is bright white. Notes in the selected step of the grid
  track are painted in the track color's bright shade; in Layout 2 the same marking applies.
  Last point is a hardware question: confirm on the device.
- Pad flash for sounding notes uses all of `_lit_notes`.

## Screen
Edit view and main view show the notes of the step joined by a space. If the string is too
wide for the track strip the view shows the first notes and `+N`. Text scaling is later.

## Tests
- `tests/test_core.py`: new step model, toggle/add/remove, load of `pitches`
  with bad data, trigger sends all notes with shared gate, knob edits the selected note and skips
  duplicates, Layout 2 toggle, Layout 3 arm then step, pad colors for Layout 3.
- Existing pitch tests move to `pitches[0]` or the helpers.
- Run: `python3 -m unittest discover -s tests`.

## Docs
Update README.md and CLAUDE.md: Layout 3 controls, chord model, Layout 2 pad change.

## Out of scope
- Chord text scaling on the screen.
- Per-note velocity or gate.
- A way to add notes in Layout 1.

## Hardware check (before commit)
Step grid colors, armed pad brightness, selected-note marking, and screen text for chords.

# Working track, fixed 4-column screen, consistent note entry

Branch: `feat/quad-layout`. Status: draft, waiting for review. Builds on `2026-10-08-quad-layout-chords.md`.

## Decisions (agreed with the user)
- Root pad, when selected: dim version of the track color. Unselected root stays the full track color.
- "Main button" = Select (main). The screen always shows 4 tracks, in every layout.
- Switching track with a screen-bottom button keeps the armed note. The note value goes to the new track.
- Touching or turning an S LEN knob makes that track the working track.
- Layout 2 uses the same arm-then-tap-step entry as Layout 3.
- Chord name display (tonal.js idea): not in this change. Plain Python chord table later.

## Working track
- `engine.rate_track` is the one working track. `engine.grid_track` is removed.
- It is set by: screen-bottom buttons, S LEN touch or turn, a pitch pad press, any step selection, Page Left/Right.
- Page Left/Right moves the screen page by 4 tracks and sets the working track to the first track of the new page.

## Two track windows
- Screen window: `layouts.screen_tracks(e)`. Always 4 tracks per page (`SCREEN_TRACKS = 4`), page = `engine.track_page`.
  Used by the screen, the screen-bottom buttons, the S LEN encoders, `editing()`, and Page buttons.
- Pad window: `layouts.pad_tracks(e)`.
  - Layout 1: the screen window (unchanged).
  - Layout 2: the pair that contains the working track: start = `rate_track // 2 * 2`.
  - Layout 3: the triple that contains the working track: start = `rate_track // 3 * 3`.
- `tracks_per_page` on a layout becomes `pad_group` (4, 2, 3). `first_track`, `can_page_right`, `switch_layout` stop depending on it.
  Switching layout no longer changes `track_page`. It still clears `armed`.

## Screen
- Always 4 columns of `W // 4`. Tracks missing from the screen page leave their column empty (no dividers drawn for them is acceptable, dividers stay).
- S LEN is always the second encoder of a track column: encoders 1, 3, 5, 7 (0-based). `slen_encoder(e, slot) = slot * 2 + 1`.
- Screen-bottom buttons: 2 per track, 4 tracks, from the screen window.

## Entering notes (Layouts 2 and 3)
- `engine.armed` becomes a note number or None.
- Pitch pad press: if `armed == note` and the pad's track is the working track, disarm. Otherwise `armed = note`, working track = the pad's track.
- Step pad press with a note armed (and no Accent, Repeat or Shift): `toggle_note(track, step, armed, activate=True)`.
  The track is the quadrant's track in Layout 2, the working track in Layout 3.
- Nothing armed: step press is `tap_step`, as in Layout 1.
- The old Layout 2 behavior (pitch pad edits the selected step) is removed.
- The armed pad is drawn on the working track's pitch grid only.

## Pitch grid colors (Layouts 2 and 3)
A note is "selected" when it is the armed note on the working track's grid, or it is in the selected step of that grid's track.

| pad | unselected | selected |
| --- | --- | --- |
| root | track color | dim track color |
| in key (not root) | dim white (118) | bright white (120) |
| out of key | off | bright white (120) |

The green flash for sounding notes still wins over these colors.

## S LEN and the pads
`handle_encoder` and `handle_touch` for an S LEN knob set `rate_track` to that track first. In Layout 3 the step grid then shows it. In Layout 2 the pad pair moves to it.

## Tests
Update the Layout 3 and Layout 2 pad tests for the new model. New tests: working track set by button, by S LEN touch and turn, and by Page buttons; armed note follows a track change; Layout 2 arm-then-step; pitch grid color table; fixed 4-column screen and S LEN encoder positions in Layouts 2 and 3; pad window for each layout.

## Docs
README.md and CLAUDE.md: working track, fixed screen, Layout 2 entry change, colors.

## Out of scope
Chord names, text scaling beyond what exists.

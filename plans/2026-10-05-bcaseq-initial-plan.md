# BCA Sequencer (pta-module-bcaseq) plan

## Context
New PTA module: MIDI sequencer for Push with switchable pad/screen Layouts (Layout button, OSD on switch). Layouts change only display/pad mapping, never functionality. Reuse `~/Developer/pta-module-gridseq` (Python 3 stdlib, newline-JSON over stdio) and improve where noted. Repo: GitHub `federico-pepe/pta-module-bcaseq` (create only when user asks; no commit/push unrequested).

## Architecture (mirror gridseq split)
- `manifest.json` (id `bcaseq`, `exec: python3 run.py`, needs_midi_in/out)
- `run.py` - only file touching stdio; protocol loop, event dispatch, LED diff + **1s keepalive resend** (gridseq lacks it), save/load
- `engine.py` - model, clock, triggers, no I/O
- `view.py` - pure functions: screen ops, pad/button colors, OSD
- `palette.json` - copy from gridseq (generated, don't edit)
- `layouts.py` - Layout interface: `pad_colors(state)`, `handle_pad(...)`, `screen_ops(state)`, `encoder targets`. Layout 1 and 2 implement it; adding more later is cheap.
- `tests/` (unittest, engine/view pure; plus one subprocess protocol smoke test), `CLAUDE.md`, `README.md`, `MANUAL.md`, `plans/`, `.gitignore`, `.github/workflows/release.yml` (tag -> tarball, knobs pattern)

## Reuse from gridseq (file refs in gridseq)
- Protocol helpers `run.py:51-67`, request/response tagging `run.py:107,536`
- Tick from `draw` via `engine.tick(now)` `engine.py:980`; external clock `engine.py:951-978`
- Step/track model `engine.py:167,180`; `resolve_note`/scale tables `engine.py:41-71,1147`; `TRACK_COLORS` `engine.py:124`
- Popup/OSD `run.py:97-105`, `view.py:575-594`; button CC map `view.py:65-98`; save/load + browser `run.py:558-611`, `view.py:402`
- Defensive `Engine.load` `engine.py:288`

## Improvements over gridseq
1. Single `Friction` helper (accumulate delta, threshold 4, integer steps) replacing ~9 copy-pasted blocks; per-parameter accumulators, not shared between held-step and track edits.
2. Deferred ratchet notes keep step velocity (gridseq hardcodes 100, `engine.py:1193`).
3. Move `random` import to top.
4. LED keepalive.
5. Atomic sequence file writes.
6. Real tests.

## Global behavior
- Start with 4 tracks; `Add` button (CC 32) appends a track (cap 32). Page Left/Right moves by 4 tracks (L1) or 2 tracks (L2).
- 16 steps per track (one 4x4 quadrant). Each track has own color from `TRACK_COLORS`.
- Scene launch buttons: **global** rate, 1/4 (bottom) to 1/32t (top); gridseq `DIVISIONS` table, active one pulses. Rate becomes one engine field (not per track).
- Repeat button: dim by default, full white when on (button idx 122). While on, Scene buttons set repeat count 1..8 top to bottom (rate remains but is not editable until Repeat off). Accent same LED logic; when on, pad-created steps get velocity 127 (otherwise default 100).
- Scale button: menu with Key (enc 1), Scale (enc 2), In Key on/off (enc 3); toggle to exit. Global flag `in_key` plus root/scale (global rather than per-track - to confirm in impl; gridseq was per track).
- Layout button: cycles layouts, shows OSD popup ("LAYOUT", name). Need Layout button CC: look up in push-tethered-app `internal/pushmap/buttons.go`.
- Octave up/down: shifts pitch-pad range in L2; OSD shows range (e.g. "C3 - B5").
- Extras in scope per user: save/load sequences (Save + Set browser), external MIDI clock sync.

## Step edit params (8 encoders, 2 rows of 4 on screen)
Pitch, Velocity, Gate, Probability, Offset, MIDI Channel, Repeat, Length. Encoders use Friction (threshold for pitch/offset/repeat/length/channel; fine for vel/gate/prob like gridseq `THROTTLED_PARAMS`). Clamp, never wrap. Ranges from `_nudge_step_param` (`engine.py:915`). Delete + encoder touch resets param to default.

## Layout 1 - four tracks, 4x4 each
- Quadrants: TL=t1, TR=t2, BL=t3, BR=t4 of current page.
- Pad color = track color; off steps unlit/dim track color; playhead step green; tapped (toggled-on/selected) pad white. Step order: row by row, left to right.
- Tap pad = toggle step and select it (enter Edit mode). Shift+pad = select only, no toggle.
- Screen: 4 columns, one per track in track color. Play mode: note names triggered (C3, D3, ...). Edit mode: 8 params as 2 rows of 4 for selected step; corners drawn around the edited track's column and its color turns white while editing. Corner bracket drawing: rect ops (screen is 960x160, ASCII only, `CHAR_W=7`).

## Layout 2 - two tracks + pitch pickers
- TL and BL quadrants = sequencers (tracks on page of 2). TR/BR = 16-pitch pickers for the track on its row (TR for TL track, BR for BL track), editing the pitch of that track's selected step.
- Pad order in quadrant: bottom-left start, rightwards then up.
- In Key ON: grid walks scale degrees (C major: C3 D3 E3 F3 / G3 A3 B3 C4 / D4 ... as in IDEA), root pad = track color, all others white.
- In Key OFF: chromatic from root-oct base, root in track color, in-scale white, out-of-scale unlit.
- Octave up/down shifts the base by an octave; OSD shows range.
- Screen: two track columns/params like L1 adapted.

## Milestones
1. Scaffold repo (manifest, palette, protocol loop, popup, LED diff + keepalive).
2. Engine: model, global rate, tick, triggers, friction helper, MIDI out, external clock.
3. Layout 1 + edit mode + screen.
4. Accent/Repeat/Scene logic, Add/Page, Scale menu.
5. Layout 2 + octave OSD.
6. Save/load, docs (STE for docs via simple-english; caveman for code comments per push-family rules), CI workflow.
7. Tests throughout; deploy to Push via `go run ./cmd/pushapp -install` in push-tethered-app; **wait for user's on-device confirmation before any commit**.

## Verification
- `python3 -m unittest` (engine timing, scale grids for both In Key modes, friction, load validation).
- Subprocess protocol smoke test (init, pad, button, draw) with deadline-bounded reads.
- On Push: layout switch + OSD, pad colors/playhead green, shift-select, rate/repeat scene buttons, Accent/Repeat LEDs, scale menu, octave OSD, save/load, ext clock. Ask user what the device showed.

## Open items to resolve during build
- Layout button CC; whether Scale root/scale is global vs per-track; L2 pitch-pad behavior when no step selected.

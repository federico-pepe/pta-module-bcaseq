# BCA Sequencer

A MIDI step sequencer for Push, run as a PTA process module. The Layout button changes how the
sequencer shows on the pads and screen. The functions stay the same.

## Controls
- **Layout**: switch layout. The screen shows the layout name.
- **Add**: add a track (starts with 4). **Page Left/Right**: move by one page of tracks.
- **Scene buttons**: rate of the last touched track, 1/4 (bottom) to 1/32t (top). The screen shows each track's rate. With Repeat on: repeat count 1 (top) to 8 (bottom).
- **Select (main)**: leave edit mode and return to the main screen.
- **Accent**: tap to toggle. When on, new steps get velocity 127. Hold it and press a pad to set that step to 127 without toggling the step (press again to undo).
- **Repeat**: tap to toggle. When on, new steps get the chosen repeat count. Hold it and press a pad to set that step's repeat count without toggling the step. Scene buttons choose the count while Repeat is held or on.
- **Screen-bottom buttons**: select a track (its Scene target). Shift + button: pick a track color with the border pads. Release Shift to leave the picker.
- **Scale**: menu. Encoder 1 = key, 2 = scale, 4 = In Key on/off, 5 = Scope. Scope Global: all tracks share one key and scale. Scope Track: each track has its own, and the menu edits the last touched track (switching to Track copies the global key to every track). In Key is always global.
- **Tempo wheel**: BPM. **Play**: start/stop. **Save / Set**: save and load sequences.

### Layout 1
Four 4x4 quadrants, one track each. Empty steps are a dim version of the track color. Steps that are on use the full track color. The selected step is white. The playhead is green. Steps run left to right, then down. Tap a pad to toggle a step
and edit it. Shift + pad selects without toggling. Edit encoders 1-8: Pitch (big), then gauge knobs for VEL, GATE, PROB, OFF, MIDI, REP, N LEN. N LEN is the length of the selected note in steps. The note holds for that many steps, and later steps can still trigger. All tracks stay visible. The edited track is white with corners. When you touch or turn a knob, its value replaces the name under it. Delete + touch resets a parameter.

A step can hold several notes (a chord). All notes of a step share VEL, GATE, PROB, OFF, REP and N LEN. The Pitch encoder edits the selected note and skips notes that are already in the step. Layout 1 cannot add notes: build chords in Layout 2 or 3.

### Layout 2
Two tracks (left quadrants). The right quadrants pick the pitch of the selected step of the track
on the same row. Octave Up/Down moves the range and shows it on screen. When a track plays a note, its pad in the pitch grid flashes green.

A pitch pad adds its note to the selected step. Press it again to remove the note. Removing the last note turns the step off. Notes in the selected step show in the track color.

### Layout 3
Top-left is one 16-step grid for one track (the grid track): dim white for empty steps, the track color for steps that are on, white for the selected step, green for the playhead. The other three quadrants are the pitch grids of the 3 tracks on the page. Page Left/Right moves by 3 tracks, Octave Up/Down moves the range.

Tap a pitch pad to arm its note (the pad turns pure white) and make its track the grid track. Tap a step to add the armed note, tap it again to remove it. Tap the armed pad again to disarm. With nothing armed a step pad toggles the step as in the other layouts. Shift + step selects without changing. Select (main) and changing layout disarm. The screen shows the selected note of the selected step and `NOTE i/n` when the step is a chord.

Each track remembers the last note you entered, with a pitch pad or the Pitch encoder. A new step starts from that note. A step that already has notes keeps them when you turn it off and on.

### Main screen
Each track has an S LEN knob (the second encoder of its column) that sets the length of its sequence. A pitch shows only while its note plays. A chord shows all its notes, joined, with a smaller font when they do not fit. BPM and scale are at the top. Each track shows the last note played and a bar for its position in the loop. Track names and rates are at the bottom, above the Screen-bottom buttons. The selected track is a filled block.

### Colors
Track colors use the hardware palette for the pads and measured screen colors for the screen
(`colortable.py`). To tune them on a Push, use the `colorlab-py` example module in
`push-tethered-app`. Copy its `colors.json` next to `run.py`. This module reads it at start up.

### Clock
All tracks read one shared clock (24 ticks per quarter note, from the internal tempo or from
external MIDI clock). A track step is the clock position divided by the length of a step at its
rate, modulo its sequence length. So tracks with the same length and rate stay together, a new
track joins in phase, and tracks with different rates share one beat grid. Tracks with different
lengths loop against each other and meet again after the least common multiple of their lengths
(for example 16 and 12 steps meet every 48 steps). When you change a length, the track jumps to
the place it would be if it always had that length. The first clock tick after a MIDI Start plays
step 1.

Sequence files saved before chords (a step with `pitch` instead of `pitches`) do not load.

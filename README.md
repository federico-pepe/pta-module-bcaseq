# BCA Seq

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
- **Scale**: menu. Encoder 1 = key, 2 = scale, 3 = In Key on/off.
- **Tempo wheel**: BPM. **Play**: start/stop. **Save / Set**: save and load sequences.

### Layout 1
Four 4x4 quadrants, one track each. Empty steps are a dim version of the track color. Steps that are on use the full track color. The selected step is white. The playhead is green. Steps run left to right, then down. Tap a pad to toggle a step
and edit it. Shift + pad selects without toggling. Edit encoders 1-8: Pitch (big), then gauge knobs for VEL, GATE, PROB, OFF, MIDI, REP, LEN. All tracks stay visible. The edited track is white with corners. When you touch or turn a knob, its value replaces the name under it. Delete + touch resets a parameter.

### Layout 2
Two tracks (left quadrants). The right quadrants pick the pitch of the selected step of the track
on the same row. Octave Up/Down moves the range and shows it on screen.

### Main screen
BPM and scale are at the top. Each track shows the last note played and a bar for its position in the loop. Track names and rates are at the bottom, above the Screen-bottom buttons. The selected track is a filled block.

### Color Lab
Hold Shift and press Layout. The pads show a track color next to its dim shade. The screen shows
three swatches: the palette color, the screen color, and the dim color. Encoder 1 picks the track
color. Encoder 2 picks the dim pad shade. Encoders 3-5 set the screen R, G and B so the middle
swatch matches the pads. Encoder 6 resets the screen color. Save writes `colors.json` next to
`run.py`. Copy that file into the repo to keep it. Shift + Layout or Select (main) exits.

# BCA Seq

A MIDI step sequencer for Push, run as a PTA process module. The Layout button changes how the
sequencer shows on the pads and screen. The functions stay the same.

## Controls
- **Layout**: switch layout. The screen shows the layout name.
- **Add**: add a track (starts with 4). **Page Left/Right**: move by one page of tracks.
- **Scene buttons**: rate of the last touched track, 1/4 (bottom) to 1/32t (top). The screen shows each track's rate. With Repeat on: repeat count 1 (top) to 8 (bottom).
- **Select (main)**: leave edit mode and return to the main screen.
- **Accent**: toggle. When on, new steps get velocity 127.
- **Repeat**: toggle. When on, new steps get the chosen repeat count.
- **Scale**: menu. Encoder 1 = key, 2 = scale, 3 = In Key on/off.
- **Tempo wheel**: BPM. **Play**: start/stop. **Save / Set**: save and load sequences.

### Layout 1
Four 4x4 quadrants, one track each. Empty steps show the track color. Steps that are on are white. The playhead is green. Steps run left to right, then down. Tap a pad to toggle a step
and edit it. Shift + pad selects without toggling. Edit encoders 1-8: Pitch (big), then small knobs for VEL, GATE, PROB, OFF, MIDI, REP, LEN. All tracks stay visible. The edited track is white with corners. A knob shows its value when you touch or turn it. Delete + touch resets a parameter.

### Layout 2
Two tracks (left quadrants). The right quadrants pick the pitch of the selected step of the track
on the same row. Octave Up/Down moves the range and shows it on screen.

### Main screen
Each track shows its name, rate, the last note played and a bar for its position in the loop.

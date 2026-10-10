# BCA Sequencer

A MIDI step sequencer for Push, run as a PTA process module. The Layout button changes how the
sequencer shows on the pads and screen. The functions stay the same.

## Controls
- **Layout**: switch layout. The screen shows the layout name.
- **Add**: add a track (starts with 4). **Page Left/Right**: move the screen by 4 tracks. The first track of the new page becomes the working track.
- **Scene buttons**: rate of the last touched track, 1/4 (bottom) to 1/32t (top). The screen shows each track's rate. With Repeat on: repeat count 1 (top) to 8 (bottom).
- **Select (main)**: leave edit mode and return to the main screen.
- **Accent**: tap to toggle. When on, new steps get velocity 127. Hold it and press a pad to set that step to 127 without toggling the step (press again to undo).
- **Repeat**: tap to toggle. When on, new steps get the chosen repeat count. Hold it and press a pad to set that step's repeat count without toggling the step. Scene buttons choose the count while Repeat is held or on.
- **Working track**: the track that you touched last. These controls make a track the working track: a screen-bottom button, a pad, a pitch pad, and the S LEN knob of the track (touch or turn). The working track is the target of the Scene buttons. In Layout 3, it is the track on the step grid. In Layouts 2 and 3, the pads show the tracks around it.
- **Screen**: the screen always shows 4 tracks in 4 columns, in every layout. S LEN is the second knob of each track.
- **Screen-bottom buttons**: select a track (the working track). Shift + button: pick a track color with the border pads. Release Shift to leave the picker.
- **Scale**: menu. Encoder 1 = key, 2 = scale, 4 = In Key on/off, 5 = Scope, 6 = Names (Sharp or Flat). Names changes the spelling of the key, the notes, the octave range, and the chords (C# or Db). Scope Global: all tracks share one key and scale. Scope Track: each track has its own, and the menu edits the last touched track (switching to Track copies the global key to every track). In Key is always global.
- **Tempo wheel**: BPM. Press the tempo encoder to lead or follow a MIDI clock (see "Lead and follow" below). **Play**: start/stop. **Save / Set**: save and load sequences.

### Layout 1
Four 4x4 quadrants, one track each. Empty steps are a dim version of the track color. Steps that are on use the full track color. The selected step is white. The playhead is green. Steps run left to right, then down. Tap a pad to toggle a step
and edit it. Shift + pad selects without toggling. Edit encoders 1-7: Pitch (big), then gauge knobs for VEL, GATE, PROB, OFF, REP, N LEN. N LEN is the length of the selected note in steps. The note holds for that many steps, and later steps can still trigger. All tracks stay visible. The edited track is white with corners. When you touch or turn a knob, its value replaces the name under it. Delete + touch resets a parameter.

A step can hold several notes (a chord). All notes of a step have the same VEL, GATE, PROB, OFF, REP and N LEN. The Pitch encoder changes the selected note. It skips notes that are already in the step. Layout 1 cannot add notes. To build a chord, use Layout 2 or 3.

### Layout 2
The left quadrants show two tracks: the pair of tracks that holds the working track. Each right quadrant is the pitch grid of the track on the same row. Octave Up/Down moves the pitch range and shows it on the screen. When a track plays a note, its pad in the pitch grid flashes green. Enter notes as described in "Enter notes" below.

### Layout 3
The top-left quadrant is one 16-step grid for the working track. Empty steps are dim white. Steps that are on use the track color. The selected step is white. The playhead is green. The other three quadrants are the pitch grids of the three tracks that hold the working track. Octave Up/Down moves the pitch range.

### Pitch pads (Layouts 2 and 3)
In-key pads are dim white. The root pad is a dim track color. Out-of-key pads are off. A selected pad is bright white, and a selected root pad is the full track color. A pad is selected when its note is armed, or when the note is in the selected step.

### Enter notes (Layouts 2 and 3)
Press a pitch pad to arm its note. The track of the pad becomes the working track.

To arm several notes, hold one pitch pad and press more pitch pads. All of these notes are armed. They stay armed when you release the pads. A new press of a pitch pad, with no other pad held, replaces the armed notes. To disarm, press the only armed pad again.

Press a step pad to add all armed notes to the step. Press the step pad again to remove all armed notes. If the step has no notes left, it turns off. In Layout 2, the notes go to the track of the quadrant that you press.

If you select another track with a screen-bottom button, the armed notes stay armed. The next step that you press gets these notes on the new track.

In Layouts 2 and 3, a step press acts when you release the pad, and only if you held it for less than 0.4 seconds. Arming a pitch pad acts at once. Pressing the only armed pad again to disarm it acts on release.

To put notes into one step without arming, hold the step pad and tap pitch pads. Each tap adds the note to that step, and a second tap removes it. The note goes to the same step number on the track of the pitch pad. So you can hold step 5 and tap notes on the grids of three tracks. The armed notes do not change. When you release the step pad, the step stays as it is.

If no note is armed, a step pad toggles the step, as in Layout 1. Shift + step pad selects the step and does not change it. Select (main) and a layout change disarm all notes.

The screen shows the selected note of the selected step.

Each track remembers the last note that you entered, with a pitch pad or the Pitch encoder. A new step starts from that note. A step keeps its notes when you turn it off and on.

### Long press (Layouts 2 and 3)
Hold a pad for 0.4 seconds to see where the notes are. A long press changes nothing. Release the pad to go back.

- **Long press on a step pad**: every pitch grid shows the notes that its track plays in that step. Non-root notes are bright white. A root note is the full track color. All other pads are dark gray.
- **Long press on a pitch pad**: the step grid of that track turns dark gray. Only the steps that play the note keep their color. The playhead stays green. In Layout 2, only the quadrant of that track changes.
- Layout 1 has no pitch grids. A long press there does nothing special, and a step press acts at once.

### Main screen
Each track has two knobs. The first encoder of its column is the MIDI knob: it sets the MIDI channel of the track (1 to 16). The second encoder is the S LEN knob: it sets the length of the sequence of the track. Touch a knob to see its value. Delete + touch resets the knob (channel 1, length 16). A pitch shows only while its note plays. A chord with a name shows the name big and its notes small below it. Examples are `Cmaj7` and `Amin/C`. Minor is "min" because the screen font has upper case only. A set of notes with no name shows the notes big. Text never goes over the S LEN knob. Notes that do not fit become `+N`. The edit view does the same for the selected step. Each track shows the last note played and a bar for its position in the loop. Track names and rates are at the bottom, above the Screen-bottom buttons. The selected track is a filled block.

### Colors
Track colors use the hardware palette for the pads and measured screen colors for the screen
(`colortable.py`). To tune them on a Push, use the `colorlab-py` example module in
`push-tethered-app`. Copy its `colors.json` next to `run.py`. This module reads it at start up.

### Lead and follow
The module has two clock roles. Press the tempo encoder to change the role. The screen shows a popup (`CLOCK LEAD` or `CLOCK FOLLOW`), and the transport stops.

- **Follow** (default): the module follows the MIDI clock that it receives. It measures the tempo of the sender. The status line shows it, for example `120 BPM EXT`, and note lengths follow it. The sender owns the tempo, so the tempo wheel does nothing.
- **Lead**: the module sends MIDI clock (24 ticks per beat), Start, and Stop. It ignores the clock that it receives. The status line shows `120 BPM LEAD`. The tempo wheel changes the BPM, and the DAW follows. Play and Stop on the module start and stop the DAW.

To make Ableton Live follow the module in Lead mode, turn on Sync for the MIDI input port of the module in the Link, Tempo and MIDI settings of Live. Then switch the clock of Live to EXT. I did not test this in Live. The clock comes from a thread, so a busy screen does not delay it. The timing is not the same as a hardware clock.

### Clock
All tracks read one shared clock (24 ticks per quarter note, from the internal tempo or from
external MIDI clock). A track step is the clock position divided by the length of a step at its
rate, modulo its sequence length. So tracks with the same length and rate stay together, a new
track joins in phase, and tracks with different rates share one beat grid. Tracks with different
lengths loop against each other and meet again after the least common multiple of their lengths
(for example 16 and 12 steps meet every 48 steps). When you change a length, the track jumps to
the place it would be if it always had that length. The first clock tick after a MIDI Start plays
step 1.

Sequence files that were saved before chords (a step with `pitch` instead of `pitches`) do not load.

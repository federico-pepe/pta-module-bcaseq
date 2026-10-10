# BCA Sequencer: Manual

BCA Sequencer is a step sequencer for Push. Each track plays 16 steps, and each step can hold one note or a chord. The sequencer sends MIDI notes to your DAW or synth.

## 1. Quick start

1. Press **Layout** until the screen shows "LAYOUT 1".
2. Tap a pad. The step turns on.
3. Press **Play**. The green pad is the playhead.
4. Turn the knobs of the screen to change the sound of the step.

Press **Select (main)** to leave the step and go back to the main screen.

## 2. The screen and the tracks

The screen always shows 4 tracks in 4 columns. The **Page Left** and **Page Right** buttons move to the next 4 tracks. Press **Add** to add a track.

Each track has two knobs on the main screen:
- **MIDI**: the MIDI channel of the track (1 to 16).
- **S LEN**: the number of steps that the track plays (1 to 16).

Touch a knob to see its value. Hold **Delete** and touch a knob to reset it.

The track that you touched last is the **working track**. A pad, a knob, or a screen-bottom button makes a track the working track. The **Scene** buttons set how fast this track plays, from 1/4 to 1/32t.

To change the color of a track, hold **Shift** and press its screen-bottom button. Then press a color on the border pads.

## 3. The three layouts

Press **Layout** to change the layout. The layouts show the same sequencer in different ways.

- **Layout 1**: 4 tracks, one on each quarter of the pads. Use it to play simple patterns.
- **Layout 2**: 2 tracks on the left. The right side shows the notes that you can pick for each track.
- **Layout 3**: one track on the top-left, with 3 note grids. Use it to build chords on many tracks.

On the step grids, a step that is on shows the track color. The selected step is white, and the playhead is green.

## 4. Edit a step (all layouts)

Tap a pad to turn a step on. Tap it again to turn it off. The screen then shows the step. Turn the knobs to change it:

| Knob | What it does |
|---|---|
| Pitch | The note. Turn the knob to move the note up or down. |
| VEL | How loud the note is. |
| GATE | How long the note sounds inside the step. |
| PROB | The chance that the note plays. 100 is always. |
| OFF | Moves the note a little earlier or later. |
| REP | Repeats the note inside the step (a ratchet). |
| N LEN | Holds the note for more steps. |

Hold **Shift** and tap a pad to select a step and not change it. Hold **Delete** and touch a knob to reset it.

**Accent** makes new steps loud. Hold **Accent** and tap a step to make only that step loud. **Repeat** works the same way for the repeat count.

## 5. Enter notes (Layouts 2 and 3)

The note grids show 16 notes for each track. Dim white pads are notes in the key. The root note is dim in the track color. Pads that you select become bright.

**Arm a note, then tap steps**
1. Tap a note pad. The note is now armed.
2. Tap a step pad. The step gets the note.
3. Tap the same step again to remove the note.

**Arm many notes at once.** Hold one note pad and tap more note pads. All of them are armed. Tap a step to add all of them as a chord.

**Add notes to one step.** Hold a step pad and tap note pads. Each note goes into that step. You can tap notes on the grids of other tracks too. Each note goes into the same step number on its own track.

**See what a step holds.** Hold a step pad for half a second. The note grids light up the notes that the step plays on every track.

**See where a note plays.** Hold a note pad for half a second. The step grid dims all steps that do not play the note.

Use **Octave Up** and **Octave Down** to move the note grids up or down.

## 6. Chords

When a step has a chord, the screen shows the name of the chord, for example Cmaj7 or Amin. The notes are small below the name. All notes of a step share the same VEL, GATE, PROB, OFF, REP and N LEN.

The Pitch knob changes one note of the chord at a time. This is the note that you added last. After you select a step again, it is the lowest note.

## 7. Key and scale

Press **Scale** to open the menu. Turn a knob to change a value:

| Knob | Setting |
|---|---|
| 1 | Key (the root note) |
| 2 | Scale |
| 4 | In Key: On shows only notes in the scale. Off shows all notes. |
| 5 | Scope: Global gives one key to all tracks. Track gives each track its own key. |
| 6 | Names: Sharp (C#) or Flat (Db) |

Press **Scale** again or **Select (main)** to close the menu.

## 8. Tempo and clock

Turn the **tempo wheel** to change the BPM. Press the **Play** button to start and stop.

The sequencer can follow a clock or lead it. Press the **tempo encoder** to change the role. The screen shows "CLOCK LEAD" or "CLOCK FOLLOW".

- **Follow** (default): the sequencer follows the MIDI clock of your DAW. The clock sets the speed, so the tempo wheel does nothing while the clock arrives.
- **Lead**: the sequencer sends the clock. The tempo wheel changes the BPM, and **Play** starts and stops the DAW. First set your DAW to follow an external clock.

## 9. Save and load

- Press **Save** to save the sequence. The screen shows the name.
- Press **Set** to open the list. Use the D-pad or the jog wheel to pick a sequence. Press the jog wheel or the D-pad center to load it.
- Pick "New" in the list to start an empty sequence.

## 10. Quick reference

| I want to... | Do this |
|---|---|
| Turn a step on | Tap its pad |
| Change a note | Select the step and turn the Pitch knob |
| Make a chord | Arm many notes, then tap a step |
| Remove a note | Tap the step again with the note armed |
| Change the track channel | Turn the MIDI knob on the main screen |
| Make a track shorter | Turn the S LEN knob |
| Reset a knob | Hold Delete and touch the knob |
| Lead or follow the clock | Press the tempo encoder |

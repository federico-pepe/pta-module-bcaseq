# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/) (pre-1.0: expect breaking changes
between minor versions).

## [Unreleased]

## [0.3.1] - 2026-10-10

### Added

- `MANUAL.md`: a short user guide. The release tarball includes it.
- External clock: the module measures the tempo of the sender. The status line shows it with `EXT`, and note lengths follow it.
- Lead mode: press the tempo encoder to send MIDI clock, Start and Stop (`clockout.py`) and ignore the incoming clock. The tempo wheel then sets the BPM and the DAW follows. Press again to follow a clock.

### Changed

- The MIDI channel of a track moves from the edit view to the main screen: the first encoder of each track column. The edit view has 7 encoders now (Pitch, VEL, GATE, PROB, OFF, REP, N LEN).
- Main screen: each track shows two knobs (MIDI and S LEN). The note and chord text moved below the knobs, with a maximum size of 2.

## [0.3.0] - 2026-10-09

### Added

- Layout 3: one step grid for the working track and three pitch grids. Press a pitch pad to arm a note. Press a step to add it.
- Chords: a step can hold several notes. All notes of a step share VEL, GATE, PROB, OFF, REP and N LEN. The Pitch encoder changes the selected note.
- Multiple armed notes: hold a pitch pad and press more pitch pads. A step press adds all of them. A second press removes all of them.
- Chord names (`chords.py`). A named chord shows the name big and its notes small on the main screen and in the edit view.
- Scale menu, encoder 6 (Names): sharp or flat spelling for the key, the notes, the octave range and the chords.
- Working track: a screen-bottom button, a pad, a pitch pad, or the S LEN knob of a track makes it the working track.
- Long press (Layouts 2 and 3): hold a step pad to light its notes on every pitch grid. Hold a pitch pad to dim the steps that do not play the note.
- Hold a step pad and tap pitch pads (Layouts 2 and 3): each tap adds or removes the note in the same step of the track of that pad.
- `CHANGELOG.md`.

### Changed

- Layouts 2 and 3: a step press acts on release, and only for a short press (less than 0.4 s). Layout 1 is unchanged.
- The screen always shows 4 tracks in 4 columns, in every layout. S LEN is always the second knob of a track. Page Left/Right moves the screen by 4 tracks.
- Layout 2 enters notes like Layout 3: arm a note, then press a step. A pitch pad no longer replaces the pitch of the selected step.
- Pitch pad colors: in-key pads are dim white, the root is a dim track color. A selected pad is bright white, and a selected root is the full track color.
- Sequence files store `pitches` (a list) for each step. Files that were saved by older builds do not load.
- The empty step pads (Layouts 2 and 3) and the pads that a long press dims use palette 119 (dark gray).
- The edit view always shows the `PITCH` label.

### Fixed

- The release tarball now includes `chords.py`. Without it, `view.py` fails to import.

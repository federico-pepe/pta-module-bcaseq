# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/) (pre-1.0: expect breaking changes
between minor versions).

## [Unreleased]

### Added

- Layout 3: one step grid for the working track and three pitch grids. Press a pitch pad to arm a note. Press a step to add it.
- Chords: a step can hold several notes. All notes of a step share VEL, GATE, PROB, OFF, REP and N LEN. The Pitch encoder changes the selected note.
- Multiple armed notes: hold a pitch pad and press more pitch pads. A step press adds all of them. A second press removes all of them.
- Chord names (`chords.py`). A named chord shows the name big and its notes small on the main screen and in the edit view.
- Scale menu, encoder 6 (Names): sharp or flat spelling for the key, the notes, the octave range and the chords.
- Working track: a screen-bottom button, a pad, a pitch pad, or the S LEN knob of a track makes it the working track.
- `CHANGELOG.md`.

### Changed

- The screen always shows 4 tracks in 4 columns, in every layout. S LEN is always the second knob of a track. Page Left/Right moves the screen by 4 tracks.
- Layout 2 enters notes like Layout 3: arm a note, then press a step. A pitch pad no longer replaces the pitch of the selected step.
- Pitch pad colors: in-key pads are dim white, the root is a dim track color. A selected pad is bright white, and a selected root is the full track color.
- Sequence files store `pitches` (a list) for each step. Files that were saved by older builds do not load.

"""chords.py - name a set of MIDI notes ("Cmaj7", "Amin/C"). Pure, no I/O.

The screen font is upper case only, so minor is "min", never "m" (Cm would read as CM).

Each pitch class is tried as the root and its interval set is looked up in
CHORDS. The lowest note wins as the root, then the first entry in the table.
A root that is not the lowest note gets a slash bass.
"""

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# (suffix, intervals above the root). Earlier entries win ties.
CHORDS = [
    ("", (0, 4, 7)), ("min", (0, 3, 7)), ("dim", (0, 3, 6)), ("aug", (0, 4, 8)),
    ("sus2", (0, 2, 7)), ("sus4", (0, 5, 7)),
    ("7", (0, 4, 7, 10)), ("maj7", (0, 4, 7, 11)), ("min7", (0, 3, 7, 10)),
    ("minMaj7", (0, 3, 7, 11)), ("min7b5", (0, 3, 6, 10)), ("dim7", (0, 3, 6, 9)),
    ("7sus4", (0, 5, 7, 10)),
    ("6", (0, 4, 7, 9)), ("min6", (0, 3, 7, 9)),
    ("add9", (0, 2, 4, 7)), ("minadd9", (0, 2, 3, 7)),
    ("9", (0, 2, 4, 7, 10)), ("maj9", (0, 2, 4, 7, 11)), ("min9", (0, 2, 3, 7, 10)),
    ("5", (0, 7)),
]
_BY_INTERVALS = {frozenset(iv): (i, suffix) for i, (suffix, iv) in enumerate(CHORDS)}


def pitch_class_name(pc, flats=False):
    return (FLAT_NAMES if flats else SHARP_NAMES)[pc % 12]


def chord_name(notes, flats=False):
    """Name of a chord made of MIDI notes, or None when it has no name.
    Order and octave doubling do not matter. Two notes only name a fifth."""
    if not notes:
        return None
    bass = min(notes) % 12
    pcs = sorted({n % 12 for n in notes})
    best = None
    for root in pcs:
        found = _BY_INTERVALS.get(frozenset((pc - root) % 12 for pc in pcs))
        if found is None:
            continue
        index, suffix = found
        if len(pcs) == 2 and root != bass:
            continue
        key = (root != bass, index)
        if best is None or key < best[0]:
            best = (key, root, suffix)
    if best is None:
        return None
    _, root, suffix = best
    name = pitch_class_name(root, flats) + suffix
    if root != bass:
        name += "/" + pitch_class_name(bass, flats)
    return name

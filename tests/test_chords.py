import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chords


class ChordNameTest(unittest.TestCase):
    def test_names(self):
        for notes, want in (
            ([60, 64, 67], "C"), ([60, 63, 67], "Cmin"), ([60, 63, 66], "Cdim"),
            ([60, 64, 68], "Caug"), ([60, 62, 67], "Csus2"), ([60, 65, 67], "Csus4"),
            ([60, 64, 67, 70], "C7"), ([60, 64, 67, 71], "Cmaj7"), ([60, 63, 67, 70], "Cmin7"),
            ([60, 63, 67, 71], "CminMaj7"), ([60, 63, 66, 70], "Cmin7b5"), ([60, 63, 66, 69], "Cdim7"),
            ([60, 64, 67, 69], "C6"), ([60, 63, 67, 69], "Cmin6"),
            ([60, 62, 64, 67], "Cadd9"), ([60, 62, 63, 67], "Cminadd9"),
            ([60, 64, 67, 70, 74], "C9"), ([60, 64, 67, 71, 74], "Cmaj9"), ([60, 63, 67, 70, 74], "Cmin9"),
            ([60, 67], "C5"),
        ):
            self.assertEqual(chords.chord_name(notes), want, notes)

    def test_order_and_octaves_do_not_matter(self):
        self.assertEqual(chords.chord_name([67, 60, 64]), "C")
        self.assertEqual(chords.chord_name([60, 64, 67, 72, 76]), "C")

    def test_inversions_get_a_slash_bass(self):
        self.assertEqual(chords.chord_name([64, 67, 72]), "C/E")
        self.assertEqual(chords.chord_name([55, 60, 64]), "C/G")
        self.assertEqual(chords.chord_name([59, 62, 65, 67]), "G7/B")

    def test_lowest_note_wins_between_equal_chords(self):
        self.assertEqual(chords.chord_name([57, 60, 64, 67]), "Amin7")    # A C E G
        self.assertEqual(chords.chord_name([60, 64, 67, 69]), "C6")     # same notes, C lowest

    def test_flats_and_sharps(self):
        self.assertEqual(chords.chord_name([61, 65, 68]), "C#")
        self.assertEqual(chords.chord_name([61, 65, 68], flats=True), "Db")
        self.assertEqual(chords.chord_name([66, 70, 73, 76]), "F#7")
        self.assertEqual(chords.chord_name([66, 70, 73, 76], flats=True), "Gb7")
        self.assertEqual(chords.chord_name([64, 67, 70, 73], flats=True), "Edim7")
        self.assertEqual(chords.chord_name([62, 65, 70], flats=True), "Bb/D")
        self.assertEqual(chords.chord_name([62, 65, 70]), "A#/D")

    def test_slash_bass_uses_the_spelling(self):
        self.assertEqual(chords.chord_name([61, 64, 69]), "A/C#")
        self.assertEqual(chords.chord_name([61, 64, 69], flats=True), "A/Db")

    def test_no_name(self):
        for notes in ([], [60], [60, 64], [60, 61, 62], [60, 61, 62, 63, 64, 65], [67, 72]):
            self.assertIsNone(chords.chord_name(notes), notes)


if __name__ == "__main__":
    unittest.main()

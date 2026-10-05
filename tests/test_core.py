import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine as eng
import layouts
import view


def make():
    notes = []
    e = eng.Engine(lambda ch, n, v: notes.append(("on", ch, n, v)),
                   lambda ch, n: notes.append(("off", ch, n)))
    return e, notes


def names(notes):
    return [view.note_name(n) for n in notes]


class FrictionTest(unittest.TestCase):
    def test_threshold_and_remainder(self):
        f = eng.Friction()
        self.assertEqual(f.feed("a", 3), 0)
        self.assertEqual(f.feed("a", 2), 1)   # 5 -> 1 step, 1 left
        self.assertEqual(f.feed("a", -5), -1)  # -4 -> -1 step
        self.assertEqual(f.feed("b", 1, 1), 1)


class GridTest(unittest.TestCase):
    def test_in_key_c_major(self):
        g = eng.grid_pitches(0, "major", True, 3)
        self.assertEqual(names(g[:4]), ["C3", "D3", "E3", "F3"])
        self.assertEqual(names(g[4:8]), ["G3", "A3", "B3", "C4"])
        self.assertEqual(names(g[12:]), ["A4", "B4", "C5", "D5"])

    def test_chromatic(self):
        g = eng.grid_pitches(0, "major", False, 3)
        self.assertEqual(names(g[:4]), ["C3", "C#3", "D3", "D#3"])
        self.assertEqual(names(g[12:]), ["C4", "C#4", "D4", "D#4"])

    def test_layout2_pitch_colors(self):
        e, _ = make()
        e.layout = 1
        grid = layouts.pad_colors(e)
        # TR quadrant bottom-left pad = root of top track
        self.assertEqual(grid[4][4], e.tracks[0]["color"])
        # BR quadrant: in key, non-root pad white
        self.assertEqual(grid[0][5], layouts.PITCH_WHITE)
        e.pattern["in_key"] = False
        grid = layouts.pad_colors(e)
        self.assertEqual(grid[0][5], 0)          # C# not in C major
        self.assertEqual(grid[0][6], layouts.PITCH_WHITE)  # D in scale

    def test_octave_range(self):
        e, _ = make()
        e.octave = 8
        e.shift_octave(1)
        top = eng.max_octave(0, "major", True)
        self.assertEqual(e.octave, 8 if top >= 8 else e.octave)
        self.assertLessEqual(max(eng.grid_pitches(0, "major", True, e.octave)), 127)


class EditTest(unittest.TestCase):
    def test_tap_selects_and_toggles(self):
        e, _ = make()
        layouts.pad_press(e, 2, 7)        # TL quadrant, top row, col 2 = step 2
        self.assertTrue(e.tracks[0]["steps"][2]["on"])
        self.assertEqual(e.edit_step(), (0, 2))
        layouts.pad_press(e, 2, 7)
        self.assertFalse(e.tracks[0]["steps"][2]["on"])
        self.assertIsNone(e.edit_step())

    def test_shift_selects_only(self):
        e, _ = make()
        e.shift = True
        layouts.pad_press(e, 4, 0)        # BR quadrant, bottom-left pad = step 12 of track 3
        self.assertFalse(e.tracks[3]["steps"][12]["on"])
        self.assertEqual(e.edit_step(), (3, 12))

    def test_accent_sets_velocity_and_repeat_count(self):
        e, _ = make()
        e.accent_on, e.repeat_on, e.repeat_count = True, True, 3
        layouts.pad_press(e, 0, 7)
        s = e.tracks[0]["steps"][0]
        self.assertEqual((s["vel"], s["repeat"]), (127, 3))

    def test_encoder_friction_and_clamp(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(1, 5)                      # velocity not throttled
        self.assertEqual(e.tracks[0]["steps"][0]["vel"], 105)
        e.nudge(6, 3)                      # repeat throttled: no change yet
        self.assertEqual(e.tracks[0]["steps"][0]["repeat"], 1)
        e.nudge(6, 1)
        self.assertEqual(e.tracks[0]["steps"][0]["repeat"], 2)
        e.nudge(1, 500)
        self.assertEqual(e.tracks[0]["steps"][0]["vel"], 127)

    def test_pitch_nudge_in_key(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 4)                      # one scale step up from C
        self.assertEqual(e.tracks[0]["steps"][0]["pitch"], 62)

    def test_pitch_pad_sets_step(self):
        e, _ = make()
        e.layout = 1
        layouts.pad_press(e, 0, 7)        # TL step 0
        layouts.pad_press(e, 5, 4)        # TR quadrant bottom row, index 1 = D3
        self.assertEqual(e.tracks[0]["steps"][0]["pitch"], 62)


class ClockTest(unittest.TestCase):
    def test_play_triggers_rows_in_order(self):
        e, notes = make()
        layouts.pad_press(e, 0, 7)        # step 0
        layouts.pad_press(e, 0, 6)        # step 4
        e.start()
        t0 = e.play_start
        e.tick(t0 + 0.001)
        self.assertEqual(notes[0][:3], ("on", 1, 60))
        d = e.step_duration(e.tracks[0])
        e.tick(t0 + d * 4 + 0.001)
        self.assertEqual(sum(1 for n in notes if n[0] == "on"), 2)

    def test_ratchet_keeps_velocity(self):
        e, notes = make()
        e.accent_on = e.repeat_on = True
        e.repeat_count = 2
        layouts.pad_press(e, 0, 7)
        e.start()
        t0 = e.play_start
        e.tick(t0 + 0.001)
        e.tick(t0 + e.step_duration(e.tracks[0]) * 0.6)
        ons = [n for n in notes if n[0] == "on"]
        self.assertEqual([n[3] for n in ons], [127, 127])

    def test_rate_per_track(self):
        e, _ = make()
        e.set_rate(0, "Scene 1/4")
        self.assertAlmostEqual(e.step_duration(e.tracks[0]), 0.5)
        self.assertAlmostEqual(e.step_duration(e.tracks[1]), 0.125)

    def test_rate_follows_touched_track(self):
        e, _ = make()
        layouts.pad_press(e, 4, 0)         # track 4 (BR)
        self.assertEqual(e.rate_track, 3)

    def test_progress_bar_per_track_length(self):
        e, _ = make()
        e.tracks[1]["length"] = 8
        e.start()
        t0 = e.play_start
        e.tick(t0 + e.step_duration(e.tracks[0]) * 4.0)
        self.assertAlmostEqual(e.tracks[0]["_progress"], 4 / 16.0, places=2)
        self.assertAlmostEqual(e.tracks[1]["_progress"], 4 / 8.0, places=2)

    def test_external_clock_advances(self):
        e, notes = make()
        layouts.pad_press(e, 0, 7)
        e.start()
        for _ in range(6):
            e.on_external_clock_byte(0xF8)
        self.assertEqual(e.tracks[0]["_current_step"], 0)
        self.assertEqual(len([n for n in notes if n[0] == "on"]), 1)


class MainButtonTest(unittest.TestCase):
    def test_clear_edit(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        layouts.pad_press(e, 4, 7)
        e.scale_menu = True
        e.clear_edit()
        self.assertIsNone(e.edit_step())
        self.assertEqual(e.sel, {})
        self.assertFalse(e.scale_menu)


class PadColorTest(unittest.TestCase):
    def test_empty_is_track_color_on_is_white(self):
        e, _ = make()
        e.tracks[0]["steps"][1]["on"] = True
        grid = layouts.pad_colors(e)
        self.assertEqual(grid[7][0], e.tracks[0]["color"])   # step 0 empty
        self.assertEqual(grid[7][1], layouts.STEP_ON)        # step 1 on
        self.assertEqual(grid[0][7], e.tracks[3]["color"])

    def test_playhead_green(self):
        e, _ = make()
        e.tracks[0]["_current_step"] = 5
        self.assertEqual(layouts.pad_colors(e)[6][1], layouts.PLAYHEAD)


class PersistTest(unittest.TestCase):
    def test_roundtrip_and_bad_doc(self):
        e, _ = make()
        layouts.pad_press(e, 1, 7)
        e.pattern["root"] = 5
        e.set_rate(2, "Scene 1/8t")
        doc = e.to_doc()
        e2, _ = make()
        self.assertTrue(e2.load(doc))
        self.assertTrue(e2.tracks[0]["steps"][1]["on"])
        self.assertEqual(e2.pattern["root"], 5)
        self.assertEqual(e2.tracks[2]["rate"], "Scene 1/8t")
        self.assertEqual(e2.tracks[0]["rate"], eng.DEFAULT_RATE)
        self.assertFalse(e2.load({"version": 99}))
        self.assertFalse(e2.load(None))


class LayoutTest(unittest.TestCase):
    def test_switch_keeps_first_track(self):
        e, _ = make()
        for _ in range(4):
            e.add_track()
        e.track_page = 1                   # tracks 5-8 in layout 1
        layouts.switch_layout(e, 1)
        self.assertEqual(layouts.first_track(e), 4)
        self.assertEqual(layouts.page_tracks(e), [4, 5])

    def test_buttons_and_pads_render(self):
        class S:
            pass
        s = S()
        s.engine, _ = make()
        s.button_held, s.browser_active, s.browser_names, s.browser_cursor = {}, False, [], 0
        s.popup_title = s.popup_body = None
        s.popup_until = 0
        for layout in (0, 1):
            s.engine.layout = layout
            self.assertEqual(len(view.pad_colors(s)), 8)
            self.assertIn("Layout", view.button_colors(s))
            self.assertEqual(view.draw(s)["failed"], 0)
        layouts.pad_press(s.engine, 0, 7)
        self.assertTrue(view.draw(s)["ops"])
        # edit mode draws knobs for every track on the page
        kinds = [o["kind"] for o in view.draw(s)["ops"]]
        self.assertIn("arc", kinds)
        for layout in (0, 1):
            s.engine.layout = layout
            s.engine.touch_param(2)
            self.assertEqual(view.draw(s)["failed"], 0)
        s.engine.scale_menu = True
        self.assertTrue(view.draw(s)["ops"])


if __name__ == "__main__":
    unittest.main()

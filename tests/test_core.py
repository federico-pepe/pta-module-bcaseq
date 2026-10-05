import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import colortable
import engine as eng
import layouts
import view


def make(scale="major"):
    """Engine with C major unless scale=None (then the real default)."""
    notes = []
    e = eng.Engine(lambda ch, n, v: notes.append(("on", ch, n, v)),
                   lambda ch, n: notes.append(("off", ch, n)))
    if scale:
        e.pattern["scale"] = scale
        for t in e.tracks:
            t["scale"] = scale
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
    def test_dim_full_white(self):
        e, _ = make()
        e.tracks[0]["steps"][1]["on"] = True
        grid = layouts.pad_colors(e)
        c = e.tracks[0]["color"]
        self.assertEqual(grid[7][0], layouts.dim(c))          # empty = dim
        self.assertEqual(grid[7][1], c)                       # on = full
        layouts.pad_press(e, 2, 7)                            # tap = on + selected
        self.assertEqual(layouts.pad_colors(e)[7][2], layouts.STEP_SELECTED)

    def test_every_track_color_has_dim(self):
        for c in eng.TRACK_COLORS:
            self.assertIn(c, colortable.DEFAULT_DIM)
            self.assertNotEqual(layouts.dim(c), c)

    def test_palette_is_full_hardware_table(self):
        pal = view.PALETTE["byIndex"]
        self.assertEqual(len(pal), 128)
        self.assertEqual((pal[67]["r"], pal[67]["g"], pal[67]["b"]), (70, 3, 0))   # not a copy of 66

    def test_dim_is_darker_than_full(self):
        pal = view.PALETTE["byIndex"]
        lum = lambda i: pal[i]["r"] + pal[i]["g"] + pal[i]["b"]
        for c in eng.TRACK_COLORS:
            self.assertLess(lum(colortable.DEFAULT_DIM[c]), lum(c))

    def test_playhead_green(self):
        e, _ = make()
        e.tracks[0]["_current_step"] = 5
        self.assertEqual(layouts.pad_colors(e)[6][1], layouts.PLAYHEAD)

    def test_color_picker(self):
        e, _ = make()
        e.color_picker_track = 2
        grid = layouts.pad_colors(e)
        self.assertEqual(grid[0][2], eng.TRACK_COLORS[0])
        layouts.pad_press(e, 2, 0)
        layouts.pad_press(e, 1, 0)
        self.assertEqual(e.tracks[2]["color"], eng.TRACK_COLORS[1])
        self.assertFalse(e.tracks[2]["steps"][0]["on"])      # no step toggled


class ColorTableTest(unittest.TestCase):
    def setUp(self):
        colortable.reset()
        self.addCleanup(colortable.reset)

    def test_override_file_roundtrip(self):
        import tempfile
        c = eng.TRACK_COLORS[1]
        colortable.set_entry(c, dim_idx=77, rgb=(1, 2, 3))
        with tempfile.TemporaryDirectory() as d:
            path = d + "/colors.json"
            colortable.save(path)
            colortable.reset()
            self.assertEqual(colortable.screen_rgb(c), colortable.DEFAULT_RGB[c])
            self.assertTrue(colortable.load(path))
            self.assertEqual(colortable.dim(c), 77)
            self.assertEqual(colortable.screen_rgb(c), (1, 2, 3))

    def test_colorlab_py_file_format(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = d + "/colors.json"
            open(path, "w").write('{"version": 1, "colors": {"7": {"dim": 78}, "9": {"rgb": [4, 5, 6]}}}')
            self.assertTrue(colortable.load(path))
            self.assertEqual(colortable.dim(7), 78)
            self.assertEqual(colortable.screen_rgb(9), (4, 5, 6))
            self.assertEqual(colortable.screen_rgb(7), colortable.DEFAULT_RGB[7])

    def test_every_track_color_has_measured_screen_rgb(self):
        for c in eng.TRACK_COLORS:
            self.assertIn(c, colortable.DEFAULT_RGB)
        self.assertEqual(view.track_color(25), {"R": 255, "G": 75, "B": 153, "A": 255})   # pink on screen

    def test_screen_uses_override(self):
        c = eng.TRACK_COLORS[0]
        colortable.set_entry(c, rgb=(1, 2, 3))
        self.assertEqual(view.track_color(c), {"R": 1, "G": 2, "B": 3, "A": 255})

    def test_bad_file_is_ignored(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = d + "/colors.json"
            open(p, "w").write("{nope")
            self.assertFalse(colortable.load(p))


class ScopeTest(unittest.TestCase):
    def test_default_is_global(self):
        e, _ = make()
        e.nudge_scale_menu(0, 8)                      # Key +2 (friction 4)
        self.assertEqual(e.key_of(0), (2, "major"))
        self.assertEqual(e.key_of(3), (2, "major"))

    def test_per_track_keys(self):
        e, _ = make()
        e.nudge_scale_menu(0, 4)                      # global C# (root 1)
        e.nudge_scale_menu(4, -4)                     # Scope -> Track: tracks copy the global key
        self.assertFalse(e.pattern["scope_global"])
        self.assertEqual(e.key_of(2), (1, "major"))
        e.rate_track = 2                              # menu now edits track 3
        e.nudge_scale_menu(0, 8)
        e.nudge_scale_menu(1, 4)                      # next scale
        self.assertEqual(e.key_of(2), (3, "minor"))
        self.assertEqual(e.key_of(0), (1, "major"))   # other tracks unchanged
        e.nudge_scale_menu(4, 4)                      # back to Global: pattern key is used
        self.assertEqual(e.key_of(2), (1, "major"))

    def test_pitch_pads_use_track_key(self):
        e, _ = make()
        e.layout = 1
        e.nudge_scale_menu(4, -4)
        e.tracks[1]["root"] = 7                       # track 2 in G
        layouts.pad_press(e, 0, 7)                    # select track 1 step 0
        layouts.pad_press(e, 0, 3)                    # track 2 step 0 (BL quadrant)
        grid = layouts.pad_colors(e)
        self.assertEqual(grid[0][4], e.tracks[1]["color"])    # BR pitch grid: root pad is G, track color
        layouts.pad_press(e, 4, 0)                    # lowest pad of BR grid -> G3
        self.assertEqual(e.tracks[1]["steps"][0]["pitch"] % 12, 7)

    def test_pitch_nudge_uses_track_scale(self):
        e, _ = make()
        e.nudge_scale_menu(4, -4)
        e.tracks[0]["scale"] = "minor"
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 8)                                 # two scale steps up from C in C minor
        self.assertEqual(e.tracks[0]["steps"][0]["pitch"], 63)

    def test_persist_scope(self):
        e, _ = make()
        e.nudge_scale_menu(4, -4)
        e.tracks[1]["root"], e.tracks[1]["scale"] = 5, "dorian"
        e2, _ = make()
        self.assertTrue(e2.load(e.to_doc()))
        self.assertFalse(e2.pattern["scope_global"])
        self.assertEqual(e2.key_of(1), (5, "dorian"))

    def test_old_file_without_scope_loads_global(self):
        e, _ = make()
        doc = e.to_doc()
        del doc["pattern"]["scope_global"]
        for t in doc["pattern"]["tracks"]:
            t.pop("root", None)
            t.pop("scale", None)
        e2, _ = make()
        self.assertTrue(e2.load(doc))
        self.assertTrue(e2.pattern["scope_global"])


class LastNoteTest(unittest.TestCase):
    def test_new_step_uses_last_note_of_the_track(self):
        e, _ = make()
        e.layout = 1
        layouts.pad_press(e, 0, 7)                    # track 1 step 0
        layouts.pad_press(e, 6, 4)                    # TR pitch pad index 2 -> E3 (64)
        layouts.pad_press(e, 1, 7)                    # track 1 step 1: new step
        self.assertEqual(e.tracks[0]["steps"][1]["pitch"], 64)
        layouts.pad_press(e, 0, 3)                    # track 2 step 0: its own memory, still C3
        self.assertEqual(e.tracks[1]["steps"][0]["pitch"], 60)

    def test_encoder_updates_the_memory(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 8)                                 # two scale steps: E3
        layouts.pad_press(e, 1, 7)
        self.assertEqual(e.tracks[0]["steps"][1]["pitch"], 64)

    def test_step_keeps_its_own_pitch_when_toggled(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 8)                                 # step 0 = E3, memory E3
        layouts.pad_press(e, 1, 7)
        e.nudge(0, 4)                                 # step 1 = F3, memory F3
        layouts.pad_press(e, 0, 7)                    # step 0 off
        layouts.pad_press(e, 0, 7)                    # step 0 on again
        self.assertEqual(e.tracks[0]["steps"][0]["pitch"], 64)

    def test_first_note_follows_the_key(self):
        e, _ = make()
        e.nudge_scale_menu(0, 8)                      # root D
        layouts.pad_press(e, 0, 7)
        self.assertEqual(e.tracks[0]["steps"][0]["pitch"], 62)

    def test_memory_persists_and_old_files_load(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 8)
        e2, _ = make()
        self.assertTrue(e2.load(e.to_doc()))
        self.assertEqual(e2.tracks[0]["last_pitch"], 64)
        layouts.pad_press(e2, 1, 7)
        self.assertEqual(e2.tracks[0]["steps"][1]["pitch"], 64)
        doc = e.to_doc()
        for t in doc["pattern"]["tracks"]:
            t.pop("last_pitch", None)
            for st in t["steps"]:
                st.pop("pitch_set", None)
        e3, _ = make()
        self.assertTrue(e3.load(doc))
        self.assertIsNone(e3.tracks[0]["last_pitch"])
        self.assertTrue(e3.tracks[0]["steps"][0]["pitch_set"])    # moved off C3, so counts as set


class PitchFlashTest(unittest.TestCase):
    def setUp(self):
        self.e, _ = make()
        self.e.layout = 1

    def pad_of(self, grid, note):
        notes = eng.grid_pitches(0, "major", True, self.e.octave)
        i = notes.index(note)
        return grid[4 + i // 4][4 + i % 4]               # TR quadrant, track 1

    def test_triggered_note_flashes_green(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_note"], t["_lit_until"] = 64, _t.monotonic() + 10
        grid = layouts.pad_colors(self.e)
        self.assertEqual(self.pad_of(grid, 64), layouts.PLAYHEAD)
        self.assertEqual(self.pad_of(grid, 62), layouts.PITCH_WHITE)

    def test_flash_expires_and_ignores_other_octaves(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_note"], t["_lit_until"] = 64, _t.monotonic() - 1
        self.assertNotEqual(self.pad_of(layouts.pad_colors(self.e), 64), layouts.PLAYHEAD)
        t["_lit_note"], t["_lit_until"] = 30, _t.monotonic() + 10    # not on this octave
        grid = layouts.pad_colors(self.e)
        self.assertFalse(any(self.pad_of(grid, n) == layouts.PLAYHEAD for n in (60, 62, 64)))

    def test_trigger_sets_the_flash(self):
        e = self.e
        layouts.pad_press(e, 0, 7)
        e.start()
        e.tick(e.play_start + 0.001)
        t = e.tracks[0]
        self.assertEqual(t["_lit_note"], 60)
        self.assertGreaterEqual(t["_lit_until"] - (e.play_start + 0.001), eng.FLASH_MIN_S - 1e-6)


class SharedClockTest(unittest.TestCase):
    def ext_ticks(self, e, n):
        for _ in range(n):
            e.on_external_clock_byte(0xF8)

    def test_new_track_joins_in_phase_on_external_clock(self):
        e, _ = make()
        e.on_external_clock_byte(0xFA)
        self.ext_ticks(e, 6 * 10 + 3)                 # 10 steps and a bit
        e.add_track()
        self.ext_ticks(e, 6 * 3)
        steps = [t["_current_step"] for t in e.tracks]
        self.assertEqual(len(set(steps)), 1, steps)
        self.assertEqual(steps[0], 13)

    def test_length_change_stays_on_the_shared_timeline(self):
        e, _ = make()
        e.on_external_clock_byte(0xFA)
        self.ext_ticks(e, 6 * 20)
        e.tracks[1]["length"] = 12
        for k in range(1, 40):
            self.ext_ticks(e, 6)
            global_step = 20 + k - 1                  # step index of the tick just played
            self.assertEqual(e.tracks[0]["_current_step"], global_step % 16)
            self.assertEqual(e.tracks[1]["_current_step"], global_step % 12)

    def test_different_rates_share_the_beat_grid(self):
        e, _ = make()
        e.set_rate(0, "Scene 1/8")                    # 12 ticks per step
        e.set_rate(1, "Scene 1/16")                   # 6 ticks per step
        e.on_external_clock_byte(0xFA)
        for tick in range(96):
            e.on_external_clock_byte(0xF8)
            self.assertEqual(e.tracks[0]["_current_step"], (tick // 12) % 16)
            self.assertEqual(e.tracks[1]["_current_step"], (tick // 6) % 16)

    def test_first_tick_after_start_plays_step_one(self):
        e, notes = make()
        layouts.pad_press(e, 0, 7)
        e.on_external_clock_byte(0xFA)
        e.on_external_clock_byte(0xF8)
        self.assertEqual(len([n for n in notes if n[0] == "on"]), 1)

    def test_tempo_change_does_not_move_the_playhead(self):
        e, _ = make()
        e.start()
        t0 = e.play_start
        e.tick(t0 + 1.0)
        before = [t["_current_step"] for t in e.tracks]
        e.pattern["bpm"] = 60                         # half speed from now on
        e.tick(t0 + 1.001)
        self.assertEqual([t["_current_step"] for t in e.tracks], before)

    def test_new_track_does_not_fire_late_on_internal_clock(self):
        e, notes = make()
        e.start()
        t0, dur = e.play_start, e.step_duration(e.tracks[0])
        e.tick(t0 + dur * 5.5)                        # half way through step 5
        e.add_track()
        t = e.tracks[-1]
        t["steps"][5]["on"] = True
        self.assertEqual(t["_current_step"], 5)
        before = len(notes)
        e.tick(t0 + dur * 5.6)
        self.assertEqual(len(notes), before)          # no late hit of step 5
        e.tick(t0 + dur * 6.01)
        e.tick(t0 + dur * 21.01)                      # next time it comes round, it plays
        self.assertTrue(any(n[0] == "on" for n in notes))


class NoteLengthTest(unittest.TestCase):
    def test_note_length_holds_the_note(self):
        e, notes = make()
        layouts.pad_press(e, 0, 7)                    # step 0 on and selected
        e.nudge(7, 8)                                 # N LEN +2 (friction 4)
        self.assertEqual(e.tracks[0]["steps"][0]["len"], 3)
        self.assertEqual(e.tracks[0]["length"], 16)   # the sequence length is not touched
        e.start()
        t0, dur = e.play_start, e.step_duration(e.tracks[0])
        e.tick(t0 + 0.001)
        e.tick(t0 + dur * 2.4)                        # 2 steps + half a gate = 2.5 steps
        self.assertFalse(any(n[0] == "off" for n in notes))
        e.tick(t0 + dur * 2.6)
        self.assertTrue(any(n[0] == "off" for n in notes))

    def test_default_length_one_ends_in_the_first_step(self):
        e, notes = make()
        layouts.pad_press(e, 0, 7)
        e.start()
        t0, dur = e.play_start, e.step_duration(e.tracks[0])
        e.tick(t0 + 0.001)
        e.tick(t0 + dur * 0.6)
        self.assertTrue(any(n[0] == "off" for n in notes))

    def test_reset_and_persist(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(7, 12)
        e2, _ = make()
        self.assertTrue(e2.load(e.to_doc()))
        self.assertEqual(e2.tracks[0]["steps"][0]["len"], 4)
        e.reset_param(7)
        self.assertEqual(e.tracks[0]["steps"][0]["len"], 1)

    def test_old_file_without_len_loads(self):
        e, _ = make()
        doc = e.to_doc()
        for t in doc["pattern"]["tracks"]:
            for st in t["steps"]:
                st.pop("len", None)
        e2, _ = make()
        self.assertTrue(e2.load(doc))
        self.assertEqual(e2.tracks[0]["steps"][0]["len"], 1)


class SequenceLengthKnobTest(unittest.TestCase):
    def test_second_encoder_of_each_track(self):
        e, _ = make()
        self.assertEqual([layouts.slen_track(e, i) for i in range(8)],
                         [None, 0, None, 1, None, 2, None, 3])
        layouts.switch_layout(e, 1)
        self.assertEqual([layouts.slen_track(e, i) for i in range(8)],
                         [None, 0, None, None, None, 1, None, None])
        self.assertEqual(layouts.slen_encoder(e, 1), 5)

    def test_knob_changes_sequence_length(self):
        e, _ = make()
        e.nudge_track_length(1, -8, 3)                # friction 4: -2 steps
        self.assertEqual(e.tracks[1]["length"], 14)
        self.assertEqual(e.tracks[0]["length"], 16)
        e.nudge_track_length(1, -400, 3)
        self.assertEqual(e.tracks[1]["length"], 1)
        e.reset_track_length(1, 3)
        self.assertEqual(e.tracks[1]["length"], 16)
        self.assertEqual(e.active_param[0], 3)

    def test_main_view_draws_the_knob_and_edit_view_has_none(self):
        class S:
            pass
        st = S()
        st.engine, _ = make()
        st.button_held, st.browser_active, st.browser_names, st.browser_cursor = {}, False, [], 0
        st.popup_title = st.popup_body = None
        st.popup_until = 0
        ops = view.draw(st)["ops"]
        self.assertEqual(sum(1 for o in ops if o["kind"] == "knobarc"), 4)
        texts = [o["params"]["s"] for o in ops if o["kind"] == "text"]
        self.assertEqual(texts.count("S LEN"), 4)
        layouts.pad_press(st.engine, 0, 7)
        texts = [o["params"]["s"] for o in view.draw(st)["ops"] if o["kind"] == "text"]
        self.assertNotIn("S LEN", texts)
        self.assertIn("N LEN", texts)


class PitchDisplayTest(unittest.TestCase):
    def setUp(self):
        class S:
            pass
        self.st = S()
        self.st.engine, _ = make()
        self.e = self.st.engine
        self.st.button_held, self.st.browser_active, self.st.browser_names, self.st.browser_cursor = {}, False, [], 0
        self.st.popup_title = self.st.popup_body = None
        self.st.popup_until = 0

    def big_notes(self):
        return [o["params"]["s"] for o in view.draw(self.st)["ops"]
                if o["kind"] == "text" and o["params"].get("scale") == 3]

    def test_main_shows_no_pitch_until_a_note_plays(self):
        import time as _t
        self.assertEqual(self.big_notes(), [])
        t = self.e.tracks[0]
        t["_lit_note"], t["_show_until"] = 64, _t.monotonic() + 5
        self.assertEqual(self.big_notes(), ["E3"])
        t["_show_until"] = _t.monotonic() - 1                    # note ended
        self.assertEqual(self.big_notes(), [])
        self.e.tracks[0]["_last_note"] = 64                      # the old 'last note' never shows
        self.assertEqual(self.big_notes(), [])

    def test_stop_clears_the_pitch(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_note"], t["_show_until"] = 64, _t.monotonic() + 5
        self.e.stop()
        self.assertEqual(self.big_notes(), [])

    def test_edit_view_hides_pitch_of_a_step_that_is_off(self):
        self.e.shift = True
        layouts.pad_press(self.e, 0, 7)                           # select only: step stays off
        self.assertEqual(self.big_notes(), [])
        self.e.shift = False
        layouts.pad_press(self.e, 1, 7)                           # tap: step on and selected
        self.assertEqual(self.big_notes(), ["C3"])

    def test_edit_view_other_tracks_show_only_sounding_notes(self):
        import time as _t
        layouts.pad_press(self.e, 0, 7)
        self.assertEqual(self.big_notes(), ["C3"])
        t = self.e.tracks[1]
        t["_lit_note"], t["_show_until"] = 67, _t.monotonic() + 5
        self.assertEqual(sorted(self.big_notes()), ["C3", "G3"])


class DefaultsAndButtonsTest(unittest.TestCase):
    def test_default_key_is_c_chromatic(self):
        e, _ = make(scale=None)
        self.assertEqual(e.key_of(0), (0, "chromatic"))
        e.nudge_scale_menu(4, -4)                     # Track scope copies the global key
        self.assertTrue(all(t["scale"] == "chromatic" for t in e.tracks))
        self.assertEqual(eng.new_track(0)["scale"], "chromatic")

    def _state(self):
        class S:
            pass
        s = S()
        s.engine, _ = make()
        s.button_held, s.browser_active, s.browser_names, s.browser_cursor = {}, False, [], 0
        return s

    def test_white_led_buttons_have_a_clearly_dim_level(self):
        s = self._state()
        e = s.engine
        idle = view.button_colors(s)
        for name in view.WHITE_LED_BUTTONS:
            self.assertEqual(idle[name], view.BTN_WHITE_DIM)
        self.assertLess(view.BTN_WHITE_DIM, view.BTN_FULL // 3)
        e.accent_on, e.repeat_on, e.shift, e.delete = True, True, True, True
        lit = view.button_colors(s)
        for name in view.WHITE_LED_BUTTONS:
            self.assertEqual(lit[name], view.BTN_FULL)

    def test_repeat_count_is_steady_light_blue(self):
        s = self._state()
        e = s.engine
        e.repeat_on, e.repeat_count = True, 3
        seen = set()
        for _ in range(4):                            # pulse phases must not matter
            cols = view.button_colors(s)
            seen.add(cols[eng.DIVISION_NAMES[8 - 3]])
            import time as _t
            _t.sleep(0.3)
        self.assertEqual(seen, {view.BTN_LIGHT_BLUE})
        cols = view.button_colors(s)
        others = [cols[n] for n in eng.DIVISION_NAMES if n != eng.DIVISION_NAMES[5]]
        self.assertEqual(set(others), {view.BTN_DIM})

    def test_rate_still_pulses_green_when_repeat_is_off(self):
        s = self._state()
        vals = set()
        import time as _t
        for _ in range(6):
            vals.add(view.button_colors(s)[s.engine.tracks[0]["rate"]])
            _t.sleep(0.3)
        self.assertEqual(vals, {view.BTN_GREEN, view.BTN_OFF})


class ScaleMenuLayoutTest(unittest.TestCase):
    def test_no_scale_name_reaches_the_next_cell(self):
        e, _ = make()
        in_key_x = view.SCALE_MENU_COL["In Key"] * (view.W // 8) + 4
        scale_x = view.SCALE_MENU_COL["Scale"] * (view.W // 8) + 4
        for name in eng.SCALE_NAMES:
            e.pattern["scale"] = name
            ops = view._scale_ops(e, view.color("white"))
            value = [o for o in ops if o["params"].get("scale") == view.VALUE_SCALE
                     and o["params"]["x"] == scale_x][0]["params"]["s"]
            end = scale_x + view.CHAR_W * view.VALUE_SCALE * len(value)
            self.assertLess(end, in_key_x - 8, "%s ends at %d, In Key starts at %d" % (value, end, in_key_x))

    def test_menu_draws_in_both_scopes(self):
        e, _ = make()
        e.scale_menu = True
        for glob in (True, False):
            e.pattern["scope_global"] = glob
            self.assertTrue(view._scale_ops(e, view.color("white")))
            self.assertIn("BPM", view._status_line(e))


class HoldTest(unittest.TestCase):
    def test_accent_hold_edits_without_toggling(self):
        e, _ = make()
        e.accent_held = True
        layouts.pad_press(e, 0, 7)
        s = e.tracks[0]["steps"][0]
        self.assertFalse(s["on"])
        self.assertEqual(s["vel"], 127)
        self.assertTrue(e.accent_used)
        layouts.pad_press(e, 0, 7)                            # again = back to default
        self.assertEqual(s["vel"], 100)

    def test_repeat_hold_uses_count(self):
        e, _ = make()
        e.repeat_held, e.repeat_count = True, 4
        layouts.pad_press(e, 1, 7)
        self.assertEqual(e.tracks[0]["steps"][1]["repeat"], 4)
        self.assertFalse(e.tracks[0]["steps"][1]["on"])


class ButtonTest(unittest.TestCase):
    def setUp(self):
        import run
        self.run = run
        self.e, _ = make()

    def test_tap_toggles_hold_does_not(self):
        r, e = self.run, self.e
        r._accent_repeat_button(e, "Accent", True)
        r._accent_repeat_button(e, "Accent", False)
        self.assertTrue(e.accent_on)
        r._accent_repeat_button(e, "Accent", True)
        layouts.pad_press(e, 0, 7)
        r._accent_repeat_button(e, "Accent", False)
        self.assertTrue(e.accent_on)                           # unchanged by the hold

    def test_track_buttons_layout1_and_2(self):
        r, e = self.run, self.e
        r._track_button(e, 4)                                  # buttons 5-6 = track 3
        self.assertEqual(e.rate_track, 2)
        layouts.switch_layout(e, 1)
        r._track_button(e, 4)                                  # buttons 5-8 = second track
        self.assertEqual(e.rate_track, 1)

    def test_shift_track_opens_picker(self):
        r, e = self.run, self.e
        e.shift = True
        r._track_button(e, 2)
        self.assertEqual(e.color_picker_track, 1)

    def test_select_track_in_edit_mode(self):
        e = self.e
        layouts.pad_press(e, 0, 7)
        e.select_track(2)
        self.assertEqual(e.edit_track, 2)
        self.assertEqual(e.sel[2], 0)


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
        self.assertIn("knobarc", kinds)
        for layout in (0, 1):
            s.engine.layout = layout
            s.engine.touch_param(2)
            self.assertEqual(view.draw(s)["failed"], 0)
        s.engine.scale_menu = True
        self.assertTrue(view.draw(s)["ops"])


if __name__ == "__main__":
    unittest.main()

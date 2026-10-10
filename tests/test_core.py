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


def tap(e, col, row):
    """A short press: press and release a pad."""
    layouts.pad_press(e, col, row, now=0.0)
    layouts.pad_release(e, col, row, now=0.05)


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
        self.assertEqual(grid[4][4], layouts.dim(e.tracks[0]["color"]))
        # BR quadrant: in key, non-root pad white
        self.assertEqual(grid[0][5], layouts.PITCH_DIM_WHITE)
        e.pattern["in_key"] = False
        grid = layouts.pad_colors(e)
        self.assertEqual(grid[0][5], 0)          # C# not in C major
        self.assertEqual(grid[0][6], layouts.PITCH_DIM_WHITE)  # D in scale

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
        e.nudge(5, 3)                      # repeat throttled: no change yet
        self.assertEqual(e.tracks[0]["steps"][0]["repeat"], 1)
        e.nudge(5, 1)
        self.assertEqual(e.tracks[0]["steps"][0]["repeat"], 2)
        e.nudge(1, 500)
        self.assertEqual(e.tracks[0]["steps"][0]["vel"], 127)

    def test_pitch_nudge_in_key(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 4)                      # one scale step up from C
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [62])

    def test_layout2_arm_then_step_toggles_note(self):
        e, _ = make()
        e.layout = 1
        tap(e, 0, 7)        # TL step 0, nothing armed: plain tap
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [60])
        layouts.pad_press(e, 5, 4)        # TR quadrant bottom row, index 1 = D3: arm
        self.assertEqual(e.armed, {62})
        tap(e, 0, 7)        # step 0 gets D3
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [60, 62])
        tap(e, 0, 7)        # and loses it again
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [60])
        tap(e, 1, 7)        # armed note enters a new step
        self.assertEqual(e.tracks[0]["steps"][1]["pitches"], [62])


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
        grid = layouts.pad_colors(e)
        self.assertEqual(grid[0][4], layouts.dim(e.tracks[1]["color"]))    # BR pitch grid: root pad is G, dim track color
        layouts.pad_press(e, 5, 0)                    # second pad of BR grid -> A3, armed
        tap(e, 0, 3)                    # track 2 step 0 (BL quadrant) gets it
        self.assertEqual([n % 12 for n in e.tracks[1]["steps"][0]["pitches"]], [9])

    def test_pitch_nudge_uses_track_scale(self):
        e, _ = make()
        e.nudge_scale_menu(4, -4)
        e.tracks[0]["scale"] = "minor"
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 8)                                 # two scale steps up from C in C minor
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [63])

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
        tap(e, 0, 7)                    # track 1 step 0
        layouts.pad_press(e, 6, 4)                    # TR pitch pad index 2 -> E3 (64): arm
        layouts.pad_release(e, 6, 4)
        tap(e, 0, 7)                    # step 0 gets E3: [60, 64]
        layouts.pad_press(e, 6, 4)                    # disarm
        layouts.pad_release(e, 6, 4)
        tap(e, 1, 7)                    # track 1 step 1: new step
        self.assertEqual(e.tracks[0]["steps"][1]["pitches"], [64])
        tap(e, 0, 3)                    # track 2 step 0: its own memory, still C3
        self.assertEqual(e.tracks[1]["steps"][0]["pitches"], [60])

    def test_encoder_updates_the_memory(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 8)                                 # two scale steps: E3
        layouts.pad_press(e, 1, 7)
        self.assertEqual(e.tracks[0]["steps"][1]["pitches"], [64])

    def test_step_keeps_its_own_pitch_when_toggled(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 8)                                 # step 0 = E3, memory E3
        layouts.pad_press(e, 1, 7)
        e.nudge(0, 4)                                 # step 1 = F3, memory F3
        layouts.pad_press(e, 0, 7)                    # step 0 off
        layouts.pad_press(e, 0, 7)                    # step 0 on again
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [64])

    def test_first_note_follows_the_key(self):
        e, _ = make()
        e.nudge_scale_menu(0, 8)                      # root D
        layouts.pad_press(e, 0, 7)
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [62])

    def test_memory_persists(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.nudge(0, 8)
        e2, _ = make()
        self.assertTrue(e2.load(e.to_doc()))
        self.assertEqual(e2.tracks[0]["last_pitch"], 64)
        layouts.pad_press(e2, 1, 7)
        self.assertEqual(e2.tracks[0]["steps"][1]["pitches"], [64])


class ChordTest(unittest.TestCase):
    def step(self, e, ti=0, si=0):
        return e.tracks[ti]["steps"][si]

    def test_new_step_has_a_pitch_list(self):
        self.assertEqual(eng.new_step()["pitches"], [eng.DEFAULT_PITCH])

    def test_toggle_adds_sorted_and_removes(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)                      # step 0 on, [60]
        e.toggle_note(0, 0, 67)
        e.toggle_note(0, 0, 64)
        self.assertEqual(self.step(e)["pitches"], [60, 64, 67])
        self.assertEqual(e.sel.get(0), 0)
        self.assertEqual(e.sel_note, 1)                 # the note just added
        e.toggle_note(0, 0, 64)
        self.assertEqual(self.step(e)["pitches"], [60, 67])
        self.assertEqual(e.sel_note, 1)                 # clamped to a valid index

    def test_removing_last_note_turns_step_off(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 60)
        s = self.step(e)
        self.assertFalse(s["on"])
        self.assertEqual(s["pitches"], [60])
        self.assertNotIn(0, e.sel)
        e.toggle_note(0, 0, 62, activate=True)
        self.assertTrue(s["on"])
        self.assertEqual(s["pitches"], [62])

    def test_toggle_on_off_step_without_activate_keeps_it_off(self):
        e, _ = make()
        e.shift = True
        layouts.pad_press(e, 0, 7)                      # select only
        e.shift = False
        e.toggle_note(0, 0, 64)
        s = self.step(e)
        self.assertFalse(s["on"])
        self.assertEqual(s["pitches"], [64])
        self.assertEqual(e.tracks[0]["last_pitch"], 64)

    def test_activate_applies_accent_and_repeat_defaults(self):
        e, _ = make()
        e.accent_on = True
        e.repeat_on, e.repeat_count = True, 3
        e.toggle_note(0, 2, 64, activate=True)
        s = self.step(e, 0, 2)
        self.assertEqual((s["on"], s["vel"], s["repeat"]), (True, eng.ACCENT_VELOCITY, 3))

    def test_trigger_plays_every_note_with_shared_settings(self):
        e, notes = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 64)
        e.toggle_note(0, 0, 67)
        self.step(e)["repeat"] = 2
        e.start()
        e.tick(e.play_start + 0.001)
        ons = [n for n in notes if n[0] == "on"]
        self.assertEqual(sorted(n[2] for n in ons), [60, 64, 67])
        e.tick(e.play_start + e.step_duration(e.tracks[0]) * 0.6)    # second hit
        ons = [n for n in notes if n[0] == "on"]
        self.assertEqual(len(ons), 6)
        self.assertEqual(len({n[3] for n in ons}), 1)                # one velocity

    def test_knob_edits_selected_note_only(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 67)                         # [60, 67], selected = 67
        e.sel_note = 0
        e.nudge(0, 4)                                   # 60 -> 62
        self.assertEqual(self.step(e)["pitches"], [62, 67])
        e.nudge(0, 40)                                  # 62 up past 67: skip the taken note
        p = self.step(e)["pitches"]
        self.assertEqual(len(p), 2)
        self.assertIn(67, p)
        self.assertGreater(p[1], 67)
        self.assertEqual(e.sel_note, 1)                 # selection follows the moved note

    def test_knob_stays_at_range_edge(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        self.step(e)["pitches"] = [126, 127]
        e.sel_note = 0
        e.nudge(0, 40)
        self.assertEqual(self.step(e)["pitches"], [126, 127])

    def test_reset_param_resets_selected_note(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 67)
        e.reset_param(0)                                # selected 67 -> default C3, taken by 60: unchanged
        self.assertEqual(self.step(e)["pitches"], [60, 67])
        self.step(e)["pitches"] = [64, 67]
        e.sel_note = 0
        e.reset_param(0)
        self.assertEqual(self.step(e)["pitches"], [60, 67])

    def test_persist_pitches(self):
        e, _ = make()
        layouts.pad_press(e, 0, 7)
        e.toggle_note(0, 0, 67)
        e2, _ = make()
        self.assertTrue(e2.load(e.to_doc()))
        self.assertEqual(e2.tracks[0]["steps"][0]["pitches"], [60, 67])

    def test_load_cleans_bad_pitches(self):
        e, _ = make()
        for bad, want in ((None, [60]), ([], [60]), ("x", [60]), (["a", True], [60]),
                          ([64, 64, 300, -5], [0, 64, 127]), (5, [60])):
            doc = e.to_doc()
            doc["pattern"]["tracks"][0]["steps"][0]["pitches"] = bad
            e2, _ = make()
            self.assertTrue(e2.load(doc))
            self.assertEqual(e2.tracks[0]["steps"][0]["pitches"], want, bad)


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
        t["_lit_notes"], t["_lit_until"] = [64], _t.monotonic() + 10
        grid = layouts.pad_colors(self.e)
        self.assertEqual(self.pad_of(grid, 64), layouts.PLAYHEAD)
        self.assertEqual(self.pad_of(grid, 62), layouts.PITCH_DIM_WHITE)

    def test_flash_expires_and_ignores_other_octaves(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_notes"], t["_lit_until"] = [64], _t.monotonic() - 1
        self.assertNotEqual(self.pad_of(layouts.pad_colors(self.e), 64), layouts.PLAYHEAD)
        t["_lit_notes"], t["_lit_until"] = [30], _t.monotonic() + 10    # not on this octave
        grid = layouts.pad_colors(self.e)
        self.assertFalse(any(self.pad_of(grid, n) == layouts.PLAYHEAD for n in (60, 62, 64)))

    def test_trigger_sets_the_flash(self):
        e = self.e
        tap(e, 0, 7)
        e.start()
        e.tick(e.play_start + 0.001)
        t = e.tracks[0]
        self.assertEqual(t["_lit_notes"], [60])
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
        e.nudge(6, 8)                                 # N LEN +2 (friction 4)
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
        e.nudge(6, 12)
        e2, _ = make()
        self.assertTrue(e2.load(e.to_doc()))
        self.assertEqual(e2.tracks[0]["steps"][0]["len"], 4)
        e.reset_param(6)
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
        for layout in (1, 2):                          # same knobs in every layout
            layouts.switch_layout(e, layout)
            self.assertEqual([layouts.slen_track(e, i) for i in range(8)],
                             [None, 0, None, 1, None, 2, None, 3])
        self.assertEqual(layouts.slen_encoder(e, 1), 3)

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
        self.assertEqual(sum(1 for o in ops if o["kind"] == "knobarc"), 8)
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
                if o["kind"] == "text" and o["params"].get("scale") in (2, 3)]

    def test_main_shows_no_pitch_until_a_note_plays(self):
        import time as _t
        self.assertEqual(self.big_notes(), [])
        t = self.e.tracks[0]
        t["_lit_notes"], t["_show_until"] = [64], _t.monotonic() + 5
        self.assertEqual(self.big_notes(), ["E3"])
        t["_show_until"] = _t.monotonic() - 1                    # note ended
        self.assertEqual(self.big_notes(), [])

    def test_stop_clears_the_pitch(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_notes"], t["_show_until"] = [64], _t.monotonic() + 5
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
        t["_lit_notes"], t["_show_until"] = [67], _t.monotonic() + 5
        self.assertEqual(sorted(self.big_notes()), ["C3", "G3"])


class ChordDisplayTest(unittest.TestCase):
    def setUp(self):
        class S:
            pass
        self.st = S()
        self.st.engine, _ = make()
        self.e = self.st.engine
        self.st.button_held, self.st.browser_active, self.st.browser_names, self.st.browser_cursor = {}, False, [], 0
        self.st.popup_title = self.st.popup_body = None
        self.st.popup_until = 0

    def texts(self):
        return [(o["params"]["s"], o["params"].get("scale"))
                for o in view.draw(self.st)["ops"] if o["kind"] == "text"]

    def test_fit_scale(self):
        self.assertEqual(view.fit_scale("C3", view.CHAR_W * 2 * 3), 3)
        self.assertEqual(view.fit_scale("x" * 10, view.CHAR_W * 10 * 2), 2)
        self.assertEqual(view.fit_scale("x" * 10, 1), 1)

    def test_main_screen_joins_sounding_notes(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_notes"], t["_show_until"] = [60, 64, 67], _t.monotonic() + 5
        self.assertIn("C3 E3 G3", [s for s, _ in self.texts()])
        self.assertIn(("C", 2), self.texts())

    def test_edit_view_unnamed_step_shows_selected_note_big(self):
        layouts.pad_press(self.e, 0, 7)
        self.e.toggle_note(0, 0, 61)                    # C3 C#3: no chord name
        self.assertIn(("C#3", 3), self.texts())
        self.assertNotIn("NOTE 2/2 C#3", [s for s, _ in self.texts()])
        self.assertIn("PITCH", [s for s, _ in self.texts()])
        self.assertIn(("C3 C#3", None), self.texts())
        self.e.sel_note = 0
        self.assertIn(("C3", 3), self.texts())

    def test_edit_view_chord_name_is_big_and_notes_small(self):
        layouts.pad_press(self.e, 0, 7)
        self.e.toggle_note(0, 0, 64)
        self.e.toggle_note(0, 0, 67)
        texts = self.texts()
        self.assertIn(("C", 3), texts)
        self.assertIn(("C3 E3 G3", None), texts)
        self.assertFalse([s for s, _ in texts if s.startswith("NOTE")])

    def test_edit_view_notes_never_pass_the_knobs(self):
        layouts.pad_press(self.e, 0, 7)
        for n in (61, 63, 66, 68, 70, 72, 74):
            self.e.toggle_note(0, 0, n)
        for s_, _ in self.texts():
            if s_.startswith("C3 "):
                self.assertLessEqual(len(s_) * view.CHAR_W, view.EDIT_TEXT_W)
                self.assertIn("+", s_)

    def test_main_screen_chord_name_big_notes_small(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_notes"], t["_show_until"] = [60, 64, 67, 71], _t.monotonic() + 5
        texts = self.texts()
        self.assertIn(("Cmaj7", 2), texts)
        self.assertIn(("C3 E3 G3 B3", None), texts)

    def test_main_screen_text_stays_inside_its_column(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_notes"], t["_show_until"] = [60, 61, 62, 63, 64, 65], _t.monotonic() + 5    # no name
        for s_, sc in self.texts():
            if s_.startswith("C3"):
                self.assertLessEqual(len(s_) * view.CHAR_W * (sc or 1), view.MAIN_TEXT_W)

    def test_edit_view_other_track_shows_chord(self):
        import time as _t
        layouts.pad_press(self.e, 0, 7)
        t = self.e.tracks[1]
        t["_lit_notes"], t["_show_until"] = [60, 67], _t.monotonic() + 5
        self.assertIn("C3 G3", [s for s, _ in self.texts()])

    def test_main_screen_shows_chord_name(self):
        import time as _t
        t = self.e.tracks[0]
        t["_lit_notes"], t["_show_until"] = [60, 64, 67, 71], _t.monotonic() + 5
        self.assertIn("Cmaj7", [s for s, _ in self.texts()])
        t["_lit_notes"] = [60, 61, 62]                  # no name: only the notes
        texts = [s for s, _ in self.texts()]
        self.assertIn("C3 C#3 D3", texts)
        self.assertNotIn("Cmaj7", texts)
        self.assertNotIn("C", texts)

    def test_edit_view_shows_chord_name_of_the_step(self):
        layouts.pad_press(self.e, 0, 7)
        self.assertNotIn("C", [s for s, _ in self.texts()])    # one note: no name
        self.e.toggle_note(0, 0, 64)
        self.e.toggle_note(0, 0, 67)
        self.assertIn("C", [s for s, _ in self.texts()])
        self.e.sel_note = 0                                    # the name is for the whole step
        self.assertIn("C", [s for s, _ in self.texts()])

    def test_single_note_keeps_pitch_label(self):
        layouts.pad_press(self.e, 0, 7)
        self.assertIn("PITCH", [s for s, _ in self.texts()])

    def test_pitch_pads_mark_notes_of_the_selected_step(self):
        e = self.e
        e.layout = 1
        tap(e, 0, 7)
        e.toggle_note(0, 0, 64)                         # [60, 64]
        grid = layouts.pad_colors(e)
        notes = eng.grid_pitches(0, "major", True, e.octave)
        i, j = notes.index(64), notes.index(62)
        self.assertEqual(grid[4 + i // 4][4 + i % 4], layouts.PITCH_WHITE)
        self.assertEqual(grid[4][4], e.tracks[0]["color"])      # root C in the step: bright track color
        self.assertEqual(grid[4 + j // 4][4 + j % 4], layouts.PITCH_DIM_WHITE)


class Layout3Test(unittest.TestCase):
    def setUp(self):
        self.e, _ = make()
        layouts.switch_layout(self.e, 2)

    def pitch_pad(self, slot, note):
        """(col, row) of a note on the pitch grid in quadrant slot 1 (TR), 2 (BL) or 3 (BR)."""
        e = self.e
        track = layouts.first_track(e) + (slot - 1)
        root, scale = e.key_of(track)
        i = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave).index(note)
        col0 = 0 if slot == 2 else 4
        row0 = 4 if slot == 1 else 0
        return col0 + i % 4, row0 + i // 4

    def test_three_tracks_per_page(self):
        self.assertEqual(layouts.current(self.e).pad_group, 3)
        self.assertEqual(layouts.pad_tracks(self.e), [0, 1, 2])
        self.assertEqual(layouts.screen_tracks(self.e), [0, 1, 2, 3])

    def test_arm_then_step_adds_note_to_grid_track(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(2, 64))      # slot 2 = second track
        layouts.pad_release(e, *self.pitch_pad(2, 64))
        self.assertEqual(e.armed, {64})
        self.assertEqual(e.rate_track, 1)
        tap(e, 0, 7)                        # step 0
        s = e.tracks[1]["steps"][0]
        self.assertEqual((s["on"], s["pitches"]), (True, [64]))
        layouts.pad_press(e, *self.pitch_pad(2, 67))      # a new single press replaces the selection
        layouts.pad_release(e, *self.pitch_pad(2, 67))
        tap(e, 0, 7)
        self.assertEqual(s["pitches"], [64, 67])
        tap(e, 0, 7)                        # armed 67 again: removes it
        self.assertEqual(s["pitches"], [64])
        self.assertEqual(e.tracks[0]["steps"][0]["on"], False)

    def test_pressing_armed_pad_disarms(self):
        e = self.e
        pad = self.pitch_pad(1, 64)
        layouts.pad_press(e, *pad)
        layouts.pad_release(e, *pad)
        layouts.pad_press(e, *pad)
        layouts.pad_release(e, *pad)
        self.assertEqual(e.armed, set())
        tap(e, 0, 7)                        # nothing armed: plain tap
        self.assertEqual(e.tracks[e.rate_track]["steps"][0]["pitches"], [eng.DEFAULT_PITCH])

    def test_shift_selects_without_adding(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(1, 64))
        e.shift = True
        layouts.pad_press(e, 0, 7)
        self.assertFalse(e.tracks[0]["steps"][0]["on"])
        self.assertEqual(e.sel.get(0), 0)

    def test_switching_layout_clears_armed(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(1, 64))
        layouts.switch_layout(e, 0)
        self.assertEqual(e.armed, set())
        layouts.pad_press(e, 0, 7)                        # Layout 1 TL: plain tap
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [eng.DEFAULT_PITCH])

    def test_step_grid_colors(self):
        e = self.e
        tap(e, 1, 7)                        # step 1 on and selected
        e.start()
        e.tick(e.play_start + 0.001)                      # playhead on step 0
        grid = layouts.pad_colors(e)
        self.assertEqual(grid[7][0], layouts.PLAYHEAD)
        self.assertEqual(grid[7][1], layouts.STEP_SELECTED)
        self.assertEqual(grid[7][2], layouts.STEP_DIM_WHITE)

    def test_armed_pad_is_bright_white(self):
        e = self.e
        c, r = self.pitch_pad(1, 62)                      # D: in key, not the root
        self.assertEqual(layouts.pad_colors(e)[r][c], layouts.PITCH_DIM_WHITE)
        layouts.pad_press(e, c, r)
        self.assertEqual(layouts.pad_colors(e)[r][c], layouts.PITCH_WHITE)
        self.assertEqual(layouts.PITCH_WHITE, 120)

    def test_armed_root_pad_becomes_bright_track_color(self):
        e = self.e
        c, r = self.pitch_pad(1, 60)
        color = e.tracks[0]["color"]
        self.assertEqual(layouts.pad_colors(e)[r][c], layouts.dim(color))
        layouts.pad_press(e, c, r)
        self.assertEqual(layouts.pad_colors(e)[r][c], color)

    def test_out_of_key_note_is_white_when_selected(self):
        e = self.e
        e.pattern["in_key"] = False
        c, r = self.pitch_pad(1, 61)                      # C#: not in C major
        self.assertEqual(layouts.pad_colors(e)[r][c], layouts.OFF)
        layouts.pad_press(e, c, r)
        self.assertEqual(layouts.pad_colors(e)[r][c], layouts.PITCH_WHITE)

    def test_armed_pad_shows_only_on_the_working_track(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(1, 62))      # arm D on track 1
        e.select_track(1)                                 # work on track 2
        c, r = self.pitch_pad(1, 62)
        self.assertEqual(layouts.pad_colors(e)[r][c], layouts.PITCH_DIM_WHITE)
        c2, r2 = self.pitch_pad(2, 62)
        self.assertEqual(layouts.pad_colors(e)[r2][c2], layouts.PITCH_WHITE)

    def test_track_button_keeps_armed_note_for_new_track(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(1, 64))      # arm E on track 1
        e.select_track(1)                                 # screen-bottom button: track 2
        tap(e, 0, 7)
        self.assertEqual(e.armed, {64})
        self.assertEqual(e.tracks[1]["steps"][0]["pitches"], [64])
        self.assertFalse(e.tracks[0]["steps"][0]["on"])

    def test_s_len_touch_and_turn_select_the_track(self):
        import run
        class S:
            pass
        st = S()
        st.engine, st.browser_active = self.e, False
        run.handle_touch(st, {"name": "Encoder 6 touch", "touched": True})
        self.assertEqual(self.e.rate_track, 2)             # encoder 6 = S LEN of track 3
        self.assertEqual(layouts.track_for_slot(self.e, 0), 2)
        run.handle_encoder(st, {"name": "Encoder 4 turn", "index": 3, "delta": -8})
        self.assertEqual(self.e.rate_track, 1)             # encoder 4 = S LEN of track 2
        self.assertEqual(self.e.tracks[1]["length"], 14)
        self.assertEqual(layouts.track_for_slot(self.e, 0), 1)

    def test_grid_follows_working_track(self):
        e = self.e
        e.rate_track = 2
        self.assertEqual(layouts.track_for_slot(e, 0), 2)
        e.rate_track = 3
        self.assertEqual(layouts.pad_tracks(e), [3])
        self.assertEqual(layouts.track_for_slot(e, 0), 3)

    def test_missing_tracks_leave_pitch_grid_dark(self):
        e = self.e
        e.rate_track = 3                                  # window is just track 4
        grid = layouts.pad_colors(e)
        for r in range(4):                                # BL and BR have no track
            for c in range(8):
                self.assertEqual(grid[r][c], layouts.OFF)
        layouts.pad_press(e, 0, 0)                        # empty grids: no crash, nothing armed
        layouts.pad_press(e, 4, 0)
        self.assertEqual(e.armed, set())

    def test_octave_buttons_active_in_layout_3(self):
        self.assertTrue(layouts.has_octave(self.e))
        layouts.switch_layout(self.e, 0)
        self.assertFalse(layouts.has_octave(self.e))

    def test_screens_draw(self):
        class S:
            pass
        st = S()
        st.engine = self.e
        st.button_held, st.browser_active, st.browser_names, st.browser_cursor = {}, False, [], 0
        st.popup_title = st.popup_body = None
        st.popup_until = 0
        view.draw(st)                                     # main screen
        layouts.pad_press(self.e, *self.pitch_pad(1, 64))
        layouts.pad_press(self.e, 0, 7)
        view.draw(st)                                     # edit screen
        for idx in range(8):
            ti = layouts.slen_track(self.e, idx)
            self.assertTrue(ti is None or ti in layouts.screen_tracks(self.e))


class AccidentalsTest(unittest.TestCase):
    def setUp(self):
        class S:
            pass
        self.st = S()
        self.st.engine, _ = make()
        self.e = self.st.engine
        self.st.button_held, self.st.browser_active, self.st.browser_names, self.st.browser_cursor = {}, False, [], 0
        self.st.popup_title = self.st.popup_body = None
        self.st.popup_until = 0

    def texts(self):
        return [o["params"]["s"] for o in view.draw(self.st)["ops"] if o["kind"] == "text"]

    def test_default_is_sharps_and_encoder_6_switches(self):
        e = self.e
        self.assertFalse(e.pattern["flats"])
        e.nudge_scale_menu(5, 4)
        self.assertTrue(e.pattern["flats"])
        e.nudge_scale_menu(5, -4)
        self.assertFalse(e.pattern["flats"])

    def test_persists(self):
        self.e.nudge_scale_menu(5, 4)
        e2, _ = make()
        self.assertTrue(e2.load(self.e.to_doc()))
        self.assertTrue(e2.pattern["flats"])

    def test_note_name_spelling(self):
        self.assertEqual(view.note_name(61), "C#3")
        self.assertEqual(view.note_name(61, flats=True), "Db3")

    def test_scale_menu_shows_the_switch(self):
        self.e.scale_menu = True
        self.assertIn("Sharp", self.texts())
        self.e.nudge_scale_menu(5, 4)
        self.assertIn("Flat", self.texts())
        self.assertIn("Names", self.texts())

    def test_key_and_notes_follow_the_switch(self):
        e = self.e
        e.nudge_scale_menu(0, 4)                          # root C#
        self.assertTrue(any("C# " in t for t in self.texts()))
        e.nudge_scale_menu(5, 4)
        self.assertTrue(any("Db " in t for t in self.texts()))

    def test_chord_names_follow_the_switch(self):
        import time as _t
        e = self.e
        t = e.tracks[0]
        t["_lit_notes"], t["_show_until"] = [61, 65, 68], _t.monotonic() + 5
        self.assertIn("C#", self.texts())
        e.nudge_scale_menu(5, 4)
        self.assertIn("Db", self.texts())


class MultiNoteArmTest(unittest.TestCase):
    """Hold several pitch pads, then tap steps: all of the notes go in together."""

    def setUp(self):
        self.e, _ = make()
        layouts.switch_layout(self.e, 2)

    def pad(self, note, slot=1):
        e = self.e
        track = layouts.first_track(e) + (slot - 1)
        root, scale = e.key_of(track)
        i = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave).index(note)
        return (0 if slot == 2 else 4) + i % 4, (4 if slot == 1 else 0) + i // 4

    def hold(self, *notes):
        for n in notes:
            layouts.pad_press(self.e, *self.pad(n))

    def release(self, *notes):
        for n in notes:
            layouts.pad_release(self.e, *self.pad(n))

    def test_holding_pads_arms_all_of_them(self):
        self.hold(60, 64, 67)
        self.assertEqual(self.e.armed, {60, 64, 67})

    def test_selection_stays_armed_after_release(self):
        self.hold(60, 64, 67)
        self.release(60, 64, 67)
        self.assertEqual(self.e.armed, {60, 64, 67})
        self.assertEqual(self.e.pitch_held, set())

    def test_new_single_press_replaces_the_selection(self):
        self.hold(60, 64)
        self.release(60, 64)
        self.hold(67)
        self.assertEqual(self.e.armed, {67})

    def test_pressing_the_only_armed_pad_disarms(self):
        self.hold(64)
        self.release(64)
        self.hold(64)
        self.release(64)
        self.assertEqual(self.e.armed, set())

    def test_step_gets_all_notes_at_once(self):
        e = self.e
        self.hold(60, 64, 67)
        tap(e, 0, 7)                        # while the pads are still down
        s = e.tracks[0]["steps"][0]
        self.assertEqual((s["on"], s["pitches"]), (True, [60, 64, 67]))
        self.release(60, 64, 67)
        tap(e, 1, 7)                        # the selection is still armed
        self.assertEqual(e.tracks[0]["steps"][1]["pitches"], [60, 64, 67])

    def test_second_tap_removes_every_armed_note(self):
        e = self.e
        self.hold(60, 64, 67)
        tap(e, 0, 7)
        tap(e, 0, 7)
        s = e.tracks[0]["steps"][0]
        self.assertFalse(s["on"])
        self.assertNotIn(0, e.sel)

    def test_removing_keeps_the_notes_that_are_not_armed(self):
        e = self.e
        self.hold(60, 64, 67)
        tap(e, 0, 7)
        self.release(60, 64, 67)
        self.hold(64, 67)
        tap(e, 0, 7)
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [60])
        self.assertTrue(e.tracks[0]["steps"][0]["on"])

    def test_partial_overlap_adds_the_missing_notes(self):
        e = self.e
        self.hold(60, 64)
        tap(e, 0, 7)
        self.release(60, 64)
        self.hold(64, 67)
        tap(e, 0, 7)
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [60, 64, 67])

    def test_all_armed_notes_are_bright_on_the_grid(self):
        e = self.e
        self.hold(62, 64)
        grid = layouts.pad_colors(e)
        for n in (62, 64):
            c, r = self.pad(n)
            self.assertEqual(grid[r][c], layouts.PITCH_WHITE)
        c, r = self.pad(65)
        self.assertEqual(grid[r][c], layouts.PITCH_DIM_WHITE)

    def test_pads_from_two_grids_add_together(self):
        self.hold(60)
        layouts.pad_press(self.e, *self.pad(64, slot=2))
        self.assertEqual(self.e.armed, {60, 64})

    def test_switching_layout_forgets_held_pads(self):
        self.hold(60, 64)
        layouts.switch_layout(self.e, 1)
        self.assertEqual((self.e.armed, self.e.pitch_held), (set(), set()))

    def test_run_passes_pad_releases(self):
        import run
        class S:
            pass
        st = S()
        st.engine, st.browser_active = self.e, False
        col, row = self.pad(60)
        run.handle_pad(st, {"col": col, "row": row, "pressed": True})
        self.assertEqual(len(self.e.pitch_held), 1)
        run.handle_pad(st, {"col": col, "row": row, "pressed": False})
        self.assertEqual(self.e.pitch_held, set())
        st.browser_active = True
        run.handle_pad(st, {"col": col, "row": row, "pressed": True})
        run.handle_pad(st, {"col": col, "row": row, "pressed": False})
        self.assertEqual(self.e.pitch_held, set())


class LongPressTest(unittest.TestCase):
    """Taps act on release. A long press only highlights."""

    def setUp(self):
        self.e, _ = make()
        layouts.switch_layout(self.e, 2)

    def pitch_pad(self, note, slot=1):
        e = self.e
        track = layouts.first_track(e) + (slot - 1)
        root, scale = e.key_of(track)
        i = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave).index(note)
        return (0 if slot == 2 else 4) + i % 4, (4 if slot == 1 else 0) + i // 4

    def arm(self, *notes, slot=1):
        for n in notes:
            layouts.pad_press(self.e, *self.pitch_pad(n, slot), now=0.0)
        for n in notes:
            layouts.pad_release(self.e, *self.pitch_pad(n, slot), now=0.1)

    def set_step(self, ti, si, notes):
        s = self.e.tracks[ti]["steps"][si]
        s["on"], s["pitches"], s["pitch_set"] = True, list(notes), True

    def test_short_tap_acts_on_release(self):
        e = self.e
        self.arm(64)
        layouts.pad_press(e, 0, 7, now=1.0)
        self.assertFalse(e.tracks[0]["steps"][0]["on"])
        layouts.pad_release(e, 0, 7, now=1.1)
        self.assertEqual(e.tracks[0]["steps"][0]["pitches"], [64])
        self.assertTrue(e.tracks[0]["steps"][0]["on"])

    def test_long_press_changes_nothing(self):
        e = self.e
        self.arm(64)
        layouts.pad_press(e, 0, 7, now=1.0)
        layouts.pad_release(e, 0, 7, now=1.0 + layouts.LONG_PRESS_S + 0.1)
        self.assertFalse(e.tracks[0]["steps"][0]["on"])

    def test_plain_tap_without_armed_note_also_waits(self):
        e = self.e
        layouts.pad_press(e, 0, 7, now=1.0)
        self.assertFalse(e.tracks[0]["steps"][0]["on"])
        layouts.pad_release(e, 0, 7, now=1.1)
        self.assertTrue(e.tracks[0]["steps"][0]["on"])

    def test_layout_1_taps_stay_immediate(self):
        e = self.e
        layouts.switch_layout(e, 0)
        layouts.pad_press(e, 0, 7, now=1.0)
        self.assertTrue(e.tracks[0]["steps"][0]["on"])
        layouts.pad_release(e, 0, 7, now=1.1)
        self.assertTrue(e.tracks[0]["steps"][0]["on"])

    def test_shift_select_stays_immediate(self):
        e = self.e
        e.shift = True
        layouts.pad_press(e, 0, 7, now=1.0)
        self.assertEqual(e.sel.get(0), 0)

    def test_arming_is_immediate_but_disarm_waits_for_release(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(64), now=0.0)
        self.assertEqual(e.armed, {64})
        layouts.pad_release(e, *self.pitch_pad(64), now=0.1)
        layouts.pad_press(e, *self.pitch_pad(64), now=1.0)
        self.assertEqual(e.armed, {64})                       # not yet
        layouts.pad_release(e, *self.pitch_pad(64), now=1.1)
        self.assertEqual(e.armed, set())

    def test_long_press_on_the_armed_pad_keeps_it_armed(self):
        e = self.e
        self.arm(64)
        layouts.pad_press(e, *self.pitch_pad(64), now=1.0)
        layouts.pad_release(e, *self.pitch_pad(64), now=2.0)
        self.assertEqual(e.armed, {64})

    def test_long_press_on_a_step_lights_its_notes_on_every_grid(self):
        e = self.e
        self.set_step(0, 0, [60, 64])
        self.set_step(1, 0, [62])
        layouts.pad_press(e, 0, 7, now=1.0)                  # step 0 of the working track
        short = layouts.pad_colors(e, now=1.1)
        long_ = layouts.pad_colors(e, now=1.0 + layouts.LONG_PRESS_S + 0.05)
        def at(grid, slot, note):
            c, r = self.pitch_pad(note, slot)
            return grid[r][c]
        c0, c1 = e.tracks[0]["color"], e.tracks[1]["color"]
        self.assertEqual(at(short, 1, 64), layouts.PITCH_DIM_WHITE)
        self.assertEqual(at(long_, 1, 60), c0)                  # root: full track color
        self.assertEqual(at(long_, 1, 64), layouts.PITCH_WHITE)
        self.assertEqual(at(long_, 1, 62), layouts.LONG_PRESS_DIM)
        self.assertEqual(at(long_, 2, 62), layouts.PITCH_WHITE)  # second track, same step
        self.assertEqual(at(long_, 2, 60), layouts.dim(c1))
        self.assertEqual(at(long_, 2, 64), layouts.LONG_PRESS_DIM)
        layouts.pad_release(e, 0, 7, now=2.0)
        after = layouts.pad_colors(e, now=2.1)
        self.assertEqual(at(after, 1, 64), layouts.PITCH_DIM_WHITE)

    def test_long_press_on_a_step_ignores_the_armed_marks(self):
        e = self.e
        self.set_step(0, 0, [64])
        self.arm(62)
        layouts.pad_press(e, 0, 7, now=1.0)
        grid = layouts.pad_colors(e, now=2.0)
        c, r = self.pitch_pad(62)
        self.assertEqual(grid[r][c], layouts.LONG_PRESS_DIM)

    def test_long_press_on_a_note_dims_steps_without_it(self):
        e = self.e
        self.set_step(0, 0, [60])
        self.set_step(0, 1, [64])
        self.set_step(0, 2, [60, 64])
        layouts.pad_press(e, *self.pitch_pad(64), now=1.0)
        color = e.tracks[0]["color"]
        normal = layouts.pad_colors(e, now=1.1)
        held = layouts.pad_colors(e, now=1.0 + layouts.LONG_PRESS_S + 0.05)
        self.assertEqual(normal[7][0], color)
        self.assertEqual(held[7][0], layouts.LONG_PRESS_DIM)    # step 0: no E
        self.assertEqual(held[7][1], color)                     # step 1: has E
        self.assertEqual(held[7][2], color)                     # step 2: has E
        self.assertEqual(held[7][3], layouts.LONG_PRESS_DIM)    # step 3: off
        layouts.pad_release(e, *self.pitch_pad(64), now=2.0)
        self.assertEqual(layouts.pad_colors(e, now=2.1)[7][0], color)

    def test_layout_2_note_press_only_dims_its_own_track(self):
        e = self.e
        layouts.switch_layout(e, 1)
        self.set_step(0, 0, [60])
        self.set_step(1, 0, [60])
        layouts.pad_press(e, *self.pitch_pad(64), now=1.0)      # TR grid = first track
        grid = layouts.pad_colors(e, now=2.0)
        self.assertEqual(grid[7][0], layouts.LONG_PRESS_DIM)    # TL quadrant, first track
        self.assertEqual(grid[3][0], e.tracks[1]["color"])      # BL quadrant untouched

    def test_playhead_stays_green_while_dimmed(self):
        e = self.e
        self.set_step(0, 1, [64])
        e.tracks[0]["_current_step"] = 0
        layouts.pad_press(e, *self.pitch_pad(64), now=1.0)
        grid = layouts.pad_colors(e, now=2.0)
        self.assertEqual(grid[7][0], layouts.PLAYHEAD)

    def test_layout_switch_drops_held_pads(self):
        e = self.e
        layouts.pad_press(e, 0, 7, now=1.0)
        layouts.switch_layout(e, 0)
        layouts.pad_release(e, 0, 7, now=1.1)
        self.assertFalse(e.tracks[0]["steps"][0]["on"])


class HoldStepInputTest(unittest.TestCase):
    """Hold a step pad and tap pitch pads: the notes go into that step on the track of each pad."""

    def setUp(self):
        self.e, _ = make()
        layouts.switch_layout(self.e, 2)

    def pitch_pad(self, note, slot=1):
        e = self.e
        track = layouts.first_track(e) + (slot - 1)
        root, scale = e.key_of(track)
        i = eng.grid_pitches(root, scale, e.pattern["in_key"], e.octave).index(note)
        return (0 if slot == 2 else 4) + i % 4, (4 if slot == 1 else 0) + i // 4

    def steps(self, ti, si):
        return self.e.tracks[ti]["steps"][si]

    def test_notes_tapped_while_holding_go_into_the_held_step(self):
        e = self.e
        layouts.pad_press(e, 0, 7, now=1.0)                  # hold step 0
        tap(e, *self.pitch_pad(64))                          # track 1 grid
        s = self.steps(0, 0)
        self.assertEqual((s["on"], s["pitches"]), (True, [64]))
        tap(e, *self.pitch_pad(67))
        self.assertEqual(self.steps(0, 0)["pitches"], [64, 67])
        layouts.pad_release(e, 0, 7, now=1.2)
        self.assertEqual(self.steps(0, 0)["pitches"], [64, 67])   # releasing does not toggle the step
        self.assertTrue(self.steps(0, 0)["on"])
        self.assertEqual(e.armed, set())

    def test_tapping_a_note_again_removes_it(self):
        e = self.e
        layouts.pad_press(e, 0, 7, now=1.0)
        tap(e, *self.pitch_pad(64))
        tap(e, *self.pitch_pad(64))
        layouts.pad_release(e, 0, 7, now=1.2)
        self.assertFalse(self.steps(0, 0)["on"])

    def test_notes_from_other_tracks_go_to_the_same_step_of_that_track(self):
        e = self.e
        layouts.pad_press(e, 2, 7, now=1.0)                  # hold step 2 of the working track (1)
        tap(e, *self.pitch_pad(64, slot=1))                  # track 1
        tap(e, *self.pitch_pad(67, slot=2))                  # track 2
        tap(e, *self.pitch_pad(71, slot=3))                  # track 3
        layouts.pad_release(e, 2, 7, now=1.2)
        self.assertEqual(self.steps(0, 2)["pitches"], [64])
        self.assertEqual(self.steps(1, 2)["pitches"], [67])
        self.assertEqual(self.steps(2, 2)["pitches"], [71])
        for ti in range(3):
            self.assertTrue(self.steps(ti, 2)["on"])
            self.assertFalse(self.steps(ti, 3)["on"])

    def test_armed_notes_are_not_touched(self):
        e = self.e
        layouts.pad_press(e, *self.pitch_pad(62), now=0.0)
        layouts.pad_release(e, *self.pitch_pad(62), now=0.1)
        layouts.pad_press(e, 0, 7, now=1.0)
        tap(e, *self.pitch_pad(64))
        layouts.pad_release(e, 0, 7, now=1.2)
        self.assertEqual(e.armed, {62})

    def test_a_track_with_a_shorter_sequence_skips_the_step(self):
        e = self.e
        e.tracks[1]["length"] = 4
        layouts.pad_press(e, 0, 7, now=1.0)
        layouts.pad_press(e, 0, 6, now=1.0)                  # step 4 as well? hold only the last
        e.pad_down.pop((0, 7))
        tap(e, *self.pitch_pad(67, slot=2))
        self.assertFalse(self.steps(1, 4)["on"])

    def test_layout_2_notes_go_to_the_track_of_the_pad(self):
        e = self.e
        layouts.switch_layout(e, 1)
        layouts.pad_press(e, 0, 7, now=1.0)                  # hold step 0 of the first track
        tap(e, *self.pitch_pad(64, slot=3))                  # BR grid = second track
        layouts.pad_release(e, 0, 7, now=1.2)
        self.assertEqual(self.steps(1, 0)["pitches"], [64])
        self.assertFalse(self.steps(0, 0)["on"])

    def test_the_highlight_shows_the_new_notes(self):
        e = self.e
        layouts.pad_press(e, 0, 7, now=1.0)
        tap(e, *self.pitch_pad(64))
        grid = layouts.pad_colors(e, now=2.0)
        c, r = self.pitch_pad(64)
        self.assertEqual(grid[r][c], layouts.PITCH_WHITE)

    def test_without_a_held_step_a_pitch_tap_still_arms(self):
        e = self.e
        tap(e, *self.pitch_pad(64))
        self.assertEqual(e.armed, {64})
        self.assertFalse(self.steps(0, 0)["on"])


class ExternalTempoTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.e = eng.Engine(lambda ch, n, v: None, lambda ch, n: None,
                            send_transport=self.sent.append)
        self.base = __import__("time").monotonic()

    def ticks(self, n, bpm, start=0):
        dt = 60.0 / (bpm * 24)
        for i in range(n):
            self.e.on_external_clock_byte(0xF8, now=self.base + (start + i) * dt)
        return self.base + (start + n - 1) * dt

    def test_tempo_is_measured_from_the_clock(self):
        self.ticks(60, 90)
        self.assertAlmostEqual(self.e.bpm(), 90, delta=0.5)
        self.assertAlmostEqual(self.e.step_duration(self.e.tracks[0]), 60 / 90 * 0.25, delta=0.002)

    def test_tempo_follows_a_change_of_the_sender(self):
        last = self.ticks(60, 120)
        dt = 60.0 / (150 * 24)
        for i in range(60):
            self.e.on_external_clock_byte(0xF8, now=last + (i + 1) * dt)
        self.assertAlmostEqual(self.e.bpm(), 150, delta=0.5)

    def test_internal_bpm_is_used_without_a_clock(self):
        self.assertEqual(self.e.bpm(), self.e.pattern["bpm"])
        self.ticks(60, 90)
        self.e.last_ext_clock -= 10                     # the clock stopped long ago
        self.assertEqual(self.e.bpm(), self.e.pattern["bpm"])

    def test_nonsense_intervals_do_not_set_the_tempo(self):
        for _ in range(40):
            self.e.on_external_clock_byte(0xF8, now=self.base)     # all at the same time
        self.assertEqual(self.e.bpm(), self.e.pattern["bpm"])

    def test_a_gap_starts_a_new_measurement(self):
        self.ticks(60, 90)
        self.ticks(60, 150, start=60 + 200)             # long pause, then 150 BPM
        self.assertAlmostEqual(self.e.bpm(), 150, delta=0.5)

    def test_wheel_changes_the_internal_bpm_without_a_clock(self):
        self.e.nudge_tempo(5)
        self.assertEqual(self.e.pattern["bpm"], eng.DEFAULT_BPM + 5)
        self.e.nudge_tempo(-1000)
        self.assertEqual(self.e.pattern["bpm"], eng.MIN_BPM)
        self.assertEqual(self.sent, [])

    def test_status_line_marks_the_external_clock(self):
        self.assertNotIn("EXT", view._status_line(self.e))
        self.ticks(60, 100)
        self.e.last_ext_clock = __import__("time").monotonic()
        line = view._status_line(self.e)
        self.assertIn("EXT", line)
        self.assertIn("100 BPM", line)

class MidiChannelKnobTest(unittest.TestCase):
    def test_edit_encoders_no_longer_have_a_channel(self):
        self.assertNotIn("channel", eng.PARAMS)
        self.assertEqual(len(eng.PARAMS), 7)

    def test_first_encoder_of_each_track_is_its_channel_knob(self):
        e, _ = make()
        self.assertEqual([layouts.channel_track(e, i) for i in range(8)],
                         [0, None, 1, None, 2, None, 3, None])
        for layout in (1, 2):
            layouts.switch_layout(e, layout)
            self.assertEqual([layouts.channel_track(e, i) for i in range(8)],
                             [0, None, 1, None, 2, None, 3, None])

    def test_knob_changes_the_channel_with_friction_and_clamp(self):
        e, _ = make()
        e.nudge_channel(1, 3, 2)                       # friction 4: not yet
        self.assertEqual(e.tracks[1]["channel"], 1)
        e.nudge_channel(1, 1, 2)
        self.assertEqual(e.tracks[1]["channel"], 2)
        e.nudge_channel(1, 4000, 2)
        self.assertEqual(e.tracks[1]["channel"], 16)
        e.nudge_channel(1, -4000, 2)
        self.assertEqual(e.tracks[1]["channel"], 1)
        self.assertEqual(e.active_param[0], 2)
        self.assertEqual(e.tracks[0]["channel"], 1)

    def test_reset(self):
        e, _ = make()
        e.tracks[2]["channel"] = 9
        e.reset_channel(2, 4)
        self.assertEqual(e.tracks[2]["channel"], 1)

    def test_run_routes_turn_and_touch_and_selects_the_track(self):
        import run
        class S:
            pass
        st = S()
        st.engine, st.browser_active = make()[0], False
        e = st.engine
        run.handle_encoder(st, {"name": "Encoder 5 turn", "index": 4, "delta": 8})
        self.assertEqual(e.tracks[2]["channel"], 3)
        self.assertEqual(e.rate_track, 2)
        e.delete = True
        run.handle_touch(st, {"name": "Encoder 5 touch", "touched": True})
        self.assertEqual(e.tracks[2]["channel"], 1)
        e.delete = False
        run.handle_encoder(st, {"name": "Encoder 6 turn", "index": 5, "delta": -8})   # S LEN still works
        self.assertEqual(e.tracks[2]["length"], 14)

    def test_channel_still_plays_on_the_track_channel(self):
        e, notes = make()
        e.tracks[0]["channel"] = 5
        tap_layout1 = layouts.pad_press
        tap_layout1(e, 0, 7)
        e.start()
        e.tick(e.play_start + 0.001)
        self.assertEqual(notes[0][1], 5)

    def test_main_view_shows_a_midi_knob_per_track_and_edit_view_has_none(self):
        class S:
            pass
        st = S()
        st.engine, _ = make()
        st.button_held, st.browser_active, st.browser_names, st.browser_cursor = {}, False, [], 0
        st.popup_title = st.popup_body = None
        st.popup_until = 0
        e = st.engine
        e.tracks[1]["channel"] = 7
        texts = [o["params"]["s"] for o in view.draw(st)["ops"] if o["kind"] == "text"]
        self.assertEqual(texts.count("MIDI"), 4)
        self.assertEqual(texts.count("S LEN"), 4)
        e.touch_param(2)                               # second track's channel knob
        texts = [o["params"]["s"] for o in view.draw(st)["ops"] if o["kind"] == "text"]
        self.assertEqual(texts.count("MIDI"), 3)
        self.assertIn("7", texts)
        layouts.pad_press(e, 0, 7)                     # edit view
        e.active_param = None
        ops = view.draw(st)["ops"]
        texts = [o["params"]["s"] for o in ops if o["kind"] == "text"]
        self.assertNotIn("MIDI", texts)
        self.assertEqual(sum(1 for o in ops if o["kind"] == "knobarc"), 6 * 4)   # 6 knobs on each of 4 tracks


class LeadClockTest(unittest.TestCase):
    """Tempo encoder press: lead the DAW (send clock) or follow its clock."""

    def setUp(self):
        self.sent = []
        self.e = eng.Engine(lambda ch, n, v: None, lambda ch, n: None, send_transport=self.sent.append)
        self.now = __import__("time").monotonic()

    def follow_a_clock(self, bpm=100, n=60):
        dt = 60.0 / (bpm * 24)
        for i in range(n):
            self.e.on_external_clock_byte(0xF8, now=self.now + i * dt)
        self.e.last_ext_clock = __import__("time").monotonic()

    def test_default_is_follow(self):
        self.assertFalse(self.e.lead)

    def test_toggle_flips_the_role_and_stops_the_transport(self):
        self.e.start()
        self.assertTrue(self.e.toggle_lead())
        self.assertTrue(self.e.lead)
        self.assertFalse(self.e.playing)
        self.assertFalse(self.e.toggle_lead())
        self.assertFalse(self.e.lead)

    def test_play_and_stop_send_transport_only_when_leading(self):
        self.e.start()
        self.e.stop()
        self.assertEqual(self.sent, [])
        self.e.toggle_lead()
        self.e.toggle_play()
        self.e.toggle_play()
        self.assertEqual(self.sent, ["start", "stop"])

    def test_stop_without_playing_sends_nothing(self):
        self.e.toggle_lead()
        self.e.stop()
        self.assertEqual(self.sent, [])

    def test_incoming_clock_and_transport_are_ignored_when_leading(self):
        self.e.toggle_lead()
        self.follow_a_clock()
        self.e.on_external_clock_byte(0xFA)
        self.assertFalse(self.e.playing)
        self.assertFalse(self.e.is_externally_synced())
        self.assertEqual(self.e.bpm(), self.e.pattern["bpm"])

    def test_wheel_sets_the_bpm_when_leading(self):
        self.follow_a_clock()
        self.e.toggle_lead()
        self.e.nudge_tempo(5)
        self.assertEqual(self.e.pattern["bpm"], eng.DEFAULT_BPM + 5)

    def test_wheel_does_nothing_while_following_a_clock(self):
        self.follow_a_clock()
        before = self.e.pattern["bpm"]
        self.e.nudge_tempo(5)
        self.assertEqual(self.e.pattern["bpm"], before)
        self.assertEqual(self.sent, [])

    def test_going_back_to_follow_measures_again(self):
        self.follow_a_clock(100)
        self.e.toggle_lead()
        self.e.toggle_lead()
        self.assertIsNone(self.e.ext_bpm)

    def test_status_line_says_lead(self):
        self.e.toggle_lead()
        self.assertIn("LEAD", view._status_line(self.e))
        self.assertNotIn("EXT", view._status_line(self.e))

    def test_run_press_toggles_and_the_wheel_shows_the_tempo(self):
        import run
        class S:
            def __init__(self, e):
                self.engine, self.browser_active, self.popup = e, False, None
                self.button_held = {}

            def show_popup(self, title, body=None):
                self.popup = (title, body)
        st = S(self.e)
        run.handle_button(st, {"name": "Tempo encoder press", "pressed": True})
        self.assertTrue(self.e.lead)
        self.assertEqual(st.popup, ("CLOCK", "LEAD"))
        run.handle_button(st, {"name": "Tempo encoder press", "pressed": False})
        self.assertTrue(self.e.lead)                              # a release does nothing
        run.handle_encoder(st, {"name": "Tempo wheel turn", "delta": 3})
        self.assertEqual(st.popup, ("TEMPO", str(eng.DEFAULT_BPM + 3)))
        run.handle_button(st, {"name": "Tempo encoder press", "pressed": True})
        self.assertEqual(st.popup, ("CLOCK", "FOLLOW"))
        self.follow_a_clock(100)
        run.handle_encoder(st, {"name": "Tempo wheel turn", "delta": 3})
        self.assertEqual(st.popup[0], "TEMPO")
        self.assertIn("EXT", st.popup[1])

    def test_state_sends_transport_to_the_host(self):
        import run
        st = run.State()
        sent = []
        st.request = lambda method, params: sent.append(method)
        st.engine.toggle_lead()
        st.engine.start()
        st.engine.stop()
        self.assertEqual(sent, ["send_start", "send_stop"])


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
        r._track_button(e, 6)                                  # same buttons in every layout
        self.assertEqual(e.rate_track, 3)

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
    def test_pad_window_follows_working_track(self):
        e, _ = make()
        for _ in range(4):
            e.add_track()
        e.rate_track = 5
        layouts.switch_layout(e, 1)
        self.assertEqual(layouts.pad_tracks(e), [4, 5])
        layouts.switch_layout(e, 2)
        self.assertEqual(layouts.pad_tracks(e), [3, 4, 5])
        e.track_page = 1
        layouts.switch_layout(e, 0)                       # Layout 1 follows the screen page
        self.assertEqual(layouts.pad_tracks(e), [4, 5, 6, 7])
        self.assertEqual(layouts.screen_tracks(e), [4, 5, 6, 7])

    def test_page_buttons_move_screen_and_working_track(self):
        e, _ = make()
        for _ in range(4):
            e.add_track()
        layouts.page_screen(e, 1)
        self.assertEqual((e.track_page, e.rate_track), (1, 4))
        layouts.page_screen(e, 1)                         # no third page
        self.assertEqual(e.track_page, 1)
        layouts.page_screen(e, -1)
        self.assertEqual((e.track_page, e.rate_track), (0, 0))

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

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clockout


class FakeEngine:
    def __init__(self, lead=True, bpm=240):
        self.lead = lead
        self.pattern = {"bpm": bpm}


class ClockOutTest(unittest.TestCase):
    def run_for(self, engine, seconds, rephase_at=None):
        ticks = []
        c = clockout.ClockOut(engine, lambda: ticks.append(time.monotonic()))
        c.start()
        time.sleep(seconds)
        c.stop()
        c.join(1.0)
        return ticks

    def test_sends_24_ticks_per_beat_when_leading(self):
        ticks = self.run_for(FakeEngine(bpm=240), 0.5)          # 96 ticks per second
        self.assertGreaterEqual(len(ticks), 36)
        self.assertLessEqual(len(ticks), 60)

    def test_ticks_are_evenly_spaced(self):
        ticks = self.run_for(FakeEngine(bpm=240), 0.5)
        gaps = [b - a for a, b in zip(ticks, ticks[1:])]
        self.assertLess(max(gaps), 0.025)                       # 10.4 ms nominal

    def test_sends_nothing_when_following(self):
        self.assertEqual(self.run_for(FakeEngine(lead=False), 0.2), [])

    def test_follows_a_tempo_change(self):
        e = FakeEngine(bpm=120)                                 # 48 ticks per second
        ticks = []
        c = clockout.ClockOut(e, lambda: ticks.append(time.monotonic()))
        c.start()
        time.sleep(0.3)
        n1 = len(ticks)
        e.pattern["bpm"] = 240
        time.sleep(0.3)
        c.stop()
        c.join(1.0)
        self.assertGreater(len(ticks) - n1, n1 * 1.4)

    def test_does_not_spin_after_a_rephase_while_following(self):
        """The tempo encoder press calls rephase(). While following, that must not make the thread busy-loop."""
        e = FakeEngine(lead=False)
        waits = []
        c = clockout.ClockOut(e, lambda: None)
        real_wait = c._rephase.wait
        c._rephase.wait = lambda t=None: (waits.append(1), real_wait(t))[1]
        c.start()
        time.sleep(0.1)
        c.rephase()
        c.rephase()
        time.sleep(0.6)
        c.stop()
        c.join(1.0)
        self.assertLess(len(waits), 20)

    def test_back_to_follow_after_leading_does_not_spin(self):
        e = FakeEngine(lead=True)
        ticks = []
        c = clockout.ClockOut(e, lambda: ticks.append(1))
        c.start()
        time.sleep(0.1)
        e.lead = False
        c.rephase()                                     # what the press does
        time.sleep(0.1)
        n = len(ticks)
        waits = []
        real_wait = c._rephase.wait
        c._rephase.wait = lambda t=None: (waits.append(1), real_wait(t))[1]
        time.sleep(0.6)
        c.stop()
        c.join(1.0)
        self.assertLess(len(waits), 20)
        self.assertLessEqual(len(ticks) - n, 1)         # no ticks while following

    def test_stops_when_asked(self):
        e = FakeEngine()
        c = clockout.ClockOut(e, lambda: None)
        c.start()
        c.stop()
        c.join(1.0)
        self.assertFalse(c.is_alive())


if __name__ == "__main__":
    unittest.main()

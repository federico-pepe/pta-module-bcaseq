"""clockout.py - MIDI clock out for Lead mode. A thread, so ticks do not wait for a screen frame.

Sends 24 ticks per beat at the BPM of the engine while engine.lead is on. No engine
state changes here. The tempo is read on each tick, so the wheel changes it at once.
"""

import threading
import time

TICKS_PER_QUARTER = 24
IDLE_S = 0.25         # how often the thread looks at engine.lead while following
CATCH_UP_S = 0.25   # if the thread falls this far behind, start over instead of bursting ticks


class ClockOut(threading.Thread):
    def __init__(self, engine, send_clock):
        super().__init__(daemon=True)
        self._engine = engine
        self._send_clock = send_clock
        self._quit = threading.Event()
        self._rephase = threading.Event()

    def rephase(self):
        """Next tick goes out now. Call this right after MIDI Start, and when Lead turns on."""
        self._rephase.set()

    def stop(self):
        self._quit.set()
        self._rephase.set()             # wake the idle wait

    def run(self):
        next_t = None
        while not self._quit.is_set():
            if not self._engine.lead:
                next_t = None
                if self._rephase.wait(IDLE_S):   # follow mode: wake up rarely, never disturb the incoming clock
                    self._rephase.clear()        # a set event would make the next wait return at once: a busy loop
                continue
            now = time.monotonic()
            if next_t is None or self._rephase.is_set() or now - next_t > CATCH_UP_S:
                self._rephase.clear()
                next_t = now
            if now >= next_t:
                self._send_clock()
                next_t += 60.0 / (max(1, self._engine.pattern["bpm"]) * TICKS_PER_QUARTER)
            else:
                self._quit.wait(min(next_t - now, 0.005))

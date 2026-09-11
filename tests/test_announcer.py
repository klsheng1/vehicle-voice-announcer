# -*- coding: utf-8 -*-
"""Unit tests for the announcement arbitration logic (no audio required)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from announcer.announcer import VoiceAnnouncer                     # noqa: E402
from announcer.events import Event, EventKind, Priority            # noqa: E402
from announcer.tts.silent_engine import SilentEngine               # noqa: E402


class TestAnnouncer(unittest.TestCase):
    def setUp(self):
        self.engine = SilentEngine()
        self.a = VoiceAnnouncer(self.engine, lang="en", log=lambda *_: None)

    def test_basic_announcement(self):
        ev = Event(EventKind.DEPARTURE, t=0,
                   params={"line": "L1", "destination": "Office", "destination_zh": "公司"})
        self.assertTrue(self.a.announce(ev, now=0))
        self.assertEqual(len(self.engine.spoken), 1)

    def test_cooldown_dedup(self):
        ev1 = Event(EventKind.OVERSPEED, t=0, params={"speed": 62, "limit": 50})
        ev2 = Event(EventKind.OVERSPEED, t=5, params={"speed": 63, "limit": 50})
        self.assertTrue(self.a.announce(ev1, now=0))
        self.assertFalse(self.a.announce(ev2, now=5))       # within 30s cooldown
        self.assertEqual(len(self.engine.spoken), 1)

    def test_cooldown_expires(self):
        ev1 = Event(EventKind.OVERSPEED, t=0, params={"speed": 62, "limit": 50})
        ev2 = Event(EventKind.OVERSPEED, t=0, params={"speed": 66, "limit": 50})
        self.assertTrue(self.a.announce(ev1, now=0))
        self.assertTrue(self.a.announce(ev2, now=31))       # cooldown elapsed

    def test_preemption_flag_on_safety(self):
        class RecordingEngine(SilentEngine):
            def __init__(self):
                super().__init__()
                self.stopped = 0

            def stop(self):
                self.stopped += 1

        eng = RecordingEngine()
        a = VoiceAnnouncer(eng, lang="en", log=lambda *_: None)
        a.announce(Event(EventKind.DEPARTURE, t=0,
                          params={"line": "L1", "destination": "Office", "destination_zh": "公司"}), now=0)
        self.assertEqual(eng.stopped, 0)
        a.announce(Event(EventKind.OVERSPEED, t=10, params={"speed": 70, "limit": 50}), now=10)
        self.assertEqual(eng.stopped, 1)                    # SAFETY asked engine to stop
        self.assertTrue(a.entries[-1].preempted)

    def test_event_text_formatting(self):
        ev = Event(EventKind.OVERSPEED, t=0, params={"speed": 62, "limit": 50})
        self.assertIn("62", ev.text("en"))
        self.assertIn("50", ev.text("en"))
        self.assertEqual(ev.priority, Priority.SAFETY)


if __name__ == "__main__":
    unittest.main(verbosity=2)

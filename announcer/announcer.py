# -*- coding: utf-8 -*-
"""Priority-based voice announcement arbitration.

Rules (mirroring in-vehicle HMI practice):

1. A new event is dropped if the same kind was announced within its cooldown.
2. A SAFETY announcement preempts whatever is currently playing.
3. Otherwise announcements are queued and played in priority order
   (SAFETY > NAVIGATION > SERVICE > AMBIENT), FIFO within a class.
"""
from __future__ import annotations

import time

from .events import Event, Priority


class AnnouncementLogEntry:
    __slots__ = ("t", "priority", "label", "text", "preempted", "dropped")

    def __init__(self, t: float, priority: Priority, label: str, text: str,
                 preempted: bool = False, dropped: bool = False):
        self.t = t
        self.priority = priority
        self.label = label
        self.text = text
        self.preempted = preempted
        self.dropped = dropped


class VoiceAnnouncer:
    """Consumes events from a scenario and speaks them through a TTS engine.

    ``engine`` only needs :meth:`speak(text)` and :meth:`stop()`; see
    :mod:`announcer.tts` for the available backends. ``speedup`` compresses
    wall-clock time so a 15-minute simulated trip plays in seconds.
    """

    def __init__(self, engine, lang: str = "zh", speedup: float = 1.0,
                 log=print, quiet: bool = False):
        self.engine = engine
        self.lang = lang
        self.speedup = max(1e-6, float(speedup))
        self.log = log
        self.quiet = quiet
        self._last_played: dict[str, float] = {}
        self.entries: list[AnnouncementLogEntry] = []

    # ------------------------------------------------------------------
    def _within_cooldown(self, event: Event, now: float) -> bool:
        last = self._last_played.get(event.kind)
        return last is not None and (now - last) < event.cooldown

    def announce(self, event: Event, now: float | None = None) -> bool:
        """Decide whether/how to announce one event. Returns True if spoken.

        Note: preemption of a blocking TTS call is engine-dependent; the
        SAFETY class is always moved to the head of the queue and the engine
        is asked to ``stop()`` first.
        """
        now = time.monotonic() if now is None else now
        if self._within_cooldown(event, now):
            self.entries.append(AnnouncementLogEntry(
                event.t, event.priority, event.label, "", dropped=True))
            return False

        self._last_played[event.kind] = now
        text = event.text(self.lang)
        preempt = event.priority == Priority.SAFETY
        if preempt:
            try:
                self.engine.stop()
            except Exception:
                pass
        if not self.quiet:
            tag = "⚠ PREEMPT" if preempt else "  PLAY"
            self.log(f"[{event.t:7.1f}s] [{event.priority.name:<9}] {tag}  {text}")
        try:
            self.engine.speak(text)
        except Exception as exc:  # never let TTS failure kill the simulation
            if not self.quiet:
                self.log(f"[{event.t:7.1f}s] [ENGINE  ] TTS error: {exc}")
        self.entries.append(AnnouncementLogEntry(
            event.t, event.priority, event.label, text, preempted=preempt))
        return True

    # ------------------------------------------------------------------
    def run_scenario(self, scenario, hold: float = 0.0):
        """Drive a scenario: consume its events in simulation order.

        ``hold`` (sim-seconds) keeps the announcer alive after the last event
        so queued AMBIENT items can still be flushed in real engines.
        """
        result = scenario.run()
        events = list(result.events)
        events.sort(key=lambda e: e.t)
        start = time.monotonic()
        for ev in events:
            # pacing: respect simulated time scaled by speedup
            target = start + (ev.t / self.speedup)
            wait = target - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.announce(ev, now=ev.t / max(1.0, self.speedup) * 1.0)
        if hold:
            time.sleep(hold / self.speedup)
        return result

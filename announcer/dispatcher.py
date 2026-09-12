"""Announcement arbitration: cooldown suppression + priority preemption.

The dispatcher is pure logic (no audio), which keeps it unit-testable; the
player in :mod:`announcer.cli` executes the decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from .events import Event


@dataclass
class Decision:
    event: Event
    action: str        # "announce" | "queued" | "preempt" | "suppress"
    reason: str = ""
    displaced: Event | None = None   # message cancelled by a preemption


class Dispatcher:
    """Decides what to speak and what to drop.

    Rules
    -----
    * an event whose cooldown group fired within ``cooldown_s`` is suppressed;
    * a higher-priority event preempts (cancels) a lower-priority one that is
      still speaking/queued;
    * everything else is queued FIFO until the current message finishes.
    """

    def __init__(self, cooldown_s: float = 20.0):
        self.cooldown_s = cooldown_s
        self._last_fired: dict[str, float] = {}
        self._current: Event | None = None
        self._queue: list[Event] = []

    def submit(self, event: Event) -> Decision:
        last = self._last_fired.get(event.cooldown_group())
        if last is not None and event.t_sim - last < self.cooldown_s:
            return Decision(event, "suppress",
                            reason=f"cooldown group {event.cooldown_group()!r} "
                                   f"fired {event.t_sim - last:.0f}s ago")

        if self._current is None:
            return self._start(event, action="announce")

        if event.priority > self._current.priority:
            displaced = self._current
            self._current = event
            self._last_fired[event.cooldown_group()] = event.t_sim
            self._queue.clear()  # stale lower-priority messages are dropped
            return Decision(event, "preempt",
                            reason=f"priority {event.priority.name} > "
                                   f"{displaced.priority.name}",
                            displaced=displaced)

        self._queue.append(event)
        return Decision(event, "queued")

    def finish_current(self) -> Event | None:
        """Mark the current message as done; return the next queued one."""
        if self._current is not None:
            self._current = None
        if self._queue:
            nxt = self._queue.pop(0)
            return self._start(nxt, action="announce").event
        return None

    def _start(self, event: Event, action: str) -> Decision:
        self._current = event
        self._last_fired[event.cooldown_group()] = event.t_sim
        return Decision(event, action)

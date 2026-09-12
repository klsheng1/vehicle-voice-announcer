"""Traffic events produced by the drive simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Priority(IntEnum):
    """Higher value wins when messages collide."""

    INFO = 1
    NAVIGATION = 2
    SAFETY = 3


@dataclass(frozen=True)
class Event:
    """One announcement-worthy thing that happens during a drive.

    ``t_sim`` is seconds since drive start; ``params`` fill the prompt
    template; ``cooldown_key`` groups related events so the dispatcher can
    suppress repeats (defaults to ``kind``).
    """

    kind: str
    t_sim: float
    priority: Priority
    params: dict = field(default_factory=dict)
    cooldown_key: str | None = None

    def cooldown_group(self) -> str:
        return self.cooldown_key or self.kind

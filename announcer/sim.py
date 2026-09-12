"""A scripted urban bus drive that emits traffic events.

The drive is deterministic: a speed trace (km/h) over ~5 simulated minutes
plus a hand-authored event script. Two events are *derived* from the trace —
speeding alerts fire whenever the car exceeds the local limit, so the
dispatcher's cooldown logic has something realistic to chew on.
"""

from __future__ import annotations

import numpy as np

from .events import Event, Priority

DURATION_S = 310

# (t, km/h) control points of the speed trace.
_SPEED_WAYPOINTS = [
    (0, 0), (12, 42), (40, 42), (48, 0), (86, 0),          # start, cruise, red light
    (100, 48), (108, 48), (112, 45), (118, 45), (124, 28),  # speeding in school zone
    (132, 28), (140, 40), (150, 40), (156, 18), (200, 20),  # school zone, congestion
    (208, 45), (240, 45), (248, 0), (262, 40), (300, 0),    # bus stop, final leg
]

# School zone: lower limit between t=95..135.
_SCHOOL_ZONE = (95.0, 135.0, 30.0)
_BASE_LIMIT = 60.0

_SCRIPT = [
    ("departure",   5,   Priority.INFO,       {}),
    ("next_stop",   20,  Priority.NAVIGATION, {"stop": "东长安街"}),
    ("red_light",   44,  Priority.NAVIGATION, {"seconds": 40}),
    ("sharp_turn",  96,  Priority.SAFETY,     {}),
    ("school_zone", 99,  Priority.SAFETY,     {}),
    ("congestion",  150, Priority.NAVIGATION, {"minutes": 6}),
    ("blind_spot",  152, Priority.SAFETY,     {}),   # preempts the congestion line
    ("rain",        210, Priority.SAFETY,     {}),
    ("next_stop",   216, Priority.NAVIGATION, {"stop": "人民广场"}),
    ("next_stop",   224, Priority.NAVIGATION, {"stop": "人民广场"}),  # suppressed (cooldown)
    ("arriving",    244, Priority.NAVIGATION, {"stop": "人民广场"}),
    ("arrival",     258, Priority.NAVIGATION, {"stop": "人民广场"}),
    ("trip_end",    296, Priority.INFO,       {}),
]


def speed_limit(t: np.ndarray) -> np.ndarray:
    return np.where((t >= _SCHOOL_ZONE[0]) & (t <= _SCHOOL_ZONE[1]),
                    _SCHOOL_ZONE[2], _BASE_LIMIT)


def build_drive() -> tuple[list[Event], np.ndarray, np.ndarray, np.ndarray]:
    """Return (events sorted by time, t, speed_kmh, limit_kmh)."""
    t = np.arange(0.0, DURATION_S, 0.5)
    speed = np.interp(t, [p[0] for p in _SPEED_WAYPOINTS],
                      [p[1] for p in _SPEED_WAYPOINTS])
    limit = speed_limit(t)

    events = [Event(kind=kind, t_sim=float(ts), priority=prio, params=params)
              for kind, ts, prio, params in _SCRIPT]

    # Derived speeding alerts at each entry into "over limit" territory.
    over = speed > limit + 3.0
    for i in range(1, len(t)):
        if over[i] and not over[i - 1]:
            events.append(Event(kind="speeding", t_sim=float(t[i]),
                                priority=Priority.SAFETY, params={},
                                cooldown_key="speeding"))

    events.sort(key=lambda e: e.t_sim)
    return events, t, speed, limit

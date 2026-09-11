# -*- coding: utf-8 -*-
"""Trip simulators that produce traffic events from a simple kinematic model.

Two demo scenarios are provided:

* :class:`BusScenario` — a bus route with stops, generating
  next-stop / arrival / door announcements.
* :class:`CarScenario` — a private-car commute, generating turn-by-turn,
  overspeed, harsh-braking, congestion and fatigue events.

The simulators are deterministic (seeded) so demos and screenshots are
reproducible. Telemetry (speed trace) is recorded for plotting.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .events import Event, EventKind, ScenarioKind


@dataclass
class Stop:
    name_zh: str
    name_en: str
    distance: int          # meters from route start

    def name(self, lang: str = "zh") -> str:
        return self.name_zh if lang.startswith("zh") else self.name_en


@dataclass
class TripResult:
    scenario: str
    line: str
    destination: str = ""
    events: list = field(default_factory=list)     # list[Event]
    speeds: list = field(default_factory=list)     # km/h sample per sim second
    total_distance: float = 0.0                    # meters
    duration: float = 0.0                          # sim seconds


class BaseScenario:
    """Discrete-time simulation, one tick = one simulated second."""

    kind = ScenarioKind.BUS
    line = "Demo Line 1"
    destination_zh = ""
    destination_en = ""

    def __init__(self, seed: int | None = 42):
        self.rng = random.Random(seed)

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _accelerate(v: float, target: float, accel: float = 1.4, dt: float = 1.0) -> float:
        return v + min(accel * dt, max(0.0, target - v))

    @staticmethod
    def _brake(v: float, target: float, decel: float = 2.0, dt: float = 1.0) -> float:
        return max(target, v - decel * dt)

    @staticmethod
    def _kmh(v_ms: float) -> float:
        return v_ms * 3.6

    def destination(self, lang: str = "zh") -> str:
        return self.destination_zh if lang.startswith("zh") else self.destination_en

    def run(self) -> TripResult:  # pragma: no cover - overridden
        raise NotImplementedError


class BusScenario(BaseScenario):
    """A city bus route: 5 demo stops by default, or any real GTFS stop list."""

    kind = ScenarioKind.BUS
    line = "Demo Line 1"
    destination_zh = "科技园站"
    destination_en = "Tech Park"

    DWELL_SECONDS = 15
    CRUISE_MIN, CRUISE_MAX = 11.0, 14.5        # m/s  (~40 - 52 km/h)
    SPEED_LIMIT = 50                            # km/h
    OVERSPEED_SEGMENT = (4500, 7000)            # meters where bus slightly exceeds limit

    STOPS = [
        Stop("火车站", "Railway Station", 0),
        Stop("人民广场", "People's Square", 1800),
        Stop("市中心医院", "Central Hospital", 3900),
        Stop("体育馆", "Stadium", 6100),
        Stop("科技园站", "Tech Park", 8600),
    ]

    def __init__(self, seed: int | None = 42, stops: list[Stop] | None = None,
                 line: str | None = None, destination_zh: str | None = None,
                 destination_en: str | None = None, dwell: int = 15,
                 speed_limit: int = 50):
        """``stops`` allows injecting a real GTFS stop sequence (see gtfs.py)."""
        super().__init__(seed)
        if stops:
            self.STOPS = stops
        if line:
            self.line = line
        if destination_zh:
            self.destination_zh = destination_zh
        if destination_en:
            self.destination_en = destination_en
        self.DWELL_SECONDS = dwell
        self.SPEED_LIMIT = speed_limit
        total = self.STOPS[-1].distance
        # put the speeding episode roughly in the middle third of the route
        self.OVERSPEED_SEGMENT = (int(total * 0.45), int(total * 0.70))

    def run(self) -> TripResult:
        rng = self.rng
        result = TripResult(scenario=self.kind, line=self.line,
                            destination=self.destination_en)
        stops = self.STOPS
        result.events.append(Event(EventKind.DEPARTURE, t=0.0, params={
            "line": self.line,
            "destination": self.destination_en,
            "destination_zh": self.destination_zh,
        }))

        pos, v, t = 0.0, 0.0, 0.0
        stop_idx = 1                     # next stop index
        announced_600 = announced_300 = False
        overspeed_announced_at = -999
        congestion_done = False
        brake_done = False
        left_turn_done = False
        v_cruise = rng.uniform(self.CRUISE_MIN, self.CRUISE_MAX)

        while stop_idx < len(stops):
            target_pos = stops[stop_idx].distance
            dist_to_stop = target_pos - pos

            # -- speed control --------------------------------------
            if dist_to_stop <= 1.5:
                v = 0.0
            elif dist_to_stop < max(60.0, v * v / 3.6):
                # cap speed so the bus can actually stop at the stop line
                v = max(0.8, min(v, math.sqrt(max(0.0, 2 * 1.8 * (dist_to_stop - 1.5)))))
            elif dist_to_stop < 120:
                v = self._brake(v, 4.0, decel=1.2)
            else:
                v = self._accelerate(v, v_cruise)

            # subtle driver behaviour: slightly over the limit on one segment
            if self.OVERSPEED_SEGMENT[0] <= pos <= self.OVERSPEED_SEGMENT[1]:
                v = max(v, self.SPEED_LIMIT / 3.6 + 2.2)

            pos += v
            t += 1
            result.speeds.append(round(self._kmh(v), 1))

            # -- event rules ----------------------------------------
            speed_kmh = self._kmh(v)

            # proportional landmarks so any route length works (GTFS or demo)
            turn_at = stops[-1].distance * 0.35
            congestion_at = stops[-1].distance * 0.55
            brake_at = stops[-1].distance * 0.65

            if (not left_turn_done and turn_at <= pos <= turn_at + 50 and v > 3):
                result.events.append(Event(EventKind.TURN_LEFT, t=t, speed=speed_kmh))
                left_turn_done = True

            if (not congestion_done and congestion_at <= pos <= congestion_at + 60 and v > 3):
                result.events.append(Event(EventKind.CONGESTION, t=t, speed=speed_kmh,
                                           params={"delay": rng.randint(5, 12)}))
                congestion_done = True

            if (not brake_done and brake_at <= pos <= brake_at + 60 and v > 5):
                # a pedestrian crosses: hard braking for 2 seconds
                result.events.append(Event(EventKind.HARSH_BRAKE, t=t, speed=speed_kmh))
                brake_done = True
                v = max(2.0, v * 0.35)

            if (speed_kmh > self.SPEED_LIMIT + 1.5
                    and self.OVERSPEED_SEGMENT[0] <= pos
                    and t - overspeed_announced_at > 40):
                result.events.append(Event(EventKind.OVERSPEED, t=t, speed=round(speed_kmh),
                                           params={"speed": round(speed_kmh), "limit": self.SPEED_LIMIT}))
                overspeed_announced_at = t

            if not announced_600 and dist_to_stop <= 600:
                result.events.append(Event(EventKind.NEXT_STOP_600M, t=t, speed=speed_kmh,
                                           params={"stop": stops[stop_idx].name("en"),
                                                   "stop_zh": stops[stop_idx].name("zh")}))
                announced_600 = True
            if not announced_300 and dist_to_stop <= 300:
                result.events.append(Event(EventKind.NEXT_STOP_300M, t=t, speed=speed_kmh,
                                           params={"stop": stops[stop_idx].name("en"),
                                                   "stop_zh": stops[stop_idx].name("zh")}))
                announced_300 = True

            # -- dwelling at a stop ---------------------------------
            if dist_to_stop <= 1.5 and v < 0.5:
                result.events.append(Event(EventKind.ARRIVING, t=t, speed=0.0,
                                           params={"stop": stops[stop_idx].name("en"),
                                                   "stop_zh": stops[stop_idx].name("zh")}))
                result.events.append(Event(EventKind.DOORS_OPEN, t=t + 2, speed=0.0))
                t += self.DWELL_SECONDS
                result.speeds.extend([0.0] * self.DWELL_SECONDS)
                stop_idx += 1
                announced_600 = announced_300 = False
                v_cruise = rng.uniform(self.CRUISE_MIN, self.CRUISE_MAX)
                v = 0.0

        total_km = stops[-1].distance / 1000
        result.events.append(Event(EventKind.TRIP_SUMMARY, t=t, speed=0.0,
                                   params={"distance": total_km, "minutes": round(t / 60)}))
        result.total_distance = stops[-1].distance
        result.duration = t
        result.events.sort(key=lambda e: e.t)
        return result


class CarScenario(BaseScenario):
    """A private-car commute: turns, overspeed, congestion, fatigue."""

    kind = ScenarioKind.CAR
    line = "Commute Assist"
    destination_zh = "公司"
    destination_en = "Office"

    DURATION = 900            # 15 simulated minutes
    CRUISE = 16.0             # m/s (~58 km/h)
    URBAN_LIMIT = 60

    def run(self) -> TripResult:
        rng = self.rng
        result = TripResult(scenario=self.kind, line=self.line,
                            destination=self.destination_en)
        result.events.append(Event(EventKind.DEPARTURE, t=0.0, params={
            "line": self.line,
            "destination": self.destination_en,
            "destination_zh": self.destination_zh}))

        pos = v = 0.0
        done = set()
        v_urban = self.URBAN_LIMIT / 3.6 + 2.5      # slightly over the limit

        for t in range(1, self.DURATION + 1):
            phase = t / self.DURATION

            if phase < 0.15 or 0.45 <= phase < 0.6:
                v = self._accelerate(v, v_urban)             # urban slightly speeding
            elif 0.25 <= phase < 0.4:
                v = self._accelerate(v, self.CRUISE + 3.5)   # expressway overspeed
            elif 0.62 <= phase < 0.7:
                v = self._brake(v, 3.0, decel=1.6)           # congestion crawl
            else:
                v = self._accelerate(v, self.CRUISE)

            pos += v * 1.0
            speed_kmh = self._kmh(v)
            result.speeds.append(round(speed_kmh, 1))

            def once(kind):
                if kind not in done:
                    done.add(kind)
                    return True
                return False

            if t == 120 and once(EventKind.TURN_LEFT):
                result.events.append(Event(EventKind.TURN_LEFT, t=t, speed=speed_kmh))
            if t == 420 and once(EventKind.TURN_RIGHT):
                result.events.append(Event(EventKind.TURN_RIGHT, t=t, speed=speed_kmh))
            if t == 430 and once(EventKind.OVERSPEED):
                result.events.append(Event(EventKind.OVERSPEED, t=t, speed=round(speed_kmh),
                                           params={"speed": round(speed_kmh), "limit": 60}))
            if t == 450 and once(EventKind.CONGESTION):
                result.events.append(Event(EventKind.CONGESTION, t=t, speed=speed_kmh,
                                           params={"delay": rng.randint(6, 14)}))
            if t == 455 and once(EventKind.HARSH_BRAKE):
                result.events.append(Event(EventKind.HARSH_BRAKE, t=t, speed=speed_kmh))
            if t == 620 and once(EventKind.FATIGUE):
                result.events.append(Event(EventKind.FATIGUE, t=t, speed=speed_kmh,
                                           params={"minutes": round(t / 60)}))

        result.events.append(Event(EventKind.TRIP_SUMMARY, t=self.DURATION, speed=0.0,
                                   params={"distance": round(pos / 1000, 1),
                                           "minutes": self.DURATION // 60}))
        result.total_distance = pos
        result.duration = self.DURATION
        result.events.sort(key=lambda e: e.t)
        return result


def plot_timeline(result: TripResult, out_path: str) -> str:
    """Render a speed-profile figure with event markers (requires matplotlib)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=130)
    xs = list(range(1, len(result.speeds) + 1))
    ax.plot(xs, result.speeds, lw=1.6, color="#2b7bb9")
    ax.fill_between(xs, result.speeds, color="#2b7bb9", alpha=0.15)

    colors = {0: "#e05656", 1: "#e8912d", 2: "#3aa05a", 3: "#8a6ad0"}
    # de-clutter: at most one label per 8-s bucket, alternating heights
    top = max(result.speeds) * 1.03
    labeled_x = set()
    alt = 0
    for ev in result.events:
        bucket = int(ev.t // 8)
        if bucket in labeled_x:
            continue
        labeled_x.add(bucket)
        ax.axvline(ev.t, color=colors[int(ev.priority)], alpha=0.30, lw=1)
        y = top + (0.6 if alt % 2 == 0 else 4.2)
        alt += 1
        ax.annotate(ev.label.replace(" ", "\n"),
                    (ev.t, y), rotation=90, fontsize=5.6,
                    ha="right", va="top", color=colors[int(ev.priority)])

    ax.axhline(50, color="#e05656", ls="--", lw=0.9, alpha=0.6)
    ax.text(2, 51, "speed limit 50 km/h", fontsize=6.5, color="#e05656", alpha=0.8)

    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Speed (km/h)")
    ax.set_ylim(0, top + 12)
    ax.set_title(f"{result.line} — {result.duration:.0f}s simulated trip, "
                 f"{result.total_distance/1000:.1f} km")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path

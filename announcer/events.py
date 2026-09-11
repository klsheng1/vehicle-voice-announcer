# -*- coding: utf-8 -*-
"""Traffic event model with bilingual announcement templates.

Events are grouped into priority classes. Lower numeric value = more urgent.
The arbitration rules in :mod:`announcer.announcer` follow the same spirit as
in-vehicle HMI guidelines: safety-critical prompts always preempt navigation
and service information.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class Priority(IntEnum):
    """Announcement priority. Lower value preempts higher value."""

    SAFETY = 0      # overspeed, harsh braking, collision warning
    NAVIGATION = 1  # turns, lane guidance, next stop approaching
    SERVICE = 2     # arrival, door opening, delay info, departure greeting
    AMBIENT = 3     # weather, fatigue reminder, trip summary


class ScenarioKind:
    BUS = "bus"
    CAR = "car"


@dataclass(frozen=True)
class EventKind:
    """Registry of supported event kinds and their defaults."""

    DEPARTURE = "departure"
    NEXT_STOP_600M = "next_stop_600m"
    NEXT_STOP_300M = "next_stop_300m"
    ARRIVING = "arriving"
    ARRIVED = "arrived"
    DOORS_OPEN = "doors_open"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    OVERSPEED = "overspeed"
    HARSH_BRAKE = "harsh_brake"
    CONGESTION = "congestion"
    FATIGUE = "fatigue"
    TRIP_SUMMARY = "trip_summary"


# Default priority and cooldown (seconds) per event kind.
EVENT_POLICIES: dict[str, dict] = {
    EventKind.DEPARTURE:      {"priority": Priority.SERVICE,    "cooldown": 0},
    EventKind.NEXT_STOP_600M: {"priority": Priority.NAVIGATION, "cooldown": 60},
    EventKind.NEXT_STOP_300M: {"priority": Priority.NAVIGATION, "cooldown": 60},
    EventKind.ARRIVING:       {"priority": Priority.SERVICE,    "cooldown": 45},
    EventKind.ARRIVED:        {"priority": Priority.SERVICE,    "cooldown": 20},
    EventKind.DOORS_OPEN:     {"priority": Priority.SERVICE,    "cooldown": 15},
    EventKind.TURN_LEFT:      {"priority": Priority.NAVIGATION, "cooldown": 45},
    EventKind.TURN_RIGHT:     {"priority": Priority.NAVIGATION, "cooldown": 45},
    EventKind.OVERSPEED:      {"priority": Priority.SAFETY,     "cooldown": 30},
    EventKind.HARSH_BRAKE:    {"priority": Priority.SAFETY,     "cooldown": 30},
    EventKind.CONGESTION:     {"priority": Priority.SERVICE,    "cooldown": 120},
    EventKind.FATIGUE:        {"priority": Priority.AMBIENT,    "cooldown": 300},
    EventKind.TRIP_SUMMARY:   {"priority": Priority.AMBIENT,    "cooldown": 0},
}

# Bilingual message templates. ``{placeholders}`` are filled by the scenario.
# *_zh / *_en suffixed placeholders carry the same value in both languages.
TEMPLATES: dict[str, dict[str, str]] = {
    EventKind.DEPARTURE: {
        "zh": "欢迎体验{line}车载语音助手，本次目的地{destination_zh}，请系好安全带，我们出发啦。",
        "en": "Welcome aboard {line} to {destination}. Please fasten your seat belt. Here we go!",
    },
    EventKind.NEXT_STOP_600M: {
        "zh": "前方600米即将到达{stop_zh}，请要下车的乘客提前准备。",
        "en": "In 600 meters, next stop: {stop}. Please get ready to exit.",
    },
    EventKind.NEXT_STOP_300M: {
        "zh": "即将到站：{stop_zh}，下车的乘客请注意。",
        "en": "Approaching {stop}. Doors will open on the right.",
    },
    EventKind.ARRIVING: {
        "zh": "{stop_zh}到了，请从后门下车，注意脚下安全。",
        "en": "Now arriving at {stop}. Please exit through the rear door, mind your step.",
    },
    EventKind.ARRIVED: {
        "zh": "列车即将进站，请乘客站在黄色安全线内候车。",
        "en": "The bus is pulling in. Please wait behind the yellow line.",
    },
    EventKind.DOORS_OPEN: {
        "zh": "车门开启，请先下后上。",
        "en": "Doors opening. Please let passengers exit first.",
    },
    EventKind.TURN_LEFT: {
        "zh": "前方路口左转，请注意对向来车。",
        "en": "Turn left at the intersection ahead. Watch for oncoming traffic.",
    },
    EventKind.TURN_RIGHT: {
        "zh": "前方路口右转，请注意礼让行人。",
        "en": "Turn right ahead. Yield to pedestrians.",
    },
    EventKind.OVERSPEED: {
        "zh": "注意，当前车速{speed}公里每小时，已超过限速{limit}，请适当减速。",
        "en": "Attention: current speed {speed} kilometers per hour exceeds the {limit} limit. Please slow down.",
    },
    EventKind.HARSH_BRAKE: {
        "zh": "车辆急刹，请乘客扶稳坐好，注意后方来车。",
        "en": "Hard braking detected. Please hold on, and check the vehicle behind us.",
    },
    EventKind.CONGESTION: {
        "zh": "前方一公里交通拥堵，预计延误{delay}分钟，已为您规划备用路线。",
        "en": "Congestion ahead in one kilometer, expected delay {delay} minutes. An alternative route is ready.",
    },
    EventKind.FATIGUE: {
        "zh": "您已连续驾驶{minutes}分钟，请注意休息，安全驾驶。",
        "en": "You have been driving for {minutes} minutes. Please consider taking a break. Drive safe.",
    },
    EventKind.TRIP_SUMMARY: {
        "zh": "本次行程结束，全程{distance}公里，用时{minutes}分钟，感谢乘坐，再见！",
        "en": "Trip finished. {distance} kilometers in {minutes} minutes. Thank you for riding, goodbye!",
    },
}


@dataclass
class Event:
    """A traffic event that may trigger a voice announcement."""

    kind: str
    t: float                                  # simulation time in seconds
    speed: float = 0.0                        # vehicle speed, km/h
    params: dict = field(default_factory=dict)
    priority: Optional[Priority] = None       # defaults from EVENT_POLICIES
    cooldown: Optional[float] = None

    def __post_init__(self):
        policy = EVENT_POLICIES[self.kind]
        if self.priority is None:
            self.priority = policy["priority"]
        if self.cooldown is None:
            self.cooldown = policy["cooldown"]

    def text(self, lang: str = "zh") -> str:
        template = TEMPLATES[self.kind][lang]
        return template.format(**self.params) if self.params else template

    @property
    def label(self) -> str:
        return self.kind.upper().replace("_", " ")

"""Bilingual prompt templates for every event kind."""

from __future__ import annotations

from .events import Event

TEMPLATES: dict[str, dict[str, str]] = {
    "zh": {
        "departure": "车辆起步，请扶稳坐好。",
        "next_stop": "下一站：{stop}。",
        "red_light": "前方红灯，预计等待{seconds}秒，请耐心等候。",
        "sharp_turn": "前方急转弯，请减速慢行。",
        "school_zone": "已进入学校区域，注意儿童，减速慢行。",
        "speeding": "当前车速超过限速，请减速行驶。",
        "rain": "检测到降雨，请开启雨刮，保持安全车距。",
        "congestion": "前方路段拥堵，预计通行时间{minutes}分钟。",
        "blind_spot": "注意，右后方有非机动车接近，请避让。",
        "arriving": "前方到站：{stop}，请准备从后门下车。",
        "arrival": "{stop}到了，请带好随身物品下车。",
        "trip_end": "本次行程结束，感谢乘坐。",
    },
    "en": {
        "departure": "Departing now. Please hold on.",
        "next_stop": "Next stop: {stop}.",
        "red_light": "Red light ahead, about {seconds} seconds.",
        "sharp_turn": "Sharp turn ahead, please slow down.",
        "school_zone": "Entering a school zone. Watch for children.",
        "speeding": "You are above the speed limit. Please slow down.",
        "rain": "Rain detected. Keep a safe following distance.",
        "congestion": "Congestion ahead, about {minutes} minutes of delay.",
        "blind_spot": "Cyclist approaching on the right. Please yield.",
        "arriving": "Now approaching {stop}. Rear door exit.",
        "arrival": "{stop}. Please take your belongings.",
        "trip_end": "End of the line. Thank you for riding.",
    },
}


def render(event: Event, lang: str = "zh") -> str:
    try:
        template = TEMPLATES[lang][event.kind]
    except KeyError:
        raise KeyError(
            f"No {lang} prompt template for event kind {event.kind!r}"
        ) from None
    return template.format(**event.params)

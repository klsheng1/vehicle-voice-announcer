"""Unit tests for dispatcher and prompts (no audio, no network)."""

import pytest

from announcer.dispatcher import Dispatcher
from announcer.events import Event, Priority
from announcer.prompts import render


def ev(kind, t, priority=Priority.NAVIGATION, key=None, **params):
    return Event(kind=kind, t_sim=t, priority=priority, params=params, cooldown_key=key)


def test_first_event_announces_and_repeats_are_suppressed():
    d = Dispatcher(cooldown_s=20.0)
    assert d.submit(ev("speeding", 10, Priority.SAFETY)).action == "announce"
    again = d.submit(ev("speeding", 25, Priority.SAFETY))
    assert again.action == "suppress"
    assert "15s ago" in again.reason


def test_cooldown_expires():
    d = Dispatcher(cooldown_s=20.0)
    d.submit(ev("speeding", 10, Priority.SAFETY))
    later = d.submit(ev("speeding", 45, Priority.SAFETY))
    assert later.action in ("announce", "preempt", "queued")


def test_higher_priority_preempts_and_drops_queue():
    d = Dispatcher(cooldown_s=20.0)
    first = ev("congestion", 150, Priority.NAVIGATION, minutes=6)
    assert d.submit(first).action == "announce"
    second = ev("next_stop", 152, Priority.NAVIGATION, stop="X")
    assert d.submit(second).action == "queued"

    safety = ev("blind_spot", 153, Priority.SAFETY)
    decision = d.submit(safety)
    assert decision.action == "preempt"
    assert decision.displaced is first
    assert d._queue == []                      # stale lower-priority drops

    assert d.finish_current() is None          # safety message is current now


def test_queue_is_fifo_and_finish_current_advances():
    d = Dispatcher(cooldown_s=20.0)
    assert d.submit(ev("next_stop", 0, Priority.NAVIGATION, stop="Start",
                       key="ns")).action == "announce"
    a = ev("red_light", 1, Priority.NAVIGATION)
    b = ev("arrival", 2, Priority.NAVIGATION, stop="B")
    assert d.submit(a).action == "queued"
    assert d.submit(b).action == "queued"
    assert d.finish_current() is a
    assert d.finish_current() is b
    assert d.finish_current() is None


def test_different_cooldown_groups_do_not_cross_suppress():
    d = Dispatcher(cooldown_s=20.0)
    assert d.submit(ev("red_light", 10)).action == "announce"
    assert d.submit(ev("next_stop", 12, stop="X")).action in ("queued", "announce")


def test_prompt_rendering_zh_and_en():
    e = ev("arriving", 0, stop="人民广场")
    assert render(e, "zh") == "前方到站：人民广场，请准备从后门下车。"
    assert render(e, "en") == "Now approaching 人民广场. Rear door exit."
    with pytest.raises(KeyError):
        render(ev("unknown_kind", 0))

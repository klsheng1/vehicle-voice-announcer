# -*- coding: utf-8 -*-
"""Command-line entry points.

Examples::

    python -m announcer.cli simulate --scenario bus --engine auto --speedup 60
    python -m announcer.cli simulate --scenario car --lang en --engine sapi
    python -m announcer.cli generate-samples --outdir assets/audio
    python -m announcer.cli plot --scenario bus --out docs/trip-timeline.png
"""
from __future__ import annotations

import argparse
import os
import sys

from .announcer import VoiceAnnouncer
from .events import EVENT_POLICIES
from .scenario import BusScenario, CarScenario, plot_timeline
from .tts import create_engine


def _build_scenario(name: str, seed):
    cls = BusScenario if name == "bus" else CarScenario
    return cls(seed=seed)


def cmd_simulate(args) -> int:
    scenario = _build_scenario(args.scenario, args.seed)
    engine = create_engine(args.engine, lang=args.lang, voice=args.voice,
                           quiet=args.quiet)
    announcer = VoiceAnnouncer(engine, lang=args.lang, speedup=args.speedup,
                               quiet=args.quiet)
    result = announcer.run_scenario(scenario, hold=args.hold)
    if not args.quiet:
        print("-" * 62)
        print(f"scenario={args.scenario}  events={len(result.events)}  "
              f"distance={result.total_distance/1000:.1f} km  "
              f"duration={result.duration:.0f}s (sim)")
    engine.close()
    if args.hold:
        input("Press Enter to exit...")
    return 0


def cmd_generate_samples(args) -> int:
    """Render one wav per event kind — committed to assets/audio for the README."""
    from .events import TEMPLATES
    engine = create_engine(args.engine, lang=args.lang, voice=args.voice,
                           quiet=args.quiet)
    os.makedirs(args.outdir, exist_ok=True)
    order = ["departure", "next_stop_600m", "arriving", "turn_left",
             "overspeed", "harsh_brake", "congestion", "fatigue", "trip_summary"]
    params = {
        "line": "Demo Line 1", "destination": "Tech Park", "destination_zh": "科技园站",
        "stop": "People's Square", "stop_zh": "人民广场",
        "speed": 62, "limit": 50, "delay": 8, "minutes": 14, "distance": 8.6,
    }
    index = 0
    for kind in order:
        if kind not in TEMPLATES:
            continue
        index += 1
        text = TEMPLATES[kind][args.lang]
        try:
            text = text.format(**params)
        except KeyError:
            pass
        name = f"{index:02d}_{kind.lower()}.wav"
        path = os.path.join(args.outdir, name)
        engine.synthesize_to_file(text, path)
        print(f"  {name}  <-  {text}")
    engine.close()
    print(f"done: {index} audio files in {args.outdir}")
    return 0


def cmd_plot(args) -> int:
    scenario = _build_scenario(args.scenario, args.seed)
    result = scenario.run()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    out = plot_timeline(result, args.out)
    print(f"timeline written to {out}")
    return 0


def cmd_list_events(_args) -> int:
    for kind, policy in EVENT_POLICIES.items():
        zh = __import__("announcer.events", fromlist=["TEMPLATES"]).TEMPLATES[kind]["zh"]
        print(f"{kind:<15} priority={policy['priority'].name:<9} cooldown={policy['cooldown']:>3}s   {zh}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="announcer", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sim = sub.add_parser("simulate", help="run a traffic scenario with voice announcements")
    p_sim.add_argument("--scenario", choices=["bus", "car"], default="bus")
    p_sim.add_argument("--lang", choices=["zh", "en"], default="zh")
    p_sim.add_argument("--engine", choices=["auto", "indextts", "sapi", "silent"], default="auto")
    p_sim.add_argument("--voice", default=None, help="voice hint / IndexTTS reference wav")
    p_sim.add_argument("--speedup", type=float, default=30.0,
                       help="simulate N sim-seconds per wall second (default 30)")
    p_sim.add_argument("--seed", type=int, default=42)
    p_sim.add_argument("--hold", type=float, default=0.0,
                       help="extra seconds to keep playing after the last event")
    p_sim.add_argument("--quiet", action="store_true")
    p_sim.set_defaults(func=cmd_simulate)

    p_gen = sub.add_parser("generate-samples", help="render announcement samples to wav files")
    p_gen.add_argument("--lang", choices=["zh", "en"], default="zh")
    p_gen.add_argument("--engine", choices=["auto", "indextts", "sapi", "silent"], default="sapi")
    p_gen.add_argument("--voice", default=None)
    p_gen.add_argument("--outdir", default=os.path.join("assets", "audio"))
    p_gen.add_argument("--quiet", action="store_true")
    p_gen.set_defaults(func=cmd_generate_samples)

    p_plot = sub.add_parser("plot", help="render the speed profile with event markers")
    p_plot.add_argument("--scenario", choices=["bus", "car"], default="bus")
    p_plot.add_argument("--seed", type=int, default=42)
    p_plot.add_argument("--out", default=os.path.join("docs", "trip-timeline.png"))
    p_plot.set_defaults(func=cmd_plot)

    sub.add_parser("list-events", help="show event kinds, priorities and templates").set_defaults(
        func=cmd_list_events)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

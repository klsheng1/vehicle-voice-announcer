"""Run the simulated drive and speak (or log) every announcement.

Examples:
    python -m announcer.cli                          # auto backend, zh prompts
    python -m announcer.cli --backend edge --lang en
    python -m announcer.cli --no-audio               # decisions only, no TTS
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .dispatcher import Dispatcher
from .events import Event, Priority
from .figures import drive_timeline, spectrogram
from .prompts import render
from .sim import build_drive
from .tts import get_backend

ACTION_STYLE = {
    "ANNOUNCE": ("\033[32m", "ANNOUNCE"),
    "PREEMPT": ("\033[1;31m", "PREEMPT"),
    "SUPPRESS": ("\033[33m", "SUPPRESS"),
    "QUEUED": ("\033[36m", "QUEUED"),
}
RESET = "\033[0m"
EXT_BY_BACKEND = {"edge": ".mp3", "sapi": ".wav", "index-tts": ".wav"}

PRIORITY_TAG = {Priority.INFO: "INFO ", Priority.NAVIGATION: "NAV  ",
                Priority.SAFETY: "SAFE "}


def _clock(t: float) -> str:
    return f"{int(t) // 60:02d}:{int(t) % 60:02d}"


def _est_duration(text: str) -> float:
    """Rough spoken length (s): Mandarin chars ~4.5/s, latin ~14/s."""
    cjk = sum(1 for ch in text if ord(ch) > 0x2E80)
    return 1.2 + cjk / 4.5 + (len(text) - cjk) / 14.0


def run(backend_choice: str = "auto", lang: str = "zh", voice: str | None = None,
        outdir: Path = Path("output"), figdir: Path | None = None,
        cooldown_s: float = 20.0, no_audio: bool = False) -> list[dict]:
    if os.name == "nt":
        os.system("")  # enable ANSI escape codes on Windows terminals
    outdir.mkdir(parents=True, exist_ok=True)

    backend = None
    ext = ".wav"
    if not no_audio:
        backend = get_backend(backend_choice, cache_dir=outdir / ".tts_cache", voice=voice)
        ext = EXT_BY_BACKEND.get(backend.name, ".wav")
        print(f"TTS backend: {backend.name}")

    events, t, speed, limit = build_drive()
    dispatcher = Dispatcher(cooldown_s=cooldown_s)
    transcript: list[str] = []
    announced: list[dict] = []
    current_finish = -1.0
    file_idx = 1

    def speak(event: Event, deferred: bool = False) -> None:
        nonlocal file_idx, current_finish
        text = render(event, lang)
        suffix = "  [deferred from queue]" if deferred else ""
        line = (f"[{_clock(event.t_sim)}] {PRIORITY_TAG[event.priority]} "
                f"{event.kind:<12} ANNOUNCE  {text}{suffix}")
        transcript.append(line)
        color = ACTION_STYLE["ANNOUNCE"][0]
        print(f"{color}{line}{RESET}")
        audio_path = None
        if backend is not None:
            audio_path = outdir / f"{file_idx:02d}_{event.kind}{ext}"
            backend.synth(text, audio_path)
            file_idx += 1
        announced.append({"event": event, "text": text, "file": audio_path})
        current_finish = event.t_sim + _est_duration(text)

    def log_decision(d) -> None:
        text = render(d.event, lang)
        tag = PRIORITY_TAG[d.event.priority]
        if d.action == "suppress":
            line = (f"[{_clock(d.event.t_sim)}] {tag} {d.event.kind:<12} "
                    f"SUPPRESS  ({d.reason}) {text}")
            color = ACTION_STYLE["SUPPRESS"][0]
        elif d.action == "preempt":
            line = (f"[{_clock(d.event.t_sim)}] {tag} {d.event.kind:<12} "
                    f"PREEMPT   (cancels {d.displaced.kind!r}: {d.reason}) {text}")
            color = ACTION_STYLE["PREEMPT"][0]
        else:
            line = (f"[{_clock(d.event.t_sim)}] {tag} {d.event.kind:<12} "
                    f"QUEUED    {text}")
            color = ACTION_STYLE["QUEUED"][0]
        transcript.append(line)
        print(f"{color}{line}{RESET}")

    for event in events:
        # Let queued messages start once the current one would have finished.
        while current_finish >= 0 and event.t_sim >= current_finish:
            nxt = dispatcher.finish_current()
            if nxt is None:
                current_finish = -1.0
                break
            speak(nxt, deferred=True)
        decision = dispatcher.submit(event)
        if decision.action == "announce" or decision.action == "preempt":
            if decision.action == "preempt":
                log_decision(decision)
                current_finish = -1.0
            speak(decision.event)
        else:
            log_decision(decision)

    (outdir / "transcript.txt").write_text("\n".join(transcript) + "\n",
                                           encoding="utf-8")
    print(f"\nTranscript written to {outdir / 'transcript.txt'}")

    if figdir is not None:
        timeline = drive_timeline(t, speed, limit, announced,
                                  Path(figdir) / "drive_timeline.png")
        print(f"Timeline figure -> {timeline}")
        first_audio = next((a["file"] for a in announced if a["file"]), None)
        if first_audio is not None:
            spec = spectrogram(first_audio, Path(figdir) / "spectrogram.png")
            print(f"Spectrogram -> {spec}")
    return announced


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", default="auto",
                        choices=["auto", "index-tts", "edge", "sapi"])
    parser.add_argument("--lang", default="zh", choices=["zh", "en"])
    parser.add_argument("--voice", help="edge-tts voice name or IndexTTS speaker wav")
    parser.add_argument("--outdir", type=Path, default=Path("output"))
    parser.add_argument("--figdir", type=Path, default=Path("docs/images"),
                        help="write timeline/spectrogram figures here (skip: --no-figure)")
    parser.add_argument("--no-figure", action="store_true")
    parser.add_argument("--no-audio", action="store_true",
                        help="log decisions only; skip TTS entirely")
    parser.add_argument("--cooldown", type=float, default=20.0,
                        help="dispatcher cooldown seconds (default 20)")
    args = parser.parse_args()

    run(backend_choice=args.backend, lang=args.lang, voice=args.voice,
        outdir=args.outdir, figdir=None if args.no_figure else args.figdir,
        cooldown_s=args.cooldown, no_audio=args.no_audio)


if __name__ == "__main__":
    main()

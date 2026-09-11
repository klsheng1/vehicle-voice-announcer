# -*- coding: utf-8 -*-
"""No-audio engine: logs only. Used for CI, tests and quick logic checks."""
from __future__ import annotations

from .base import BaseEngine


class SilentEngine(BaseEngine):
    name = "silent"

    def __init__(self, lang: str = "zh", voice: str | None = None, hook=None):
        super().__init__(lang, voice)
        self.spoken: list[str] = []
        self._hook = hook

    def speak(self, text: str) -> None:
        self.spoken.append(text)
        if self._hook:
            self._hook(text)

    def stop(self) -> None:  # nothing playing
        pass

    def synthesize_to_file(self, text: str, path: str) -> str:
        self.spoken.append(text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"[silent] {text}\n")
        return path

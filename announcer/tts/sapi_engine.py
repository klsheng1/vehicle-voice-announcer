# -*- coding: utf-8 -*-
"""Windows SAPI5 fallback engine via pyttsx3.

Works fully offline on Windows out of the box, which keeps the demo runnable
even before the (multi-GB) IndexTTS checkpoints are downloaded.
"""
from __future__ import annotations

import os

from .base import BaseEngine, EngineUnavailable

_ZH_VOICE_HINTS = ("huihui", "yaoyao", "tingting", "kangkang", "zh-cn", "chinese")
_EN_VOICE_HINTS = ("zira", "david", "en-us", "english")


class SapiEngine(BaseEngine):
    name = "sapi"

    def __init__(self, lang: str = "zh", voice: str | None = None):
        super().__init__(lang, voice)
        try:
            import pyttsx3
        except Exception as exc:  # pragma: no cover
            raise EngineUnavailable(
                "pyttsx3 is not installed. Run: pip install pyttsx3") from exc
        self._pyttsx3 = pyttsx3
        self._engine = None

    # ------------------------------------------------------------------
    def _tune(self, engine, rate: int | None = None) -> None:
        """Apply language-appropriate rate and voice hints to an engine."""
        engine.setProperty("rate", rate if rate else
                           (175 if self.lang.startswith("zh") else 165))
        hints = _ZH_VOICE_HINTS if self.lang.startswith("zh") else _EN_VOICE_HINTS
        for v in engine.getProperty("voices"):
            name = (v.name or "").lower()
            vid = (v.id or "").lower()
            if self.voice and self.voice.lower() in name:
                engine.setProperty("voice", v.id)
                return
            if any(h in name or h in vid for h in hints):
                engine.setProperty("voice", v.id)
                return

    def _engine_obj(self) -> "pyttsx3.Engine":
        if self._engine is None:
            self._engine = self._pyttsx3.init()
            self._tune(self._engine)
        return self._engine

    # ------------------------------------------------------------------
    def speak(self, text: str) -> None:
        engine = self._engine_obj()
        engine.say(text)
        engine.runAndWait()

    def stop(self) -> None:
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

    def synthesize_to_file(self, text: str, path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        # A fresh engine per file avoids the pyttsx3 runAndWait re-entry hang
        # that appears when saving many files on one shared instance.
        engine = self._pyttsx3.init()
        self._tune(engine)
        try:
            engine.save_to_file(text, path)
            engine.runAndWait()
        finally:
            try:
                engine.stop()
            except Exception:
                pass
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            raise EngineUnavailable(f"SAPI did not produce {path}")
        return path

    def close(self):
        self.stop()
        self._engine = None

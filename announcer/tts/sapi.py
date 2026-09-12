"""Offline fallback via Windows SAPI 5 (pyttsx3). No network needed."""

from __future__ import annotations

from pathlib import Path

from .base import TTSBackend


class SapiBackend(TTSBackend):
    name = "sapi"

    def available(self) -> bool:
        try:
            import pyttsx3  # noqa: F401
            return True
        except ImportError:
            return False

    def _synth(self, text: str, out_path: Path, voice: str | None) -> Path:
        import pyttsx3

        engine = pyttsx3.init()
        if voice:
            engine.setProperty("voice", voice)
        if out_path.suffix.lower() != ".wav":
            out_path = out_path.with_suffix(".wav")
        engine.save_to_file(text, str(out_path))
        engine.runAndWait()
        return out_path

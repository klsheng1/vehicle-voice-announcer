# -*- coding: utf-8 -*-
"""TTS engine factory.

``auto`` resolves to the best available backend:

1. IndexTTS2 (zero-shot voice cloning, needs checkpoints) — see README
2. Windows SAPI via pyttsx3 (offline fallback)
3. Silent engine (no audio; CI / tests)
"""
from __future__ import annotations

from .base import BaseEngine, EngineUnavailable

__all__ = ["BaseEngine", "EngineUnavailable", "create_engine", "AVAILABLE"]

AVAILABLE: list[str] = ["sapi", "silent"]

try:  # probe without importing heavy modules
    import importlib.util as _ilu
    if _ilu.find_spec("indextts") is not None:
        AVAILABLE.insert(0, "indextts")
except Exception:  # pragma: no cover
    pass


def create_engine(kind: str = "auto", lang: str = "zh", voice: str | None = None,
                  quiet: bool = False, log=print) -> BaseEngine:
    """Create a TTS engine by kind: auto | indextts | sapi | silent."""
    if kind == "silent":
        from .silent_engine import SilentEngine
        return SilentEngine(lang, voice)
    if kind in ("auto", "indextts"):
        try:
            from .indextts_engine import IndexTTSEngine
            engine = IndexTTSEngine(lang=lang, voice=voice)
            if not quiet:
                log(f"[engine] IndexTTS2 ready (voice cloning from {engine.ref_voice})")
            return engine
        except Exception as exc:
            if kind == "indextts":
                raise
            if not quiet:
                log(f"[engine] IndexTTS unavailable ({exc}); falling back to SAPI")
    if kind in ("auto", "sapi"):
        try:
            from .sapi_engine import SapiEngine
            engine = SapiEngine(lang=lang, voice=voice)
            if not quiet:
                log("[engine] Windows SAPI fallback engine ready")
            return engine
        except Exception as exc:
            if kind == "sapi":
                raise
            if not quiet:
                log(f"[engine] SAPI unavailable ({exc}); using silent engine")
    from .silent_engine import SilentEngine
    return SilentEngine(lang, voice)

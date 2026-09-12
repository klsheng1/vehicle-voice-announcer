"""Backend registry and auto-selection chain.

``auto`` resolves to the best backend that is actually usable on this
machine: IndexTTS 2 (voice cloning) -> edge-tts (neural, needs network)
-> Windows SAPI (offline, robotic).
"""

from __future__ import annotations

from pathlib import Path

from .base import TTSBackend
from .edge import EdgeTTSBackend
from .index_tts import IndexTTSBackend
from .sapi import SapiBackend

__all__ = ["TTSBackend", "IndexTTSBackend", "EdgeTTSBackend", "SapiBackend", "get_backend"]

_CHAIN = [IndexTTSBackend, EdgeTTSBackend, SapiBackend]


def get_backend(choice: str = "auto", cache_dir: Path | None = None,
                voice: str | None = None) -> TTSBackend:
    cache_dir = Path(cache_dir or "output/.tts_cache")

    def make(cls, **kw) -> TTSBackend:
        return cls(cache_dir=cache_dir, **kw)

    if choice == "auto":
        for cls in _CHAIN:
            backend = make(cls)
            if backend.available():
                return backend
        raise RuntimeError(
            "No TTS backend available. `pip install edge-tts` (network) or "
            "`pip install pyttsx3` (Windows offline), or set up IndexTTS — "
            "see announcer/tts/index_tts.py."
        )

    mapping = {"index-tts": IndexTTSBackend, "edge": EdgeTTSBackend, "sapi": SapiBackend}
    try:
        cls = mapping[choice]
    except KeyError:
        raise ValueError(f"Unknown backend {choice!r}; choose from "
                         f"{['auto', *mapping]}") from None
    kwargs = {"voice": voice} if voice and choice == "edge" else {}
    backend = make(cls, **kwargs)
    if not backend.available():
        raise RuntimeError(f"Backend {choice!r} is not available on this machine.")
    return backend

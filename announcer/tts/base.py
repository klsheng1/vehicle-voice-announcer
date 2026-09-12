"""TTS backend interface + shared caching."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path


class TTSBackend(ABC):
    """A backend turns one announcement into an audio file.

    Subclasses must set ``name`` and implement :meth:`_synth`. Results are
    cached by (backend, voice, text) so repeated prompts are free.
    """

    name: str = "base"

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def synth(self, text: str, out_path: Path, voice: str | None = None) -> Path:
        digest = hashlib.sha1(f"{self.name}|{voice}|{text}".encode()).hexdigest()[:12]
        cached = self.cache_dir / f"{digest}{out_path.suffix}"
        if cached.exists():
            return cached
        result = self._synth(text, Path(out_path), voice)
        return result if result is not None else Path(out_path)

    @abstractmethod
    def _synth(self, text: str, out_path: Path, voice: str | None) -> Path | None:
        ...

    @abstractmethod
    def available(self) -> bool:
        ...

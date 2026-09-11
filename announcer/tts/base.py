# -*- coding: utf-8 -*-
"""Abstract TTS engine interface shared by all backends."""
from __future__ import annotations

import abc


class EngineUnavailable(RuntimeError):
    """Raised when a TTS backend cannot be initialised (missing deps/models)."""


class BaseEngine(abc.ABC):
    """Minimal contract required by :class:`announcer.announcer.VoiceAnnouncer`."""

    name: str = "base"

    def __init__(self, lang: str = "zh", voice: str | None = None):
        self.lang = lang
        self.voice = voice

    @abc.abstractmethod
    def speak(self, text: str) -> None:
        """Speak ``text`` aloud (blocking)."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Abort current playback as soon as possible (best effort)."""

    @abc.abstractmethod
    def synthesize_to_file(self, text: str, path: str) -> str:
        """Render ``text`` to an audio file and return the path."""

    def close(self) -> None:  # noqa: B027 - optional hook
        """Release resources. Default: nothing to do."""

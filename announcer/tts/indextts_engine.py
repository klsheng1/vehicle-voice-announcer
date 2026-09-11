# -*- coding: utf-8 -*-
"""IndexTTS2 engine wrapper (zero-shot voice-cloning TTS by Bilibili).

This backend is *optional*: it requires the ``indextts`` package and its
multi-GB checkpoints. Install with::

    pip install -r requirements-indextts.txt
    # clone https://github.com/index-tts/index-tts and download checkpoints
    # from HuggingFace (IndexTeam/IndexTTS-2) or ModelScope, then set:
    #   INDEXTTS_CKPT_DIR / INDEXTTS_CONFIG / INDEXTTS_REF_VOICE

If anything is missing, :class:`EngineUnavailable` is raised and the factory
falls back to the SAPI engine, so the demo always runs.
"""
from __future__ import annotations

import os
import tempfile

from .base import BaseEngine, EngineUnavailable


class IndexTTSEngine(BaseEngine):
    name = "indextts"

    def __init__(self, lang: str = "zh", voice: str | None = None,
                 ckpt_dir: str | None = None, config: str | None = None,
                 use_fp16: bool = True):
        super().__init__(lang, voice)
        self.ckpt_dir = ckpt_dir or os.environ.get("INDEXTTS_CKPT_DIR", "checkpoints")
        self.config = config or os.environ.get(
            "INDEXTTS_CONFIG", os.path.join(self.ckpt_dir, "config.yaml"))
        self.ref_voice = voice or os.environ.get(
            "INDEXTTS_REF_VOICE", os.path.join("assets", "voices", "ref.wav"))
        if not os.path.isdir(self.ckpt_dir):
            raise EngineUnavailable(
                f"IndexTTS checkpoints not found at '{self.ckpt_dir}'. "
                "See README 'Enable IndexTTS' section.")
        try:
            from indextts.infer_v2 import IndexTTS2  # noqa: WPS433 - lazy import
        except Exception as exc:
            raise EngineUnavailable(
                "indextts package unavailable. pip install -r requirements-indextts.txt") from exc
        self._tts = IndexTTS2(cfg_path=self.config, use_fp16=use_fp16)

    # ------------------------------------------------------------------
    def synthesize_to_file(self, text: str, path: str) -> str:
        if not os.path.exists(self.ref_voice):
            raise EngineUnavailable(
                f"reference voice not found: {self.ref_voice} "
                "(drop any 3-10s clean speech clip there)")
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        self._tts.infer(
            spk_audio_prompt=self.ref_voice,
            text=text,
            output_path=path,
        )
        return path

    def speak(self, text: str) -> None:
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            self.synthesize_to_file(text, tmp)
            self._play_wav(tmp)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    @staticmethod
    def _play_wav(path: str) -> None:
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME)  # blocking
        except ImportError:  # non-Windows dev box: no playback, synthesis only
            import time
            time.sleep(min(3.0, os.path.getsize(path) / 64000.0))

    def stop(self) -> None:
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)  # abort playback
        except Exception:
            pass

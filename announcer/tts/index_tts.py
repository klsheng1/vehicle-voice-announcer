"""IndexTTS 2 backend — zero-shot voice-cloning TTS from Bilibili.

This is the primary backend: it renders every announcement in a *cloned*
driver voice from a few seconds of reference audio.

One-time setup (GPU strongly recommended, ~6 GB VRAM for fp16):

    git clone https://github.com/index-tts/index-tts
    cd index-tts
    uv sync                                    # or: pip install -e .
    hf download IndexTeam/IndexTTS-2 --local-dir checkpoints

Then point this backend at the checkout:

    set INDEX_TTS_REPO=C:/path/to/index-tts
    set INDEX_TTS_VOICE=C:/path/to/speaker.wav
    python -m announcer.cli --backend index-tts

The backend first tries the Python API (``indextts.infer_v2.IndexTTS2``) and
falls back to the repo's ``indextts`` CLI. ``available()`` reports honestly
whether either path exists on this machine.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .base import TTSBackend


class IndexTTSBackend(TTSBackend):
    name = "index-tts"

    def __init__(self, cache_dir: Path, repo_dir: str | None = None,
                 voice_wav: str | None = None, device: str | None = None):
        super().__init__(cache_dir)
        self.repo_dir = Path(repo_dir or os.environ.get("INDEX_TTS_REPO", "") or
                             "third_party/index-tts")
        self.voice_wav = voice_wav or os.environ.get("INDEX_TTS_VOICE")
        self.device = device or os.environ.get("INDEX_TTS_DEVICE")
        self._model = None

    def available(self) -> bool:
        if (self.repo_dir / "indextts").is_dir():
            return True
        try:
            import indextts  # noqa: F401
            return True
        except ImportError:
            return False

    def _load_model(self):
        if self._model is not None:
            return self._model
        sys.path.insert(0, str(self.repo_dir))
        try:
            from indextts.infer_v2 import IndexTTS2
        except ImportError as exc:  # pragma: no cover - needs the real repo
            raise RuntimeError(
                f"IndexTTS not importable. Clone https://github.com/index-tts/index-tts "
                f"and set INDEX_TTS_REPO to the checkout (see module docstring). "
                f"Original error: {exc}"
            ) from exc
        kwargs = {"cfg_path": str(self.repo_dir / "checkpoints" / "config.yaml"),
                  "model_dir": str(self.repo_dir / "checkpoints")}
        if self.device:
            kwargs["device"] = self.device
        self._model = IndexTTS2(**kwargs)
        return self._model

    def _synth(self, text: str, out_path: Path, voice: str | None) -> Path:
        speaker = voice or self.voice_wav
        try:
            tts = self._load_model()
            tts.infer(spk_audio_prompt=speaker, text=text, output_path=str(out_path))
            return out_path
        except ImportError:
            return self._synth_cli(text, out_path, speaker)

    def _synth_cli(self, text: str, out_path: Path, speaker: str | None) -> Path:
        cmd = ["uv", "run", "indextts", text, "--output", str(out_path)]
        if speaker:
            cmd += ["--voice", speaker]
        if shutil.which("uv") is None:
            raise RuntimeError("Neither the indextts package nor the `uv` CLI is "
                               "available — see index_tts.py setup instructions.")
        subprocess.run(cmd, cwd=self.repo_dir, check=True)
        return out_path

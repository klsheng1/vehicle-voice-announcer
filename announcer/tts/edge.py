"""edge-tts backend — Microsoft neural voices over the network.

Small, fast and sounds natural; needs internet access. Default voice is a
Mandarin one because the demo prompts are bilingual (zh first).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from .base import TTSBackend


class EdgeTTSBackend(TTSBackend):
    name = "edge"

    def __init__(self, cache_dir: Path, voice: str = "zh-CN-XiaoxiaoNeural"):
        super().__init__(cache_dir)
        self.voice = voice

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def _synth(self, text: str, out_path: Path, voice: str | None) -> Path:
        import edge_tts

        voice = voice or self.voice

        async def run() -> None:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(out_path))

        asyncio.run(run())
        return out_path

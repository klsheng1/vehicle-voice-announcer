"""Evaluation/demo figures: drive timeline and announcement spectrogram."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .events import Priority

PRIORITY_COLORS = {
    Priority.INFO: "#718096",
    Priority.NAVIGATION: "#2b6cb0",
    Priority.SAFETY: "#c53030",
}


def drive_timeline(t: np.ndarray, speed: np.ndarray, limit: np.ndarray,
                   announced: list, out_path: Path) -> Path:
    """Speed trace with the limit, plus markers for every announced event."""
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.fill_between(t, 0, speed, step=None, alpha=0.15, color="#2b6cb0")
    ax.plot(t, speed, color="#2b6cb0", linewidth=1.8, label="vehicle speed")
    ax.plot(t, limit, color="#dd6b20", linewidth=1.4, linestyle="--", label="speed limit")

    ymin, ymax = -4, max(speed.max(), limit.max()) + 12
    for item in announced:
        color = PRIORITY_COLORS[item["event"].priority]
        ax.axvline(item["event"].t_sim, color=color, alpha=0.35, linewidth=1.0)
        ax.plot(item["event"].t_sim, ymax - 3, marker="v", color=color, markersize=6)

    handles = [plt.Line2D([], [], color=c, marker="v", linestyle="", markersize=6,
                          label=f"{p.name} announcement")
               for p, c in PRIORITY_COLORS.items()]
    handles += [plt.Line2D([], [], color="#2b6cb0", label="vehicle speed"),
                plt.Line2D([], [], color="#dd6b20", linestyle="--", label="speed limit")]
    ax.legend(handles=handles, fontsize=8, loc="upper right")
    ax.set_ylim(ymin, ymax)
    ax.set_xlabel("simulated time (s)")
    ax.set_ylabel("speed (km/h)")
    ax.set_title("Simulated urban drive — announced events vs. vehicle dynamics")
    ax.grid(alpha=0.25)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def spectrogram(audio_path: Path, out_path: Path) -> Path:
    """Plain-numpy spectrogram (no scipy). Decodes wav via `wave`, other
    formats via soundfile if installed."""
    samples, sr = _load_audio(audio_path)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)

    frame, hop = 1024, 512
    n = 1 + max(len(samples) - frame, 0) // hop
    window = np.hanning(frame)
    spec = np.stack([
        np.abs(np.fft.rfft(window * samples[i * hop:i * hop + frame])) for i in range(n)
    ]).T
    db = 20.0 * np.log10(spec + 1e-9)
    db = np.clip(db - db.max(), -80.0, 0.0)

    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.imshow(db, origin="lower", aspect="auto", cmap="magma",
              extent=[0, len(samples) / sr, 0, sr / 2000])
    ax.set_xlabel("time (s)")
    ax.set_ylabel("frequency (kHz)")
    ax.set_title(f"Spectrogram — {audio_path.name}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def _load_audio(path: Path) -> tuple[np.ndarray, int]:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        import wave

        with wave.open(str(path), "rb") as wf:
            sr = wf.getframerate()
            width = wf.getsampwidth()
            raw = wf.readframes(wf.getnframes())
        dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
        return np.frombuffer(raw, dtype=dtype).astype(np.float64), sr
    import soundfile as sf

    data, sr = sf.read(str(path))
    return np.asarray(data, dtype=np.float64), int(sr)

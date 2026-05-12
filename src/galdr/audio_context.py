"""Shared audio context for one galdr listen run."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np


@dataclass(frozen=True)
class AudioContext:
    """Loaded mono audio shared across analysis modules."""

    y: np.ndarray
    sr: int
    duration: float
    path: str | None = None


def load_audio_context(audio_path: str, *, sr: int = 22050) -> AudioContext:
    """Load audio once with galdr's standard analysis parameters."""
    y, loaded_sr = librosa.load(audio_path, sr=sr, mono=True)
    duration = librosa.get_duration(y=y, sr=loaded_sr)
    return AudioContext(y=y, sr=loaded_sr, duration=float(duration), path=audio_path)

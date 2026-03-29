"""Regression tests for galdr — guards against specific previously-fixed bugs."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import librosa
import numpy as np
import pytest


# ─── 1. Short audio: analyze_track() does not crash ──────────────────────────


def _write_short_wav(path: Path, duration_sec: float = 0.3, sr: int = 22050) -> None:
    """Write a synthetic short WAV file using soundfile."""
    import soundfile as sf

    n_samples = int(sr * duration_sec)
    # simple sine wave
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    y = (0.3 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    sf.write(str(path), y, sr)


def test_analyze_track_short_audio_no_crash():
    """analyze_track() on very short audio (< 1s) should not raise ValueError."""
    from galdr.analyze import analyze_track

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "short.wav"
        _write_short_wav(wav_path, duration_sec=0.3)

        out_dir = Path(tmpdir) / "out"
        # Should not raise
        result = analyze_track(str(wav_path), str(out_dir), "short")

    assert isinstance(result, dict)
    assert "energy_arc" in result
    # energy_arc must have at least 1 segment and each must have non-empty fields
    assert len(result["energy_arc"]) >= 1
    for seg in result["energy_arc"]:
        assert "mean_energy" in seg
        assert "peak_energy" in seg


# ─── 2. Frame target: select_frames() returns exactly `target` ───────────────


def _make_perception(n_events: int = 0) -> dict:
    """Build a minimal perception dict for select_frames() tests."""
    return {
        "pattern_breaks": [
            {"time": float(i * 10), "type": "break", "intensity": 0.5}
            for i in range(n_events)
        ]
    }


@pytest.mark.parametrize("target,n_events,duration", [
    (12, 0, 300.0),   # all coverage
    (12, 5, 300.0),   # mixed anchor + coverage
    (8, 0, 120.0),    # fewer frames
    (20, 10, 600.0),  # more frames
    (5, 0, 60.0),     # short track
    (1, 0, 30.0),     # single frame
])
def test_select_frames_returns_exactly_target(target, n_events, duration):
    """select_frames() must return exactly `target` frames when possible."""
    from galdr.frames import select_frames

    perception = _make_perception(n_events)
    frames = select_frames(perception, duration=duration, target=target)
    assert len(frames) == target, (
        f"Expected {target} frames, got {len(frames)} "
        f"(n_events={n_events}, duration={duration})"
    )


# ─── 3. Frame bounds: select_frames() raises ValueError for bad args ──────────


def test_select_frames_raises_for_zero_target():
    """select_frames() must raise ValueError when target=0."""
    from galdr.frames import select_frames

    with pytest.raises(ValueError, match="target"):
        select_frames(_make_perception(), duration=300.0, target=0)


def test_select_frames_raises_for_negative_target():
    """select_frames() must raise ValueError when target < 0."""
    from galdr.frames import select_frames

    with pytest.raises(ValueError, match="target"):
        select_frames(_make_perception(), duration=300.0, target=-1)


def test_select_frames_raises_for_anchor_ratio_too_high():
    """select_frames() must raise ValueError when anchor_ratio > 1."""
    from galdr.frames import select_frames

    with pytest.raises(ValueError, match="anchor_ratio"):
        select_frames(_make_perception(), duration=300.0, target=12, anchor_ratio=1.5)


def test_select_frames_raises_for_anchor_ratio_negative():
    """select_frames() must raise ValueError when anchor_ratio < 0."""
    from galdr.frames import select_frames

    with pytest.raises(ValueError, match="anchor_ratio"):
        select_frames(_make_perception(), duration=300.0, target=12, anchor_ratio=-0.1)


def test_select_frames_accepts_boundary_anchor_ratios():
    """anchor_ratio=0.0 and anchor_ratio=1.0 are valid."""
    from galdr.frames import select_frames

    for ratio in (0.0, 1.0):
        frames = select_frames(_make_perception(), duration=300.0, target=6, anchor_ratio=ratio)
        assert len(frames) == 6


# ─── 4. Version: galdr.__version__ is a non-empty string ─────────────────────


def test_version_is_nonempty_string():
    """galdr.__version__ must be a non-empty string."""
    import galdr

    assert isinstance(galdr.__version__, str)
    assert galdr.__version__ != ""


def test_version_not_unknown_when_installed():
    """galdr.__version__ should not be 'unknown' when the package is installed."""
    import galdr

    # If the package is installed (pip install -e . or pip install .),
    # importlib.metadata.version() should resolve correctly.
    assert galdr.__version__ != "unknown", (
        "Package metadata not found — ensure galdr is installed (pip install -e .)"
    )


# ─── 5. mean_pattern_lock = 0.0 not replaced by mean_surprise ────────────────


def test_catalog_mean_pattern_lock_zero_preserved():
    """CatalogState.index_track() must preserve mean_pattern_lock=0.0, not fall back to mean_surprise."""
    from galdr.catalog import CatalogState

    with tempfile.TemporaryDirectory() as tmpdir:
        cat = CatalogState(catalog_dir=tmpdir)

        perception = {
            "summary": {
                "mean_pattern_lock": 0.0,   # falsy but explicitly set
                "mean_surprise": 99.9,       # must NOT be used
                "mean_momentum": 0.5,
                "total_silence_sec": 10.0,
                "pattern_break_count": 3,
                "breath_positive_pct": 40.0,
                "breath_negative_pct": 10.0,
                "breath_sustain_pct": 50.0,
            }
        }

        cat.index_track("test_track", perception=perception)

        track_metrics = cat.tracks.get("test_track", {})
        assert "mean_pattern_lock" in track_metrics
        assert track_metrics["mean_pattern_lock"] == 0.0, (
            f"Expected 0.0 but got {track_metrics['mean_pattern_lock']!r} — "
            "0.0 was likely replaced by mean_surprise"
        )


# ─── 6. --only invalid_name: CLI exits nonzero or produces no output ─────────


def test_cli_only_invalid_module_no_audio():
    """galdr listen with --only invalid_name on a non-existent file exits nonzero."""
    result = subprocess.run(
        [sys.executable, "-m", "galdr.cli", "listen", "/tmp/nonexistent_audio.wav",
         "--only", "invalid_module_xyz"],
        capture_output=True,
        text=True,
    )
    # Should fail because audio file doesn't exist
    assert result.returncode != 0


def test_cli_only_invalid_module_with_audio():
    """galdr listen with --only invalid_name exits nonzero (now validated)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import soundfile as sf

        wav_path = Path(tmpdir) / "short.wav"
        n_samples = 22050
        y = (0.3 * np.sin(2 * np.pi * 440.0 * np.linspace(0, 1.0, n_samples))).astype(np.float32)
        sf.write(str(wav_path), y, 22050)

        result = subprocess.run(
            [sys.executable, "-m", "galdr.cli", "listen", str(wav_path),
             "--only", "invalid_module_xyz",
             "--analysis-dir", tmpdir,
             "--no-catalog"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Invalid module name must cause nonzero exit
        assert result.returncode != 0, (
            f"Expected nonzero exit for --only invalid_module_xyz, got {result.returncode}"
        )
        combined = result.stdout + result.stderr
        assert "invalid_module_xyz" in combined, (
            "Error message should mention the invalid module name"
        )


# ─── 7. Tonal center timestamp doesn't exceed audio duration ─────────────────


def test_tonal_center_timestamp_within_audio_duration():
    """compute_tonal_center() timestamps must not exceed the audio duration on short inputs."""
    from galdr.harmony import compute_tonal_center

    sr = 22050
    hop_length = 512
    n_frames = 10  # very short — fewer frames than the default window size

    # Synthetic chroma: 12 pitch classes × 10 frames, all uniform energy
    rng = np.random.default_rng(42)
    chroma = rng.random((12, n_frames)).astype(np.float32)
    chroma /= chroma.sum(axis=0, keepdims=True) + 1e-8  # normalize columns

    times, key_names, modes, stability, major_minor, confidence = compute_tonal_center(
        chroma, sr=sr, hop_length=hop_length
    )

    # Maximum representable audio time is the last frame's time
    max_valid_time = librosa.frames_to_time(n_frames - 1, sr=sr, hop_length=hop_length)

    for t in times:
        assert t <= max_valid_time + 1e-6, (
            f"Tonal center timestamp {t:.4f}s exceeds audio duration {max_valid_time:.4f}s"
        )

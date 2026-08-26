"""Functional tests for galdr — run synthetic audio through the pipeline.

Run with: pytest tests/test_functional.py -v
Skip in CI: pytest -m "not slow"
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


def _galdr_cli_cmd(*args: str) -> list[str]:
    return [sys.executable, "-m", "galdr.cli", *args]


def _galdr_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


@pytest.fixture
def audio_path(tmp_path):
    """Path to a generated test tone fixture."""
    sr = 22050
    duration = 3.0
    t = np.linspace(0.0, duration, int(sr * duration), endpoint=False)
    # Two tones plus a soft amplitude rise give the pipeline enough structure
    # without depending on private or copyrighted audio fixtures.
    y = 0.18 * np.sin(2 * np.pi * 220.0 * t)
    y += 0.08 * np.sin(2 * np.pi * 440.0 * t)
    y *= np.linspace(0.35, 1.0, len(t))
    path = tmp_path / "synthetic-tone.wav"
    sf.write(path, y, sr)
    return str(path)


# ── Perception stream tests ──────────────────────────────────────────


@pytest.mark.slow
def test_perception_stream_writes_json(audio_path, tmp_path):
    """generate_perception_stream writes a stream JSON file."""
    from galdr.perceive import generate_perception_stream

    report = generate_perception_stream(audio_path, str(tmp_path), "test-track")
    stream_file = tmp_path / "test-track_stream.json"
    assert stream_file.exists()


@pytest.mark.slow
def test_perception_stream_entry_keys(audio_path, tmp_path):
    """Each stream entry has the expected keys."""
    from galdr.perceive import generate_perception_stream

    report = generate_perception_stream(audio_path, str(tmp_path), "test-track")
    stream = report.get("stream", [])

    expected_keys = {
        "t",
        "weight",
        "attention",
        "pattern",
        "pressure",
        "surface_balance",
        "harmonic_weight",
        "percussive_weight",
    }
    for entry in stream:
        assert expected_keys.issubset(entry.keys()), (
            f"Missing keys at t={entry.get('t')}: {expected_keys - entry.keys()}"
        )


@pytest.mark.slow
def test_perception_stream_pattern_range(audio_path, tmp_path):
    """pattern values must be between 0.0 and 1.0."""
    from galdr.perceive import generate_perception_stream

    report = generate_perception_stream(audio_path, str(tmp_path), "test-track")
    stream = report.get("stream", [])

    for entry in stream:
        assert 0.0 <= entry["pattern"] <= 1.0, (
            f"pattern out of range at t={entry['t']}: {entry['pattern']}"
        )


@pytest.mark.slow
def test_perception_stream_attention_range(audio_path, tmp_path):
    """attention values must be between 0.0 and 1.0."""
    from galdr.perceive import generate_perception_stream

    report = generate_perception_stream(audio_path, str(tmp_path), "test-track")
    stream = report.get("stream", [])

    for entry in stream:
        assert 0.0 <= entry["attention"] <= 1.0, (
            f"attention out of range at t={entry['t']}: {entry['attention']}"
        )


# ── Analyze track tests ─────────────────────────────────────────────


@pytest.mark.slow
def test_analyze_track_report_structure(audio_path, tmp_path):
    """analyze_track returns a report dict with expected top-level keys."""
    from galdr.analyze import analyze_track

    report = analyze_track(audio_path, str(tmp_path), "test-track")

    assert isinstance(report, dict)
    for key in [
        "track",
        "duration_seconds",
        "detected_pulse_bpm",
        "felt_pulse_bpm",
        "beat_count",
        "pulse",
        "surface_balance",
        "weight_arc",
    ]:
        assert key in report, f"Missing report key: {key}"
    assert report["track"] == "test-track"
    assert report["duration_seconds"] > 0


@pytest.mark.slow
def test_analyze_track_writes_report_json(audio_path, tmp_path):
    """analyze_track writes a report JSON file."""
    from galdr.analyze import analyze_track

    analyze_track(audio_path, str(tmp_path), "test-track")

    report_file = tmp_path / "test-track_report.json"
    assert report_file.exists()
    data = json.loads(report_file.read_text())
    assert data["track"] == "test-track"


# ── CLI integration test ─────────────────────────────────────────────


@pytest.mark.slow
def test_cli_listen_subprocess(audio_path, tmp_path):
    """galdr listen via subprocess exits 0 and creates output files."""
    result = subprocess.run(
        _galdr_cli_cmd(
            "listen",
            audio_path,
            "--name",
            "test-synthetic-tone",
            "--analysis-dir",
            str(tmp_path),
            "--no-catalog",
        ),
        capture_output=True,
        text=True,
        env=_galdr_subprocess_env(),
        timeout=300,
    )
    assert result.returncode == 0, f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    output_dir = tmp_path / "test-synthetic-tone"
    assert output_dir.exists()
    assert (output_dir / "test-synthetic-tone_report.json").exists()
    assert (output_dir / "test-synthetic-tone_stream.json").exists()
    assert (output_dir / "galdr-complete.json").exists()
    assert not list(tmp_path.glob(".test-synthetic-tone.tmp-*"))

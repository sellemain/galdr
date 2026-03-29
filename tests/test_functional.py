"""Functional tests for galdr — run real audio through the pipeline.

These tests require audio files in audio/ and are marked slow.
Run with: pytest tests/test_functional.py -v
Skip in CI: pytest -m "not slow"
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

AUDIO_FILE = Path("audio/1-anoana.wav")


@pytest.fixture
def audio_path():
    """Path to test audio file, skip if not available."""
    if not AUDIO_FILE.exists():
        pytest.skip(f"Audio file not found: {AUDIO_FILE}")
    return str(AUDIO_FILE)


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

    expected_keys = {"t", "energy", "momentum", "pattern_lock", "breath", "hp_balance",
                     "h_energy", "p_energy"}
    for entry in stream:
        assert expected_keys.issubset(entry.keys()), (
            f"Missing keys at t={entry.get('t')}: {expected_keys - entry.keys()}"
        )



@pytest.mark.slow
def test_perception_stream_pattern_lock_range(audio_path, tmp_path):
    """pattern_lock values must be between 0.0 and 1.0."""
    from galdr.perceive import generate_perception_stream

    report = generate_perception_stream(audio_path, str(tmp_path), "test-track")
    stream = report.get("stream", [])

    for entry in stream:
        assert 0.0 <= entry["pattern_lock"] <= 1.0, (
            f"pattern_lock out of range at t={entry['t']}: {entry['pattern_lock']}"
        )


@pytest.mark.slow
def test_perception_stream_momentum_range(audio_path, tmp_path):
    """momentum values must be between 0.0 and 1.0."""
    from galdr.perceive import generate_perception_stream

    report = generate_perception_stream(audio_path, str(tmp_path), "test-track")
    stream = report.get("stream", [])

    for entry in stream:
        assert 0.0 <= entry["momentum"] <= 1.0, (
            f"momentum out of range at t={entry['t']}: {entry['momentum']}"
        )


# ── Analyze track tests ─────────────────────────────────────────────


@pytest.mark.slow
def test_analyze_track_report_structure(audio_path, tmp_path):
    """analyze_track returns a report dict with expected top-level keys."""
    from galdr.analyze import analyze_track

    report = analyze_track(audio_path, str(tmp_path), "test-track")

    assert isinstance(report, dict)
    for key in ["track", "duration_seconds", "tempo_bpm", "beat_count",
                 "beat_regularity", "percussion_ratio", "energy_arc"]:
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
        [
            sys.executable, "-m", "galdr.cli",
            "listen", audio_path,
            "--name", "test-anoana",
            "--analysis-dir", str(tmp_path),
            "--no-catalog",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    output_dir = tmp_path / "test-anoana"
    assert output_dir.exists()
    assert (output_dir / "test-anoana_report.json").exists()
    assert (output_dir / "test-anoana_stream.json").exists()

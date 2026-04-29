"""Regression tests for galdr — guards against specific previously-fixed bugs."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import librosa
import numpy as np
import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _galdr_cli_cmd(*args: str) -> list[str]:
    """Run the checked-out galdr CLI, not a stale site-packages install.

    Tests may be launched through `pytest` from the system Python by accident.
    In that case, `sys.executable -m galdr.cli` can resolve to an older
    installed galdr instead of this working tree. For subprocess tests, force
    PYTHONPATH to the repository's src/ layout and use the current interpreter.
    """
    return [sys.executable, "-m", "galdr.cli", *args]


def _galdr_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def _make_short_audio(duration_sec: float = 2.0, sr: int = 22050) -> tuple:
    """Return (y, sr) for a short synthetic sine-wave audio array."""
    n_samples = int(sr * duration_sec)
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    y = (0.3 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    return y, sr


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
        _galdr_cli_cmd("listen", "/tmp/nonexistent_audio.wav", "--only", "invalid_module_xyz"),
        capture_output=True,
        text=True,
        env=_galdr_subprocess_env(),
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
            _galdr_cli_cmd(
                "listen", str(wav_path),
                "--only", "invalid_module_xyz",
                "--analysis-dir", tmpdir,
                "--no-catalog",
            ),
            capture_output=True,
            text=True,
            env=_galdr_subprocess_env(),
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


# ─── 8. pattern_break_counts dict in perception summary ──────────────────────


def test_pattern_break_counts_present_in_summary():
    """generate_perception_stream() summary must have pattern_break_counts with all four keys."""
    from galdr.perceive import compute_perception

    y, sr = _make_short_audio(duration_sec=3.0)
    report = compute_perception(y, sr, "test-counts")

    summary = report.get("summary", {})
    assert "pattern_break_counts" in summary, (
        "summary missing 'pattern_break_counts' key"
    )
    pbc = summary["pattern_break_counts"]
    for key in ("pattern_break", "momentum_drop", "momentum_gain", "silence"):
        assert key in pbc, f"pattern_break_counts missing key '{key}'"
    # Values must be non-negative integers
    for key, val in pbc.items():
        assert isinstance(val, int) and val >= 0, (
            f"pattern_break_counts['{key}'] = {val!r}, expected non-negative int"
        )


# ─── 9. generate_perception_stream() returns a dict, not a tuple ─────────────


def test_generate_perception_stream_returns_dict(tmp_path):
    """generate_perception_stream() must return a dict (not a tuple)."""
    import soundfile as sf
    from galdr.perceive import generate_perception_stream

    y, sr = _make_short_audio(duration_sec=3.0)
    wav_path = tmp_path / "test.wav"
    sf.write(str(wav_path), y, sr)

    result = generate_perception_stream(str(wav_path), str(tmp_path), "test-return")
    assert isinstance(result, dict), (
        f"generate_perception_stream() returned {type(result).__name__}, expected dict"
    )
    assert "stream" in result, "result dict missing 'stream' key"
    assert isinstance(result["stream"], list), "'stream' should be a list"


def test_cli_null_audio_skips_remaining_modules(tmp_path):
    """galdr listen should stop after null_signal and not write analysis artifacts."""
    import soundfile as sf

    wav_path = tmp_path / "null.wav"
    y = np.zeros(22050, dtype=np.float32)
    sf.write(str(wav_path), y, 22050)

    analysis_dir = tmp_path / "analysis"
    result = subprocess.run(
        _galdr_cli_cmd(
            "listen", str(wav_path),
            "--name", "null-cli",
            "--analysis-dir", str(analysis_dir),
            "--no-catalog",
        ),
        capture_output=True,
        text=True,
        env=_galdr_subprocess_env(),
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "remaining modules skipped" in result.stdout
    out_dir = analysis_dir / "null-cli"
    assert not out_dir.exists() or not any(out_dir.iterdir())


def test_cli_null_audio_only_perceive_skips_outputs(tmp_path):
    """The null-signal guard should still run when report is not selected."""
    import soundfile as sf

    wav_path = tmp_path / "null.wav"
    y = np.zeros(22050, dtype=np.float32)
    sf.write(str(wav_path), y, 22050)

    analysis_dir = tmp_path / "analysis"
    result = subprocess.run(
        _galdr_cli_cmd(
            "listen", str(wav_path),
            "--name", "null-only-perceive",
            "--analysis-dir", str(analysis_dir),
            "--only", "perceive",
            "--no-catalog",
        ),
        capture_output=True,
        text=True,
        env=_galdr_subprocess_env(),
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "remaining modules skipped" in result.stdout
    out_dir = analysis_dir / "null-only-perceive"
    assert not out_dir.exists() or not any(out_dir.iterdir())


def test_assemble_unknown_slug_raises(tmp_path):
    """assemble_prompt_from_disk should not fabricate zero metrics for missing slugs."""
    from galdr.assemble import assemble_prompt_from_disk

    with pytest.raises(ValueError, match="No analysis or context found"):
        assemble_prompt_from_disk("missing-slug", tmp_path)


def test_assemble_context_only_reports_missing_structural_analysis(tmp_path):
    """Context-only tracks should not emit fabricated zero-valued metrics."""
    from galdr.assemble import assemble_prompt_from_disk

    slug = "context-only"
    track_dir = tmp_path / slug
    track_dir.mkdir()
    (track_dir / "context.json").write_text(json.dumps({
        "slug": slug,
        "artist": "Example Artist",
        "title": "Example Track",
    }))

    prompt = assemble_prompt_from_disk(slug, tmp_path)

    assert "No structural analysis files found" in prompt
    assert "Duration: 0:00" not in prompt
    assert "Tempo: 0.0 BPM" not in prompt


def test_frames_download_rejects_non_youtube_url(tmp_path):
    """frames video download should reuse the strict YouTube URL allowlist."""
    from galdr.frames import download_video

    with pytest.raises(ValueError, match="Invalid YouTube URL"):
        download_video("https://example.com/video.mp4", tmp_path, "safe-slug")


def test_yt_dlp_base_cmd_uses_current_python_environment():
    """yt-dlp should run from galdr's Python env, not a PATH binary."""
    from galdr.fetch import _yt_dlp_base_cmd

    cmd = _yt_dlp_base_cmd()
    assert cmd[:3] == [sys.executable, "-m", "yt_dlp"]


def test_download_youtube_caption_failure_keeps_audio(monkeypatch, tmp_path):
    """Subtitle failures should not make an otherwise-good audio download fail."""
    from galdr import fetch as fetch_mod

    slug = "caption-fail"
    calls = []

    def fake_run(cmd, capture_output, text, timeout):
        calls.append(cmd)
        if "--skip-download" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "HTTP Error 429: Too Many Requests")

        (tmp_path / f"{slug}.mp3").write_bytes(b"fake mp3")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(fetch_mod.subprocess, "run", fake_run)

    result = fetch_mod.download_youtube(
        "https://www.youtube.com/watch?v=X7drilHsM6c",
        tmp_path,
        slug,
    )

    assert len(calls) == 2
    assert "--write-auto-sub" not in calls[0]
    assert "--skip-download" in calls[1]
    assert result["download_ok"] is True
    assert result["audio_file"] == str(tmp_path / f"{slug}.mp3")
    assert result["captions_file"] is None
    assert "429" in result["captions_stderr"]


def test_run_yt_dlp_retries_remote_ejs_for_challenge_failure(monkeypatch):
    """YouTube JS challenge failures should retry once with remote EJS components."""
    from galdr import fetch as fetch_mod

    calls = []

    def fake_run(cmd, capture_output, text, timeout):
        calls.append(cmd)
        if "--remote-components" in cmd:
            return subprocess.CompletedProcess(cmd, 0, '{"title": "ok"}', "")
        return subprocess.CompletedProcess(
            cmd,
            1,
            "",
            "WARNING: [youtube] [jsc] Remote components challenge solver script skipped. "
            "n challenge solving failed: Some formats may be missing.",
        )

    monkeypatch.setattr(fetch_mod.subprocess, "run", fake_run)

    result = fetch_mod._run_yt_dlp(
        ["--dump-json", "--no-playlist", "https://www.youtube.com/watch?v=X7drilHsM6c"],
        timeout=60,
    )

    assert result.returncode == 0
    assert len(calls) == 2
    assert "--remote-components" not in calls[0]
    assert calls[1][calls[1].index("--remote-components") + 1] == "ejs:github"


def test_update_deps_installs_yt_dlp_reliability_extras(monkeypatch):
    """update-deps should upgrade the same yt-dlp extras galdr depends on."""
    from galdr import cli

    calls = []

    def fake_run(cmd, capture_output=False, text=False, timeout=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    cli.cmd_update_deps()

    assert [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "yt-dlp[default,curl-cffi]",
    ] in calls


def test_cli_doctor_subprocess():
    """galdr doctor should print local diagnostics and exit cleanly."""
    result = subprocess.run(
        _galdr_cli_cmd("doctor"),
        capture_output=True,
        text=True,
        env=_galdr_subprocess_env(),
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "galdr doctor" in result.stdout
    assert "yt-dlp" in result.stdout
    assert "Impersonation targets" in result.stdout


# ─── 10. compute_track_features and compute_perception are importable ─────────


def test_compute_track_features_importable():
    """compute_track_features must be importable from galdr."""
    from galdr import compute_track_features
    assert callable(compute_track_features)


def test_compute_perception_importable():
    """compute_perception must be importable from galdr."""
    from galdr import compute_perception
    assert callable(compute_perception)


def test_compute_track_features_callable_with_synthetic_audio():
    """compute_track_features() must not crash on short synthetic audio."""
    from galdr import compute_track_features

    y, sr = _make_short_audio(duration_sec=2.0)
    result = compute_track_features(y, sr, "synth")

    assert isinstance(result, dict)
    assert "tempo_bpm" in result
    assert "beat_regularity" in result
    assert "energy_arc" in result
    # Private arrays should have been added but are stripped on JSON serialization;
    # verify the report fields are present.
    assert result["track"] == "synth"


def test_compute_perception_callable_with_synthetic_audio():
    """compute_perception() must not crash on short synthetic audio."""
    from galdr import compute_perception

    y, sr = _make_short_audio(duration_sec=2.0)
    result = compute_perception(y, sr, "synth-perc")

    assert isinstance(result, dict)
    assert "stream" in result
    assert isinstance(result["stream"], list)
    assert "summary" in result
    assert "pattern_break_counts" in result["summary"]

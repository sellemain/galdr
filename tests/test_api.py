"""Tests for galdr's high-level Python API."""

import json

import pytest


def test_public_api_exports():
    import galdr

    assert callable(galdr.listen)
    assert callable(galdr.assemble)
    assert callable(galdr.load_stream_df)
    assert hasattr(galdr, "Analysis")


def test_analysis_from_dir_loads_report(tmp_path):
    from galdr import Analysis

    track_dir = tmp_path / "analysis" / "demo-track"
    track_dir.mkdir(parents=True)
    (track_dir / "demo-track_report.json").write_text(json.dumps({"track": "demo-track"}))

    analysis = Analysis.from_dir(track_dir)

    assert analysis.slug == "demo-track"
    assert analysis.analysis_dir == tmp_path / "analysis"
    assert analysis.report == {"track": "demo-track"}
    assert analysis.path == track_dir


def test_load_stream_df_supports_dict_stream(tmp_path):
    pd = pytest.importorskip("pandas")
    from galdr import load_stream_df

    path = tmp_path / "demo_stream.json"
    path.write_text(json.dumps({"stream": [{"t": 0, "attention": 0.1}, {"t": 1, "attention": 0.2}]}))

    df = load_stream_df(path)

    assert list(df.columns) == ["t", "attention"]
    assert df["attention"].tolist() == [0.1, 0.2]


def test_load_streams_df_loads_available_modules(tmp_path):
    pd = pytest.importorskip("pandas")
    from galdr import load_streams_df

    track_dir = tmp_path / "analysis" / "demo"
    track_dir.mkdir(parents=True)
    (track_dir / "demo_stream.json").write_text(json.dumps([{"t": 0, "weight": 0.3}]))
    (track_dir / "demo_harmony_stream.json").write_text(json.dumps({"stream": [{"t": 0, "harmonic_pull": 0.4}]}))

    frames = load_streams_df("demo", tmp_path / "analysis")

    assert set(frames) == {"perception", "harmony"}
    assert frames["perception"].iloc[0]["weight"] == 0.3
    assert frames["harmony"].iloc[0]["harmonic_pull"] == 0.4


def test_assemble_accepts_raw_analysis_dict():
    from galdr import assemble

    prompt = assemble(
        {"report": {"duration_seconds": 61.0, "detected_pulse_bpm": 90.0}},
        context={"artist": "Example", "title": "Demo"},
        mode="blind",
    )

    assert "## Galdr Analysis" in prompt
    assert "Duration: 1:01 (61.0s)" in prompt
    assert "Pulse: detected ~90.0 BPM" in prompt


def test_python_module_entrypoint_help():
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"

    result = subprocess.run(
        [sys.executable, "-m", "galdr", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "Deterministic ears for AI agents" in result.stdout

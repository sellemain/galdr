"""Tempo validation regression tests."""

import numpy as np
import pytest

from galdr.tempo import estimate_tempo_profile, normalize_tempo_scalar


def test_normalize_tempo_scalar_handles_librosa_array_output():
    assert normalize_tempo_scalar(np.array([92.285])) == pytest.approx(92.285)
    assert normalize_tempo_scalar(np.array([])) == 0.0
    assert normalize_tempo_scalar(float("nan")) == 0.0


def test_cipher_style_alternate_pulse_prefers_windowed_141_candidate():
    profile = estimate_tempo_profile(
        92.3,
        window_tempos=[140.2, 140.6, 141.0, 142.3, 92.1],
    )

    assert profile["detected_pulse_bpm"] == pytest.approx(92.3)
    assert profile["felt_pulse_bpm"] == pytest.approx(140.8, abs=1.0)
    assert profile["pulse_ambiguous"] is True
    assert profile["pulse_confidence"] < 0.75
    assert profile["tempo_candidates"][0]["bpm"] == pytest.approx(140.8, abs=1.0)
    assert "window" in profile["tempo_candidates"][0]["source"]


def test_detected_tempo_preserved_when_windows_agree():
    profile = estimate_tempo_profile(120.0, window_tempos=[119.5, 120.1, 120.4])

    assert profile["detected_pulse_bpm"] == pytest.approx(120.0)
    assert profile["felt_pulse_bpm"] == pytest.approx(120.0, abs=1.0)
    assert profile["pulse_ambiguous"] is False
    assert profile["pulse_confidence"] >= 0.5


def test_metric_tension_flags_stable_pulse_with_competing_candidates():
    from galdr.tempo import estimate_metric_tension

    tension = estimate_metric_tension(
        pulse=0.96,
        pulse_confidence=0.82,
        tempo_candidates=[
            {"bpm": 152.0, "support": 9, "source": "detected:1+window:8"},
            {"bpm": 114.0, "support": 5, "source": "window:5"},
            {"bpm": 92.0, "support": 3, "source": "window:3"},
            {"bpm": 76.0, "support": 2, "source": "alternate:1+window:1"},
        ],
    )

    assert tension["metric_tension"] >= 0.30
    assert tension["metric_tension_state"] in {"present", "high"}


def test_metric_tension_stays_low_for_plain_half_double_alternates():
    from galdr.tempo import estimate_metric_tension

    tension = estimate_metric_tension(
        pulse=0.96,
        pulse_confidence=0.9,
        tempo_candidates=[
            {"bpm": 120.0, "support": 8, "source": "detected:1+window:7"},
            {"bpm": 60.0, "support": 2, "source": "alternate:1+window:1"},
            {"bpm": 240.0, "support": 2, "source": "alternate:1+window:1"},
        ],
    )

    assert tension["metric_tension"] < 0.30
    assert tension["metric_tension_state"] in {"absent", "trace"}

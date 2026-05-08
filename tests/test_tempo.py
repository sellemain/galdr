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

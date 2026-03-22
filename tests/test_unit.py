"""Unit tests for galdr — pure functions and pipeline logic. No audio required."""

import math
import pytest


# ── hz_to_note_name ──────────────────────────────────────────────────


class TestHzToNoteName:
    def setup_method(self):
        from galdr.melody import hz_to_note_name
        self.fn = hz_to_note_name

    def test_concert_a(self):
        assert self.fn(440.0) == "A4"

    def test_middle_c(self):
        assert self.fn(261.63) == "C4"

    def test_c5(self):
        assert self.fn(523.25) == "C5"

    def test_lowest_piano_a(self):
        # A0 = 27.5 Hz
        assert self.fn(27.5) == "A0"

    def test_zero_returns_unknown(self):
        assert self.fn(0.0) == "?"

    def test_negative_returns_unknown(self):
        assert self.fn(-100.0) == "?"

    def test_nan_returns_unknown(self):
        import numpy as np
        assert self.fn(float("nan")) == "?"

    def test_octave_relationship(self):
        # A4 and A5 should share the note letter, differ by one octave
        assert self.fn(440.0) == "A4"
        assert self.fn(880.0) == "A5"

    def test_sharp_note(self):
        # C#4 ≈ 277.18 Hz
        assert self.fn(277.18) == "C#4"


# ── hz_to_cents ──────────────────────────────────────────────────────


class TestHzToCents:
    def setup_method(self):
        from galdr.overtone import hz_to_cents
        self.fn = hz_to_cents

    def test_unison_is_zero(self):
        assert self.fn(440.0, 440.0) == pytest.approx(0.0)

    def test_octave_up_is_1200(self):
        assert self.fn(220.0, 440.0) == pytest.approx(1200.0)

    def test_octave_down_is_negative_1200(self):
        assert self.fn(440.0, 220.0) == pytest.approx(-1200.0)

    def test_perfect_fifth(self):
        # 3/2 ratio ≈ 701.96 cents
        assert self.fn(440.0, 660.0) == pytest.approx(701.96, abs=0.5)

    def test_semitone(self):
        # One semitone = 100 cents
        f2 = 440.0 * (2 ** (1 / 12))
        assert self.fn(440.0, f2) == pytest.approx(100.0, abs=0.1)

    def test_zero_f1_returns_inf(self):
        import math
        assert math.isinf(self.fn(0.0, 440.0))

    def test_zero_f2_returns_inf(self):
        import math
        assert math.isinf(self.fn(440.0, 0.0))

    def test_antisymmetric(self):
        # cents(f1, f2) == -cents(f2, f1)
        a = self.fn(440.0, 523.25)
        b = self.fn(523.25, 440.0)
        assert a == pytest.approx(-b, abs=0.01)


# ── flatten_metrics ──────────────────────────────────────────────────


class TestFlattenMetrics:
    def setup_method(self):
        from galdr.compare import flatten_metrics
        self.fn = flatten_metrics

    def test_empty_input(self):
        assert self.fn({}) == {}

    def test_report_section_extracted(self):
        data = {"report": {"duration_seconds": 180.0, "tempo_bpm": 120.0, "beat_count": 360}}
        result = self.fn(data)
        assert result["duration_seconds"] == 180.0
        assert result["tempo_bpm"] == 120.0
        assert result["beat_count"] == 360

    def test_non_numeric_values_skipped(self):
        data = {"report": {"duration_seconds": 180.0, "track": "some-track", "tempo_bpm": 120.0}}
        result = self.fn(data)
        assert "track" not in result
        assert "duration_seconds" in result

    def test_perception_section_extracted(self):
        data = {
            "perception": {
                "summary": {
                    "mean_momentum": 0.85,
                    "mean_pattern_lock": 0.96,
                    "total_silence_sec": 4.2,
                    "pattern_break_count": 3,
                }
            }
        }
        result = self.fn(data)
        assert result["mean_momentum"] == pytest.approx(0.85)
        assert result["mean_pattern_lock"] == pytest.approx(0.96)
        assert result["pattern_break_count"] == 3

    def test_harmony_section_extracted(self):
        data = {
            "harmony": {
                "mean_tension": 0.35,
                "key_confidence": 0.72,
                "mean_chroma_flux": 0.21,
            }
        }
        result = self.fn(data)
        assert result["mean_tension"] == pytest.approx(0.35)
        assert result["key_confidence"] == pytest.approx(0.72)

    def test_all_sections_combined(self):
        data = {
            "report": {"duration_seconds": 200.0, "tempo_bpm": 100.0},
            "perception": {"summary": {"mean_momentum": 0.8, "pattern_break_count": 2}},
            "harmony": {"mean_tension": 0.4},
            "melody": {"mean_direction": 0.1},
        }
        result = self.fn(data)
        assert "duration_seconds" in result
        assert "mean_momentum" in result
        assert "mean_tension" in result
        assert "mean_direction" in result

    def test_missing_sections_dont_crash(self):
        # Only harmony present — others absent
        data = {"harmony": {"mean_tension": 0.3}}
        result = self.fn(data)
        assert result == {"mean_tension": 0.3}


# ── assemble_prompt (pipeline) ───────────────────────────────────────


class TestAssemblePrompt:
    def setup_method(self):
        from galdr.assemble import assemble_prompt
        self.fn = assemble_prompt

    def _minimal_analysis(self):
        return {
            "report": {"duration_seconds": 200.0, "tempo_bpm": 120.0, "beat_regularity": 0.96},
            "perception": {"summary": {"mean_momentum": 0.85, "mean_pattern_lock": 0.95}},
        }

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown mode"):
            self.fn(self._minimal_analysis(), mode="nonsense")

    def test_blind_mode_returns_string(self):
        result = self.fn(self._minimal_analysis(), mode="blind")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_full_mode_longer_than_blind(self):
        analysis = self._minimal_analysis()
        context = {
            "artist_context": "Background about the artist.",
            "lyrics": {"full_text": "Some lyrics here."},
        }
        full = self.fn(analysis, context=context, mode="full")
        blind = self.fn(analysis, context=context, mode="blind")
        assert len(full) > len(blind)

    def test_blind_mode_excludes_background(self):
        analysis = self._minimal_analysis()
        context = {"artist_context": "UNIQUE_ARTIST_CONTEXT_STRING"}
        result = self.fn(analysis, context=context, mode="blind")
        assert "UNIQUE_ARTIST_CONTEXT_STRING" not in result

    def test_context_mode_excludes_lyrics(self):
        analysis = self._minimal_analysis()
        context = {
            "artist_context": "Some background.",
            "lyrics": {"full_text": "UNIQUE_LYRIC_STRING"},
        }
        result = self.fn(analysis, context=context, mode="context")
        assert "UNIQUE_LYRIC_STRING" not in result

    def test_lyrics_mode_includes_lyrics(self):
        analysis = self._minimal_analysis()
        context = {"lyrics": {"full_text": "UNIQUE_LYRIC_STRING"}}
        result = self.fn(analysis, context=context, mode="lyrics")
        assert "UNIQUE_LYRIC_STRING" in result

    def test_no_context_doesnt_crash(self):
        result = self.fn(self._minimal_analysis(), context=None, mode="full")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_context_doesnt_crash(self):
        result = self.fn(self._minimal_analysis(), context={}, mode="full")
        assert isinstance(result, str)

    def test_metrics_always_present(self):
        # Galdr metrics block is included in all modes
        for mode in ("blind", "lyrics", "context", "full"):
            result = self.fn(self._minimal_analysis(), mode=mode)
            # tempo should always appear in the metrics section
            assert "120" in result or "bpm" in result.lower(), \
                f"Metrics missing from mode={mode}"

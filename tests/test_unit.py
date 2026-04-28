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
        assert math.isinf(self.fn(0.0, 440.0))

    def test_zero_f2_returns_inf(self):
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


# ── Null Signal Guard ─────────────────────────────────────────────────────────


class TestNullSignalGuard:
    """analyze_track should early-exit cleanly on degenerate/empty audio."""

    def _write_null_wav(self, path, duration_sec=2.0, sr=22050):
        import numpy as np
        import soundfile as sf
        silence = np.zeros(int(sr * duration_sec), dtype=np.float32)
        sf.write(path, silence, sr)

    def test_null_audio_returns_null_signal_dict(self, tmp_path):
        from galdr.analyze import analyze_track
        wav = tmp_path / "null.wav"
        self._write_null_wav(wav)
        result = analyze_track(str(wav), str(tmp_path / "out"), "null-test")
        assert result.get("null_signal") is True

    def test_null_audio_no_output_files(self, tmp_path):
        from galdr.analyze import analyze_track
        out = tmp_path / "out"
        wav = tmp_path / "null.wav"
        self._write_null_wav(wav)
        analyze_track(str(wav), str(out), "null-test")
        # Should not create any analysis files
        assert not out.exists() or not any(out.iterdir())

    def test_null_audio_has_duration(self, tmp_path):
        from galdr.analyze import analyze_track
        wav = tmp_path / "null.wav"
        self._write_null_wav(wav, duration_sec=5.0)
        result = analyze_track(str(wav), str(tmp_path / "out"), "null-test")
        assert result["duration_seconds"] == pytest.approx(5.0, abs=0.2)

    def test_real_audio_not_flagged(self, tmp_path):
        import numpy as np
        import soundfile as sf
        from galdr.analyze import analyze_track
        sr = 22050
        t = np.linspace(0, 2.0, sr * 2)
        tone = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        wav = tmp_path / "tone.wav"
        sf.write(wav, tone, sr)
        result = analyze_track(str(wav), str(tmp_path / "out"), "tone-test")
        assert result.get("null_signal") is None or result.get("null_signal") is False


# ── Active-Frame Silence Stats ────────────────────────────────────────────────


class TestActiveFrameStats:
    """perceive.py should report active-frame stats alongside whole-track averages."""

    def _make_perception_summary(self, silence_pct, momentum_active=0.8, momentum_whole=0.4):
        """Build a minimal perception summary dict as if returned by generate_perception_stream."""
        return {
            "mean_momentum": momentum_whole,
            "mean_pattern_lock": 0.7,
            "momentum_range": [0.1, 0.9],
            "total_silence_sec": 30.0,
            "silent_duration_sec": 30.0,
            "active_duration_sec": 70.0,
            "silence_pct": silence_pct,
            "mean_momentum_active": momentum_active,
            "mean_pattern_lock_active": 0.85,
            "momentum_range_active": [0.5, 0.9],
            "pattern_break_count": 4,
            "pattern_break_counts": {
                "pattern_break": 2,
                "momentum_drop": 1,
                "momentum_gain": 0,
                "silence": 1,
            },
            "breath_positive_pct": 40.0,
            "breath_negative_pct": 30.0,
            "breath_sustain_pct": 30.0,
        }

    def test_active_frame_fields_present(self):
        s = self._make_perception_summary(silence_pct=33.0)
        assert "active_duration_sec" in s
        assert "silent_duration_sec" in s
        assert "silence_pct" in s
        assert "mean_momentum_active" in s
        assert "mean_pattern_lock_active" in s

    def test_pattern_break_counts_split(self):
        s = self._make_perception_summary(silence_pct=5.0)
        pbc = s["pattern_break_counts"]
        assert "pattern_break" in pbc
        assert "momentum_drop" in pbc
        assert "momentum_gain" in pbc
        assert "silence" in pbc
        assert sum(pbc.values()) == s["pattern_break_count"]

    def test_catalog_uses_active_momentum_when_silence_high(self):
        """When silence_pct >= threshold, catalog should index active-frame momentum."""
        from galdr.catalog import CatalogState
        from galdr.constants import ACTIVE_FRAME_SILENCE_PCT_THRESHOLD

        cat = CatalogState(analysis_dir="/tmp", catalog_dir="/tmp/cat-test")
        perception = {"summary": self._make_perception_summary(
            silence_pct=ACTIVE_FRAME_SILENCE_PCT_THRESHOLD + 5.0,
            momentum_active=0.80,
            momentum_whole=0.40,
        )}
        cat.index_track("test-silence-track", perception=perception)
        indexed = cat.tracks["test-silence-track"]
        # Should use active-frame momentum for catalog ranking
        assert indexed["mean_momentum"] == pytest.approx(0.80, abs=0.01)

    def test_catalog_uses_whole_momentum_when_silence_low(self):
        from galdr.catalog import CatalogState
        from galdr.constants import ACTIVE_FRAME_SILENCE_PCT_THRESHOLD

        cat = CatalogState(analysis_dir="/tmp", catalog_dir="/tmp/cat-test2")
        perception = {"summary": self._make_perception_summary(
            silence_pct=ACTIVE_FRAME_SILENCE_PCT_THRESHOLD - 5.0,
            momentum_active=0.80,
            momentum_whole=0.40,
        )}
        cat.index_track("test-quiet-track", perception=perception)
        indexed = cat.tracks["test-quiet-track"]
        # Should use whole-track momentum (silence not significant)
        assert indexed["mean_momentum"] == pytest.approx(0.40, abs=0.01)

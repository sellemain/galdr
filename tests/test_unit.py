"""Unit tests for galdr — pure functions and pipeline logic. No audio required."""

import math
import numpy as np
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
        data = {"report": {"duration_seconds": 180.0, "detected_pulse_bpm": 120.0, "beat_count": 360}}
        result = self.fn(data)
        assert result["duration_seconds"] == 180.0
        assert result["detected_pulse_bpm"] == 120.0
        assert result["beat_count"] == 360

    def test_non_numeric_values_skipped(self):
        data = {"report": {"duration_seconds": 180.0, "track": "some-track", "detected_pulse_bpm": 120.0}}
        result = self.fn(data)
        assert "track" not in result
        assert "duration_seconds" in result

    def test_perception_section_extracted(self):
        data = {
            "perception": {
                "summary": {
                    "mean_attention": 0.85,
                    "mean_pattern": 0.96,
                    "total_silence_sec": 4.2,
                    "pattern_break_count": 3,
                }
            }
        }
        result = self.fn(data)
        assert result["mean_attention"] == pytest.approx(0.85)
        assert result["mean_pattern"] == pytest.approx(0.96)
        assert result["pattern_break_count"] == 3

    def test_harmony_section_extracted(self):
        data = {
            "harmony": {
                "mean_harmonic_pull": 0.35,
                "key_confidence": 0.72,
                "mean_chroma_motion": 0.21,
            }
        }
        result = self.fn(data)
        assert result["mean_harmonic_pull"] == pytest.approx(0.35)
        assert result["key_confidence"] == pytest.approx(0.72)

    def test_all_sections_combined(self):
        data = {
            "report": {"duration_seconds": 200.0, "detected_pulse_bpm": 100.0},
            "perception": {"summary": {"mean_attention": 0.8, "pattern_break_count": 2}},
            "harmony": {"mean_harmonic_pull": 0.4},
            "melody": {"mean_direction": 0.1},
        }
        result = self.fn(data)
        assert "duration_seconds" in result
        assert "mean_attention" in result
        assert "mean_harmonic_pull" in result
        assert "mean_direction" in result

    def test_missing_sections_dont_crash(self):
        # Only harmony present — others absent
        data = {"harmony": {"mean_harmonic_pull": 0.3}}
        result = self.fn(data)
        assert result == {"mean_harmonic_pull": 0.3}


# ── assemble_prompt (pipeline) ───────────────────────────────────────


class TestAssemblePrompt:
    def setup_method(self):
        from galdr.assemble import assemble_prompt
        self.fn = assemble_prompt

    def _minimal_analysis(self):
        return {
            "report": {"duration_seconds": 200.0, "detected_pulse_bpm": 120.0, "felt_pulse_bpm": 120.0, "pulse": 0.96},
            "perception": {"summary": {"mean_attention": 0.85, "mean_pattern": 0.95}},
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


    def test_low_confidence_context_excluded_from_prompt(self):
        analysis = self._minimal_analysis()
        context = {
            "artist_context": {
                "found": True,
                "extract": "WRONG_ARTIST_CONTEXT",
                "confidence": "rejected",
                "use_in_prompt": False,
            },
            "song_context": {
                "found": True,
                "extract": "GOOD_SONG_CONTEXT",
                "confidence": "medium",
                "use_in_prompt": True,
            },
        }
        result = self.fn(analysis, context=context, mode="full")
        assert "WRONG_ARTIST_CONTEXT" not in result
        assert "GOOD_SONG_CONTEXT" in result

    def test_low_confidence_genius_text_excluded_but_captions_remain(self):
        analysis = self._minimal_analysis()
        context = {
            "lyrics": {
                "source": "genius+autocaptions",
                "genius_text": "WRONG_GENIUS_TEXT",
                "caption_lines": [{"ts": "0:01", "text": "caption words"}],
                "full_text": "WRONG_GENIUS_TEXT",
                "confidence": "rejected",
                "use_in_prompt": False,
            }
        }
        result = self.fn(analysis, context=context, mode="lyrics")
        assert "WRONG_GENIUS_TEXT" not in result
        assert "caption words" in result

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

    def test_ambiguous_tempo_not_presented_as_plain_truth(self):
        analysis = {
            "report": {
                "duration_seconds": 200.0,
                "detected_pulse_bpm": 92.3,
                "felt_pulse_bpm": 140.8,
                "pulse_confidence": 0.68,
                "pulse_ambiguous": True,
                "pulse_note": "detected pulse conflicts with repeated windowed beat tracking",
            }
        }
        result = self.fn(analysis, mode="blind")

        assert "Tempo: 92.3 BPM" not in result
        assert "felt ~140.8 BPM" in result
        assert "detected pulse 92.3 BPM" in result
        assert "ambiguous/suspect" in result


# ── SM-308 Perception surface demotion ───────────────────────────────────────


def _sm308_analysis():
    return {
        "report": {
            "duration_seconds": 180.0,
            "detected_pulse_bpm": 92.0,
            "felt_pulse_bpm": 92.0,
            "pulse": 0.76,
            "harmonic_weight": 0.7,
            "percussive_weight": 0.3,
            "texture": -0.4,
            "character": "pure harmonic/vocal",
        },
        "perception": {
            "summary": {
                "mean_attention": 0.52,
                "mean_pattern": 0.81,
                "pressure_building_pct": 35.0,
                "pressure_releasing_pct": 25.0,
                "pressure_sustaining_pct": 40.0,
                "silence_pct": 12.0,
                "active_duration_sec": 158.0,
                "pattern_break_count": 3,
            },
            "pattern_breaks": [
                {"time": 42.0, "type": "attention_drop", "intensity": 0.62},
                {"time": 80.0, "type": "silence", "duration": 1.2, "depth_db": -72.0},
            ],
        },
        "harmony": {
            "detected_key": "D",
            "detected_mode": "minor",
            "key_confidence": 0.44,
            "mean_major_minor": -0.7,
            "top_chords": [{"chord": "Dm"}, {"chord": "A7"}],
            "mean_harmonic_pull": 0.33,
            "mean_tonal_anchor": 0.58,
            "mean_chroma_motion": 0.27,
        },
        "melody": {
            "overall_range_semitones": 31.0,
            "overall_center_note": "A4",
            "mean_foreground_line": 0.18,
            "contour_ascending_pct": 40.0,
            "contour_descending_pct": 35.0,
            "contour_holding_pct": 25.0,
            "mean_direction": 0.12,
        },
        "overtone": {
            "mean_overtone_fit": 0.61,
            "mean_overtone_density": 0.48,
            "mean_inharmonicity": 12.0,
        },
    }


def test_sm308_assemble_demotes_theory_and_vocal_labels():
    from galdr.assemble import assemble_prompt

    prompt = assemble_prompt(_sm308_analysis(), mode="blind")

    assert "Attention:" in prompt
    assert "Pattern:" in prompt
    assert "Pressure:" in prompt
    assert "How to read galdr" in prompt
    assert "Event timeline" in prompt
    assert "Harmonic pull:" in prompt
    assert "Foreground line:" in prompt

    forbidden = [
        "Character:",
        "Major/minor balance",
        "Top chords",
        "Vocal presence",
        "Melody contour",
        "Mean direction",
        "detected_key",
        "Key:",
        "Harmonic series fit",
        "Overtone richness",
    ]
    for text in forbidden:
        assert text not in prompt


def test_sm308_catalog_card_is_perception_first():
    from galdr.catalog import CatalogState

    cat = CatalogState(analysis_dir="/tmp", catalog_dir="/tmp/cat-sm308")
    analysis = _sm308_analysis()
    cat.index_track(
        "sm308-track",
        perception=analysis["perception"],
        harmony=analysis["harmony"],
        melody=analysis["melody"],
        overtone=analysis["overtone"],
        report=analysis["report"],
    )
    card = cat.summary_card("sm308-track")

    assert "Pattern" in card
    assert "Attention" in card
    assert "Pressure Building" in card
    assert "Structural Breaks" in card
    assert "Harmonic pull" in card

    forbidden = [
        "Vocal Presence",
        "Melodic Range",
        "Overtone richness",
        "Overtone fit",
        "Key Confidence",
        "Detected Pulse",
        "Major/minor",
    ]
    for text in forbidden:
        assert text not in card


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

    def test_compute_track_features_adds_tempo_validation_fields(self):
        import numpy as np
        from galdr.analyze import compute_track_features

        sr = 22050
        t = np.linspace(0, 2.0, sr * 2)
        tone = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        result = compute_track_features(tone, sr, "tone-test")

        assert "detected_pulse_bpm" in result
        assert "detected_pulse_bpm" in result
        assert "felt_pulse_bpm" in result
        assert "tempo_candidates" in result
        assert "pulse_confidence" in result
        assert "pulse_ambiguous" in result
        assert "pulse_note" in result
        assert "metric_tension" in result
        assert "metric_tension_state" in result
        assert "metric_tension_note" in result


# ── Active-Frame Silence Stats ────────────────────────────────────────────────


class TestActiveFrameStats:
    """perceive.py should report active-frame stats alongside whole-track averages."""

    def _make_perception_summary(self, silence_pct, attention_active=0.8, attention_whole=0.4):
        """Build a minimal perception summary dict as if returned by generate_perception_stream."""
        return {
            "mean_attention": attention_whole,
            "mean_pattern": 0.7,
            "attention_range": [0.1, 0.9],
            "total_silence_sec": 30.0,
            "silent_duration_sec": 30.0,
            "active_duration_sec": 70.0,
            "silence_pct": silence_pct,
            "mean_attention_active": attention_active,
            "mean_pattern_active": 0.85,
            "attention_range_active": [0.5, 0.9],
            "pattern_break_count": 4,
            "pattern_break_counts": {
                "pattern_break": 2,
                "attention_drop": 1,
                "attention_gain": 0,
                "silence": 1,
            },
            "pressure_building_pct": 40.0,
            "pressure_releasing_pct": 30.0,
            "pressure_sustaining_pct": 30.0,
        }

    def test_active_frame_fields_present(self):
        s = self._make_perception_summary(silence_pct=33.0)
        assert "active_duration_sec" in s
        assert "silent_duration_sec" in s
        assert "silence_pct" in s
        assert "mean_attention_active" in s
        assert "mean_pattern_active" in s

    def test_pattern_break_counts_split(self):
        s = self._make_perception_summary(silence_pct=5.0)
        pbc = s["pattern_break_counts"]
        assert "pattern_break" in pbc
        assert "attention_drop" in pbc
        assert "attention_gain" in pbc
        assert "silence" in pbc
        assert sum(pbc.values()) == s["pattern_break_count"]

    def test_catalog_uses_active_attention_when_silence_high(self):
        """When silence_pct >= threshold, catalog should index active-frame attention."""
        from galdr.catalog import CatalogState
        from galdr.constants import ACTIVE_FRAME_SILENCE_PCT_THRESHOLD

        cat = CatalogState(analysis_dir="/tmp", catalog_dir="/tmp/cat-test")
        perception = {"summary": self._make_perception_summary(
            silence_pct=ACTIVE_FRAME_SILENCE_PCT_THRESHOLD + 5.0,
            attention_active=0.80,
            attention_whole=0.40,
        )}
        cat.index_track("test-silence-track", perception=perception)
        indexed = cat.tracks["test-silence-track"]
        # Should use active-frame attention for catalog ranking
        assert indexed["mean_attention"] == pytest.approx(0.80, abs=0.01)

    def test_catalog_uses_whole_attention_when_silence_low(self):
        from galdr.catalog import CatalogState
        from galdr.constants import ACTIVE_FRAME_SILENCE_PCT_THRESHOLD

        cat = CatalogState(analysis_dir="/tmp", catalog_dir="/tmp/cat-test2")
        perception = {"summary": self._make_perception_summary(
            silence_pct=ACTIVE_FRAME_SILENCE_PCT_THRESHOLD - 5.0,
            attention_active=0.80,
            attention_whole=0.40,
        )}
        cat.index_track("test-quiet-track", perception=perception)
        indexed = cat.tracks["test-quiet-track"]
        # Should use whole-track attention (silence not significant)
        assert indexed["mean_attention"] == pytest.approx(0.40, abs=0.01)


# ── SM-300 LUFS Pressure ───────────────────────────────────────────────────────


class TestLufsPressureMotion:
    def _tone(self, amp=0.2, duration_sec=6.0, sr=22050):
        import numpy as np
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
        return (np.sin(2 * np.pi * 440 * t) * amp).astype(np.float32), sr

    def test_loudness_treats_silence_as_silence_aware(self):
        import numpy as np
        from galdr.perceive import compute_loudness

        sr = 22050
        y = np.zeros(sr * 6, dtype=np.float32)
        loudness = compute_loudness(y, sr, 6.0)

        assert loudness["integrated_lufs"] is None
        assert loudness["silence_mask"].all()
        assert np.allclose(loudness["pressure"], 0.0)

    def test_steady_loudness_sustains(self):
        import numpy as np
        from galdr.perceive import compute_loudness

        y, sr = self._tone(amp=0.2)
        loudness = compute_loudness(y, sr, 6.0)

        assert loudness["integrated_lufs"] is not None
        assert not loudness["silence_mask"].all()
        assert float(np.mean(np.abs(loudness["pressure"]))) < 0.2

    def test_building_pressure_goes_positive(self):
        import numpy as np
        from galdr.perceive import compute_loudness

        sr = 22050
        t = np.linspace(0, 8.0, sr * 8, endpoint=False)
        amp = np.linspace(0.03, 0.5, len(t))
        y = (np.sin(2 * np.pi * 440 * t) * amp).astype(np.float32)
        loudness = compute_loudness(y, sr, 8.0)

        assert float(np.mean(loudness["pressure"][2:-2])) > 0.25

    def test_release_pressure_goes_negative(self):
        import numpy as np
        from galdr.perceive import compute_loudness

        sr = 22050
        t = np.linspace(0, 8.0, sr * 8, endpoint=False)
        amp = np.linspace(0.5, 0.03, len(t))
        y = (np.sin(2 * np.pi * 440 * t) * amp).astype(np.float32)
        loudness = compute_loudness(y, sr, 8.0)

        assert float(np.mean(loudness["pressure"][2:-2])) < -0.25

    def test_perception_stream_keeps_rms_and_adds_lufs_pressure_fields(self):
        from galdr.perceive import compute_perception

        y, sr = self._tone(amp=0.2)
        report = compute_perception(y, sr, "steady-tone")
        entry = report["stream"][0]
        summary = report["summary"]

        assert "weight" in entry
        assert "loudness_lufs" in entry
        assert "pressure_lufs_delta" in entry
        assert "pressure_state" in entry
        assert "body" in entry
        assert "body_state" in entry
        assert "weight" in entry
        assert "weight_state" in entry
        for field in (
            "groove_comfort",
            "accent_phase_drift",
            "expectation_debt",
            "release_force",
            "section_gravity",
            "body_capture",
            "body_comfort",
            "surface_density",
        ):
            assert field in entry
            assert 0.0 <= entry[field] <= 1.0
            assert f"mean_{field}" in summary
            assert f"peak_{field}" in summary
        event_entries = [e for e in report["stream"] if "event" in e]
        assert event_entries
        assert "event_note" in event_entries[0]
        assert "integrated_lufs" in summary
        assert summary["integrated_lufs"] is not None

    def test_assembled_metrics_use_pressure_language_not_lufs_first(self):
        from galdr.assemble import assemble_prompt

        analysis = {
            "report": {"duration_seconds": 60.0, "detected_pulse_bpm": 90.0, "felt_pulse_bpm": 90.0, "pulse": 0.8},
            "perception": {
                "summary": {
                    "mean_attention": 0.5,
                    "mean_pattern": 0.8,
                    "pressure_building_pct": 45.0,
                    "pressure_releasing_pct": 35.0,
                    "pressure_sustaining_pct": 20.0,
                    "integrated_lufs": -18.5,
                    "loudness_silence_pct": 10.0,
                }
            },
        }
        prompt = assemble_prompt(analysis, mode="blind")

        assert "pressure building" in prompt
        assert "releasing" in prompt
        assert "silence-aware" in prompt
        assert "LUFS" not in prompt

    def test_assembled_metrics_include_local_stream_metrics(self):
        from galdr.assemble import assemble_prompt

        analysis = {
            "report": {"duration_seconds": 60.0, "detected_pulse_bpm": 90.0, "felt_pulse_bpm": 90.0, "pulse": 0.8},
            "perception": {
                "summary": {
                    "mean_attention": 0.5,
                    "mean_pattern": 0.8,
                    "pressure_building_pct": 45.0,
                    "pressure_releasing_pct": 35.0,
                    "pressure_sustaining_pct": 20.0,
                    "mean_groove_comfort": 0.42,
                    "peak_groove_comfort": 0.73,
                    "mean_accent_phase_drift": 0.19,
                    "peak_accent_phase_drift": 0.64,
                    "mean_expectation_debt": 0.31,
                    "peak_expectation_debt": 0.88,
                    "mean_release_force": 0.11,
                    "peak_release_force": 0.57,
                    "mean_section_gravity": 0.55,
                    "peak_section_gravity": 0.91,
                    "mean_body_capture": 0.62,
                    "peak_body_capture": 0.84,
                    "mean_body_comfort": 0.38,
                    "peak_body_comfort": 0.65,
                    "mean_surface_density": 0.25,
                    "peak_surface_density": 0.79,
                }
            },
        }
        prompt = assemble_prompt(analysis, mode="blind")

        assert "Local stream metrics:" in prompt
        assert "Groove comfort mean 0.420, peak 0.730" in prompt
        assert "Body capture mean 0.620, peak 0.840" in prompt
        assert "Body comfort mean 0.380, peak 0.650" in prompt
        assert "Expectation debt mean 0.310, peak 0.880" in prompt


    def test_assembled_timeline_includes_sustained_state_spans(self):
        from galdr.assemble import assemble_prompt

        analysis = {
            "report": {"duration_seconds": 60.0, "detected_pulse_bpm": 120.0, "felt_pulse_bpm": 120.0, "pulse": 0.9},
            "perception": {
                "summary": {"mean_attention": 0.9, "mean_pattern": 0.95},
                "sustained_state_spans": [
                    {
                        "start": 10.0,
                        "end": 40.0,
                        "type": "locked_engine",
                        "description": "locked engine; expectation debt accumulating",
                        "peak_expectation_debt": 0.91,
                        "peak_accent_phase_drift": 0.82,
                        "mean_body_capture": 0.70,
                        "mean_body_comfort": 0.44,
                    }
                ],
                "pattern_breaks": [],
            },
        }

        prompt = assemble_prompt(analysis, mode="blind")

        assert "0:10–0:40 — locked engine; expectation debt accumulating" in prompt
        assert "body capture 0.700 / comfort 0.440" in prompt

# ── Rhythm Body-Entrainment ──────────────────────────────────────────────────


def test_compute_body_separates_body_lock_from_raw_tempo():
    from galdr.analyze import compute_body

    locked = compute_body(
        duration=120.0,
        beat_count=240,
        pulse=0.94,
        pulse_confidence=0.92,
        pulse_ambiguous=False,
        texture=0.62,
        onsets_per_second=3.2,
    )
    loose = compute_body(
        duration=120.0,
        beat_count=240,
        pulse=0.94,
        pulse_confidence=0.92,
        pulse_ambiguous=False,
        texture=0.05,
        onsets_per_second=0.15,
    )

    assert locked["body"] > loose["body"]
    assert locked["body_state"] == "locked"
    assert loose["body_state"] in {"weak", "emerging"}
    assert "groove" not in locked["entrainment_note"]


def test_compute_body_damps_ambiguous_pulse():
    from galdr.analyze import compute_body

    clear = compute_body(
        duration=120.0,
        beat_count=220,
        pulse=0.88,
        pulse_confidence=0.8,
        pulse_ambiguous=False,
        texture=0.5,
        onsets_per_second=2.5,
    )
    ambiguous = compute_body(
        duration=120.0,
        beat_count=220,
        pulse=0.88,
        pulse_confidence=0.8,
        pulse_ambiguous=True,
        texture=0.5,
        onsets_per_second=2.5,
    )

    assert ambiguous["body"] < clear["body"]
    assert "ambiguous/alternate-pulse" in ambiguous["entrainment_note"]


def test_compute_weight_separates_drag_from_motor_lock():
    from galdr.analyze import compute_weight

    drag = compute_weight(
        pulse=0.95,
        pulse_confidence=0.60,
        body=0.52,
        texture=0.31,
        onsets_per_second=1.7,
        harmonic_weight=0.21,
        percussive_weight=0.095,
        dynamic_range_ratio=1000.0,
    )
    motor = compute_weight(
        pulse=0.97,
        pulse_confidence=0.90,
        body=0.78,
        texture=0.35,
        onsets_per_second=4.2,
        harmonic_weight=0.12,
        percussive_weight=0.065,
        dynamic_range_ratio=1000.0,
    )

    assert drag["weight"] > motor["weight"]
    assert drag["weight_state"] in {"suspended", "heavy"}
    assert motor["weight_state"] == "light"


def test_assembled_metrics_include_body_language():
    from galdr.assemble import assemble_prompt

    analysis = {
        "report": {
            "duration_seconds": 60.0,
            "detected_pulse_bpm": 120.0,
            "felt_pulse_bpm": 120.0,
            "pulse": 0.93,
            "body": 0.81,
            "body_state": "locked",
            "entrainment_note": "strong body-lock with real percussive support",
            "weight": 0.22,
            "weight_state": "light",
            "metric_tension": 0.61,
            "metric_tension_state": "high",
            "metric_tension_note": "stable pulse with strong competing metric evidence",
        },
        "perception": {"summary": {"mean_attention": 0.7, "mean_pattern": 0.9}},
    }

    prompt = assemble_prompt(analysis, mode="blind")

    assert "Body: 0.810 (locked)" in prompt
    assert "strong body-lock" in prompt
    assert "Weight: 0.220 (light)" in prompt
    assert "Metric tension: 0.610 (high)" in prompt
    assert "competing metric evidence" in prompt


# ── Silence Re-entry / Recovery ───────────────────────────────────────────────


def test_compute_silence_reentries_classifies_post_gap_return():
    from galdr.perceive import compute_silence_reentries

    times = np.arange(0.0, 10.0, 0.5)
    attention = np.array([0.8, 0.82, 0.81, 0.8, 0.1, 0.1, 0.76, 0.82, 0.84, 0.84, 0.84, 0.84, 0.84, 0.84, 0.84, 0.84, 0.84, 0.84, 0.84, 0.84])
    pressure = np.array([0.02, 0.02, 0.01, 0.0, -0.5, -0.5, 0.15, 0.12, 0.03, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02])
    loudness_delta = np.zeros_like(times)
    silences = [{"start": 4.0, "end": 5.0, "duration": 1.0, "depth_db": -80.0}]

    reentries = compute_silence_reentries(silences, times, attention, pressure, loudness_delta, 10.0)

    assert len(reentries) == 1
    event = reentries[0]
    assert event["reentry_shape"] == "continuation"
    assert event["boundary_position"] == "internal"
    assert event["reentry_time"] == 5.0
    assert event["recovered"] is True
    assert event["recovery_time_sec"] is not None
    assert "reentry_force" in event


def test_perception_report_exposes_silence_reentries():
    from galdr.perceive import compute_perception

    sr = 22050
    tone_a = np.sin(2 * np.pi * 220 * np.linspace(0, 1.0, sr, endpoint=False)) * 0.3
    gap = np.zeros(int(sr * 0.8))
    tone_b = np.sin(2 * np.pi * 330 * np.linspace(0, 1.2, int(sr * 1.2), endpoint=False)) * 0.35
    y = np.concatenate([tone_a, gap, tone_b]).astype(np.float32)

    report = compute_perception(y, sr, "silence-return")

    assert report["silence_reentries"]
    assert "silence_reentry_count" in report["summary"]
    assert "silence_reentry_shapes" in report["summary"]
    assert "silence_boundary_positions" in report["summary"]
    silence_breaks = [b for b in report["pattern_breaks"] if b["type"] == "silence"]
    assert silence_breaks
    assert "reentry_shape" in silence_breaks[0]
    assert "boundary_position" in silence_breaks[0]


def test_compute_silence_reentries_marks_boundaries_separately():
    from galdr.perceive import compute_silence_reentries

    times = np.arange(0.0, 12.0, 0.5)
    attention = np.full_like(times, 0.75, dtype=float)
    pressure = np.zeros_like(times)
    loudness_delta = np.zeros_like(times)
    silences = [
        {"start": 0.0, "end": 1.5, "duration": 1.5, "depth_db": -80.0},
        {"start": 9.4, "end": 11.5, "duration": 2.1, "depth_db": -80.0},
    ]

    reentries = compute_silence_reentries(silences, times, attention, pressure, loudness_delta, 12.0)

    assert reentries[0]["boundary_position"] == "opening"
    assert reentries[0]["reentry_shape"] == "entry_preparation"
    assert reentries[1]["boundary_position"] == "closing"
    assert reentries[1]["reentry_shape"] == "terminal_decay"


def test_assembled_structural_events_include_reentry_language():
    from galdr.assemble import assemble_prompt

    analysis = {
        "report": {"duration_seconds": 20.0, "detected_pulse_bpm": 80.0, "pulse": 0.7},
        "perception": {
            "summary": {
                "mean_attention": 0.6,
                "mean_pattern": 0.8,
                "pressure_building_pct": 20.0,
                "pressure_releasing_pct": 20.0,
                "pressure_sustaining_pct": 60.0,
                "integrated_lufs": -20.0,
                "loudness_silence_pct": 5.0,
                "silence_reentry_count": 1,
                "silence_reentry_shapes": {
                    "entry_preparation": 0,
                    "continuation": 1,
                    "rupture": 0,
                    "reset": 0,
                    "withdrawal": 0,
                    "terminal_decay": 0,
                },
                "silence_boundary_positions": {"opening": 0, "internal": 1, "closing": 0},
            },
            "pattern_breaks": [
                {
                    "time": 4.0,
                    "type": "silence",
                    "duration": 1.25,
                    "depth_db": -70.0,
                    "reentry_shape": "continuation",
                    "boundary_position": "internal",
                    "reentry_force": 0.12,
                    "recovery_time_sec": 0.5,
                }
            ],
        },
    }

    prompt = assemble_prompt(analysis, mode="blind")

    assert "Silence returns" in prompt
    assert "return: continuation" in prompt
    assert "re-entry force" in prompt

class TestContextConfidenceScoring:
    def test_genius_hit_rejects_unrelated_result(self):
        from galdr.fetch import _score_genius_hit

        result = _score_genius_hit(
            {
                "title": "The History of England, Vol. I, Chap. 158",
                "artist": "David Hume",
                "full_title": "The History of England, Vol. I, Chap. 158 by David Hume",
            },
            artist="Band of the Atholl Highlanders",
            title="The Atholl Highlanders",
        )
        assert result["confidence"] == "rejected"
        assert result["use_in_prompt"] is False

    def test_wikipedia_song_partial_match_can_be_low_but_usable(self):
        from galdr.fetch import _score_wikipedia_result

        result = _score_wikipedia_result(
            {
                "found": True,
                "title": "Atholl Highlanders",
                "extract": "The Atholl Highlanders is a Scottish private ceremonial infantry regiment.",
            },
            expected_name="The Atholl Highlanders",
            entity_type="song",
        )
        assert result["confidence"] in {"medium", "high"}
        assert result["use_in_prompt"] is True

    def test_wikipedia_disambiguation_stub_rejected_even_with_title_match(self):
        from galdr.fetch import _score_wikipedia_result

        result = _score_wikipedia_result(
            {
                "found": True,
                "title": "Teardrop",
                "extract": "Teardrop or Teardrops may refer to:",
            },
            expected_name="Teardrop",
            entity_type="song",
        )
        assert result["confidence"] == "rejected"
        assert result["use_in_prompt"] is False

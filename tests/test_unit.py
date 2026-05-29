"""Unit tests for galdr — pure functions and pipeline logic. No audio required."""

import json
import math
import numpy as np
import pytest

from galdr.arc import derive_arc_scales, derive_arc_spans, normalize_stream, select_arc_scale


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


# ── arc helpers ───────────────────────────────────────────────────────


def test_normalize_stream_adapts_legacy_rows():
    stream = [
        {
            "t": 0.0,
            "momentum": 0.8,
            "pattern_lock": 0.7,
            "breath": 0.35,
            "energy": 0.6,
            "h_energy": 0.7,
            "p_energy": 0.2,
        }
    ]

    frames = normalize_stream(stream)

    assert len(frames) == 1
    assert frames[0].attention == pytest.approx(0.8)
    assert frames[0].pattern == pytest.approx(0.7)
    assert frames[0].pressure == pytest.approx(0.35)
    assert frames[0].body == pytest.approx(0.76)
    assert frames[0].weight == pytest.approx(0.69)
    assert frames[0].silence == 0.0


def test_normalize_stream_preserves_explicit_legacy_silence_bool():
    stream = [
        {"t": 0.0, "momentum": 0.0, "pattern_lock": 1.0, "silence": True},
        {"t": 0.5, "momentum": 0.5, "pattern_lock": 1.0, "silence": False},
    ]

    frames = normalize_stream(stream)

    assert [frame.silence for frame in frames] == [1.0, 0.0]


def test_normalize_stream_preserves_listener_state_rows():
    stream = [
        {
            "time": 4.0,
            "attention": 0.91,
            "pattern": 0.88,
            "pressure": -0.27,
            "body": 0.73,
            "weight": 0.31,
            "silence": 0.0,
        }
    ]

    frames = normalize_stream(stream)

    assert frames[0].t == pytest.approx(4.0)
    assert frames[0].attention == pytest.approx(0.91)
    assert frames[0].pattern == pytest.approx(0.88)
    assert frames[0].pressure == pytest.approx(-0.27)
    assert frames[0].body == pytest.approx(0.73)
    assert frames[0].weight == pytest.approx(0.31)


def test_derive_arc_spans_collapses_contiguous_states():
    stream = [
        {"t": 0.0, "attention": 0.55, "pattern": 0.58, "pressure": 0.35, "body": 0.42, "weight": 0.28, "silence": 0.0},
        {"t": 1.0, "attention": 0.60, "pattern": 0.62, "pressure": 0.30, "body": 0.50, "weight": 0.30, "silence": 0.0},
        {"t": 2.0, "attention": 0.78, "pattern": 0.82, "pressure": 0.02, "body": 0.72, "weight": 0.34, "silence": 0.0},
        {"t": 3.0, "attention": 0.80, "pattern": 0.84, "pressure": 0.00, "body": 0.75, "weight": 0.36, "silence": 0.0},
        {"t": 4.0, "attention": 0.65, "pattern": 0.61, "pressure": -0.33, "body": 0.58, "weight": 0.39, "silence": 0.0},
        {"t": 5.0, "attention": 0.59, "pattern": 0.55, "pressure": -0.28, "body": 0.54, "weight": 0.42, "silence": 0.0},
        {"t": 6.0, "attention": 0.12, "pattern": 0.10, "pressure": 0.01, "body": 0.18, "weight": 0.22, "silence": 1.0},
        {"t": 7.0, "attention": 0.10, "pattern": 0.08, "pressure": 0.00, "body": 0.16, "weight": 0.20, "silence": 1.0},
    ]

    spans = derive_arc_spans(stream)

    assert [span["label"] for span in spans] == ["building", "held", "releasing", "emptying"]
    assert spans[0]["start"] == pytest.approx(0.0)
    assert spans[0]["end"] == pytest.approx(1.0)
    assert spans[1]["mean_body"] == pytest.approx(0.735)
    assert spans[-1]["silence_ratio"] == pytest.approx(1.0)



def test_arc_scales_preserve_detail_but_coalesce_shallow_chatter():
    stream = []
    pressures = [0.23, 0.0, -0.23, 0.0] * 10
    for i, pressure in enumerate(pressures):
        stream.append({"t": float(i), "attention": 0.92, "pattern": 0.95, "pressure": pressure, "body": 0.58, "weight": 0.44})

    scales = derive_arc_scales(stream)
    selected, reason = select_arc_scale(scales)

    assert len(scales["detail"]) > len(scales["macro"])
    assert selected == "macro"
    assert "chatter" in reason or "shallow" in reason or "whole-form" in reason


def test_arc_scale_selector_keeps_real_high_contrast_detail():
    stream = []
    for i in range(20):
        if i % 2 == 0:
            stream.append({"t": float(i), "attention": 0.95, "pattern": 0.92, "pressure": 0.85, "body": 0.70})
        else:
            stream.append({"t": float(i), "attention": 0.30, "pattern": 0.40, "pressure": -0.85, "body": 0.20})

    scales = derive_arc_scales(stream)
    selected, reason = select_arc_scale(scales)

    assert selected == "detail"
    assert "contrast" in reason

def test_arc_archetype_splits_plateau_subtypes():
    from galdr.assemble import _arc_archetype

    martial = {
        "total_frames": 100,
        "frame_counts": {"held": 94, "emptying": 6},
        "weighted": {"mean_body": 0.70},
        "transitions": {("held", "emptying"): 1},
        "longest": [{"frame_count": 94, "label": "held"}],
        "span_count": 3,
        "final_label": "emptying",
    }
    narrative = {
        "total_frames": 100,
        "frame_counts": {"held": 88, "emptying": 7, "releasing": 5},
        "weighted": {"mean_body": 0.45},
        "transitions": {("held", "releasing"): 1, ("releasing", "emptying"): 1},
        "longest": [{"frame_count": 88, "label": "held"}],
        "span_count": 7,
        "final_label": "emptying",
    }

    assert _arc_archetype(martial)[0] == "martial/body lock"
    assert _arc_archetype(narrative)[0] == "suspended narrative gravity"

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

    def test_lyrics_include_source_provenance(self):
        analysis = self._minimal_analysis()
        context = {
            "lyrics": {
                "source": "genius",
                "genius_url": "https://genius.example/song",
                "genius_text": "clean lyric text",
                "full_text": "clean lyric text",
            }
        }
        result = self.fn(analysis, context=context, mode="lyrics")
        assert "Source: Genius (https://genius.example/song)" in result
        assert "clean lyric text" in result

    def test_local_vtt_caption_source_provenance(self):
        analysis = self._minimal_analysis()
        context = {
            "lyrics": {
                "source": "local-vtt-captions",
                "captions_file": "/tmp/song.en.vtt",
                "caption_lines": [{"ts": "0:01", "text": "caption words"}],
                "full_text": "caption words",
            }
        }
        result = self.fn(analysis, context=context, mode="lyrics")
        assert "Source: local VTT captions (/tmp/song.en.vtt)" in result
        assert "[0:01]  caption words" in result

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

    def test_stream_arc_structure_is_included_for_experience_prompt(self):
        stream = []
        for i in range(12):
            stream.append({"t": i * 1.0, "attention": 0.90, "pattern": 0.95, "pressure": 0.50, "body": 0.70})
        for i in range(12, 16):
            stream.append({"t": i * 1.0, "attention": 0.82, "pattern": 0.88, "pressure": 0.72, "body": 0.68})
        for i in range(16, 20):
            stream.append({"t": i * 1.0, "attention": 0.70, "pattern": 0.72, "pressure": 0.22, "body": 0.50})

        analysis = {
            "report": {"duration_seconds": 20.0, "detected_pulse_bpm": 90.0, "felt_pulse_bpm": 90.0, "pulse": 0.8},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": stream,
            },
        }

        prompt = self.fn(analysis, mode="blind")

        assert "### Arc structure" in prompt
        assert "Felt mechanism:" in prompt
        assert "Pattern scale selected:" in prompt
        assert "Selected span count:" in prompt
        assert "State distribution:" in prompt
        assert "Longest spans:" in prompt
        assert "Coarse timeline:" in prompt
        assert "Never mention galdr" in prompt
        assert "metrics, percentages, frame counts, span counts" in prompt
        assert "Translate them into felt experience" in prompt


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
        import numpy as np
        from galdr.perceive import compute_perception

        # Tone with a sudden amplitude jump so onset/spectral disruption has a
        # real transient to detect — a perfectly steady sine produces no
        # spectral novelty and would never exercise the event code path.
        y, sr = self._tone(amp=0.15, duration_sec=8.0)
        mid = len(y) // 2
        y[mid:] = (y[mid:] * 3.0).astype(np.float32)
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


def test_assembled_prompt_omits_ordinary_closing_silence_from_prose_events():
    from galdr.assemble import assemble_prompt

    analysis = {
        "report": {"duration_seconds": 120.0, "detected_pulse_bpm": 120.0, "pulse": 0.8},
        "perception": {
            "summary": {
                "mean_attention": 0.8,
                "mean_pattern": 0.9,
                "pressure_building_pct": 10.0,
                "pressure_releasing_pct": 10.0,
                "pressure_sustaining_pct": 80.0,
                "silence_reentry_count": 1,
                "silence_reentry_shapes": {
                    "entry_preparation": 0,
                    "continuation": 0,
                    "rupture": 0,
                    "reset": 0,
                    "withdrawal": 0,
                    "terminal_decay": 1,
                },
                "silence_boundary_positions": {"opening": 0, "internal": 0, "closing": 1},
            },
            "pattern_breaks": [
                {
                    "time": 112.0,
                    "type": "silence",
                    "duration": 8.0,
                    "depth_db": -80.0,
                    "reentry_shape": "terminal_decay",
                    "boundary_position": "closing",
                }
            ],
        },
    }

    prompt = assemble_prompt(analysis, mode="blind")

    assert "Silence returns" not in prompt
    assert "terminal_decay" not in prompt
    assert "silence 8.00s" not in prompt


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

    def test_wikipedia_song_rejects_title_match_without_expected_artist(self):
        from galdr.fetch import _score_wikipedia_result

        result = _score_wikipedia_result(
            {
                "found": True,
                "title": "Alright (Supergrass song)",
                "extract": "\"Alright\" is a song by English alternative rock band Supergrass.",
            },
            expected_name="Alright",
            entity_type="song",
            expected_artist="Kendrick Lamar",
        )

        assert result["confidence"] == "rejected"
        assert result["use_in_prompt"] is False
        assert "song context lacks expected artist evidence" in result["match_reasons"]

    def test_wikipedia_song_accepts_title_match_with_expected_artist(self):
        from galdr.fetch import _score_wikipedia_result

        result = _score_wikipedia_result(
            {
                "found": True,
                "title": "Alright (Kendrick Lamar song)",
                "extract": "\"Alright\" is a song by American rapper Kendrick Lamar.",
            },
            expected_name="Alright",
            entity_type="song",
            expected_artist="Kendrick Lamar",
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


    def test_wikipedia_artist_prefers_music_qualified_page_over_disambiguation(self, monkeypatch):
        import galdr.fetch as fetch

        def fake_intro(title):
            if title == "Machine Head (band)":
                return {"found": True, "title": "Machine Head (band)", "extract": "Machine Head is an American heavy metal band from Oakland, California."}
            if title == "Machine Head":
                return {"found": True, "title": "Machine head", "extract": "Machine head may refer to:"}
            return {"found": False}

        monkeypatch.setattr(fetch, "fetch_wikipedia_intro", fake_intro)

        result = fetch.fetch_wikipedia_context("Machine Head", entity_type="artist")

        assert result["title"] == "Machine Head (band)"
        assert result["use_in_prompt"] is True

    def test_genius_sanitizer_removes_live_ticket_cta(self):
        from galdr.fetch import _sanitize_lyric_lines

        lines = _sanitize_lyric_lines([
            "See Machine Head LiveGet tickets as low as $67",
            "This is real lyric text",
            "Embed",
        ])

        assert lines == ["This is real lyric text"]

    def test_genius_translation_hit_rejected_by_title_bracket(self):
        from galdr.fetch import _is_genius_translation_hit

        hit = {
            "title": "Wardruna - Helvegen (English Translation)",
            "artist": "Genius English Translations",
            "full_title": "Wardruna - Helvegen (English Translation) by Genius English Translations",
            "url": "https://genius.com/Genius-english-translations-wardruna-helvegen-english-translation-lyrics",
        }
        is_trans, reason = _is_genius_translation_hit(hit)
        assert is_trans is True
        assert "translation marker in title" in reason

    def test_genius_translation_hit_rejected_by_artist_name(self):
        from galdr.fetch import _is_genius_translation_hit

        hit = {
            "title": "Helvegen",
            "artist": "Genius English Translations",
            "full_title": "Wardruna - Helvegen (English Translation) by Genius English Translations",
            "url": "https://genius.com/Genius-english-translations-wardruna-helvegen-english-translation-lyrics",
        }
        is_trans, reason = _is_genius_translation_hit(hit)
        assert is_trans is True
        assert "translation artist" in reason

    def test_genius_translation_hit_accepted_when_clean(self):
        from galdr.fetch import _is_genius_translation_hit

        hit = {
            "title": "Helvegen",
            "artist": "Wardruna",
            "full_title": "Wardruna - Helvegen",
            "url": "https://genius.com/Wardruna-helvegen-lyrics",
        }
        is_trans, reason = _is_genius_translation_hit(hit)
        assert is_trans is False
        assert reason is None

    def test_genius_search_prefers_non_translation_hit(self):
        from galdr.fetch import _genius_search
        import galdr.fetch as fetch

        original_urlopen = fetch.urllib.request.urlopen

        def fake_urlopen(req, *args, **kwargs):
            return __import__('io').BytesIO(__import__('json').dumps({
                "response": {
                    "hits": [
                        {
                            "result": {
                                "path": "/Genius-english-translations-wardruna-helvegen-english-translation-lyrics",
                                "title": "Wardruna - Helvegen (English Translation)",
                                "full_title": "Wardruna - Helvegen (English Translation) by Genius English Translations",
                                "primary_artist": {"name": "Genius English Translations"},
                            }
                        },
                        {
                            "result": {
                                "path": "/Wardruna-helvegen-lyrics",
                                "title": "Helvegen",
                                "full_title": "Wardruna - Helvegen",
                                "primary_artist": {"name": "Wardruna"},
                            }
                        },
                    ]
                }
            }).encode())

        fetch.urllib.request.urlopen = fake_urlopen
        try:
            result = _genius_search("Wardruna", "Helvegen")
            assert result is not None
            assert result["artist"] == "Wardruna"
            assert result["url"] == "https://genius.com/Wardruna-helvegen-lyrics"
            assert len(result.get("rejected_translation_hits", [])) == 1
            assert "translation marker" in result["rejected_translation_hits"][0]["reason"]
        finally:
            fetch.urllib.request.urlopen = original_urlopen


def test_salience_guide_is_advisory_and_preserves_metric_detail():
    from galdr.assemble import assemble_prompt

    analysis = {
        "report": {
            "duration_seconds": 240.0,
            "detected_pulse_bpm": 152.0,
            "felt_pulse_bpm": 152.0,
            "pulse_confidence": 0.82,
            "pulse": 0.96,
            "body": 0.60,
            "body_state": "emerging",
            "weight": 0.45,
            "weight_state": "suspended",
            "metric_tension": 0.36,
            "metric_tension_state": "present",
            "metric_tension_note": "stable pulse with audible alternate metric pressure",
        },
        "perception": {
            "summary": {
                "mean_attention": 0.94,
                "mean_pattern": 0.96,
                "pressure_building_pct": 4.0,
                "pressure_releasing_pct": 5.0,
                "pressure_sustaining_pct": 91.0,
                "mean_body_capture": 0.72,
                "peak_body_capture": 0.88,
                "mean_body_comfort": 0.31,
                "peak_body_comfort": 0.45,
                "mean_groove_comfort": 0.31,
                "peak_groove_comfort": 0.45,
                "mean_surface_density": 0.38,
                "peak_surface_density": 0.55,
                "peak_release_force": 0.20,
            }
        },
    }

    prompt = assemble_prompt(analysis, mode="blind")

    assert "Metric tension: 0.360 (present)" in prompt
    assert "Local stream metrics:" in prompt
    assert "Perceptual salience guide (advisory, not a filter):" in prompt
    assert "Primary contract: lock" in prompt
    assert "Secondary contracts: grid" in prompt
    assert "Force axes:" in prompt
    assert "body_relation=captured" in prompt
    assert "comfort_relation=resisted" in prompt
    assert "Technical underlayer: metric tension" in prompt
    assert "do not hide technically true secondary evidence" in prompt


def test_salience_factorizes_minimal_grid_from_mass_lock():
    from galdr.salience import synthesize_salience

    analysis = {
        "report": {
            "pulse_confidence": 0.86,
            "pulse": 0.96,
            "body": 0.68,
            "weight": 0.24,
            "metric_tension": 0.08,
        },
        "perception": {
            "summary": {
                "mean_attention": 0.94,
                "mean_pattern": 0.95,
                "pressure_building_pct": 2.0,
                "pressure_releasing_pct": 6.0,
                "pressure_sustaining_pct": 62.0,
                "mean_body_capture": 0.78,
                "mean_body_comfort": 0.42,
                "mean_groove_comfort": 0.42,
                "mean_surface_density": 0.31,
                "mean_accent_phase_drift": 0.82,
            }
        },
    }

    salience = synthesize_salience(analysis)

    assert salience["primary_contract"] == "grid"
    assert salience["force_axes"]["body_relation"]["value"] == "captured"
    assert salience["force_axes"]["comfort_relation"]["value"] == "resisted"
    assert salience["force_axes"]["weight"]["value"] == "present"
    assert "tight minimal grid" in salience["prose_hints"]
    assert "heavy lock" not in salience["prose_hints"]


def test_salience_factorizes_ambient_field_as_force_without_motor_lock():
    from galdr.salience import synthesize_salience

    analysis = {
        "report": {
            "pulse_confidence": 0.10,
            "pulse": 0.0,
            "body": 0.02,
            "weight": 0.71,
            "weight_state": "heavy",
            "texture": 0.10,
            "metric_tension": 0.0,
        },
        "perception": {
            "summary": {
                "mean_attention": 0.0,
                "mean_pattern": 0.98,
                "pressure_building_pct": 0.0,
                "pressure_releasing_pct": 4.0,
                "pressure_sustaining_pct": 55.0,
                "mean_body_capture": 0.02,
                "mean_body_comfort": 0.02,
                "mean_groove_comfort": 0.02,
                "mean_surface_density": 0.08,
                "loudness_silence_pct": 12.0,
            }
        },
    }

    salience = synthesize_salience(analysis)

    assert salience["primary_contract"] == "field"
    assert salience["force_axes"]["body_relation"]["value"] == "absent"
    assert salience["force_axes"]["weight"]["value"] == "heavy"
    assert "held field" in salience["prose_hints"]
    assert "force without motor lock" in salience["prose_hints"]


def test_salience_distinguishes_braced_mass_from_impact_mass_lock():
    from galdr.salience import synthesize_salience

    base_analysis = {
        "report": {
            "pulse_confidence": 0.90,
            "pulse": 0.98,
            "body": 0.60,
            "weight": 0.43,
            "metric_tension": 0.11,
        },
        "perception": {
            "summary": {
                "mean_attention": 0.94,
                "mean_pattern": 0.96,
                "pressure_building_pct": 4.0,
                "pressure_releasing_pct": 6.0,
                "pressure_sustaining_pct": 89.0,
                "mean_body_capture": 0.65,
                "mean_body_comfort": 0.57,
                "mean_groove_comfort": 0.57,
                "mean_surface_density": 0.13,
                "mean_accent_phase_drift": 0.28,
            }
        },
    }

    impact = synthesize_salience(base_analysis)

    assert impact["primary_contract"] == "lock"
    assert "mass lock" in impact["prose_hints"]
    assert "impact mass lock" in impact["prose_hints"]
    assert "braced mass lock" not in impact["prose_hints"]

    braced_analysis = {
        **base_analysis,
        "report": {**base_analysis["report"], "body": 0.30},
        "perception": {
            "summary": {
                **base_analysis["perception"]["summary"],
                "pressure_building_pct": 42.0,
                "pressure_sustaining_pct": 22.0,
                "mean_body_comfort": 0.46,
                "mean_groove_comfort": 0.46,
            }
        },
    }

    braced = synthesize_salience(braced_analysis)

    assert braced["primary_contract"] == "lock"
    assert "mass lock" in braced["prose_hints"]
    assert "braced mass lock" in braced["prose_hints"]
    assert "impact mass lock" not in braced["prose_hints"]


def test_assemble_renders_salience_axes_without_headline_forces():
    from galdr.assemble import assemble_prompt

    analysis = {
        "report": {
            "pulse_confidence": 0.86,
            "pulse": 0.97,
            "body": 0.40,
            "weight": 0.20,
            "metric_tension": 0.16,
        },
        "perception": {
            "summary": {
                "mean_attention": 0.71,
                "mean_pattern": 0.76,
                "pressure_building_pct": 12.0,
                "pressure_releasing_pct": 12.0,
                "pressure_sustaining_pct": 76.0,
                "mean_body_capture": 0.40,
                "mean_body_comfort": 0.46,
                "mean_groove_comfort": 0.46,
                "mean_surface_density": 0.25,
                "mean_accent_phase_drift": 0.39,
            }
        },
    }

    prompt = assemble_prompt(analysis, mode="blind")

    assert "Perceptual salience guide (advisory, not a filter):" in prompt
    assert "Primary contract: balanced_listener_state" in prompt
    assert "Force axes:" in prompt
    assert "body_relation=lightly_engaged" in prompt


def test_salience_labels_plain_body_drive_pattern_hold():
    from galdr.salience import synthesize_salience

    analysis = {
        "report": {
            "pulse_confidence": 0.86,
            "pulse": 0.97,
            "body": 0.64,
            "weight": 0.32,
            "metric_tension": 0.16,
        },
        "perception": {
            "summary": {
                "mean_attention": 0.71,
                "mean_pattern": 0.87,
                "pressure_building_pct": 12.0,
                "pressure_releasing_pct": 12.0,
                "pressure_sustaining_pct": 76.0,
                "mean_body_capture": 0.58,
                "mean_body_comfort": 0.46,
                "mean_groove_comfort": 0.46,
                "mean_surface_density": 0.25,
                "mean_accent_phase_drift": 0.39,
            }
        },
    }

    salience = synthesize_salience(analysis)

    assert salience["primary_contract"] == "pattern_hold"
    assert "plain body drive" in salience["prose_hints"]
    assert salience["headline_forces"][0]["name"] == "pattern hold"


def test_salience_labels_soft_mass_lock_without_promoting_to_new_contract():
    from galdr.salience import synthesize_salience

    analysis = {
        "report": {
            "pulse_confidence": 0.91,
            "pulse": 0.98,
            "body": 0.52,
            "weight": 0.40,
            "metric_tension": 0.14,
        },
        "perception": {
            "summary": {
                "mean_attention": 0.88,
                "mean_pattern": 0.95,
                "pressure_building_pct": 22.0,
                "pressure_releasing_pct": 18.0,
                "pressure_sustaining_pct": 58.0,
                "mean_body_capture": 0.63,
                "mean_body_comfort": 0.52,
                "mean_groove_comfort": 0.52,
                "mean_surface_density": 0.30,
                "mean_accent_phase_drift": 0.56,
            }
        },
    }

    salience = synthesize_salience(analysis)

    assert salience["primary_contract"] == "lock"
    assert "mass lock" in salience["prose_hints"]
    assert "soft mass lock" in salience["prose_hints"]
    assert "braced mass lock" not in salience["prose_hints"]
    assert "impact mass lock" not in salience["prose_hints"]


# ── Boundary Candidates ──────────────────────────────────────────────────────


def _boundary_frame(
    t, *, silence=False, attention=0.8, pattern=0.9, pressure=0.0,
    body=0.5, weight=0.4, density=0.5, rms=0.08, lufs=-24.0
):
    return {
        "t": t,
        "silence": silence,
        "attention": attention,
        "pattern": pattern,
        "pressure": pressure,
        "body": body,
        "weight": weight,
        "surface_density": density,
        "rms_energy": rms,
        "loudness_lufs": lufs,
        "silence_depth_db": -70.0 if silence else -10.0,
    }


def test_boundary_candidates_are_separate_from_arc_transitions():
    from galdr.boundary import derive_boundary_candidates

    stream = []
    for t in range(0, 6):
        stream.append(_boundary_frame(t, pressure=0.05, density=0.7))
    for t in range(6, 12):
        stream.append(
            _boundary_frame(
                t, silence=True, attention=0.1, pattern=0.2, pressure=-0.4,
                density=0.0, rms=0.001, lufs=-68.0
            )
        )
    for t in range(12, 20):
        stream.append(_boundary_frame(t, attention=0.92, pattern=0.96, pressure=0.42, body=0.8, density=0.8))

    candidates = derive_boundary_candidates(stream, min_gap_sec=3.0, context_sec=4.0)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["start"] == 6.0
    assert candidate["end"] == 12.0
    assert candidate["kind"] == "probable_boundary"
    assert candidate["reset_strength"] >= 0.28
    assert candidate["confidence"] >= 0.6


def test_boundary_candidates_accept_wrapped_stream_payload_and_hop():
    from galdr.boundary import derive_boundary_candidates

    stream = []
    for t in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]:
        stream.append(_boundary_frame(t, pressure=0.05, density=0.7))
    for t in [3.0, 3.5, 4.0, 4.5, 5.0, 5.5]:
        stream.append(
            _boundary_frame(
                t, silence=True, attention=0.1, pattern=0.2, pressure=-0.4,
                density=0.0, rms=0.001, lufs=-68.0
            )
        )
    for t in [6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5]:
        stream.append(_boundary_frame(t, attention=0.92, pattern=0.96, pressure=0.42, body=0.8, density=0.8))

    candidates = derive_boundary_candidates({"stream_hop_sec": 0.5, "stream": stream}, min_gap_sec=3.0, context_sec=2.0)

    assert len(candidates) == 1
    assert candidates[0]["start"] == 3.0
    assert candidates[0]["end"] == 6.0
    assert candidates[0]["kind"] == "probable_boundary"


def test_boundary_candidates_mark_opening_and_closing_gaps():
    from galdr.boundary import derive_boundary_candidates

    stream = []
    for t in range(0, 4):
        stream.append(
            _boundary_frame(t, silence=True, attention=0.0, pattern=0.0, density=0.0, rms=0.0005, lufs=-70.0)
        )
    for t in range(4, 10):
        stream.append(_boundary_frame(t))
    for t in range(10, 14):
        stream.append(
            _boundary_frame(t, silence=True, attention=0.0, pattern=0.0, density=0.0, rms=0.0005, lufs=-70.0)
        )

    candidates = derive_boundary_candidates(stream, min_gap_sec=3.0)

    assert [candidate["kind"] for candidate in candidates] == ["opening_gap", "ending_gap"]



def test_boundary_candidates_can_include_non_silent_reset_points():
    from galdr.boundary import derive_boundary_candidates

    stream = []
    for t in range(0, 8):
        stream.append(_boundary_frame(t, attention=0.9, pattern=0.96, pressure=-0.08, body=0.43, weight=0.88, density=0.06, rms=0.07, lufs=-24.0))
    for t in range(8, 16):
        stream.append(_boundary_frame(t, attention=0.97, pattern=0.99, pressure=0.08, body=0.72, weight=0.55, density=0.31, rms=0.16, lufs=-19.0))

    gap_only = derive_boundary_candidates(stream, min_gap_sec=3.0)
    with_resets = derive_boundary_candidates(stream, min_gap_sec=3.0, include_reset_points=True, reset_window_sec=4.0)

    assert gap_only == []
    assert len(with_resets) == 1
    candidate = with_resets[0]
    assert candidate["kind"] == "reset_point"
    assert candidate["duration"] == 0.0
    assert candidate["state_reset"] >= 0.11
    assert candidate["acoustic_reset"] >= 0.12


def test_rank_reset_candidates_keeps_reset_points_separate_and_spaced():
    from galdr.boundary import rank_reset_candidates

    candidates = [
        {"start": 10.0, "end": 12.0, "kind": "probable_boundary", "confidence": 0.9},
        {
            "start": 20.0,
            "end": 20.0,
            "kind": "reset_point",
            "confidence": 0.55,
            "state_reset": 0.32,
            "acoustic_reset": 0.18,
            "pressure_turn": 0.05,
            "weight_release": 0.35,
        },
        {
            "start": 31.0,
            "end": 31.0,
            "kind": "reset_point",
            "confidence": 0.70,
            "state_reset": 0.35,
            "acoustic_reset": 0.21,
            "pressure_turn": 0.22,
            "weight_release": -0.20,
        },
        {
            "start": 80.0,
            "end": 80.0,
            "kind": "reset_point",
            "confidence": 0.40,
            "state_reset": 0.11,
            "acoustic_reset": 0.10,
            "pressure_turn": 0.08,
            "weight_release": 0.02,
        },
    ]

    ranked = rank_reset_candidates(candidates, top_n=2, min_spacing_sec=18.0)

    assert [candidate["start"] for candidate in ranked] == [31.0, 80.0]
    assert all(candidate["kind"] == "reset_point" for candidate in ranked)
    assert all("rank_score" in candidate for candidate in ranked)


def test_rank_reset_candidates_can_apply_score_floor():
    from galdr.boundary import rank_reset_candidates

    candidates = [
        {
            "start": 20.0,
            "end": 20.0,
            "kind": "reset_point",
            "confidence": 0.30,
            "state_reset": 0.10,
            "acoustic_reset": 0.09,
            "pressure_turn": 0.01,
            "weight_release": 0.0,
        },
        {
            "start": 50.0,
            "end": 50.0,
            "kind": "reset_point",
            "confidence": 0.70,
            "state_reset": 0.40,
            "acoustic_reset": 0.25,
            "pressure_turn": 0.20,
            "weight_release": 0.20,
        },
    ]

    ranked = rank_reset_candidates(candidates, min_rank_score=0.35)

    assert [candidate["start"] for candidate in ranked] == [50.0]


def test_boundary_alignment_scores_known_section_starts_and_extras():
    from galdr.boundary import align_candidates_to_sections

    candidates = [
        {"start": 0.0, "end": 5.0, "kind": "opening_gap", "confidence": 0.7, "reset_strength": 0.0},
        {"start": 317.5, "end": 322.0, "kind": "probable_boundary", "confidence": 0.93, "reset_strength": 0.89},
        {"start": 610.0, "end": 635.0, "kind": "probable_boundary", "confidence": 0.95, "reset_strength": 0.78},
        {"start": 700.0, "end": 705.0, "kind": "interlude_gap", "confidence": 0.5, "reset_strength": 0.0},
    ]
    sections = [
        {"start": 0.0, "title": "Asja"},
        {"start": 318.0, "title": "Anoana"},
        {"start": 617.0, "title": "Tenet"},
        {"start": 900.0, "title": "Missing"},
    ]

    alignment = align_candidates_to_sections(candidates, sections, tolerance_sec=12.0)

    assert alignment["section_count"] == 4
    assert alignment["candidate_count"] == 4
    assert alignment["match_count"] == 3
    assert alignment["missed_count"] == 1
    assert alignment["extra_count"] == 1
    assert alignment["matches"][1]["section"] == "Anoana"
    assert alignment["matches"][1]["delta"] == pytest.approx(0.5)
    assert alignment["missed_sections"] == [{"section": "Missing", "start": 900.0}]
    assert alignment["extra_candidates"][0]["start"] == 700.0


def test_section_boundary_report_keeps_chapters_and_acoustic_evidence_separate():
    from galdr.boundary import build_section_boundary_report

    candidates = [
        {"start": 0.0, "end": 4.0, "kind": "opening_gap", "confidence": 0.7, "reset_strength": 0.0},
        {"start": 100.0, "end": 110.0, "kind": "probable_boundary", "confidence": 0.88, "reset_strength": 0.5},
        {"start": 210.0, "end": 214.0, "kind": "possible_boundary", "confidence": 0.62, "reset_strength": 0.22},
        {"start": 400.0, "end": 408.0, "kind": "interlude_gap", "confidence": 0.42, "reset_strength": 0.0},
    ]
    sections = [
        {"start": 0.0, "title": "Opening"},
        {"start": 106.0, "title": "Matched"},
        {"start": 185.0, "title": "Near miss"},
        {"start": 900.0, "title": "Declared only"},
    ]

    report = build_section_boundary_report(candidates, sections, tolerance_sec=8.0, near_miss_sec=30.0)

    assert report["summary"] == {
        "declared_section_count": 4,
        "acoustic_candidate_count": 4,
        "matched_count": 2,
        "near_miss_count": 1,
        "section_without_acoustic_boundary_count": 1,
        "acoustic_without_declared_section_count": 2,
        "tolerance_sec": 8.0,
        "near_miss_sec": 30.0,
    }
    assert [match["section"] for match in report["matched_declared_sections"]] == ["Opening", "Matched"]
    assert report["near_misses"] == [{
        "section": "Near miss",
        "section_start": 185.0,
        "nearest_candidate_start": 210.0,
        "nearest_candidate_end": 214.0,
        "nearest_candidate_kind": "possible_boundary",
        "delta": 25.0,
        "confidence": 0.62,
    }]
    assert report["sections_without_acoustic_boundary"] == [{"section": "Declared only", "start": 900.0}]
    assert [candidate["start"] for candidate in report["acoustic_boundaries_without_declared_section"]] == [210.0, 400.0]


def test_packet_builds_generic_evidence_container(tmp_path):
    from galdr.packet import build_packet_from_disk

    slug = "packet-track"
    track_dir = tmp_path / slug
    track_dir.mkdir()
    (track_dir / f"{slug}_report.json").write_text(json.dumps({
        "track": slug,
        "duration_seconds": 8.0,
        "felt_pulse_bpm": 96.0,
    }))
    (track_dir / f"{slug}_perception.json").write_text(json.dumps({
        "track": slug,
        "summary": {"mean_attention": 0.72, "mean_pattern": 0.81},
    }))
    (track_dir / f"{slug}_stream.json").write_text(json.dumps({
        "schema_version": "listener_state_v1",
        "stream": [
            {"t": 0.0, "attention": 0.7, "pattern": 0.8, "pressure": 0.0, "body": 0.7, "weight": 0.4},
            {"t": 0.5, "attention": 0.7, "pattern": 0.8, "pressure": 0.0, "body": 0.7, "weight": 0.4},
            {"t": 1.0, "attention": 0.8, "pattern": 0.9, "pressure": 0.4, "body": 0.8, "weight": 0.5},
            {"t": 1.5, "attention": 0.8, "pattern": 0.9, "pressure": 0.4, "body": 0.8, "weight": 0.5},
        ],
    }))
    (track_dir / "context.json").write_text(json.dumps({
        "slug": slug,
        "artist": "Packet Artist",
        "title": "Packet Title",
        "youtube_url": "https://www.youtube.com/watch?v=packet",
        "lyrics": {
            "source": "genius",
            "confidence": "high",
            "genius_url": "https://genius.example/packet",
            "genius_text": "first line\nsecond line",
        },
        "artist_context": {
            "found": True,
            "confidence": "medium",
            "use_in_prompt": True,
            "extract": "Packet Artist is a test fixture.",
        },
    }))

    packet = build_packet_from_disk(slug, tmp_path)

    assert packet["metadata"]["schema_version"] == "evidence_packet_v0"
    assert packet["subject"] == {
        "kind": "track",
        "id": slug,
        "slug": slug,
        "title": "Packet Title",
        "artist": "Packet Artist",
        "source_refs": [{"kind": "youtube", "url": "https://www.youtube.com/watch?v=packet"}],
    }
    assert set(packet) == {
        "metadata",
        "subject",
        "artifacts",
        "observations",
        "timeline",
        "sources",
        "claims",
        "collections",
        "views",
        "warnings",
    }
    assert any(item["role"] == "listener_state_stream" for item in packet["artifacts"])
    assert any(item["kind"] == "arc_span" for item in packet["timeline"])
    assert packet["collections"]["lyrics"]["status"] == "verified"
    assert packet["collections"]["lyrics"]["items"][0]["line_count"] == 2
    assert packet["collections"]["background"]["items"][0]["source_ref"] == "artist_context"
    assert packet["views"] == {}


def test_packet_cli_writes_json_file(tmp_path):
    from galdr import cli

    slug = "packet-cli-track"
    track_dir = tmp_path / "analysis" / slug
    track_dir.mkdir(parents=True)
    (track_dir / f"{slug}_report.json").write_text(json.dumps({"track": slug, "duration_seconds": 1.0}))
    output = tmp_path / "packet.json"
    args = type("args", (), {"slug": slug, "analysis_dir": tmp_path / "analysis", "output": output})()

    cli.cmd_packet(args)

    data = json.loads(output.read_text())
    assert data["subject"]["slug"] == slug
    assert data["metadata"]["generator"] == "galdr.packet"

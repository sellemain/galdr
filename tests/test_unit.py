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



def test_arc_scale_coalescing_preserves_terminal_silence_boundary():
    stream = []
    for i in range(90):
        stream.append(
            {
                "t": float(i),
                "attention": 0.82,
                "pattern": 0.84,
                "pressure": 0.01,
                "body": 0.76,
                "weight": 0.48,
                "silence": 0.0,
            }
        )
    for i in range(90, 94):
        stream.append(
            {
                "t": float(i),
                "attention": 0.06,
                "pattern": 0.04,
                "pressure": 0.0,
                "body": 0.05,
                "weight": 0.08,
                "silence": 1.0,
            }
        )

    scales = derive_arc_scales(stream)

    assert [span["label"] for span in scales["detail"]] == ["held", "emptying"]
    assert [span["label"] for span in scales["standard"]] == ["held", "emptying"]
    assert [span["label"] for span in scales["macro"]] == ["held", "emptying"]
    assert scales["macro"][-1]["start"] == pytest.approx(90.0)
    assert scales["macro"][-1]["silence_ratio"] == pytest.approx(1.0)


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


def test_arc_scale_selector_rejects_dense_moderate_detail_chatter():
    stream = []
    for i in range(160):
        if (i // 2) % 2 == 0:
            stream.append(
                {
                    "t": float(i),
                    "attention": 0.72,
                    "pattern": 0.74,
                    "pressure": 0.24,
                    "body": 0.60,
                    "weight": 0.42,
                    "silence": 0.0,
                }
            )
        else:
            stream.append(
                {
                    "t": float(i),
                    "attention": 0.58,
                    "pattern": 0.60,
                    "pressure": -0.24,
                    "body": 0.48,
                    "weight": 0.38,
                    "silence": 0.0,
                }
            )

    scales = derive_arc_scales(stream)
    selected, reason = select_arc_scale(scales)

    assert len(scales["detail"]) >= 80
    assert selected == "macro"
    assert "chatter" in reason


def test_arc_scale_selector_caps_extreme_detail_volume_to_standard():
    stream = []
    for i in range(540):
        phase = (i // 3) % 4
        stream.append(
            {
                "t": float(i),
                "attention": [0.84, 0.62, 0.78, 0.44][phase],
                "pattern": [0.80, 0.58, 0.74, 0.40][phase],
                "pressure": [0.46, -0.12, 0.38, -0.32][phase],
                "body": [0.70, 0.48, 0.64, 0.34][phase],
                "weight": [0.52, 0.36, 0.46, 0.28][phase],
                "silence": 0.0,
            }
        )

    scales = derive_arc_scales(stream)
    selected, reason = select_arc_scale(scales)

    assert len(scales["detail"]) >= 120
    assert len(scales["standard"]) < len(scales["detail"])
    assert selected == "standard"
    assert "flood" in reason


def test_arc_spans_mark_pressure_pivots_between_opposed_states():
    stream = [
        {"t": 0.0, "attention": 0.82, "pattern": 0.78, "pressure": 0.50, "body": 0.66, "silence": 0.0},
        {"t": 1.0, "attention": 0.80, "pattern": 0.76, "pressure": 0.46, "body": 0.64, "silence": 0.0},
        {"t": 2.0, "attention": 0.76, "pattern": 0.72, "pressure": -0.42, "body": 0.58, "silence": 0.0},
        {"t": 3.0, "attention": 0.74, "pattern": 0.70, "pressure": -0.38, "body": 0.54, "silence": 0.0},
        {"t": 4.0, "attention": 0.78, "pattern": 0.74, "pressure": 0.37, "body": 0.62, "silence": 0.0},
        {"t": 5.0, "attention": 0.81, "pattern": 0.77, "pressure": 0.41, "body": 0.65, "silence": 0.0},
    ]

    spans = derive_arc_spans(stream)

    assert [span["label"] for span in spans] == ["building", "pressure_peak_release", "pressure_rebound"]
    assert spans[1]["start"] == pytest.approx(2.0)
    assert spans[2]["start"] == pytest.approx(4.0)


def test_arc_spans_do_not_mark_silence_as_pressure_pivot():
    stream = [
        {"t": 0.0, "attention": 0.82, "pattern": 0.78, "pressure": 0.50, "body": 0.66, "silence": 0.0},
        {"t": 1.0, "attention": 0.05, "pattern": 0.05, "pressure": -0.60, "body": 0.05, "silence": 1.0},
    ]

    spans = derive_arc_spans(stream, min_span_frames=1)

    assert [span["label"] for span in spans] == ["building", "emptying"]


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

    assert _arc_archetype(martial)[0] == "martial/motor command"
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
        assert "## Lyrics — local VTT captions (coarse timing; text may contain transcription or alignment errors)" in result
        assert "Source: local VTT captions (/tmp/song.en.vtt)" in result
        assert "[0:01]  caption words" in result
        assert "## Lyrics — autocaptions" not in result

    def test_autocaption_lyrics_are_labeled_as_coarse_timing(self):
        analysis = self._minimal_analysis()
        context = {
            "lyrics": {
                "source": "youtube-auto-captions",
                "caption_lines": [{"ts": "0:01", "text": "caption words"}],
                "full_text": "caption words",
            }
        }
        result = self.fn(analysis, context=context, mode="lyrics")
        assert "## Lyrics — autocaptions (coarse timing; text may contain mishears)" in result
        assert "timestamps accurate" not in result

    def test_youtube_music_timed_lyrics_are_labeled_separately(self):
        analysis = self._minimal_analysis()
        context = {
            "lyrics": {
                "source": "genius+youtube-music-timed-lyrics",
                "genius_url": "https://genius.example/song",
                "genius_text": "clean lyric text",
                "full_text": "clean lyric text",
                "timed_lyrics_source": {"provider_source": "Source: Musixmatch"},
                "timed_lines": [{"ts": "0:10.65", "text": "provider timed words"}],
            }
        }
        result = self.fn(analysis, context=context, mode="lyrics")
        assert "## Lyrics — YouTube Music timed lyrics (provider line timing; verify central words)" in result
        assert "Source: Genius (https://genius.example/song) + YouTube Music timed lyrics (Source: Musixmatch)" in result
        assert "[0:10.65]  provider timed words" in result
        assert "## Lyrics — autocaptions" not in result
        assert "clean lyric text" in result

    def test_genius_only_lyrics_are_labeled_without_timestamps(self):
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
        assert "## Lyrics — Genius (clean text, no timestamps)" in result
        assert "clean lyric text" in result

    def test_legacy_full_text_lyrics_keep_plain_heading(self):
        analysis = self._minimal_analysis()
        context = {
            "lyrics": {
                "source": "legacy-import",
                "full_text": "legacy lyric text",
            }
        }
        result = self.fn(analysis, context=context, mode="lyrics")
        assert "## Lyrics\n\nSource: legacy-import\nlegacy lyric text" in result
        assert "clean text, no timestamps" not in result

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

    def test_structured_song_context_includes_evidence_not_constraints(self):
        analysis = self._minimal_analysis()
        context = {
            "song_context": {
                "summary": "Breakup context directly tied to the track.",
                "claims": [
                    {
                        "claim": "The writer described it as a breakup song.",
                        "source_type": "artist_interview",
                        "source_url": "https://example.test/interview",
                        "confidence": "high",
                    }
                ],
                "lyric_references": [
                    {
                        "reference": "the named character",
                        "meaning": "a sourced person from the artist's life",
                        "source_url": "https://example.test/annotation",
                    }
                ],
                "source_notes": ["Interview happened after the album cycle."],
                "constraints": ["Do not quote lyrics directly."],
            }
        }
        result = self.fn(analysis, context=context, mode="full")
        assert "Song context: Breakup context directly tied to the track." in result
        assert "Song context claim: The writer described it as a breakup song." in result
        assert "artist_interview" in result
        assert "https://example.test/interview" in result
        assert (
            "Song lyric reference: the named character: a sourced person from the artist's life"
            in result
        )
        assert "Song context source note: Interview happened after the album cycle." in result
        assert "Do not quote lyrics directly." not in result

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
            # tempo should always appear in the metrics section as felt language
            assert "Pulse:" in result, f"Metrics missing from mode={mode}"

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
        assert "BPM" not in result
        assert "Pulse: fast pulse" in result
        assert "detected pulse ambiguous/suspect" in result

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

        prompt = self.fn(analysis, mode="blind", template="arc")

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

    def test_arc_prompt_protects_natural_vivid_major_turns(self):
        analysis = {
            "report": {"duration_seconds": 240.0, "detected_pulse_bpm": 90.0, "felt_pulse_bpm": 90.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        prompt = self.fn(analysis, mode="blind", template="arc")

        assert "Surface discipline is not a command to flatten" in prompt
        assert "Treat anti-pattern warnings as guardrails" in prompt
        assert "sound natural, specific, and alive" in prompt
        assert "Write from the listening, not from the role of an agent completing an assignment" in prompt
        assert "not like proof of work" in prompt
        assert "Listen as a person who actually lives with music" in prompt
        assert "not like a system describing a track" in prompt
        assert "Protect major form turns" in prompt
        assert "late groove turn" in prompt
        assert "private transition map" in prompt
        assert "Do not use a fixed lyric quota" in prompt
        assert "Treat lyrics as sung words, not supplied text" in prompt
        assert "Write as if the words arrive through the performance" in prompt
        assert "A lyric timestamp is the start of a sung line or phrase" in prompt
        assert "Failure case: do not make up exact entrances for words" in prompt
        assert "Galdr stream/event timestamps are authoritative for sound and structure" in prompt
        assert "provider-timed, manual, verified" in prompt
        assert "primary clock for lyric, vocal, verse, chorus" in prompt
        assert "Use Galdr/audio-state timestamps freely" in prompt
        assert "Treat timestamps as **orientation markers**, not beat-by-beat labels" in prompt
        assert "Do **not** timestamp every event" in prompt
        assert "Obey time" in prompt
        assert "use only what the listener has heard up to that point" in prompt
        assert "The final concluding paragraph may summarize the whole experience" in prompt
        assert "Do not attach a quoted lyric to a specific metric event or timestamp" in prompt
        assert "audio-state timestamp pretend to be a lyric start" in prompt
        assert "first sustained arrival" in prompt
        assert "Output only the listening experience body" in prompt
        assert "private scaffolding" in prompt
        assert "Start with the first sentence of prose" in prompt
        assert "Do not begin with `Source:`" not in prompt
        assert "Analysis slug:" not in prompt
        assert "provenance label" not in prompt
        assert "Source: <url>" not in prompt
        assert "Include the source, then start the experience" not in prompt
        assert "Do not expose lyric provenance in public prose" in prompt
        assert "Do not default to triads" in prompt
        assert "do not amputate the arrangement" in prompt
        assert "not as a claimed second-by-second alignment" in prompt
        assert "galdr assemble <slug>" not in prompt
        assert "Pipe the output to any model" not in prompt
        assert "~150 words per minute" in prompt
        assert "900-1,300" in prompt

    def test_arc_family_default_lens_renders_base_and_lens(self):
        analysis = {
            "report": {"duration_seconds": 180.0, "detected_pulse_bpm": 92.0, "felt_pulse_bpm": 92.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        prompt = self.fn(analysis, mode="blind", template="arc-family", lens="default")

        assert "ARC Prompt Family Base" in prompt
        assert "Sound Translation Test" in prompt
        assert "Prose Shape" in prompt
        assert "compress them into one stronger sentence or one combined event" in prompt
        assert "Cut the weaker echo instead of proving the point again" in prompt
        assert "Default Lens" in prompt
        assert "Avoid reusable full-page architecture" in prompt
        assert "what would help the listener hear this more clearly" in prompt
        assert "changed returns" in prompt
        assert "Keep interpretation cumulative" in prompt
        assert "shortest complete walk" in prompt
        assert "Do not compress the song's governing sequence" in prompt
        assert "A list of names is not coverage" in prompt
        assert "This is a default, not a ceiling" in prompt
        assert "Write from the listening, not from the role of an agent completing an assignment" in prompt
        assert "not like proof of work" in prompt
        assert "Listen as a person who actually lives with music" in prompt
        assert "not like a system describing a track" in prompt
        assert "Do not assume the lyric and music are doing the same thing" in prompt
        assert "make one silent editorial pass" in prompt
        assert "three most useful things" in prompt
        assert "Write in the publication's public voice" in prompt
        assert "continuous with the surrounding corpus" in prompt
        assert "Do not mention prompts, agents, private memory, or internal process" in prompt
        assert "Sellemain" not in prompt
        assert "Elizabeth" not in prompt
        assert "Jason" not in prompt
        assert "## Galdr Analysis" in prompt

    def test_arc_family_lens_implies_template_when_omitted(self):
        analysis = {
            "report": {"duration_seconds": 180.0, "detected_pulse_bpm": 92.0, "felt_pulse_bpm": 92.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        prompt = self.fn(analysis, mode="blind", lens="structure")

        assert "ARC Prompt Family Base" in prompt
        assert "Structure Lens" in prompt
        assert "compact track anatomy" in prompt
        assert "privately reconcile every available timing surface" in prompt
        assert "Galdr stream events and structural events" in prompt
        assert "reliable aligned lyric or caption timings" in prompt
        assert "collapse that evidence into the cleanest major-section map" in prompt
        assert "do not turn every event, lyric line, or micro-change into its own section" in prompt
        assert "Account for the whole track" in prompt
        assert "post-solo reset, reprise, or chorus return" in prompt
        assert "prove the frame still works" in prompt
        assert "Obey time inside the map" in prompt
        assert "Each section note should describe what that span is doing when it arrives" in prompt
        assert "Vary section language" in prompt
        assert "section boundaries and section jobs" in prompt
        assert "not another sound essay" in prompt
        assert "treating a broad middle span as one section unless the evidence says it really is one sustained formal job" in prompt
        assert "3 to 6 short section headings" in prompt
        assert "visibly shorter than the Sound lens" in prompt

    def test_arc_family_sound_lens_renders_shape_first_instructions(self):
        analysis = {
            "report": {"duration_seconds": 180.0, "detected_pulse_bpm": 92.0, "felt_pulse_bpm": 92.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        prompt = self.fn(analysis, mode="blind", template="arc-sound")

        assert "ARC Prompt Family Base" in prompt
        assert "Sound Lens" in prompt
        assert "moving physical shape" in prompt
        assert "watching the waveform become architecture" in prompt
        assert "use them only when they clarify a heard event" in prompt
        assert "Do not use later arrivals" in prompt
        assert "Do not turn the sound walk into a repeated timestamp layout" in prompt
        assert "Sound-first does not mean proving one audible state three times" in prompt
        assert "collapse them into one exact claim and move to the next audible change" in prompt

    def test_arc_family_dance_lens_renders_movement_contract_instructions(self):
        analysis = {
            "report": {"duration_seconds": 180.0, "detected_pulse_bpm": 128.0, "felt_pulse_bpm": 128.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        prompt = self.fn(analysis, mode="blind", template="arc-dance")

        assert "ARC Prompt Family Base" in prompt
        assert "Dance Lens" in prompt
        assert "how the track teaches movement" in prompt
        assert "Keep the dance walk from becoming a reusable build/drop template" in prompt
        assert "dance as a listening contract, not a genre label" in prompt
        assert "Pressure belongs here only when it changes movement" in prompt
        assert "Do not force dance language onto a track that only has a beat" in prompt
        assert "Describe the movement contract as it is taught" in prompt
        assert "what movement becomes possible here" in prompt
        assert "private movement model" in prompt
        assert "movement scale" in prompt
        assert "could test the claim while the track plays" in prompt
        assert "could be relabeled as a default listening experience" in prompt

    def test_arc_family_meaning_lens_renders_human_situation_instructions(self):
        analysis = {
            "report": {"duration_seconds": 180.0, "detected_pulse_bpm": 92.0, "felt_pulse_bpm": 92.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        prompt = self.fn(analysis, mode="full", lens="meaning")

        assert "ARC Prompt Family Base" in prompt
        assert "Meaning Lens" in prompt
        assert "what the song is saying" in prompt
        assert "what the song is about" in prompt
        assert "make the words a primary evidence layer" in prompt
        assert "This lens is allowed to say what the song is about" in prompt
        assert "Sound is the proof and complication layer" in prompt
        assert "This lens is allowed to be retrospective" in prompt
        assert "It may summarize the whole track" in prompt
        assert "Do not make every Meaning page use the same mini-essay order" in prompt
        assert "Usually write 1 or 2 paragraphs around 100-180 words" in prompt
        assert "Do not walk the whole song again in timeline order" in prompt
        assert "use sound only as proof or complication" in prompt
        assert "Shape: usually 4 to 7 paragraphs" not in prompt

    def test_arc_family_prompts_avoid_public_banned_body_lock_language(self):
        analysis = {
            "report": {"duration_seconds": 180.0, "detected_pulse_bpm": 92.0, "felt_pulse_bpm": 92.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        for lens in [
            "default",
            "sound",
            "dance",
            "structure",
            "meaning",
            "lyrics-study",
            "classical",
            "ritual",
        ]:
            prompt = self.fn(analysis, mode="full", template="arc-family", lens=lens)

            assert "body-lock" not in prompt
            assert "body lock" not in prompt.lower()
            assert "mass lock" not in prompt
            assert "Primary contract: lock" not in prompt

    def test_arc_family_lens_alias_selects_lens(self):
        analysis = {
            "report": {"duration_seconds": 180.0, "detected_pulse_bpm": 92.0, "felt_pulse_bpm": 92.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        prompt = self.fn(analysis, mode="blind", template="arc-classical")

        assert "ARC Prompt Family Base" in prompt
        assert "Classical Lens" in prompt
        assert "Do not force verse/chorus/hook/lyric-persona logic" in prompt
        assert "Write each formal moment from what the listener has heard so far" in prompt
        assert "what must the listener remember for the form to become audible" in prompt
        assert "private memory map" in prompt
        assert "transformed recurrence" in prompt
        assert "Track musical agency" in prompt
        assert "another default arc with orchestral nouns" in prompt

    def test_arc_family_ritual_lens_renders_permission_first_reading(self):
        analysis = {
            "report": {"duration_seconds": 180.0, "detected_pulse_bpm": 92.0, "felt_pulse_bpm": 92.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        prompt = self.fn(analysis, mode="blind", template="arc-ritual")

        assert "ARC Prompt Family Base" in prompt
        assert "Ritual Lens" in prompt
        assert "Tell the truth of the experience as strongly as you can" in prompt
        assert "safe exploratory chamber" in prompt
        assert "Use exact ritual names when the experience earns them" in prompt
        assert "Then prove the name" in prompt
        assert "recurrence, phrase extension, harmonic delay" in prompt
        assert "song as enacted procedure" in prompt
        assert "recognizable to another careful listener" in prompt
        assert "Follow the enacted sequence as it happens" in prompt
        assert "If the name would sound silly" in prompt
        assert "public draft decides what survives" not in prompt
        assert "what is your ritual interpretation" in prompt
        assert "Ritual means true enacted meaning, not genre smell" in prompt
        assert "private ritual grammar" in prompt
        assert "where ordinary listening becomes participation" in prompt
        assert "strongest reason this may instead be atmosphere" in prompt
        assert "Do not retell the entire sound arc in ceremonial vocabulary" in prompt
        assert "could be relabeled as a default listening experience" in prompt
        assert "map each one privately" in prompt
        assert "Do not collapse an enacted sequence into a list of subjects" in prompt
        assert "Ritual follows how the procedure is performed" in prompt
        assert "do not omit distinct ritual acts" in prompt
        assert "the danger or condition being named" in prompt
        assert "A translated sequence is not yet a ritual reading" in prompt
        assert "Keep the ritual grammar, counter-reading, and qualification test private" in prompt
        assert "Do not publish contract labels" in prompt
        assert "Let audible procedure, changed role, transformation, and exit prove the reading" in prompt
        assert "Do not print that private pass" in prompt
        assert "Output only the resulting public listening experience" in prompt
        assert "a separate list of public prose sparks" in prompt

    def test_arc_family_rejects_unknown_lens(self):
        analysis = {
            "report": {"duration_seconds": 180.0, "detected_pulse_bpm": 92.0, "felt_pulse_bpm": 92.0},
            "perception": {
                "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
                "stream": [{"t": 0.0, "attention": 0.80, "pattern": 0.85, "pressure": 0.50, "body": 0.60}],
            },
        }

        with pytest.raises(ValueError, match="Unknown lens"):
            self.fn(analysis, mode="blind", template="arc-family", lens="wrong")


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
            "surface_balance": -0.4,
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
        assert "surface_evidence" in entry
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
        for field in (
            "roughness",
            "noise_density",
            "transient_attack",
            "sustain_drone",
            "band_pressure",
        ):
            assert field in entry["surface_evidence"]
            assert 0.0 <= entry["surface_evidence"][field] <= 1.0
            assert f"mean_surface_{field}" in summary
            assert f"peak_surface_{field}" in summary
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


def test_perception_metric_plots_cover_listener_state_and_surface_evidence(tmp_path):
    import numpy as np

    from galdr.perceive import (
        _plot_listener_state_metrics,
        _plot_reading_map,
        _plot_surface_evidence_metrics,
    )

    stream = []
    for i in range(8):
        v = i / 7
        stream.append({
            "t": float(i),
            "body_capture": v,
            "body_comfort": 1.0 - v,
            "groove_comfort": 0.5,
            "accent_phase_drift": v * 0.4,
            "section_gravity": 0.2 + v * 0.6,
            "surface_density": 0.1 + v * 0.5,
            "expectation_debt": v * 0.8,
            "release_force": max(0.0, 0.7 - v),
            "weight": 0.25 + v * 0.2,
            "pressure": -0.5 + v,
            "surface_evidence": {
                "roughness": v,
                "noise_density": 1.0 - v,
                "surface_motion": 0.2 + v * 0.5,
                "brightness_tilt": 0.4,
                "transient_attack": v * 0.6,
                "punch": v * 0.5,
                "sustain_drone": 1.0 - v * 0.5,
                "band_pressure": 0.3 + v * 0.3,
                "bass_weight": 0.25,
                "body_weight": 0.35,
                "presence_weight": 0.30,
                "air_weight": 0.10,
                "percussive_ratio": v,
            },
        })

    silences = [{"start": 2.0, "end": 3.0}]
    sr = 22050
    t = np.linspace(0, 8, sr * 8, endpoint=False)
    y = (0.15 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    hp_times = np.asarray([entry["t"] for entry in stream], dtype=float)
    hp_balance = np.linspace(-0.4, 0.5, len(stream))

    _plot_listener_state_metrics(stream, silences, tmp_path, "plot-test", duration=8.0)
    _plot_surface_evidence_metrics(stream, silences, tmp_path, "plot-test", duration=8.0)
    _plot_reading_map(y, sr, stream, hp_times, hp_balance, silences, tmp_path, "plot-test", duration=8.0)

    listener_plot = tmp_path / "plot-test_listener_state.png"
    surface_plot = tmp_path / "plot-test_surface_evidence.png"
    reading_plot = tmp_path / "plot-test_reading_map.png"
    assert listener_plot.exists()
    assert listener_plot.stat().st_size > 0
    assert surface_plot.exists()
    assert surface_plot.stat().st_size > 0
    assert reading_plot.exists()
    assert reading_plot.stat().st_size > 0


def test_cli_plot_index_lists_png_artifacts(tmp_path):
    from galdr.cli import _write_plot_index

    (tmp_path / "plot-test_reading_map.png").write_bytes(b"fake-png")
    (tmp_path / "plot-test_surface_evidence.png").write_bytes(b"fake-png")
    (tmp_path / "other-track_reading_map.png").write_bytes(b"fake-png")

    index_path = _write_plot_index(tmp_path, "plot-test")

    assert index_path == tmp_path / "index.html"
    text = index_path.read_text()
    assert "plot-test_reading_map.png" in text
    assert "plot-test_surface_evidence.png" in text
    assert "other-track_reading_map.png" not in text
    assert "color-scheme: dark" in text
    assert "background: #0d1117" in text
    assert "grid-template-columns: minmax(0, 1fr)" in text

# ── Rhythm Body-Entrainment ──────────────────────────────────────────────────


def test_compute_body_separates_motor_entrainment_from_raw_tempo():
    from galdr.analyze import compute_body

    locked = compute_body(
        duration=120.0,
        beat_count=240,
        pulse=0.94,
        pulse_confidence=0.92,
        pulse_ambiguous=False,
        surface_balance=0.62,
        onsets_per_second=3.2,
    )
    loose = compute_body(
        duration=120.0,
        beat_count=240,
        pulse=0.94,
        pulse_confidence=0.92,
        pulse_ambiguous=False,
        surface_balance=0.05,
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
        surface_balance=0.5,
        onsets_per_second=2.5,
    )
    ambiguous = compute_body(
        duration=120.0,
        beat_count=220,
        pulse=0.88,
        pulse_confidence=0.8,
        pulse_ambiguous=True,
        surface_balance=0.5,
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
        surface_balance=0.31,
        onsets_per_second=1.7,
        harmonic_weight=0.21,
        percussive_weight=0.095,
        dynamic_range_ratio=1000.0,
    )
    motor = compute_weight(
        pulse=0.97,
        pulse_confidence=0.90,
        body=0.78,
        surface_balance=0.35,
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
            "entrainment_note": "strong motor capture with real percussive support",
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
    assert "strong motor capture" in prompt
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
            artist="Example Ensemble",
            title="Bright Signal",
        )
        assert result["confidence"] == "rejected"
        assert result["use_in_prompt"] is False

    def test_wikipedia_song_partial_match_can_be_low_but_usable(self):
        from galdr.fetch import _score_wikipedia_result

        result = _score_wikipedia_result(
            {
                "found": True,
                "title": "Bright Signal",
                "extract": "Bright Signal is a traditional ceremonial march.",
            },
            expected_name="The Bright Signal",
            entity_type="song",
        )
        assert result["confidence"] in {"medium", "high"}
        assert result["use_in_prompt"] is True

    def test_wikipedia_song_rejects_title_match_without_expected_artist(self):
        from galdr.fetch import _score_wikipedia_result

        result = _score_wikipedia_result(
            {
                "found": True,
                "title": "Bright Signal (Example Ensemble song)",
                "extract": "\"Bright Signal\" is a song by Example Ensemble.",
            },
            expected_name="Bright Signal",
            entity_type="song",
            expected_artist="Reference Artist",
        )

        assert result["confidence"] == "rejected"
        assert result["use_in_prompt"] is False
        assert "song context lacks expected artist evidence" in result["match_reasons"]

    def test_wikipedia_song_accepts_title_match_with_expected_artist(self):
        from galdr.fetch import _score_wikipedia_result

        result = _score_wikipedia_result(
            {
                "found": True,
                "title": "Bright Signal (Reference Artist song)",
                "extract": "\"Bright Signal\" is a song by Reference Artist.",
            },
            expected_name="Bright Signal",
            entity_type="song",
            expected_artist="Reference Artist",
        )

        assert result["confidence"] in {"medium", "high"}
        assert result["use_in_prompt"] is True

    def test_wikipedia_disambiguation_stub_rejected_even_with_title_match(self):
        from galdr.fetch import _score_wikipedia_result

        result = _score_wikipedia_result(
            {
                "found": True,
                "title": "Bright Signal",
                "extract": "Bright Signal may refer to:",
            },
            expected_name="Bright Signal",
            entity_type="song",
        )
        assert result["confidence"] == "rejected"
        assert result["use_in_prompt"] is False


    def test_wikipedia_artist_prefers_music_qualified_page_over_disambiguation(self, monkeypatch):
        import galdr.fetch as fetch

        def fake_intro(title):
            if title == "Example Band (band)":
                return {"found": True, "title": "Example Band (band)", "extract": "Example Band is an American heavy metal band from Oakland, California."}
            if title == "Example Band":
                return {"found": True, "title": "Example band", "extract": "Example band may refer to:"}
            return {"found": False}

        monkeypatch.setattr(fetch, "fetch_wikipedia_intro", fake_intro)

        result = fetch.fetch_wikipedia_context("Example Band", entity_type="artist")

        assert result["title"] == "Example Band (band)"
        assert result["use_in_prompt"] is True

    def test_genius_sanitizer_removes_live_ticket_cta(self):
        from galdr.fetch import _sanitize_lyric_lines

        lines = _sanitize_lyric_lines([
            "See Example Band LiveGet tickets as low as $67",
            "This is real lyric text",
            "Embed",
        ])

        assert lines == ["This is real lyric text"]

    def test_genius_translation_hit_rejected_by_title_bracket(self):
        from galdr.fetch import _is_genius_translation_hit

        hit = {
            "title": "Reference Artist - Long Road (English Translation)",
            "artist": "Genius English Translations",
            "full_title": "Reference Artist - Long Road (English Translation) by Genius English Translations",
            "url": "https://genius.com/Genius-english-translations-reference-artist-long-road-english-translation-lyrics",
        }
        is_trans, reason = _is_genius_translation_hit(hit)
        assert is_trans is True
        assert "translation marker in title" in reason

    def test_genius_translation_hit_rejected_by_artist_name(self):
        from galdr.fetch import _is_genius_translation_hit

        hit = {
            "title": "Long Road",
            "artist": "Genius English Translations",
            "full_title": "Reference Artist - Long Road (English Translation) by Genius English Translations",
            "url": "https://genius.com/Genius-english-translations-reference-artist-long-road-english-translation-lyrics",
        }
        is_trans, reason = _is_genius_translation_hit(hit)
        assert is_trans is True
        assert "translation artist" in reason

    def test_genius_translation_hit_accepted_when_clean(self):
        from galdr.fetch import _is_genius_translation_hit

        hit = {
            "title": "Long Road",
            "artist": "Reference Artist",
            "full_title": "Reference Artist - Long Road",
            "url": "https://genius.com/Reference-artist-long-road-lyrics",
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
                                "path": "/Genius-english-translations-reference-artist-long-road-english-translation-lyrics",
                                "title": "Reference Artist - Long Road (English Translation)",
                                "full_title": "Reference Artist - Long Road (English Translation) by Genius English Translations",
                                "primary_artist": {"name": "Genius English Translations"},
                            }
                        },
                        {
                            "result": {
                                "path": "/Reference-artist-long-road-lyrics",
                                "title": "Long Road",
                                "full_title": "Reference Artist - Long Road",
                                "primary_artist": {"name": "Reference Artist"},
                            }
                        },
                    ]
                }
            }).encode())

        fetch.urllib.request.urlopen = fake_urlopen
        try:
            result = _genius_search("Reference Artist", "Long Road")
            assert result is not None
            assert result["artist"] == "Reference Artist"
            assert result["url"] == "https://genius.com/Reference-artist-long-road-lyrics"
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
    assert "Primary contract: motor_capture" in prompt
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
            "surface_balance": 0.10,
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
    assert "force without motor capture" in salience["prose_hints"]


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

    assert impact["primary_contract"] == "motor_capture"
    assert "mass hold" in impact["prose_hints"]
    assert "impact mass hold" in impact["prose_hints"]
    assert "braced mass hold" not in impact["prose_hints"]

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

    assert braced["primary_contract"] == "motor_capture"
    assert "mass hold" in braced["prose_hints"]
    assert "braced mass hold" in braced["prose_hints"]
    assert "impact mass hold" not in braced["prose_hints"]


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

    assert salience["primary_contract"] == "motor_capture"
    assert "mass hold" in salience["prose_hints"]
    assert "soft mass hold" in salience["prose_hints"]
    assert "braced mass hold" not in salience["prose_hints"]
    assert "impact mass hold" not in salience["prose_hints"]


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
        {"start": 0.0, "title": "Section A"},
        {"start": 318.0, "title": "Section B"},
        {"start": 617.0, "title": "Section C"},
        {"start": 900.0, "title": "Missing"},
    ]

    alignment = align_candidates_to_sections(candidates, sections, tolerance_sec=12.0)

    assert alignment["section_count"] == 4
    assert alignment["candidate_count"] == 4
    assert alignment["match_count"] == 3
    assert alignment["missed_count"] == 1
    assert alignment["extra_count"] == 1
    assert alignment["matches"][1]["section"] == "Section B"
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


# ── Section / Arc Events ─────────────────────────────────────────────────────


def test_section_arc_events_keep_sustained_arc_without_boundary_evidence():
    from galdr.section_arc import derive_section_arc_events

    stream = []
    for t in range(0, 16):
        stream.append(_boundary_frame(t, pressure=0.04, body=0.64, density=0.55))

    events = derive_section_arc_events(stream)

    assert [event["source"] for event in events["arc_spans"]] == ["arc_span"]
    assert events["arc_spans"][0]["label"] == "held"
    assert events["acoustic_boundaries"] == []
    assert events["reset_points"] == []
    assert events["declared_alignment"] is None
    assert all(event["source"] == "arc_span" for event in events["arc_spans"])


def test_section_arc_events_split_acoustic_boundary_from_reset_point():
    from galdr.section_arc import derive_section_arc_events

    silence_stream = []
    for t in range(0, 6):
        silence_stream.append(_boundary_frame(t, pressure=0.05, density=0.7))
    for t in range(6, 12):
        silence_stream.append(
            _boundary_frame(
                t, silence=True, attention=0.1, pattern=0.2, pressure=-0.4,
                density=0.0, rms=0.001, lufs=-68.0
            )
        )
    for t in range(12, 20):
        silence_stream.append(_boundary_frame(t, attention=0.92, pattern=0.96, pressure=0.42, body=0.8, density=0.8))

    boundary_events = derive_section_arc_events(silence_stream)

    assert [event["label"] for event in boundary_events["acoustic_boundaries"]] == ["probable_boundary"]
    assert boundary_events["acoustic_boundaries"][0]["source"] == "acoustic_boundary"
    assert boundary_events["reset_points"] == []

    reset_stream = []
    for t in range(0, 8):
        reset_stream.append(
            _boundary_frame(t, attention=0.9, pattern=0.96, pressure=-0.08, body=0.43, weight=0.88,
                            density=0.06, rms=0.07, lufs=-24.0)
        )
    for t in range(8, 16):
        reset_stream.append(
            _boundary_frame(t, attention=0.97, pattern=0.99, pressure=0.08, body=0.72, weight=0.55,
                            density=0.31, rms=0.16, lufs=-19.0)
        )

    reset_events = derive_section_arc_events(reset_stream)

    assert reset_events["acoustic_boundaries"] == []
    assert [event["label"] for event in reset_events["reset_points"]] == ["reset_point"]
    assert reset_events["reset_points"][0]["source"] == "reset_point"


def test_section_arc_events_caps_packet_facing_reset_points(monkeypatch):
    import galdr.section_arc as section_arc

    stream = [_boundary_frame(t, pressure=0.04, body=0.64, density=0.55) for t in range(0, 16)]
    reset_candidates = [
        {
            "kind": "reset_point",
            "start": float(t),
            "end": float(t),
            "confidence": 0.7,
            "state_reset": 0.4,
            "acoustic_reset": 0.2,
            "rank_score": 0.5,
        }
        for t in range(10, 110, 10)
    ]

    def fake_derive_boundary_candidates(*args, **kwargs):
        if kwargs.get("include_reset_points"):
            return reset_candidates
        return []

    def fake_rank_reset_candidates(candidates, *, top_n, **kwargs):
        assert top_n == 3
        return candidates[:top_n]

    monkeypatch.setattr(section_arc, "derive_boundary_candidates", fake_derive_boundary_candidates)
    monkeypatch.setattr(section_arc, "rank_reset_candidates", fake_rank_reset_candidates)

    events = section_arc.derive_section_arc_events(stream, max_reset_points=3)

    assert [event["start"] for event in events["reset_points"]] == [10.0, 20.0, 30.0]
    assert all(event["source"] == "reset_point" for event in events["reset_points"])


def test_section_arc_events_align_declared_sections_without_merging_lanes():
    from galdr.section_arc import derive_section_arc_events

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

    events = derive_section_arc_events(stream, declared_sections=[{"start": 12.0, "title": "Second movement"}])

    assert events["declared_alignment"]["summary"]["matched_count"] == 1
    assert events["declared_alignment"]["matched_declared_sections"][0]["section"] == "Second movement"
    assert events["acoustic_boundaries"][0]["source"] == "acoustic_boundary"
    assert "declared_alignment" not in events["acoustic_boundaries"][0]


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
        "song_context": {
            "summary": "The song context is directly tied to the track.",
            "claims": [
                {
                    "claim": "The artist described this as a breakup song.",
                    "source_type": "artist_interview",
                    "source_url": "https://example.test/song-interview",
                    "confidence": "high",
                }
            ],
            "lyric_references": [
                {
                    "reference": "the named character",
                    "meaning": "a person in the artist's life",
                    "source_url": "https://example.test/annotation",
                }
            ],
            "source_notes": ["This source note is evidence context, not policy."],
            "constraints": ["Do not quote lyrics directly."],
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
    assert any(
        claim["kind"] == "song_context_claim"
        and claim["text"] == "The artist described this as a breakup song."
        for claim in packet["claims"]
    )
    assert any(
        claim["kind"] == "song_context_lyric_reference"
        and claim["text"] == "the named character: a person in the artist's life"
        for claim in packet["claims"]
    )
    assert any(
        item["kind"] == "song_context_source_notes"
        and item["items"] == ["This source note is evidence context, not policy."]
        for item in packet["collections"]["background"]["items"]
    )
    assert "Do not quote lyrics directly." not in json.dumps(packet)
    assert packet["views"] == {}


def test_packet_marks_provider_timed_lyrics_as_distinct_timing_surface(tmp_path):
    from galdr.packet import build_packet_from_disk

    slug = "packet-provider-timed-lyrics"
    track_dir = tmp_path / slug
    track_dir.mkdir()
    (track_dir / f"{slug}_report.json").write_text(json.dumps({"track": slug, "duration_seconds": 8.0}))
    (track_dir / "context.json").write_text(json.dumps({
        "slug": slug,
        "lyrics": {
            "source": "genius+youtube-music-timed-lyrics",
            "confidence": "high",
            "genius_text": "clean text",
            "full_text": "clean text",
            "timed_lyrics_source": {
                "provider_source": "Source: Musixmatch",
                "lyrics_browse_id": "MPLYt_demo",
            },
            "timed_lines": [{"ts": "0:10.65", "start": 10.65, "text": "provider timed words"}],
            "caption_lines": [],
        },
    }))

    packet = build_packet_from_disk(slug, tmp_path)
    lyrics = packet["collections"]["lyrics"]

    assert lyrics["timing"] == {
        "kind": "provider_timed_lyrics",
        "surface": "timed_lines",
        "confidence": "provider",
        "line_count": 1,
        "provider_source": "Source: Musixmatch",
        "provider_ref": "MPLYt_demo",
    }
    assert lyrics["timed_lines"][0]["text"] == "provider timed words"
    assert "caption_lines" not in lyrics


def test_packet_marks_autocaptions_as_coarse_timing_surface(tmp_path):
    from galdr.packet import build_packet_from_disk

    slug = "packet-autocaption-lyrics"
    track_dir = tmp_path / slug
    track_dir.mkdir()
    (track_dir / f"{slug}_report.json").write_text(json.dumps({"track": slug, "duration_seconds": 8.0}))
    (track_dir / "context.json").write_text(json.dumps({
        "slug": slug,
        "lyrics": {
            "source": "youtube-auto-captions",
            "confidence": "high",
            "full_text": "caption words",
            "caption_lines": [{"ts": "0:01", "start": 1.0, "text": "caption words"}],
        },
    }))

    packet = build_packet_from_disk(slug, tmp_path)
    lyrics = packet["collections"]["lyrics"]

    assert lyrics["timing"] == {
        "kind": "youtube_autocaption_timing",
        "surface": "caption_lines",
        "confidence": "coarse_asr",
        "line_count": 1,
    }
    assert lyrics["caption_lines"][0]["text"] == "caption words"


def test_packet_timeline_uses_section_arc_structural_events(tmp_path):
    from galdr.packet import build_packet_from_disk

    slug = "packet-section-arc-track"
    track_dir = tmp_path / slug
    track_dir.mkdir()
    (track_dir / f"{slug}_report.json").write_text(json.dumps({
        "track": slug,
        "duration_seconds": 36.0,
    }))
    (track_dir / f"{slug}_perception.json").write_text(json.dumps({
        "track": slug,
        "summary": {"mean_attention": 0.72, "mean_pattern": 0.81},
    }))

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
    for t in range(20, 28):
        stream.append(
            _boundary_frame(t, attention=0.9, pattern=0.96, pressure=-0.08, body=0.43, weight=0.88,
                            density=0.06, rms=0.07, lufs=-24.0)
        )
    for t in range(28, 36):
        stream.append(
            _boundary_frame(t, attention=0.97, pattern=0.99, pressure=0.08, body=0.72, weight=0.55,
                            density=0.31, rms=0.16, lufs=-19.0)
        )

    (track_dir / f"{slug}_stream.json").write_text(json.dumps({
        "schema_version": "listener_state_v1",
        "stream": stream,
    }))
    (track_dir / "context.json").write_text(json.dumps({"slug": slug}))

    packet = build_packet_from_disk(slug, tmp_path)
    structural = [item for item in packet["timeline"] if item["source_ref"] == "perception.stream"]

    assert any(item["kind"] == "arc_span" for item in structural)
    boundaries = [item for item in structural if item["kind"] == "boundary_candidate"]
    resets = [item for item in structural if item["kind"] == "reset_point"]
    assert [(item["start"], item["end"], item["label"]) for item in boundaries] == [(6.0, 12.0, "probable_boundary")]
    assert [(item["start"], item["end"], item["label"]) for item in resets] == [(22.0, 22.0, "reset_point")]
    starts = [item["start"] for item in structural]
    assert starts == sorted(starts)


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

# ── caption cue confidence helpers ────────────────────────────────────


def test_parse_vtt_cues_preserves_end_times_and_strips_music_note_wrappers(tmp_path):
    from galdr.captions import parse_vtt_cues, timed_lyric_segments

    path = tmp_path / "song.en.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:03.500\n"
        "♪ I hurt myself today to see if I still feel ♪\n\n"
        "00:00:04.000 --> 00:00:06.000\n"
        "(slow quiet piano music)\n",
        encoding="utf-8",
    )

    cues = parse_vtt_cues(path)

    assert cues[0]["start"] == pytest.approx(1.0)
    assert cues[0]["end"] == pytest.approx(3.5)
    assert cues[0]["normalized_text"] == "I hurt myself today to see if I still feel"
    assert cues[0]["kind"] == "lyric"
    assert cues[0]["confidence"] == "high"
    assert cues[1]["kind"] == "stage"
    assert cues[1]["confidence"] == "rejected"
    assert timed_lyric_segments(cues) == [
        {
            "start": 1.0,
            "end": 3.5,
            "ts": "0:01.00",
            "text": "I hurt myself today to see if I still feel",
            "source": "timed-caption",
            "confidence": "high",
        }
    ]


def test_caption_confidence_rejects_short_asr_fragments_as_lyric_timing_evidence(tmp_path):
    from galdr.captions import parse_vtt_cues, timed_lyric_segments

    path = tmp_path / "negative.en.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\n"
        "my life\n\n"
        "00:00:03.000 --> 00:00:04.000\n"
        "oh a\n\n"
        "00:00:05.000 --> 00:00:06.000\n"
        "[Music]\n",
        encoding="utf-8",
    )

    cues = parse_vtt_cues(path)

    assert [cue["kind"] for cue in cues] == ["caption", "caption", "stage"]
    assert timed_lyric_segments(cues) == []


def test_caption_confidence_accepts_clean_dense_lyrics_and_keeps_raw_captions(tmp_path):
    from galdr.captions import parse_vtt_cues, timed_lyric_segments

    path = tmp_path / "dense.en.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "00:00:10.000 --> 00:00:12.000\n"
        "We're up all night to get lucky\n\n"
        "00:00:12.000 --> 00:00:13.000\n"
        "you\n",
        encoding="utf-8",
    )

    cues = parse_vtt_cues(path)
    lyrics = timed_lyric_segments(cues)

    assert len(cues) == 2
    assert lyrics[0]["text"] == "We're up all night to get lucky"
    assert lyrics[0]["confidence"] == "high"
    assert cues[1]["kind"] == "caption"
    assert len(lyrics) == 1


def test_fetch_does_not_promote_rejected_autocaptions_to_lyric_timestamps(tmp_path, monkeypatch):
    from galdr import fetch

    audio_dir = tmp_path / "audio"
    analysis_dir = tmp_path / "analysis"
    vtt_path = audio_dir / "demo-song.en.vtt"

    def fake_download_youtube(url, audio_dir_arg, slug):
        audio_dir_arg.mkdir(parents=True, exist_ok=True)
        vtt_path.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "[Music] you\n\n"
            "00:00:03.000 --> 00:00:04.000\n"
            "oh\n",
            encoding="utf-8",
        )
        return {
            "audio_file": str(audio_dir_arg / f"{slug}.mp3"),
            "captions_file": str(vtt_path),
            "downloaded_at": "2026-01-01T00:00:00Z",
            "audio_sha256": "fake",
        }

    def fake_genius_lyrics(artist, title):
        return {
            "found": True,
            "url": "https://genius.example/demo",
            "lines": ["Hey you, big star", "Shove it aside"],
            "confidence": "high",
            "match_score": 1.0,
            "match_reasons": [],
            "use_in_prompt": True,
            "candidate_title": title,
            "candidate_artist": artist,
        }

    monkeypatch.setattr(fetch, "download_youtube", fake_download_youtube)
    monkeypatch.setattr(fetch, "fetch_genius_lyrics", fake_genius_lyrics)

    context = fetch.fetch_track(
        "demo-song",
        "Demo Artist",
        "Demo Song",
        analysis_dir,
        audio_dir,
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        skip_wikipedia=True,
    )

    assert context["lyrics"]["source"] == "genius"
    assert context["lyrics"]["genius_text"] == "Hey you, big star\nShove it aside"
    assert context["lyrics"]["caption_lines"] == []


def test_fetch_stores_provider_timed_lyrics_with_genius(tmp_path, monkeypatch):
    from galdr import fetch

    audio_dir = tmp_path / "audio"
    analysis_dir = tmp_path / "analysis"

    def fake_download_youtube(url, audio_dir_arg, slug):
        audio_dir_arg.mkdir(parents=True, exist_ok=True)
        return {
            "audio_file": str(audio_dir_arg / f"{slug}.mp3"),
            "captions_file": None,
            "downloaded_at": "2026-01-01T00:00:00Z",
            "audio_sha256": "fake",
        }

    def fake_provider_timed_lyrics(video_id):
        return {
            "found": True,
            "source": "youtube-music-timed-lyrics",
            "provider": "youtube-music",
            "provider_source": "Source: Musixmatch",
            "lyrics_browse_id": "MPLYt_demo",
            "video_id": video_id,
            "has_timestamps": True,
            "line_count": 1,
            "timed_lines": [
                {
                    "start": 10.65,
                    "end": 15.1,
                    "ts": "0:10.65",
                    "text": "provider timed words",
                    "source": "youtube-music-timed-lyrics",
                    "confidence": "provider-timed",
                }
            ],
        }

    def fake_genius_lyrics(artist, title):
        return {
            "found": True,
            "url": "https://genius.example/demo",
            "lines": ["Clean lyric text"],
            "confidence": "high",
            "match_score": 1.0,
            "match_reasons": [],
            "use_in_prompt": True,
            "candidate_title": title,
            "candidate_artist": artist,
        }

    monkeypatch.setattr(fetch, "download_youtube", fake_download_youtube)
    monkeypatch.setattr(fetch, "fetch_provider_timed_lyrics", fake_provider_timed_lyrics)
    monkeypatch.setattr(fetch, "fetch_genius_lyrics", fake_genius_lyrics)

    context = fetch.fetch_track(
        "demo-song",
        "Demo Artist",
        "Demo Song",
        analysis_dir,
        audio_dir,
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        skip_wikipedia=True,
    )

    assert context["lyrics"]["source"] == "genius+youtube-music-timed-lyrics"
    assert context["lyrics"]["timed_lines"][0]["ts"] == "0:10.65"
    assert context["lyrics"]["timed_lyrics_source"]["provider_source"] == "Source: Musixmatch"
    assert context["lyrics"]["caption_lines"] == []
    assert context["lyrics"]["genius_text"] == "Clean lyric text"


def test_fetch_uses_provider_timed_lyrics_when_genius_missing(tmp_path, monkeypatch):
    from galdr import fetch

    audio_dir = tmp_path / "audio"
    analysis_dir = tmp_path / "analysis"

    def fake_download_youtube(url, audio_dir_arg, slug):
        audio_dir_arg.mkdir(parents=True, exist_ok=True)
        return {
            "audio_file": str(audio_dir_arg / f"{slug}.mp3"),
            "captions_file": None,
            "downloaded_at": "2026-01-01T00:00:00Z",
            "audio_sha256": "fake",
        }

    monkeypatch.setattr(fetch, "download_youtube", fake_download_youtube)
    monkeypatch.setattr(
        fetch,
        "fetch_provider_timed_lyrics",
        lambda video_id: {
            "found": True,
            "source": "youtube-music-timed-lyrics",
            "provider": "youtube-music",
            "provider_source": "Source: LyricFind",
            "lyrics_browse_id": "MPLYt_demo",
            "video_id": video_id,
            "has_timestamps": True,
            "line_count": 1,
            "timed_lines": [{"ts": "0:01.00", "text": "timed only", "start": 1.0, "end": 2.0}],
        },
    )
    monkeypatch.setattr(
        fetch,
        "fetch_genius_lyrics",
        lambda artist, title: {"found": False, "reason": "no match"},
    )

    context = fetch.fetch_track(
        "demo-song",
        "Demo Artist",
        "Demo Song",
        analysis_dir,
        audio_dir,
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        skip_wikipedia=True,
    )

    assert context["lyrics"]["source"] == "youtube-music-timed-lyrics"
    assert context["lyrics"]["timed_lines"][0]["text"] == "timed only"
    assert context["lyrics"]["full_text"] == "timed only"
    assert context["lyrics"]["genius_text"] is None


def test_provider_timed_lyrics_normalizes_provider_lines(monkeypatch):
    from galdr import provider_timed_lyrics

    class FakeYTMusic:
        def get_watch_playlist(self, videoId):
            assert videoId == "DO0yaw3Wj1A"
            return {"lyrics": "MPLYt_demo"}

        def get_lyrics(self, browse_id, timestamps=False):
            assert browse_id == "MPLYt_demo"
            assert timestamps is True
            return {
                "hasTimestamps": True,
                "source": "Source: Musixmatch",
                "lyrics": [
                    {"text": "♪", "start_time": 0, "end_time": 1000, "id": 0},
                    {"text": "Timed words", "start_time": 10650, "end_time": 15100, "id": 1},
                ],
            }

    monkeypatch.setattr(provider_timed_lyrics, "YTMusic", FakeYTMusic)

    result = provider_timed_lyrics.fetch_provider_timed_lyrics("DO0yaw3Wj1A")

    assert result["found"] is True
    assert result["provider_source"] == "Source: Musixmatch"
    assert result["line_count"] == 1
    assert result["timed_lines"] == [
        {
            "start": 10.65,
            "end": 15.1,
            "ts": "0:10.65",
            "text": "Timed words",
            "source": "youtube-music-timed-lyrics",
            "confidence": "provider-timed",
            "line_id": 1,
        }
    ]


def test_provider_timed_lyrics_recovers_raw_rows_after_cuerange_error(monkeypatch):
    from galdr import provider_timed_lyrics

    class MobileContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeYTMusic:
        def get_watch_playlist(self, videoId):
            assert videoId == "DO0yaw3Wj1A"
            return {"lyrics": "MPLYt_demo"}

        def get_lyrics(self, browse_id, timestamps=False):
            assert browse_id == "MPLYt_demo"
            assert timestamps is True
            raise KeyError("cueRange")

        def as_mobile(self):
            return MobileContext()

        def _send_request(self, endpoint, payload):
            assert endpoint == "browse"
            assert payload == {"browseId": "MPLYt_demo"}
            return {
                "contents": {
                    "elementRenderer": {
                        "newElement": {
                            "type": {
                                "componentType": {
                                    "model": {
                                        "timedLyricsModel": {
                                            "lyricsData": {
                                                "timedLyricsData": [
                                                    {
                                                        "lyricLine": "♪",
                                                        "cueRange": {
                                                            "startTimeMilliseconds": "0",
                                                            "endTimeMilliseconds": "1000",
                                                            "metadata": {"id": "0"},
                                                        },
                                                    },
                                                    {
                                                        "lyricLine": "Timed words",
                                                        "cueRange": {
                                                            "startTimeMilliseconds": "10650",
                                                            "endTimeMilliseconds": "15100",
                                                            "metadata": {"id": "1"},
                                                        },
                                                    },
                                                ],
                                                "sourceMessage": "Source: LyricFind",
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

    monkeypatch.setattr(provider_timed_lyrics, "YTMusic", FakeYTMusic)

    result = provider_timed_lyrics.fetch_provider_timed_lyrics("DO0yaw3Wj1A")

    assert result["found"] is True
    assert result["provider_source"] == "Source: LyricFind"
    assert result["line_count"] == 1
    assert result["timed_lines"][0]["text"] == "Timed words"
    assert result["timed_lines"][0]["start"] == 10.65
    assert result["timed_lines"][0]["end"] == 15.1


def test_provider_timed_lyrics_marks_cuerange_less_rows_as_untimed(monkeypatch):
    from galdr import provider_timed_lyrics

    class MobileContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeYTMusic:
        def get_watch_playlist(self, videoId):
            assert videoId == "Tn7wvu8R4Wk"
            return {"lyrics": "MPLYt_demo"}

        def get_lyrics(self, browse_id, timestamps=False):
            assert browse_id == "MPLYt_demo"
            assert timestamps is True
            raise KeyError("cueRange")

        def as_mobile(self):
            return MobileContext()

        def _send_request(self, endpoint, payload):
            assert endpoint == "browse"
            assert payload == {"browseId": "MPLYt_demo"}
            return {
                "contents": {
                    "elementRenderer": {
                        "newElement": {
                            "type": {
                                "componentType": {
                                    "model": {
                                        "timedLyricsModel": {
                                            "lyricsData": {
                                                "timedLyricsData": [
                                                    {"lyricLine": "La nuit comme une toile"},
                                                    {"lyricLine": "Suspendue s'effondre"},
                                                ],
                                                "sourceMessage": "Source: LyricFind",
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

    monkeypatch.setattr(provider_timed_lyrics, "YTMusic", FakeYTMusic)

    result = provider_timed_lyrics.fetch_provider_timed_lyrics("Tn7wvu8R4Wk")

    assert result["found"] is False
    assert result["reason"] == "Provider lyrics are not timed"
    assert result["lyrics_available"] is True
    assert result["untimed_line_count"] == 2
    assert result["provider_source"] == "Source: LyricFind"
    assert result["error"] == "KeyError: 'cueRange'"


def test_provider_timed_lyrics_fails_soft_on_provider_error(monkeypatch):
    from galdr import provider_timed_lyrics

    class FakeYTMusic:
        def get_watch_playlist(self, videoId):
            raise KeyError("cueRange")

    monkeypatch.setattr(provider_timed_lyrics, "YTMusic", FakeYTMusic)

    result = provider_timed_lyrics.fetch_provider_timed_lyrics("dQw4w9WgXcQ")

    assert result["found"] is False
    assert result["reason"] == "Provider timed lyrics fetch failed"
    assert "KeyError" in result["error"]


class TestSurfaceFeatureBank:
    def test_surface_feature_bank_outputs_bounded_listener_evidence(self):
        from galdr.surface import compute_surface_feature_bank, surface_snapshot

        sr = 22050
        t = np.linspace(0, 2.0, sr * 2, endpoint=False)
        tone = 0.15 * np.sin(2 * np.pi * 220 * t)
        click = np.zeros_like(tone)
        click[:: sr // 4] = 0.8
        y = (tone + click).astype(np.float32)

        bank = compute_surface_feature_bank(y, sr, hop_sec=0.5)

        assert bank["hop_sec"] == pytest.approx(0.5)
        assert len(bank["times"]) == 4
        bounded_fields = (
            "roughness",
            "noise_density",
            "transient_attack",
            "sustain_drone",
            "band_pressure",
            "surface_motion",
            "punch",
            "bass_weight",
            "body_weight",
            "presence_weight",
            "air_weight",
            "brightness_tilt",
            "percussive_ratio",
        )
        for field in bounded_fields:
            assert len(bank[field]) == len(bank["times"])
            assert all(0.0 <= value <= 1.0 for value in bank[field])

        for field in ("harmonic_rms", "percussive_rms"):
            assert len(bank[field]) == len(bank["times"])
            assert all(value >= 0.0 for value in bank[field])

        snapshot = surface_snapshot(bank, 0)
        assert snapshot["roughness_state"] in {"smooth", "grained", "abrasive"}
        assert snapshot["motion_state"] in {"sustained", "moving", "striking"}
        assert snapshot["pressure_state"] in {"thin", "held", "pressurized"}
        assert snapshot["tilt_state"] in {"dark", "balanced", "bright"}
        assert 0.0 <= snapshot["percussive_ratio"] <= 1.0

    def test_surface_feature_bank_separates_tone_noise_and_attacks(self):
        from galdr.surface import compute_surface_feature_bank, surface_snapshot

        sr = 22050
        t = np.linspace(0, 2.0, sr * 2, endpoint=False)
        tone = (0.15 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        rng = np.random.default_rng(7)
        noise = (0.08 * rng.standard_normal(len(t))).astype(np.float32)
        click = np.zeros_like(tone)
        click[:: sr // 4] = 0.8
        clicky = (tone + click).astype(np.float32)

        tone_bank = compute_surface_feature_bank(tone, sr, hop_sec=0.5)
        noise_bank = compute_surface_feature_bank(noise, sr, hop_sec=0.5)
        click_bank = compute_surface_feature_bank(clicky, sr, hop_sec=0.5)

        assert np.mean(noise_bank["noise_density"]) > np.mean(tone_bank["noise_density"])
        assert np.mean(noise_bank["roughness"]) > np.mean(tone_bank["roughness"])
        assert surface_snapshot(noise_bank, 0)["roughness_state"] == "abrasive"
        assert surface_snapshot(click_bank, 0)["roughness_state"] == "smooth"
        assert np.mean(click_bank["transient_attack"]) > np.mean(tone_bank["transient_attack"])
        assert np.mean(click_bank["surface_motion"]) > np.mean(tone_bank["surface_motion"])
        assert np.mean(click_bank["punch"]) > np.mean(tone_bank["punch"])
        assert np.mean(tone_bank["sustain_drone"]) > np.mean(click_bank["sustain_drone"])


    def test_surface_feature_bank_tracks_band_balance_and_brightness_tilt(self):
        from galdr.surface import compute_surface_feature_bank

        sr = 22050
        t = np.linspace(0, 2.0, sr * 2, endpoint=False)
        bass = (0.15 * np.sin(2 * np.pi * 80 * t)).astype(np.float32)
        air = (0.15 * np.sin(2 * np.pi * 6000 * t)).astype(np.float32)

        bass_bank = compute_surface_feature_bank(bass, sr, hop_sec=0.5)
        air_bank = compute_surface_feature_bank(air, sr, hop_sec=0.5)

        assert np.mean(bass_bank["bass_weight"]) > np.mean(air_bank["bass_weight"])
        assert np.mean(air_bank["air_weight"]) > np.mean(bass_bank["air_weight"])
        assert np.mean(air_bank["brightness_tilt"]) > np.mean(bass_bank["brightness_tilt"])


    def test_surface_punch_is_gated_by_audible_body(self):
        from galdr.surface import compute_surface_feature_bank

        sr = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        quiet_click = np.zeros_like(t)
        loud_click = np.zeros_like(t)
        quiet_click[:: sr // 2] = 0.01
        loud_click[:: sr // 2] = 0.8

        quiet_bank = compute_surface_feature_bank(quiet_click.astype(np.float32), sr, hop_sec=0.5)
        loud_bank = compute_surface_feature_bank(loud_click.astype(np.float32), sr, hop_sec=0.5)

        assert np.mean(quiet_bank["transient_attack"]) > 0.0
        assert np.mean(quiet_bank["punch"]) < 0.10
        assert np.mean(loud_bank["punch"]) > np.mean(quiet_bank["punch"]) + 0.25

    def test_band_pressure_requires_more_than_bass_weight(self):
        from galdr.surface import compute_surface_feature_bank, surface_snapshot

        sr = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        bass = (0.15 * np.sin(2 * np.pi * 80 * t)).astype(np.float32)
        rng = np.random.default_rng(11)
        dense_low_body = (
            0.25 * np.sin(2 * np.pi * 80 * t)
            + 0.20 * np.sin(2 * np.pi * 300 * t)
            + 0.03 * rng.standard_normal(len(t))
        ).astype(np.float32)

        bass_bank = compute_surface_feature_bank(bass, sr, hop_sec=0.5)
        dense_bank = compute_surface_feature_bank(dense_low_body, sr, hop_sec=0.5)

        assert np.mean(bass_bank["bass_weight"]) > 0.95
        assert np.mean(bass_bank["band_pressure"]) < 0.45
        assert surface_snapshot(bass_bank, 0)["pressure_state"] != "pressurized"
        assert np.mean(dense_bank["band_pressure"]) > np.mean(bass_bank["band_pressure"]) + 0.10

    def test_surface_feature_bank_rejects_non_positive_hop(self):
        from galdr.surface import compute_surface_feature_bank

        with pytest.raises(ValueError, match="hop_sec must be positive"):
            compute_surface_feature_bank(np.ones(22050, dtype=np.float32), 22050, hop_sec=0)

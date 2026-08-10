"""galdr assemble — build a model prompt from context + analysis data.

Two entry points:
  assemble_prompt(analysis, context, ...)  — takes data dicts directly (Python API)
  assemble_prompt_from_disk(slug, ...)     — loads from analysis dir (CLI path)

Output structure (controlled by mode):
  [Template instructions]  <- prepended when --template is not "none"
  [Background]             <- artist background + song context (full, context)
  [Galdr analysis]         <- metrics, events, melody        (all modes)
  [Lyrics]                 <- timed lyrics / captions         (full, lyrics)
  [Frame descriptions]     <- vision descriptions at events  (full, if present)
  [Optional witness]       <- inner-ear packet or hearing stream (when provided)

Modes:
  full     — everything available. Best default output. (DEFAULT)
  lyrics   — galdr + lyrics. Words, no story.
  context  — galdr + background. Story, no words.
  blind    — galdr data only. No prior knowledge. Purest experience.

Templates:
  none     — data block only, user adds their own instructions. (DEFAULT)
  arc      — prepends ARC-PROMPT.md (listening experience: body, attention, time)
  first    — alias for arc
  arc-family — prepends the shared ARC prompt-family base, optionally with a lens
  <path>   — any file path, read directly

Default mode is full (graceful degradation — missing sections silently omitted).
Default template is none.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path
from importlib import resources as pkg_resources

from .arc import derive_arc_scales, select_arc_scale
from .boundary import derive_boundary_candidates
from .metric_vocabulary import display_name, glossary_lines
from .salience import synthesize_salience
from .captions import dedup_captions_with_timestamps, parse_vtt
from .witness import HEARING_STREAM_SCHEMA, INNER_EAR_PACKET_SCHEMA, validate_witness_packet, witness_kind


# ─── Mode definitions ─────────────────────────────────────────────────────────

MODES = {
    "full":    {"background": True,  "metrics": True, "lyrics": True,  "frames": True},
    "lyrics":  {"background": False, "metrics": True, "lyrics": True,  "frames": False},
    "context": {"background": True,  "metrics": True, "lyrics": False, "frames": False},
    "blind":   {"background": False, "metrics": True, "lyrics": False, "frames": False},
}

DEFAULT_MODE = "full"
DEFAULT_TEMPLATE = "none"

BUNDLED_TEMPLATES = {
    "arc": "ARC-PROMPT.md",
    "first": "ARC-PROMPT.md",  # "first" aliased to "arc"
    "arc-family": "ARC-FAMILY-BASE.md",
    "inner-ear": "INNER-EAR-PROMPT.md",
}
ARC_LENS_TEMPLATES = {
    "default": "ARC-LENS-DEFAULT.md",
    "sound": "ARC-LENS-SOUND.md",
    "sound-sync": "ARC-LENS-SOUND-SYNC.md",
    "dance": "ARC-LENS-DANCE.md",
    "structure": "ARC-LENS-STRUCTURE.md",
    "meaning": "ARC-LENS-MEANING.md",
    "lyrics-study": "ARC-LENS-LYRICS-STUDY.md",
    "classical": "ARC-LENS-CLASSICAL.md",
    "ritual": "ARC-LENS-RITUAL.md",
}
ARC_LENS_ALIASES = {
    "arc-default": "default",
    "arc-sound": "sound",
    "arc-sound-sync": "sound-sync",
    "arc-dance": "dance",
    "arc-structure": "structure",
    "arc-meaning": "meaning",
    "arc-lyrics-study": "lyrics-study",
    "arc-classical": "classical",
    "arc-ritual": "ritual",
}

# These lenses are complete prompt contracts rather than variants of the
# chronological read-along family. Prepending ARC-FAMILY-BASE would make them
# spend instructions undoing chronology, prose-shape, and output-format rules.
STANDALONE_ARC_LENSES = {"meaning", "structure", "sound-sync"}


def _read_bundled_template(filename: str) -> str | None:
    try:
        ref = pkg_resources.files("galdr.templates") / filename
        return ref.read_text(encoding="utf-8")
    except Exception:
        # Fallback for editable installs: templates/ sibling to this file
        local_path = Path(__file__).parent / "templates" / filename
        if local_path.exists():
            return local_path.read_text()
    return None


# ─── Template resolution ──────────────────────────────────────────────────────

def resolve_template(name: str, docs_dir: Path | None = None, lens: str | None = None) -> str | None:
    """Resolve a template name or path to its text content.

    Resolution order:
      1. "none"            -> returns None (no template)
      2. File path         -> used directly (absolute or relative)
      3. docs_dir/{name}.md -> user's local override (e.g. custom-template.md)
      4. Bundled package templates via importlib.resources (arc, first, arc-family)

    Bundled templates live in galdr/templates/ and are shipped with the package,
    so they work after pip install without needing the source repo present.
    """
    if name in ARC_LENS_ALIASES:
        alias_lens = ARC_LENS_ALIASES[name]
        if lens and lens != alias_lens:
            raise ValueError(f"Template '{name}' already selects lens '{alias_lens}', got '{lens}'")
        name = "arc-family"
        lens = alias_lens

    if lens and lens not in ARC_LENS_TEMPLATES:
        raise ValueError(
            f"Unknown lens '{lens}'. Choose from: {', '.join(ARC_LENS_TEMPLATES)}"
        )

    if name == "none":
        if lens:
            name = "arc-family"
        else:
            return None

    # Explicit file path
    p = Path(name)
    if p.exists():
        base = p.read_text()
        if lens:
            return _append_lens(base, lens, docs_dir)
        return base

    # Local docs override (dev workflow — docs/ takes precedence over bundled)
    if docs_dir:
        local = docs_dir / f"{name}.md"
        if local.exists():
            base = local.read_text()
            if lens:
                return _append_lens(base, lens, docs_dir)
            return base

    # Bundled package templates (works after pip install)
    if name in BUNDLED_TEMPLATES:
        filename = BUNDLED_TEMPLATES[name]
        base = _read_bundled_template(filename)
        if base is not None:
            if lens:
                return _append_lens(base, lens, docs_dir)
            return base

    raise ValueError(
        f"Template '{name}' not found. "
        f"Use 'none', 'arc', 'first', 'arc-family', an arc-* lens alias, or a file path. "
        f"Known templates: {', '.join([*BUNDLED_TEMPLATES, *ARC_LENS_ALIASES])}"
    )


def _append_lens(base: str, lens: str, docs_dir: Path | None = None) -> str:
    """Resolve a lens, appending the family base only when the lens uses it."""
    lens_text = None
    if docs_dir:
        local = docs_dir / f"arc-lens-{lens}.md"
        if local.exists():
            lens_text = local.read_text()
    if lens_text is None:
        lens_text = _read_bundled_template(ARC_LENS_TEMPLATES[lens])
    if lens_text is None:
        raise ValueError(f"Lens template for '{lens}' not found")
    if lens in STANDALONE_ARC_LENSES:
        return f"{lens_text.strip()}\n"
    return f"{base.strip()}\n\n---\n\n{lens_text.strip()}\n"


# ─── Loaders ──────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict | None:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None


def load_analysis(slug: str, analysis_dir: Path) -> dict:
    """Load all galdr analysis files for a track slug.

    Files are named {slug}_{module}.json (e.g. 7-helvegen_report.json).
    Returns a dict with keys: report, perception, harmony, melody, overtone.
    Missing files produce None values — callers must handle gracefully.
    """
    d = analysis_dir / slug
    modules = ["report", "perception", "harmony", "melody", "overtone"]
    analysis = {m: _load_json(d / f"{slug}_{m}.json") for m in modules}

    # The perception summary and sampled stream are written as separate files.
    # Attach the stream for prompt assembly so local listening events can be
    # exposed alongside macro structural events.
    stream = _load_json(d / f"{slug}_stream.json")
    if stream and isinstance(analysis.get("perception"), dict):
        if isinstance(stream, dict) and isinstance(stream.get("stream"), list):
            analysis["perception"].setdefault("stream_metadata", {
                k: v for k, v in stream.items() if k != "stream"
            })
            analysis["perception"]["stream"] = stream["stream"]
        else:
            analysis["perception"]["stream"] = stream

    return analysis


def load_context(slug: str, analysis_dir: Path) -> dict:
    """Load context.json for a slug. Returns empty dict if not found."""
    path = analysis_dir / slug / "context.json"
    return _load_json(path) or {}


def _has_lyrics(context: dict) -> bool:
    """Return True when context already contains usable lyric/caption text."""
    lyrics = context.get("lyrics")
    if not lyrics:
        return False
    if isinstance(lyrics, str):
        return bool(lyrics.strip())
    if lyrics.get("timed_lines"):
        return True
    if lyrics.get("caption_lines"):
        return True
    if (lyrics.get("genius_text") or "").strip():
        return True
    if (lyrics.get("full_text") or "").strip():
        return True
    return False


def _caption_candidates(slug: str, analysis_dir: Path, context: dict) -> list[Path]:
    """Find raw VTT caption files associated with a slug."""
    candidates: list[Path] = []
    dl = context.get("download") if isinstance(context.get("download"), dict) else {}
    captions_file = dl.get("captions_file") or context.get("captions_file")
    if captions_file:
        candidates.append(Path(captions_file))
    audio_file = context.get("audio_file") or dl.get("audio_file")
    if audio_file:
        audio_dir = Path(audio_file).expanduser().parent
        candidates.extend(sorted(audio_dir.glob(f"{slug}*.vtt")))
    candidates.extend(sorted((analysis_dir.parent / "audio").glob(f"{slug}*.vtt")))
    candidates.extend(sorted(Path("audio").glob(f"{slug}*.vtt")))
    seen = set()
    unique = []
    for path in candidates:
        resolved = path.expanduser()
        key = str(resolved)
        if key not in seen and resolved.exists():
            seen.add(key)
            unique.append(resolved)
    return unique


def _augment_context_with_caption_file(slug: str, analysis_dir: Path, context: dict) -> dict:
    """Add lyrics from a raw VTT file when context.json lacks them."""
    if _has_lyrics(context):
        return context
    for path in _caption_candidates(slug, analysis_dir, context):
        segments = parse_vtt(path)
        caption_lines = dedup_captions_with_timestamps(segments)
        if caption_lines:
            augmented = dict(context)
            augmented["lyrics"] = {
                "source": "local-vtt-captions",
                "captions_file": str(path),
                "caption_lines": caption_lines,
                "full_text": "\n".join(line["text"] for line in caption_lines),
                "genius_text": None,
            }
            return augmented
    return context


def _lyrics_source_label(lyrics: dict) -> str | None:
    """Return a short human-readable source label for the Lyrics section."""
    source = lyrics.get("source")
    if source == "local-vtt-captions":
        path = lyrics.get("captions_file")
        return f"local VTT captions ({path})" if path else "local VTT captions"
    if source == "youtube-auto-captions":
        return "YouTube auto-captions"
    if source == "youtube-music-timed-lyrics":
        timed_source = lyrics.get("timed_lyrics_source") or {}
        provider = timed_source.get("provider_source")
        return f"YouTube Music timed lyrics ({provider})" if provider else "YouTube Music timed lyrics"
    if source == "genius+youtube-music-timed-lyrics":
        timed_source = lyrics.get("timed_lyrics_source") or {}
        provider = timed_source.get("provider_source")
        suffix = f" + YouTube Music timed lyrics ({provider})" if provider else " + YouTube Music timed lyrics"
        url = lyrics.get("genius_url")
        return f"Genius ({url}){suffix}" if url else f"Genius lyrics{suffix}"
    if source == "genius+autocaptions":
        return "Genius lyrics + YouTube auto-captions"
    if source == "genius":
        url = lyrics.get("genius_url")
        return f"Genius ({url})" if url else "Genius"
    return source if isinstance(source, str) and source.strip() and source != "none" else None


def _lyrics_timing_verdict(lyrics: dict) -> dict[str, str]:
    """Return assemble-facing labels for lyric timing confidence."""
    if lyrics.get("timed_lines"):
        return {
            "surface": "timed_lines",
            "heading": "YouTube Music timed lyrics",
            "confidence_note": "provider line timing; verify central words",
        }

    if lyrics.get("caption_lines"):
        source = lyrics.get("source")
        if source == "youtube-auto-captions":
            return {
                "surface": "caption_lines",
                "heading": "autocaptions",
                "confidence_note": "coarse timing; text may contain mishears",
            }
        if source == "local-vtt-captions":
            return {
                "surface": "caption_lines",
                "heading": "local VTT captions",
                "confidence_note": "coarse timing; text may contain transcription or alignment errors",
            }
        return {
            "surface": "caption_lines",
            "heading": "captions",
            "confidence_note": "coarse timing; verify text and alignment",
        }

    return {
        "surface": "none",
        "heading": "Genius",
        "confidence_note": "clean text, no timestamps",
    }


# ─── Section builders ─────────────────────────────────────────────────────────

def _context_is_prompt_usable(ctx_value) -> bool:
    """Return True when fetched context is trusted enough for prompt assembly."""
    if not ctx_value:
        return False
    if not isinstance(ctx_value, dict):
        return bool(str(ctx_value).strip())
    if not ctx_value.get("found"):
        return False
    confidence = ctx_value.get("confidence")
    if confidence is None:
        return True  # legacy context.json files had no confidence field
    return bool(ctx_value.get("use_in_prompt", confidence in {"high", "medium"}))


def _extract_text(ctx_value) -> str:
    """Extract prompt-usable text from a context field."""
    if isinstance(ctx_value, dict):
        if _context_is_prompt_usable(ctx_value):
            return ctx_value.get("extract", "")
        return ""
    return str(ctx_value) if ctx_value else ""


def _format_source_tail(item: dict) -> str:
    """Format optional provenance details for a context claim."""
    parts = []
    source_type = item.get("source_type")
    confidence = item.get("confidence")
    source_url = item.get("source_url")
    if source_type:
        parts.append(str(source_type))
    if confidence:
        parts.append(f"confidence: {confidence}")
    if source_url:
        parts.append(str(source_url))
    return f" ({'; '.join(parts)})" if parts else ""


def _build_song_context(ctx_value) -> list[str]:
    """Build song-specific context lines without treating it as policy."""
    if not ctx_value:
        return []
    if not isinstance(ctx_value, dict):
        text = str(ctx_value).strip()
        return [f"Song context: {text}"] if text else []

    lines = []

    summary = str(ctx_value.get("summary") or "").strip()
    if summary:
        lines.append(f"Song context: {summary}")

    extract = _extract_text(ctx_value).strip()
    if extract and extract != summary:
        lines.append(f"Song context: {extract}")

    claims = ctx_value.get("claims")
    if isinstance(claims, list):
        for item in claims:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or "").strip()
            if claim:
                lines.append(f"Song context claim: {claim}{_format_source_tail(item)}")

    lyric_references = ctx_value.get("lyric_references")
    if isinstance(lyric_references, list):
        for item in lyric_references:
            if not isinstance(item, dict):
                continue
            reference = str(item.get("reference") or "").strip()
            meaning = str(item.get("meaning") or "").strip()
            if not reference and not meaning:
                continue
            text = f"{reference}: {meaning}" if reference and meaning else reference or meaning
            lines.append(f"Song lyric reference: {text}{_format_source_tail(item)}")

    source_notes = ctx_value.get("source_notes")
    if isinstance(source_notes, list):
        for note in source_notes:
            note_text = str(note).strip()
            if note_text:
                lines.append(f"Song context source note: {note_text}")

    return lines


def _build_track_header(context: dict) -> str | None:
    """Build a brief track identity block: artist, title, source URL."""
    artist = context.get("artist", "")
    title = context.get("title", "")
    url = context.get("youtube_url", "") or context.get("source_url", "")

    lines = []
    if artist or title:
        lines.append(f"## Track\n")
        if artist:
            lines.append(f"Artist: {artist}")
        if title:
            lines.append(f"Title: {title}")
    if url:
        lines.append(f"Source: {url}")

    return "\n".join(lines) if lines else None


def _build_background(context: dict) -> str | None:
    """Build background section from artist and song context."""
    artist_text = _extract_text(context.get("artist_context"))
    song_context_lines = _build_song_context(context.get("song_context"))

    bg_parts = []
    if artist_text:
        bg_parts.append(f"Artist background: {artist_text}")
    bg_parts.extend(song_context_lines)

    if not bg_parts:
        return None

    lines = ["## Background\n"]
    lines.extend(bg_parts)
    return "\n".join(lines)


def _fmt_time(seconds: float) -> str:
    """Format seconds as M:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def _tempo_feel(value: float) -> str:
    """Translate raw BPM into listener-facing pulse language."""
    if value <= 0:
        return "unknown pulse"
    if value < 75:
        return "slow pulse"
    if value < 105:
        return "moderate pulse"
    if value < 140:
        return "quick pulse"
    if value < 175:
        return "fast pulse"
    return "very fast pulse"


def _confidence_feel(value: float) -> str:
    """Translate numeric pulse confidence without leaking metric values."""
    if value < 0.35:
        return "low confidence"
    if value < 0.70:
        return "moderate confidence"
    return "high confidence"


def _fmt_tempo(report: dict) -> str:
    """Format tempo as felt pulse language, not raw BPM."""
    detected = report.get("detected_pulse_bpm", 0)
    felt = report.get("felt_pulse_bpm")
    confidence = report.get("pulse_confidence")
    ambiguous = bool(report.get("pulse_ambiguous"))
    note = report.get("pulse_note")

    if felt is None:
        return f"Pulse: {_tempo_feel(float(detected))} (detected)"

    line = f"Pulse: {_tempo_feel(float(felt))}"
    if ambiguous or abs(float(felt) - float(detected)) >= 1.0:
        line += " (felt pulse; detected pulse ambiguous/suspect)"

    if confidence is not None:
        line += f"; {_confidence_feel(float(confidence))}"
    if note:
        line += f" — {note}"
    return line


def _event_rank(event: str, btype: str = "") -> int:
    """Sort simultaneous prompt events by listening hierarchy."""
    if btype == "silence":
        return 0
    if btype:
        return 60
    if event in {"attention_arrives", "attention_releases"}:
        return 10
    if event in {
        "motor_capture_arrives",
        "motor_capture_recedes",
    }:
        return 20
    if event in {"weight_arrives", "weight_lifts", "surface_hardens"}:
        return 30
    if event in {"pressure_builds", "pressure_releases"}:
        return 40
    if event in {"phrase_lifts", "phrase_drops", "ornamental_flash"}:
        return 50
    return 70


def _summarize_arc_spans(spans: list[dict]) -> dict | None:
    """Summarize arc spans at one perceptual scale."""
    if not spans:
        return None

    total_frames = sum(span["frame_count"] for span in spans)
    if total_frames <= 0:
        return None

    frame_counts = Counter()
    run_counts = Counter()
    transitions = Counter()
    weighted = defaultdict(float)
    previous = None
    for span in spans:
        label = span["label"]
        frame_count = span["frame_count"]
        frame_counts[label] += frame_count
        run_counts[label] += 1
        for key in ["mean_attention", "mean_pattern", "mean_pressure", "mean_body", "mean_weight", "silence_ratio"]:
            weighted[key] += span[key] * frame_count
        if previous:
            transitions[(previous, label)] += 1
        previous = label

    timeline = []
    last_t = spans[-1]["end"]
    window_size = 30.0
    start = 0.0
    while start <= last_t:
        end = start + window_size
        counts = Counter()
        for span in spans:
            overlap = max(0.0, min(float(span["end"]), end) - max(float(span["start"]), start))
            if overlap > 0:
                counts[span["label"]] += overlap
        if counts:
            timeline.append((start, end, counts.most_common(3)))
        start = end

    return {
        "span_count": len(spans),
        "total_frames": total_frames,
        "frame_counts": frame_counts,
        "run_counts": run_counts,
        "weighted": {key: value / total_frames for key, value in weighted.items()},
        "transitions": transitions,
        "longest": sorted(spans, key=lambda span: span["frame_count"], reverse=True)[:8],
        "timeline": timeline,
        "final_label": spans[-1]["label"],
    }


def _arc_summary(stream: list[dict]) -> dict | None:
    """Summarize arc-pattern scales for prompt assembly."""
    scales = derive_arc_scales(stream)
    selected_scale, reason = select_arc_scale(scales)
    scale_summaries = {name: _summarize_arc_spans(spans) for name, spans in scales.items()}
    selected = scale_summaries.get(selected_scale)
    if not selected:
        return None

    selected = dict(selected)
    selected["selected_scale"] = selected_scale
    selected["selection_reason"] = reason
    selected["scale_counts"] = {name: summary["span_count"] for name, summary in scale_summaries.items() if summary}
    selected["scale_summaries"] = scale_summaries
    return selected



def _build_boundary_candidates(stream: list[dict]) -> str | None:
    """Build a prompt-facing section for possible song/interlude boundaries."""
    candidates = derive_boundary_candidates(stream)
    if not candidates:
        return None

    lines = ["### Boundary candidates\n"]
    lines.append(
        "These are possible song, interlude, or large-section boundaries. "
        "They are separate from arc transitions: a boundary candidate marks a low-energy gap "
        "plus reset/re-entry evidence, not merely a listener-state change."
    )
    for candidate in candidates[:12]:
        lines.append(
            f"- {_fmt_time(candidate['start'])}–{_fmt_time(candidate['end'])} "
            f"{candidate['kind']} (confidence {candidate['confidence']:.2f}; "
            f"gap {candidate['duration']:.1f}s; reset {candidate['reset_strength']:.2f}; "
            f"re-entry {candidate['reentry_strength']:.2f})"
        )
    lines.append(
        "Use these as terrain markers for long uploads and albums. Confirm boundaries from context "
        "when available, and do not treat ambient continuity as a track cut unless the post-gap state resets."
    )
    return "\n".join(lines)

def _arc_archetype(summary: dict) -> tuple[str, str]:
    """Name the dominant felt mechanism implied by arc-span shape."""
    total = summary["total_frames"]
    frames = summary["frame_counts"]
    weighted = summary["weighted"]
    held_pct = frames.get("held", 0) / total
    returning_pct = frames.get("returning", 0) / total
    emptying_pct = frames.get("emptying", 0) / total
    churn_pct = (frames.get("building", 0) + frames.get("releasing", 0)) / total
    transition_rate = sum(summary["transitions"].values()) / total
    longest = summary["longest"][0]["frame_count"] / total if summary["longest"] else 0.0
    span_count = summary["span_count"]
    mean_body = weighted.get("mean_body", 0.0)
    final_label = summary.get("final_label", "")

    if emptying_pct >= 0.08 or returning_pct >= 0.28:
        return (
            "collapse-return",
            "withdrawal and re-entry matter; describe subtraction, recovery, and what remains after the hold loosens.",
        )
    if held_pct >= 0.60 and longest >= 0.08:
        if held_pct >= 0.90 and span_count <= 8 and mean_body >= 0.62 and transition_rate <= 0.03:
            return (
                "martial/motor command",
                "a stable pulse and motor capture dominate; write sustained forward motion as the dramatic argument.",
            )
        if span_count <= 12 and final_label in {"emptying", "returning"}:
            return (
                "suspended narrative gravity",
                "long holds carry the story; write suspension, plainness, and terminal draining rather than generic plateau.",
            )
        return (
            "plateau track",
            "long held spans dominate; write stability as active sustained pressure rather than stillness.",
        )
    if held_pct >= 0.45 and churn_pct >= 0.25 and transition_rate >= 0.18:
        return (
            "twitch-loop under calm surface",
            "the track may sound static, but the listener-state keeps micro-correcting through build/release flips.",
        )
    if frames.get("building", 0) > frames.get("releasing", 0) * 1.4 and churn_pct >= 0.20:
        return (
            "pressure ratchet",
            "repeated building outweighs clean release; write accumulation before relief.",
        )
    if held_pct >= 0.55:
        return (
            "ritual lock",
            "high hold and pattern dominate; write repetition as embodied commitment, not lack of change.",
        )
    return (
        "mixed arc",
        "no single state dominates; move through local shifts proportionally and avoid flattening the song into one mood.",
    )


def _build_arc_structure(stream: list[dict]) -> str | None:
    """Build a prompt-facing arc-span section from local stream data."""
    summary = _arc_summary(stream)
    if not summary:
        return None

    archetype, guidance = _arc_archetype(summary)
    total = summary["total_frames"]
    weighted = summary["weighted"]
    lines = ["### Arc structure\n"]
    scale_counts = summary.get("scale_counts", {})
    if scale_counts:
        rendered_counts = ", ".join(f"{name} {count}" for name, count in scale_counts.items())
        lines.append(
            f"Pattern scale selected: {summary.get('selected_scale', 'standard')} "
            f"({summary.get('selection_reason', 'default readable scale')}); available scales: {rendered_counts}."
        )
    lines.append(f"Felt mechanism: {archetype} — {guidance}")
    lines.append(
        f"Selected span count: {summary['span_count']} spans across {total} frames; "
        f"means attention {weighted['mean_attention']:.3f}, pattern {weighted['mean_pattern']:.3f}, "
        f"pressure {weighted['mean_pressure']:.3f}, body {weighted['mean_body']:.3f}, "
        f"silence {weighted['silence_ratio']:.3f}"
    )
    lines.append("State distribution:")
    for label, frames in summary["frame_counts"].most_common():
        pct = frames / total * 100
        runs = summary["run_counts"][label]
        lines.append(f"- {label}: {pct:.1f}% of frames across {runs} runs")

    transitions = summary["transitions"].most_common(5)
    if transitions:
        rendered = ", ".join(f"{a}→{b} x{count}" for (a, b), count in transitions)
        lines.append(f"Top transitions: {rendered}")

    lines.append("Longest spans:")
    for span in summary["longest"][:5]:
        lines.append(
            f"- {_fmt_time(span['start'])}–{_fmt_time(span['end'])} {span['label']} "
            f"({span['frame_count']} frames; attention {span['mean_attention']:.3f}, "
            f"pattern {span['mean_pattern']:.3f}, pressure {span['mean_pressure']:.3f}, "
            f"body {span['mean_body']:.3f})"
        )

    lines.append("Coarse timeline:")
    for start, end, counts in summary["timeline"]:
        rendered = ", ".join(f"{label} {amount:.1f}s" for label, amount in counts)
        lines.append(f"- {_fmt_time(start)}–{_fmt_time(end)}: {rendered}")

    lines.append(
        "Use this section as a private second sense for experience prose. Never mention galdr, "
        "detectors, metrics, percentages, frame counts, span counts, or state labels in the final prose. "
        "Translate them into felt experience: stability, micro-correction, pressure, withdrawal, or re-entry."
    )
    return "\n".join(lines)


def _build_metrics(analysis: dict, *, compact: bool = False) -> str:
    """Build core galdr metrics section."""
    report = analysis.get("report") or {}
    perception = analysis.get("perception") or {}
    harmony = analysis.get("harmony") or {}
    melody = analysis.get("melody") or {}
    overtone = analysis.get("overtone") or {}

    if not any([report, perception, harmony, melody, overtone]):
        return "## Galdr Analysis\n\nNo structural analysis files found for this track."

    lines = ["## Galdr Analysis\n"]

    # Track identity — field names from report.json. Avoid fabricating
    # zero-valued metrics when only partial/legacy files are present.
    has_duration = "duration_seconds" in report
    if not has_duration and not any([perception, harmony, melody, overtone]):
        return "## Galdr Analysis\n\nNo structural analysis files found for this track."

    duration = report.get("duration_seconds")
    pulse = report.get("pulse", 0)
    har_e = report.get("harmonic_weight", 0)
    perc_e = report.get("percussive_weight", 0)

    if has_duration:
        lines.append(f"Duration: {_fmt_time(duration)} ({duration:.1f}s)")
    else:
        lines.append("Duration: unavailable")
    lines.append(_fmt_tempo(report))
    entrainment = report.get("body")
    entrainment_state = report.get("body_state")
    entrainment_note = report.get("entrainment_note")
    if entrainment is not None and not compact:
        line = f"{display_name('body')}: {float(entrainment):.3f}"
        if entrainment_state:
            line += f" ({entrainment_state})"
        if entrainment_note:
            line += f" — {entrainment_note}"
        lines.append(line)
    weight = report.get("weight")
    weight_state = report.get("weight_state")
    if weight is not None and not compact:
        line = f"{display_name('weight')}: {float(weight):.3f}"
        if weight_state:
            line += f" ({weight_state})"
        lines.append(line)
        lines.append(
            "Weight states: light = little hold; "
            "present = some hold; suspended = held, slowed, dragged, or swaying; "
            "heavy = strong sustained pressure or drag. Suspended is not automatically heavy."
        )
    metric_tension = report.get("metric_tension")
    metric_tension_state = report.get("metric_tension_state")
    metric_tension_note = report.get("metric_tension_note")
    if metric_tension is not None and not compact:
        line = f"{display_name('metric_tension')}: {float(metric_tension):.3f}"
        if metric_tension_state:
            line += f" ({metric_tension_state})"
        if metric_tension_note:
            line += f" — {metric_tension_note}"
        lines.append(line)

    # Perception summary — handles both new schema (mean_pattern) and
    # old schema (mean_surprise = disruption, pattern = 1 - surprise)
    summary = perception.get("summary", {})
    if summary and not compact:
        attention = summary.get("mean_attention", 0)
        pattern = summary.get("mean_pattern", 0)
        pressure_building = summary.get("pressure_building_pct", 0)
        pressure_releasing = summary.get("pressure_releasing_pct", 0)
        pressure_sustaining = summary.get("pressure_sustaining_pct", 0)

        lines.append(f"\n{display_name('attention')}: {attention:.3f} (listener engagement, 0–1)")
        lines.append(f"{display_name('pattern')}: {pattern:.3f} (predictability/hold, 0–1)")
        lines.append(f"{display_name('pulse')}: {pulse:.3f} (metronomic regularity)")
        lines.append(
            f"{display_name('pressure')}: {pressure_building:.1f}% pressure building / "
            f"{pressure_releasing:.1f}% releasing / {pressure_sustaining:.1f}% sustaining"
        )
        if summary.get("integrated_lufs") is not None:
            silence_pct = summary.get("loudness_silence_pct", 0)
            lines.append(
                f"Heard pressure: {silence_pct:.1f}% silence-aware floor; "
                "describe movement as pressure, build, release, or sustain "
                "rather than meter readings"
            )
        local_metric_fields = (
            "groove_comfort",
            "accent_phase_drift",
            "expectation_debt",
            "release_force",
            "section_gravity",
            "body_capture",
            "body_comfort",
            "surface_density",
        )
        local_bits = []
        for field in local_metric_fields:
            mean_value = summary.get(f"mean_{field}")
            peak_value = summary.get(f"peak_{field}")
            if mean_value is not None and peak_value is not None:
                local_bits.append(f"{display_name(field)} mean {float(mean_value):.3f}, peak {float(peak_value):.3f}")
        if local_bits:
            lines.append("Local stream metrics: " + "; ".join(local_bits))
        shapes = summary.get("silence_reentry_shapes") or {}
        boundaries = summary.get("silence_boundary_positions") or {}
        reentry_count = summary.get("silence_reentry_count", 0)
        ordinary_closing_only = (
            reentry_count > 0
            and boundaries.get("closing", 0) == reentry_count
            and shapes.get("terminal_decay", 0) == reentry_count
        )
        if reentry_count and not ordinary_closing_only:
            shape_bits = [f"{shape}:{count}" for shape, count in shapes.items() if count]
            boundary_bits = [f"{pos}:{count}" for pos, count in boundaries.items() if count]
            shape_text = ", ".join(shape_bits) if shape_bits else "none classified"
            boundary_text = f"; boundary {', '.join(boundary_bits)}" if boundary_bits else ""
            lines.append(
                f"Silence returns: {reentry_count} silence outcomes "
                f"({shape_text}{boundary_text}); describe internal returns as "
                "continuation, rupture, reset, or withdrawal, and boundary "
                "silence as entry preparation only when it changes how the music begins"
            )

    salience = synthesize_salience(analysis)
    primary_contract = salience.get("primary_contract", salience.get("listening_contract", "balanced_listener_state"))
    has_salience_context = any(
        salience.get(key)
        for key in (
            "headline_forces",
            "supporting_forces",
            "force_axes",
            "prose_hints",
            "secondary_contracts",
            "technical_underlayer",
            "low_confidence_metrics",
            "conflict_notes",
        )
    )
    if has_salience_context and not compact:
        lines.append("\nPerceptual salience guide (advisory, not a filter):")
        lines.append(f"Primary contract: {primary_contract}")
        secondary_contracts = salience.get("secondary_contracts") or []
        if secondary_contracts:
            lines.append("Secondary contracts: " + ", ".join(secondary_contracts))
        axes = salience.get("force_axes") or {}
        if axes:
            axis_bits = [
                f"{axis}={item.get('value', 'unknown')} ({item.get('confidence', 'medium')}: {item.get('evidence', '')})"
                for axis, item in axes.items()
            ]
            lines.append("Force axes: " + "; ".join(axis_bits))
        prose_hints = salience.get("prose_hints") or []
        if prose_hints:
            lines.append("Prose hints: " + ", ".join(prose_hints))
        for label, key in (
            ("Headline forces", "headline_forces"),
            ("Supporting forces", "supporting_forces"),
            ("Technical underlayer", "technical_underlayer"),
            ("Low-confidence metrics", "low_confidence_metrics"),
        ):
            items = salience.get(key) or []
            if items:
                bits = [
                    f"{item['name']} ({item.get('confidence', 'medium')}: {item.get('evidence', '')})"
                    for item in items
                ]
                lines.append(f"{label}: " + "; ".join(bits))
        notes = salience.get("conflict_notes") or []
        if notes:
            lines.append("Conflict notes: " + " ".join(notes))
        lines.append(
            "Use this guide to choose narrative emphasis, but keep the raw metrics available; "
            "do not hide technically true secondary evidence or collapse the axes into compound labels."
        )

    boundary_candidates = _build_boundary_candidates(perception.get("stream", []))
    if boundary_candidates:
        lines.append("\n" + boundary_candidates)

    arc_structure = _build_arc_structure(perception.get("stream", []))
    if arc_structure and not compact:
        lines.append("\n" + arc_structure)

    # Surface balance derived from report harmonic/percussive weight ratio
    if har_e or perc_e:
        total = har_e + perc_e
        if total > 0:
            surface_balance = (perc_e - har_e) / total  # negative = harmonic dominant
            surface_balance_label = "harmonic dominant (tonal, warm)" if surface_balance < -0.2 else "percussive dominant" if surface_balance > 0.2 else "balanced"
            lines.append(f"{display_name('surface_balance')}: {surface_balance:.3f} ({surface_balance_label})")

    # Harmony surface: keep listener-state tension foregrounded.  Key/mode,
    # major/minor balance, and chord names remain internal evidence unless a
    # later task adds confidence-gated prose.
    if harmony:
        tension = harmony.get("mean_harmonic_pull")
        tonal_anchor = harmony.get("mean_tonal_anchor")
        chroma_motion = harmony.get("mean_chroma_motion")

        if tension is not None:
            lines.append(f"\n{display_name('harmonic_pull')}: {tension:.3f} (tension/motion, 0–1)")
        if tonal_anchor is not None:
            lines.append(f"{display_name('tonal_anchor')}: {tonal_anchor:.3f}")
        if chroma_motion is not None:
            lines.append(f"{display_name('chroma_motion')}: {chroma_motion:.3f}")

    # Melody surface: mean_foreground_line is a pitch-extraction confidence
    # signal, not proof of voice.  Do not present vocal/contour authority here.
    if melody:
        foreground_pitch = melody.get("mean_foreground_line")
        if foreground_pitch is not None:
            lines.append(
                f"\n{display_name('foreground_line')}: {foreground_pitch:.3f} "
                "(pitch-tracking support; not a vocal claim)"
            )

    if not compact:
        lines.append("\n### Metric glossary\n")
        lines.append(
            "Use the `Use as` phrases as translation cues, not canned wording. "
            "Prefer audible description over metric names, and check each caveat before making a strong prose claim."
        )
        lines.extend(glossary_lines())
        lines.append("\n### How to read galdr\n")
        lines.append(
            "Galdr traces listener-state pressure: pulse availability, bodily coupling, "
            "pattern stability, harmonic warmth, local phrase motion, rupture, and release. "
            "Treat these as evidence of felt experience, not detector facts to recite."
        )
        lines.append(
            "Macro events change the listening landscape: attention, motor entrainment, weight, "
            "surface change, pressure movement, pattern break, and silence. Phrase events "
            "are local motion inside that landscape and usually become surface balance within a paragraph."
        )
        lines.append(
            "Metric families: pattern / pulse = reliability and carried time; "
            "body = whether the pulse has the body or merely offers itself; "
            "metric tension = cross-rhythm/accent pressure against a stable pulse; "
            "weight / weight arc = hold, suspension, or macro weight; "
            "pressure = heard pressure movement; surface_balance = harmonic warmth vs percussive edge; "
            "harmonic pull / chroma motion = tonal restlessness, drift, or pitch-color movement; "
            "phrase dynamics = local lift, drop, or flash, usually not structure."
        )

    # Unified timeline: stream-local narrative anchors and structural events share
    # one chronological surface so prose models do not reconcile separate clocks.
    timeline = []
    for f in perception.get("stream", []):
        event = f.get("event")
        if not event or event == "pattern_breaks":
            continue
        t = float(f.get("t", 0))
        note = f.get("event_note")
        suffix = f" — {note}" if note else ""
        timeline.append((t, _event_rank(event), f"{_fmt_time(t)} — {event}{suffix}"))

    # Structural events — handles both schemas:
    # New: pattern_breaks (unified list with type="silence"|"break")
    # Old: separate silences list + moments list
    raw_breaks = perception.get("pattern_breaks", [])
    raw_silences = perception.get("silences", [])
    raw_moments = perception.get("moments", [])

    # Prefer new unified schema; fall back to old separate lists
    if raw_breaks:
        event_source = raw_breaks
    elif raw_moments:
        event_source = raw_moments
    else:
        event_source = [{"start": s["start"], "type": "silence", "duration": s["duration"],
                         "depth_db": s["depth_db"]} for s in raw_silences]

    for span in perception.get("sustained_state_spans", []):
        start = float(span.get("start", 0.0))
        end = float(span.get("end", start))
        desc = span.get("description") or span.get("type", "sustained state")
        detail_bits = []
        if span.get("peak_expectation_debt") is not None:
            detail_bits.append(f"debt peak {float(span['peak_expectation_debt']):.3f}")
        if span.get("peak_accent_phase_drift") is not None:
            detail_bits.append(f"drift peak {float(span['peak_accent_phase_drift']):.3f}")
        if span.get("mean_body_capture") is not None and span.get("mean_body_comfort") is not None:
            detail_bits.append(
                f"body capture {float(span['mean_body_capture']):.3f} / comfort {float(span['mean_body_comfort']):.3f}"
            )
        details = f" ({', '.join(detail_bits)})" if detail_bits else ""
        timeline.append((
            start,
            _event_rank("sustained_state_span"),
            f"{_fmt_time(start)}–{_fmt_time(end)} — {desc}{details}",
        ))

    ordinary_closing_only = False
    if perception.get("summary"):
        summary = perception.get("summary") or {}
        shapes = summary.get("silence_reentry_shapes") or {}
        boundaries = summary.get("silence_boundary_positions") or {}
        reentry_count = summary.get("silence_reentry_count", 0)
        ordinary_closing_only = (
            reentry_count > 0
            and boundaries.get("closing", 0) == reentry_count
            and shapes.get("terminal_decay", 0) == reentry_count
        )

    for b in event_source:
        # New schema uses "time"; old uses "start" or "time"
        t = float(b.get("time", b.get("start", 0)))
        btype = b.get("type", "")
        intensity = b.get("intensity", 0)

        if btype == "silence":
            dur = b.get("duration", 0)
            db = b.get("depth_db", -80)
            shape = b.get("reentry_shape")
            boundary = b.get("boundary_position")
            if ordinary_closing_only and (boundary == "closing" or shape == "terminal_decay"):
                continue
            force = b.get("reentry_force")
            recovery = b.get("recovery_time_sec")
            if shape:
                force_text = f", re-entry force {force:.3f}" if isinstance(force, (int, float)) else ""
                if isinstance(recovery, (int, float)):
                    recovery_text = f", recovery {recovery:.2f}s"
                elif boundary == "closing" or shape == "terminal_decay":
                    recovery_text = ", no recovery before ending"
                elif boundary == "opening" or shape == "entry_preparation":
                    recovery_text = ", entry follows"
                else:
                    recovery_text = ", no recovery before next withdrawal"
                boundary_text = f", {boundary}" if boundary in {"opening", "closing"} else ""
                text = (
                    f"{_fmt_time(t)} — silence {dur:.2f}s at {db:.1f}dB; "
                    f"return: {shape}{boundary_text}{force_text}{recovery_text}"
                )
            else:
                text = f"{_fmt_time(t)} — silence {dur:.2f}s at {db:.1f}dB"
            timeline.append((t, _event_rank("", btype), text))
        else:
            components = b.get("components", {})
            comp_str = ""
            if components and isinstance(components, dict):
                parts = [f"{k}:{v:.2f}" for k, v in components.items() if isinstance(v, (int, float))]
                if parts:
                    comp_str = f" [{', '.join(parts)}]"
            timeline.append((
                t,
                _event_rank("", btype or "break"),
                f"{_fmt_time(t)} — pattern break (intensity {intensity:.3f}{comp_str})",
            ))

    if timeline:
        lines.append("\n### Event timeline\n")
        timeline.sort(key=lambda x: (x[0], x[1]))
        lines.extend(e[2] for e in timeline)

    return "\n".join(lines)


def _build_lyrics(context: dict) -> str | None:
    """Build lyrics section(s) from context.json.

    When multiple lyric evidence sources are available, renders separate
    sections for provider-timed lyric lines, autocaptions, and clean Genius text.

    Provider-timed lines carry line-level timing evidence. Autocaptions remain
    coarse orientation only; Genius is clean text without timing.

    Falls back to a single section if only one source is available.
    """
    lyrics = context.get("lyrics")
    if not lyrics:
        return None
    if isinstance(lyrics, str):
        # Legacy plain-string format
        return f"## Lyrics\n\n{lyrics.strip()}" if lyrics.strip() else None

    source_label = _lyrics_source_label(lyrics)
    source_line = f"Source: {source_label}" if source_label else None
    lyrics_usable = lyrics.get("use_in_prompt", True)
    genius_text = (lyrics.get("genius_text") or "") if lyrics_usable else ""
    timed_lines = lyrics.get("timed_lines") or []
    caption_lines = lyrics.get("caption_lines") or []
    timing_verdict = _lyrics_timing_verdict(lyrics)

    sections: list[str] = []

    if timed_lines:
        timed_section = [
            f"## Lyrics — {timing_verdict['heading']} ({timing_verdict['confidence_note']})\n"
        ]
        if source_line:
            timed_section.append(source_line)
        for entry in timed_lines:
            ts = entry.get("ts", "?")
            text = entry.get("text", "")
            timed_section.append(f"[{ts}]  {text}")
        sections.append("\n".join(timed_section))

    if caption_lines:
        cap_section = [f"## Lyrics — {timing_verdict['heading']} ({timing_verdict['confidence_note']})\n"]
        if source_line:
            cap_section.append(source_line)
        for entry in caption_lines:
            ts = entry.get("ts", "?")
            text = entry.get("text", "")
            cap_section.append(f"[{ts}]  {text}")
        sections.append("\n".join(cap_section))

    if genius_text.strip():
        genius_section = ["## Lyrics — Genius (clean text, no timestamps)\n"]
        if source_line:
            genius_section.append(source_line)
        genius_section.append(genius_text.strip())
        sections.append("\n".join(genius_section))

    if not sections:
        # Fall back to full_text for old context.json files
        text = lyrics.get("full_text", "") if lyrics_usable else ""
        if text and text.strip():
            prefix = f"{source_line}\n" if source_line else ""
            return f"## Lyrics\n\n{prefix}{text.strip()}"
        return None

    return "\n\n".join(sections)


def _build_frames(context: dict) -> str | None:
    """Build video frame descriptions section if present.

    Expects frame_descriptions as a list of dicts with keys:
      time, event_type, event (label), window (list of timestamps), description
    """
    frames = context.get("frame_descriptions")
    if not frames:
        return None

    lines = ["## Visual context (video frames at structural moments)\n"]
    lines.append(
        "These descriptions come from 3 sequential frames extracted around each"
        " structural event. This is optional context — the music stands alone."
    )
    lines.append("")

    for f in frames:
        t = f.get("time", 0)
        kind = f.get("kind", "anchor")
        desc = f.get("description", "")

        # Build event label from kind + event metadata
        if kind == "coverage":
            label = f"[{_fmt_time(t)}] (coverage)"
        else:
            ev = f.get("event") or {}
            if isinstance(ev, dict):
                etype = ev.get("type", "")
                intensity = ev.get("intensity")
                if intensity is not None:
                    label = f"[{_fmt_time(t)}] ({etype}, intensity {intensity:.2f})"
                elif etype:
                    label = f"[{_fmt_time(t)}] ({etype})"
                else:
                    label = f"[{_fmt_time(t)}] ({f.get('event', '')})"
            else:
                # event is a string label (legacy frame_descriptions format)
                event_label = ev if isinstance(ev, str) else f.get("event", "")
                label = f"[{_fmt_time(t)}] ({event_label})" if event_label else f"[{_fmt_time(t)}]"

        lines.append(label)
        lines.append(f"  {desc}")
        lines.append("")

    return "\n".join(lines)


def _voice_intensity(event: dict) -> str | None:
    voice = event.get("voice")
    if isinstance(voice, dict):
        intensity = voice.get("intensity")
        return str(intensity) if intensity is not None else None
    if isinstance(voice, str) and voice.strip():
        return voice.strip()
    return None


def _compact_hearing_events(events: list[dict], *, max_events: int = 24) -> list[dict]:
    """Select a star subset from a dense hearing stream for Arc writing.

    Keep open/close anchors and non-hold changes. Fill remaining budget with
    evenly spaced continuity samples so the writer sees shape without a transcript.
    """
    if len(events) <= max_events:
        return list(events)

    ranked: list[tuple[int, int]] = []
    prev_voice = None
    for index, event in enumerate(events):
        change = str(event.get("change") or "").strip().lower()
        voice = _voice_intensity(event)
        score = 0
        if index == 0 or index == len(events) - 1:
            score += 100
        if change and change not in {"hold", "none"}:
            score += 40
        if voice and voice != prev_voice:
            score += 25
        if event.get("unsure"):
            score += 5
        ranked.append((score, index))
        prev_voice = voice or prev_voice

    # Always keep anchors.
    chosen: set[int] = {0, len(events) - 1}

    # Take strongest non-anchor events first.
    for score, index in sorted(ranked, key=lambda row: (-row[0], row[1])):
        if index in chosen:
            continue
        if score < 25 and len(chosen) >= max(8, max_events // 2):
            continue
        chosen.add(index)
        if len(chosen) >= max_events:
            break

    # Fill gaps with evenly spaced continuity if still under budget.
    if len(chosen) < max_events:
        step = max(1, len(events) // max_events)
        for index in range(0, len(events), step):
            chosen.add(index)
            if len(chosen) >= max_events:
                break

    return [events[i] for i in sorted(chosen)[:max_events]]


def _format_hearing_event_line(event: dict) -> str:
    t = float(event.get("t", 0.0))
    now = str(event.get("now") or event.get("foreground") or "").strip()
    voice = _voice_intensity(event) or "n/a"
    density = event.get("density") or "n/a"
    body = event.get("body")
    change = event.get("change") or ""
    parts = [f"t={t:.1f}s", f"voice={voice}", f"density={density}"]
    if body:
        parts.append(f"body={body}")
    if change:
        parts.append(f"change={change}")
    return f"- {' | '.join(parts)} — {now}"


def _build_hearing_stream_section(packet: dict) -> str:
    events = packet.get("events") or []
    selected = _compact_hearing_events(events)
    lines = [
        "## Optional hearing stream",
        "",
        "This is model-produced sensory evidence, not Galdr measurement.",
        "It is a dense chronological hearing log. Do not publish it and do not paraphrase its grid into prose.",
        "",
        "Simultaneous-evidence reminder:",
        "At any moment, words, music, and sound-as-heard are happening together.",
        "These layers split that unity so you can inspect parts. Your job is to reunite the moment the current lens needs.",
        "",
        "Evidence roles:",
        "- Prefer source-bound Galdr measurement for candidate timing, structure, pressure, returns, and silence; confirm release-critical boundaries against the exact recording or a reviewed map.",
        "- Prefer this stream for surface, voice body, local intensity, and support density color.",
        "- Prefer lyrics/context only when the lens earns them.",
        "- Star a few decisive simultaneous moments. Write the lens contract, not a transcript.",
        "- Tone: alive grounded companion. Keep human temperature and care. No first-listen rapture, new-age haze, or mystic-guide voice. Do not flatten into dead inventory prose.",
        "- Named Galdr language such as pulse, pocket, body lock, motor capture, pressure, or suspended weight is allowed when true and useful. A raw label or score is evidence rather than proof; keep the audible cause nearby and avoid repetition that replaces listening.",
        "- Vary attention across the page: voice, support or pulse, then a different musical feature. Let this track set the page's temperature.",
        "- Lyrics: quote only when actively referring to the words. Prefer a short hinge line; do not stack stanzas or use quotes as atmosphere.",
        "- Ending options: meaningful residue, a quick surprising cutoff, the last audible fact, or no closer. Do not default to a 'what it leaves' paragraph.",
        "",
        f"Stream provenance: model={packet.get('model') or 'unknown'}; "
        f"prompt_version={packet.get('prompt_version') or 'unknown'}; "
        f"overlay={packet.get('overlay') or 'none'}; "
        f"events={len(events)}; shown={len(selected)}.",
        "",
        "Selected hearing moments:",
    ]
    lines.extend(_format_hearing_event_line(event) for event in selected)
    if len(events) > len(selected):
        lines.append("")
        lines.append(
            f"({len(events) - len(selected)} additional hold/continuity events omitted from the prompt.)"
        )
    return "\n".join(lines)


def _build_inner_ear_packet_section(packet: dict) -> str:
    return "\n".join([
        "## Optional witness packet",
        "",
        "This is model-produced evidence, not Galdr measurement. Treat its timed claims as "
        "candidates unless Galdr supports them. It may add timbre, space, grain, vocal body, "
        "and other directly heard surface detail; it must not silently override Galdr timing "
        "or structure.",
        "",
        "Simultaneous-evidence reminder: words, music, and sound-as-heard are happening together. "
        "Use this packet as one partial view, then write the reunited moment the lens needs.",
        "",
        "```json",
        json.dumps(packet, indent=2, ensure_ascii=False),
        "```",
    ])


def _build_witness_packet(packet: dict) -> str:
    """Render optional model-produced witness evidence as bounded prompt material."""
    kind = witness_kind(packet)
    if kind == "hearing_stream" or packet.get("schema") == HEARING_STREAM_SCHEMA:
        return _build_hearing_stream_section(packet)
    if kind == "inner_ear_packet" or packet.get("schema") == INNER_EAR_PACKET_SCHEMA:
        return _build_inner_ear_packet_section(packet)
    # validate_witness_packet should prevent this path; keep a safe fallback.
    return _build_inner_ear_packet_section(packet)


# ─── Core assembly ────────────────────────────────────────────────────────────

def assemble_prompt(
    analysis: dict,
    context: dict | None = None,
    mode: str = DEFAULT_MODE,
    template: str = DEFAULT_TEMPLATE,
    docs_dir: Path | None = None,
    lens: str | None = None,
    witness_packet: dict | None = None,
) -> str:
    """Assemble a model prompt from analysis data and optional context.

    Python API entry point — takes data dicts directly.

    Args:
        analysis: dict from load_analysis() — keys: report, perception, harmony, melody
        context:  dict from load_context() or fetch pipeline — keys: artist_context,
                  song_context, lyrics, frame_descriptions. None = empty context.
        mode:     "full" | "lyrics" | "context" | "blind" (default: "full")
        template: "none" | "arc" | "first" | "arc-family" | file path (default: "none")
        docs_dir: optional path to docs/ directory for local template overrides
        lens:     optional prompt-family lens: default, sound, sound-sync, dance, structure, meaning, lyrics-study, classical, ritual
        witness_packet: optional model-produced listening evidence; Galdr remains the
                        timing and structure authority

    Returns:
        Complete prompt string ready to send to a model.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Choose from: {', '.join(MODES)}")
    if witness_packet is not None:
        witness_packet = validate_witness_packet(witness_packet)

    flags = MODES[mode]
    ctx = context or {}

    sections = []

    # Template instructions
    if template != "none" or lens:
        tmpl = resolve_template(template, docs_dir, lens=lens)
        if tmpl:
            sections.append(tmpl.strip())
            sections.append("\n---\n")

    # Background
    if flags["background"]:
        bg = _build_background(ctx)
        if bg:
            sections.append(bg)

    # Track header — artist, title, source URL (withheld in blind mode)
    if mode != "blind":
        header = _build_track_header(ctx)
        if header:
            sections.append(header)

    # Galdr metrics (always included)
    sections.append(_build_metrics(analysis, compact=lens == "classical"))

    # Lyrics
    if flags["lyrics"]:
        lyr = _build_lyrics(ctx)
        if lyr:
            sections.append(lyr)

    # Frame descriptions
    if flags["frames"]:
        frames = _build_frames(ctx)
        if frames:
            sections.append(frames)

    if witness_packet:
        sections.append(_build_witness_packet(witness_packet))

    return "\n\n".join(sections)


def assemble_prompt_from_disk(
    slug: str,
    analysis_dir: Path,
    mode: str = DEFAULT_MODE,
    template: str = DEFAULT_TEMPLATE,
    docs_dir: Path | None = None,
    lens: str | None = None,
    witness_packet: dict | None = None,
) -> str:
    """Assemble a prompt by loading data from disk for a given slug.

    CLI path — loads analysis and context from analysis_dir/slug/.

    Args:
        slug:         track slug (e.g. "7-helvegen", "tool-lateralus")
        analysis_dir: path to the analysis/ directory
        mode:         "full" | "lyrics" | "context" | "blind" (default: "full")
        template:     "none" | "arc" | "first" | "arc-family" | file path (default: "none")
        docs_dir:     optional path to docs/ for local template overrides
        lens:         optional prompt-family lens: default, sound, sound-sync, dance, structure, meaning, lyrics-study, classical, ritual

    Returns:
        Complete prompt string ready to send to a model.
    """
    analysis = load_analysis(slug, analysis_dir)
    context = load_context(slug, analysis_dir)
    if mode in {"full", "lyrics"}:
        context = _augment_context_with_caption_file(slug, analysis_dir, context)
    if not any(analysis.values()) and not context:
        raise ValueError(
            f"No analysis or context found for slug '{slug}' in {analysis_dir / slug}"
        )
    return assemble_prompt(
        analysis,
        context,
        mode=mode,
        template=template,
        docs_dir=docs_dir,
        lens=lens,
        witness_packet=witness_packet,
    )

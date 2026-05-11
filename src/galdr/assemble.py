"""galdr assemble — build a model prompt from context + analysis data.

Two entry points:
  assemble_prompt(analysis, context, ...)  — takes data dicts directly (Python API)
  assemble_prompt_from_disk(slug, ...)     — loads from analysis dir (CLI path)

Output structure (controlled by mode):
  [Template instructions]  <- prepended when --template is not "none"
  [Background]             <- artist/song Wikipedia context  (full, context)
  [Galdr analysis]         <- metrics, events, melody        (all modes)
  [Lyrics]                 <- timestamped caption segments   (full, lyrics)
  [Frame descriptions]     <- vision descriptions at events  (full, if present)

Modes:
  full     — everything available. Best default output. (DEFAULT)
  lyrics   — galdr + lyrics. Words, no story.
  context  — galdr + background. Story, no words.
  blind    — galdr data only. No prior knowledge. Purest experience.

Templates:
  none     — data block only, user adds their own instructions. (DEFAULT)
  arc      — prepends ARC-PROMPT.md (listening experience: body, attention, time)
  first    — alias for arc
  <path>   — any file path, read directly

Default mode is full (graceful degradation — missing sections silently omitted).
Default template is none.
"""

import json
from pathlib import Path
from importlib import resources as pkg_resources

from .metric_vocabulary import display_name, glossary_lines


# ─── Mode definitions ─────────────────────────────────────────────────────────

MODES = {
    "full":    {"background": True,  "metrics": True, "lyrics": True,  "frames": True},
    "lyrics":  {"background": False, "metrics": True, "lyrics": True,  "frames": False},
    "context": {"background": True,  "metrics": True, "lyrics": False, "frames": False},
    "blind":   {"background": False, "metrics": True, "lyrics": False, "frames": False},
}

DEFAULT_MODE = "full"
DEFAULT_TEMPLATE = "none"

BUNDLED_TEMPLATES = {"arc": "ARC-PROMPT.md", "first": "ARC-PROMPT.md"}  # "first" aliased to "arc"


# ─── Template resolution ──────────────────────────────────────────────────────

def resolve_template(name: str, docs_dir: Path | None = None) -> str | None:
    """Resolve a template name or path to its text content.

    Resolution order:
      1. "none"            -> returns None (no template)
      2. File path         -> used directly (absolute or relative)
      3. docs_dir/{name}.md -> user's local override (e.g. custom-template.md)
      4. Bundled package templates via importlib.resources (arc, first)

    Bundled templates live in galdr/templates/ and are shipped with the package,
    so they work after pip install without needing the source repo present.
    """
    if name == "none":
        return None

    # Explicit file path
    p = Path(name)
    if p.exists():
        return p.read_text()

    # Local docs override (dev workflow — docs/ takes precedence over bundled)
    if docs_dir:
        local = docs_dir / f"{name}.md"
        if local.exists():
            return local.read_text()

    # Bundled package templates (works after pip install)
    if name in BUNDLED_TEMPLATES:
        filename = BUNDLED_TEMPLATES[name]
        try:
            ref = pkg_resources.files("galdr.templates") / filename
            return ref.read_text(encoding="utf-8")
        except Exception:
            # Fallback for editable installs: templates/ sibling to this file
            local_path = Path(__file__).parent / "templates" / filename
            if local_path.exists():
                return local_path.read_text()

    raise ValueError(
        f"Template '{name}' not found. "
        f"Use 'none', 'arc', 'first', or a file path. "
        f"Known templates: {', '.join(BUNDLED_TEMPLATES)}"
    )


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
        analysis["perception"]["stream"] = stream

    return analysis


def load_context(slug: str, analysis_dir: Path) -> dict:
    """Load context.json for a slug. Returns empty dict if not found."""
    path = analysis_dir / slug / "context.json"
    return _load_json(path) or {}


# ─── Section builders ─────────────────────────────────────────────────────────

def _extract_text(ctx_value) -> str:
    """Extract text from a context field — handles both str and dict (fetch pipeline)."""
    if not ctx_value:
        return ""
    if isinstance(ctx_value, dict):
        # fetch pipeline stores {found, title, url, extract}
        if ctx_value.get("found"):
            return ctx_value.get("extract", "")
        return ""
    return str(ctx_value)


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
    """Build background section from Wikipedia context."""
    artist_text = _extract_text(context.get("artist_context"))
    song_text = _extract_text(context.get("song_context"))

    bg_parts = []
    if artist_text:
        bg_parts.append(f"Artist: {artist_text}")
    if song_text:
        bg_parts.append(f"Track: {song_text}")

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


def _fmt_tempo(report: dict) -> str:
    """Format tempo without presenting suspect alternate pulses as plain truth."""
    detected = report.get("detected_pulse_bpm", 0)
    felt = report.get("felt_pulse_bpm")
    confidence = report.get("pulse_confidence")
    ambiguous = bool(report.get("pulse_ambiguous"))
    note = report.get("pulse_note")

    if felt is None:
        return f"Pulse: detected ~{float(detected):.1f} BPM"

    if ambiguous or abs(float(felt) - float(detected)) >= 1.0:
        line = f"Pulse: felt ~{float(felt):.1f} BPM"
        if detected:
            line += f" (detected pulse {float(detected):.1f} BPM; ambiguous/suspect)"
    else:
        line = f"Pulse: {float(felt):.1f} BPM"

    if confidence is not None:
        line += f"; confidence {float(confidence):.2f}"
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
    if event in {"body_lock_arrives", "body_lock_recedes"}:
        return 20
    if event in {"weight_arrives", "weight_lifts", "surface_hardens"}:
        return 30
    if event in {"pressure_builds", "pressure_releases"}:
        return 40
    if event in {"phrase_lifts", "phrase_drops", "ornamental_flash"}:
        return 50
    return 70

def _build_metrics(analysis: dict) -> str:
    """Build core galdr metrics section."""
    report = analysis.get("report") or {}
    perception = analysis.get("perception") or {}
    harmony = analysis.get("harmony") or {}
    melody = analysis.get("melody") or {}
    overtone = analysis.get("overtone") or {}

    if not any([report, perception, harmony, melody, overtone]):
        return "## Galdr Analysis\n\nNo structural analysis files found for this track."

    lines = ["## Galdr Analysis\n"]

    # Track identity — field names from report.json
    duration = report.get("duration_seconds", 0)
    pulse = report.get("pulse", 0)
    har_e = report.get("harmonic_weight", 0)
    perc_e = report.get("percussive_weight", 0)

    lines.append(f"Duration: {_fmt_time(duration)} ({duration:.1f}s)")
    lines.append(_fmt_tempo(report))
    entrainment = report.get("body")
    entrainment_state = report.get("body_state")
    entrainment_note = report.get("entrainment_note")
    if entrainment is not None:
        line = f"{display_name('body')}: {float(entrainment):.3f}"
        if entrainment_state:
            line += f" ({entrainment_state})"
        if entrainment_note:
            line += f" — {entrainment_note}"
        lines.append(line)
    weight = report.get("weight")
    weight_state = report.get("weight_state")
    if weight is not None:
        line = f"{display_name('weight')}: {float(weight):.3f}"
        if weight_state:
            line += f" ({weight_state})"
        lines.append(line)
        lines.append(
            "Weight states: light = little hold; "
            "present = some hold; suspended = held, slowed, dragged, or swaying; "
            "heavy = strong sustained pressure or drag. Suspended is not automatically heavy."
        )

    # Perception summary — handles both new schema (mean_pattern) and
    # old schema (mean_surprise = disruption, pattern = 1 - surprise)
    summary = perception.get("summary", {})
    if summary:
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
        shapes = summary.get("silence_reentry_shapes") or {}
        boundaries = summary.get("silence_boundary_positions") or {}
        reentry_count = summary.get("silence_reentry_count", 0)
        if reentry_count:
            shape_bits = [f"{shape}:{count}" for shape, count in shapes.items() if count]
            boundary_bits = [f"{pos}:{count}" for pos, count in boundaries.items() if count]
            shape_text = ", ".join(shape_bits) if shape_bits else "none classified"
            boundary_text = f"; boundary {', '.join(boundary_bits)}" if boundary_bits else ""
            lines.append(
                f"Silence returns: {reentry_count} silence outcomes "
                f"({shape_text}{boundary_text}); describe internal returns as "
                "continuation, rupture, reset, or withdrawal, and boundary "
                "silence as entry preparation or terminal decay"
            )

    # Texture balance derived from report harmonic/percussive weight ratio
    if har_e or perc_e:
        total = har_e + perc_e
        if total > 0:
            texture = (perc_e - har_e) / total  # negative = harmonic dominant
            texture_label = "harmonic dominant (tonal, warm)" if texture < -0.2 else "percussive dominant" if texture > 0.2 else "balanced"
            lines.append(f"{display_name('texture')}: {texture:.3f} ({texture_label})")

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

    lines.append("\n### Metric glossary\n")
    lines.extend(glossary_lines())
    lines.append("\n### How to read galdr\n")
    lines.append(
        "Galdr traces listener-state pressure: pulse availability, bodily coupling, "
        "pattern stability, harmonic warmth, local phrase motion, rupture, and release. "
        "Treat these as evidence of felt experience, not detector facts to recite."
    )
    lines.append(
        "Macro events change the listening landscape: attention, body lock, weight, "
        "surface change, pressure movement, pattern break, and silence. Phrase events "
        "are local motion inside that landscape and usually become texture within a paragraph."
    )
    lines.append(
        "Metric families: pattern / pulse = reliability and carried time; "
        "body = whether the pulse has the body or merely offers itself; "
        "weight / weight arc = hold, suspension, or macro weight; "
        "pressure = heard pressure movement; texture = harmonic warmth vs percussive edge; "
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

    When both Genius and autocaptions are available, renders two sections:
      1. Timestamped autocaption lines (accurate timing, may have ASR mishears)
      2. Clean Genius text (correct words, no timestamps)

    The model uses captions for structural anchoring (frame selection, timing
    claims) and Genius as the reference for what was actually sung.

    Falls back to a single section if only one source is available.
    """
    lyrics = context.get("lyrics")
    if not lyrics:
        return None
    if isinstance(lyrics, str):
        # Legacy plain-string format
        return f"## Lyrics\n\n{lyrics.strip()}" if lyrics.strip() else None

    genius_text = lyrics.get("genius_text") or ""
    caption_lines = lyrics.get("caption_lines") or []

    sections: list[str] = []

    if caption_lines:
        cap_section = ["## Lyrics — autocaptions (timestamps accurate; text may contain mishears)\n"]
        for entry in caption_lines:
            ts = entry.get("ts", "?")
            text = entry.get("text", "")
            cap_section.append(f"[{ts}]  {text}")
        sections.append("\n".join(cap_section))

    if genius_text.strip():
        genius_section = ["## Lyrics — Genius (clean text, no timestamps)\n"]
        genius_section.append(genius_text.strip())
        sections.append("\n".join(genius_section))

    if not sections:
        # Fall back to full_text for old context.json files
        text = lyrics.get("full_text", "")
        if text and text.strip():
            return f"## Lyrics\n\n{text.strip()}"
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


# ─── Core assembly ────────────────────────────────────────────────────────────

def assemble_prompt(
    analysis: dict,
    context: dict | None = None,
    mode: str = DEFAULT_MODE,
    template: str = DEFAULT_TEMPLATE,
    docs_dir: Path | None = None,
) -> str:
    """Assemble a model prompt from analysis data and optional context.

    Python API entry point — takes data dicts directly.

    Args:
        analysis: dict from load_analysis() — keys: report, perception, harmony, melody
        context:  dict from load_context() or fetch pipeline — keys: artist_context,
                  song_context, lyrics, frame_descriptions. None = empty context.
        mode:     "full" | "lyrics" | "context" | "blind" (default: "full")
        template: "none" | "arc" | "first" | file path (default: "none")
        docs_dir: optional path to docs/ directory for local template overrides

    Returns:
        Complete prompt string ready to send to a model.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Choose from: {', '.join(MODES)}")

    flags = MODES[mode]
    ctx = context or {}

    sections = []

    # Template instructions
    if template != "none":
        tmpl = resolve_template(template, docs_dir)
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
    sections.append(_build_metrics(analysis))

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

    return "\n\n".join(sections)


def assemble_prompt_from_disk(
    slug: str,
    analysis_dir: Path,
    mode: str = DEFAULT_MODE,
    template: str = DEFAULT_TEMPLATE,
    docs_dir: Path | None = None,
) -> str:
    """Assemble a prompt by loading data from disk for a given slug.

    CLI path — loads analysis and context from analysis_dir/slug/.

    Args:
        slug:         track slug (e.g. "7-helvegen", "tool-lateralus")
        analysis_dir: path to the analysis/ directory
        mode:         "full" | "lyrics" | "context" | "blind" (default: "full")
        template:     "none" | "arc" | "first" | file path (default: "none")
        docs_dir:     optional path to docs/ for local template overrides

    Returns:
        Complete prompt string ready to send to a model.
    """
    analysis = load_analysis(slug, analysis_dir)
    context = load_context(slug, analysis_dir)
    if not any(analysis.values()) and not context:
        raise ValueError(
            f"No analysis or context found for slug '{slug}' in {analysis_dir / slug}"
        )
    return assemble_prompt(analysis, context, mode=mode, template=template, docs_dir=docs_dir)

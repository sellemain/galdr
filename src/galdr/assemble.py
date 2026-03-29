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
    return {m: _load_json(d / f"{slug}_{m}.json") for m in modules}


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


def _build_metrics(analysis: dict) -> str:
    """Build core galdr metrics section."""
    report = analysis.get("report") or {}
    perception = analysis.get("perception") or {}
    harmony = analysis.get("harmony") or {}
    melody = analysis.get("melody") or {}

    lines = ["## Galdr Analysis\n"]

    # Track identity — field names from report.json
    duration = report.get("duration_seconds", 0)
    tempo = report.get("tempo_bpm", 0)
    beat_reg = report.get("beat_regularity", 0)
    har_e = report.get("harmonic_energy", 0)
    perc_e = report.get("percussive_energy", 0)
    character = report.get("character", "")

    lines.append(f"Duration: {_fmt_time(duration)} ({duration:.1f}s)")
    lines.append(f"Tempo: {tempo:.1f} BPM")

    # Perception summary — handles both new schema (mean_pattern_lock) and
    # old schema (mean_surprise = disruption, pattern_lock = 1 - surprise)
    summary = perception.get("summary", {})
    if summary:
        momentum = summary.get("mean_momentum", 0)
        # New schema: mean_pattern_lock directly. Old: derive from mean_surprise.
        val = summary.get("mean_pattern_lock")
        pattern_lock = val if val is not None else (1.0 - summary.get("mean_surprise", 0))
        breath_pos = summary.get("breath_positive_pct", 0)
        breath_neg = summary.get("breath_negative_pct", 0)
        breath_sus = summary.get("breath_sustain_pct", 0)

        lines.append(f"\nMomentum: {momentum:.3f} (listener engagement, 0–1)")
        lines.append(f"Pattern lock: {pattern_lock:.3f} (predictability/hold, 0–1)")
        lines.append(f"Beat regularity: {beat_reg:.3f} (metronomic pulse stability)")
        lines.append(f"Breath: {breath_pos:.1f}% building / {breath_neg:.1f}% releasing / {breath_sus:.1f}% sustaining")

    # HP balance derived from report harmonic/percussive energy ratio
    if har_e or perc_e:
        total = har_e + perc_e
        if total > 0:
            hp = (perc_e - har_e) / total  # negative = harmonic dominant
            hp_label = "harmonic dominant (tonal, warm)" if hp < -0.2 else "percussive dominant" if hp > 0.2 else "balanced"
            lines.append(f"HP balance: {hp:.3f} ({hp_label})")
        if character:
            lines.append(f"Character: {character}")

    # Harmony — field names from harmony.json
    if harmony:
        mm = harmony.get("mean_major_minor", 0)
        tension = harmony.get("mean_tension", 0)
        mm_label = "minor-leaning" if mm < -0.1 else "major-leaning" if mm > 0.1 else "neutral"

        lines.append(f"\nMajor/minor balance: {mm:.3f} ({mm_label})")
        lines.append(f"Mean tension: {tension:.3f}")

        top_chords = harmony.get("top_chords", [])
        if top_chords:
            chord_names = [c["chord"] if isinstance(c, dict) else str(c) for c in top_chords[:6]]
            lines.append(f"Top chords: {', '.join(chord_names)}")

    # Melody — flat field names from melody.json (not nested)
    if melody:
        vp = melody.get("mean_vocal_presence", 0)
        asc = melody.get("contour_ascending_pct", 0)
        desc = melody.get("contour_descending_pct", 0)
        hold = melody.get("contour_holding_pct", 0)
        mean_dir = melody.get("mean_direction", 0)
        dir_label = "predominantly falling" if mean_dir < -0.1 else "predominantly rising" if mean_dir > 0.1 else "flat"

        lines.append(f"\nVocal presence: {vp:.3f} (0=none, 1=dominant)")
        lines.append(f"Melody contour: {asc:.1f}% ascending / {desc:.1f}% descending / {hold:.1f}% holding")
        lines.append(f"Mean direction: {mean_dir:.3f} ({dir_label})")

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

    if event_source:
        lines.append("\n### Structural events\n")
        events = []
        for b in event_source:
            # New schema uses "time"; old uses "start" or "time"
            t = b.get("time", b.get("start", 0))
            btype = b.get("type", "")
            intensity = b.get("intensity", 0)

            if btype == "silence":
                dur = b.get("duration", 0)
                db = b.get("depth_db", -80)
                events.append((t, f"{_fmt_time(t)} — silence {dur:.2f}s at {db:.1f}dB"))
            else:
                components = b.get("components", {})
                comp_str = ""
                if components and isinstance(components, dict):
                    parts = [f"{k}:{v:.2f}" for k, v in components.items() if isinstance(v, (int, float))]
                    if parts:
                        comp_str = f" [{', '.join(parts)}]"
                events.append((t, f"{_fmt_time(t)} — pattern break (intensity {intensity:.3f}{comp_str})"))

        events.sort(key=lambda x: x[0])
        lines.extend(e[1] for e in events)

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
        event_label = f.get("event", "")
        window = f.get("window", [t])
        desc = f.get("description", "")

        # Format: 6:19 — 7.3s silence at -80dB  [6:19 / 6:22 / 6:26]
        window_str = " / ".join(_fmt_time(w) for w in window)
        lines.append(f"{_fmt_time(t)} — {event_label}  [{window_str}]")
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
    return assemble_prompt(analysis, context, mode=mode, template=template, docs_dir=docs_dir)

"""galdr — AI music perception framework.

Stateful listener, pattern analysis, harmonic decomposition.

Quick start (Python API):
    from galdr import analyze_track, assemble_prompt, load_context

    # Analyze audio — writes JSON to output_dir/track_name/
    result = analyze_track("helvegen.mp3", "analysis/", "7-helvegen")

    # Build prompt (default: full context, no template)
    ctx = load_context("7-helvegen", "analysis/")
    prompt = assemble_prompt(result, context=ctx)

    # Or with mode + template
    prompt = assemble_prompt(result, context=ctx, mode="blind", template="arc")

Modes:
    full     Everything available — background, lyrics, frames (default)
    lyrics   galdr + lyrics. Words, no story.
    context  galdr + background. Story, no words.
    blind    galdr data only. No prior knowledge. Purest experience.

Templates:
    none     Data block only (default)
    arc      ARC-PROMPT: analytical arc, body tracking
    first    FIRST-LISTEN: impressionistic, no chords
"""

from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("galdr")
except PackageNotFoundError:
    __version__ = "unknown"

# ─── Analysis pipeline ────────────────────────────────────────────────────────
from .analyze import analyze_track
from .perceive import generate_perception_stream, compute_momentum
from .harmony import analyze_harmony, detect_key_kk
from .melody import analyze_melody
from .overtone import analyze_overtones
from .compare import compare_tracks
from .catalog import CatalogState

# ─── Visual frame extraction ──────────────────────────────────────────────────
from .frames import extract_visual_moments, select_events

# ─── Prompt assembly (Python API) ─────────────────────────────────────────────
from .assemble import (
    assemble_prompt,           # takes analysis + context dicts directly
    assemble_prompt_from_disk, # loads from disk by slug (CLI path)
    load_analysis,             # loads all JSON for a slug -> dict
    load_context,              # loads context.json for a slug -> dict
    MODES,                     # mode definitions dict
)

__all__ = [
    # Analysis
    "analyze_track",
    "generate_perception_stream",
    "compute_momentum",
    "analyze_harmony",
    "detect_key_kk",
    "analyze_melody",
    "analyze_overtones",
    "compare_tracks",
    "CatalogState",
    # Frame extraction
    "extract_visual_moments",
    "select_events",
    # Prompt assembly
    "assemble_prompt",
    "assemble_prompt_from_disk",
    "load_analysis",
    "load_context",
    "MODES",
]

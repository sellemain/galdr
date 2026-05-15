"""galdr — deterministic ears for AI agents.

Audio in, listener-state traces out. Acoustic signal becomes structured evidence an LLM can encounter.

Quick start (Python API):
    from galdr import listen, assemble

    # Analyze audio — writes JSON to analysis/helvegen/
    analysis = listen("helvegen.mp3")

    # Build prompt (default: full context, no template)
    prompt = analysis.to_prompt()

    # Or with mode + template
    prompt = assemble(analysis, mode="blind", template="arc")

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
from .analyze import analyze_track, compute_track_features
from .perceive import generate_perception_stream, compute_attention, compute_perception
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
from .api import (
    Analysis,
    assemble,
    listen,
    load_stream_df,
    load_streams_df,
)

__all__ = [
    # High-level API
    "Analysis",
    "assemble",
    "listen",
    "load_stream_df",
    "load_streams_df",
    # Analysis
    "analyze_track",
    "compute_track_features",
    "generate_perception_stream",
    "compute_perception",
    "compute_attention",
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

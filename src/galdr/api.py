"""High-level Python API for galdr.

This module is intentionally small and boring. The CLI remains the full-featured
interface; these wrappers give Python users a clean path for notebooks, scripts,
and web apps without needing to know galdr's on-disk file layout first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .analyze import analyze_track
from .assemble import assemble_prompt, assemble_prompt_from_disk, load_analysis, load_context
from .catalog import CatalogState
from .harmony import analyze_harmony
from .melody import analyze_melody
from .overtone import analyze_overtones
from .perceive import generate_perception_stream

_DEFAULT_MODULES = ("report", "perception", "harmony", "melody", "overtone")
_STREAM_MODULES = ("perception", "harmony", "melody", "overtone")


@dataclass
class Analysis:
    """Convenience wrapper around one galdr analysis directory.

    Args:
        slug: Track slug, matching the analysis subdirectory and JSON filename prefix.
        analysis_dir: Root analysis directory. The track lives at ``analysis_dir/slug``.
        data: Optional preloaded module data. Missing modules are loaded lazily by
            ``reload()`` or by helper methods that need them.
    """

    slug: str
    analysis_dir: Path = Path("analysis")
    data: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.analysis_dir = Path(self.analysis_dir)
        if self.data is None:
            self.data = load_analysis(self.slug, self.analysis_dir)

    @classmethod
    def from_dir(cls, path: str | Path) -> "Analysis":
        """Load an analysis from ``analysis/<slug>/`` or any track directory."""
        track_dir = Path(path)
        return cls(slug=track_dir.name, analysis_dir=track_dir.parent)

    @classmethod
    def from_slug(cls, slug: str, analysis_dir: str | Path = "analysis") -> "Analysis":
        """Load an analysis by slug from an analysis root."""
        return cls(slug=slug, analysis_dir=Path(analysis_dir))

    @property
    def path(self) -> Path:
        """Directory containing this track's analysis files."""
        return self.analysis_dir / self.slug

    @property
    def report(self) -> dict[str, Any] | None:
        return (self.data or {}).get("report")

    @property
    def perception(self) -> dict[str, Any] | None:
        return (self.data or {}).get("perception")

    @property
    def harmony(self) -> dict[str, Any] | None:
        return (self.data or {}).get("harmony")

    @property
    def melody(self) -> dict[str, Any] | None:
        return (self.data or {}).get("melody")

    @property
    def overtone(self) -> dict[str, Any] | None:
        return (self.data or {}).get("overtone")

    @property
    def events(self) -> list[dict[str, Any]]:
        """Return perception events/pattern breaks when present.

        galdr has evolved its event schema over time, so this checks common keys
        rather than promising a single internal name forever.
        """
        perception = self.perception or {}
        for key in ("events", "pattern_breaks", "structural_events", "moments"):
            value = perception.get(key)
            if isinstance(value, list):
                return value
        return []

    def reload(self) -> "Analysis":
        """Reload all known analysis JSON files from disk."""
        self.data = load_analysis(self.slug, self.analysis_dir)
        return self

    def context(self) -> dict[str, Any]:
        """Load ``context.json`` for this track, returning ``{}`` when absent."""
        return load_context(self.slug, self.analysis_dir)

    def to_prompt(self, mode: str = "full", template: str = "none") -> str:
        """Assemble this analysis into a model prompt."""
        return assemble_prompt_from_disk(
            self.slug,
            self.analysis_dir,
            mode=mode,
            template=template,
        )

    def to_dataframes(self) -> dict[str, Any]:
        """Return available stream files as pandas DataFrames.

        Requires ``pandas``. Install with ``pip install 'galdr[data]'`` or
        ``pip install 'galdr[notebook]'``.
        """
        return load_streams_df(self.slug, self.analysis_dir)


def _default_slug(audio_path: str | Path) -> str:
    stem = Path(audio_path).stem.strip() or "track"
    return "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in stem).strip("-._") or "track"


def listen(
    audio_path: str | Path,
    name: str | None = None,
    analysis_dir: str | Path = "analysis",
    modules: Iterable[str] | None = None,
    catalog: bool = True,
    catalog_dir: str | Path | None = None,
) -> Analysis:
    """Analyze an audio file and return an ``Analysis`` object.

    This is the Python happy path equivalent of ``galdr listen``.

    Example:
        >>> from galdr import listen
        >>> analysis = listen("song.mp3")
        >>> prompt = analysis.to_prompt(template="arc")
    """
    slug = name or _default_slug(audio_path)
    root = Path(analysis_dir)
    output_dir = root / slug
    selected = tuple(modules or _DEFAULT_MODULES)
    invalid = set(selected) - set(_DEFAULT_MODULES)
    if invalid:
        raise ValueError(f"Unknown galdr module(s): {', '.join(sorted(invalid))}")

    results: dict[str, Any] = {}
    if "report" in selected:
        report = analyze_track(str(audio_path), str(output_dir), slug)
        results["report"] = report
        if report.get("null_signal"):
            return Analysis(slug=slug, analysis_dir=root, data=results)

    if "perception" in selected:
        results["perception"] = generate_perception_stream(str(audio_path), str(output_dir), slug)
    if "harmony" in selected:
        results["harmony"] = analyze_harmony(str(audio_path), str(output_dir), slug)
    if "melody" in selected:
        results["melody"] = analyze_melody(str(audio_path), str(output_dir), slug)
    if "overtone" in selected:
        results["overtone"] = analyze_overtones(str(audio_path), str(output_dir), slug)

    if catalog and results:
        state = CatalogState(str(root), catalog_dir=str(catalog_dir) if catalog_dir else None)
        state.load()
        state.index_track(
            slug,
            perception=results.get("perception"),
            harmony=results.get("harmony"),
            melody=results.get("melody"),
            overtone=results.get("overtone"),
            report=results.get("report"),
        )
        state.save()

    return Analysis(slug=slug, analysis_dir=root, data=results)


def assemble(
    analysis: Analysis | dict[str, Any] | str,
    context: dict[str, Any] | None = None,
    analysis_dir: str | Path = "analysis",
    mode: str = "full",
    template: str = "none",
) -> str:
    """Assemble a prompt from an ``Analysis``, raw data dict, or slug."""
    if isinstance(analysis, Analysis):
        return analysis.to_prompt(mode=mode, template=template)
    if isinstance(analysis, str):
        return assemble_prompt_from_disk(analysis, Path(analysis_dir), mode=mode, template=template)
    return assemble_prompt(analysis, context=context or {}, mode=mode, template=template)


def _require_pandas():
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pandas support is optional. Install it with: pip install 'galdr[data]' "
            "or pip install 'galdr[notebook]'"
        ) from exc
    return pd


def load_stream_df(path: str | Path):
    """Load a galdr stream JSON file as a pandas DataFrame.

    Accepts either a raw list of records or a dict containing a ``stream`` key.
    """
    import json

    pd = _require_pandas()
    payload = json.loads(Path(path).read_text())
    if isinstance(payload, dict):
        payload = payload.get("stream", [])
    return pd.DataFrame(payload)


def load_streams_df(slug: str, analysis_dir: str | Path = "analysis") -> dict[str, Any]:
    """Load all available ``*_stream.json`` files for a track as DataFrames."""
    root = Path(analysis_dir) / slug
    frames = {}
    for module in _STREAM_MODULES:
        path = root / f"{slug}_{module}_stream.json"
        if path.exists():
            frames[module] = load_stream_df(path)
    return frames

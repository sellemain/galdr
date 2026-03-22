#!/usr/bin/env python3
"""galdr CLI — unified entry point for music analysis.

Usage:
    galdr listen <audio_file> [--name NAME] [--analysis-dir DIR] [--skip MODULES] [--only MODULES] [--no-catalog] [--catalog-dir DIR]
    galdr compare <track_a> <track_b> [--analysis-dir DIR]
    galdr catalog [--catalog-dir DIR] [--analysis-dir DIR] [--rebuild] [--track NAME]
"""

import argparse
import re
import sys
import time
from pathlib import Path

_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_slug(slug: str) -> str:
    """Reject slugs that could escape the analysis directory."""
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid slug {slug!r}. Slugs may only contain letters, digits, "
            "dots, hyphens, and underscores."
        )
    return slug


def run_module(name, func, *args, **kwargs):
    """Run a module with timing and error handling."""
    print(f"\n{'='*60}")
    print(f"  MODULE: {name}")
    print(f"{'='*60}")
    start = time.time()
    try:
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"  + {name} complete ({elapsed:.1f}s)")
        return result
    except Exception as e:
        elapsed = time.time() - start
        print(f"  x {name} failed ({elapsed:.1f}s): {e}")
        import traceback
        traceback.print_exc()
        return None


def cmd_listen(args):
    """Run full analysis pipeline on an audio file."""
    from .analyze import analyze_track
    from .perceive import generate_perception_stream
    from .harmony import analyze_harmony
    from .melody import analyze_melody
    from .overtone import analyze_overtones
    from .catalog import CatalogState

    audio_path = args.audio
    if not Path(audio_path).exists():
        print(f"Error: {audio_path} not found")
        sys.exit(1)

    track_name = _validate_slug(args.name or Path(audio_path).stem)
    output_dir = str(Path(args.analysis_dir) / track_name)

    # Determine which modules to run
    all_modules = ["report", "perceive", "harmony", "melody", "overtone"]
    if args.only:
        modules = [m.strip() for m in args.only.split(",")]
    elif args.skip:
        skip = {m.strip() for m in args.skip.split(",")}
        modules = [m for m in all_modules if m not in skip]
    else:
        modules = all_modules

    print(f"\n{'#'*60}")
    print(f"  LISTENING TO: {track_name}")
    print(f"  Audio: {audio_path}")
    print(f"  Output: {output_dir}")
    print(f"  Modules: {', '.join(modules)}")
    print(f"{'#'*60}")

    total_start = time.time()
    results = {}

    if "report" in modules:
        result = run_module("Audio Analysis", analyze_track, audio_path, output_dir, track_name)
        if result:
            results["report"] = result

    if "perceive" in modules:
        result = run_module("Perception", generate_perception_stream, audio_path, output_dir, track_name)
        if result:
            report, stream = result
            results["perception"] = report

    if "harmony" in modules:
        result = run_module("Harmony", analyze_harmony, audio_path, output_dir, track_name)
        if result:
            summary, stream = result
            results["harmony"] = summary

    if "melody" in modules:
        result = run_module("Melody", analyze_melody, audio_path, output_dir, track_name)
        if result:
            summary, stream = result
            results["melody"] = summary

    if "overtone" in modules:
        result = run_module("Overtone", analyze_overtones, audio_path, output_dir, track_name)
        if result:
            summary, stream = result
            results["overtone"] = summary

    # Catalog indexing
    if not args.no_catalog and results:
        print(f"\n{'='*60}")
        print(f"  CATALOG INDEXING")
        print(f"{'='*60}")
        try:
            catalog = CatalogState(args.analysis_dir, catalog_dir=args.catalog_dir)
            catalog.load()
            catalog.index_track(
                track_name,
                perception=results.get("perception"),
                harmony=results.get("harmony"),
                melody=results.get("melody"),
                overtone=results.get("overtone"),
                report=results.get("report"),
            )
            catalog.save()

            card = catalog.summary_card(track_name)
            print(f"\n{card}")
        except Exception as e:
            print(f"  Catalog indexing failed: {e}")

    # Unified summary
    total_elapsed = time.time() - total_start
    print(f"\n{'#'*60}")
    print(f"  SUMMARY: {track_name} ({total_elapsed:.1f}s total)")
    print(f"{'#'*60}\n")

    if "report" in results:
        r = results["report"]
        print(f"  Duration: {r.get('duration_seconds', '?')}s | "
              f"Tempo: {r.get('tempo_bpm', '?')} BPM | "
              f"Beat reg: {r.get('beat_regularity', '?')} | "
              f"Character: {r.get('character', '?')}")

    if "perception" in results:
        s = results["perception"].get("summary", results["perception"])
        print(f"  Momentum: {s.get('mean_momentum', '?')} | "
              f"Pattern Lock: {s.get('mean_pattern_lock', '?')} | "
              f"Silence: {s.get('total_silence_sec', '?')}s | "
              f"Pattern Breaks: {s.get('pattern_break_count', '?')}")
        print(f"  Breath: +{s.get('breath_positive_pct', '?')}% / "
              f"-{s.get('breath_negative_pct', '?')}% / "
              f"={s.get('breath_sustain_pct', '?')}%")

    if "harmony" in results:
        h = results["harmony"]
        print(f"  Key: {h.get('detected_key', '?')} "
              f"(confidence: {h.get('key_confidence', '?')}) | "
              f"Temperament: {h.get('mean_temperament_alignment', '?')} | "
              f"Series: {h.get('mean_consonance_series', '?')}")
        print(f"  Tension: {h.get('mean_tension', '?')} | "
              f"Chroma Flux: {h.get('mean_chroma_flux', '?')} | "
              f"Major/minor: {h.get('mean_major_minor', '?')}")

    if "melody" in results:
        m = results["melody"]
        print(f"  Range: {m.get('overall_range_semitones', '?')}st "
              f"({m.get('range_low', '?')}-{m.get('range_high', '?')}) | "
              f"Center: {m.get('overall_center_note', '?')} | "
              f"Presence: {m.get('mean_vocal_presence', '?')}")

    if "overtone" in results:
        o = results["overtone"]
        print(f"  Series fit: {o.get('mean_series_fit', '?')} | "
              f"Richness: {o.get('mean_richness', '?')} | "
              f"Inharmonicity: {o.get('mean_inharmonicity', '?')} cents")

    if "layers" in results:
        layers = results["layers"]
        cp = layers.get("carrier_pct", {})
        print(f"  Layers: harmonic={cp.get('harmonic', '?')}% | "
              f"percussive={cp.get('percussive', '?')}% | "
              f"both={cp.get('both', '?')}% | "
              f"neither={cp.get('neither', '?')}%")

    print(f"\n  Analysis files: {output_dir}/")
    print(f"  Total time: {total_elapsed:.1f}s")
    print()


def cmd_compare(args):
    """Compare two tracks."""
    from .compare import compare_tracks
    compare_tracks(args.track_a, args.track_b, args.analysis_dir)


def cmd_fetch(args):
    """Download audio + context for a track."""
    from pathlib import Path
    from .fetch import fetch_track

    analysis_dir = Path(args.analysis_dir)
    audio_dir = Path(args.audio_dir)

    fetch_track(
        slug=_validate_slug(args.name),
        artist=args.artist,
        title=args.title,
        analysis_dir=analysis_dir,
        audio_dir=audio_dir,
        url=args.url,
        skip_download=args.no_download,
        skip_wikipedia=args.no_wikipedia,
        skip_lyrics=args.no_lyrics,
        wiki_artist=getattr(args, "wiki_artist", None),
        wiki_song=getattr(args, "wiki_song", None),
        censor=args.censor,
    )

    if args.analyze and not args.no_download:
        # Run galdr listen on the downloaded audio
        audio_path = audio_dir / f"{args.name}.mp3"
        if audio_path.exists():
            listen_args = type("args", (), {
                "audio": str(audio_path),
                "name": args.name,
                "analysis_dir": args.analysis_dir,
                "skip": None,
                "only": None,
                "no_catalog": False,
                "catalog_dir": None,
            })()
            cmd_listen(listen_args)
        else:
            print(f"[fetch] Audio not found at {audio_path}, skipping analysis")


def cmd_assemble(args):
    """Assemble a model prompt from context + galdr analysis data."""
    from pathlib import Path
    from .assemble import assemble_prompt_from_disk

    analysis_dir = Path(args.analysis_dir)
    docs_dir = analysis_dir.parent / "docs"

    try:
        prompt = assemble_prompt_from_disk(
            slug=_validate_slug(args.slug),
            analysis_dir=analysis_dir,
            mode=args.mode,
            template=args.template,
            docs_dir=docs_dir if docs_dir.exists() else None,
        )
        if args.output:
            Path(args.output).write_text(prompt)
            print(f"[assemble] Prompt written to {args.output}", file=sys.stderr)
        else:
            print(prompt)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_frames(args):
    """Extract and describe video frames (target count, event-anchored + coverage)."""
    from pathlib import Path
    from .frames import extract_visual_moments

    analysis_dir = Path(args.analysis_dir)
    video_dir = Path(args.video_dir) if args.video_dir else None
    video_path = Path(args.video) if args.video else None

    try:
        results = extract_visual_moments(
            slug=_validate_slug(args.slug),
            analysis_dir=analysis_dir,
            video_path=video_path,
            video_dir=video_dir,
            url=args.url,
            target=args.target,
            anchor_ratio=args.anchor_ratio,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            print(f"\n[dry-run] {len(results)} frames planned. Pass a video or --url to run.")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_catalog(args):
    """Show or rebuild catalog state."""
    from .catalog import CatalogState

    catalog = CatalogState(args.analysis_dir, catalog_dir=args.catalog_dir)

    if args.rebuild:
        catalog.load()
        catalog.rebuild_from_files()
        print(f"\nCatalog rebuilt: {len(catalog.tracks)} tracks")
        for metric, stats in sorted(catalog.stats.items()):
            print(f"  {metric}: mean={stats['mean']:.4f} std={stats['std']:.4f} "
                  f"range=[{stats['min']:.4f}, {stats['max']:.4f}] n={stats['count']}")
    elif args.track:
        catalog.load()
        print(catalog.summary_card(args.track))
    else:
        catalog.load()
        if catalog.tracks:
            print(f"\nCatalog: {len(catalog.tracks)} tracks\n")
            for name in catalog.tracks:
                print(f"  {name}")
        else:
            print("Catalog is empty")


def main():
    parser = argparse.ArgumentParser(
        prog="galdr",
        description="AI music perception framework",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # listen
    listen_parser = subparsers.add_parser("listen", help="Analyze an audio file")
    listen_parser.add_argument("audio", help="Path to audio file (WAV)")
    listen_parser.add_argument("--name", help="Track name (default: from filename)")
    listen_parser.add_argument("--analysis-dir", default="analysis", help="Output directory root")
    listen_parser.add_argument("--skip", help="Comma-separated modules to skip")
    listen_parser.add_argument("--only", help="Comma-separated modules to run (overrides skip)")
    listen_parser.add_argument("--no-catalog", action="store_true", help="Skip catalog indexing")
    listen_parser.add_argument("--catalog-dir", default=None, help="Catalog state directory (default: ~/.galdr/)")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Download audio + context for a track")
    fetch_parser.add_argument("url", nargs="?", help="YouTube URL (omit if audio already downloaded)")
    fetch_parser.add_argument("--name", required=True, help="Track slug (e.g. 7-helvegen)")
    fetch_parser.add_argument("--artist", required=True, help="Artist name for Wikipedia lookup")
    fetch_parser.add_argument("--title", required=True, help="Song title for Wikipedia lookup")
    fetch_parser.add_argument("--audio-dir", default="audio", help="Directory for audio files (default: audio)")
    fetch_parser.add_argument("--analysis-dir", default="analysis", help="Analysis directory root (default: analysis)")
    fetch_parser.add_argument("--analyze", action="store_true", help="Run galdr listen after download")
    fetch_parser.add_argument("--no-download", action="store_true", help="Skip audio download (context only)")
    fetch_parser.add_argument("--no-wikipedia", action="store_true", help="Skip Wikipedia fetch")
    fetch_parser.add_argument("--no-lyrics", action="store_true", help="Skip lyrics/captions")
    fetch_parser.add_argument("--wiki-artist", help="Exact Wikipedia article title for artist (overrides auto-lookup)")
    fetch_parser.add_argument("--wiki-song", help="Exact Wikipedia article title for song (overrides auto-lookup)")
    fetch_parser.add_argument("--censor", action="store_true", help="Sanitize explicit lyrics before saving (avoids content filter errors)")

    # assemble
    assemble_parser = subparsers.add_parser(
        "assemble",
        help="Build a model prompt from context + analysis data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
Build a model prompt for a track. Output goes to stdout (pipe to a model or file).

Modes control what context is included:
  full     Everything available — best default, graceful degradation (DEFAULT)
  lyrics   galdr metrics + lyrics. Words, no story.
  context  galdr metrics + background. Story, no words.
  blind    galdr metrics only. Purest structural experience.

Templates prepend instruction rules to the data block:
  none     Data block only — add your own instructions (DEFAULT)
  arc      ARC-PROMPT: analytical arc, body tracking, timestamps
  first    FIRST-LISTEN: impressionistic, no chords

Examples:
  galdr assemble 7-helvegen                              # full data, no instructions
  galdr assemble 7-helvegen --template first             # impressionistic
  galdr assemble 7-helvegen --mode blind --template arc  # pure structure, analytical
  galdr assemble 7-helvegen --mode blind > blind.md && galdr assemble 7-helvegen > full.md
""",
    )
    assemble_parser.add_argument("slug", help="Track slug (e.g. 7-helvegen)")
    assemble_parser.add_argument("--analysis-dir", default="analysis", help="Analysis directory (default: analysis)")
    assemble_parser.add_argument("--mode", default="full", choices=["full", "lyrics", "context", "blind"],
                                  help="What context to include (default: full)")
    assemble_parser.add_argument("--template", default="none",
                                  help="Instructions to prepend: none, arc, first, or a file path (default: none)")
    assemble_parser.add_argument("--output", "-o", help="Write prompt to file instead of stdout")

    # frames
    frames_parser = subparsers.add_parser(
        "frames",
        help="Extract and describe video frames (target count, event-anchored + coverage)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
Select a TARGET number of frames from two sources:
  - Event anchors: structural moments (silences, pattern breaks) scored by importance
  - Coverage fill: gap-bisection sampling of underrepresented timeline regions

A track with 2 structural events gets the same number of frames as one with 20.
Requires OPENAI_API_KEY for vision descriptions.

Examples:
  galdr frames 7-helvegen --url https://youtube.com/watch?v=...   # download + describe
  galdr frames 7-helvegen                                          # if video/ exists
  galdr frames 7-helvegen --dry-run                               # show frame plan only
  galdr frames 7-helvegen --target 8                              # fewer frames
  galdr frames 7-helvegen --target 20                             # denser coverage
  galdr frames 7-helvegen --anchor-ratio 0.4                      # more coverage frames
""",
    )
    frames_parser.add_argument("slug", help="Track slug (e.g. 7-helvegen)")
    frames_parser.add_argument("--url", help="YouTube URL to download video from")
    frames_parser.add_argument("--video", help="Explicit path to video file")
    frames_parser.add_argument("--video-dir", default=None,
                                help="Directory to search/save video files (default: video/)")
    frames_parser.add_argument("--analysis-dir", default="analysis",
                                help="Analysis directory root (default: analysis)")
    frames_parser.add_argument("--target", type=int, default=12,
                                help="Total number of frames to select (default: 12)")
    frames_parser.add_argument("--anchor-ratio", type=float, default=0.6,
                                help="Fraction of frames from structural events (default: 0.6)")
    frames_parser.add_argument("--dry-run", action="store_true",
                                help="Show frame plan without extracting frames")

    # compare
    compare_parser = subparsers.add_parser("compare", help="Compare two tracks")
    compare_parser.add_argument("track_a", help="First track name")
    compare_parser.add_argument("track_b", help="Second track name")
    compare_parser.add_argument("--analysis-dir", default="analysis", help="Analysis directory")

    # catalog
    catalog_parser = subparsers.add_parser("catalog", help="View catalog state")
    catalog_parser.add_argument("--catalog-dir", default=None, help="Catalog state directory (default: ~/.galdr/)")
    catalog_parser.add_argument("--analysis-dir", default="analysis", help="Analysis directory")
    catalog_parser.add_argument("--rebuild", action="store_true", help="Rebuild from analysis files")
    catalog_parser.add_argument("--track", help="Show summary card for a specific track")

    args = parser.parse_args()

    if args.command == "listen":
        cmd_listen(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "assemble":
        cmd_assemble(args)
    elif args.command == "frames":
        cmd_frames(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "catalog":
        cmd_catalog(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

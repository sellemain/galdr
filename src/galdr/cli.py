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
    parts = slug.replace("\\", "/").split("/")
    if any(p in (".", "..") or p == "" for p in parts):
        raise ValueError(f"Invalid slug: {slug!r}")
    return slug


_module_failed = False


def run_module(name, func, *args, **kwargs):
    """Run a module with timing and error handling."""
    global _module_failed
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
        _module_failed = True
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
    valid_modules = set(all_modules)
    if args.only:
        requested = [m.strip() for m in args.only.split(",")]
        invalid = [m for m in requested if m not in valid_modules]
        if invalid:
            print(f"Error: unknown module(s) in --only: {', '.join(invalid)}")
            print(f"  Valid modules: {', '.join(sorted(valid_modules))}")
            sys.exit(1)
        modules = requested
    elif args.skip:
        skip_requested = {m.strip() for m in args.skip.split(",")}
        invalid = [m for m in skip_requested if m not in valid_modules]
        if invalid:
            print(f"Error: unknown module(s) in --skip: {', '.join(invalid)}")
            print(f"  Valid modules: {', '.join(sorted(valid_modules))}")
            sys.exit(1)
        modules = [m for m in all_modules if m not in skip_requested]
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
            results["perception"] = result

    if "harmony" in modules:
        result = run_module("Harmony", analyze_harmony, audio_path, output_dir, track_name)
        if result:
            results["harmony"] = result

    if "melody" in modules:
        result = run_module("Melody", analyze_melody, audio_path, output_dir, track_name)
        if result:
            results["melody"] = result

    if "overtone" in modules:
        result = run_module("Overtone", analyze_overtones, audio_path, output_dir, track_name)
        if result:
            results["overtone"] = result

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

    if _module_failed:
        sys.exit(1)


def cmd_compare(args):
    """Compare two tracks."""
    from .compare import compare_tracks
    compare_tracks(args.track_a, args.track_b, args.analysis_dir)


def cmd_fetch(args):
    """Download audio + context for a track."""
    from pathlib import Path
    from .fetch import fetch_track, get_youtube_metadata, slugify, derive_artist_title

    analysis_dir = Path(args.analysis_dir)
    audio_dir = Path(args.audio_dir)

    # Auto-derive slug / artist / title from YouTube metadata when not provided
    name = getattr(args, "name", None)
    artist = getattr(args, "artist", None)
    title = getattr(args, "title", None)

    if args.url and (not name or not artist or not title):
        print(f"[fetch] Fetching metadata from YouTube...")
        try:
            meta = get_youtube_metadata(args.url)
            derived_artist, derived_title = derive_artist_title(
                meta["title"], meta["uploader"]
            )
            if not artist:
                artist = derived_artist
            if not title:
                title = derived_title
            if not name:
                name = slugify(f"{artist}-{title}")
            print(f"[fetch] Artist : {artist}")
            print(f"[fetch] Title  : {title}")
            print(f"[fetch] Slug   : {name}")
        except Exception as e:
            print(f"[fetch] Metadata fetch failed: {e}")
            print("[fetch] Pass --name, --artist, --title explicitly to continue.")
            sys.exit(1)

    if not name or not artist or not title:
        print("[fetch] Error: --name, --artist, and --title are required when no URL is given.")
        sys.exit(1)

    slug = _validate_slug(name)

    fetch_track(
        slug=slug,
        artist=artist,
        title=title,
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
        audio_path = audio_dir / f"{slug}.mp3"
        if audio_path.exists():
            listen_args = type("args", (), {
                "audio": str(audio_path),
                "name": slug,
                "analysis_dir": args.analysis_dir,
                "skip": None,
                "only": None,
                "no_catalog": False,
                "catalog_dir": None,
            })()
            cmd_listen(listen_args)
        else:
            print(f"[fetch] Audio not found at {audio_path}, skipping analysis")

    # Always print the slug at the end so users know what to pass to assemble
    print(f"\n{'─'*50}")
    print(f"  Slug   : {slug}")
    print(f"  Next   : galdr assemble {slug} --template arc --mode full")
    print(f"{'─'*50}\n")


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

    if args.target <= 0:
        print(f"Error: --target must be > 0, got {args.target}", file=sys.stderr)
        sys.exit(1)
    if args.anchor_ratio < 0 or args.anchor_ratio > 1:
        print(f"Error: --anchor-ratio must be between 0 and 1, got {args.anchor_ratio}", file=sys.stderr)
        sys.exit(1)

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


def cmd_update_deps():
    """Update yt-dlp in the current Python environment."""
    import subprocess
    import sys

    print("Updating yt-dlp in current environment...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
        capture_output=False,
    )
    if result.returncode == 0:
        ver = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True,
            text=True,
        )
        print(f"yt-dlp → {ver.stdout.strip()}")
    else:
        print(
            "yt-dlp update failed — run: python -m pip install --upgrade yt-dlp",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    import importlib.metadata
    try:
        _version = importlib.metadata.version("galdr")
    except importlib.metadata.PackageNotFoundError:
        _version = "dev"

    parser = argparse.ArgumentParser(
        prog="galdr",
        description="AI music perception framework",
    )
    parser.add_argument("--version", "-V", action="version", version=f"%(prog)s {_version}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # listen
    listen_parser = subparsers.add_parser("listen", help="Analyze an audio file")
    listen_parser.add_argument(
        "audio",
        help="Path to audio file (WAV/MP3/FLAC/OGG/M4A/AIFF; ffmpeg-supported)",
    )
    listen_parser.add_argument("--name", help="Track name (default: from filename)")
    listen_parser.add_argument("--analysis-dir", default="analysis", help="Output directory root")
    listen_parser.add_argument("--skip", help="Comma-separated modules to skip")
    listen_parser.add_argument("--only", help="Comma-separated modules to run (overrides skip)")
    listen_parser.add_argument("--no-catalog", action="store_true", help="Skip catalog indexing")
    listen_parser.add_argument("--catalog-dir", default=None, help="Catalog state directory (default: ~/.galdr/)")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Download audio + context for a track")
    fetch_parser.add_argument("url", nargs="?", help="YouTube URL (omit if audio already downloaded)")
    fetch_parser.add_argument("--name", default=None, help="Track slug (auto-derived from YouTube title if omitted)")
    fetch_parser.add_argument("--artist", default=None, help="Artist name for Wikipedia lookup (auto-derived if omitted)")
    fetch_parser.add_argument("--title", default=None, help="Song title for Wikipedia lookup (auto-derived if omitted)")
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
  arc      Listening experience template (body, attention, time — first sound to last)
  first    Alias for arc

Examples:
  galdr assemble 7-helvegen                              # full data, no instructions
  galdr assemble 7-helvegen --template arc               # full listening experience
  galdr assemble 7-helvegen --mode blind --template arc  # structure only, no context
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

    # update-deps
    subparsers.add_parser(
        "update-deps",
        help="Update yt-dlp in the current Python environment",
    )

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
    elif args.command == "update-deps":
        cmd_update_deps()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

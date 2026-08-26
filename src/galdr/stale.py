"""Cache validation and stale artifact regeneration helpers."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .provenance import LEGACY_DERIVED_SCHEMA_VERSION, SCHEMA_VERSION, should_reprocess


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def artifact_state(slug: str, analysis_dir: str | Path) -> dict[str, Any]:
    """Inspect a track analysis directory and decide whether it is current."""
    root = Path(analysis_dir) / slug
    perception_path = root / f"{slug}_perception.json"
    stream_path = root / f"{slug}_stream.json"
    context_path = root / "context.json"
    perception = _load_json(perception_path)
    stream_payload = _load_json(stream_path)
    context = _load_json(context_path) or {}

    stale_reasons: list[str] = []
    if should_reprocess(perception, SCHEMA_VERSION):
        stale_reasons.append("perception schema missing/stale")
    if isinstance(stream_payload, dict):
        if should_reprocess(stream_payload, SCHEMA_VERSION):
            stale_reasons.append("stream schema missing/stale")
    elif stream_payload is not None:
        stale_reasons.append("stream is legacy raw list")
    else:
        stale_reasons.append("stream missing")

    dl = context.get("download") if isinstance(context.get("download"), dict) else {}
    audio_file = context.get("audio_file") or dl.get("audio_file")
    youtube_url = context.get("youtube_url") or (context.get("source") or {}).get("url")

    return {
        "slug": slug,
        "analysis_dir": str(Path(analysis_dir)),
        "current": not stale_reasons,
        "stale_reasons": stale_reasons,
        "audio_file": audio_file,
        "audio_exists": bool(audio_file and Path(audio_file).exists()),
        "youtube_url": youtube_url,
        "context_path": str(context_path),
    }


def regenerate_if_stale(
    slug: str,
    analysis_dir: str | Path = "analysis",
    *,
    hop_sec: float | None = None,
    allow_download: bool = True,
) -> dict[str, Any]:
    """Reprocess stale artifacts when local audio or source URL can recover them.

    Policy:
    - current schema: use it
    - stale + local audio: rerun ``galdr listen``
    - stale + source URL: caller may fetch/download first (left explicit for CLI)
    - unrecoverable: mark as ``legacy_derived`` and leave legacy adapter as parachute
    """
    state = artifact_state(slug, analysis_dir)
    if state["current"]:
        state["action"] = "use_current"
        return state

    if state["audio_exists"]:
        cmd = [
            sys.executable,
            "-m",
            "galdr.cli",
            "listen",
            state["audio_file"],
            "--name",
            slug,
            "--analysis-dir",
            str(analysis_dir),
            "--no-catalog",
        ]
        if hop_sec is not None:
            cmd += ["--hop-sec", str(hop_sec)]
        subprocess.run(cmd, check=True)
        state = artifact_state(slug, analysis_dir)
        state["action"] = "reprocessed_local_audio"
        return state

    if allow_download and state.get("youtube_url"):
        state["action"] = "download_required"
        state["note"] = (
            "source URL available; run galdr fetch --analyze to redownload and reprocess"
        )
        return state

    state["action"] = "legacy_derived"
    state["schema_version"] = LEGACY_DERIVED_SCHEMA_VERSION
    state["note"] = "no local audio or recoverable source; use legacy adapter and mark dirty"
    return state

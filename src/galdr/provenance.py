"""Output schema and provenance helpers for galdr analysis artifacts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from . import __version__ as _GALDR_VERSION
except Exception:  # pragma: no cover - defensive during partial imports
    _GALDR_VERSION = "unknown"

SCHEMA_VERSION = "listener_state_v1"
LEGACY_DERIVED_SCHEMA_VERSION = "legacy_derived_v1"


def utc_now_iso() -> str:
    """Return a stable UTC timestamp for artifact metadata."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def file_sha256(path: str | Path) -> str | None:
    """Return a file SHA-256, or None when the file cannot be read."""
    try:
        h = hashlib.sha256()
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def audio_provenance(audio_path: str | Path | None) -> dict[str, Any]:
    """Build provenance for a local audio source."""
    if not audio_path:
        return {"kind": "local_audio", "audio_path": None}
    path = Path(audio_path)
    meta: dict[str, Any] = {
        "kind": "local_audio",
        "audio_path": str(path),
        "audio_sha256": file_sha256(path),
    }
    if path.exists():
        meta["audio_size_bytes"] = path.stat().st_size
    return meta


def artifact_metadata(
    *,
    module: str,
    stream_schema: str = SCHEMA_VERSION,
    audio_path: str | Path | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Common metadata stamped into new galdr artifacts."""
    return {
        "galdr_version": _GALDR_VERSION,
        "schema_version": stream_schema,
        "module": module,
        "created_at": utc_now_iso(),
        "source": source or audio_provenance(audio_path),
    }


def is_current_artifact(payload: dict[str, Any], current_schema: str = SCHEMA_VERSION) -> bool:
    """Return True when an artifact is safe to use without regeneration."""
    return payload.get("schema_version") == current_schema


def should_reprocess(payload: dict[str, Any] | None, current_schema: str = SCHEMA_VERSION) -> bool:
    """Return True for missing, unversioned, or stale artifacts."""
    if not payload:
        return True
    return not is_current_artifact(payload, current_schema=current_schema)

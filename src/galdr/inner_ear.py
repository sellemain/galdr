"""Optional audio-model runner for Galdr Inner Ear witness packets."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .assemble import resolve_template
from .witness import INNER_EAR_PACKET_SCHEMA, validate_witness_packet


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
INNER_EAR_PROMPT_VERSION = "galdr-inner-ear-v0"
REQUIRED_PACKET_FIELDS = {
    "opening",
    "hinges",
    "surface",
    "uncertainties",
    "suspect_claims",
    "assembler_notes",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_response_schema() -> dict[str, Any]:
    """Return the portable subset of JSON Schema accepted by Gemini."""
    return {
        "type": "object",
        "required": [
            "schema",
            "subject",
            "witness",
            "literal_claim_allowed",
            "full_mix_first",
            *sorted(REQUIRED_PACKET_FIELDS),
        ],
        "properties": {
            "schema": {"type": "string", "enum": [INNER_EAR_PACKET_SCHEMA]},
            "subject": {"type": "object"},
            "witness": {"type": "object"},
            "literal_claim_allowed": {"type": "boolean", "enum": [False]},
            "full_mix_first": {"type": "boolean", "enum": [True]},
            "opening": {"type": "object"},
            "hinges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "time_sec",
                        "kind",
                        "claim",
                        "confidence",
                        "suspect",
                    ],
                    "properties": {
                        "time_sec": {"type": "number", "minimum": 0},
                        "kind": {"type": "string"},
                        "claim": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "suspect": {"type": "boolean"},
                    },
                },
            },
            "surface": {"type": "object"},
            "uncertainties": {"type": "array", "items": {"type": "object"}},
            "suspect_claims": {"type": "array", "items": {"type": "object"}},
            "assembler_notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("set GEMINI_API_KEY to use Gemini")
    return key


def _parse_response_text(response: Any) -> dict[str, Any]:
    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Gemini returned no JSON response")
    try:
        packet = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned invalid JSON: {exc}") from exc
    if not isinstance(packet, dict):
        raise ValueError("Gemini response must be a JSON object")
    missing = sorted(REQUIRED_PACKET_FIELDS - packet.keys())
    if missing:
        raise ValueError("Gemini response is missing fields: " + ", ".join(missing))
    return packet


def generate_gemini_witness(
    slug: str,
    audio_path: str | Path,
    model: str = DEFAULT_GEMINI_MODEL,
) -> dict[str, Any]:
    """Upload audio to Gemini and return a locally validated Inner Ear packet."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            'Gemini support is optional; install it with: pip install "galdr[inner-ear]"'
        ) from exc

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise ValueError(f"audio file not found: {audio_path}")

    prompt = resolve_template("inner-ear")
    if not prompt:
        raise RuntimeError("bundled Inner Ear prompt is unavailable")
    audio_sha256 = _sha256_file(audio_path)
    mime_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    client = genai.Client(api_key=_api_key())
    uploaded = None
    try:
        uploaded = client.files.upload(
            file=str(audio_path),
            config=types.UploadFileConfig(mime_type=mime_type),
        )
        while getattr(getattr(uploaded, "state", None), "name", None) == "PROCESSING":
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        state = getattr(getattr(uploaded, "state", None), "name", None)
        if state == "FAILED":
            raise RuntimeError("Gemini could not process the uploaded audio")

        response = client.models.generate_content(
            model=model,
            contents=[prompt, uploaded],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=_load_response_schema(),
            ),
        )
        packet = _parse_response_text(response)
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"Gemini request failed: {exc}") from exc
    finally:
        if uploaded is not None and getattr(uploaded, "name", None):
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass

    packet["schema"] = INNER_EAR_PACKET_SCHEMA
    packet["subject"] = {
        **(packet.get("subject") if isinstance(packet.get("subject"), dict) else {}),
        "slug": slug,
        "audio_sha256": audio_sha256,
    }
    packet["witness"] = {
        "kind": "model_audio",
        "provider": "google-ai-studio",
        "model": model,
        "prompt_version": INNER_EAR_PROMPT_VERSION,
        "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    packet["literal_claim_allowed"] = False
    packet["full_mix_first"] = True
    return validate_witness_packet(packet)

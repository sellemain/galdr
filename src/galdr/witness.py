"""Validation helpers for optional model-produced witness evidence."""

from __future__ import annotations

from typing import Any

from . import __version__


INNER_EAR_PACKET_SCHEMA = "galdr.inner_ear_packet.v0"
HEARING_STREAM_SCHEMA = "galdr.hearing_stream.v0"
INNER_EAR_SUPPORT_MODES = {"galdr_and_audio", "audio_only", "galdr_only"}
WITNESS_SCHEMAS = {INNER_EAR_PACKET_SCHEMA, HEARING_STREAM_SCHEMA}
HEARING_VOICE_INTENSITIES = {"none", "soft", "medium", "hard", "screamed"}
HEARING_DENSITIES = {"thin", "medium", "thick", "wall"}
HEARING_CONFIDENCES = {"medium", "high"}


def validate_witness_packet(packet: Any) -> dict:
    """Validate a supported optional witness packet without a JSON Schema dependency.

    Supported schemas:
    - ``galdr.inner_ear_packet.v0`` — sparse hinge packet
    - ``galdr.hearing_stream.v0`` — dense chronological hearing log
    """
    if not isinstance(packet, dict):
        raise ValueError("witness packet must be a JSON object")

    schema = packet.get("schema")
    if schema == INNER_EAR_PACKET_SCHEMA:
        return _validate_inner_ear_packet(packet)
    if schema == HEARING_STREAM_SCHEMA:
        return _validate_hearing_stream(packet)
    raise ValueError("witness packet schema must be one of: " + ", ".join(sorted(WITNESS_SCHEMAS)))


def _validate_inner_ear_packet(packet: dict) -> dict:
    if packet.get("literal_claim_allowed") is not False:
        raise ValueError("witness packet must set literal_claim_allowed to false")
    if packet.get("full_mix_first") is not True:
        raise ValueError("witness packet must set full_mix_first to true")

    hinges = packet.get("hinges")
    if not isinstance(hinges, list):
        raise ValueError("witness packet hinges must be an array")
    for index, hinge in enumerate(hinges):
        if not isinstance(hinge, dict):
            raise ValueError(f"witness packet hinge {index} must be an object")
        support_mode = hinge.get("support_mode")
        if support_mode not in INNER_EAR_SUPPORT_MODES:
            choices = ", ".join(sorted(INNER_EAR_SUPPORT_MODES))
            raise ValueError(f"witness packet hinge {index} support_mode must be one of: {choices}")
    return packet


def _validate_hearing_stream(packet: dict) -> dict:
    """Validate a frozen v0 dense hearing-stream witness."""
    packet = dict(packet)

    if packet.get("literal_claim_allowed") is not False:
        raise ValueError("hearing stream must set literal_claim_allowed to false")

    if packet.get("full_mix_first") is not True:
        raise ValueError("hearing stream must set full_mix_first to true")

    for field in ("track", "model", "prompt_version"):
        value = packet.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"hearing stream must include non-empty {field}")

    try:
        duration = float(packet["duration_hint_sec"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("hearing stream duration_hint_sec must be a number") from exc
    if duration <= 0:
        raise ValueError("hearing stream duration_hint_sec must be positive")

    events = packet.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("hearing stream events must be a non-empty array")
    if packet.get("event_count") != len(events):
        raise ValueError("hearing stream event_count must equal events length")

    previous_t = -1.0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"hearing stream event {index} must be an object")
        if "t" not in event:
            raise ValueError(f"hearing stream event {index} must include t")
        try:
            event_t = float(event["t"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"hearing stream event {index} t must be a number") from exc
        if event_t < 0 or event_t > duration + 0.5:
            raise ValueError(f"hearing stream event {index} t must be within the source duration")
        if event_t < previous_t:
            raise ValueError("hearing stream event timestamps must be monotonic")
        previous_t = event_t
        now = event.get("now") or event.get("foreground")
        if not isinstance(now, str) or not now.strip():
            raise ValueError(
                f"hearing stream event {index} must include a non-empty now/foreground"
            )
        voice = event.get("voice")
        if not isinstance(voice, dict):
            raise ValueError(f"hearing stream event {index} voice must be an object")
        intensity = voice.get("intensity")
        if intensity not in HEARING_VOICE_INTENSITIES:
            choices = ", ".join(sorted(HEARING_VOICE_INTENSITIES))
            raise ValueError(
                f"hearing stream event {index} voice intensity must be one of: {choices}"
            )
        if event.get("density") not in HEARING_DENSITIES:
            choices = ", ".join(sorted(HEARING_DENSITIES))
            raise ValueError(f"hearing stream event {index} density must be one of: {choices}")
        if event.get("confidence") not in HEARING_CONFIDENCES:
            choices = ", ".join(sorted(HEARING_CONFIDENCES))
            raise ValueError(f"hearing stream event {index} confidence must be one of: {choices}")
    return packet


def witness_kind(packet: dict) -> str:
    """Return a stable kind label for rendering."""
    schema = packet.get("schema")
    if schema == HEARING_STREAM_SCHEMA:
        return "hearing_stream"
    if schema == INNER_EAR_PACKET_SCHEMA:
        return "inner_ear_packet"
    return "unknown"


def assembly_provenance(packet: dict | None = None) -> dict:
    """Return exact Galdr and optional witness provenance for a generated document."""
    result = {
        "schema": "galdr.assembly_provenance.v1",
        "galdr_version": __version__,
    }
    if packet is None:
        return result

    packet = validate_witness_packet(packet)
    witness = {
        "schema": packet["schema"],
        "kind": witness_kind(packet),
    }
    packet_witness = packet.get("witness")
    packet_witness = packet_witness if isinstance(packet_witness, dict) else {}
    for field in ("model", "prompt_version"):
        value = packet.get(field) or packet_witness.get(field)
        if isinstance(value, str) and value.strip():
            witness[field] = value.strip()
    result["witness"] = witness
    return result

"""Validation helpers for optional model-produced witness evidence."""

from __future__ import annotations

from typing import Any

from . import __version__


INNER_EAR_PACKET_SCHEMA = "galdr.inner_ear_packet.v0"
INNER_EAR_SUPPORT_MODES = {"galdr_and_audio", "audio_only", "galdr_only"}


def validate_witness_packet(packet: Any) -> dict:
    """Validate the stable minimum contract without adding a JSON Schema dependency."""
    if not isinstance(packet, dict):
        raise ValueError("witness packet must be a JSON object")
    if packet.get("schema") != INNER_EAR_PACKET_SCHEMA:
        raise ValueError(f"witness packet schema must be '{INNER_EAR_PACKET_SCHEMA}'")
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
            raise ValueError(
                f"witness packet hinge {index} support_mode must be one of: {choices}"
            )
    return packet


def assembly_provenance(packet: dict | None = None) -> dict:
    """Return exact Galdr and optional Inner Ear provenance for a document."""
    result = {
        "schema": "galdr.assembly_provenance.v1",
        "galdr_version": __version__,
    }
    if packet is None:
        return result

    packet = validate_witness_packet(packet)
    packet_witness = packet.get("witness")
    packet_witness = packet_witness if isinstance(packet_witness, dict) else {}
    witness = {
        "schema": packet["schema"],
        "kind": "inner_ear_packet",
    }
    for field in ("model", "prompt_version"):
        value = packet.get(field) or packet_witness.get(field)
        if isinstance(value, str) and value.strip():
            witness[field] = value.strip()
    result["witness"] = witness
    return result

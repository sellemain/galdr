"""Validation helpers for optional model-produced witness evidence."""

from __future__ import annotations

from typing import Any


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

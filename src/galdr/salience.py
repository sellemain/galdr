"""Advisory perceptual salience synthesis for galdr prompts.

This layer does not hide metrics or make final prose decisions. It gives the
prompt a ranked reading of which forces probably deserve narrative weight for
this track, while preserving raw evidence for downstream correction.
"""

from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _add_unique(target: list[dict], name: str, evidence: str, *, confidence: str = "medium") -> None:
    if any(item.get("name") == name for item in target):
        return
    target.append({"name": name, "confidence": confidence, "evidence": evidence})


def synthesize_salience(analysis: dict) -> dict:
    """Return an advisory listening-contract guide from report/perception data.

    The result is deliberately soft: all metrics still remain available. This
    only ranks likely perceptual dominance and flags metrics that should be
    treated as secondary or suspect.
    """
    report = analysis.get("report") or {}
    perception = analysis.get("perception") or {}
    summary = perception.get("summary") or {}

    attention = _f(summary.get("mean_attention"))
    pattern = _f(summary.get("mean_pattern"))
    body = _f(report.get("body"))
    body_capture = _f(summary.get("mean_body_capture"), body)
    body_comfort = _f(summary.get("mean_body_comfort"), _f(summary.get("mean_groove_comfort")))
    groove_comfort = _f(summary.get("mean_groove_comfort"), body_comfort)
    weight = _f(report.get("weight"))
    metric_tension = _f(report.get("metric_tension"))
    pulse_confidence = _f(report.get("pulse_confidence"), 0.5)
    pulse = _f(report.get("pulse"))
    surface_density = _f(summary.get("mean_surface_density"))
    texture = _f(report.get("texture"), 0.5)
    release_force = _f(summary.get("peak_release_force"))
    pressure_building = _f(summary.get("pressure_building_pct"))
    pressure_releasing = _f(summary.get("pressure_releasing_pct"))
    pressure_sustaining = _f(summary.get("pressure_sustaining_pct"))
    silence_pct = _f(summary.get("loudness_silence_pct"))

    headline: list[dict] = []
    supporting: list[dict] = []
    technical: list[dict] = []
    low_confidence: list[dict] = []
    conflict_notes: list[str] = []

    # Broad listening contract. This is a prompt guide, not a genre label.
    contract = "balanced_listener_state"

    high_lock = attention >= 0.82 and pattern >= 0.88
    captured = body_capture >= 0.58 or body >= 0.58
    comfortable = body_comfort >= 0.48 or groove_comfort >= 0.48
    discomfort_gap = body_capture - body_comfort
    uncomfortable = captured and body_comfort and (body_comfort <= 0.45 or discomfort_gap >= 0.22)
    pressure_dominant = weight >= 0.38 or pressure_sustaining >= 70 or pressure_building >= 20
    sparse_or_suspended = (
        (body_capture < 0.45 and surface_density <= 0.35 and (weight >= 0.35 or silence_pct >= 10))
        or (body <= 0.45 and weight >= 0.45 and texture <= 0.20)
    )

    if high_lock and captured and pressure_dominant and (
        weight >= 0.30 or pressure_sustaining >= 88 or (body_comfort <= 0.45 and discomfort_gap >= 0.20)
    ):
        contract = "coercive_heavy_lock"
        _add_unique(
            headline,
            "coercive body lock",
            f"attention {attention:.3f}, pattern {pattern:.3f}, body_capture {body_capture:.3f}, body_comfort {body_comfort:.3f}",
            confidence="high",
        )
        _add_unique(supporting, "pressure hold", f"weight {weight:.3f}; pressure sustaining {pressure_sustaining:.1f}%")
    elif sparse_or_suspended:
        contract = "suspended_texture_or_ambient_space"
        _add_unique(
            headline,
            "sustained texture / space",
            f"body_capture {body_capture:.3f}, surface_density {surface_density:.3f}, weight {weight:.3f}",
            confidence="high",
        )
        if high_lock:
            _add_unique(supporting, "pattern hold", f"attention {attention:.3f}, pattern {pattern:.3f}")
    elif high_lock and captured and comfortable and metric_tension < 0.30 and weight < 0.35 and pressure_sustaining < 88:
        contract = "settled_pocket_or_groove"
        _add_unique(
            headline,
            "body-settled groove",
            f"body_capture {body_capture:.3f}, body_comfort {body_comfort:.3f}, metric_tension {metric_tension:.3f}",
            confidence="high",
        )
    elif high_lock and metric_tension >= 0.45:
        contract = "metric_grid_pressure"
        _add_unique(
            headline,
            "metric / grid pressure",
            f"metric_tension {metric_tension:.3f}, pulse_confidence {pulse_confidence:.2f}",
            confidence="medium",
        )
    elif high_lock and surface_density <= 0.50 and captured:
        contract = "sparse_hook_or_minimal_grid"
        _add_unique(
            headline,
            "minimal grid / hook",
            f"attention {attention:.3f}, surface_density {surface_density:.3f}, body_capture {body_capture:.3f}",
            confidence="medium",
        )
    elif high_lock:
        contract = "sustained_pattern_hold"
        _add_unique(headline, "pattern hold", f"attention {attention:.3f}, pattern {pattern:.3f}", confidence="medium")

    if release_force >= 0.55 or pressure_releasing >= 20:
        _add_unique(supporting, "release behavior", f"peak_release_force {release_force:.3f}; pressure releasing {pressure_releasing:.1f}%")
    if surface_density >= 0.50:
        _add_unique(supporting, "surface density", f"mean_surface_density {surface_density:.3f}")
    if metric_tension >= 0.30:
        target = supporting if contract in {"metric_grid_pressure", "sustained_pattern_hold"} else technical
        _add_unique(
            target,
            "metric tension",
            f"metric_tension {metric_tension:.3f} ({report.get('metric_tension_state', 'unknown')})",
        )
    if weight >= 0.45 and contract != "coercive_heavy_lock":
        _add_unique(supporting, "weight / suspension", f"weight {weight:.3f} ({report.get('weight_state', 'unknown')})")

    if metric_tension >= 0.30 and pulse_confidence < 0.45:
        _add_unique(low_confidence, "metric tension", f"pulse_confidence {pulse_confidence:.2f}; treat as technical/ambiguous")
    if metric_tension >= 0.30 and contract == "coercive_heavy_lock":
        conflict_notes.append("Metric tension is present, but the dominant felt state looks like body/pressure lock; do not automatically headline technical meter complexity.")
    if contract != "settled_pocket_or_groove" and uncomfortable and metric_tension < 0.20 and pulse >= 0.85:
        conflict_notes.append("Low comfort with stable pulse may reflect force, stiffness, or sound design rather than true metric complexity.")

    return {
        "listening_contract": contract,
        "headline_forces": headline,
        "supporting_forces": supporting,
        "technical_underlayer": technical,
        "low_confidence_metrics": low_confidence,
        "conflict_notes": conflict_notes,
    }

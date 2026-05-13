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


def _add_axis(axes: dict[str, dict], axis: str, value: str, evidence: str, *, confidence: str = "medium") -> None:
    axes[axis] = {"value": value, "confidence": confidence, "evidence": evidence}


def _axis_label(value: float, bands: tuple[tuple[float, str], ...]) -> str:
    for cutoff, label in bands:
        if value < cutoff:
            return label
    return bands[-1][1]


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
    accent_drift = _f(summary.get("mean_accent_phase_drift"))
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
    prose_hints: list[str] = []
    secondary_contracts: list[str] = []
    force_axes: dict[str, dict] = {}

    high_pattern = attention >= 0.82 and pattern >= 0.88
    pattern_drive = pattern >= 0.82 and body_capture >= 0.55 and body >= 0.55 and 0.24 <= weight < 0.35
    captured = body_capture >= 0.58 or body >= 0.58
    comfortable = body_comfort >= 0.48 or groove_comfort >= 0.48
    settled_comfort = body_comfort >= 0.58 or groove_comfort >= 0.58
    discomfort_gap = body_capture - body_comfort
    uncomfortable = captured and body_comfort and (body_comfort <= 0.45 or (discomfort_gap >= 0.24 and body_comfort < 0.56))
    light_or_present_weight = weight < 0.35
    heavy_or_suspended_weight = weight >= 0.35
    pressure_dominant = heavy_or_suspended_weight or pressure_sustaining >= 82 or pressure_building >= 24
    pressure_only_lock = pressure_sustaining >= 84 and not settled_comfort and not light_or_present_weight
    sparse_or_suspended = (
        (body_capture < 0.45 and surface_density <= 0.35 and (weight >= 0.35 or silence_pct >= 10))
        or (body <= 0.45 and weight >= 0.45 and texture <= 0.20)
    )

    # Factorized force axes. These are reusable primitives, not compound genre labels.
    body_relation = "absent"
    if body_capture >= 0.70:
        body_relation = "captured"
    elif body_capture >= 0.52:
        body_relation = "engaged"
    elif body_capture >= 0.32:
        body_relation = "lightly_engaged"
    _add_axis(force_axes, "body_relation", body_relation, f"body_capture {body_capture:.3f}, body {body:.3f}")

    comfort_relation = "neutral"
    if body_comfort >= 0.58 or groove_comfort >= 0.58:
        comfort_relation = "comfortable"
    elif uncomfortable:
        comfort_relation = "resisted"
    elif body_comfort <= 0.34 and captured:
        comfort_relation = "tense"
    _add_axis(
        force_axes,
        "comfort_relation",
        comfort_relation,
        f"body_comfort {body_comfort:.3f}, groove_comfort {groove_comfort:.3f}, capture-comfort gap {discomfort_gap:.3f}",
    )

    _add_axis(
        force_axes,
        "weight",
        _axis_label(weight, ((0.18, "light"), (0.35, "present"), (0.55, "suspended"), (1.01, "heavy"))),
        f"weight {weight:.3f} ({report.get('weight_state', 'unknown')})",
    )
    _add_axis(
        force_axes,
        "surface",
        _axis_label(surface_density, ((0.22, "sparse"), (0.42, "open"), (0.60, "dense"), (1.01, "saturated"))),
        f"surface_density {surface_density:.3f}",
    )
    _add_axis(
        force_axes,
        "pressure",
        "sustained" if pressure_sustaining >= 80 else "building" if pressure_building >= 20 else "releasing" if pressure_releasing >= 20 else "balanced",
        f"building {pressure_building:.1f}%, sustaining {pressure_sustaining:.1f}%, releasing {pressure_releasing:.1f}%",
    )
    _add_axis(
        force_axes,
        "grid_relation",
        "drifting" if accent_drift >= 0.72 else "elastic" if accent_drift >= 0.45 else "stable",
        f"accent_phase_drift {accent_drift:.3f}, metric_tension {metric_tension:.3f}",
    )

    # Broad listening contract. This is deliberately simple: contract first,
    # modifiers/axes second. Avoid names that bake multiple forces together.
    primary_contract = "balanced_listener_state"

    if sparse_or_suspended:
        primary_contract = "field"
        _add_unique(
            headline,
            "sustained texture / space",
            f"body_capture {body_capture:.3f}, surface_density {surface_density:.3f}, weight {weight:.3f}",
            confidence="high",
        )
        prose_hints.extend(["suspended texture", "held field"])
        if high_pattern:
            _add_unique(supporting, "pattern hold", f"attention {attention:.3f}, pattern {pattern:.3f}")
    elif high_pattern and captured and metric_tension >= 0.45:
        primary_contract = "grid"
        _add_unique(
            headline,
            "metric / grid pressure",
            f"metric_tension {metric_tension:.3f}, pulse_confidence {pulse_confidence:.2f}",
            confidence="medium",
        )
        prose_hints.append("grid pressure")
    elif high_pattern and captured and light_or_present_weight and surface_density <= 0.55 and (
        uncomfortable or (metric_tension >= 0.30 and not settled_comfort) or (accent_drift >= 0.72 and body_comfort < 0.56)
    ):
        primary_contract = "grid"
        _add_unique(
            headline,
            "minimal grid / hook",
            f"attention {attention:.3f}, surface_density {surface_density:.3f}, body_capture {body_capture:.3f}, body_comfort {body_comfort:.3f}",
            confidence="medium",
        )
        prose_hints.append("minimal grid")
    elif high_pattern and captured and (settled_comfort or (comfortable and not uncomfortable)) and metric_tension < 0.30 and light_or_present_weight:
        primary_contract = "pocket"
        _add_unique(
            headline,
            "body-settled groove",
            f"body_capture {body_capture:.3f}, body_comfort {body_comfort:.3f}, metric_tension {metric_tension:.3f}",
            confidence="high",
        )
        prose_hints.append("settled pocket")
    elif high_pattern and captured and (heavy_or_suspended_weight or uncomfortable or pressure_only_lock):
        primary_contract = "lock"
        _add_unique(
            headline,
            "body lock",
            f"attention {attention:.3f}, pattern {pattern:.3f}, body_capture {body_capture:.3f}, body_comfort {body_comfort:.3f}",
            confidence="high" if weight >= 0.30 or pressure_sustaining >= 88 else "medium",
        )
        if weight >= 0.35:
            prose_hints.append("mass lock")
            braced_mass = (
                surface_density <= 0.22
                and accent_drift < 0.45
                and (pressure_building >= 20 or body < 0.45 or body_comfort < 0.52)
            )
            soft_mass = surface_density >= 0.26 and body_comfort >= 0.48 and pressure_sustaining < 84
            if braced_mass:
                prose_hints.append("braced mass lock")
            elif pressure_sustaining >= 84:
                prose_hints.append("impact mass lock")
            elif soft_mass:
                prose_hints.append("soft mass lock")
        elif uncomfortable:
            prose_hints.append("tense lock")
        elif pressure_only_lock:
            prose_hints.append("sustained lock")
    elif high_pattern and surface_density <= 0.50 and captured:
        primary_contract = "grid"
        _add_unique(
            headline,
            "minimal grid / hook",
            f"attention {attention:.3f}, surface_density {surface_density:.3f}, body_capture {body_capture:.3f}",
            confidence="medium",
        )
        prose_hints.append("minimal grid")
    elif high_pattern or pattern_drive:
        primary_contract = "pattern_hold"
        _add_unique(
            headline,
            "pattern hold",
            f"attention {attention:.3f}, pattern {pattern:.3f}, body_capture {body_capture:.3f}, weight {weight:.3f}",
            confidence="medium",
        )
        if pattern_drive:
            prose_hints.append("plain body drive")

    if primary_contract != "grid" and metric_tension >= 0.30:
        secondary_contracts.append("grid")
    if primary_contract != "field" and sparse_or_suspended:
        secondary_contracts.append("field")
    if primary_contract != "lock" and captured and (heavy_or_suspended_weight or uncomfortable or pressure_only_lock):
        secondary_contracts.append("lock")
    if primary_contract != "pocket" and captured and (settled_comfort or (comfortable and not uncomfortable)) and light_or_present_weight:
        secondary_contracts.append("pocket")

    if primary_contract == "grid" and (uncomfortable or body_comfort < 0.56) and weight < 0.35:
        prose_hints.append("tight minimal grid")
    if primary_contract == "grid" and uncomfortable:
        prose_hints.append("hostile pocket")
    if primary_contract == "pocket" and weight < 0.20 and body_capture >= 0.70:
        prose_hints.append("light body pocket")
    if primary_contract == "field" and weight >= 0.45 and body_capture < 0.35:
        prose_hints.append("force without motor lock")

    if release_force >= 0.55 or pressure_releasing >= 20:
        _add_unique(supporting, "release behavior", f"peak_release_force {release_force:.3f}; pressure releasing {pressure_releasing:.1f}%")
    if surface_density >= 0.50:
        _add_unique(supporting, "surface density", f"mean_surface_density {surface_density:.3f}")
    if metric_tension >= 0.30:
        target = supporting if primary_contract in {"grid", "pattern_hold"} else technical
        _add_unique(
            target,
            "metric tension",
            f"metric_tension {metric_tension:.3f} ({report.get('metric_tension_state', 'unknown')})",
        )
    if weight >= 0.45 and primary_contract != "lock":
        _add_unique(supporting, "weight / suspension", f"weight {weight:.3f} ({report.get('weight_state', 'unknown')})")
    if primary_contract in {"lock", "grid"} and pressure_dominant:
        _add_unique(supporting, "pressure hold", f"weight {weight:.3f}; pressure sustaining {pressure_sustaining:.1f}%")

    if metric_tension >= 0.30 and pulse_confidence < 0.45:
        _add_unique(low_confidence, "metric tension", f"pulse_confidence {pulse_confidence:.2f}; treat as technical/ambiguous")
    if metric_tension >= 0.30 and primary_contract == "lock":
        conflict_notes.append("Metric tension is present, but the dominant felt state looks like body/pressure lock; do not automatically headline technical meter complexity.")
    if primary_contract != "pocket" and uncomfortable and metric_tension < 0.20 and pulse >= 0.85:
        conflict_notes.append("Low comfort with stable pulse may reflect force, stiffness, or sound design rather than true metric complexity.")
    if primary_contract == "lock" and weight < 0.30 and pressure_sustaining < 88:
        conflict_notes.append("This is a lock by capture/attention, not necessarily mass; avoid weight-language unless weight or pressure earns it.")
    if primary_contract == "lock" and weight >= 0.35:
        conflict_notes.append("Mass lock means weight or gravity is the holding force, not necessarily loudness or metal heaviness.")

    # Back-compat field: old callers expect listening_contract. Prefer
    # primary_contract for new code/docs.
    return {
        "primary_contract": primary_contract,
        "listening_contract": primary_contract,
        "secondary_contracts": list(dict.fromkeys(secondary_contracts)),
        "force_axes": force_axes,
        "prose_hints": list(dict.fromkeys(prose_hints)),
        "headline_forces": headline,
        "supporting_forces": supporting,
        "technical_underlayer": technical,
        "low_confidence_metrics": low_confidence,
        "conflict_notes": conflict_notes,
    }

#!/usr/bin/env python3
"""Boundary-candidate helpers for album/interlude segmentation.

Arc spans describe listener-state regimes.  Boundary candidates describe
possible song or section cuts: silence/interlude zones plus evidence that
the state resets after the gap.
"""

from __future__ import annotations


def _num(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(rows: list[dict], key: str, default: float = 0.0) -> float:
    if not rows:
        return default
    return sum(_num(row.get(key), default) for row in rows) / len(rows)


def _max_delta(before: dict[str, float], after: dict[str, float]) -> float:
    keys = ("attention", "pattern", "pressure", "body", "weight", "surface_density")
    return min(1.0, max(abs(after.get(key, 0.0) - before.get(key, 0.0)) for key in keys))


def _is_gap_frame(frame: dict) -> bool:
    """Return true for frames that can plausibly separate songs/sections."""
    if not bool(frame.get("silence")):
        return False
    rms = _num(frame.get("rms_energy"), 1.0)
    density = _num(frame.get("surface_density"), 1.0)
    depth = _num(frame.get("silence_depth_db"), 0.0)
    lufs = frame.get("loudness_lufs")
    loudness_floor = lufs is not None and _num(lufs, 0.0) <= -55.0
    return rms < 0.01 or density < 0.12 or depth <= -35.0 or loudness_floor


def _row_t(row: dict, index: int, hop_sec: float) -> float:
    return _num(row.get("t", row.get("time")), index * hop_sec)


def _summarize_window(rows: list[dict]) -> dict[str, float]:
    return {
        "attention": _mean(rows, "attention"),
        "pattern": _mean(rows, "pattern"),
        "pressure": _mean(rows, "pressure"),
        "body": _mean(rows, "body"),
        "weight": _mean(rows, "weight"),
        "surface_density": _mean(rows, "surface_density"),
    }


def derive_boundary_candidates(
    stream: list[dict],
    *,
    hop_sec: float | None = None,
    min_gap_sec: float = 3.0,
    context_sec: float = 4.0,
    merge_gap_sec: float = 2.0,
) -> list[dict]:
    """Find possible song/interlude boundaries from silence plus reset evidence.

    These are deliberately not arc transitions.  A candidate marks a low-energy
    gap and estimates whether the material after it feels like continuation,
    reset, withdrawal, or terminal decay.
    """
    if not stream:
        return []

    if hop_sec is None:
        if len(stream) >= 2:
            hop_sec = max(0.001, _row_t(stream[1], 1, 1.0) - _row_t(stream[0], 0, 1.0))
        else:
            hop_sec = 1.0

    rows = [dict(row, _boundary_t=_row_t(row, i, hop_sec)) for i, row in enumerate(stream)]
    runs: list[list[dict]] = []
    current: list[dict] = []
    for row in rows:
        if _is_gap_frame(row):
            current.append(row)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)

    merged_runs: list[list[dict]] = []
    for run in runs:
        if not merged_runs:
            merged_runs.append(run)
            continue
        previous_end = merged_runs[-1][-1]["_boundary_t"] + hop_sec
        if run[0]["_boundary_t"] - previous_end <= merge_gap_sec:
            merged_runs[-1].extend(run)
        else:
            merged_runs.append(run)

    duration = rows[-1]["_boundary_t"] + hop_sec
    candidates: list[dict] = []
    for run in merged_runs:
        start = run[0]["_boundary_t"]
        end = run[-1]["_boundary_t"] + hop_sec
        gap_sec = end - start
        if gap_sec < min_gap_sec:
            continue

        pre_rows = [row for row in rows if start - context_sec <= row["_boundary_t"] < start]
        post_rows = [row for row in rows if end <= row["_boundary_t"] < end + context_sec]
        before = _summarize_window(pre_rows)
        after = _summarize_window(post_rows)
        reset_strength = _max_delta(before, after) if pre_rows and post_rows else 0.0

        if start <= 2.0:
            kind = "opening_gap"
        elif end >= max(duration - 3.0, 0.0):
            kind = "ending_gap"
        elif reset_strength >= 0.28:
            kind = "probable_boundary"
        elif gap_sec >= 8.0:
            kind = "possible_boundary"
        else:
            kind = "interlude_gap"

        reentry_strength = 0.0
        if pre_rows and post_rows:
            reentry_strength = max(0.0, after["attention"] - before["attention"])
            reentry_strength += max(0.0, after["pressure"] - before["pressure"]) * 0.5
            reentry_strength = min(1.0, reentry_strength)

        confidence = 0.30
        confidence += min(gap_sec / 20.0, 0.35)
        confidence += min(reset_strength, 0.30)
        if kind in {"opening_gap", "ending_gap"}:
            confidence = max(confidence, 0.70)
        elif kind == "probable_boundary":
            confidence += 0.10
        elif kind == "interlude_gap":
            confidence -= 0.12
        confidence = max(0.0, min(0.95, confidence))

        candidates.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(gap_sec, 2),
            "kind": kind,
            "confidence": round(confidence, 3),
            "reset_strength": round(reset_strength, 3),
            "reentry_strength": round(reentry_strength, 3),
            "mean_rms_energy": round(_mean(run, "rms_energy"), 5),
            "mean_surface_density": round(_mean(run, "surface_density"), 3),
            "min_loudness_lufs": round(min(_num(row.get("loudness_lufs"), 0.0) for row in run), 1),
        })

    return candidates

#!/usr/bin/env python3
"""Compare two tracks side-by-side.

Outputs a formatted comparison showing deltas for all shared metrics,
highlighting where tracks diverge most and converge most.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

from .arc import derive_arc_spans


def _unwrap_stream_payload(data):
    if isinstance(data, dict) and isinstance(data.get("stream"), list):
        return data["stream"]
    if isinstance(data, list):
        return data
    return []


def load_track_data(analysis_dir, track_name):
    """Load all available analysis data for a track."""
    d = Path(analysis_dir) / track_name
    if not d.exists():
        return None

    data = {}
    for suffix, key in [
        ("_report.json", "report"),
        ("_perception.json", "perception"),
        ("_stream.json", "stream"),
        ("_harmony.json", "harmony"),
        ("_melody.json", "melody"),
        ("_overtone.json", "overtone"),
    ]:
        path = d / f"{track_name}{suffix}"
        if path.exists():
            with open(path) as f:
                data[key] = json.load(f)

    return data if data else None


def flatten_metrics(data):
    """Extract a flat dict of numeric metrics from nested analysis data."""
    metrics = {}

    if "report" in data:
        r = data["report"]
        for k in ["duration_seconds", "detected_pulse_bpm", "felt_pulse_bpm",
                   "beat_count", "pulse", "body", "weight", "texture",
                   "harmonic_weight", "percussive_weight", "spectral_centroid_mean_hz",
                   "onset_count", "onsets_per_second", "mean_zcr", "dynamic_range_ratio"]:
            if k in r and isinstance(r[k], (int, float)):
                metrics[k] = r[k]

    if "perception" in data:
        s = data["perception"].get("summary", data["perception"])
        for k in ["mean_attention", "mean_pattern",
                   "total_silence_sec", "pattern_break_count",
                   "pressure_building_pct", "pressure_releasing_pct",
                   "pressure_sustaining_pct"]:
            if k in s and isinstance(s[k], (int, float)):
                metrics[k] = s[k]

    if "harmony" in data:
        h = data["harmony"]
        for k in ["mean_pitch_grid", "mean_interval_coherence", "mean_harmonic_pull",
                   "mean_chroma_motion", "mean_tonal_anchor",
                   "mean_major_minor", "key_confidence"]:
            if k in h and isinstance(h[k], (int, float)):
                metrics[k] = h[k]

    if "melody" in data:
        m = data["melody"]
        for k in ["overall_range_semitones", "mean_foreground_line",
                   "contour_ascending_pct", "contour_descending_pct",
                   "contour_holding_pct", "mean_direction"]:
            if k in m and isinstance(m[k], (int, float)):
                metrics[k] = m[k]

    if "overtone" in data:
        o = data["overtone"]
        for k in ["mean_overtone_fit", "mean_overtone_density", "mean_inharmonicity",
                   "voiced_frames", "total_frames"]:
            if k in o and isinstance(o[k], (int, float)):
                metrics[k] = o[k]

    return metrics


def format_delta(a_val, b_val):
    """Format the delta between two values with direction arrow."""
    delta = b_val - a_val
    if abs(delta) < 0.0005:
        return "  ="
    arrow = ">" if delta > 0 else "<"
    return f"{arrow} {abs(delta):+.3f}"


def _arc_summary(data):
    stream = _unwrap_stream_payload(data.get("stream"))
    if not stream:
        return None

    spans = derive_arc_spans(stream)
    if not spans:
        return None

    total_frames = sum(span["frame_count"] for span in spans)
    if total_frames <= 0:
        return None

    frame_counts = Counter()
    run_counts = Counter()
    transitions = Counter()
    weighted = defaultdict(float)
    previous = None
    for span in spans:
        label = span["label"]
        frame_count = span["frame_count"]
        frame_counts[label] += frame_count
        run_counts[label] += 1
        for key in ["mean_attention", "mean_pattern", "mean_pressure", "mean_body", "mean_weight", "silence_ratio"]:
            weighted[key] += span[key] * frame_count
        if previous:
            transitions[(previous, label)] += 1
        previous = label

    return {
        "span_count": len(spans),
        "total_frames": total_frames,
        "frame_counts": frame_counts,
        "run_counts": run_counts,
        "weighted": {key: value / total_frames for key, value in weighted.items()},
        "transitions": transitions,
        "longest": sorted(spans, key=lambda span: span["frame_count"], reverse=True)[:5],
    }


def _print_arc_summary(track_name, summary):
    print(f"  {track_name}: {summary['span_count']} arc spans across {summary['total_frames']} frames")
    weighted = summary["weighted"]
    print(
        "    means: "
        f"attention={weighted['mean_attention']:.3f}, "
        f"pattern={weighted['mean_pattern']:.3f}, "
        f"pressure={weighted['mean_pressure']:.3f}, "
        f"body={weighted['mean_body']:.3f}, "
        f"silence={weighted['silence_ratio']:.3f}"
    )
    for label, frames in summary["frame_counts"].most_common():
        pct = frames / summary["total_frames"] * 100
        runs = summary["run_counts"][label]
        print(f"    {label:<10} {frames:>4} frames  {pct:>5.1f}%  runs={runs}")
    print("    longest:")
    for span in summary["longest"]:
        print(
            f"      {span['label']:<10} {span['start']:>6.1f}-{span['end']:<6.1f} "
            f"frames={span['frame_count']:>3} "
            f"att={span['mean_attention']:.3f} pat={span['mean_pattern']:.3f} "
            f"pressure={span['mean_pressure']:.3f} body={span['mean_body']:.3f}"
        )


def _print_arc_comparison(track_a, arc_a, track_b, arc_b):
    if not arc_a and not arc_b:
        return

    print("\n  ARC SPANS:")
    if arc_a:
        _print_arc_summary(track_a, arc_a)
    else:
        print(f"  {track_a}: no stream data found")
    if arc_b:
        _print_arc_summary(track_b, arc_b)
    else:
        print(f"  {track_b}: no stream data found")

    if not (arc_a and arc_b):
        return

    labels = sorted(set(arc_a["frame_counts"]) | set(arc_b["frame_counts"]))
    print("\n  Arc frame distribution delta, B - A:")
    for label in labels:
        pct_a = arc_a["frame_counts"].get(label, 0) / arc_a["total_frames"]
        pct_b = arc_b["frame_counts"].get(label, 0) / arc_b["total_frames"]
        print(f"    {label:<10} {pct_a:>6.1%} -> {pct_b:>6.1%} ({pct_b - pct_a:+.1%})")

    print("\n  Top arc transitions:")
    for name, arc in [(track_a, arc_a), (track_b, arc_b)]:
        transitions = arc["transitions"].most_common(5)
        rendered = ", ".join(f"{a}->{b} x{count}" for (a, b), count in transitions) or "none"
        print(f"    {name}: {rendered}")


def compare_tracks(track_a, track_b, analysis_dir="analysis"):
    """Compare two tracks and print a formatted side-by-side report."""
    data_a = load_track_data(analysis_dir, track_a)
    data_b = load_track_data(analysis_dir, track_b)

    if not data_a:
        print(f"Error: No analysis data found for '{track_a}' in {analysis_dir}/")
        return
    if not data_b:
        print(f"Error: No analysis data found for '{track_b}' in {analysis_dir}/")
        return

    metrics_a = flatten_metrics(data_a)
    metrics_b = flatten_metrics(data_b)

    # Find shared metrics
    shared_keys = sorted(set(metrics_a.keys()) & set(metrics_b.keys()))
    only_a = sorted(set(metrics_a.keys()) - set(metrics_b.keys()))
    only_b = sorted(set(metrics_b.keys()) - set(metrics_a.keys()))

    # Compute deltas and sort by magnitude
    deltas = []
    for k in shared_keys:
        a_val = metrics_a[k]
        b_val = metrics_b[k]
        max_val = max(abs(a_val), abs(b_val), 0.001)
        norm_delta = abs(b_val - a_val) / max_val
        deltas.append((k, a_val, b_val, b_val - a_val, norm_delta))

    # Print comparison
    print(f"\n{'=' * 70}")
    print(f"  COMPARISON: {track_a}  vs  {track_b}")
    print(f"{'=' * 70}\n")

    # String metadata
    for data, name in [(data_a, track_a), (data_b, track_b)]:
        parts = []
        if "report" in data:
            r = data["report"]
            parts.append(f"{r.get('duration_seconds', '?')}s")
            parts.append(f"{r.get('felt_pulse_bpm', '?')} BPM")
            parts.append(r.get('character', ''))
            parts.append(r.get('brightness', ''))
        if "harmony" in data:
            parts.append(f"key: {data['harmony'].get('detected_key', '?')}")
        if "melody" in data:
            parts.append(f"center: {data['melody'].get('overall_center_note', '?')}")
        print(f"  {name}: {', '.join(p for p in parts if p)}")
    print()

    # Header
    max_key_len = max(len(k) for k in shared_keys) if shared_keys else 20
    header = f"  {'Metric':<{max_key_len}}  {'A':>10}  {'B':>10}  {'Delta':>12}  {'Rel%':>6}"
    print(header)
    print(f"  {'-' * (max_key_len + 44)}")

    # Sort by normalized delta (largest differences first)
    deltas.sort(key=lambda x: -x[4])

    for k, a_val, b_val, raw_delta, norm_delta in deltas:
        if norm_delta > 0.5:
            marker = "##"
        elif norm_delta > 0.2:
            marker = "++"
        elif norm_delta > 0.1:
            marker = ".."
        else:
            marker = "  "

        rel_pct = norm_delta * 100
        print(f"  {k:<{max_key_len}}  {a_val:>10.3f}  {b_val:>10.3f}  {raw_delta:>+11.3f}  {rel_pct:>5.1f}% {marker}")

    # Show metrics only in one track
    if only_a:
        print(f"\n  Only in {track_a}: {', '.join(only_a)}")
    if only_b:
        print(f"\n  Only in {track_b}: {', '.join(only_b)}")

    # Biggest convergences and divergences
    if len(deltas) >= 3:
        print(f"\n  MOST DIFFERENT:")
        for k, a_val, b_val, raw_delta, norm_delta in deltas[:3]:
            print(f"    {k}: {a_val:.3f} -> {b_val:.3f} ({raw_delta:+.3f})")

        print(f"\n  MOST SIMILAR:")
        for k, a_val, b_val, raw_delta, norm_delta in deltas[-3:]:
            print(f"    {k}: {a_val:.3f} ~ {b_val:.3f} ({raw_delta:+.3f})")

    _print_arc_comparison(track_a, _arc_summary(data_a), track_b, _arc_summary(data_b))

    print()

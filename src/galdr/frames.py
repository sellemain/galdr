"""galdr frames — extract and describe video frames at structural and coverage moments.

Selects a TARGET number of frames (default 12) from two sources:
  - Event anchors: structural moments (silences, pattern breaks), scored by importance
  - Coverage fill: gap-based sampling of underrepresented timeline regions

This produces a consistent visual record regardless of how event-dense a track is.
A track with 2 structural events gets the same number of frames as one with 20.

Design principles:
  - Fixed target: caller controls budget, not event count
  - Events are priority anchors, not the only source
  - Gap-fill maximizes coverage of uncovered timeline
  - Dense event clusters don't monopolize the frame budget
  - Eyes-closed listening is valid. Frames are comparative, not default.

Frame windows per event type (from empirical testing on Helvegen):
  - Long silence (≥3s):  [t-1s, t, t+dur×0.6]  — before, onset, deep into silence
  - Short silence (<3s): [t-1s, t]              — before, onset
  - Pattern break:       [t-1s, t]              — before, onset

Vision API: anchor frames from the same event go to one call (sequence context).
Coverage frames are one call each (no structural context to attach).

Usage:
    galdr frames 7-helvegen --url https://youtube.com/watch?v=...
    galdr frames 7-helvegen                     # if video/7-helvegen.mp4 exists
    galdr frames 7-helvegen --dry-run           # show selected timestamps, no extraction
    galdr frames 7-helvegen --target 8          # fewer frames
    galdr frames 7-helvegen --target 20         # denser coverage
"""

import base64
import heapq
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path


# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_TARGET = 12
DEFAULT_ANCHOR_RATIO = 0.6  # up to 60% of slots from structural events
CLUSTER_GAP = 2.0           # seconds: events within this window are clustered


# ─── Event loading ─────────────────────────────────────────────────────────────

def _load_events(perception: dict) -> list[dict]:
    """Extract all events from perception data. Handles old and new schemas.

    New schema: perception['pattern_breaks'] — unified list, type='silence'|'break'
    Old schema: perception['silences'] + perception['moments'] — separate lists
    """
    events = []

    raw_breaks = perception.get("pattern_breaks", [])
    if raw_breaks:
        for b in raw_breaks:
            t = b.get("time", 0)
            btype = b.get("type", "break")
            if btype == "silence":
                events.append({
                    "time": t,
                    "type": "silence",
                    "duration": b.get("duration", 0),
                    "depth_db": b.get("depth_db", -80),
                    "intensity": 0,
                })
            else:
                events.append({
                    "time": t,
                    "type": "break",
                    "duration": 0,
                    "intensity": b.get("intensity", 0),
                    "components": b.get("components", {}),
                })
    else:
        for s in perception.get("silences", []):
            events.append({
                "time": s.get("start", 0),
                "type": "silence",
                "duration": s.get("duration", 0),
                "depth_db": s.get("depth_db", -80),
                "intensity": 0,
            })
        for m in perception.get("moments", []):
            if m.get("type") != "silence":
                events.append({
                    "time": m.get("time", 0),
                    "type": "break",
                    "duration": 0,
                    "intensity": m.get("intensity", 0),
                })

    return sorted(events, key=lambda e: e["time"])


# ─── Event scoring & clustering ───────────────────────────────────────────────

def _score_event(ev: dict) -> float:
    """Score an event by structural significance. Silences score 2× breaks."""
    if ev["type"] == "silence":
        depth_factor = min(1.0, abs(ev.get("depth_db", -80)) / 80.0)
        dur_factor = min(1.0, ev.get("duration", 0) / 10.0)
        return 2.0 * (depth_factor * 0.4 + dur_factor * 0.6)
    return float(ev.get("intensity", 0))


def _cluster_events(events: list[dict], gap: float = CLUSTER_GAP) -> list[list[dict]]:
    """Group events that occur within `gap` seconds of each other."""
    clusters: list[list[dict]] = []
    for ev in events:
        if clusters and ev["time"] - clusters[-1][-1]["time"] <= gap:
            clusters[-1].append(ev)
        else:
            clusters.append([ev])
    return clusters


def _best_in_cluster(cluster: list[dict]) -> dict:
    """Pick the most significant event from a cluster."""
    silences = [e for e in cluster if e["type"] == "silence"]
    if silences:
        return max(silences, key=lambda e: e["duration"])
    return max(cluster, key=lambda e: e["intensity"])


# ─── Timestamp windows ────────────────────────────────────────────────────────

def _event_timestamps(ev: dict, duration: float) -> list[tuple[float, str]]:
    """Compute frame timestamps for an event. Returns list of (time, role) tuples.

    Roles: 'before' | 'onset' | 'during'

    Windows (from empirical testing):
      Long silence (≥3s):  [t-1, t, t+dur×0.6]  — 3 frames
      Short silence (<3s): [t-1, t]              — 2 frames
      Pattern break:       [t-1, t]              — 2 frames

    When t=0 (or near-zero), the 'before' frame clamps to 0.0 — same as 'onset'.
    In that case, 'before' is dropped to avoid extracting the identical frame twice.
    """
    t = ev["time"]
    dur = ev.get("duration", 0)

    def clamp(x: float) -> float:
        return max(0.0, min(duration, x)) if duration else max(0.0, x)

    before_t = clamp(t - 1.0)
    onset_t = t

    if ev["type"] == "silence":
        if dur >= 3.0:
            during_t = clamp(t + dur * 0.6)
            candidates = [(before_t, "before"), (onset_t, "onset"), (during_t, "during")]
        else:
            candidates = [(before_t, "before"), (onset_t, "onset")]
    else:
        candidates = [(before_t, "before"), (onset_t, "onset")]

    # Deduplicate: drop 'before' if it landed on the same timestamp as 'onset'
    seen: set[float] = set()
    result: list[tuple[float, str]] = []
    for ts, role in candidates:
        if ts not in seen:
            seen.add(ts)
            result.append((ts, role))
    return result


# ─── Coverage gap-fill ────────────────────────────────────────────────────────

def _fill_coverage_gaps(
    existing_times: list[float],
    duration: float,
    n: int,
) -> list[float]:
    """Greedily fill n timestamps by repeatedly bisecting the largest gap.

    Uses a max-heap. Each iteration plants a frame at the midpoint of the
    widest uncovered stretch of the track, then splits that gap in two.

    This naturally distributes coverage to wherever there are the fewest frames,
    without needing any knowledge of the track's content.
    """
    if n <= 0 or duration <= 0:
        return []

    boundaries = sorted(set([0.0, duration] + existing_times))

    # Max-heap via negated span
    heap: list[tuple[float, float, float]] = []
    for i in range(len(boundaries) - 1):
        span = boundaries[i + 1] - boundaries[i]
        heapq.heappush(heap, (-span, boundaries[i], boundaries[i + 1]))

    results: list[float] = []
    for _ in range(n):
        if not heap:
            break
        neg_span, lo, hi = heapq.heappop(heap)
        mid = (lo + hi) / 2.0
        results.append(mid)
        # Split into two sub-gaps
        heapq.heappush(heap, (-(mid - lo), lo, mid))
        heapq.heappush(heap, (-(hi - mid), mid, hi))

    return sorted(results)


# ─── Frame selection (main algorithm) ────────────────────────────────────────

def select_frames(
    perception: dict,
    duration: float,
    target: int = DEFAULT_TARGET,
    anchor_ratio: float = DEFAULT_ANCHOR_RATIO,
) -> list[dict]:
    """Select `target` frame timestamps balancing event anchors and coverage.

    Phase 1 — Anchor budget (target × anchor_ratio slots):
      Score all structural events, cluster nearby ones, assign 1–3 timestamp
      slots per event in score order until the anchor budget is exhausted.

    Phase 2 — Coverage fill (remaining slots):
      Bisect the largest uncovered timeline gaps until target is reached.

    Returns a list of frame dicts sorted by time:
      {
        "time":  float,               # timestamp to extract
        "kind":  "anchor"|"coverage", # source type
        "role":  str,                 # before|onset|during|coverage
        "event": dict | None,         # originating event (anchors only)
        "group": str | None,          # group ID (anchors share with same event)
      }
    """
    raw_events = _load_events(perception)
    anchor_budget = round(target * anchor_ratio)

    # Cluster → best per cluster → score-ranked
    clusters = _cluster_events(raw_events, gap=CLUSTER_GAP)
    representatives = [_best_in_cluster(c) for c in clusters]
    ranked = sorted(representatives, key=_score_event, reverse=True)

    # Assign anchor slots in score order
    anchors: list[dict] = []
    slots_used = 0

    for ev in ranked:
        if slots_used >= anchor_budget:
            break
        timestamps = _event_timestamps(ev, duration)
        remaining_budget = anchor_budget - slots_used
        timestamps = timestamps[:remaining_budget]  # trim if near budget

        group_id = f"{ev['type']}_{ev['time']:.1f}"
        for ts, role in timestamps:
            anchors.append({
                "time": ts,
                "kind": "anchor",
                "role": role,
                "event": ev,
                "group": group_id,
            })
        slots_used += len(timestamps)

    # Fill remaining slots with coverage
    coverage_needed = target - len(anchors)
    coverage_times = _fill_coverage_gaps(
        existing_times=[a["time"] for a in anchors],
        duration=duration,
        n=coverage_needed,
    )
    coverage_frames = [
        {
            "time": ts,
            "kind": "coverage",
            "role": "coverage",
            "event": None,
            "group": None,
        }
        for ts in coverage_times
    ]

    all_frames = sorted(anchors + coverage_frames, key=lambda f: f["time"])

    # Enforce minimum inter-frame spacing across all frames.
    # When two frames fall within min_spacing seconds of each other, drop the
    # lower-priority one.  Priority: anchor > coverage; within anchor, earlier
    # role index wins (before > onset > during, matching the role order in each
    # event's timestamp list).
    #
    # This catches the case where a 'during' frame from one event and the
    # 'before' frame of an immediately adjacent event overlap.
    ROLE_PRIORITY = {"before": 0, "onset": 1, "during": 2, "coverage": 3}
    MIN_SPACING = 1.0  # seconds

    kept: list[dict] = []
    kept_times: list[float] = []
    for f in all_frames:
        ts = f["time"]
        too_close = any(abs(ts - kt) < MIN_SPACING for kt in kept_times)
        if not too_close:
            kept.append(f)
            kept_times.append(ts)
        else:
            # Check if this frame is higher priority than the closest kept frame
            closest_idx = min(range(len(kept_times)), key=lambda i: abs(kept_times[i] - ts))
            existing = kept[closest_idx]
            existing_prio = ROLE_PRIORITY.get(existing["role"], 9)
            incoming_prio = ROLE_PRIORITY.get(f["role"], 9)
            if incoming_prio < existing_prio:
                # Replace the kept frame with the higher-priority one
                kept[closest_idx] = f
                kept_times[closest_idx] = ts

    return kept


# ─── Frame extraction via ffmpeg ──────────────────────────────────────────────

def extract_single_frame(video_path: Path, timestamp: float, out_path: Path) -> bool:
    """Extract one frame from video at the given timestamp. Returns True on success."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(out_path),
        "-y",
        "-loglevel", "error",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and out_path.exists():
        return True
    print(f"  [frames] ffmpeg failed at t={timestamp:.2f}s: {result.stderr.decode()[:100]}")
    return False


# ─── Vision API ───────────────────────────────────────────────────────────────

def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _describe_anchor_group(
    frame_paths: list[Path],
    timestamps: list[float],
    roles: list[str],
    event: dict,
    track_name: str,
) -> str:
    """Describe an anchor group: 1–3 frames around a structural event."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return "[no OPENAI_API_KEY — description skipped]"

    t = event["time"]
    ts_str = " / ".join(f"{w:.1f}s [{r}]" for w, r in zip(timestamps, roles))

    if event["type"] == "silence":
        dur = event.get("duration", 0)
        db = event.get("depth_db", -80)
        event_desc = f"a {dur:.1f}s silence ({db:.1f}dB) at t={t:.1f}s"
    else:
        intensity = event.get("intensity", 0)
        event_desc = f"a structural disruption (intensity {intensity:.3f}) at t={t:.1f}s"

    n = len(frame_paths)

    prompt = (
        f"These {n} frames are from '{track_name}', captured at {ts_str}.\n\n"
        f"Audio analysis flagged {event_desc} here. "
        f"Roles: 'before' = just prior to the event; 'onset' = the moment it begins; "
        f"'during' = inside the silence or disruption.\n\n"
        f"Describe: who is on screen and camera distance (close-up / medium / wide). "
        f"For each frame, note head direction, hands, and posture. "
        f"State the most significant visible change between frames — even subtle shifts count. "
        f"If the image cuts or goes dark, say exactly when.\n\n"
        f"3–5 sentences. Specific over general. Minimal interpretation."
    )

    content = []
    for frame_path in frame_paths:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{_encode_image(frame_path)}",
                "detail": "high",
            }
        })
    content.append({"type": "text", "text": prompt})

    return _call_vision_api(content, api_key)


def _describe_coverage_frame(frame_path: Path, timestamp: float, track_name: str) -> str:
    """Describe a single coverage frame — no structural event context."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return "[no OPENAI_API_KEY — description skipped]"

    prompt = (
        f"This frame is from '{track_name}' at t={timestamp:.1f}s.\n\n"
        f"Describe: camera distance (close-up / medium / wide), who or what is on screen, "
        f"what they are doing, and the energy implied by their posture or motion.\n\n"
        f"2–3 sentences."
    )

    content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{_encode_image(frame_path)}",
                "detail": "high",
            }
        },
        {"type": "text", "text": prompt},
    ]

    return _call_vision_api(content, api_key)


def _call_vision_api(content: list, api_key: str) -> str:
    """Make one gpt-4o vision API call. Returns response text."""
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 300,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[vision API error: {e}]"


# ─── Video download ────────────────────────────────────────────────────────────

def download_video(url: str, video_dir: Path, slug: str) -> Path | None:
    """Download video at up to 720p via yt-dlp. Returns path or None on failure."""
    video_dir.mkdir(parents=True, exist_ok=True)
    out_template = video_dir / f"{slug}.%(ext)s"

    cmd = [
        "yt-dlp",
        "--format", (
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
            "/best[height<=720][ext=mp4]/best[height<=720]"
        ),
        "--merge-output-format", "mp4",
        "--output", str(out_template),
        "--no-playlist",
        url,
    ]

    print(f"  [frames] downloading video: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    for ext in ["mp4", "mkv", "webm"]:
        p = video_dir / f"{slug}.{ext}"
        if p.exists():
            print(f"  [frames] video saved: {p}")
            return p

    print(f"  [frames] download failed:\n{result.stderr[:400]}")
    return None


# ─── Display helpers ──────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _event_label(ev: dict) -> str:
    if ev["type"] == "silence":
        return f"{ev['duration']:.1f}s silence at {ev['depth_db']:.0f}dB"
    return f"pattern break (intensity {ev.get('intensity', 0):.3f})"


def print_frame_plan(frames: list[dict], duration: float) -> None:
    """Print the frame selection plan to stdout."""
    anchors = [f for f in frames if f["kind"] == "anchor"]
    coverage = [f for f in frames if f["kind"] == "coverage"]

    # Group anchors by group ID
    groups: dict[str, list[dict]] = {}
    for f in anchors:
        g = f["group"]
        groups.setdefault(g, []).append(f)

    print(f"  Frame plan: {len(frames)} total "
          f"({len(anchors)} anchor / {len(coverage)} coverage)")
    print()

    for f in frames:
        t = f["time"]
        kind = f["kind"]
        role = f["role"]
        marker = "●" if kind == "anchor" else "·"
        ev = f.get("event")
        if ev:
            ev_info = f"  ← {ev['type']} @ {_fmt_time(ev['time'])} ({_event_label(ev)})"
        else:
            ev_info = ""
        print(f"  {marker} {_fmt_time(t)} ({t:.1f}s)  [{role}]{ev_info}")

    print()
    # Show coverage: how many frames per track-third
    third = duration / 3
    thirds = [0, 0, 0]
    for f in frames:
        idx = min(2, int(f["time"] / third))
        thirds[idx] += 1
    print(f"  Coverage: intro {thirds[0]} / mid {thirds[1]} / outro {thirds[2]}")


# ─── Main entry point ─────────────────────────────────────────────────────────

def extract_visual_moments(
    slug: str,
    analysis_dir: Path,
    video_path: Path | None = None,
    video_dir: Path | None = None,
    url: str | None = None,
    target: int = DEFAULT_TARGET,
    anchor_ratio: float = DEFAULT_ANCHOR_RATIO,
    dry_run: bool = False,
) -> list[dict]:
    """Extract and describe frames for a track, hitting exactly `target` frames.

    Anchor frames (≤target×anchor_ratio) come from structural events.
    Coverage frames fill the rest using gap-bisection for even distribution.

    Each anchor group (frames from the same event) gets one vision call.
    Each coverage frame gets its own (simpler) vision call.

    Results stored in analysis/{slug}/context.json under 'frame_descriptions'.
    Each entry: {time, kind, role, event (label str), window, description}
    """
    track_dir = analysis_dir / slug

    # Load perception data
    perc_path = track_dir / f"{slug}_perception.json"
    if not perc_path.exists():
        raise FileNotFoundError(
            f"No perception data at {perc_path}. Run 'galdr listen' first."
        )
    perception = json.loads(perc_path.read_text())

    # Inject duration from report
    report_path = track_dir / f"{slug}_report.json"
    duration = 0.0
    if report_path.exists():
        report = json.loads(report_path.read_text())
        duration = report.get("duration_seconds", 0.0)
    if not duration:
        duration = perception.get("duration", 0.0)

    if not duration:
        raise ValueError(f"Cannot determine track duration for '{slug}'.")

    # Select frames
    frames = select_frames(perception, duration, target=target, anchor_ratio=anchor_ratio)
    print_frame_plan(frames, duration)

    if dry_run:
        return frames

    # Resolve video file
    if video_path is None:
        if video_dir is None:
            video_dir = analysis_dir.parent / "video"
        for ext in ["mp4", "mkv", "webm", "mov"]:
            candidate = video_dir / f"{slug}.{ext}"
            if candidate.exists():
                video_path = candidate
                break

    if video_path is None:
        if url:
            if video_dir is None:
                video_dir = analysis_dir.parent / "video"
            video_path = download_video(url, video_dir, slug)
        if video_path is None:
            raise FileNotFoundError(
                f"No video found for '{slug}'. "
                f"Pass --url to download, or place a file at video/{slug}.mp4"
            )

    print(f"  [frames] video: {video_path}")

    # Resolve track name for vision prompts
    ctx_path = track_dir / "context.json"
    ctx: dict = {}
    ctx_loaded = False
    track_name = slug
    if ctx_path.exists():
        try:
            ctx = json.loads(ctx_path.read_text())
            ctx_loaded = True
            artist = ctx.get("artist", "")
            title = ctx.get("title", "")
            if artist and title:
                track_name = f"{artist} — {title}"
        except Exception as e:
            print(f"  [frames] warning: could not parse context.json ({e}); frame descriptions will not be saved")
            ctx_loaded = False

    # Extract all frames, then process by group
    tmp_dir = Path(tempfile.mkdtemp(prefix="galdr_frames_"))
    frame_descriptions: list[dict] = []

    try:
        # Extract all frame images first
        extracted: dict[float, Path] = {}
        for f in frames:
            ts = f["time"]
            out_path = tmp_dir / f"frame_{ts:.3f}.png"
            if extract_single_frame(video_path, ts, out_path):
                extracted[ts] = out_path
            else:
                extracted[ts] = None  # type: ignore

        # Process anchor groups
        groups_done: set[str] = set()
        for f in frames:
            if f["kind"] != "anchor" or f["group"] in groups_done:
                continue
            group_id = f["group"]
            groups_done.add(group_id)

            # Collect all frames in this group
            group_frames = [x for x in frames if x.get("group") == group_id]
            group_frames.sort(key=lambda x: x["time"])

            timestamps = [x["time"] for x in group_frames]
            roles = [x["role"] for x in group_frames]
            event = group_frames[0]["event"]
            frame_paths = [extracted[ts] for ts in timestamps if extracted.get(ts)]

            label = _event_label(event)
            print(f"  [frames] anchor group: {group_id}  ({len(frame_paths)} frames)")

            if frame_paths:
                description = _describe_anchor_group(
                    frame_paths, timestamps, roles, event, track_name
                )
            else:
                description = "[frame extraction failed]"

            preview = description[:80].replace("\n", " ")
            print(f"  [frames] → {preview}...")

            frame_descriptions.append({
                "time": event["time"],
                "kind": "anchor",
                "role": "anchor",
                "event": label,
                "window": timestamps,
                "roles": roles,
                "description": description,
            })

        # Process coverage frames
        for f in frames:
            if f["kind"] != "coverage":
                continue
            ts = f["time"]
            frame_path = extracted.get(ts)
            print(f"  [frames] coverage: {_fmt_time(ts)}")

            if frame_path:
                description = _describe_coverage_frame(frame_path, ts, track_name)
            else:
                description = "[frame extraction failed]"

            frame_descriptions.append({
                "time": ts,
                "kind": "coverage",
                "role": "coverage",
                "event": None,
                "window": [ts],
                "roles": ["coverage"],
                "description": description,
            })

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Sort by time before saving
    frame_descriptions.sort(key=lambda x: x["time"])

    # Write back to context.json — only if we successfully loaded it
    if ctx_loaded:
        ctx["frame_descriptions"] = frame_descriptions
        ctx_path.parent.mkdir(parents=True, exist_ok=True)
        ctx_path.write_text(json.dumps(ctx, indent=2))
    else:
        print("  [frames] skipping context.json write (parse error on load — original preserved)")

    anchor_count = sum(1 for x in frame_descriptions if x["kind"] == "anchor")
    coverage_count = sum(1 for x in frame_descriptions if x["kind"] == "coverage")
    print(
        f"  [frames] saved {len(frame_descriptions)} descriptions "
        f"({anchor_count} anchor / {coverage_count} coverage) → {ctx_path}"
    )

    return frame_descriptions


# ─── Legacy alias ─────────────────────────────────────────────────────────────

def select_events(perception: dict, max_events: int = 4) -> list[dict]:
    """Deprecated: use select_frames() instead.

    Returns events in the old format (with 'window' key) for backward compat.
    Kept so existing test code doesn't break.
    """
    raw = _load_events(perception)
    duration = perception.get("duration", 0)

    clusters = _cluster_events(raw)
    representatives = [_best_in_cluster(c) for c in clusters]
    ranked = sorted(representatives, key=_score_event, reverse=True)
    selected = sorted(ranked[:max_events], key=lambda e: e["time"])

    for ev in selected:
        ts_roles = _event_timestamps(ev, duration)
        ev["window"] = [t for t, _ in ts_roles]

    return selected

#!/usr/bin/env python3
"""Run one galdr breadth-evaluation track from a rotating queue.

Designed for cron: each invocation claims the next unfinished track, runs
`galdr listen`, writes a blind assembled prompt, and advances state.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aiff", ".aif"}


@dataclass(frozen=True)
class Track:
    audio: Path
    slug: str


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_tracks(path: Path, repo: Path) -> list[Track]:
    tracks: list[Track] = []
    with path.open(newline="") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
                continue
            audio = Path(row[0].strip())
            slug = row[1].strip() if len(row) > 1 and row[1].strip() else audio.stem
            if audio.suffix.lower() not in AUDIO_EXTS:
                raise ValueError(f"Not an audio file in queue: {audio}")
            if not audio.is_absolute():
                audio = repo / audio
            tracks.append(Track(audio=audio, slug=slug))
    if not tracks:
        raise ValueError(f"No tracks found in {path}")
    return tracks


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"cursor": 0, "runs": []}
    return json.loads(path.read_text())


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def run(cmd: list[str], cwd: Path, log_path: Path) -> None:
    with log_path.open("a") as log:
        log.write(f"\n$ {' '.join(cmd)}\n")
        log.flush()
        subprocess.run(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".", help="galdr repo root")
    parser.add_argument("--queue", default="configs/sm331-evaluation-tracks.txt")
    parser.add_argument("--state", default="analysis/sm331-breadth-eval/state.json")
    parser.add_argument("--analysis-dir", default="analysis/sm331-breadth-eval/runs")
    parser.add_argument("--log-dir", default="analysis/sm331-breadth-eval/logs")
    parser.add_argument("--limit", type=int, default=100, help="stop after this many successful runs")
    parser.add_argument("--hop-sec", default="0.5")
    parser.add_argument("--python", default=None, help="python executable; default prefers .venv/bin/python")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    queue_path = (repo / args.queue).resolve() if not Path(args.queue).is_absolute() else Path(args.queue)
    state_path = (repo / args.state).resolve() if not Path(args.state).is_absolute() else Path(args.state)
    analysis_dir = (repo / args.analysis_dir).resolve() if not Path(args.analysis_dir).is_absolute() else Path(args.analysis_dir)
    log_dir = (repo / args.log_dir).resolve() if not Path(args.log_dir).is_absolute() else Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    python = args.python or str(repo / ".venv" / "bin" / "python")
    if not Path(python).exists():
        python = sys.executable

    tracks = load_tracks(queue_path, repo)
    state = load_state(state_path)
    runs = state.setdefault("runs", [])
    succeeded = {r["slug"] for r in runs if r.get("status") == "ok"}
    if len(succeeded) >= args.limit:
        print(f"limit reached: {len(succeeded)} successful runs >= {args.limit}")
        return 0

    cursor = int(state.get("cursor", 0)) % len(tracks)
    chosen: Track | None = None
    for offset in range(len(tracks)):
        candidate = tracks[(cursor + offset) % len(tracks)]
        if candidate.slug not in succeeded:
            chosen = candidate
            state["cursor"] = (cursor + offset + 1) % len(tracks)
            break
    if chosen is None:
        print(f"all {len(tracks)} queued tracks already succeeded")
        return 0

    if not chosen.audio.exists():
        record = {"at": iso_now(), "slug": chosen.slug, "audio": str(chosen.audio), "status": "missing"}
        runs.append(record)
        save_state(state_path, state)
        print(f"missing audio: {chosen.audio}")
        return 2

    log_path = log_dir / f"{iso_now().replace(':', '')}-{chosen.slug}.log"
    record = {"at": iso_now(), "slug": chosen.slug, "audio": str(chosen.audio), "status": "running"}
    runs.append(record)
    save_state(state_path, state)

    env = os.environ.copy()
    cache_root = Path.home() / ".cache" / "galdr"
    env.setdefault("NUMBA_CACHE_DIR", str(cache_root / "numba"))
    env.setdefault("UV_CACHE_DIR", str(cache_root / "uv"))
    Path(env["NUMBA_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(env["UV_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)

    try:
        # Use env via a tiny wrapper because run() intentionally keeps command logging simple.
        with log_path.open("a") as log:
            log.write(f"started {iso_now()} slug={chosen.slug} audio={chosen.audio}\n")
            log.flush()
            listen_cmd = [
                python,
                "-m",
                "galdr",
                "listen",
                str(chosen.audio),
                "--name",
                chosen.slug,
                "--analysis-dir",
                str(analysis_dir),
                "--hop-sec",
                str(args.hop_sec),
            ]
            log.write(f"\n$ {' '.join(listen_cmd)}\n")
            log.flush()
            subprocess.run(listen_cmd, cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)

            prompt_path = analysis_dir / chosen.slug / "assembled-blind.md"
            assemble_cmd = [
                python,
                "-m",
                "galdr",
                "assemble",
                chosen.slug,
                "--analysis-dir",
                str(analysis_dir),
                "--mode",
                "blind",
            ]
            log.write(f"\n$ {' '.join(assemble_cmd)} > {prompt_path}\n")
            log.flush()
            assembled = subprocess.run(
                assemble_cmd,
                cwd=repo,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=True,
            )
            prompt_path.write_text(assembled.stdout)

        record.update({"status": "ok", "finished_at": iso_now(), "log": str(log_path), "analysis": str(analysis_dir / chosen.slug)})
        save_state(state_path, state)
        print(f"ok {chosen.slug}")
        return 0
    except subprocess.CalledProcessError as exc:
        record.update({"status": "failed", "finished_at": iso_now(), "returncode": exc.returncode, "log": str(log_path)})
        save_state(state_path, state)
        print(f"failed {chosen.slug}; see {log_path}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())

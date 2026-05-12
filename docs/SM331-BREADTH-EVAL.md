# SM-331 breadth evaluation

Purpose: run the current perception/salience stack across a broad, boringly consistent track set before making more perception changes.

## Queue

`configs/sm331-evaluation-tracks.txt` is the explicit track queue. It uses tab-separated rows:

```text
audio/path.mp3<TAB>analysis-slug
```

The current queue contains the locally available evaluation audio, excluding the known full-album Aphex Twin file marked `FULL_ALBUM_DO_NOT_ANALYZE`.

## Runner

Run one track:

```bash
./tools/eval/run_rotation_once.py
```

Default outputs:

- `analysis/sm331-breadth-eval/state.json` — cursor and run status
- `analysis/sm331-breadth-eval/runs/<slug>/` — galdr analysis output
- `analysis/sm331-breadth-eval/runs/<slug>/assembled-blind.md` — blind assembled prompt
- `analysis/sm331-breadth-eval/logs/*.log` — command logs

The runner stops after 100 successful tracks by default. With the current local queue it will stop after all queued tracks have succeeded.

## Cron shape

Use OpenClaw cron to run it every 10 minutes from `/home/user/src/galdr`:

```bash
./tools/eval/run_rotation_once.py --repo /home/user/src/galdr
```

The job should be quiet on success and surface failures only. Do not change perception metrics again until the breadth run has produced enough evidence to judge calibration failures.

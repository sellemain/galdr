# SM-309 Silence Recovery and Re-entry

## Failure / mismatch

Before SM-309, galdr could mark silence windows but could not say what happened after the gap. A reader saw "silence 0.58s" or "silence 7.05s" with no distinction between a return that resumes the prior state, resets attention, ruptures the stream, or withdraws into ending.

## Baseline output

Using the existing Helvegen / Wardruna + Aurora live source, pre-SM-309 output could only surface silence windows. The exact windows were true, but structurally flat: a half-second ceremonial pause, a late breath gap, and a terminal departure were all just `silence`.

Representative old shape:

```text
Heard pressure: silence-aware floor; describe movement as pressure, build, release, or sustain rather than meter readings
6:12 — silence 0.57s at -46.2dB
6:17 — silence 0.56s at -47.4dB
6:22 — silence 0.68s at -49.3dB
6:27 — silence 0.56s at -46.8dB
6:33 — silence 1.56s at -52.8dB
6:46 — silence 5.26s at -80.0dB
```

The windows are true, but the return behavior is missing.

## Change

Added silence re-entry events in perception:

- `silence_reentries[]`
- `reentry_shape`: internal returns use `continuation`, `rupture`, `reset`, or `withdrawal`; boundary silences use `entry_preparation` or `terminal_decay`
- `boundary_position`: `opening`, `internal`, or `closing`
- `reentry_force`
- `recovery_time_sec`
- pre/post momentum and pressure fields for auditability
- pattern-break silence events enriched with re-entry fields
- assembled output now surfaces silence outcomes in listener-state language

## Re-run

Re-ran Helvegen from `/home/user/galdr-queue/Wardruna and Aurora - Helvegen (Live).wav` through the current branch:

```bash
.venv/bin/python -m galdr.cli listen \
  "/home/user/galdr-queue/Wardruna and Aurora - Helvegen (Live).wav" \
  --name helvegen-sm309 \
  --analysis-dir /tmp/galdr-sm309-helvegen/analysis \
  --no-catalog
.venv/bin/python -m galdr.cli assemble helvegen-sm309 \
  --analysis-dir /tmp/galdr-sm309-helvegen/analysis \
  --mode blind
```

New output excerpt:

```text
Silence returns: 7 silence outcomes (entry_preparation:1, continuation:4, withdrawal:1, terminal_decay:1; boundary opening:1, internal:5, closing:1); describe internal returns as continuation, rupture, reset, or withdrawal, and boundary silence as entry preparation or terminal decay
0:00 — silence 1.58s at -80.0dB; return: entry_preparation, opening, re-entry force 0.000, entry follows
6:12 — silence 0.57s at -46.2dB; return: continuation, re-entry force 0.004, recovery 0.10s
6:17 — silence 0.56s at -47.4dB; return: continuation, re-entry force 0.031, recovery 0.07s
6:22 — silence 0.68s at -49.3dB; return: withdrawal, re-entry force 0.000, recovery 0.38s
6:27 — silence 0.56s at -46.8dB; return: continuation, re-entry force 0.073, recovery 0.19s
6:33 — silence 1.56s at -52.8dB; return: continuation, re-entry force 0.000, no recovery before next withdrawal
6:46 — silence 5.26s at -80.0dB; return: terminal_decay, closing, re-entry force 0.397, no recovery before ending
```

## Result

Improved: silence is now structural and boundary-aware. The same late Helvegen windows are still visible, but they no longer collapse into identical events. The opening lead-in is entry preparation, the short ritual gaps mostly resume as continuation, and the terminal long silence is terminal decay rather than a mid-song withdrawal. The 6:22 internal gap is still flagged as a small withdrawal despite a quick recovery, which is useful as a tuning target: the model is catching a drop in local state, but the label may read harsher than the music feels.

Still wrong / risk: the labels are heuristic and should be treated as listener-state evidence, not final interpretation. `rupture` may need tuning on tracks with dramatic drop-to-hit returns. The current artifact proves the output lane and schema, not universal threshold correctness.

## Verification

```text
54 passed, 4 warnings  # tests/test_unit.py
34 passed, 3 warnings  # tests/test_regressions.py
89 passed, 9 warnings  # combined unit + regression run
```

Warnings are existing Python 3.13 `aifc`/`sunau` deprecations and librosa short-audio `n_fft` warnings.

# SM-309 Silence Recovery and Re-entry

## Failure / mismatch

Before SM-309, galdr could mark silence windows but could not say what happened after the gap. A reader saw "silence 0.58s" or "silence 7.05s" with no distinction between a return that resumes the prior state, resets attention, ruptures the stream, or withdraws into ending.

## Baseline output

Using the existing Aurora Runaway v0.2.2 artifact:

```text
Heard pressure: 0.6% silence-aware floor; describe movement as pressure, build, release, or sustain rather than meter readings
0:00 — silence 0.58s at -80.0dB
0:20 — silence 0.51s at -53.7dB
0:33 — silence 0.58s at -53.3dB
4:02 — silence 7.05s at -80.0dB
```

The windows are true, but structurally flat.

## Change

Added silence re-entry events in perception:

- `silence_reentries[]`
- `reentry_shape`: `continuation`, `rupture`, `reset`, or `withdrawal`
- `reentry_force`
- `recovery_time_sec`
- pre/post momentum and pressure fields for auditability
- pattern-break silence events enriched with re-entry fields
- assembled output now surfaces silence outcomes in listener-state language

## Re-run

Re-ran Aurora from the same `/tmp/galdr-022-eval/audio/aurora-runaway-022-eval.mp3` source through the current branch:

```bash
.venv/bin/python -m galdr.cli listen /tmp/galdr-022-eval/audio/aurora-runaway-022-eval.mp3 \
  --name aurora-sm309 \
  --analysis-dir /tmp/galdr-sm309-check/analysis \
  --no-catalog
.venv/bin/python -m galdr.cli assemble aurora-sm309 \
  --analysis-dir /tmp/galdr-sm309-check/analysis \
  --mode blind
```

New output excerpt:

```text
Silence returns: 4 silence outcomes (continuation:2, reset:1, withdrawal:1); describe whether the music resumes as continuation, rupture, reset, or withdrawal
0:00 — silence 0.58s at -80.0dB; return: reset, re-entry force 0.110, recovery 0.42s
0:20 — silence 0.51s at -53.7dB; return: continuation, re-entry force 0.016, recovery 0.13s
0:33 — silence 0.58s at -53.3dB; return: continuation, re-entry force 0.001, recovery 0.09s
4:02 — silence 7.05s at -80.0dB; return: withdrawal, re-entry force 0.437, no recovery before next withdrawal
```

## Result

Improved: silence is now structural. The same four windows are still visible, but they no longer collapse into identical events. Short gaps that resume are marked as continuation. The opening gap is a reset. The terminal long silence is withdrawal.

Still wrong / risk: the labels are heuristic and should be treated as listener-state evidence, not final interpretation. `rupture` may need tuning on tracks with dramatic drop-to-hit returns. The current artifact proves the output lane and schema, not universal threshold correctness.

## Verification

```text
54 passed, 4 warnings  # tests/test_unit.py
34 passed, 3 warnings  # tests/test_regressions.py
88 passed, 9 warnings  # combined unit + regression run
```

Warnings are existing Python 3.13 `aifc`/`sunau` deprecations and librosa short-audio `n_fft` warnings.

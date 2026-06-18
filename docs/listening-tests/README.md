# Listening-Test Workflow

Use this workflow for any change that alters perception metrics, event selection, salience, ARC assembly, or prompt-facing interpretation.

The goal is not to prove that the new output is prettier. The goal is to prove that one concrete listening mismatch became more honest without hiding the remaining risk.

## Required Packet

Each metric slice should leave a short note under this directory or in a linked work packet with:

1. **Mismatch**: the track, moment, and specific perceptual failure.
2. **Baseline**: the current released output or prompt-facing evidence before the change.
3. **Change**: the metric, threshold, field, or prompt behavior being changed.
4. **Rerun**: the same track or track pair after the change, with command notes.
5. **Verdict**: what improved, what stayed wrong, and what new risk appeared.

For small fixes, a single Markdown note is enough. For broader metric work, keep the raw outputs in an ignored analysis/work packet and link the exact paths from the note.

## Template

```markdown
# <metric or behavior> listening test - <track>

## Mismatch

- Track:
- Source/audio path:
- Moment:
- Problem:

## Baseline

- Version/commit:
- Command:
- Relevant output:

## Change

- Version/commit:
- What changed:

## Rerun

- Command:
- Relevant output:

## Verdict

- Improved:
- Still wrong:
- New risk:
- Next action:
```

## Rules

- Test one concrete mismatch first. Aggregate "seems better" is not evidence.
- Use the same track before and after unless the claim is comparative.
- Keep raw metrics in the packet, but translate them in the verdict.
- Do not count prose fluency as metric success unless the underlying trace is also more honest.
- Demoting, renaming, or hiding a misleading field counts as success.

## Surface-Metric Notes

Surface evidence fields are cues, not claims. `roughness`, `band_pressure`, `punch`, band weights, and brightness tilt should point the reviewer toward what to hear: grain, abrasion, low/body weight, transient edge, air, or brightness. They should not become public prose by field name.

For surface changes, the verdict should answer:

- Did the change help identify the audible surface turn?
- Did it avoid overclaiming quiet transients as impact?
- Did it distinguish low/body weight from felt pressure?
- Did it preserve the difference between sustained tone and attack?

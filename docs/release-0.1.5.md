# Galdr 0.1.5 Release Plan

**Target:** Wednesday 2026-04-02
**Branch:** `feature/silence-aware-metrics` → `main`

**Status:** Branch merged, version bumped to 0.1.5, all commits on main. Ready to push Wednesday.

## What's in 0.1.5

- **Null signal guard** (`analyze.py`): degenerate/empty audio (RMS < 1e-6) exits early with `{null_signal: true}`, no files written, not indexed into catalog. Prevents pipeline mislabeling of test artifacts.
- **Active-frame silence stats** (`perceive.py`): additive fields in perception summary — `silence_pct`, `active_duration_sec`, `silent_duration_sec`, `mean_momentum_active`, `mean_pattern_lock_active`, `momentum_range_active`. Backward compatible: existing fields unchanged.
- **Silence-aware catalog ranking** (`catalog.py`): when `silence_pct >= 10%`, catalog uses active-frame momentum/pattern_lock for rankings. Prevents tracks that use silence intentionally (Helvegen, Feldman) from ranking low on momentum vs. tracks with no silence. `silence_pct` and `active_duration_sec` added as catalog dimensions.
- **New constants**: `NULL_SIGNAL_RMS_THRESHOLD`, `ACTIVE_FRAME_SILENCE_PCT_THRESHOLD`
- **8 new tests**, 53 total passing

## Release Checklist

- [x] Merge `feature/silence-aware-metrics` into `main` (cherry-picked, 2026-03-29)
- [x] Bump version: `pyproject.toml` → `0.1.5` (done 2026-03-29; `__init__.py` reads dynamically)
- [x] ARC-PROMPT template updated: Posture section added + rules tightened (ca443e9, ea4547b)
- [ ] Run full test suite: `pytest tests/ -q` — all green
- [ ] Run against full catalog (re-index 2–3 tracks to verify silence_pct in output)
- [ ] Build: `python3 -m build`
- [ ] Publish: `twine upload dist/*` (PyPI token from Vault: `secret/pypi`)
- [ ] Tag: `git tag v0.1.5`
- [ ] Push to GitLab: `git push origin main && git push origin v0.1.5`
- [ ] Push to GitHub: `git push github main && git push github v0.1.5`
- [ ] Update `uv.lock` if needed

## Notes

- PyPI token rotated 2026-03-29 (Vault version 3). If 403 on upload, check `vault kv get secret/pypi` — token should be `pypi-...` format.
- Next milestone: **0.2.0** — biphonation support (Huun-Huur-Tu). Requires structural changes to pitch detection (one-voice-one-pitch assumption). Not backward compatible on melody analysis output.

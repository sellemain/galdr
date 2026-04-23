# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.7] - 2026-04-22

### Added
- Public example listening doc for AURORA — `docs/aurora-runaway.md`

### Changed
- CI now installs and runs through `uv` with locked dependencies to match the documented repo workflow
- `galdr update-deps` now upgrades `yt-dlp` in the current Python environment instead of using a user-level fallback that could drift from the repo env
- README example links now point to two public listening docs instead of one

## [0.1.6] - 2026-04-03

### Added
- `galdr update-deps`: command to update yt-dlp and other dependencies in place
- Active-frame silence stats in perception summary: `silence_pct`, `active_duration_sec`, `silent_duration_sec`, `mean_momentum_active`, `mean_pattern_lock_active`, `momentum_range_active` — when silence exceeds 10%, catalog ranking uses active-frame stats instead of whole-track means
- Null signal guard: tracks with RMS below threshold exit early with `{null_signal: true}`, no files written, not indexed — prevents degenerate inputs from polluting catalog
- `pythonpath = ["src"]` in pytest config for correct src-layout test isolation

### Fixed
- Subprocess timeouts added throughout to prevent hung calls
- JS runtime path detected dynamically instead of hardcoded `/usr/bin/node`
- yt-dlp version floor tightened to 2026.1.0
- VTT filename detection made dynamic (was fragile on some yt-dlp versions)
- `pattern_break_counts`, frame semantics, and unified return shapes across DSP/IO separation

### Changed
- Repository canonical source moved from `sm/music-experience` to `sm/galdr` on GitLab

## [0.1.3] - 2026-03-27

### Added
- Security: input validation for YouTube URLs and slugs (`validate_youtube_url`, `validate_slug` in `fetch.py`)
- Security: SECURITY.md with private vulnerability reporting policy

### Changed
- CI: pin GitHub Actions to commit SHAs (supply chain hardening)
- Docs: `galdr-skill/` directory explained in README; agent integration section clarified

### Removed
- `requirements.lock` removed from version control (not used by CI; confusing for library consumers)

## [0.1.2] - 2026-03-22

### Added
- `galdr fetch`: auto-derive slug, artist, and title from YouTube metadata — `--name`/`--artist`/`--title` now optional when a URL is provided

### Fixed
- pytest runs fast by default (`-m 'not slow'` in `pyproject.toml`); slow functional tests still accessible via `pytest -m slow`
- `hz_to_cents` zero-input sentinel corrected from `0.0` to `math.inf`

## [0.1.1] - 2026-03-21

### Added
- `--version` / `-V` flag added to CLI

### Fixed
- Quote YouTube URLs in all shell examples (zsh glob expansion fix)
- `yt-dlp>=2024.1.0` added to `install_requires` (was missing; broke `galdr fetch` on clean installs)
- Documented `--no-download` and explicit `--artist`/`--title` fallback for when YouTube blocks audio

## [0.1.0] - 2026-03-20

### Added
- Initial release of galdr
- Perception stream: momentum, pattern_lock, breath, hp_balance metrics
- Audio analysis: tempo, beat regularity, energy arc, silence detection
- Harmony analysis: temperament alignment, HP balance, tonal center
- Melody analysis: pitch contour, melodic range, phrase structure
- Overtone analysis: harmonic series matching, spectral purity
- Catalog: persistent track comparison across sessions
- CLI: `galdr listen`, `galdr catalog`, `galdr compare`
- `galdr assemble` — build model prompts from analysis data with mode/template control
- `galdr fetch` — download audio and context via yt-dlp with optional auto-analysis
- `galdr frames` — extract and describe video frames at structural moments
- SKILL.md for AI agent integration

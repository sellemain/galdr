# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

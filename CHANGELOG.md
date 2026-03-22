# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

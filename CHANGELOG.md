# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Local stream listener-state metrics for body capture vs body comfort, groove comfort, accent phase drift, expectation debt, release force, section gravity, and surface density.
- Metric tension reporting for stable pulses pressured by competing metric grids, with conservative low-confidence handling for weak pulse evidence.
- Advisory perceptual salience guide in assembled prompts, ranking headline forces, supporting forces, technical underlayers, low-confidence metrics, and conflict notes without hiding raw evidence.
- Documentation for stream-first listener-state interpretation, the new local metrics, and the salience guide.

### Changed
- Shortened public metric field/display names (`attention`, `pattern`, `pulse`, `body`, `weight`, `pressure`, `texture`, `chroma_motion`, `pitch_grid`, `foreground_line`) and promoted `metric_vocabulary.py` into the canonical glossary layer for agent and human interpretation.
- Assembled prompts now include compact metric glossary lines with definitions, evidence, and caveats so downstream LLMs read short metric names in context.

## [0.2.2] - 2026-05-08

### Added
- Public listening examples for Dvořák's _Symphony No. 9_, fourth movement, and Wardruna/Aurora's _Helvegen_.
- README links for the new classical and ritual listening examples.

### Changed
- Polished the Helvegen and Dvořák example prose for public release, with source/performance context and less release-note framing.
- Bumped the bundled OpenClaw skill metadata to 0.2.2 for ClawHub/package consumers.

## [0.2.1] - 2026-05-07

### Added
- Python API helpers for listening, assembling, fetching, and DataFrame-oriented catalog exploration.
- Notebook and script examples for agent and application integration.
- Tempo profile validation with candidate tempos, confidence scoring, ambiguity flags, and windowed cross-checks.
- LUFS-based loudness and pressure/pressure analysis using `pyloudnorm`.
- Perception stream fields for loudness, LUFS pressure delta, pressure state, and loudness-aware silence.
- Perception-first roadmap and listening-test templates for future metric validation.
- GitHub issue templates for bug reports and usage questions.
- Public support/contact guidance in the README.

### Changed
- Pressure and assembled prose now describe pressure/build/release/sustain instead of raw loudness jargon.
- Package author email now uses the public galdr alias at `galdr@sellemain.com`.
- Security policy now reflects the current supported release line and fallback contact path.
- Agent skill packaging now uses `galdr-skill/galdr/SKILL.md` as the canonical distributable skill, with `docs/AGENT-CLI-REFERENCE.md` as the no-frontmatter CLI reference.

## [0.2.0] - 2026-04-29

### Added
- `galdr doctor` reports local YouTube download diagnostics, including the active Python executable, yt-dlp, helper packages, ffmpeg/ffprobe, JavaScript runtimes, and impersonation targets.

### Changed
- Agent skill install examples now use the current PyPI package instead of a stale pinned version.
- `src/galdr/SKILL.md` is now declared as package data for built distributions.
- YouTube downloads now invoke yt-dlp through galdr's current Python environment instead of a PATH binary.
- The yt-dlp dependency now installs the `default` and `curl-cffi` extras with a current stable version floor for better YouTube reliability.
- yt-dlp calls now retry once with remote EJS components from GitHub when YouTube challenge solving fails.
- `galdr update-deps` now upgrades `yt-dlp[default,curl-cffi]` in galdr's current Python environment and prints component versions after success.

### Fixed
- Null-signal detection now runs even when `galdr listen` skips the `report` module, preventing degenerate output from `--only perceive` and similar narrow runs.
- YouTube caption/subtitle failures no longer abort successful audio downloads.

## [0.1.9] - 2026-04-28

### Changed
- Source install docs and CI now use the no-lockfile library workflow (`uv sync`) instead of assuming a committed `uv.lock`.
- CI now runs the default non-slow test suite and lints tests as well as source.

### Fixed
- `galdr listen` now stops after null-signal detection instead of running the remaining modules and writing degenerate analysis files.
- `galdr frames --url` now reuses the strict YouTube URL allowlist and yt-dlp runtime setup from `fetch`.
- `galdr assemble` now errors on completely unknown slugs and reports missing structural analysis instead of emitting zero-valued metrics for context-only tracks.

## [0.1.8] - 2026-04-23

### Added
- Real `analyze` alias for `listen`, so `galdr analyze` works instead of failing as an invalid command

### Changed
- README and getting-started docs now make the second-by-second, stream-first workflow explicit for human and AI operators
- `listen --help` now states the broader local audio-format support instead of implying WAV-only input
- SKILL docs and packaged `galdr.skill` now make install provenance explicit and treat external model piping as optional, review-first behavior


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
- Active-frame silence stats in perception summary: `silence_pct`, `active_duration_sec`, `silent_duration_sec`, `mean_attention_active`, `mean_pattern_active`, `attention_range_active` — when silence exceeds 10%, catalog ranking uses active-frame stats instead of whole-track means
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
- Perception stream: attention, pattern, pressure, hp_balance metrics
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

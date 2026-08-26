# Run Galdr with Docker

The Galdr image is an optional runtime for people and agents that do not want to install Python, ffmpeg, and the scientific Python stack on the host. The normal contributor workflow remains `uv sync`.

## Workspace storage

Galdr keeps durable data in a bind-mounted workspace:

```text
work/
├── audio/       # supplied or downloaded source media
├── analysis/    # generated analysis artifacts
└── .galdr/      # cross-track catalog state
```

Runtime caches live at `/cache`. They are disposable and may be backed by a Docker volume for faster repeated runs. Never rely on the container writable layer for source media or analysis artifacts.

## Analyze a local file

From a directory containing `audio/song.mp3`:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" \
  ghcr.io/sellemain/galdr:latest \
  listen audio/song.mp3 --name song
```

The result is written to `analysis/song/`. A successful analysis includes `galdr-complete.json`. Its absence means the run stopped or failed before all requested modules completed; inspect or regenerate the directory rather than treating it as complete.

Each run writes into a hidden sibling staging directory and promotes it to `analysis/<slug>/` only after success. A cancelled container may leave a hidden `.slug.tmp-*` directory, but it cannot expose partial output at the canonical track path. A failed rerun leaves the previous completed track directory intact.

## Fetch and analyze

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" \
  -v galdr-cache:/cache \
  ghcr.io/sellemain/galdr:latest \
  fetch '<youtube-url>' --analyze
```

Network access is only needed for fetches and optional external context or Inner Ear providers. Local analysis is offline.

## Separate mounts for workers

```bash
docker run --rm \
  --user 1000:1000 \
  -v /srv/galdr/audio:/work/audio:ro \
  -v /srv/galdr/analysis:/work/analysis \
  -v galdr-catalog:/work/.galdr \
  -v galdr-cache:/cache \
  ghcr.io/sellemain/galdr:latest \
  listen audio/song.flac --name song
```

Use one writer per `analysis/<slug>` and catalog. Galdr does not currently coordinate concurrent writes to the same track or catalog file.

## Paths and permissions

The container sets these defaults:

- `GALDR_AUDIO_DIR=/work/audio`
- `GALDR_ANALYSIS_DIR=/work/analysis`
- `GALDR_CATALOG_DIR=/work/.galdr`
- `XDG_CACHE_HOME=/cache`

CLI flags override the defaults. On Linux, `--user "$(id -u):$(id -g)"` keeps generated files owned by the invoking user. The image itself runs as an unprivileged user when `--user` is omitted.

## Upgrades and diagnostics

Run `doctor` to inspect the image runtime:

```bash
docker run --rm ghcr.io/sellemain/galdr:latest doctor
```

Pull a newer image to update Galdr or yt-dlp. Do not use `galdr update-deps` as an image-upgrade mechanism; changes inside a disposable container are lost.

Release tags are immutable. Prefer a version tag or `sha-<commit>` tag in automation rather than `latest`.

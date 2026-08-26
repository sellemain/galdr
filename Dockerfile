FROM python:3.12-slim@sha256:a249c9f47e05708dd367f3fe8ada03cf347390fad66fb8b0518c0ef55ae3cb84

LABEL org.opencontainers.image.title="galdr" \
      org.opencontainers.image.description="Deterministic ears for AI agents" \
      org.opencontainers.image.source="https://github.com/sellemain/galdr" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp/galdr-home \
    XDG_CACHE_HOME=/cache \
    GALDR_AUDIO_DIR=/work/audio \
    GALDR_ANALYSIS_DIR=/work/analysis \
    GALDR_CATALOG_DIR=/work/.galdr

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates ffmpeg libsndfile1 nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

RUN mkdir -p /work /cache /tmp/galdr-home && chmod 1777 /work /cache /tmp/galdr-home
WORKDIR /work
USER 10001:10001
ENTRYPOINT ["galdr"]
CMD ["--help"]

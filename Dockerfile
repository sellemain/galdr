FROM python:3.12-slim@sha256:a249c9f47e05708dd367f3fe8ada03cf347390fad66fb8b0518c0ef55ae3cb84 AS builder

WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir uv==0.12.6 \
    && uv export --frozen --no-dev --no-emit-project --output-file requirements.lock \
    && python -m pip install --no-cache-dir --require-hashes --requirement requirements.lock \
    && python -m pip install --no-cache-dir --no-deps . \
    && python -m pip uninstall --yes uv

FROM python:3.12-slim@sha256:a249c9f47e05708dd367f3fe8ada03cf347390fad66fb8b0518c0ef55ae3cb84

ARG GALDR_VERSION=dev
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="galdr" \
      org.opencontainers.image.description="Deterministic ears for AI agents" \
      org.opencontainers.image.source="https://github.com/sellemain/galdr" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="$GALDR_VERSION" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.created="$BUILD_DATE"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp/galdr-home \
    XDG_CACHE_HOME=/cache \
    GALDR_AUDIO_DIR=/work/audio \
    GALDR_ANALYSIS_DIR=/work/analysis \
    GALDR_CATALOG_DIR=/work/.galdr

RUN apt-get update \
    && apt-get upgrade --yes \
    && apt-get install --yes --no-install-recommends ca-certificates ffmpeg libsndfile1 nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local
RUN python -m pip uninstall --yes pip

RUN mkdir -p /work /cache /tmp/galdr-home && chmod 1777 /work /cache /tmp/galdr-home
WORKDIR /work
USER 10001:10001
ENTRYPOINT ["galdr"]
CMD ["--help"]

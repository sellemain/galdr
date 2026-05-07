"""Tiny FastAPI integration example for galdr.

Install extras yourself, then run:

    pip install fastapi uvicorn python-multipart
    uvicorn examples.fastapi_app:app --reload

POST an audio file to /analyze. The example writes uploads to a temporary file,
runs galdr, and returns the analysis slug plus a compact report summary.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile

from galdr import listen

app = FastAPI(title="galdr example service")


@app.post("/analyze")
def analyze(file: UploadFile):
    suffix = Path(file.filename or "track.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        analysis = listen(tmp_path, name=Path(file.filename or "track").stem, analysis_dir="analysis")
        report = analysis.report or {}
        return {
            "slug": analysis.slug,
            "analysis_dir": str(analysis.path),
            "duration_seconds": report.get("duration_seconds"),
            "tempo_bpm": report.get("tempo_bpm"),
            "character": report.get("character"),
        }
    finally:
        tmp_path.unlink(missing_ok=True)

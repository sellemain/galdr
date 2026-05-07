"""Minimal galdr Python API example.

Run after installing galdr:

    python examples/python_api.py path/to/song.mp3
"""

from __future__ import annotations

import sys
from pathlib import Path

from galdr import listen


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python examples/python_api.py path/to/song.mp3")
        raise SystemExit(2)

    audio = Path(sys.argv[1])
    analysis = listen(audio, analysis_dir="analysis")
    prompt = analysis.to_prompt(template="arc", mode="full")

    print(f"Analyzed: {analysis.slug}")
    print(f"Files: {analysis.path}")
    print("\nPrompt preview:\n")
    print(prompt[:2000])


if __name__ == "__main__":
    main()

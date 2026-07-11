# Python API

galdr can be used as a normal Python library, not only as a CLI.

## Install shapes

```bash
pip install galdr
pip install "galdr[data]"      # adds pandas helpers
pip install "galdr[notebook]"  # adds pandas, Jupyter, Plotly
```

## Happy path

```python
from galdr import listen

analysis = listen("song.mp3")
print(analysis.report)

prompt = analysis.to_prompt(template="arc", mode="full")
```

`listen()` writes the same analysis files as `galdr listen` and returns an
`Analysis` object pointing at those files.

To use the ARC prompt-family lenses:

```python
prompt = analysis.to_prompt(template="arc-family", lens="default", mode="full")
prompt = analysis.to_prompt(template="arc-family", lens="dance", mode="blind")
```

## Load existing analysis

```python
from galdr import Analysis

analysis = Analysis.from_slug("helvegen", analysis_dir="analysis")
# or
analysis = Analysis.from_dir("analysis/helvegen")

print(analysis.report)
print(analysis.events)
print(analysis.to_prompt(mode="blind"))
```

## DataFrames

Install the data or notebook extra first:

```bash
pip install "galdr[data]"
```

Then:

```python
from galdr import Analysis, load_stream_df

analysis = Analysis.from_slug("helvegen")
frames = analysis.to_dataframes()
perception = frames["perception"]

# Or load one stream directly
perception = load_stream_df("analysis/helvegen/helvegen_stream.json")
```

## Raw prompt assembly

```python
from galdr import assemble

prompt = assemble("helvegen", analysis_dir="analysis", template="arc")
prompt = assemble("helvegen", analysis_dir="analysis", lens="structure")
prompt = assemble("helvegen", analysis_dir="analysis", lens="ritual")
```

For advanced callers that already have dicts:

```python
prompt = assemble(analysis_dict, context=context_dict, mode="blind")
```

`context_dict` may include structured song-specific evidence for Meaning and
other full-context prompts:

```python
context_dict = {
    "song_context": {
        "summary": "Known context directly tied to this track.",
        "claims": [
            {
                "claim": "The writer described the song as...",
                "source_type": "artist_interview",
                "source_url": "https://example.test/interview",
                "confidence": "high",
            }
        ],
        "lyric_references": [
            {
                "reference": "the named character",
                "meaning": "who or what it refers to, if sourced",
                "source_url": "https://example.test/annotation",
            }
        ],
        "source_notes": ["This is a later interview; treat as retrospective."],
    }
}
```

Keep durable lyric/style policy in the prompt templates. `song_context` is for
evidence, provenance, and source-specific caveats, not per-track safety rules.

## Web app shape

See `examples/python_api.py` and `examples/notebooks/` for runnable API examples.

## Notebooks

Starter notebooks live in `examples/notebooks/`:

- `first-listen.ipynb`
- `catalog-exploration.ipynb`

They are intentionally small. They show the shape without pretending to be a
full product. Catalog exploration is local index tooling, not the main ARC product path.

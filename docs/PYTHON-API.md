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
perception = load_stream_df("analysis/helvegen/helvegen_perception_stream.json")
```

## Raw prompt assembly

```python
from galdr import assemble

prompt = assemble("helvegen", analysis_dir="analysis", template="arc")
```

For advanced callers that already have dicts:

```python
prompt = assemble(analysis_dict, context=context_dict, mode="blind")
```

## Web app shape

See `examples/fastapi_app.py` for a minimal upload-and-analyze FastAPI route.

## Notebooks

Starter notebooks live in `examples/notebooks/`:

- `first-listen.ipynb`
- `compare-two-tracks.ipynb`
- `catalog-exploration.ipynb`

They are intentionally small. They show the shape without pretending to be a
full product.

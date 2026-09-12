# OCR + Ollama Pipeline

One approach for turning a flyer photo into `mittendrin.in – Brandenburg`
`AdapterData` JSON, fully local.

**See [FAQ.md](FAQ.md) for the design rationale and answers to common
"why does it do X?" questions.**

## Pipeline

```
image  →  EasyOCR (words + boxes)  →  column-aware block grouping
       →  local Ollama LLM (structured JSON, schema-constrained)
       →  deterministic safety scan (lexicons + regex + Luhn)
       →  per-offer AdapterData JSON files
```

Everything runs on your machine — no data leaves.

## What's here

```
notebooks/flyer_extraction.ipynb   ← walkthrough, one cell per stage, plain-English commentary
src/flyer_extract/                 ← the pipeline package
    io.py         image load + EXIF fix
    ocr.py        EasyOCR wrapper
    layout.py     DBSCAN vertical clustering + column-gap split
    viz.py        draw boxes on the image
    llm.py        Ollama call + one-shot repair retry
    safety.py     deterministic PII / profanity / hate / scam scanner
    schema.py     Pydantic models (target AdapterData + LLM sub-schemas)
    pipeline.py   orchestration + directory-per-poster file layout
lexicons/                          ← word lists the safety scan uses
scripts/build_notebook.py          ← notebook is generated, not hand-edited
tests/                             ← 25 unit tests (safety, schema, slugs)
data/inputs/                       ← the four demo flyers
data/outputs/                      ← executed output per poster (one dir each)
data/samples/json_target_format.json   ← the target schema reference
pyproject.toml
```

## Quickstart

```bash
# 1. Install Ollama (https://ollama.com) and pull a model
ollama pull qwen2.5:7b

# 2. Python deps
py -3.13 -m venv .venv
.venv/Scripts/pip install -e ".[dev]"

# 3. Run the notebook
.venv/Scripts/jupyter lab notebooks/flyer_extraction.ipynb
```

Or run the pipeline directly:

```python
from flyer_extract import pipeline
adapter_data, debug = pipeline.run("data/inputs/<some-flyer>.jpg",
                                   model="qwen2.5:7b",
                                   langs=("de", "en"),
                                   output_dir="data/outputs")
```

Tests need neither Ollama nor an OCR model:

```bash
.venv/Scripts/pytest -q
```

## Output layout — one directory per poster

```
data/outputs/<poster-slug>/
    _all.json           ← aggregate: every offer on the poster in one AdapterData
    _debug.json         ← OCR words, blocks, safety flags, timings
    <offer-slug>.json   ← one AdapterData per offer — the per-item deliverable
```

Poster slug comes from the filename (camera-ID suffixes like `_PXL_20240913_…`
are stripped). Offer slug comes from the item title. German umlauts become
`ae/oe/ue/ss` before slugifying.

## Design notes

**Multi-item per poster.** One flyer usually advertises several offers (chorus,
dance class, counseling). The LLM returns `{"items": [ … ]}` and each item
becomes its own file.

**Column-aware layout.** Simple vertical clustering fuses left+right columns
of a two-column poster into one text block. `layout.py` also splits within a
y-band whenever the horizontal gap between adjacent words exceeds 3× median
line height.

**Schema-constrained LLM.** The Pydantic model is the single source of truth —
its JSON Schema is passed to Ollama as `format=<schema>`, so the model's
output validates on the first try in almost every run. A one-shot repair
retry handles the rare validation error.

**Deterministic safety.** The scanner labels but never blocks:

- **PII** — emails, phone numbers, Luhn-valid credit-card numbers
- **Profanity / hate / violence / self-harm** — word-boundary lexicon matches
  (EN + DE), with leet-speak folded (`sh1t` → `shit`)
- **Scam heuristics** — urgency phrases, suspicious TLDs

`human_review_required = True` when any hard flag fires or two+ soft flags
stack. Humans are the actual safety net.

## What works well, what's rough

- 8/8 offers extracted on the Heiligensee poster; 5 on the Netzwerk-Gemeinsamkeit
  poster; 6 on the Potsdam network poster; 2 on the TPF poster.
- OCR occasionally drops umlauts (`Kreativtreff am` → `Kreativtreffam`) —
  visible in some offer slugs.
- Details (hours/description) sometimes come out sparser on posters with dense
  interleaved layouts. Prompt tuning trades detail for accuracy.
- CSAM lexicon is intentionally empty pending a governed source; the framework
  is in place.

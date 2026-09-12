# FAQ

Answers to the questions that come up when reading the notebook or the code.

---

## Big picture

### What does this pipeline actually do?

Takes an image of a flyer or poster and turns it into structured JSON in the
`mittendrin.in – Brandenburg` `AdapterData` shape. One image in → one
directory of JSON files out, with one file per offer advertised on the poster.

### Why local? Why not just call GPT-4 or Gemini?

Three reasons:
1. **Privacy** — flyer photos may include phone numbers, home addresses, or
   photos of people. Nothing leaves the machine.
2. **Cost** — a batch of 500 flyers is free to re-run when you tweak the
   prompt.
3. **Reproducibility** — Ollama pins a specific model weight; a hosted API can
   silently update the model under you.

Trade-off: a 7B local model is weaker than GPT-4. We mitigate with a strict
JSON Schema, a two-column-aware layout stage, and a repair retry.

### Which model should I use?

Default is `qwen2.5:7b`. It gave the best German extraction quality in
testing with acceptable latency (~5-15 s per poster on CPU).
Alternatives:
- `llama3.1:8b` — comparable quality, sometimes stricter on JSON
- `qwen2.5:14b` — better but slow on CPU-only machines

Swap via the `MODEL` variable in the notebook or the `model=` argument to
`pipeline.run(...)`.

---

## Pipeline stages

### Why OCR *and* an LLM? Can't the LLM read the image directly?

Vision-language models (LLaVA, Qwen-VL) can, but at 7B they're much weaker at
reading small German text than a dedicated OCR model. We use EasyOCR for
reading + word-level bounding boxes, then hand the text to a text-only LLM.
Cleaner separation, better results.

### What is EasyOCR doing?

It scans the image and returns, for every piece of text it can see:
- **the text** it read
- a **confidence** score (0…1)
- a **bounding box** (four corners) in pixel coordinates

We keep the raw output — it goes into `_debug.json` for auditing.

### Why do we group words into "blocks" after OCR?

Feeding the LLM a raw dump of 80 tiny word fragments loses spatial structure —
it can't tell that "Chor Cantamus" is a title and the "09:45 Uhr" below is
that chorus's time slot. Grouping words that share a visual line gives the
LLM paragraph-like inputs it can reason about.

### How does the block grouping work?

Two stages in `layout.py`:

1. **Vertical clustering (DBSCAN).** Every word's y-center is a point. Words
   with y-centers within ~0.9× the median line-height cluster into the same
   horizontal band. So all words on one line of the poster end up in one
   cluster.
2. **Column-gap split.** Within each cluster, we sort words left-to-right and
   split whenever the horizontal gap between adjacent words exceeds 3× median
   line-height. This is the key fix for two-column posters — otherwise the
   left column's title and the right column's title get fused into one string.

The reason clustering is *vertical only* first is that horizontal groupings
depend on knowing where lines are, and lines are defined vertically.

### Why not use a fancy layout model (LayoutLMv3, DocLayNet)?

They're bigger, slower, and need finetuning on flyer layouts to beat the
simple heuristic. DBSCAN + a gap threshold works well enough for the domain
(A4 posters with 1–3 columns).

---

## The LLM stage

### How does the LLM know what fields to fill?

We pass the JSON Schema of `LLMPosterExtraction` to Ollama via the
`format=<schema>` parameter (Ollama v0.4+). The model's output is
constrained to match the schema at token-sampling time, so it can't return
something like `{"titel": …}` when the schema expects `title`.

### What does the system prompt tell the model?

Key instructions (all in German, matching the flyer language):
- Return a **list** of items — one per distinct offer.
- Always fill `title`.
- Fill `hours_de` whenever a time hint sits near a title.
- Fill other fields only when the flyer text supports them.
- Don't hallucinate contact info.
- Don't treat the venue/footer as its own item.
- **Don't copy names from the example in the prompt.**

That last point matters because early runs showed the model literally copying
"Chor Cantamus / Anna Weber / Donnerstags 18 Uhr" from the illustrative
example when the input poster was ambiguous.

### What is the "repair retry"?

If the model's first response fails Pydantic validation (e.g., a type
mismatch, a missing bracket), we send a second message containing the
validation errors and ask for a corrected response. One retry only. In
testing, first-try validation succeeded on ~95% of runs; the retry mops up
the rest.

### Why is the temperature 0.1 (not 0)?

Pure 0 makes Ollama deterministic but occasionally gets stuck in
repetition loops. 0.1 avoids the loops while keeping runs near-reproducible.

### Why do some outputs come out sparser than others?

Two causes:
1. **OCR quality.** A blurry poster or an unusual font means the text the LLM
   sees is fragmented, and it hedges by filling fewer fields.
2. **Prompt tension.** Our prompt trades detail for accuracy — we'd rather
   the model leave a field blank than hallucinate.

---

## The safety stage

### Is this an AI safety filter?

No. It's a **deterministic** rules-based scanner: lexicons + regex + Luhn.
It has zero AI in it. That's the point — a rules-based floor is auditable and
predictable in a way an LLM-based safety filter never is.

### What does it look for?

- **PII** — email addresses, phone numbers, Luhn-valid credit-card numbers
- **Profanity / hate / violence / self-harm** — word-boundary matches against
  seed lexicons in English and German
- **Scam heuristics** — urgency phrases ("act now"), suspicious TLDs

### What are "soft" and "hard" flags?

- **soft** — one is fine; two or more stacked triggers human review.
  Example: a single email address (contact info is expected on a flyer).
- **hard** — one triggers human review immediately. Example: a Luhn-valid
  credit card number, or a hate-speech term.

`human_review_required` becomes `True` when any hard flag fires OR when
soft flags stack. The pipeline **never blocks** — it labels and forwards.
Humans are the safety net.

### Why is `lexicons/csam_terms.txt` empty?

CSAM lexicons need a governed source (e.g., IWF, INHOPE). We wired the
mechanism but intentionally shipped no terms — using a made-up list gives a
false sense of coverage. Populate from a real source in production.

### What is leet-speak folding?

Someone writing `sh1t` or `@ss` should still trigger the profanity lexicon.
Before matching, we translate common leet substitutions (`1`→`i`, `4`→`a`,
`@`→`a`, etc.) so `sh1t` normalizes to `shit` and hits the lexicon.

Length is preserved so match spans still point at the right characters in
the original text.

---

## Output files

### Why one directory per poster?

A single poster can advertise 5–8 offers. Flat files (`<poster>.json`,
`<poster>-1.json`, `<poster>-2.json`) get impossible to scan. Instead:

```
data/outputs/<poster-slug>/
    _all.json                      ← every offer bundled into one AdapterData
    _debug.json                    ← OCR words, blocks, safety flags, timings
    <offer-slug>.json              ← one AdapterData per offer
```

Reviewers can drop-in-replace an individual offer JSON without touching the
others.

### How are the slug filenames generated?

- **Poster slug** — from the image filename, with camera-ID suffixes stripped
  (`_PXL_20240913_114824546`, `_1000281131`, etc.). German umlauts become
  `ae/oe/ue/ss`. Then everything non-alphanumeric becomes a hyphen.
- **Offer slug** — same transform applied to the offer's `title`. Duplicates
  get `-2`, `-3` appended.

Example: `Foto_Netzwerk Älter werden in Potsdam 1_PXL_20260909_174935695.jpg`
→ poster slug `netzwerk-aelter-werden-in-potsdam` → one file per offer
under that directory.

### Why is `_all.json` prefixed with an underscore?

So it sorts before every offer file. Reviewers open the directory, the
aggregate view is at the top.

### What's in the debug JSON?

Everything the pipeline saw: OCR words with confidences, grouped blocks,
raw LLM response, all safety flags, and per-stage timings. Kept alongside
`_all.json` so an auditor can trace any surprising output back to the OCR
or LLM step.

---

## Development & testing

### How do the tests work without Ollama or an OCR model?

The 25 unit tests only cover the deterministic layers: schema validation,
safety scanning, and slug generation. OCR and LLM calls need real models and
aren't part of the unit test surface — the notebook is the integration test.

### Why is the notebook auto-generated from a script?

`scripts/build_notebook.py` builds the notebook cell-by-cell with `nbformat`.
Two reasons:
1. **One source of truth for narrative.** All the plain-English commentary
   between cells lives in one auditable Python file, not scattered across a
   JSON blob.
2. **Diff-friendly.** Reviewers can see prose changes cleanly instead of
   diffing notebook cell JSON.

To modify the notebook, edit the script and re-run:

```bash
.venv/Scripts/python scripts/build_notebook.py
```

Then re-execute:

```bash
.venv/Scripts/jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=900 notebooks/flyer_extraction.ipynb
```

### Why is the notebook file 60 MB?

Every cell's outputs are embedded — including the annotated images (OCR
boxes drawn on the flyer). Viewers without a running kernel still see all
the results. Trade-off: it's a big file to `git clone`.

### How do I try a different LLM without re-running OCR?

`scripts/replay_llm.py` reads cached OCR blocks out of the existing
`_debug.json` files and re-runs only the LLM step:

```bash
.venv/Scripts/python scripts/replay_llm.py qwen2.5:14b
```

Fast A/B without paying for OCR every time.

---

## Known rough edges

- OCR occasionally drops umlauts (`Kreativtreff am` → `Kreativtreffam`) —
  visible in some offer slugs.
- Local 7B models don't always populate every detail field; details win/loss
  varies between runs because of the small non-zero temperature.
- Multi-column posters with tightly interleaved rows can still confuse the
  layout stage — the fix helps but doesn't cover every case.
- The CSAM lexicon is intentionally empty pending a governed source.

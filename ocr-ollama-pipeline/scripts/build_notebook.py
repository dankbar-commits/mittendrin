"""Build notebooks/flyer_extraction.ipynb programmatically.

Each code cell is preceded by a plain-English markdown cell so a non-engineer
reader can follow along. Kept as a script (not the notebook itself) so the
narrative lives in one auditable place.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

NB = nbf.v4.new_notebook()
NB["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}


def md(text: str) -> None:
    NB["cells"].append(nbf.v4.new_markdown_cell(text.strip("\n")))


def code(src: str) -> None:
    NB["cells"].append(nbf.v4.new_code_cell(src.strip("\n")))


# ── Intro ────────────────────────────────────────────────────
md("""
# Flyer → OCR → Local-LLM Entity Extraction → JSON

**What this notebook does, in plain terms:**

1. **Load an image** — a flyer or poster from `data/inputs/`.
2. **Find text with bounding boxes** — the *OCR* (Optical Character Recognition) step draws
   rectangles around every piece of text it can see and reads what's inside.
3. **Group text into blocks** — nearby lines that belong together (a title, an address, a
   time slot) get bundled so the AI sees structured groups instead of a soup of words.
4. **Ask a local AI model for the meaningful bits** — a *local* Ollama model (running on this
   machine, nothing sent to the cloud) is given the text and asked to fill in a form:
   *title, short description, address, phone, email, opening hours, …*
5. **Run a deterministic safety check** — a rules-based scanner looks for PII (emails,
   phones, credit-card numbers), profanity, hate/violence terms, and scam patterns. It
   never blocks — it *labels*, and marks the item for **human review** when anything worrying
   appears.
6. **Write a JSON file** matching the `mittendrin.in – Brandenburg` target format
   (`AdapterData` with one `Item` inside).

**Two files land in `data/outputs/` per image:**
- `<name>.json` — the deliverable, in the target schema.
- `<name>.debug.json` — everything the pipeline saw (OCR words, blocks, safety flags, timings).

**Terms you'll see:**
- *OCR* = reading text out of an image.
- *Bounding box* = the rectangle around a piece of detected text.
- *Entity* = a meaningful piece of information (a date, a phone number, an address, …).
- *PII* = Personally Identifiable Information (email, phone, ID number).
""")

# ── Setup ────────────────────────────────────────────────────
md("""
## 1. Setup — imports and health checks

We import the pipeline pieces and check that **Ollama** (the local AI runtime) is reachable and
which models it has ready. If this cell prints an error, start Ollama Desktop or run
`ollama serve` in a terminal, then re-run this cell.
""")
code("""
import json
from pathlib import Path

import ollama
from IPython.display import display, JSON, Markdown, Image as IPyImage

from flyer_extract import io, ocr, layout, viz, llm, safety, pipeline
from flyer_extract.schema import AdapterData, DebugResult

print("Ollama version:", ollama.__version__ if hasattr(ollama, "__version__") else "unknown")
models = ollama.list()
model_names = [m.get("model") or m.get("name") for m in models.get("models", [])]
print("Installed Ollama models:")
for n in model_names:
    print(" -", n)
""")

# ── Config ───────────────────────────────────────────────────
md("""
## 2. Configuration — which image, which model, which languages

**Knobs you can change:**
- `IMAGE_PATH` — path to one flyer. Section 9 later loops over *all* flyers in `data/inputs/`.
- `MODEL` — the local LLM used for extraction. `llama3.1:8b` is the default; try
  `qwen2.5:7b` or `qwen2.5:14b` for a comparison.
- `LANGS` — OCR language hint. The flyers are German-first, so `("de", "en")`.
""")
code("""
INPUT_DIR = Path("../data/inputs")
OUTPUT_DIR = Path("../data/outputs")

IMAGE_PATH = sorted(p for p in INPUT_DIR.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})[0]
MODEL = "qwen2.5:7b"
LANGS = ("de", "en")

print("Will process:", IMAGE_PATH.name)
print("Model:", MODEL)
print("OCR languages:", LANGS)
""")

# ── Load image ───────────────────────────────────────────────
md("""
## 3. Load and preview the image

Loads the file, applies EXIF orientation (phone photos are often rotated), converts to RGB,
and downscales if it's larger than 4096 px on the long edge (keeps OCR fast).
""")
code("""
image = io.load_image(IMAGE_PATH)
print("Image size:", image.size)
image
""")

# ── OCR ──────────────────────────────────────────────────────
md("""
## 4. Run OCR — find every piece of text and its bounding box

EasyOCR downloads its model weights the first time (~ a few hundred MB) — subsequent runs are
cached. Each detected piece of text gets:

- **text** — what was read,
- **confidence** — how sure the model is (0…1),
- **bounding box** — the rectangle in the image.

Look at the confidence values: anything below ~0.4 is often a misread and worth eyeballing.
""")
code("""
words = ocr.run(image, langs=LANGS)
print(f"Detected {len(words)} text spans. Top 10 by confidence:")
for w in sorted(words, key=lambda w: -w.confidence)[:10]:
    print(f"  [{w.confidence:.2f}] {w.text!r}")
""")

# ── Annotated preview ────────────────────────────────────────
md("""
## 5. Show the OCR boxes on the image

Green rectangles = where the OCR thinks text is. Use this to sanity-check coverage: if a big
chunk of the flyer has no box on it, OCR missed something and downstream extraction will be
weaker for that region.
""")
code("""
annotated = viz.draw_boxes(image, words)
annotated
""")

# ── Blocks ───────────────────────────────────────────────────
md("""
## 6. Group nearby text into reading-order blocks

Feeding the AI one giant blob of text loses structure. We cluster words vertically (using a
simple density-based clustering keyed off the median line height) and get **blocks**
(paragraph-like groups). Each block gets a colored outline; the AI later sees the text
labeled with block numbers like `[Block 0] …`.
""")
code("""
blocks = layout.group_blocks(words)
print(f"Grouped {len(words)} words into {len(blocks)} blocks.")
for b in blocks[:12]:
    preview = b.text[:80].replace("\\n", " ")
    print(f"  Block {b.id:2d}: {preview}{'…' if len(b.text) > 80 else ''}")

annotated_blocks = viz.draw_boxes(image, words, blocks=blocks)
annotated_blocks
""")

# ── LLM extraction ───────────────────────────────────────────
md("""
## 7. Ask the local AI to fill in the target form — for every offer on the poster

A single poster often advertises **several offers** (a chorus, a dance class, a counseling
service). The model is instructed to return a *list* of items — one per distinct offer.

We hand the block-labeled text to Ollama along with the **JSON schema** of the wrapper
`{"items": [ … ]}`. The model is told (in German) to fill only fields that actually appear in
the flyer for each offer and to leave everything else `null`. The response is validated against
our Pydantic model; if it doesn't parse, we retry once with the validation errors attached as
a repair prompt.

If this is slow the first time, the model is warming up in Ollama's memory — subsequent images
will be much faster.
""")
code("""
blocks_text = layout.blocks_to_text(blocks)
poster, timing = llm.extract_items(blocks_text, model=MODEL)
print(f"LLM latency: {timing['llm_ms']:.0f} ms (retried={timing['retried']}, {len(poster.items)} offer(s) extracted)")
display(JSON(poster.model_dump(exclude_none=True)))
""")

# ── Safety ───────────────────────────────────────────────────
md("""
## 8. Deterministic safety scan

A rules-based scanner runs over **both** the raw OCR text and the LLM's output. It looks for:

- **PII** — emails, phone numbers, Luhn-valid credit-card numbers.
- **Profanity / hate / violence / self-harm** — word-boundary lexicon matches (EN + DE),
  with leet-speak folded (`sh1t` → `shit`).
- **Scam heuristics** — urgency phrases, suspicious TLDs.

Every flag records the *exact matched span* and a *rule ID* so a human reviewer can audit
quickly.

**Soft vs hard flags:**
- **soft** — a single one is fine; two or more stacked → human review.
- **hard** — a single one → human review immediately (Luhn-valid card, hate/CSAM terms).

`human_review_required` is the load-bearing output. The pipeline **never blocks** — it labels
and forwards. Humans are the actual safety net.
""")
code("""
ocr_flags = safety.scan(blocks_text, source="ocr")
llm_flags = safety.scan(poster.model_dump_json(), source="llm")
all_flags = ocr_flags + llm_flags
review_required = safety.evaluate(all_flags)

print(f"Safety flags found: {len(all_flags)}   (ocr={len(ocr_flags)}, llm={len(llm_flags)})")
print(f"→ human_review_required = {review_required}")
print()
for f in all_flags[:20]:
    print(f"  [{f.severity}/{f.category}/{f.source}] {f.rule_id}: '{f.matched_span}'")
""")

# ── Assemble & save ──────────────────────────────────────────
md("""
## 9. Assemble the target JSON (all offers) and save it

Runs the whole pipeline via `pipeline.run(...)` (same steps as above, but with error isolation
and file writing). The output `AdapterData.itemsRecord` now holds **one entry per extracted
offer** — the key is a slug derived from each offer's title.

**Output layout — one directory per poster:**
```
data/outputs/<poster-slug>/
    _all.json          ← the aggregate: all offers on this poster in one AdapterData
    _debug.json        ← OCR words, blocks, safety flags, timings
    <offer-slug>.json  ← one AdapterData per offer — the per-item deliverable
```

The poster slug is derived from the image filename (camera-ID suffixes like `_PXL_20260909…`
are stripped), and each offer slug comes from that offer's title. German umlauts become
`ae/oe/ue/ss` before slugifying.

The `editingNote` field on each Item carries the poster-level safety flags in human-readable
form so downstream reviewers see them without opening the debug file.
""")
code("""
adapter_data, debug = pipeline.run(IMAGE_PATH, model=MODEL, langs=LANGS, output_dir=OUTPUT_DIR)
from flyer_extract.pipeline import _poster_slug
poster_dir = OUTPUT_DIR / _poster_slug(IMAGE_PATH.stem)
print(f"Wrote {len(adapter_data.itemsRecord)} offer(s) into {poster_dir}/")
for f in sorted(poster_dir.iterdir()):
    print(f"  {f.name}")
print()
print(f"Total pipeline time: {debug.timings.total_ms:.0f} ms")
print(f"  ocr:    {debug.timings.ocr_ms:.0f} ms")
print(f"  layout: {debug.timings.layout_ms:.0f} ms")
print(f"  llm:    {debug.timings.llm_ms:.0f} ms")
print(f"  safety: {debug.timings.safety_ms:.0f} ms")
display(JSON(adapter_data.model_dump(exclude_none=True)))
""")

# ── Batch loop ───────────────────────────────────────────────
md("""
## 10. Try all the flyers in `data/inputs/`

Runs the full pipeline over every image in the input folder and prints a compact summary
(number of offers extracted, per-offer titles, review flag). Each image gets its own
`<poster-slug>/` directory with `_all.json`, `_debug.json`, and one file per offer.
""")
code("""
from flyer_extract.pipeline import _poster_slug

for path in sorted(p for p in INPUT_DIR.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}):
    ad, dbg = pipeline.run(path, model=MODEL, langs=LANGS, output_dir=OUTPUT_DIR)
    review_marker = "!! REVIEW" if dbg.human_review_required else "   ok    "
    p_slug = _poster_slug(path.stem)
    print(f"{review_marker}  {path.name}")
    print(f"           -> {OUTPUT_DIR}/{p_slug}/  ({len(ad.itemsRecord)} offer(s), "
          f"{len(dbg.safety_flags)} flag(s), {int(dbg.timings.total_ms)} ms)")
    for key, item in ad.itemsRecord.items():
        print(f"           - {key}.json  |  {item.title}")
        if item.tags:
            print(f"               tags: {', '.join(item.tags)}")
        if item.phone or item.email:
            print(f"               phone: {item.phone}   email: {item.email}")
    print()
""")


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "notebooks" / "flyer_extraction.ipynb"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        nbf.write(NB, f)
    print(f"Wrote {out} with {len(NB['cells'])} cells")


if __name__ == "__main__":
    main()

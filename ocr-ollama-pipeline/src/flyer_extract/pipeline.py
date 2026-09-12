"""End-to-end orchestration.

A single poster can advertise MULTIPLE offers. The pipeline runs the LLM once
per image and materializes ONE Item per offer. All Items land in the same
`AdapterData.itemsRecord` under unique slugs.

Failure-isolated: an error in any stage is captured into DebugResult.errors,
forces `human_review_required = True`, but the pipeline still assembles what
it can and writes both output files.

Emits two files per image:
- `data/outputs/<stem>.json`        — target AdapterData (all extracted items)
- `data/outputs/<stem>.debug.json`  — full internal DebugResult
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from . import io, layout, llm, ocr, safety
from .schema import (
    Adapter, AdapterData, DebugResult, Item, LLMItemExtraction,
    LLMPosterExtraction, PipelineError,
)

ADAPTER_NAME = "flyer-extract"
ADAPTER_VERSION = "0.1.0"

# German umlaut transliteration (applied before unidecode so we get 'ae' not 'a').
_DE_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
})

# Camera-ID / suffix patterns to strip from an image stem before slugifying.
_CAMERA_SUFFIX = re.compile(
    r"_(?:PXL|IMG|DSC|DSCF|MVIMG|VID)_[\d_]+$"
    r"|_\d{7,}$"                # trailing all-digit token like _1000281131
    r"|\s+\d{1,2}$",            # trailing single/two-digit ordinal like ' 1'
    re.IGNORECASE,
)
_FOTO_PREFIX = re.compile(r"^(?:Foto|Bild|Photo|Scan)_", re.IGNORECASE)


def _slug(text: str, fallback: str) -> str:
    """Slugify: German umlauts → ae/oe/ue/ss, then unidecode → lowercase → hyphen-join."""
    from unidecode import unidecode
    s = (text or "").translate(_DE_MAP)
    s = unidecode(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or fallback


def _poster_slug(image_stem: str) -> str:
    """Turn a raw filename stem into a clean poster identifier.

    Strips `Foto_` / `Bild_` prefixes and trailing camera IDs / ordinals so
    'Foto_Netzwerk Älter werden in Potsdam 1_PXL_20260909_174935695' becomes
    'netzwerk-aelter-werden-in-potsdam'.
    """
    s = _FOTO_PREFIX.sub("", image_stem)
    # Apply suffix stripping repeatedly (e.g. ' 1' then '_PXL_...')
    for _ in range(3):
        new = _CAMERA_SUFFIX.sub("", s)
        if new == s:
            break
        s = new
    return _slug(s, fallback="poster")


def _to_multilang(value: str | None) -> dict[str, str] | None:
    if value is None or not value.strip():
        return None
    return {"de": value.strip()}


def _materialize_item(
    ext: LLMItemExtraction,
    image_path: str,
    editing_note: str | None,
    index: int,
) -> Item:
    """Turn one LLM extraction into the target Item shape."""
    fallback_title = f"{Path(image_path).stem} (Angebot {index + 1})"
    return Item(
        title=(ext.title or fallback_title).strip(),
        state="suggestion",
        brief=_to_multilang(ext.brief_de) or {"de": ""},
        description=_to_multilang(ext.description_de) or {"de": ""},
        tags=[t.strip().lower() for t in (ext.tags or []) if t.strip()][:8],
        primaryTopic=ext.primaryTopic,
        location=ext.location,
        address=ext.address,
        zip=ext.zip,
        city=ext.city,
        responsibleInstitution=ext.responsibleInstitution,
        sponsors=ext.sponsors,
        website=ext.website,
        email=ext.email,
        facebook=ext.facebook,
        whatsapp=ext.whatsapp,
        contact=ext.contact,
        phone=ext.phone,
        mobile=ext.mobile,
        hours=_to_multilang(ext.hours_de),
        accessibility=_to_multilang(ext.accessibility_de),
        charge=_to_multilang(ext.charge_de),
        venue=_to_multilang(ext.venue_de),
        editingNote=editing_note,
    )


def _safety_note(flags, human_review_required: bool, errors) -> str | None:
    parts: list[str] = []
    if human_review_required:
        parts.append("HUMAN REVIEW REQUIRED")
    for e in errors:
        parts.append(f"[error/{e.stage}] {e.message}")
    for f in flags:
        parts.append(f"[flag/{f.severity}/{f.category}/{f.source}] {f.rule_id}: '{f.matched_span}'")
    return "\n".join(parts) if parts else None


def _dedupe_slugs(items: list[Item], poster_slug: str) -> dict[str, Item]:
    """Slugify item titles into itemsRecord keys, appending -2, -3 on collisions."""
    record: dict[str, Item] = {}
    for i, item in enumerate(items):
        base = _slug(item.title, fallback=f"{poster_slug}-item-{i + 1}")
        key = base
        n = 2
        while key in record:
            key = f"{base}-{n}"
            n += 1
        record[key] = item
    return record


def run(
    image_path: str | Path,
    model: str = "qwen2.5:7b",
    langs: tuple[str, ...] = ("de", "en"),
    output_dir: str | Path = "data/outputs",
) -> tuple[AdapterData, DebugResult]:
    image_path = str(image_path)
    debug = DebugResult(image_path=image_path, model_name=model)
    total_start = time.perf_counter()

    # ── IO ────────────────────────────────────────────────────
    try:
        image = io.load_image(image_path)
    except Exception as e:
        debug.errors.append(PipelineError(stage="io", message=str(e)))
        debug.human_review_required = True
        return _finalize(debug, output_dir)

    # ── OCR ───────────────────────────────────────────────────
    t = time.perf_counter()
    try:
        debug.ocr = ocr.run(image, langs=langs)
    except Exception as e:
        debug.errors.append(PipelineError(stage="ocr", message=str(e)))
    debug.timings.ocr_ms = (time.perf_counter() - t) * 1000

    # ── Layout ────────────────────────────────────────────────
    t = time.perf_counter()
    try:
        debug.blocks = layout.group_blocks(debug.ocr)
    except Exception as e:
        debug.errors.append(PipelineError(stage="layout", message=str(e)))
    debug.timings.layout_ms = (time.perf_counter() - t) * 1000

    blocks_text = layout.blocks_to_text(debug.blocks)

    # ── LLM extraction (multi-item) ───────────────────────────
    t = time.perf_counter()
    poster = LLMPosterExtraction()
    try:
        poster, timing = llm.extract_items(blocks_text, model=model)
        debug.llm_raw = poster
        debug.timings.llm_ms = timing["llm_ms"]
    except Exception as e:
        debug.errors.append(PipelineError(stage="llm", message=str(e)))
        debug.timings.llm_ms = (time.perf_counter() - t) * 1000

    # ── Safety ────────────────────────────────────────────────
    t = time.perf_counter()
    try:
        ocr_flags = safety.scan(blocks_text, source="ocr")
        llm_flags = safety.scan(poster.model_dump_json(), source="llm")
        debug.safety_flags = ocr_flags + llm_flags
        debug.human_review_required = safety.evaluate(debug.safety_flags)
    except Exception as e:
        debug.errors.append(PipelineError(stage="safety", message=str(e)))
    debug.timings.safety_ms = (time.perf_counter() - t) * 1000

    if debug.errors:
        debug.human_review_required = True

    # ── Materialize N items (one per offer) ───────────────────
    note = _safety_note(debug.safety_flags, debug.human_review_required, debug.errors)
    if poster.items:
        debug.items = [_materialize_item(ext, image_path, note, i)
                       for i, ext in enumerate(poster.items)]
    else:
        # No offers extracted — still emit a placeholder Item flagged for review
        stem = Path(image_path).stem
        debug.human_review_required = True
        placeholder_note = "\n".join(filter(None, [
            note,
            "[warn] LLM extracted no items — flyer may need manual entry",
        ]))
        debug.items = [Item(
            title=stem, state="suggestion",
            brief={"de": ""}, description={"de": ""},
            editingNote=placeholder_note,
        )]

    debug.timings.total_ms = (time.perf_counter() - total_start) * 1000
    return _finalize(debug, output_dir)


def _finalize(debug: DebugResult, output_dir: str | Path) -> tuple[AdapterData, DebugResult]:
    """Write output files in the directory-per-poster layout:

        <output_dir>/<poster-slug>/
            _all.json           # AdapterData wrapping ALL items on this poster
            _debug.json         # OCR words, blocks, safety flags, timings
            <item-slug>.json    # AdapterData wrapping ONE item — deliverable per offer
    """
    stem = Path(debug.image_path).stem
    p_slug = _poster_slug(stem)

    items = debug.items or [Item(
        title=stem, state="suggestion",
        brief={"de": ""}, description={"de": ""},
        editingNote="HUMAN REVIEW REQUIRED\n[error] pipeline failed before extraction",
    )]

    now = int(time.time())
    items_record = _dedupe_slugs(items, p_slug)
    adapter = Adapter(name=ADAPTER_NAME, sourceName=stem, sourceUrl=debug.image_path)

    adapter_data = AdapterData(
        adapter=adapter,
        lastUpdate=now,
        version=ADAPTER_VERSION,
        itemsRecord=items_record,
    )

    poster_dir = Path(output_dir) / p_slug
    poster_dir.mkdir(parents=True, exist_ok=True)

    # Aggregate: all items in one file
    (poster_dir / "_all.json").write_text(
        adapter_data.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")

    # Debug: OCR + blocks + safety + timings (poster-level)
    (poster_dir / "_debug.json").write_text(
        debug.model_dump_json(indent=2), encoding="utf-8")

    # Per-offer files: each a full AdapterData wrapping exactly one item
    for item_slug, item in items_record.items():
        single = AdapterData(
            adapter=adapter,
            lastUpdate=now,
            version=ADAPTER_VERSION,
            itemsRecord={item_slug: item},
        )
        (poster_dir / f"{item_slug}.json").write_text(
            single.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")

    return adapter_data, debug

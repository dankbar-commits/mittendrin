"""Pydantic models.

Two families:

1. **Target output** — `AdapterData` and `Item` mirror the `mittendrin.in – Brandenburg`
   schema (see data/samples/json_target_format.json). This is what the pipeline
   emits as its deliverable JSON.

2. **Internal / debug** — `OCRWord`, `Block`, `SafetyFlag`, `PipelineError`,
   `Timings`, `Result` carry stage-level artifacts for the notebook and for
   audit. Written to a separate `<stem>.debug.json`.

`LLMItemExtraction` is the sub-schema the local LLM must return. It is a
subset of `Item` (only fields plausibly extractable from a flyer's text).
The same Pydantic model exports its JSON Schema and is passed to Ollama's
`format=` parameter, so the model is told the exact shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────────────────────────────────────────
# Target output (AdapterData / Item) — mirrors json_target_format.json
# ─────────────────────────────────────────────────────────────

ItemState = Literal["public", "draft", "archived", "suggestion"]

# Multilang string: { "de": "…", "en": "…" } — free-form dict of 2-letter codes.
MultiLang = dict[str, str]


class Item(BaseModel):
    """One entry in the mittendrin-in-Brandenburg directory."""
    model_config = ConfigDict(extra="ignore")

    # Required by the target schema
    title: str
    state: ItemState = "suggestion"
    brief: MultiLang = Field(default_factory=dict)
    description: MultiLang = Field(default_factory=dict)

    # Optional fields (all nullable; empty when the flyer didn't say)
    titleAddOn: MultiLang | None = None
    image: str | None = None
    tags: list[str] = Field(default_factory=list)
    primaryTopic: str | None = None
    location_ref: str | None = None
    location: str | None = None
    directions: MultiLang | None = None
    address: str | None = None
    zip: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    recurring_event: str | None = None
    responsibleInstitution: str | None = None
    sponsors: str | None = None
    website: str | None = None
    email: str | None = None
    facebook: str | None = None
    whatsapp: str | None = None
    contact: str | None = None
    phone: str | None = None
    mobile: str | None = None
    editingNote: str | None = None
    hours: MultiLang | None = None
    accessibility: MultiLang | None = None
    charge: MultiLang | None = None
    venue: MultiLang | None = None
    resubmissionDate: str | None = None


class Adapter(BaseModel):
    name: str
    sourceName: str
    sourceUrl: str | None = None


class AdapterData(BaseModel):
    """Top-level target output — a wrapper of items + metadata."""
    model_config = ConfigDict(extra="ignore")

    adapter: Adapter
    lastUpdate: int  # unix seconds
    version: str | None = None
    itemsRecord: dict[str, Item] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# LLM extraction sub-schema — this is what Ollama fills
# ─────────────────────────────────────────────────────────────

class LLMItemExtraction(BaseModel):
    """One extracted offer/service/event.

    All fields are optional strings so the model can leave gaps instead of
    inventing content. Multilang fields collapse to a plain German string here;
    the pipeline wraps them into {"de": …} shape.
    """
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    brief_de: str | None = None
    description_de: str | None = None
    tags: list[str] = Field(default_factory=list)
    primaryTopic: str | None = None
    location: str | None = None
    address: str | None = None
    zip: str | None = None
    city: str | None = None
    responsibleInstitution: str | None = None
    sponsors: str | None = None
    website: str | None = None
    email: str | None = None
    facebook: str | None = None
    whatsapp: str | None = None
    contact: str | None = None
    phone: str | None = None
    mobile: str | None = None
    hours_de: str | None = None
    accessibility_de: str | None = None
    charge_de: str | None = None
    venue_de: str | None = None


class LLMPosterExtraction(BaseModel):
    """A poster can advertise multiple offers. The LLM returns them as a list.

    A single-offer flyer returns a one-element list. Empty list is allowed when
    no offer is discernible (rare — the pipeline treats it as a review flag).
    """
    model_config = ConfigDict(extra="ignore")

    items: list[LLMItemExtraction] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# Internal pipeline artifacts (debug output, notebook visuals)
# ─────────────────────────────────────────────────────────────

SafetyCategory = Literal[
    "profanity", "hate", "violence", "selfharm", "csam",
    "pii", "spam", "scam",
]

Severity = Literal["soft", "hard"]

FlagSource = Literal["ocr", "llm"]


class BoundingBox(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    polygon: list[tuple[float, float]] | None = None


class OCRWord(BaseModel):
    text: str
    confidence: float
    bbox: BoundingBox


class Block(BaseModel):
    id: int
    text: str
    bbox: BoundingBox
    word_ids: list[int]


class SafetyFlag(BaseModel):
    category: SafetyCategory
    rule_id: str
    severity: Severity
    matched_span: str
    source: FlagSource


class PipelineError(BaseModel):
    stage: Literal["io", "ocr", "layout", "llm", "safety", "pipeline"]
    message: str


class Timings(BaseModel):
    ocr_ms: float = 0.0
    layout_ms: float = 0.0
    llm_ms: float = 0.0
    safety_ms: float = 0.0
    total_ms: float = 0.0


class DebugResult(BaseModel):
    """Everything the pipeline knows about a single image — for the notebook and audit."""
    image_path: str
    created_at: datetime = Field(default_factory=datetime.now)
    model_name: str = ""
    ocr: list[OCRWord] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)
    llm_raw: LLMPosterExtraction | None = None
    items: list[Item] = Field(default_factory=list)
    safety_flags: list[SafetyFlag] = Field(default_factory=list)
    human_review_required: bool = False
    errors: list[PipelineError] = Field(default_factory=list)
    timings: Timings = Field(default_factory=Timings)

"""
app/schemas.py

All Pydantic models: the shapes of data going in and out of the API.
Kept in one file since the flat structure doesn't split by feature —
if this grows past a few hundred lines, splitting by domain (event
schemas vs chat schemas) becomes worth revisiting.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


class EventCategory(StrEnum):
    MUSIC = "Musik"
    SPORT = "Sport"
    FAMILY = "Familie & Kinder"
    CULTURE = "Kultur"
    MARKET = "Märkte"
    WORKSHOP = "Workshops"


# --------------------------------------------------------------------------
# Location
# --------------------------------------------------------------------------


class Location(BaseModel):
    address: str
    latitude: float | None = None
    longitude: float | None = None


# --------------------------------------------------------------------------
# Event
# --------------------------------------------------------------------------


class EventBase(BaseModel):
    title: str
    category: EventCategory
    date: str  # ISO date string, e.g. "2026-09-20"
    location: Location
    description: str
    spots_left: int | None = None


class EventCreate(EventBase):
    """Used when an organizer's draft is finalized into a real event."""

    pass


class EventOut(EventBase):
    """Shape returned to the frontend when listing/searching events."""

    id: str
    created_at: datetime


# --------------------------------------------------------------------------
# Event draft (organizer autofill-then-ask flow)
# --------------------------------------------------------------------------


class EventDraft(BaseModel):
    """
    A partially-filled event being built up over a conversation.
    All fields optional since the draft starts empty and fills in gradually.
    """

    title: str | None = None
    category: EventCategory | None = None
    date: str | None = None
    location: Location | None = None
    description: str | None = None

    def missing_fields(self) -> list[str]:
        required = ["title", "category", "date", "location", "description"]
        return [field for field in required if getattr(self, field) is None]

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0


class EventDraftMessageRequest(BaseModel):
    session_id: str
    message: str


class EventDraftMessageResponse(BaseModel):
    session_id: str
    draft: EventDraft
    missing_fields: list[str]
    reply: str  # the SLM's follow-up question, or a completion confirmation


# --------------------------------------------------------------------------
# Visitor chat (search/discovery)
# --------------------------------------------------------------------------


class ChatMessageRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    reply: str
    events: list[EventOut]


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


class RegistrationRequest(BaseModel):
    event_id: str
    name: str
    email: EmailStr
    participants: int = Field(default=1, ge=1, le=10)


class RegistrationOut(BaseModel):
    id: str
    event_id: str
    name: str
    email: EmailStr
    participants: int
    created_at: datetime


# --------------------------------------------------------------------------
# Draft item — mirrors frontend/src/lib/schema.js exactly.
#
# This is a DIFFERENT, unrelated data model from EventDraft/EventOut above.
# It backs the actual shipped frontend's chat-based single-submission flow
# (POST /api/extract), which has no category/date/registration concept at
# all — it produces one general community-offering entry with tags instead
# of a fixed category, and is never persisted (see frontend's own note:
# "Es findet keine Speicherung statt — dies ist ein reiner Prototyp").
#
# Keep this in sync BY HAND with frontend/src/lib/schema.js if either side
# changes — same warning the frontend file gives about its own duplication.
# --------------------------------------------------------------------------

RECURRING_INTERVALS = [
    "fixed",
    "daily",
    "mon-fri",
    "weekly",
    "bi-weekly",
    "three-weekly",
    "four-weekly",
    "first_of_month",
    "second_of_month",
    "third_of_month",
    "fourth_of_month",
    "last_of_month",
]

RECURRING_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Controlled vocabulary served via GET /api/tags. Not exhaustive — extend as
# real usage reveals gaps. Kept here (not services.py) since it's data
# tightly coupled to DraftItem.tags, not business logic.
TAG_VOCABULARY = [
    "kostenlos",
    "barrierefrei",
    "kinder",
    "familie",
    "senioren",
    "beratung",
    "gesundheit",
    "sport",
    "kultur",
    "musik",
    "bildung",
    "sprachkurs",
    "ehrenamt",
    "migration",
    "online",
    "workshop",
    "selbsthilfe",
    "notfall",
]


class I18nText(BaseModel):
    de: str


class RecurringRule(BaseModel):
    interval: str
    day: str | None = None
    start: str | None = None
    end: str | None = None
    exampleDate: str | None = None


class DraftItem(BaseModel):
    """Mirrors frontend/src/lib/schema.js's emptyDraft() field-for-field."""

    title: str | None = None
    brief: I18nText | None = None
    description: I18nText | None = None
    location: str | None = None
    address: str | None = None
    zip: str | None = None
    city: str | None = None
    website: str | None = None
    onlineOnly: bool | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    contact: str | None = None
    responsibleInstitution: str | None = None
    sponsors: str | None = None
    hours: I18nText | None = None
    charge: I18nText | None = None
    accessibility: I18nText | None = None
    directions: I18nText | None = None
    venue: I18nText | None = None
    image: str | None = None
    tags: list[str] = Field(default_factory=list)
    recurringEvent: list[RecurringRule] = Field(default_factory=list)
    state: str = "suggestion"
    latitude: float | None = None
    longitude: float | None = None
    inferredFields: list[str] = Field(default_factory=list)
    turnCount: int = 0


class ExtractRequest(BaseModel):
    draft: DraftItem
    message: str = Field(min_length=1, max_length=2000)


class GeocodeRequest(BaseModel):
    """Backs POST /api/geocode — lets the frontend re-geocode after the
    person edits the address/city fields by hand, independent of the
    chat/extract flow."""

    address: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)


class SubmitRequest(BaseModel):
    """Backs POST /api/submit. Just the draft — no persistence yet, see
    routes.py / services.py docstrings."""

    draft: DraftItem
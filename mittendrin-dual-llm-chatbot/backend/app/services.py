"""
app/services.py

Business logic layer — combines storage.py with the LLM, maps, and email
clients. Three areas:
  - event_service:        search/list events for visitors
  - draft_service:        the autofill-then-ask flow for organizers
                           creating a new event through conversation
  - registration_service: registering for an event + sending a confirmation
"""

import logging

from app import storage
from app.clients import email_client, llm_client, maps_client
from app.clients.email_client import EmailError
from app.clients.llm_client import LLMError
from app.clients.maps_client import MapsError
from app.schemas import (
    RECURRING_DAYS,
    RECURRING_INTERVALS,
    TAG_VOCABULARY,
    DraftItem,
    EventCategory,
    EventCreate,
    EventDraft,
    EventDraftMessageResponse,
    EventOut,
    I18nText,
    Location,
    RecurringRule,
    RegistrationOut,
    RegistrationRequest,
)

logger = logging.getLogger(__name__)


# ==========================================================================
# Event service (visitor search)
# ==========================================================================


def search_events(
    category: str | None = None, keywords: str | None = None
) -> list[EventOut]:
    """Simple in-memory filter over all stored events. No LLM involved here
    — that lives in the chat route, which parses free text into these
    plain category/keywords arguments before calling this function."""
    events = storage.load_events()

    if category:
        events = [e for e in events if e.category == category]

    if keywords:
        kw = keywords.lower()
        events = [
            e for e in events if kw in e.title.lower() or kw in e.description.lower()
        ]

    return events


# ==========================================================================
# Draft service (organizer autofill-then-ask)
# ==========================================================================

# In-memory session store: session_id -> EventDraft. Fine for local dev —
# a restart loses in-progress drafts, which is an acceptable tradeoff for
# now. Swap for a persisted store (even just another JSON file) if that
# becomes a problem.
_draft_sessions: dict[str, EventDraft] = {}

_VALID_CATEGORIES = ", ".join(f'"{c.value}"' for c in EventCategory)

_FIELD_EXTRACTOR_SYSTEM_PROMPT = f"""Du hilfst dabei, aus einer Nachricht eines Veranstalters
Informationen für eine Veranstaltung zu extrahieren.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in genau diesem Format,
ohne zusätzlichen Text, ohne Markdown-Codeblöcke. Felder, die nicht in
der Nachricht vorkommen, bleiben null:

{{
  "title": string | null,
  "category": {_VALID_CATEGORIES} | null,
  "date": string | null,
  "location": string | null,
  "description": string | null
}}

Regeln:
- "date" im Format YYYY-MM-DD, falls ein Datum erkennbar ist.
- "location" ist die rohe Adresse/Ortsangabe als Text (wird separat geokodiert).
- "category" muss GENAU einer der oben gelisteten Werte sein, oder null.
- Erfinde keine Informationen, die nicht in der Nachricht stehen."""

_FOLLOWUP_QUESTION_SYSTEM_PROMPT = """Du hilfst einem Veranstalter dabei, eine Veranstaltung
anzulegen. Du bekommst die bereits bekannten Felder und eine Liste der noch
fehlenden Felder.

Schreibe EINE kurze, freundliche Frage auf Deutsch, die nach dem ERSTEN
fehlenden Feld fragt. Frage nach nur einem Feld auf einmal, nicht nach mehreren.
Gib nur die Frage zurück, keinen zusätzlichen Text."""

_FIELD_LABELS_DE = {
    "title": "Titel",
    "category": "Kategorie",
    "date": "Datum",
    "location": "Ort",
    "description": "Beschreibung",
}


def _sanitize_category(value: str | None) -> EventCategory | None:
    if value is None:
        return None
    for category in EventCategory:
        if category.value == value:
            return category
    return None


async def _extract_fields(message: str) -> dict:
    """Calls the SLM to pull known fields out of free text. Returns an
    empty dict (nothing extracted) rather than raising, so a parsing
    failure doesn't block the conversation."""
    try:
        return await llm_client.chat_completion_json(
            [
                {"role": "system", "content": _FIELD_EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0.1,
            enable_thinking=False,
        )
    except LLMError as e:
        logger.warning("Field extraction failed, continuing with no new fields: %s", e)
        return {}


async def _resolve_location(address_text: str) -> Location:
    """Geocodes a raw address string. Falls back to an address-only
    Location (no coordinates) if geocoding fails, rather than blocking
    the draft on a map API hiccup."""
    try:
        location = await maps_client.geocode_address(address_text)
        if location:
            return location
    except MapsError as e:
        logger.warning("Geocoding failed for '%s': %s", address_text, e)

    return Location(address=address_text, latitude=None, longitude=None)


async def _generate_followup_question(draft: EventDraft, missing: list[str]) -> str:
    known = {k: v for k, v in draft.model_dump().items() if v is not None}
    next_field = missing[0]

    user_message = (
        f"Bekannte Felder: {known}\n"
        f"Fehlende Felder: {[_FIELD_LABELS_DE[f] for f in missing]}\n"
        f"Frage als nächstes nach: {_FIELD_LABELS_DE[next_field]}"
    )

    try:
        return await llm_client.chat_completion(
            [
                {"role": "system", "content": _FOLLOWUP_QUESTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
            enable_thinking=True,
        )
    except LLMError as e:
        logger.warning("Follow-up question generation failed, using fallback: %s", e)
        return f"Kannst du mir noch den/die {_FIELD_LABELS_DE[next_field]} nennen?"


async def process_draft_message(
    session_id: str, message: str
) -> EventDraftMessageResponse:
    draft = _draft_sessions.get(session_id, EventDraft())

    extracted = await _extract_fields(message)

    if extracted.get("title"):
        draft.title = extracted["title"]
    if extracted.get("category"):
        category = _sanitize_category(extracted["category"])
        if category:
            draft.category = category
    if extracted.get("date"):
        draft.date = extracted["date"]
    if extracted.get("location"):
        draft.location = await _resolve_location(extracted["location"])
    if extracted.get("description"):
        draft.description = extracted["description"]

    _draft_sessions[session_id] = draft

    missing = draft.missing_fields()

    if missing:
        reply = await _generate_followup_question(draft, missing)
    else:
        reply = (
            "Perfekt, ich habe jetzt alle Informationen! "
            "Möchtest du die Veranstaltung so veröffentlichen?"
        )

    return EventDraftMessageResponse(
        session_id=session_id,
        draft=draft,
        missing_fields=missing,
        reply=reply,
    )


def finalize_draft(session_id: str) -> EventOut:
    """Turns a complete draft into a real, saved event. Raises ValueError
    if the draft isn't complete or doesn't exist — callers (the route)
    should turn this into a 400 response."""
    draft = _draft_sessions.get(session_id)
    if draft is None:
        raise ValueError("No draft found for this session")
    if not draft.is_complete():
        raise ValueError(f"Draft is missing fields: {draft.missing_fields()}")

    event = storage.create_event(EventCreate(**draft.model_dump()))
    del _draft_sessions[session_id]
    return event


# ==========================================================================
# Draft extraction — backs the actual shipped frontend (POST /api/extract).
#
# This is UNRELATED to the EventDraft/session flow above: it's stateless
# (the frontend sends the whole current draft every turn, no session_id),
# it has no category/date concept, and it's never persisted to storage.py —
# see the DraftItem docstring in schemas.py for why these are two separate
# data models rather than one being a subset of the other.
# ==========================================================================

_RECURRING_INTERVALS_STR = ", ".join(f'"{i}"' for i in RECURRING_INTERVALS)
_RECURRING_DAYS_STR = ", ".join(f'"{d}"' for d in RECURRING_DAYS)
_TAG_VOCAB_STR = ", ".join(f'"{t}"' for t in TAG_VOCABULARY)

_EXTRACT_SYSTEM_PROMPT = f"""Du hilfst dabei, aus einer Nachricht Informationen für einen
Eintrag (Angebot/Einrichtung/Veranstaltung) zu extrahieren. Du bekommst die
bereits bekannten Felder und eine neue Nachricht dazu.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in genau diesem Format, ohne
zusätzlichen Text, ohne Markdown-Codeblöcke. Felder, die du nicht aus der
Nachricht ableiten kannst, bleiben null (nicht raten):

{{
  "title": string | null,
  "brief": string | null,
  "description": string | null,
  "generated_text_fields": array of any of ["title", "brief", "description"],
  "location_name": string | null,
  "address": string | null,
  "zip": string | null,
  "city": string | null,
  "website": string | null,
  "onlineOnly": boolean | null,
  "email": string | null,
  "phone": string | null,
  "mobile": string | null,
  "contact": string | null,
  "responsibleInstitution": string | null,
  "sponsors": string | null,
  "hours": string | null,
  "charge": string | null,
  "accessibility": string | null,
  "directions": string | null,
  "venue": string | null,
  "tags": array of zero or more values from [{_TAG_VOCAB_STR}],
  "recurringEvent": array of {{"interval": one of [{_RECURRING_INTERVALS_STR}], "day": one of [{_RECURRING_DAYS_STR}] or null, "start": "HH:MM" or null, "end": "HH:MM" or null, "exampleDate": "YYYY-MM-DD" or null}} | null
}}

Regeln:
1. "address"/"zip"/"city" nur setzen, wenn eine VOLLSTÄNDIGE Adresse explizit
   im Text steht. Wird nur ein Name eines Orts/einer Einrichtung genannt
   (z. B. "Sozialstation Torstraße"), setze das in "location_name" —
   NICHT in "address". Die Geokodierung passiert separat.
2. "title", "brief", "description": wenn kein passender Text explizit
   vorhanden ist, formuliere einen sinnvollen Vorschlag basierend auf dem
   Kontext und liste das Feld in "generated_text_fields". Wenn der Nutzer
   explizit einen Titel/Text vorgibt, übernimm ihn wörtlich und liste das
   Feld NICHT in "generated_text_fields".
3. "tags" ausschließlich aus der gegebenen Liste wählen, nichts erfinden.
4. Erfinde keine Fakten (Adressen, Telefonnummern, Preise), die nicht im
   Text stehen oder eindeutig daraus hervorgehen."""


def _sanitize_recurring_rule(raw: dict) -> RecurringRule | None:
    interval = raw.get("interval")
    if interval not in RECURRING_INTERVALS:
        return None
    day = raw.get("day")
    if day not in RECURRING_DAYS:
        day = None
    return RecurringRule(
        interval=interval,
        day=day,
        start=raw.get("start"),
        end=raw.get("end"),
        exampleDate=raw.get("exampleDate"),
    )


async def _extract_patch(known_fields: dict, message: str) -> dict:
    """Calls the LLM to produce a partial patch of new/updated fields.
    Raises LLMError on failure (network down, both local and Claude
    fallback exhausted, or unparseable JSON) — the route turns this into
    the frontend's {ok: false, error} shape, since the frontend has a
    real error UI for this rather than silently doing nothing."""
    user_content = f"Bereits bekannte Felder: {known_fields}\n\nNeue Nachricht: {message}"

    return await llm_client.chat_completion_json(
        [
            {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_tokens=800,
        enable_thinking=False,
    )


async def extract_draft(draft: DraftItem, message: str) -> DraftItem:
    """
    The core of POST /api/extract: merges whatever the LLM can pull out of
    `message` into `draft` and returns the updated draft. Stateless by
    design — the frontend owns the draft and resends it whole every turn.

    Raises LLMError if the LLM call itself fails — the route is
    responsible for turning that into {ok: false, error}.
    """
    known_fields = draft.model_dump(exclude={"inferredFields", "turnCount", "state"})
    patch = await _extract_patch(known_fields, message)

    new_draft = draft.model_copy(deep=True)
    inferred = set(new_draft.inferredFields)
    generated = set(patch.get("generated_text_fields") or [])

    if patch.get("title"):
        new_draft.title = patch["title"]
        (inferred.add if "title" in generated else inferred.discard)("title")

    if patch.get("brief"):
        new_draft.brief = I18nText(de=patch["brief"])
        (inferred.add if "brief" in generated else inferred.discard)("brief.de")

    if patch.get("description"):
        new_draft.description = I18nText(de=patch["description"])
        (inferred.add if "description" in generated else inferred.discard)("description.de")

    simple_fields = [
        "website",
        "email",
        "phone",
        "mobile",
        "contact",
        "responsibleInstitution",
        "sponsors",
    ]
    for field in simple_fields:
        if patch.get(field):
            setattr(new_draft, field, patch[field])

    if patch.get("onlineOnly") is True:
        new_draft.onlineOnly = True

    i18n_fields = ["hours", "charge", "accessibility", "directions", "venue"]
    for field in i18n_fields:
        if patch.get(field):
            setattr(new_draft, field, I18nText(de=patch[field]))

    if patch.get("tags"):
        valid_tags = [t for t in patch["tags"] if t in TAG_VOCABULARY]
        new_draft.tags = sorted(set(new_draft.tags) | set(valid_tags))

    if patch.get("recurringEvent"):
        rules = [rule for raw in patch["recurringEvent"] if (rule := _sanitize_recurring_rule(raw))]
        if rules:
            new_draft.recurringEvent = rules

    if patch.get("location_name"):
        new_draft.location = patch["location_name"]

    # Address handling: explicit full address given -> trust the text
    # directly, but still geocode it (address text itself is untouched,
    # only latitude/longitude get filled in — needed for the map preview).
    # Only a place name given -> geocode it for the address text too, and
    # flag it as inferred, since it's a lookup result rather than verbatim
    # user input.
    if patch.get("address") and patch.get("city"):
        new_draft.address = patch["address"]
        new_draft.city = patch["city"]
        if patch.get("zip"):
            new_draft.zip = patch["zip"]
        inferred.discard("address")

        if new_draft.latitude is None or new_draft.longitude is None:
            try:
                location = await maps_client.geocode_address(f"{patch['address']}, {patch['city']}")
            except MapsError as e:
                logger.warning("Geocoding failed for '%s, %s': %s", patch["address"], patch["city"], e)
                location = None
            if location:
                new_draft.latitude = location.latitude
                new_draft.longitude = location.longitude
    elif patch.get("location_name") and not new_draft.address and new_draft.onlineOnly is not True:
        try:
            location = await maps_client.geocode_address(patch["location_name"])
        except MapsError as e:
            logger.warning("Geocoding failed for '%s': %s", patch["location_name"], e)
            location = None
        if location:
            new_draft.address = location.address
            new_draft.latitude = location.latitude
            new_draft.longitude = location.longitude
            inferred.add("address")

    new_draft.inferredFields = sorted(inferred)
    new_draft.turnCount = draft.turnCount + 1
    return new_draft


async def geocode_location(address: str, city: str) -> Location | None:
    """Backs POST /api/geocode. Thin passthrough to maps_client — kept in
    services.py rather than called directly from routes.py so the
    "nothing calls a client directly except services.py" rule stays true
    everywhere, not just for the chat/extract flow."""
    return await maps_client.geocode_address(f"{address}, {city}")


async def submit_draft(draft: DraftItem) -> bool:
    """
    Backs POST /api/submit. No persistence yet (see routes.py docstring) —
    this only sends the organizer a confirmation email, and only if they
    filled in the optional "email" field. Returns whether an email was
    actually sent, so the route can report it without treating "no email
    on file" as an error.

    A failed send is logged and swallowed, same policy as
    register_for_event below — a missed email shouldn't turn a successful
    submission into an error response.
    """
    if not draft.email:
        return False

    brief_text = draft.brief.de if draft.brief else None

    try:
        await email_client.send_submission_confirmation(
            to_email=draft.email,
            title=draft.title or "(ohne Titel)",
            brief=brief_text,
            address=draft.address,
            city=draft.city,
        )
        return True
    except EmailError as e:
        logger.warning("Submission confirmation email failed: %s", e)
        return False


# ==========================================================================
# Registration service
# ==========================================================================


async def register_for_event(request: RegistrationRequest) -> RegistrationOut:
    event = storage.get_event(request.event_id)
    if event is None:
        raise ValueError(f"Event not found: {request.event_id}")

    registration = storage.create_registration(request)

    try:
        await email_client.send_registration_confirmation(
            to_email=request.email,
            name=request.name,
            event_title=event.title,
            event_date=event.date,
            event_address=event.location.address,
            participants=request.participants,
        )
    except EmailError as e:
        # A failed confirmation email shouldn't undo a successful
        # registration — log it and move on.
        logger.warning("Registration saved but confirmation email failed: %s", e)

    return registration
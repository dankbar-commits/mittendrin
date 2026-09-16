"""
app/routes.py

All HTTP endpoints. This layer is intentionally thin — it validates
input via the schemas, calls into services.py for the actual logic, and
translates service-layer exceptions (ValueError, LLMError, etc.) into
proper HTTP responses. No business logic should live here.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app import services
from app.clients.llm_client import LLMError
from app.clients.maps_client import MapsError
from app.schemas import (
    TAG_VOCABULARY,
    ChatMessageRequest,
    ChatMessageResponse,
    EventDraftMessageRequest,
    EventDraftMessageResponse,
    EventOut,
    ExtractRequest,
    GeocodeRequest,
    RegistrationOut,
    RegistrationRequest,
    SubmitRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==========================================================================
# Health
# ==========================================================================


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}


# ==========================================================================
# Events (visitor search)
# ==========================================================================


@router.get("/events", response_model=list[EventOut])
async def list_events(
    category: str | None = None, q: str | None = None
) -> list[EventOut]:
    """Plain filter-based search. For free-text natural language queries,
    the frontend should use /chat instead, which parses the query first."""
    return services.search_events(category=category, keywords=q)


@router.post("/chat", response_model=ChatMessageResponse)
async def chat(request: ChatMessageRequest) -> ChatMessageResponse:
    """Visitor free-text search — currently does a plain keyword search
    using the raw message. Swap in an LLM-based query parser here later
    if free-text understanding needs to improve (see prompts/visitor/)."""
    events = services.search_events(keywords=request.message)

    if events:
        reply = f"Ich habe {len(events)} passende Veranstaltung(en) gefunden:"
    else:
        reply = "Ich konnte leider keine passenden Veranstaltungen finden. Versuch es mit anderen Begriffen."

    return ChatMessageResponse(reply=reply, events=events)


# ==========================================================================
# Event draft (organizer autofill-then-ask)
# ==========================================================================


@router.post("/event-draft/message", response_model=EventDraftMessageResponse)
async def event_draft_message(
    request: EventDraftMessageRequest,
) -> EventDraftMessageResponse:
    return await services.process_draft_message(request.session_id, request.message)


@router.post("/event-draft/{session_id}/finalize", response_model=EventOut)
async def finalize_event_draft(session_id: str) -> EventOut:
    try:
        return services.finalize_draft(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ==========================================================================
# Registration
# ==========================================================================


@router.post("/registrations", response_model=RegistrationOut)
async def register(request: RegistrationRequest) -> RegistrationOut:
    try:
        return await services.register_for_event(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ==========================================================================
# Draft extraction — what the actual shipped frontend (frontend/src) calls.
# See services.py's "Draft extraction" section for why this is a separate,
# unrelated flow from /chat and /event-draft above.
# ==========================================================================


@router.post("/geocode")
async def geocode(request: GeocodeRequest) -> dict:
    """
    Standalone geocoding for when the person edits the address/city fields
    directly in the form, separate from the chat-driven /extract flow.
    Same always-200, {ok: bool} shape as /extract so the frontend handles
    both the same way. A `null` location (ok: true, no match found) is not
    an error — the address just didn't resolve to anywhere on the map.
    """
    try:
        location = await services.geocode_location(request.address, request.city)
    except MapsError as e:
        logger.warning("Geocode request failed: %s", e)
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "location": location.model_dump() if location else None,
    }


@router.post("/submit")
async def submit(request: SubmitRequest) -> dict:
    """
    No persistence yet — see services.submit_draft docstring. Sends a
    confirmation email if (and only if) the draft has an email address on
    file; `emailed: false` covers both "no email given" and "email send
    failed," since the frontend doesn't need to distinguish those to show
    a sensible message.
    """
    emailed = await services.submit_draft(request.draft)
    return {"ok": True, "emailed": emailed}


@router.get("/tags")
async def get_tags() -> dict:
    return {"tags": TAG_VOCABULARY}


@router.post("/extract")
async def extract(request: ExtractRequest) -> dict:
    """
    Matches the frontend's expected contract exactly (frontend/src/api/client.js):
    always HTTP 200, body is either {"ok": true, "draft": {...}} or
    {"ok": false, "error": "..."} — never an HTTPException, since the
    frontend's error handling only ever inspects the JSON body's `ok` field,
    not the HTTP status code.
    """
    try:
        updated_draft = await services.extract_draft(request.draft, request.message)
        return {"ok": True, "draft": updated_draft.model_dump()}
    except LLMError as e:
        logger.warning("Extract request failed: %s", e)
        return {"ok": False, "error": str(e)}
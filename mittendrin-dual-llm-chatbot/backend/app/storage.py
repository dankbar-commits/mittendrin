"""
app/storage.py

This is the whole "database" for now: two flat JSON files, one for events
and one for registrations. Nothing else in the app should open these files
directly — everything goes through the functions here, so swapping this
for a real database later only means rewriting this one file.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.schemas import EventCreate, EventOut, RegistrationOut, RegistrationRequest

DATA_DIR = Path(__file__).parent / "data"
EVENTS_FILE = DATA_DIR / "events.json"
REGISTRATIONS_FILE = DATA_DIR / "registrations.json"


def _load_json(path: Path) -> list[dict]:
    """Reads a JSON file as a list of dicts. Treats a missing or empty file
    as an empty list rather than raising, so a freshly-scaffolded or
    accidentally-truncated data file doesn't crash the app."""
    if not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text("[]", encoding="utf-8")
        return []

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    return json.loads(content)


def _save_json(path: Path, data: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------


def load_events() -> list[EventOut]:
    raw = _load_json(EVENTS_FILE)
    return [EventOut(**item) for item in raw]


def get_event(event_id: str) -> EventOut | None:
    for event in load_events():
        if event.id == event_id:
            return event
    return None


def create_event(event: EventCreate) -> EventOut:
    """Assigns an id + timestamp and appends the event to events.json."""
    new_event = EventOut(
        id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        **event.model_dump(),
    )

    events = _load_json(EVENTS_FILE)
    events.append(json.loads(new_event.model_dump_json()))
    _save_json(EVENTS_FILE, events)

    return new_event


# --------------------------------------------------------------------------
# Registrations
# --------------------------------------------------------------------------


def load_registrations() -> list[RegistrationOut]:
    raw = _load_json(REGISTRATIONS_FILE)
    return [RegistrationOut(**item) for item in raw]


def create_registration(registration: RegistrationRequest) -> RegistrationOut:
    new_registration = RegistrationOut(
        id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        **registration.model_dump(),
    )

    registrations = _load_json(REGISTRATIONS_FILE)
    registrations.append(json.loads(new_registration.model_dump_json()))
    _save_json(REGISTRATIONS_FILE, registrations)

    return new_registration

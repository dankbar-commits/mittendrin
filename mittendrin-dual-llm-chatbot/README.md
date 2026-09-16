# Mittendrin in Brandenburg — Chatbot

An organizer-facing chatbot that turns a free-text description of a
community event, service, or offering into a structured, publish-ready
entry. You describe your event in plain German; an LLM extracts what it
can (title, description, address, hours, tags, recurrence pattern, ...),
geocodes the location automatically, flags anything it *generated* rather
than found verbatim, and asks follow-up questions for whatever's still
missing — all inline, field-by-field, as you keep chatting.

This is a prototype: there is currently **no database** and **no
persistence**. The finished entry is shown as a copyable JSON block; the
only side effect on submission is an optional confirmation email.

---

## Tech stack

| Layer | Technology | Version |
|---|---|---|
| Backend framework | [FastAPI](https://fastapi.tiangolo.com/) | 0.141.1 |
| Backend server | Uvicorn (standard extras) | 0.53.0 |
| Backend language / runtime | Python | 3.12 |
| Backend package manager | [uv](https://docs.astral.sh/uv/) | — |
| Backend linter/formatter | [Ruff](https://docs.astral.sh/ruff/) | ≥0.6.0 |
| Validation | Pydantic (+ `email` extra) / Pydantic Settings | 2.13.5 / 2.15.0 |
| HTTP client | httpx | 0.28.1 |
| Email | aiosmtplib (generic SMTP) | 5.1.3 |
| Frontend framework | [React](https://react.dev/) | 18.3.1 |
| Frontend build tool | [Vite](https://vite.dev/) | 8.3.0 |
| Frontend styling | **[Tailwind CSS 4](https://tailwindcss.com/)** (via `@tailwindcss/vite`, no PostCSS config needed) | 4.3.0 |
| Frontend validation | [Zod](https://zod.dev/) | 4.6.2 |
| Primary LLM | Claude (Anthropic Messages API) | configurable, default `claude-sonnet-5` |
| Fallback LLM | Any OpenAI-compatible local server (LM Studio, Ollama, vLLM, ...) | default model: `nvidia/nemotron-3-nano-4b` |
| Geocoding | OpenStreetMap Nominatim (default, no key) or Google Geocoding API | — |
| Containerization | Docker + Docker Compose | — |

---

## Architecture

```
frontend/ (React + Vite + Tailwind 4)
      │  fetch() over HTTP, CORS
      ▼
backend/ (FastAPI)
      │
      ├── app/clients/llm_client.py  ──► app/clients/anthropic_client.py  (Claude — primary)
      │                               ╲► app/clients/llm_client.py's local call (fallback)
      ├── app/clients/maps_client.py ──► OpenStreetMap Nominatim / Google Geocoding
      └── app/clients/email_client.py──► SMTP (Gmail / SendGrid relay / SES / Outlook / ...)
```

**LLM fallback order.** `LLM_PRIMARY_PROVIDER` in `backend/.env` controls
which model is tried first — **Claude by default**. If the primary fails
or times out, the other is used automatically:

- **Claude primary, no `ANTHROPIC_API_KEY` set** → skips straight to the
  local model, no failed attempt first.
- **Claude primary, key set, Claude fails/times out** → falls back to the
  local model.
- **Local primary, local fails/times out** → falls back to Claude (if a
  key is configured).
- **Both fail** → the request returns a clean `{"ok": false, "error": "..."}`
  — the frontend always gets a real HTTP 200 with this shape from
  `/api/extract`, never a raw 500, so its own error UI can display it.

**Two separate data models exist in this codebase on purpose.** The
actively-used frontend talks to `POST /api/extract`, backed by
`DraftItem` in `backend/app/schemas.py` (general-purpose: title, address,
tags, recurrence — no fixed category). An older `EventDraft`/`EventOut`
flow (`/chat`, `/event-draft/*`, `/registrations`) also still exists in
`services.py`/`routes.py` from an earlier iteration with a fixed-category
event model; it's unused by the current frontend but left in place. See
the docstrings at the top of each section in `services.py` for details —
don't be surprised to find what looks like two unrelated apps in one
backend.

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 20+ and npm
- (Optional) [LM Studio](https://lmstudio.ai/), [Ollama](https://ollama.com/),
  or another OpenAI-compatible server, if you want the local-LLM fallback
  to actually work rather than just fail through to Claude
- (Optional) Docker + Docker Compose, if you'd rather not install Python/Node locally

---

## Required setup: fill in your API keys

Copy the example env files first:

```bash
cd backend && cp .env.example .env
cd ../frontend && cp .env.example .env
```

**Two values in `backend/.env` need real credentials before the app will
actually do anything useful — everything else has a working default:**

1. **`ANTHROPIC_API_KEY`** — required for the primary LLM (Claude) to
   work at all. Get one at [console.anthropic.com](https://console.anthropic.com/).
   Without it, every request silently uses the local LLM instead (see
   the fallback behavior above) — the app won't crash, but it also won't
   use Claude.

2. **`SMTP_USERNAME` / `SMTP_PASSWORD`** — required for confirmation
   emails to actually send. Any SMTP provider works:
   - **Gmail**: enable 2-Step Verification, then create an
     [App Password](https://myaccount.google.com/apppasswords) — use
     that as `SMTP_PASSWORD`, not your regular Gmail password.
   - **SendGrid**: `SMTP_HOST=smtp.sendgrid.net`, `SMTP_USERNAME=apikey`,
     `SMTP_PASSWORD=<your SendGrid API key>`.
   - Without these set, `/api/submit` still works — it just skips
     sending an email and reports `"emailed": false`.

Everything else (`LOCAL_LLM_*`, `MAP_PROVIDER`, `MAPS_API_KEY`) has a
sensible default and is optional to change.

> **Never commit `.env` or share it outside your machine** — it holds
> live credentials. `.gitignore` already excludes it from git, but that
> doesn't protect against, say, zipping the whole folder to share
> elsewhere. Double-check before you do.

---

## Running it

### Option 1 — one command (recommended for local dev)

From the repo root:

```bash
uv run dev.py
```

This starts the backend (`uv run uvicorn app.main:app --reload --port 8000`)
and the frontend (`npm run dev`, installing `node_modules` automatically
on first run) together, and stops both on `Ctrl+C`.

- Backend: http://localhost:8000 (interactive API docs at `/docs`)
- Frontend: http://localhost:5173

### Option 2 — manually, in two terminals

```bash
# Terminal 1
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2
cd frontend
npm install
npm run dev
```

### Option 3 — Docker

```bash
docker compose up --build
```

Builds and runs both services together (backend on `:8000`, frontend on
`:5173` via nginx). The backend container reaches a local LLM on your
host machine through `host.docker.internal` — see `docker-compose.yml`.

---

## API endpoints actually used by the frontend

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/tags` | Controlled tag vocabulary |
| `POST` | `/api/extract` | The core chat turn: extracts fields from a message, merges into the draft |
| `POST` | `/api/geocode` | Re-geocodes after a manual address/city edit |
| `POST` | `/api/submit` | Sends a confirmation email (if an address was given); no persistence |

Full interactive docs (all endpoints, including the older unused
`EventDraft` flow) are available at `http://localhost:8000/docs` once the
backend is running.

---

## Testing & linting

```bash
cd backend
uv run ruff check .      # lint
uv run pytest            # tests (currently placeholder files, add real ones as the app grows)
```

```bash
cd frontend
npm run build             # type/build check via Vite
```

---

## Known limitations

- **No persistence.** Submitted entries are never saved anywhere; the
  "finished" state is a JSON blob the organizer copies out manually.
- **In-memory draft sessions** for the legacy `EventDraft` flow are lost
  on backend restart — a non-issue for the actively-used `/api/extract`
  flow, which is stateless by design (the frontend resends the whole
  draft each turn).
- **`frontend/tailwind.config.js` is currently dead weight** — Tailwind 4
  via the `@tailwindcss/vite` plugin does its own automatic content
  scanning and doesn't read this file. Verified by removing it and
  confirming an identical build output; left in place since deleting
  files wasn't asked for, but safe to delete if you want one less file.
- **`frontend/src/components/EventCard.jsx`, `EventList.jsx`, and
  `hooks/useEventSearch.js` are unused** by the current app — leftovers
  from an earlier event-browsing concept that predates the current
  chat-only flow. Safe to delete, or keep if you plan to revive event
  browsing later.
- **Docker's frontend build doesn't explicitly pass `VITE_API_BASE_URL`
  as a build arg** — Vite bakes env vars in at build time, and the
  Dockerfile currently relies on `client.js`'s hardcoded fallback
  (`http://localhost:8000`) happening to match the backend's Docker port.
  Works today, but is implicit rather than explicit; worth hardening with
  a proper `ARG`/`ENV` if this ever needs to point somewhere else.
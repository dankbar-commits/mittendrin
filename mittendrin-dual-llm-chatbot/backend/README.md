# Mittendrin Backend

FastAPI backend for the Mittendrin events chatbot. See the repo root
`README.md` for the full project overview (frontend + backend + how to
run both together).

## Run standalone

```
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## Endpoints

- `POST /api/extract` — chat-driven draft autofill (local LLM first,
  Claude fallback, see `app/clients/llm_client.py`)
- `POST /api/geocode` — re-geocode after manual address edits
- `POST /api/submit` — sends a confirmation email if the draft has one
  on file; no persistence yet
- `GET /api/tags` — allowed tag vocabulary

## Tests

```
uv run pytest
```
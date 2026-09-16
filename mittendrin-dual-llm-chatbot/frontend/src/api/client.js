/**
 * Thin fetch wrapper around the FastAPI backend (backend/app/routes.py).
 * Base URL comes from VITE_API_BASE_URL (see .env) since the two run as
 * separate processes on separate ports — cross-origin, so the backend
 * needs CORS enabled (see backend/app/main.py's CORSMiddleware).
 *
 * NOTE: Vite only reads .env at dev-server startup — if you change
 * VITE_API_BASE_URL, restart `npm run dev` (a hot-reload is NOT enough).
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** GET /api/tags — the controlled tag vocabulary. Falls back to an empty
 * list on any network error; the tag picker just shows nothing to pick
 * from rather than crashing the page. */
export async function fetchTags() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/tags`);
        if (!res.ok) return [];
        const data = await res.json();
        return data.tags ?? [];
    } catch {
        return [];
    }
}

/**
 * POST /api/extract — the one LLM call per turn. Returns the same
 * { ok: true, draft } | { ok: false, error } shape the backend sends;
 * never throws for an application-level failure (bad model output, rate
 * limit, etc.) — only a genuine network failure produces a rejected
 * promise, which callers should catch.
 */
export async function extract(draft, message) {
    const res = await fetch(`${API_BASE_URL}/api/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft, message }),
    });
    return res.json();
}

/**
 * POST /api/geocode — re-resolves coordinates when the person edits the
 * address/city fields directly, independent of the chat/extract flow.
 * Same { ok, ... } shape as extract(); on ok:true, `location` is either
 * { address, latitude, longitude } or null (address didn't resolve).
 */
export async function geocode(address, city) {
    const res = await fetch(`${API_BASE_URL}/api/geocode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address, city }),
    });
    return res.json();
}

/**
 * POST /api/submit — no persistence yet, just triggers a confirmation
 * email if the draft has an email address on file. { ok, emailed }.
 */
export async function submitDraft(draft) {
    const res = await fetch(`${API_BASE_URL}/api/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft }),
    });
    return res.json();
}
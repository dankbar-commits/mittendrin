/**
 * Not wired to any current feature. The app has no listing or search of
 * existing events — it builds and submits exactly one draft at a time (see
 * README, "Out of scope"). This file exists to match the requested
 * scaffold; it's an inert placeholder, not a real implementation — filling
 * it with a fake search would invent product scope nobody asked for.
 *
 * If a real event search gets built later, EventList.jsx / EventCard.jsx
 * are the components that would consume it.
 */
export function useEventSearch() {
  return { results: [], loading: false, error: null, search: () => {} };
}

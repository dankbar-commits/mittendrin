/**
 * Frontend copy of ../../../lib/client/buildItem.ts (JS port, same logic).
 * Assembles the strict submit-time Item shape from the running draft.
 * Validate the result against ItemSchema before trusting it — this
 * function alone does not guarantee validity (e.g. title may be "").
 */

import { serializeRecurringEvent } from "./recurring";

export function buildItem(draft) {
  return {
    title: draft.title ?? "",
    state: "suggestion",
    brief: draft.brief ?? { de: "" },
    description: draft.description ?? { de: "" },
    location: draft.location,
    address: draft.address,
    zip: draft.zip,
    city: draft.city,
    website: draft.website,
    onlineOnly: draft.onlineOnly,
    email: draft.email,
    phone: draft.phone,
    mobile: draft.mobile,
    contact: draft.contact,
    responsibleInstitution: draft.responsibleInstitution,
    sponsors: draft.sponsors,
    hours: draft.hours,
    charge: draft.charge,
    accessibility: draft.accessibility,
    directions: draft.directions,
    venue: draft.venue,
    image: draft.image,
    tags: draft.tags.length > 0 ? draft.tags : undefined,
    recurring_event: draft.recurringEvent.length > 0 ? serializeRecurringEvent(draft.recurringEvent) : undefined,
    // Set by the backend's auto-geocode step (lib/server/geocode.ts), not
    // by the LLM extraction — forward whatever the draft carries rather
    // than hardcoding null (this used to always be null, back when
    // lat/lng really were always null — see lib/schema.ts's comment).
    latitude: draft.latitude,
    longitude: draft.longitude,
  };
}

/**
 * Deterministic field metadata: which of the four tabs a field lives in,
 * its label/hint, and whether it's required. The model never decides any
 * of this — RegistrationForm.jsx only ever renders a slot listed here, and
 * only once it's satisfied (see RegistrationForm.jsx's "only extracted
 * fields are shown" filter).
 *
 * `tags` is deliberately NOT a slot here — the field still exists on the
 * draft (`draft.tags`), the backend still extracts it
 * (lib/server/prompt.ts) and it's still included in the final submitted
 * Item (buildItem.js), it's just never shown or editable in the UI. Add a
 * slot back here (category "general", inputType "tags", isSatisfied:
 * d => d.tags.length > 0) if that changes.
 */

/** The four tabs shown at the top of the page. */
export const CATEGORY_ORDER = ["general", "location", "time", "more"];

export const CATEGORY_LABELS = {
  general: "Allgemeine Infos",
  location: "Ort",
  time: "Zeit",
  more: "Weitere Infos",
};

const filled = (v) => v !== null && v !== undefined && v !== "";

export const QUESTION_SLOTS = [
  // ---- Allgemeine Infos --------------------------------------------------
  {
    id: "title",
    fields: ["title"],
    required: true,
    category: "general",
    label: "Titel",
    hint: "Wird als Vorschlag generiert, wenn kein Eigenname im Text steht — bei Bedarf anpassen.",
    inputType: "text",
    isSatisfied: (d) => filled(d.title),
  },
  {
    id: "brief",
    fields: ["brief"],
    required: true,
    category: "general",
    label: "Untertitel / Kurzbeschreibung (Suchergebnisse)",
    hint: "1–2 Sätze, wie ein Teaser. Wird als Vorschlag generiert.",
    inputType: "textarea",
    isSatisfied: (d) => filled(d.brief?.de),
  },
  {
    id: "description",
    fields: ["description"],
    required: true,
    category: "general",
    label: "Beschreibung",
    hint: "Alltagssprache, keine Fachbegriffe, kein Werbeton. Wird als Vorschlag generiert.",
    inputType: "textarea",
    isSatisfied: (d) => filled(d.description?.de),
  },
  {
    id: "responsibleInstitution",
    fields: ["responsibleInstitution"],
    required: false,
    category: "general",
    label: "Verantwortliche Institution",
    inputType: "text",
    isSatisfied: (d) => filled(d.responsibleInstitution),
  },
  {
    id: "sponsors",
    fields: ["sponsors"],
    required: false,
    category: "general",
    label: "Förderer / Unterstützer",
    inputType: "text",
    isSatisfied: (d) => filled(d.sponsors),
  },
  {
    id: "image",
    fields: ["image"],
    required: false,
    category: "general",
    label: "Bild",
    hint: "Bild-Upload folgt später — hier vorerst eine Bild-URL.",
    inputType: "text",
    isSatisfied: (d) => filled(d.image),
  },

  // ---- Ort ----------------------------------------------------------------
  {
    id: "locating",
    fields: ["address", "city", "website", "onlineOnly"],
    required: true,
    category: "location",
    label: "Auffindbarkeit (Adresse / Website / online)",
    hint: "Mindestens eins wird gebraucht: vollständige Adresse, oder Website, oder „nur online“.",
    inputType: "text",
    isSatisfied: (d) => Boolean((filled(d.address) && filled(d.city)) || filled(d.website) || d.onlineOnly === true),
  },
  {
    id: "location",
    fields: ["location"],
    required: false,
    category: "location",
    label: "Name des Orts / der Einrichtung",
    hint: "z. B. „Sozialstation Torstraße“, falls anders als der Titel.",
    inputType: "text",
    isSatisfied: (d) => filled(d.location),
  },
  {
    id: "zip",
    fields: ["zip"],
    required: false,
    category: "location",
    label: "PLZ",
    inputType: "text",
    isSatisfied: (d) => filled(d.zip),
  },
  {
    id: "website",
    fields: ["website"],
    required: false,
    category: "location",
    label: "Website",
    inputType: "text",
    isSatisfied: (d) => filled(d.website),
  },
  {
    id: "venue",
    fields: ["venue"],
    required: false,
    category: "location",
    label: "Beschreibung des Orts",
    hint: "Raum, Ausstattung, Atmosphäre.",
    inputType: "textarea",
    isSatisfied: (d) => filled(d.venue?.de),
  },
  {
    id: "directions",
    fields: ["directions"],
    required: false,
    category: "location",
    label: "Wegbeschreibung",
    inputType: "textarea",
    isSatisfied: (d) => filled(d.directions?.de),
  },

  // ---- Zeit -----------------------------------------------------------
  {
    id: "hoursOrRecurring",
    fields: ["hours", "recurringEvent"],
    required: false,
    category: "time",
    label: "Öffnungszeiten / Termin(e)",
    hint: "Bei Wiederholung reicht z. B. „jeden Donnerstag 19–21 Uhr“.",
    inputType: "recurring",
    isSatisfied: (d) => filled(d.hours?.de) || d.recurringEvent.length > 0,
  },

  // ---- Weitere Infos --------------------------------------------------
  {
    id: "charge",
    fields: ["charge"],
    required: false,
    category: "more",
    label: "Kosten",
    hint: "Bei kostenlos reicht „kostenlos“ oder „Eintritt frei“.",
    inputType: "text",
    isSatisfied: (d) => filled(d.charge?.de),
  },
  {
    id: "accessibility",
    fields: ["accessibility"],
    required: false,
    category: "more",
    label: "Barrierefreiheit",
    inputType: "text",
    isSatisfied: (d) => filled(d.accessibility?.de),
  },
  {
    id: "email",
    fields: ["email"],
    required: false,
    category: "more",
    label: "E-Mail",
    inputType: "text",
    isSatisfied: (d) => filled(d.email),
  },
  {
    id: "phone",
    fields: ["phone"],
    required: false,
    category: "more",
    label: "Telefon",
    inputType: "text",
    isSatisfied: (d) => filled(d.phone),
  },
  {
    id: "mobile",
    fields: ["mobile"],
    required: false,
    category: "more",
    label: "Mobil",
    inputType: "text",
    isSatisfied: (d) => filled(d.mobile),
  },
  {
    id: "contact",
    fields: ["contact"],
    required: false,
    category: "more",
    label: "Ansprechperson",
    inputType: "text",
    isSatisfied: (d) => filled(d.contact),
  },
];

const I18N_PATHS = {
  brief: "brief.de",
  description: "description.de",
  hours: "hours.de",
  charge: "charge.de",
  accessibility: "accessibility.de",
  directions: "directions.de",
  venue: "venue.de",
};

/** Maps a draft key to the path string used in the model's `inferred` list. */
export function fieldPath(key) {
  return I18N_PATHS[key] ?? String(key);
}

const I18N_FIELDS = new Set(["brief", "description", "hours", "charge", "accessibility", "directions", "venue"]);
export function isI18nField(key) {
  return I18N_FIELDS.has(key);
}

export function slotStatus(slot, draft) {
  if (!slot.isSatisfied(draft)) return "missing";
  const inferred = slot.fields.some((f) => draft.inferredFields.includes(fieldPath(f)));
  return inferred ? "inferred" : "filled";
}

export function slotsByCategory(category) {
  return QUESTION_SLOTS.filter((s) => s.category === category);
}

/** Count of unsatisfied required slots within one tab — drives the tab's red badge. */
export function missingCountByCategory(category, draft) {
  return slotsByCategory(category).filter((s) => s.required && !s.isSatisfied(draft)).length;
}

/** All required slots still missing — drives the submit gate. */
export function missingRequired(draft) {
  return QUESTION_SLOTS.filter((s) => s.required && !s.isSatisfied(draft));
}

export function isSubmittable(draft) {
  return missingRequired(draft).length === 0;
}

/** Slots whose underlying field(s) changed between two drafts. Currently
 * unused — it used to back a "Erkannt/aktualisiert: …" chat message
 * (context/ChatContext.jsx), which was removed on request: the chat only
 * asks (see followUpQuestions() below), it doesn't narrate what changed —
 * that's what the tabs (RegistrationForm.jsx) are for. Left in place as a
 * genuinely reusable diff utility, not dead-code cruft. */
export function touchedSlots(before, after) {
  return QUESTION_SLOTS.filter((slot) => slot.fields.some((f) => JSON.stringify(before[f]) !== JSON.stringify(after[f])));
}

/**
 * Deterministic, non-blocking follow-up questions about Ort/Zeit — the two
 * fields worth actively nudging on, since a real address and a clear time
 * are what make an entry actually useful. Still a plain lookup table, not
 * the model deciding what to ask (same principle as the rest of this
 * file): "missing" is the existing isSatisfied() check; "imprecise" is
 * approximated by "address" showing up in draft.inferredFields — i.e. the
 * backend auto-filled it via a Nominatim geocoding lookup rather than
 * reading it verbatim from the text (see lib/server/geocode.ts; the LLM
 * itself never guesses an address, see lib/server/prompt.ts rule 1), so
 * it's worth a confirmation — the lookup could still be the wrong branch
 * of a chain, or no match to a same-named place elsewhere. There's no
 * equivalent signal for imprecise *time* text (e.g. "nachmittags") — only
 * the missing case is covered there. Called after every extraction turn in
 * context/ChatContext.jsx; each returned question becomes its own chat
 * bubble. Non-blocking: nothing about this gates the input or the tabs.
 */
export function followUpQuestions(draft) {
  const questions = [];

  const locating = QUESTION_SLOTS.find((s) => s.id === "locating");
  if (!locating.isSatisfied(draft)) {
    questions.push(
      "Wo genau findet das statt? Am besten Straße und Hausnummer, oder eine Website — oder sag, falls es nur online stattfindet.",
    );
  } else if (draft.inferredFields.includes("address")) {
    questions.push("Ich hab automatisch eine Adresse dazu gefunden — passt die so, oder hast du eine andere?");
  }

  const time = QUESTION_SLOTS.find((s) => s.id === "hoursOrRecurring");
  if (!time.isSatisfied(draft)) {
    questions.push("Wann genau findet das statt? Einmalig, regelmäßig, feste Öffnungszeiten — was trifft zu?");
  }

  return questions;
}

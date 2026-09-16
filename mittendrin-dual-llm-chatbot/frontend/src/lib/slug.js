/**
 * Frontend copy of ../../../lib/client/slug.ts (JS port, same logic).
 * Slug generation for the AdapterData itemsRecord key. Prototype-simple: no
 * collision handling since there's only ever one item per submission.
 */
export function slugFromTitle(title) {
  const base = title
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "") // strip remaining diacritics
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return base || "eintrag";
}

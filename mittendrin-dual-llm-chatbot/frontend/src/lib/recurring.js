/**
 * Frontend copy of ../../../lib/client/recurring.ts (JS port, same logic).
 */

/**
 * Serializes the structured rules the model/UI work with into the final
 * on-the-wire shape: a JSON string of positional tuples, e.g.
 *   '[["weekly","thu","19:00","21:00",null]]'
 * This is the ONLY place that string gets produced — never let the model
 * write it directly (see task brief: models get the positional format wrong).
 */
export function serializeRecurringEvent(rules) {
  const tuples = rules.map((r) => [r.interval, r.day, r.start, r.end, r.exampleDate]);
  return JSON.stringify(tuples);
}

const INTERVAL_LABELS = {
  fixed: "einmalig",
  daily: "täglich",
  "mon-fri": "werktags (Mo–Fr)",
  weekly: "jede Woche",
  "bi-weekly": "alle zwei Wochen",
  "three-weekly": "alle drei Wochen",
  "four-weekly": "alle vier Wochen",
  first_of_month: "am ersten",
  second_of_month: "am zweiten",
  third_of_month: "am dritten",
  fourth_of_month: "am vierten",
  last_of_month: "am letzten",
};

const DAY_LABELS = {
  mon: "Montag",
  tue: "Dienstag",
  wed: "Mittwoch",
  thu: "Donnerstag",
  fri: "Freitag",
  sat: "Samstag",
  sun: "Sonntag",
};

const MONTHLY_INTERVALS = new Set([
  "first_of_month",
  "second_of_month",
  "third_of_month",
  "fourth_of_month",
  "last_of_month",
]);

/** Human-readable German rendering for the UI — never show the raw tuple/string to the user. */
export function humanReadableRule(rule) {
  const time = rule.start && rule.end ? `, ${rule.start}–${rule.end} Uhr` : rule.start ? `, ab ${rule.start} Uhr` : "";

  if (rule.interval === "fixed") {
    const date = rule.exampleDate ? ` am ${rule.exampleDate}` : "";
    return `einmalig${date}${time}`;
  }

  if (MONTHLY_INTERVALS.has(rule.interval)) {
    const day = rule.day ? ` ${DAY_LABELS[rule.day]}` : "";
    return `${INTERVAL_LABELS[rule.interval]}${day} im Monat${time}`;
  }

  if (rule.interval === "daily" || rule.interval === "mon-fri") {
    return `${INTERVAL_LABELS[rule.interval]}${time}`;
  }

  // weekly / bi-weekly / three-weekly / four-weekly
  const day = rule.day ? ` ${DAY_LABELS[rule.day]}` : "";
  const prefix = rule.interval === "weekly" ? "jeden" : INTERVAL_LABELS[rule.interval];
  return rule.interval === "weekly" ? `jeden${day}${time}` : `${prefix}${day}${time}`;
}

export function humanReadableRules(rules) {
  if (rules.length === 0) return "";
  return rules.map(humanReadableRule).join("; ");
}

export function emptyRule() {
  return { interval: "weekly", day: "thu", start: null, end: null, exampleDate: null };
}

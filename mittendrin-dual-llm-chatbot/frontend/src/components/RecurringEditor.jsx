import { DAY_VALUES, INTERVAL_VALUES } from "../lib/schema";
import { emptyRule, humanReadableRule } from "../lib/recurring";

const INTERVAL_LABELS = {
  fixed: "einmalig",
  daily: "täglich",
  "mon-fri": "werktags (Mo–Fr)",
  weekly: "wöchentlich",
  "bi-weekly": "alle 2 Wochen",
  "three-weekly": "alle 3 Wochen",
  "four-weekly": "alle 4 Wochen",
  first_of_month: "1. im Monat",
  second_of_month: "2. im Monat",
  third_of_month: "3. im Monat",
  fourth_of_month: "4. im Monat",
  last_of_month: "letzter im Monat",
};

const DAY_LABELS = {
  mon: "Mo",
  tue: "Di",
  wed: "Mi",
  thu: "Do",
  fri: "Fr",
  sat: "Sa",
  sun: "So",
};

export default function RecurringEditor({ rules, onChange }) {
  const updateRule = (index, patch) => {
    const next = rules.map((r, i) => (i === index ? { ...r, ...patch } : r));
    onChange(next);
  };

  const removeRule = (index) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-2">
      {rules.map((rule, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2 rounded-xl border border-(--color-border) bg-white p-2 text-sm">
          <select
            className="rounded-xl border border-(--color-border) px-1.5 py-1"
            value={rule.interval}
            onChange={(e) => updateRule(i, { interval: e.target.value })}
          >
            {INTERVAL_VALUES.map((v) => (
              <option key={v} value={v}>
                {INTERVAL_LABELS[v]}
              </option>
            ))}
          </select>

          {rule.interval !== "fixed" && (
            <select
              className="rounded-xl border border-(--color-border) px-1.5 py-1"
              value={rule.day ?? ""}
              onChange={(e) => updateRule(i, { day: e.target.value || null })}
            >
              <option value="">Tag –</option>
              {DAY_VALUES.map((d) => (
                <option key={d} value={d}>
                  {DAY_LABELS[d]}
                </option>
              ))}
            </select>
          )}

          {rule.interval === "fixed" && (
            <input
              type="date"
              className="rounded-xl border border-(--color-border) px-1.5 py-1"
              value={rule.exampleDate ?? ""}
              onChange={(e) => updateRule(i, { exampleDate: e.target.value || null })}
            />
          )}

          <input
            type="time"
            className="w-24 rounded-xl border border-(--color-border) px-1.5 py-1"
            value={rule.start ?? ""}
            onChange={(e) => updateRule(i, { start: e.target.value || null })}
          />
          <span className="text-(--color-ink-muted)">–</span>
          <input
            type="time"
            className="w-24 rounded-xl border border-(--color-border) px-1.5 py-1"
            value={rule.end ?? ""}
            onChange={(e) => updateRule(i, { end: e.target.value || null })}
          />

          <button
            type="button"
            onClick={() => removeRule(i)}
            className="ml-auto text-xs text-(--color-required-missing) hover:underline"
          >
            entfernen
          </button>

          <div className="w-full text-xs text-(--color-ink-muted)">{humanReadableRule(rule)}</div>
        </div>
      ))}

      <button
        type="button"
        onClick={() => onChange([...rules, emptyRule()])}
        className="rounded-xl border border-dashed border-(--color-border) px-2 py-1 text-xs text-(--color-ink-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
      >
        + Termin/Regel hinzufügen
      </button>
    </div>
  );
}

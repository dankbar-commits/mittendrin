import { memo, useRef, useState } from "react";
import { useChat } from "../hooks/useChat";
import { CATEGORY_LABELS, CATEGORY_ORDER, isI18nField, missingCountByCategory, slotsByCategory, slotStatus } from "../lib/questions";
import { geocode as geocodeApi } from "../api/client";
import RecurringEditor from "./RecurringEditor";

// The form you fill out to submit ("register") an entry — the port of the
// Next.js prototype's FieldTabs.tsx, renamed to fit this scaffold. Reads
// its state from useChat() rather than props, since the draft is shared
// with ChatWindow via ChatContext.

// Only ever rendered for satisfied slots (see the filter below) — "missing"
// never actually shows as a row, but the keys stay so slotStatus() and
// missingCountByCategory() (still used for the tab badges + the "Es fehlen
// noch" summary) keep a consistent status vocabulary.
const STATUS_STYLES = {
    missing: "border-l-(--color-required-missing) bg-(--color-required-missing-bg)",
    inferred: "border-l-(--color-inferred) bg-(--color-inferred-bg)",
    filled: "border-l-(--color-filled) bg-white",
};

const STATUS_LABEL = {
    missing: "fehlt",
    // Covers two different sources — a model-generated suggestion (title/
    // brief/description) and a server-side lookup (address/zip/coordinates
    // via geocoding, see lib/server/geocode.ts) — neither is verbatim from
    // what was typed, so both get the same "please check" treatment.
    inferred: "automatisch ermittelt, bitte prüfen",
    filled: "ok",
};

// Memoized so typing anywhere else in the form (which re-renders
// RegistrationForm on every keystroke) doesn't touch this — only an
// actual change in latitude/longitude re-renders the iframe.
const LocationMap = memo(function LocationMap({ latitude, longitude }) {
    if (latitude == null || longitude == null) return null;
    return (
        <div className="sm:col-span-2">
            <iframe
                title="Standort auf der Karte"
                className="w-full rounded-xl border border-(--color-border)"
                style={{ height: "220px" }}
                loading="lazy"
                src={`https://www.openstreetmap.org/export/embed.html?bbox=${longitude - 0.01}%2C${latitude - 0.01}%2C${longitude + 0.01}%2C${latitude + 0.01}&layer=mapnik&marker=${latitude}%2C${longitude}`}
            />
            <a
                href={`https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=16/${latitude}/${longitude}`}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-block text-xs text-(--color-accent) underline"
            >
                Größere Karte öffnen
            </a>
        </div>
    );
});

// Hoisted to module scope, not defined inside RegistrationForm — a
// component defined inline in a parent's function body gets a new
// identity on every parent re-render, which makes React unmount and
// remount it (and any focused input inside it) on every keystroke.
const Field = memo(function Field({ slot, status, children }) {
    return (
        <div className={`rounded-r-2xl border-l-4 px-3 py-2 ${STATUS_STYLES[status]}`}>
            <div className="mb-1 flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{slot.label}</span>
                <span className="shrink-0 text-xs font-normal text-(--color-ink-muted)">{STATUS_LABEL[status]}</span>
            </div>
            {slot.hint && <p className="mb-1 text-xs text-(--color-ink-muted)">{slot.hint}</p>}
            {children}
        </div>
    );
});

export default function RegistrationForm() {
    const { draft, updateDraft, submit, submittable, stillMissing } = useChat();
    const [activeTab, setActiveTab] = useState("general");

    // Geocodes only when the person presses Enter or leaves the field
    // (blur) — never automatically while typing. A timing-based debounce
    // still fired mid-typing for anyone with normal pauses between
    // characters, which read as "refreshing on every keystroke."
    const latestFieldsRef = useRef({ address: "", city: "" });

    const runGeocode = async () => {
        const { address, city } = latestFieldsRef.current;
        if (!address || !city) return;
        try {
            const data = await geocodeApi(address, city);
            if (data.ok && data.location) {
                updateDraft({ latitude: data.location.latitude, longitude: data.location.longitude }, []);
            }
        } catch {
            // Silent — the address text stays exactly as typed either way,
            // the map preview just won't update. Not worth a form-level error.
        }
    };

    const handleGeocodeKeyDown = (e) => {
        if (e.key === "Enter") {
            e.preventDefault(); // don't submit the form on Enter
            runGeocode();
        }
    };

    const setField = (key, value) => {
        if (isI18nField(key)) {
            updateDraft({ [key]: value ? { de: value } : null }, [key]);
        } else {
            updateDraft({ [key]: value || null }, [key]);
        }
    };

    const getFieldValue = (key) => {
        const v = draft[key];
        if (v && typeof v === "object" && "de" in v) {
            return String(v.de ?? "");
        }
        return v == null ? "" : String(v);
    };

    latestFieldsRef.current = { address: getFieldValue("address"), city: getFieldValue("city") };

    const renderEditor = (slot) => {
        switch (slot.id) {
            case "locating":
                return (
                    <div className="grid gap-1.5 sm:grid-cols-2">
                        <input
                            className="rounded-xl border border-(--color-border) px-2 py-1 text-sm"
                            placeholder="Straße, Hausnummer"
                            value={getFieldValue("address")}
                            onChange={(e) => {
                                updateDraft({ address: e.target.value || null }, ["address"]);
                                latestFieldsRef.current = { ...latestFieldsRef.current, address: e.target.value };
                            }}
                            onKeyDown={handleGeocodeKeyDown}
                            onBlur={runGeocode}
                        />
                        <input
                            className="rounded-xl border border-(--color-border) px-2 py-1 text-sm"
                            placeholder="Ort"
                            value={getFieldValue("city")}
                            onChange={(e) => {
                                updateDraft({ city: e.target.value || null }, ["city"]);
                                latestFieldsRef.current = { ...latestFieldsRef.current, city: e.target.value };
                            }}
                            onKeyDown={handleGeocodeKeyDown}
                            onBlur={runGeocode}
                        />
                        <input
                            className="rounded-xl border border-(--color-border) px-2 py-1 text-sm sm:col-span-2"
                            placeholder="Website (alternativ)"
                            value={getFieldValue("website")}
                            onChange={(e) => updateDraft({ website: e.target.value || null }, ["website"])}
                        />
                        <label className="flex items-center gap-1.5 text-sm sm:col-span-2">
                            <input
                                type="checkbox"
                                checked={draft.onlineOnly === true}
                                onChange={(e) => updateDraft({ onlineOnly: e.target.checked || null }, ["onlineOnly"])}
                            />
                            findet nur online statt (kein physischer Ort)
                        </label>
                        {draft.latitude != null && draft.longitude != null && (
                            <LocationMap latitude={draft.latitude} longitude={draft.longitude} />
                        )}
                    </div>
                );

            case "hoursOrRecurring":
                return (
                    <div className="space-y-2">
                        <RecurringEditor
                            rules={draft.recurringEvent}
                            onChange={(rules) => updateDraft({ recurringEvent: rules }, ["recurringEvent"])}
                        />
                        <div>
                            <span className="text-xs text-(--color-ink-muted)">oder als Freitext:</span>
                            <textarea
                                className="mt-1 w-full rounded-xl border border-(--color-border) px-2 py-1 text-sm"
                                rows={2}
                                value={getFieldValue("hours")}
                                onChange={(e) => setField("hours", e.target.value)}
                            />
                        </div>
                    </div>
                );

            default: {
                const key = slot.fields[0];
                if (slot.inputType === "textarea") {
                    return (
                        <textarea
                            className="w-full rounded-xl border border-(--color-border) px-2 py-1 text-sm"
                            rows={3}
                            value={getFieldValue(key)}
                            onChange={(e) => setField(key, e.target.value)}
                        />
                    );
                }
                return (
                    <input
                        className="w-full rounded-xl border border-(--color-border) px-2 py-1 text-sm"
                        value={getFieldValue(key)}
                        onChange={(e) => setField(key, e.target.value)}
                    />
                );
            }
        }
    };

    return (
        <section className="rounded-2xl bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-xs text-(--color-ink-muted)">
                    Was bisher erkannt wurde — bei Bedarf direkt anpassen. Was noch fehlt, steht unten und als Zahl am Reiter.
                </p>
                <button
                    onClick={submit}
                    disabled={!submittable}
                    className="shrink-0 rounded-xl bg-(--color-accent) px-4 py-1.5 text-sm font-medium text-(--color-accent-contrast) disabled:opacity-40"
                >
                    Eintrag absenden
                </button>
            </div>

            <div className="flex flex-wrap gap-1 border-b border-(--color-border)">
                {CATEGORY_ORDER.map((cat) => {
                    const missing = missingCountByCategory(cat, draft);
                    const active = cat === activeTab;
                    return (
                        <button
                            key={cat}
                            type="button"
                            onClick={() => setActiveTab(cat)}
                            className={
                                "relative -mb-px flex items-center gap-1.5 rounded-t-2xl border border-b-0 px-3 py-1.5 text-sm " +
                                (active
                                    ? "border-(--color-border) bg-white font-medium text-(--color-ink)"
                                    : "border-transparent text-(--color-ink-muted) hover:text-(--color-ink)")
                            }
                        >
                            {CATEGORY_LABELS[cat]}
                            {missing > 0 && (
                                <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-(--color-required-missing) px-1 text-[10px] font-semibold text-white">
                                    {missing}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>

            <div className="space-y-2 border border-t-0 border-(--color-border) p-3">
                {(() => {
                    const extracted = slotsByCategory(activeTab).filter((slot) => slot.isSatisfied(draft));
                    if (extracted.length === 0) {
                        return <p className="text-sm text-(--color-ink-muted)">Hier ist noch nichts erkannt worden.</p>;
                    }
                    return extracted.map((slot) => (
                        <Field key={slot.id} slot={slot} status={slotStatus(slot, draft)}>
                            {renderEditor(slot)}
                        </Field>
                    ));
                })()}
            </div>

            {!submittable && (
                <p className="mt-2 text-xs text-(--color-ink-muted)">
                    Es fehlen noch: {stillMissing.map((s) => s.label).join(", ")}
                </p>
            )}
        </section>
    );
}
import { createContext, useState } from "react";
import { emptyDraft, ItemSchema, AdapterDataSchema } from "../lib/schema";
import { fieldPath, followUpQuestions, isSubmittable, missingRequired } from "../lib/questions";
import { buildItem } from "../lib/buildItem";
import { slugFromTitle } from "../lib/slug";
import { extract as extractApi, submitDraft } from "../api/client";

export const MAX_TURNS = 8;
export const MAX_MESSAGE_LENGTH = 2000;

// The single source of truth for the draft + chat log + submit state.
// Consume it via the useChat() hook (hooks/useChat.js), never
// useContext(ChatContext) directly outside of that hook.
export const ChatContext = createContext(null);

export function ChatProvider({ children }) {
    const [draft, setDraft] = useState(() => emptyDraft());
    const [log, setLog] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [resultJson, setResultJson] = useState(null);
    const [emailStatus, setEmailStatus] = useState(null); // null | "sent" | "skipped" | "error"

    // Tags are still extracted by the backend and still submitted (see
    // lib/server/prompt.ts, lib/buildItem.js) — GET /api/tags (fetchTags in
    // ../api/client.js) is just no longer called here, since nothing in the
    // UI displays or edits tags anymore (see RegistrationForm.jsx / README
    // "dont show the tags at all"). Bring fetchTags() back if a tag editor
    // returns.

    const pushLog = (entry) => setLog((l) => [...l, entry]);

    // Same merge policy as the Next.js version (app/page.tsx before the
    // split): editing a field directly clears its "inferred" (amber) flag,
    // since the user just confirmed/overwrote it themselves.
    function updateDraft(patch, touchedFields) {
        setDraft((d) => {
            const next = { ...d, ...patch };
            const touchedPaths = touchedFields.map(fieldPath);
            next.inferredFields = d.inferredFields.filter((p) => !touchedPaths.includes(p));
            return next;
        });
    }

    async function sendMessage(message) {
        const trimmed = message.trim();
        if (!trimmed || trimmed.length > MAX_MESSAGE_LENGTH || draft.turnCount >= MAX_TURNS || loading) return;

        setLoading(true);
        setError(null);
        pushLog({ role: "user", text: trimmed });

        try {
            const data = await extractApi(draft, trimmed);
            if (data.ok) {
                setDraft(data.draft);
                // No "Erkannt/aktualisiert: …" confirmation — what was recognized
                // is visible directly in the tabs (RegistrationForm.jsx), not
                // repeated in the chat. The chat only ever asks; it doesn't
                // narrate. Non-blocking either way: these are just extra bubbles,
                // not a gate — the fields stay editable and the tabs stay usable
                // whether or not a follow-up fires.
                for (const question of followUpQuestions(data.draft)) {
                    pushLog({ role: "assistant", text: question });
                }
            } else {
                setError(data.error);
                pushLog({ role: "system", text: `Fehler: ${data.error}` });
            }
        } catch {
            setError("Netzwerkfehler — ist der Server erreichbar?");
            pushLog({ role: "system", text: "Fehler: Netzwerkfehler." });
        } finally {
            setLoading(false);
        }
    }

    function submit() {
        setError(null);
        const item = buildItem(draft);
        const parsedItem = ItemSchema.safeParse(item);
        if (!parsedItem.success) {
            setError("Eintrag ist noch nicht vollständig: " + parsedItem.error.issues.map((i) => i.message).join("; "));
            return;
        }

        const adapterData = {
            adapter: { name: "web-form", sourceName: "Nutzereingabe (Prototyp)" },
            lastUpdate: Date.now(),
            itemsRecord: { [slugFromTitle(parsedItem.data.title)]: parsedItem.data },
        };
        const parsedAdapter = AdapterDataSchema.safeParse(adapterData);
        if (!parsedAdapter.success) {
            setError("Interner Validierungsfehler beim Zusammenbauen des Eintrags.");
            return;
        }

        setResultJson(JSON.stringify(parsedAdapter.data, null, 2));

        // Best-effort, fire-and-forget — a failed or skipped email never
        // blocks showing the JSON above; still a pure local prototype
        // otherwise (see the "no persistence" note in ResultView).
        setEmailStatus(null);
        submitDraft(draft)
            .then((data) => setEmailStatus(data.ok && data.emailed ? "sent" : "skipped"))
            .catch(() => setEmailStatus("error"));
    }

    const value = {
        draft,
        log,
        loading,
        error,
        resultJson,
        emailStatus,
        submittable: isSubmittable(draft),
        stillMissing: missingRequired(draft),
        updateDraft,
        sendMessage,
        submit,
        resetResult: () => {
            setResultJson(null);
            setEmailStatus(null);
        },
    };

    return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}
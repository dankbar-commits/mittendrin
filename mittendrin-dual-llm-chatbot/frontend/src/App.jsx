import { useState } from "react";
import { ChatProvider } from "./context/ChatContext";
import { useChat } from "./hooks/useChat";
import RegistrationForm from "./components/RegistrationForm";
import ChatWindow from "./components/ChatWindow";

function ResultView() {
    const { resultJson, resetResult, emailStatus } = useChat();
    const [copied, setCopied] = useState(false);

    async function handleCopy() {
        await navigator.clipboard.writeText(resultJson);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    }

    const EMAIL_STATUS_TEXT = {
        sent: "Bestätigungs-E-Mail wurde verschickt.",
        skipped: "Keine Bestätigungs-E-Mail — keine E-Mail-Adresse angegeben.",
        error: "Bestätigungs-E-Mail konnte nicht verschickt werden.",
    };

    return (
        <section className="rounded-2xl border border-(--color-border) bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
                <h2 className="text-lg font-extrabold">Eintrag bereit</h2>
                <div className="flex gap-2">
                    <button
                        onClick={handleCopy}
                        className="rounded-xl bg-(--color-accent) px-3 py-1.5 text-sm text-(--color-accent-contrast) hover:opacity-90"
                    >
                        {copied ? "Kopiert ✓" : "JSON kopieren"}
                    </button>
                    <button
                        onClick={resetResult}
                        className="rounded-xl border border-(--color-border) px-3 py-1.5 text-sm hover:bg-(--color-bg)"
                    >
                        Zurück zur Bearbeitung
                    </button>
                </div>
            </div>
            {emailStatus && (
                <p className="mb-2 text-xs text-(--color-ink-muted)">{EMAIL_STATUS_TEXT[emailStatus]}</p>
            )}
            <pre className="max-h-[70vh] overflow-auto rounded-xl bg-[#1e1c19] p-4 text-xs text-[#f3f1ec]">{resultJson}</pre>
            <p className="mt-3 text-xs text-(--color-ink-muted)">
                Es findet keine Speicherung statt — dies ist ein reiner Prototyp. Kein Datenbank-Backend angebunden.
            </p>
        </section>
    );
}

function AppShell() {
    const { draft, resultJson } = useChat();
    const hasContent = draft.turnCount > 0;

    return (
        <main className="mx-auto max-w-5xl px-4 py-8">
            <header className="mb-6">
                <h1 className="text-2xl font-extrabold tracking-tight">
                    mittendrin.<span className="text-(--color-accent-secondary)">in Brandenburg</span> – Eintrag per
                    Text
                </h1>
                <p className="mt-1 text-sm text-(--color-ink-muted)">
                    Beschreib dein Angebot im Chat — egal wie vollständig. Wir extrahieren daraus, was geht, und
                    schlagen Titel und Untertitel vor. Sobald etwas erkannt wurde, erscheinen die Felder direkt editierbar
                    oben.
                </p>
            </header>

            {resultJson ? (
                <ResultView />
            ) : (
                <div className="space-y-6">
                    {/* Only shown once there's something to review — before the
              first message, the chat box is the only thing on the page. */}
                    {hasContent && <RegistrationForm />}
                    <ChatWindow />
                </div>
            )}
        </main>
    );
}

export default function App() {
    return (
        <ChatProvider>
            <AppShell />
        </ChatProvider>
    );
}
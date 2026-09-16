import { useState } from "react";
import { MAX_MESSAGE_LENGTH, MAX_TURNS } from "../context/ChatContext";

export default function ChatInput({ onSend, loading, hasContent, turnCount }) {
  const [message, setMessage] = useState("");

  const counterColor =
    message.length > MAX_MESSAGE_LENGTH
      ? "text-(--color-required-missing)"
      : message.length > MAX_MESSAGE_LENGTH * 0.9
        ? "text-(--color-inferred)"
        : "text-(--color-ink-muted)";

  function handleSend() {
    if (!message.trim() || message.length > MAX_MESSAGE_LENGTH || loading) return;
    onSend(message);
    setMessage("");
  }

  return (
    <>
      <textarea
        className="w-full resize-none rounded-xl border border-(--color-border) p-2 text-sm"
        rows={hasContent ? 3 : 5}
        maxLength={MAX_MESSAGE_LENGTH + 200}
        value={message}
        placeholder={
          hasContent
            ? "Noch etwas ergänzen oder korrigieren..."
            : 'Beschreib dein Angebot in eigenen Worten — z. B. "Jeden Donnerstag 19 Uhr offenes Brettspieltreffen im Café Nord, Hauptstr. 12, 14467 Potsdam, kostenlos". Muss nicht vollständig sein.'
        }
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
          }
        }}
      />
      <div className="mt-1 flex items-center justify-between">
        <span className={`text-xs ${counterColor}`}>
          {message.length} / {MAX_MESSAGE_LENGTH}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-(--color-ink-muted)">
            Nachricht {turnCount + 1}/{MAX_TURNS}
          </span>
          <button
            onClick={handleSend}
            disabled={loading || !message.trim() || message.length > MAX_MESSAGE_LENGTH}
            className="rounded-xl bg-(--color-accent) px-3 py-1.5 text-sm text-(--color-accent-contrast) disabled:opacity-40"
          >
            {loading ? "…" : hasContent ? "Ergänzen" : "Extrahieren"}
          </button>
        </div>
      </div>
    </>
  );
}

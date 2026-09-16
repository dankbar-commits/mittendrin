import { useEffect, useRef } from "react";
import { useChat } from "../hooks/useChat";
import { MAX_TURNS } from "../context/ChatContext";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";

export default function ChatWindow() {
  const { draft, log, loading, error, sendMessage } = useChat();
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  const overTurnLimit = draft.turnCount >= MAX_TURNS;
  const hasContent = draft.turnCount > 0;

  return (
    <section className="flex flex-col rounded-2xl border border-(--color-border) bg-white">
      {log.length > 0 && (
        <div
          className="space-y-3 overflow-y-auto rounded-xl bg-(--color-surface-muted) p-4"
          style={{ maxHeight: "30vh" }}
        >
          {log.map((entry, i) => (
            <MessageBubble key={i} entry={entry} />
          ))}
          <div ref={logEndRef} />
        </div>
      )}

      <div className="p-3">
        {overTurnLimit ? (
          <p className="rounded-xl bg-(--color-required-missing-bg) p-2 text-sm text-(--color-required-missing)">
            Maximale Anzahl an Nachrichten ({MAX_TURNS}) erreicht. Bitte die restlichen Felder oben manuell
            ausfüllen.
          </p>
        ) : (
          <ChatInput onSend={sendMessage} loading={loading} hasContent={hasContent} turnCount={draft.turnCount} />
        )}

        {error && <p className="mt-2 text-xs text-(--color-required-missing)">{error}</p>}
      </div>
    </section>
  );
}

import { useContext } from "react";
import { ChatContext } from "../context/ChatContext";

/** Convenience accessor for ChatContext — the draft, the chat log, and the
 * actions (updateDraft/sendMessage/submit) all live in one place so the
 * checklist-tabs and the chat box stay in sync automatically. */
export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within a <ChatProvider>");
  return ctx;
}

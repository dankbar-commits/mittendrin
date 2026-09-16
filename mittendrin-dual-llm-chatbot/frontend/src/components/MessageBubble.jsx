export default function MessageBubble({ entry }) {
  const className =
    "max-w-[85%] rounded-2xl px-3 py-2 text-sm " +
    (entry.role === "user"
      ? "ml-auto bg-(--color-accent) text-(--color-accent-contrast)"
      : entry.role === "assistant"
        ? "bg-(--color-bg)"
        : "mx-auto bg-transparent text-center text-xs italic text-(--color-ink-muted)");

  return <div className={className}>{entry.text}</div>;
}

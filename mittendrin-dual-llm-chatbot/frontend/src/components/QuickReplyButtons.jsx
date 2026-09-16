/**
 * Reusable "pick one of a few short options" row — e.g. a future quick
 * suggestion like ["kostenlos", "5€", "10€"] next to a field. Not wired
 * into any flow right now: the app deliberately dropped a scripted
 * step-by-step Q&A (see README, "no forced next-question flow"), and
 * wiring quick-reply chips into the chat would reintroduce that pattern
 * through the back door. Kept as a ready-to-use primitive for a genuinely
 * optional enhancement — not a stub with invented behavior.
 */
export default function QuickReplyButtons({ options, onSelect }) {
  if (!options || options.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onSelect(opt)}
          className="rounded-full border border-(--color-border) bg-white px-2.5 py-1 text-xs hover:border-(--color-accent)"
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

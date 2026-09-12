"""Deterministic safety flagger.

Layered: normalization → lexicons → regex → heuristics. Every flag records the
matched span from the ORIGINAL text (not the normalized copy) plus a rule ID.
This module never blocks — it labels and forwards; `human_review_required` is
the load-bearing output, and the human reviewer is the actual safety net.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from unidecode import unidecode

from .schema import SafetyCategory, SafetyFlag, Severity

LEXICON_DIR = Path(__file__).resolve().parents[2] / "lexicons"

# Category → (filename, severity). CSAM lexicon → hard-flag always.
_LEXICON_SPEC: list[tuple[SafetyCategory, str, Severity]] = [
    ("profanity", "profanity_en.txt", "soft"),
    ("profanity", "profanity_de.txt", "soft"),
    ("hate",      "hate_terms.txt",   "hard"),
    ("violence",  "violence_terms.txt", "soft"),
    ("selfharm",  "selfharm_terms.txt", "soft"),
    ("csam",      "csam_terms.txt",   "hard"),
]

# leet-speak folding for the NORMALIZED copy only. Preserves length so span
# offsets in the normalized string map 1:1 back to the original.
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def _normalize(text: str) -> str:
    """Lowercase + strip diacritics + fold leet-speak. Length-preserving."""
    folded = unidecode(text)
    # unidecode may change length (e.g., 'ß' → 'ss'). Fall back to lower+leet only
    # when lengths diverge, to keep span offsets stable.
    if len(folded) != len(text):
        folded = text
    return folded.lower().translate(_LEET)


def _load_lexicon(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _compile_lexicon_patterns() -> list[tuple[SafetyCategory, Severity, re.Pattern[str]]]:
    patterns: list[tuple[SafetyCategory, Severity, re.Pattern[str]]] = []
    for category, filename, severity in _LEXICON_SPEC:
        terms = _load_lexicon(LEXICON_DIR / filename)
        if not terms:
            continue
        # word-boundary matched; escape terms; longest first so multi-word phrases win
        terms_sorted = sorted(terms, key=len, reverse=True)
        joined = "|".join(re.escape(t) for t in terms_sorted)
        patterns.append((category, severity, re.compile(rf"\b(?:{joined})\b", re.IGNORECASE)))
    return patterns


_LEXICON_PATTERNS = _compile_lexicon_patterns()

# PII / regex patterns
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_E164 = re.compile(r"\+?\d[\d\s\-().]{7,}\d")
_DIGIT_RUN_16 = re.compile(r"\b(?:\d[ -]?){13,19}\b")  # candidate credit card
_URL = re.compile(r"\bhttps?://[^\s<>\"']+", re.IGNORECASE)
_SUSPICIOUS_TLDS = {".zip", ".mov", ".click", ".top", ".xyz"}

# Heuristic keywords
_URGENCY = re.compile(r"\b(act now|limited time|hurry|only today|last chance|guaranteed returns|send btc|send bitcoin)\b", re.IGNORECASE)


def _luhn_valid(digits: str) -> bool:
    s = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        s += n
    return s % 10 == 0 and len(digits) >= 13


def scan(text: str, source: Literal["ocr", "llm"] = "ocr") -> list[SafetyFlag]:
    """Return flags found in `text`. Spans point into the ORIGINAL text."""
    flags: list[SafetyFlag] = []
    if not text:
        return flags

    normalized = _normalize(text)

    # 1. Lexicons (word-boundary, case-insensitive, on normalized copy)
    for category, severity, pattern in _LEXICON_PATTERNS:
        for m in pattern.finditer(normalized):
            # normalized length matches original when unidecode was skipped;
            # otherwise we still surface the span in the original by offset.
            span = text[m.start():m.end()] if len(text) == len(normalized) else m.group(0)
            flags.append(SafetyFlag(
                category=category,
                rule_id=f"lex/{category}/{m.group(0).lower()}",
                severity=severity,
                matched_span=span,
                source=source,
            ))

    # 2. Regex — PII
    for m in _EMAIL.finditer(text):
        flags.append(SafetyFlag(category="pii", rule_id="pii/email", severity="soft",
                                matched_span=m.group(0), source=source))
    for m in _PHONE_E164.finditer(text):
        digits_only = re.sub(r"\D", "", m.group(0))
        if 8 <= len(digits_only) <= 15:
            flags.append(SafetyFlag(category="pii", rule_id="pii/phone", severity="soft",
                                    matched_span=m.group(0), source=source))
    for m in _DIGIT_RUN_16.finditer(text):
        digits_only = re.sub(r"\D", "", m.group(0))
        if _luhn_valid(digits_only):
            flags.append(SafetyFlag(category="pii", rule_id="pii/credit-card", severity="hard",
                                    matched_span=m.group(0), source=source))

    # 3. Suspicious URLs
    for m in _URL.finditer(text):
        url = m.group(0).lower()
        if any(url.split("/", 3)[2].endswith(tld) for tld in _SUSPICIOUS_TLDS if "/" in url):
            flags.append(SafetyFlag(category="scam", rule_id="scam/suspicious-tld", severity="soft",
                                    matched_span=m.group(0), source=source))

    # 4. Heuristics — scam/urgency phrases
    for m in _URGENCY.finditer(text):
        flags.append(SafetyFlag(category="scam", rule_id="scam/urgency", severity="soft",
                                matched_span=m.group(0), source=source))

    return flags


def evaluate(flags: list[SafetyFlag]) -> bool:
    """Decide whether human review is required.

    Rule: any hard-severity flag → True. Otherwise True when two or more soft flags stack.
    """
    hard = sum(1 for f in flags if f.severity == "hard")
    soft = sum(1 for f in flags if f.severity == "soft")
    return hard >= 1 or soft >= 2

"""Ollama entity extraction with structured JSON output + one repair retry.

A single poster can advertise MULTIPLE offers (a chorus, a dance class, a
counseling service on the same flyer). The model is asked to return a list
of items — one per distinct offer. Single-offer flyers return a one-element
list.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import ValidationError

from .schema import LLMPosterExtraction

SYSTEM_PROMPT = (
    "Du extrahierst strukturierte Angaben aus dem Text eines Flyers oder Plakats "
    "für das Verzeichnis 'mittendrin.in – Brandenburg', das Angebote für ältere "
    "Menschen in Brandenburg auflistet.\n\n"
    "WICHTIG — ein Poster kann MEHRERE Angebote enthalten (z. B. ein Programm "
    "eines Mehrgenerationenhauses mit Chor, Tanz, Kreativkurs …). Gib deshalb "
    "IMMER eine Liste `items` zurück, mit EINEM Eintrag pro erkennbarem Angebot, "
    "Kurs, Service oder Veranstaltung. Ein einzelnes Angebot ergibt eine "
    "einelementige Liste.\n\n"
    "WAS IST KEIN eigenes Angebot:\n"
    "- Das Gebäude / der Veranstaltungsort selbst (z. B. 'Mehrgenerationenhaus X', "
    "'Bürgerhaus Y', 'Treffpunkt Z' im Kopf oder Fußbereich) — dieser Name gehört "
    "in das Feld `venue_de` oder `responsibleInstitution` der einzelnen Angebote, "
    "nicht als eigenes Item.\n"
    "- Öffnungszeiten des Hauses — die gehören nicht in `hours_de` eines Angebots. "
    "Nutze sie höchstens als `venue_de`-Zusatz.\n"
    "- Kontaktinformationen im Fußbereich (Adresse, Telefon, E-Mail) — diese "
    "gelten für ALLE Angebote und dürfen an jedes Item angehängt werden, aber "
    "NIE als eigenes Item erscheinen.\n\n"
    "So gehst du pro Item vor:\n"
    "1. **title** IMMER füllen mit dem prominenten Namen des Angebots aus dem "
    "Flyertext. Verwende nur Text, der WÖRTLICH auf DIESEM Flyer steht.\n"
    "2. **brief_de** kurz füllen (max. 120 Zeichen), wenn möglich.\n"
    "3. **description_de** 2–4 Sätze in einfacher Sprache, wenn genug Text da ist.\n"
    "4. **hours_de** IMMER füllen, wenn ein Zeit-/Termin­hinweis direkt neben "
    "oder unter dem Titel steht (z. B. 'jeden Dienstag 09:45–11:45 Uhr', "
    "'monatlich', '2x jährlich', 'Termin auf Nachfrage'). Ordne Zeiten dem "
    "räumlich nächsten Titel zu.\n"
    "5. Weitere Felder (address, city, phone, email, charge_de, venue_de, "
    "responsibleInstitution …) NUR füllen, wenn sie im Text vorkommen. "
    "Kontakt-Angaben aus dem Fußbereich (Adresse/Telefon/E-Mail/Website des "
    "Hauses) dürfen an jedes Item angehängt werden. Der Hausname selbst "
    "gehört in `venue_de` und/oder `responsibleInstitution`.\n"
    "6. **tags**: 3–8 kleingeschriebene deutsche Schlagwörter pro Item.\n"
    "7. Erfinde nichts. Übernimm KEINEN Text aus dem Beispiel unten (Namen wie "
    "'Spielekreis', 'Yoga für Ältere', 'Musterstadt' usw.) — nutze ausschließlich "
    "Angaben aus dem Flyertext der Nutzernachricht.\n\n"
    "Antworte AUSSCHLIESSLICH mit gültigem JSON nach dem vorgegebenen Schema:\n"
    "{\"items\": [ { …item 1… }, { …item 2… }, … ] }\n\n"
    "Beispiel — ein fiktives Poster mit zwei Angeboten (nur zur Illustration; "
    "übernimm diese Namen NIEMALS in deine Antwort):\n"
    "Input: '[Block 0] Wintersaison im Vereinshaus Musterstadt\\n"
    "[Block 1] Spielekreis — jeden Freitag 15–17 Uhr\\n"
    "[Block 2] Yoga für Ältere — montags 10 Uhr, mit Frau Beispielheim\\n"
    "[Block 3] Kontakt: 0999 000000'\n"
    "Output: {\"items\": [\n"
    "  {\"title\": \"Spielekreis\", \"brief_de\": \"Wöchentlicher Spielekreis.\", "
    "\"tags\": [\"spiele\", \"treffpunkt\", \"senioren\"], "
    "\"hours_de\": \"Freitags 15–17 Uhr\", "
    "\"venue_de\": \"Vereinshaus Musterstadt\", \"phone\": \"0999 000000\"},\n"
    "  {\"title\": \"Yoga für Ältere\", \"brief_de\": \"Yoga speziell für "
    "ältere Menschen.\", \"tags\": [\"yoga\", \"bewegung\", \"senioren\"], "
    "\"hours_de\": \"Montags 10 Uhr\", \"contact\": \"Frau Beispielheim\", "
    "\"venue_de\": \"Vereinshaus Musterstadt\", \"phone\": \"0999 000000\"}\n"
    "]}"
)


def extract_items(
    blocks_text: str,
    model: str = "qwen2.5:7b",
    host: str | None = None,
) -> tuple[LLMPosterExtraction, dict[str, Any]]:
    """Call Ollama, return (poster_extraction, timing_info). One repair retry on validation error."""
    import ollama

    client = ollama.Client(host=host) if host else ollama
    schema = LLMPosterExtraction.model_json_schema()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
         "content": f"Extrahiere alle Angebote aus folgendem Flyer-Text:\n\n{blocks_text}"},
    ]

    start = time.perf_counter()
    resp = client.chat(model=model, messages=messages, format=schema, options={"temperature": 0.1})
    raw = resp["message"]["content"]

    try:
        parsed = LLMPosterExtraction.model_validate_json(raw)
        return parsed, {"llm_ms": (time.perf_counter() - start) * 1000, "retried": False}
    except ValidationError as e:
        repair = [
            *messages,
            {"role": "assistant", "content": raw},
            {"role": "user",
             "content": (
                 f"Dein vorheriges JSON war ungültig:\n{e.errors()}\n"
                 f"Gib korrigiertes JSON strikt nach dem Schema zurück. "
                 f"Wurzel muss ein Objekt mit 'items' (Liste) sein. Keine Prosa."
             )},
        ]
        resp2 = client.chat(model=model, messages=repair, format=schema, options={"temperature": 0.0})
        raw2 = resp2["message"]["content"]
        parsed = LLMPosterExtraction.model_validate_json(raw2)
        return parsed, {"llm_ms": (time.perf_counter() - start) * 1000, "retried": True}

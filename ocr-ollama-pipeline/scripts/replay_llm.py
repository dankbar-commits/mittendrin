"""Replay LLM extraction over cached OCR blocks from debug JSONs.
Fast A/B without re-running OCR. Prints one summary per extracted offer.
"""
import json
import sys
from pathlib import Path

from flyer_extract import llm
from flyer_extract.schema import Block

DEBUG_DIR = Path(__file__).resolve().parents[1] / "data" / "outputs"


def blocks_text_from_debug(debug_json: dict) -> str:
    blocks = [Block.model_validate(b) for b in debug_json["blocks"]]
    return "\n\n".join(f"[Block {b.id}] {b.text}" for b in blocks)


def main(model: str) -> None:
    files = sorted(DEBUG_DIR.glob("*.debug.json"))
    print(f"Replaying LLM with model={model} on {len(files)} debug files:\n")
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        text = blocks_text_from_debug(data)
        try:
            poster, timing = llm.extract_items(text, model=model)
            print(f"== {f.stem} ({timing['llm_ms']:.0f} ms, retried={timing['retried']}, {len(poster.items)} item(s)) ==")
            for i, ext in enumerate(poster.items):
                filled = {k: v for k, v in ext.model_dump(exclude_none=True).items() if v not in (None, [], "")}
                print(f"  -- item {i + 1}")
                for k, v in filled.items():
                    s = str(v)
                    print(f"       {k}: {s[:120]}{'...' if len(s) > 120 else ''}")
            if not poster.items:
                print("  (LLM returned empty items list)")
            print()
        except Exception as e:
            print(f"== {f.stem}: ERROR {e}\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b")

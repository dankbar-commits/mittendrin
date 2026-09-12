"""Annotated-image renderer — draw OCR word boxes and/or block outlines."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .schema import Block, OCRWord

_BLOCK_COLORS = [
    "#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#9A6324", "#800000", "#008080",
]


def draw_boxes(image: Image.Image, words: list[OCRWord], blocks: list[Block] | None = None) -> Image.Image:
    out = image.copy()
    draw = ImageDraw.Draw(out)

    word_to_block: dict[int, int] = {}
    if blocks:
        for b in blocks:
            for wid in b.word_ids:
                word_to_block[wid] = b.id

    for i, w in enumerate(words):
        color = _BLOCK_COLORS[word_to_block.get(i, i) % len(_BLOCK_COLORS)] if blocks else "#00ff00"
        b = w.bbox
        if b.polygon:
            draw.polygon(b.polygon, outline=color, width=2)
        else:
            draw.rectangle([b.x_min, b.y_min, b.x_max, b.y_max], outline=color, width=2)

    if blocks:
        for b in blocks:
            color = _BLOCK_COLORS[b.id % len(_BLOCK_COLORS)]
            draw.rectangle([b.bbox.x_min, b.bbox.y_min, b.bbox.x_max, b.bbox.y_max],
                           outline=color, width=4)
    return out

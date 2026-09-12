"""EasyOCR wrapper — returns OCRWord list with polygon → axis-aligned bbox conversion.

EasyOCR downloads model weights on first use (a few hundred MB); subsequent calls
are cached to ~/.EasyOCR/. The Reader is cached at module level because init is slow.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image

from .schema import BoundingBox, OCRWord


@lru_cache(maxsize=4)
def _reader(langs_tuple: tuple[str, ...]):
    import easyocr  # lazy import so `import flyer_extract` stays cheap
    return easyocr.Reader(list(langs_tuple), gpu=False, verbose=False)


def run(image: Image.Image, langs: tuple[str, ...] = ("en", "de")) -> list[OCRWord]:
    """Detect + recognize text. Returns a list of OCRWord."""
    reader = _reader(langs)
    raw = reader.readtext(np.array(image))
    words: list[OCRWord] = []
    for polygon, text, confidence in raw:
        pts = [(float(x), float(y)) for x, y in polygon]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bbox = BoundingBox(
            x_min=min(xs), y_min=min(ys),
            x_max=max(xs), y_max=max(ys),
            polygon=pts,
        )
        words.append(OCRWord(text=text, confidence=float(confidence), bbox=bbox))
    return words

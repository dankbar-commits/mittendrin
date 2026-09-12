"""Image loading with EXIF-aware orientation normalization."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

MAX_EDGE = 4096


def load_image(path: str | Path) -> Image.Image:
    """Load an image, apply EXIF orientation, convert to RGB, downscale if huge."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    if max(img.size) > MAX_EDGE:
        scale = MAX_EDGE / max(img.size)
        new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
        img = img.resize(new_size, Image.LANCZOS)
    return img

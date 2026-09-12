"""Group OCR words into reading-order blocks using vertical clustering."""

from __future__ import annotations

from statistics import median

import numpy as np
from sklearn.cluster import DBSCAN

from .schema import Block, BoundingBox, OCRWord


def group_blocks(words: list[OCRWord]) -> list[Block]:
    if not words:
        return []

    heights = [w.bbox.y_max - w.bbox.y_min for w in words]
    median_h = max(median(heights), 1.0)
    y_centers = np.array([[(w.bbox.y_min + w.bbox.y_max) / 2] for w in words])

    labels = DBSCAN(eps=median_h * 0.9, min_samples=1).fit_predict(y_centers)

    clusters: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(int(label), []).append(idx)

    # Column-gap threshold: split a horizontal row when the gap between adjacent
    # words exceeds this many median line-heights. Prevents left/right columns of
    # a two-column poster from being mashed into one block.
    x_gap_threshold = median_h * 3.0

    blocks: list[Block] = []
    for word_ids in clusters.values():
        word_ids.sort(key=lambda i: words[i].bbox.x_min)
        # Split this y-band into sub-runs whenever a big horizontal gap appears.
        sub_runs: list[list[int]] = [[word_ids[0]]]
        for prev, cur in zip(word_ids, word_ids[1:]):
            gap = words[cur].bbox.x_min - words[prev].bbox.x_max
            if gap > x_gap_threshold:
                sub_runs.append([cur])
            else:
                sub_runs[-1].append(cur)

        for run in sub_runs:
            xs_min = [words[i].bbox.x_min for i in run]
            ys_min = [words[i].bbox.y_min for i in run]
            xs_max = [words[i].bbox.x_max for i in run]
            ys_max = [words[i].bbox.y_max for i in run]
            blocks.append(Block(
                id=0,  # assigned after sort
                text=" ".join(words[i].text for i in run),
                bbox=BoundingBox(x_min=min(xs_min), y_min=min(ys_min),
                                 x_max=max(xs_max), y_max=max(ys_max)),
                word_ids=run,
            ))

    blocks.sort(key=lambda b: b.bbox.y_min)
    for i, b in enumerate(blocks):
        b.id = i
    return blocks


def blocks_to_text(blocks: list[Block]) -> str:
    return "\n\n".join(f"[Block {b.id}] {b.text}" for b in blocks)

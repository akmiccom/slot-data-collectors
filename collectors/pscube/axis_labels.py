"""Restricted numeric masks, never OCR of the whole image.

Templates contain only binary label shapes: observed B–E raster variants and
Arial 15px candidates (including unverified A values). No runtime font required.
"""

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from PIL import Image


@dataclass(frozen=True)
class AxisLabel:
    y: int
    recognized_value: int | None = None
    confidence: str = "low"


@lru_cache(maxsize=1)
def _templates() -> tuple[tuple[int, Image.Image], ...]:
    data = json.loads(Path(__file__).with_name("axis_templates.json").read_text(encoding="utf-8"))
    masks: list[tuple[int, Image.Image]] = []
    for value, variants in data.items():
        for rows in variants:
            mask = Image.new("1", (len(rows[0]), len(rows)))
            mask.putdata([int(bit) for row in rows for bit in row])
            masks.append((int(value), mask))
    return tuple(masks)


def recognize_axis_labels(image: Image.Image, left: int, grid: list[int]) -> list[AxisLabel]:
    """Inspect only the left margin within a narrow band of each grid row.

    Thresholds and aspect/scale limits are conservative implementation choices,
    not a guarantee for other fonts or arbitrary resized images.
    """
    scale = image.width / 800
    radius = max(6, round(10 * scale))
    end = left - max(5, round(10 * scale))  # exclude axis ticks
    labels: list[AxisLabel] = []
    grayscale = image.convert("L")
    for y in grid:
        crop = grayscale.crop((0, max(0, y-radius), max(1, end), min(image.height, y+radius)))
        mask = crop.point(lambda v: 255 if v > 160 else 0, mode="1")
        bounds = mask.getbbox()
        if not bounds:
            labels.append(AxisLabel(y))
            continue
        mask = mask.crop(bounds)
        scores: dict[int, float] = {}
        for value, template in _templates():
            if (abs(mask.width / mask.height - template.width / template.height) > .15
                    or not .8 <= mask.height / (template.height * scale) <= 1.2):
                continue
            resized = mask.resize(template.size, Image.Resampling.NEAREST)
            error = sum(a != b for a, b in zip(
                resized.convert("L").tobytes(), template.convert("L").tobytes()
            )) / (template.width * template.height)
            scores[value] = min(scores.get(value, 1), error)
        ranked = sorted(scores.items(), key=lambda pair: pair[1])
        if ranked and ranked[0][1] <= .06 and (len(ranked) == 1 or ranked[1][1] - ranked[0][1] >= .03):
            labels.append(AxisLabel(y, ranked[0][0], "high"))
        else:
            labels.append(AxisLabel(y))
    return labels

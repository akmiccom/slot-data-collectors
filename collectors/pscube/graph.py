"""Pillow-only geometric prototype. Axis values are a declared layout profile, not OCR."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from statistics import median
from urllib.parse import urljoin, urlsplit
import re
from PIL import Image, ImageDraw
from collectors.pscube.client import PscubeClient
from collectors.pscube.collector import PscubeCollector
from common.exceptions import CollectorError


@dataclass(frozen=True)
class GraphProfile:
    top_medal: int = 5000
    bottom_medal: int = -1000
    step_medal: int = 1000

    def __post_init__(self) -> None:
        if (self.step_medal <= 0 or self.top_medal <= self.bottom_medal
                or not self.bottom_medal <= 0 <= self.top_medal
                or (self.top_medal - self.bottom_medal) % self.step_medal
                or self.top_medal % self.step_medal):
            raise ValueError("Invalid scale profile")


@dataclass
class GraphEstimate:
    business_date: date
    unit_no: str
    image_path: str
    image_width: int
    image_height: int
    plot_bounds: tuple[int, int, int, int] | None = None
    horizontal_grid_y: list[int] = field(default_factory=list)
    zero_y: float | None = None
    step_px: float | None = None
    line_end_x: float | None = None
    line_end_y: float | None = None
    estimated_medal: int | None = None
    confidence: str = "low"
    warnings: list[str] = field(default_factory=list)


def _unit(value: str) -> None:
    if not value or not value.isascii() or not value.isdigit():
        raise ValueError("Unit must be a digit string")


def fetch_graph(client: PscubeClient, unit_url: str, day: date, unit: str, directory: Path) -> Path:
    """One current unit JSON and one image, using normal Session and Referer."""
    _unit(unit)
    detail = PscubeCollector(client).collect_unit(unit_url)
    if detail.days[0].unit_no != unit:
        raise CollectorError("Unit mismatch")
    matches = [g for g in detail.graphs if g.business_date == day and g.src]
    if len(matches) != 1:
        raise CollectorError("Requested graph is unavailable")
    parts = urlsplit(unit_url)
    # Verified template: /h/<hall>/graph/{{>src}}. Other layouts are unsupported.
    match = re.fullmatch(r"(/h/[^/]+)/cgi-bin/nc-v06-001\.php", parts.path)
    if not match:
        raise CollectorError("Unsupported graph layout")
    base = f"{parts.scheme}://{parts.netloc}{match.group(1)}/graph/"
    target = urljoin(base, matches[0].src)
    parsed = urlsplit(target)
    if (parsed.scheme != parts.scheme or parsed.netloc != parts.netloc
            or not parsed.path.startswith(match.group(1) + "/graph/")):
        raise CollectorError("Unexpected graph origin or path")
    content = client.fetch_bytes(target, headers={"Referer": unit_url})
    with Image.open(BytesIO(content)) as source:
        source.load()
        image = source.convert("RGB")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{day:%Y%m%d}_{unit}.png"
    image.save(path)  # Normalizes format and drops request/PNG metadata.
    return path


def _groups(rows: list[int]) -> list[list[int]]:
    groups: list[list[int]] = []
    for y in rows:
        if not groups or y > groups[-1][-1] + 1:
            groups.append([y])
        else:
            groups[-1].append(y)
    return groups


def _gray(pixel: tuple[int, int, int]) -> bool:
    return min(pixel) >= 45 and max(pixel) - min(pixel) <= 30


def _pink(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return r >= 85 and b >= 70 and r - g >= 25 and b - g >= 20 and abs(r - b) <= 110


def estimate_graph(path: Path, day: date, unit: str, profile: GraphProfile = GraphProfile()) -> GraphEstimate:
    _unit(unit)
    with Image.open(path) as source:
        source.load()
        image = source.convert("RGB")
    w, h = image.size
    result = GraphEstimate(day, unit, str(path), w, h)
    result.warnings.append("Axis values assumed from supplied profile; labels are not recognized.")
    if w < 80 or h < 80:
        result.warnings.append("Image too small.")
        return result
    pixels = image.load()
    # Central horizontal coverage suppresses labels, text, vertical grids and titles.
    sx, ex = int(w * .18), int(w * .97)
    rows = [y for y in range(int(h * .01), int(h * .96))
            if sum(_gray(pixels[x, y]) for x in range(sx, ex)) >= (ex - sx) * .32]
    grid = [round(median(group)) for group in _groups(rows)]
    result.horizontal_grid_y = grid
    expected = (profile.top_medal - profile.bottom_medal) // profile.step_medal + 1
    if len(grid) != expected or len(grid) < 3:
        result.warnings.append("Grid count does not match profile; no scale interpolation attempted.")
        return result
    gaps = [b - a for a, b in zip(grid, grid[1:])]
    step = float(median(gaps))
    if step <= 0 or max(abs(g - step) for g in gaps) / step > .06:
        result.warnings.append("Grid spacing is unstable.")
        return result
    top, bottom = grid[0], grid[-1]
    # Locate the long y-axis; no fixed plot x coordinates.
    columns = [(sum(_gray(pixels[x, y]) for y in range(top, bottom + 1)), x)
               for x in range(int(w * .04), int(w * .30))]
    coverage, left = max(columns)
    if coverage < (bottom - top) * .65:
        result.warnings.append("Plot left axis not found.")
        return result
    ends = [max((x for x in range(left, w) if _gray(pixels[x, y])), default=left) for y in grid]
    right = max(ends)
    if right - left < w * .5:
        result.warnings.append("Plot width is unstable.")
        return result
    result.plot_bounds = (left, top, right, bottom)
    # Average over the full span reduces integer raster rounding of individual gaps.
    step = (bottom - top) / (len(grid) - 1)
    result.step_px = step
    zero_index = profile.top_medal // profile.step_medal
    result.zero_y = float(grid[zero_index])
    # A visibly emphasized line elsewhere contradicts the zero-line profile.
    brightness = []
    for y in grid:
        gray = [sum(pixels[x, y]) / 3 for x in range(sx, ex) if _gray(pixels[x, y])]
        brightness.append(median(gray) if gray else 0)
    interior = brightness[1:-1]
    if (interior and max(interior) > median(brightness) * 1.4
            and brightness[zero_index] < max(interior) * .8):
        result.warnings.append("Emphasized grid contradicts assumed zero line.")
        return result
    points = {(x, y) for y in range(top, bottom + 1) for x in range(left, right + 1)
              if _pink(pixels[x, y])}
    components = []
    while points:
        seed = points.pop()
        stack, component = [seed], [seed]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
                neighbor = (x + dx, y + dy)
                if neighbor in points:
                    points.remove(neighbor)
                    stack.append(neighbor)
                    component.append(neighbor)
        xs = [p[0] for p in component]
        if max(xs) - min(xs) >= (right - left) * .15 and len(component) >= (right - left) * .15:
            components.append(component)
    if not components:
        result.warnings.append("No sufficiently connected pink line.")
        return result
    components.sort(key=lambda c: max(x for x,y in c) - min(x for x,y in c), reverse=True)
    main = components[0]
    if len(components) > 1:
        result.warnings.append("Multiple substantial line components; endpoint ambiguous.")
        return result
    end_x = max(x for x,y in main)
    end_y = float(median(y for x,y in main if x == end_x))
    result.line_end_x, result.line_end_y = float(end_x), end_y
    if end_y <= top + 2 or end_y >= bottom - 2:
        result.warnings.append("Line may be clipped vertically.")
        return result
    value = (Decimal(str(result.zero_y)) - Decimal(str(end_y))) / Decimal(str(step)) * profile.step_medal
    result.estimated_medal = int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    result.confidence = "high" if (end_x - left) / (right - left) >= .85 else "medium"
    if result.confidence == "medium":
        result.warnings.append("Line ends before right side; may be an incomplete trading day.")
    return result


def annotate_graph(result: GraphEstimate, directory: Path) -> Path:
    with Image.open(result.image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    if result.plot_bounds:
        left, top, right, bottom = result.plot_bounds
        draw.rectangle(result.plot_bounds, outline="cyan", width=2)
        for y in result.horizontal_grid_y:
            draw.line((left,y,right,y), fill="orange", width=1)
        if result.zero_y is not None:
            draw.line((left,result.zero_y,right,result.zero_y), fill="lime", width=2)
    if result.line_end_x is not None and result.line_end_y is not None:
        x, y = result.line_end_x, result.line_end_y
        draw.ellipse((x-5,y-5,x+5,y+5), outline="red", width=2)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.business_date:%Y%m%d}_{result.unit_no}.png"
    image.save(path)
    return path

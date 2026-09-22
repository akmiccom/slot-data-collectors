"""Pure m06 JSON parsing, with no HTTP or image retrieval."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from collectors.pscube.models import PscubeGraph, PscubeUnitDaily, PscubeUnitDetail
from collectors.pscube.estimation import estimate_game
from collectors.pscube.parser import _date
from common.exceptions import MachineParseError, UnitParseError


def business_date(value: object) -> date:
    try:
        parsed = _date(value)
    except MachineParseError:
        raise UnitParseError("Invalid business date") from None
    if parsed is None:
        raise UnitParseError("Missing business date")
    return parsed


def number(value: object, *, probability: bool = False) -> int | float | None:
    if value is None or value is False or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise UnitParseError("Invalid numeric value")
    text = str(value).strip()
    if probability and text.startswith("1/"):
        text = text[2:].strip()
    try:
        parsed = Decimal(text)
        if not parsed.is_finite() or parsed < 0:
            raise InvalidOperation
        if probability:
            if parsed == 0:
                return None
            result = float(parsed)
            if not Decimal(str(result)).is_finite():
                raise InvalidOperation
            return result
        if parsed != parsed.to_integral_value():
            raise InvalidOperation
        return int(parsed)
    except (InvalidOperation, ValueError, OverflowError):
        raise UnitParseError("Invalid numeric value") from None


def optional_text(value: object) -> str | None:
    if value is None or value is False or value == "":
        return None
    if not isinstance(value, str):
        raise UnitParseError("Invalid text value")
    return value


def parse_unit_detail(data: dict[str, object]) -> PscubeUnitDetail:
    if not isinstance(data, dict):
        raise UnitParseError("Expected JSON object")
    current = business_date(data.get("YMD_biz"))
    dai, ki, rows = data.get("Dai"), data.get("Ki"), data.get("Data")
    if not isinstance(dai, dict) or not isinstance(ki, dict) or not isinstance(rows, list):
        raise UnitParseError("Missing Dai, Ki or Data")
    unit = dai.get("cd_dai")
    if not isinstance(unit, str) or not unit.isascii() or not unit.isdigit():
        raise UnitParseError("Unit number must be a digit string")
    titles = {"BIG", "REG", "BIG確率", "REG確率", "合成確率", "最大出玉"}
    values = {}
    for row in rows:
        if row is None or row is False:
            continue
        if not isinstance(row, dict) or not isinstance(row.get("title"), str):
            raise UnitParseError("Invalid Data row")
        title = row["title"]
        if title not in titles:
            continue
        if title in values or not isinstance(row.get("item"), list):
            raise UnitParseError("Duplicate title or invalid item")
        values[title] = row["item"]
    if not values:
        raise UnitParseError("No supported Data titles")
    raw_graphs = data.get("Graph")
    if raw_graphs is None or raw_graphs is False:
        raw_graphs = []
    if not isinstance(raw_graphs, list):
        raise UnitParseError("Graph must be an array")
    graphs = []
    by_date = {}
    for graph in raw_graphs:
        if not isinstance(graph, dict):
            raise UnitParseError("Invalid Graph entry")
        g = PscubeGraph(business_date(graph.get("YMD_biz")), optional_text(graph.get("title")),
                        optional_text(graph.get("src")), graph.get("legend"))
        if g.business_date in by_date:
            raise UnitParseError("Duplicate Graph date")
        graphs.append(g)
        by_date[g.business_date] = g
    days = []
    for index in range(4):
        def value(title: str, probability: bool = False) -> int | float | None:
            items = values.get(title, [])
            return number(items[index] if index < len(items) else None, probability=probability)
        bb, rb = value("BIG"), value("REG")
        bp, rp, cp = value("BIG確率", True), value("REG確率", True), value("合成確率", True)
        estimate = estimate_game(bb, rb, bp, rp, cp)
        day = current - timedelta(days=index)
        graph = by_date.get(day)
        days.append(PscubeUnitDaily(day, unit, optional_text(ki.get("name")), optional_text(ki.get("cd_kisyu")),
                    bb, rb, bp, rp, cp, value("最大出玉"), estimate.value, estimate.candidates,
                    estimate.spread, graph.src if graph else None))
    return PscubeUnitDetail(days, graphs)

"""Pure HTML parsing interface; no network access."""

from common.exceptions import ParserNotImplementedError
from common.exceptions import MachineParseError
from collectors.pscube.models import PscubeMachine, PscubeMachinePage
from datetime import datetime, date
import math


def _integer(value: object, field: str, *, optional: bool = False) -> int | None:
    if optional and value in (None, ""):
        return None
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise MachineParseError(f"Invalid {field}")


def _date(value: object) -> date | None:
    if value in (None, ""):
        return None
    # Actual XHR uses an eight-digit JSON integer, not only a string.
    if type(value) is int:
        if not 10000000 <= value <= 99999999:
            raise MachineParseError("Invalid YMD_biz")
        value = str(value)
    if isinstance(value, str):
        for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass
    raise MachineParseError("Invalid YMD_biz")


def _text(value: object, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise MachineParseError(f"Invalid {field}")
    return value


def parse_machine_page(data: dict[str, object]) -> PscubeMachinePage:
    """Pure JSON mapping. Unknown source fields are ignored, never guessed."""
    if not isinstance(data, dict) or not all(key in data for key in ("Ki", "count", "page", "pageMax")):
        raise MachineParseError("Missing machine page fields")
    count = _integer(data["count"], "count")
    page = _integer(data["page"], "page")
    maximum = _integer(data["pageMax"], "pageMax")
    if page < 1 or (maximum == 0 and (count != 0 or page != 1)) or (maximum > 0 and page > maximum):
        raise MachineParseError("Invalid pagination")
    if not isinstance(data["Ki"], list):
        raise MachineParseError("Ki must be an array")
    business_date = _date(data.get("YMD_biz"))
    machines = []
    for row in data["Ki"]:
        if not isinstance(row, dict) or not isinstance(row.get("nmk_kisyu"), str) or not row["nmk_kisyu"].strip():
            raise MachineParseError("Missing machine name")
        listing = row.get("list")
        if not isinstance(listing, dict) or not isinstance(listing.get("cd_dai"), list):
            raise MachineParseError("Missing list.cd_dai")
        numbers = listing["cd_dai"]
        if any(not isinstance(n, str) or not n.isascii() or not n.isdigit() for n in numbers):
            raise MachineParseError("Unit numbers must be digit strings")
        rate = row.get("bai")
        if rate is not None and rate != "":
            try:
                if isinstance(rate, bool):
                    raise ValueError
                rate = float(rate)
                if not math.isfinite(rate) or rate < 0:
                    raise ValueError
            except (ValueError, TypeError):
                raise MachineParseError("Invalid bai") from None
        else:
            rate = None
        machines.append(PscubeMachine(
            business_date=_date(row.get("YMD_biz")), machine_name=row["nmk_kisyu"],
            cd_ps=_integer(row.get("cd_ps"), "cd_ps", optional=True), rate=rate,
            unit_count=_integer(row.get("ct_dai"), "ct_dai", optional=True),
            machine_code=_text(listing.get("cd_kisyu"), "cd_kisyu"),
            unit_numbers=list(numbers), machine_path=_text(row.get("mph"), "mph"),
        ))
    if count == 0 and machines:
        raise MachineParseError("Nonempty Ki with zero count")
    return PscubeMachinePage(business_date, count, page, maximum, machines)


class PscubeParser:
    def parse(self, html: str) -> list[dict[str, object]]:
        raise ParserNotImplementedError("PScube parser requires verified HTML fixtures")

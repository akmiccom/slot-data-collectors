"""PScube-specific contracts; identifiers retain leading zeros."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PscubeMachine:
    business_date: date | None  # YMD_biz
    machine_name: str  # nmk_kisyu
    cd_ps: int | None
    rate: float | None  # bai
    unit_count: int | None  # ct_dai
    machine_code: str | None  # list.cd_kisyu
    unit_numbers: list[str]  # list.cd_dai
    machine_path: str | None  # mph (not fetched)


@dataclass(frozen=True)
class PscubeMachinePage:
    business_date: date | None
    count: int
    page: int
    page_max: int
    machines: list[PscubeMachine]

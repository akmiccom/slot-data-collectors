"""PScube-specific contracts; identifiers retain leading zeros."""

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class PscubeGraph:
    business_date: date
    title: str | None
    src: str | None = field(repr=False)
    legend: object = field(repr=False)


@dataclass(frozen=True)
class PscubeUnitDaily:
    business_date: date
    unit_no: str
    machine_name: str | None
    machine_code: str | None
    bb: int | None
    rb: int | None
    bb_probability: float | None
    rb_probability: float | None
    combined_probability: float | None
    max_payout: int | None
    estimated_game: int | None
    estimated_game_candidates: list[int]
    game_estimation_spread: float | None
    graph_src: str | None = field(repr=False)


@dataclass(frozen=True)
class PscubeUnitDetail:
    days: list[PscubeUnitDaily]
    graphs: list[PscubeGraph]

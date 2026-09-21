"""Source-independent slot results. Dates refer to the source's business date."""

from dataclasses import dataclass, field
from datetime import date as Date, datetime, timezone


@dataclass(frozen=True, kw_only=True)
class SlotResult:
    unit_no: int
    date: Date
    source: str
    hall_id: int | None = None
    model_id: int | None = None
    hall_name: str | None = None
    model_name: str | None = None
    game: int | None = None
    bb: int | None = None
    rb: int | None = None
    medal: int | None = None
    source_url: str | None = None
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        for name in ("unit_no", "hall_id", "model_id", "game", "bb", "rb", "medal"):
            value = getattr(self, name)
            if value is None and name != "unit_no":
                continue
            if type(value) is not int:
                raise ValueError(f"{name} must be an integer")
            if name == "unit_no" and value <= 0:
                raise ValueError("unit_no must be positive")
            if name in ("game", "bb", "rb") and value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if type(self.date) is not Date:
            raise ValueError("date must be a date, not a datetime")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a nonempty string")
        for name in ("hall_name", "model_name", "source_url"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None")
        if not isinstance(self.collected_at, datetime) or self.collected_at.utcoffset() is None:
            raise ValueError("collected_at must be a timezone-aware datetime")

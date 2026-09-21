"""REITO collector interface shared across halls."""

from common.models import SlotResult


class ReitowebCollector:
    def collect(self, url: str) -> list[SlotResult]:
        raise NotImplementedError("REITO collection is not implemented")

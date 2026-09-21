"""Source mappings belong here, never HTML selectors or HTTP requests."""

from collections.abc import Mapping
from datetime import datetime
from common.exceptions import NormalizationError
from common.models import SlotResult


def normalize_pscube(
    row: Mapping[str, object], *, source_url: str, collected_at: datetime
) -> SlotResult:
    """Define the mapping after the real parser's field contract is established."""
    raise NormalizationError("PScube normalization requires verified source fields")

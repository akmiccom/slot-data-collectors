"""Game estimates from rounded denominators, never exact observed game counts."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class GameEstimate:
    value: int | None
    candidates: list[int]
    spread: float | None


def displayed_probability(games: int, count: int) -> Decimal:
    return (Decimal(games) / Decimal(count)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def estimate_game(bb: int | None, rb: int | None, bb_probability: float | None,
                  rb_probability: float | None, combined_probability: float | None) -> GameEstimate:
    for count in (bb, rb):
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("Invalid event count")
    total = bb + rb if bb is not None and rb is not None else None
    pairs: list[tuple[int, Decimal]] = []
    for count, probability in ((bb, bb_probability), (rb, rb_probability), (total, combined_probability)):
        if probability is None:
            continue
        if isinstance(probability, bool):
            raise ValueError("Invalid denominator")
        p = Decimal(str(probability))
        if not p.is_finite() or p <= 0:
            raise ValueError("Invalid denominator")
        if count is not None and count > 0:
            pairs.append((count, p))
    if not pairs:
        return GameEstimate(None, [], None)
    values = [Decimal(count) * p for count, p in pairs]
    mean = sum(values) / len(values)
    center = int(mean.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    candidates = [g for g in range(max(0, center - 20), center + 21)
                  if all(displayed_probability(g, count) == p for count, p in pairs)]
    # Ties prefer the larger integer, consistent with half-up for nonnegative games.
    chosen = min(candidates, key=lambda g: (abs(Decimal(g) - mean), -g)) if candidates else center
    return GameEstimate(chosen, candidates, float(max(values) - min(values)))

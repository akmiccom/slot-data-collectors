from datetime import date, datetime
import pytest
from common.models import SlotResult


def result(**overrides):
    return SlotResult(**{"unit_no": 1, "date": date(2026, 9, 21), "source": "pscube", **overrides})


def test_normal_result():
    value = result(game=5000, bb=20, rb=10, medal=-500)
    assert (value.game, value.bb, value.rb, value.medal) == (5000, 20, 10, -500)
    assert value.collected_at.utcoffset().total_seconds() == 0


def test_missing_values():
    value = result()
    for name in ("hall_id", "model_id", "hall_name", "model_name", "game", "bb", "rb", "medal", "source_url"):
        assert getattr(value, name) is None


@pytest.mark.parametrize("source", ["pscube", "reitoweb", "minrepo", "future_source"])
def test_source_preserved(source):
    assert result(source=source).source == source


@pytest.mark.parametrize("field,value", [
    ("unit_no", 0), ("unit_no", -1), ("unit_no", None), ("unit_no", True),
    ("game", -1), ("bb", -1), ("rb", -1), ("game", "100"), ("bb", 1.5),
    ("source", " "), ("date", "2026-09-21"), ("date", datetime(2026, 9, 21)),
    ("collected_at", datetime(2026, 9, 21)),
])
def test_invalid_values(field, value):
    with pytest.raises(ValueError):
        result(**{field: value})


def test_zero_counts():
    value = result(game=0, bb=0, rb=0)
    assert value.game == value.bb == value.rb == 0

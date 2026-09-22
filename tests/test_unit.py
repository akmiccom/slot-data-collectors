import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
import pytest
import requests
from collectors.pscube.estimation import displayed_probability, estimate_game
from collectors.pscube.unit_parser import parse_unit_detail, number
from collectors.pscube.unit_request import unit_request_params
from collectors.pscube.client import PscubeClient
from collectors.pscube.collector import PscubeCollector
from common.exceptions import UnitParseError, UnitRequestUnsupported
from jobs import inspect_pscube_unit as cli

URL = "https://example.invalid/h/sample/cgi-bin/nc-v06-001.php?cd_dai=0272"
# Synthetic request configuration, never real credentials.
HTML = '''<script>api.apikey = 'fixture-key';
api.token = JSON.parse('{"_i":"fixture-i","_t":123}');
api06.show('0272', '20260922');</script>'''


@pytest.fixture
def payload():
    return json.loads((Path(__file__).parent / "fixtures/pscube_unit.json").read_text(encoding="utf-8"))


def test_estimation_candidates():
    result = estimate_game(38, 25, 193.5, 294.1, 116.7)
    assert result.value == 7353
    assert result.candidates == [7352, 7353]
    assert result.spread == pytest.approx(0.9)
    assert displayed_probability(21, 20) == Decimal("1.1")


def test_zero_and_missing():
    assert estimate_game(0, 1, None, 295, 295).value == 295
    assert estimate_game(0, 0, None, None, None).value is None
    assert estimate_game(None, None, None, None, None).candidates == []
    assert estimate_game(None, 1, None, 295, 999).value == 295


def test_single_and_no_candidates():
    assert estimate_game(1, 0, 12, None, None).candidates == [12]
    result = estimate_game(1, 1, 10, 20, None)
    assert result.candidates == [] and result.value == 15 and result.spread == 10


def test_four_days(payload):
    detail = parse_unit_detail(json.loads(json.dumps(payload, ensure_ascii=True)))
    assert [d.business_date for d in detail.days] == [date(2026, 9, n) for n in (22, 21, 20, 19)]
    assert all(d.unit_no == "0272" for d in detail.days)
    day = detail.days[1]
    assert (day.bb, day.rb, day.bb_probability, day.rb_probability, day.combined_probability, day.max_payout) == (38,25,193.5,294.1,116.7,3715)
    assert day.estimated_game == 7353
    assert day.graph_src == "/synthetic-graph.png"
    assert detail.days[0].graph_src is None
    assert detail.days[0].bb_probability is None
    assert detail.graphs[0].title == "1日前"
    assert detail.graphs[0].legend == ["sample"]


def test_missing_past(payload):
    for row in payload["Data"]:
        if row is not None:
            row["item"] = [False, None, ""]
    assert all(d.bb is None and d.estimated_game is None for d in parse_unit_detail(payload).days)


@pytest.mark.parametrize("value", [True, -1, "NaN", "Infinity", {}, "bad"])
def test_bad_numbers(value):
    with pytest.raises(UnitParseError):
        number(value, probability=True)


@pytest.mark.parametrize("value", [False, None, "", "  "])
def test_missing_numbers(value):
    assert number(value) is None


def test_numeric_strings():
    assert number("38") == 38
    assert number("1/193.5", probability=True) == 193.5
    assert number(0) == 0


def test_request_params():
    params = unit_request_params(HTML, "0272")
    assert params == {"cd_dai":"0272", "YMD_biz":"20260922", "apikey":"fixture-key", "_i":"fixture-i", "_t":123, "page":1}
    with pytest.raises(UnitRequestUnsupported):
        unit_request_params("<html>consent</html>", "0272")


def response(body):
    result = requests.Response()
    result.status_code = 200
    result.url = URL
    result.encoding = "utf-8"
    result._content = body.encode("utf-8")
    result._content_consumed = True
    result.headers["Content-Type"] = "application/json"
    return result


def test_collector_order(payload, monkeypatch):
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [response(HTML), response(json.dumps(payload))]
    sleep = MagicMock()
    monkeypatch.setattr("collectors.pscube.client.time.monotonic", lambda: 10)
    monkeypatch.setattr("collectors.pscube.client.time.sleep", sleep)
    result = PscubeCollector(PscubeClient(session=session)).collect_unit(URL)
    assert len(result.days) == 4
    assert session.get.call_count == 2
    first, second = session.get.call_args_list
    assert first.args == (URL,)
    assert second.args[0].endswith("nc-m06-001.php")
    assert second.kwargs["params"]["cd_dai"] == "0272"
    assert second.kwargs["headers"]["Referer"] == URL
    sleep.assert_called_once_with(1)


def test_wrong_unit(payload):
    payload["Dai"]["cd_dai"] = "0273"
    client = MagicMock(spec=PscubeClient)
    client.fetch.return_value = HTML
    client.fetch_json.return_value.data = payload
    with pytest.raises(UnitParseError):
        PscubeCollector(client).collect_unit(URL)


def test_cli_save_and_redaction(payload, monkeypatch, tmp_path, capsys, caplog):
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [response(HTML), response(json.dumps(payload))]
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setattr(cli, "PscubeClient", lambda **kw: PscubeClient(session=session, request_interval=0))
    assert cli.main([URL, "--save-json"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)[1]["estimated_game"] == 7353
    assert "synthetic-graph.png" not in output
    assert "fixture-key" not in output + caplog.text
    files = list((tmp_path / "debug/pscube").glob("*_unit.json"))
    assert len(files) == 1
    assert cli.main(["--from-json", str(files[0])]) == 0
    assert session.get.call_count == 2


def test_help(capsys):
    with pytest.raises(SystemExit) as result:
        cli.main(["--help"])
    assert result.value.code == 0
    assert "--save-json" in capsys.readouterr().out


def test_missing_config_does_not_request_xhr():
    client = MagicMock(spec=PscubeClient)
    client.fetch.return_value = "<html>no request configuration</html>"
    with pytest.raises(UnitRequestUnsupported):
        PscubeCollector(client).collect_unit(URL)
    client.fetch_json.assert_not_called()


def test_save_before_parse_failure(monkeypatch, tmp_path, caplog):
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [response(HTML), response('{"error":"fixture-private-value"}')]
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setattr(cli, "PscubeClient", lambda **kw: PscubeClient(session=session, request_interval=0))
    assert cli.main([URL, "--save-json"]) == 1
    assert len(list((tmp_path / "debug/pscube").glob("*_unit.json"))) == 1
    assert caplog.records[-1].stage == "parse_json"
    assert "fixture-private-value" not in caplog.text
    assert "fixture-key" not in caplog.text


def test_malformed_request_config():
    for html in (HTML.replace('"_t":123', '"other":123'), HTML.replace("fixture-key", ""),
                 HTML.replace('"_t":123', '"_t":true')):
        with pytest.raises(UnitRequestUnsupported):
            unit_request_params(html, "0272")


def test_missing_or_invalid_detail(payload):
    payload["Dai"]["cd_dai"] = 272
    with pytest.raises(UnitParseError):
        parse_unit_detail(payload)


def test_unknown_and_duplicate_titles(payload):
    payload["Data"].append({"title":"未対応項目","item":[999]})
    assert parse_unit_detail(payload).days[1].estimated_game == 7353
    payload["Data"].append({"title":"BIG","item":[1]})
    with pytest.raises(UnitParseError):
        parse_unit_detail(payload)

import copy
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock
import pytest
import requests
from collectors.pscube.client import PscubeClient
from collectors.pscube.collector import PscubeCollector
from collectors.pscube.parser import parse_machine_page
from common.exceptions import JsonDecodeError, MachineParseError, FetchError
from jobs import inspect_pscube_machines as cli

URL = "https://example.invalid/h/sample/cgi-bin/nc-v03-001.php?cd_ps=2"


@pytest.fixture
def payload():
    return json.loads((Path(__file__).parent / "fixtures/pscube_machines.json").read_text(encoding="utf-8"))


def response(body, status=200):
    r = requests.Response()
    r.status_code = status
    r.url = URL
    r.encoding = "utf-8"
    r.headers["Content-Type"] = "application/json"
    r._content = body.encode("utf-8")
    r._content_consumed = True
    return r


def test_mapping(payload):
    p = parse_machine_page(payload)
    assert (p.business_date, p.count, p.page, p.page_max) == (date(2026, 9, 22), 2, 1, 2)
    m = p.machines[0]
    assert m.machine_name == "テスト機種A"
    assert m.unit_count == 3
    assert m.unit_numbers == ["0272", "0273", "0274"]
    assert m.machine_code == "00123"
    assert m.rate == 21.74 and m.cd_ps == 2
    assert m.machine_path == "sample-machine.php"


def test_integer_business_dates(payload):
    payload["YMD_biz"] = 20260922
    payload["Ki"][0]["YMD_biz"] = 20260922
    parsed = parse_machine_page(payload)
    assert parsed.business_date == date(2026, 9, 22)
    assert parsed.machines[0].business_date == date(2026, 9, 22)


@pytest.mark.parametrize("value", [True, 20260922.0, 20260230, 2026092, 0])
def test_invalid_integer_business_dates(payload, value):
    payload["YMD_biz"] = value
    with pytest.raises(MachineParseError):
        parse_machine_page(payload)


@pytest.mark.parametrize("maximum", [0, 1])
def test_empty(maximum):
    p = parse_machine_page({"Ki": [], "count": 0, "page": 1, "pageMax": maximum})
    assert p.machines == [] and p.business_date is None


@pytest.mark.parametrize("key", ["Ki", "count", "page", "pageMax"])
def test_required_top(payload, key):
    del payload[key]
    with pytest.raises(MachineParseError):
        parse_machine_page(payload)


@pytest.mark.parametrize("key", ["nmk_kisyu", "list"])
def test_required_machine(payload, key):
    del payload["Ki"][0][key]
    with pytest.raises(MachineParseError):
        parse_machine_page(payload)


def test_optional_fields(payload):
    payload["Ki"] = [{"nmk_kisyu": "sample", "list": {"cd_dai": []}}]
    m = parse_machine_page(payload).machines[0]
    assert m.rate is m.unit_count is m.cd_ps is m.machine_code is m.machine_path is m.business_date is None


@pytest.mark.parametrize("numbers", [[272], [True], [""], ["abc"]])
def test_invalid_units(payload, numbers):
    payload["Ki"][0]["list"]["cd_dai"] = numbers
    with pytest.raises(MachineParseError):
        parse_machine_page(payload)


@pytest.mark.parametrize("body", ["<html>not JSON</html>", "[]", "null"])
def test_invalid_json(body):
    session = MagicMock(spec=requests.Session)
    session.get.return_value = response(body)
    with pytest.raises(JsonDecodeError):
        PscubeClient(session=session).fetch_json(URL, params={})


def test_http_error():
    session = MagicMock(spec=requests.Session)
    session.get.return_value = response("{}", 403)
    with pytest.raises(FetchError):
        PscubeClient(session=session).fetch_json(URL, params={})


def setup_session(payload):
    second = copy.deepcopy(payload)
    second["page"] = 2
    second["Ki"][0]["nmk_kisyu"] = "テスト機種B"
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [response("<html></html>"), response(json.dumps(payload)), response(json.dumps(second))]
    return session


def test_order_and_interval(payload, monkeypatch):
    session = setup_session(payload)
    monkeypatch.setattr("collectors.pscube.client.time.monotonic", lambda: 1)
    sleep = MagicMock()
    monkeypatch.setattr("collectors.pscube.client.time.sleep", sleep)
    result = PscubeCollector(PscubeClient(session=session, request_interval=2)).collect_machines(URL)
    assert [m.machine_name for m in result] == ["テスト機種A", "テスト機種B"]
    calls = session.get.call_args_list
    assert calls[0].args == (URL,)
    assert calls[1].args[0].endswith("/nc-m03-001.php")
    assert calls[1].kwargs["params"] == {"cd_ps": 2, "bai": 0, "YMD_biz": "", "page": 1, "loaded": ""}
    assert calls[2].kwargs["params"]["page"] == 2
    assert sleep.call_count == 2
    assert all(call.args == (2,) for call in sleep.call_args_list)


def test_pagination_mismatch(payload):
    client = MagicMock(spec=PscubeClient)
    payload["page"] = 2
    client.fetch_json.return_value.data = payload
    with pytest.raises(MachineParseError):
        PscubeCollector(client).collect_machines(URL)


@pytest.mark.parametrize("field,value", [("pageMax", 3), ("count", 3), ("YMD_biz", "20260923")])
def test_metadata_change(payload, field, value):
    second = copy.deepcopy(payload)
    second["page"] = 2
    second[field] = value
    client = MagicMock(spec=PscubeClient)
    client.fetch_json.side_effect = [MagicMock(data=payload), MagicMock(data=second)]
    with pytest.raises(MachineParseError):
        PscubeCollector(client).collect_machines(URL)


def test_cli_save(payload, monkeypatch, tmp_path, capsys):
    session = setup_session(payload)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setattr(cli, "PscubeClient", lambda **kw: PscubeClient(session=session, request_interval=0))
    assert cli.main([URL, "--save-json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["count"] == output["pageMax"] == output["collected_machine_count"] == 2
    assert output["machines"][0]["unit_numbers_count"] == 3
    files = list((tmp_path / "debug/pscube").glob("*.json"))
    assert len(files) == 2
    assert sorted(json.loads(p.read_text(encoding="utf-8"))["page"] for p in files) == [1, 2]


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as result:
        cli.main(["--help"])
    assert result.value.code == 0
    assert "--save-json" in capsys.readouterr().out


@pytest.mark.parametrize("field,value", [("bai", "NaN"), ("ct_dai", -1), ("cd_ps", True), ("YMD_biz", "invalid")])
def test_invalid_fields(payload, field, value):
    payload["Ki"][0][field] = value
    with pytest.raises(MachineParseError):
        parse_machine_page(payload)


def test_cli_failure_hides_exception(monkeypatch, caplog):
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    client = MagicMock()
    client.__enter__.return_value.fetch.side_effect = FetchError("synthetic-sensitive-marker")
    monkeypatch.setattr(cli, "PscubeClient", lambda **kw: client)
    assert cli.main([URL]) == 1
    assert "synthetic-sensitive-marker" not in caplog.text
    assert "machine_collection_failed" in caplog.text
    record = caplog.records[-1]
    assert record.stage == "initial_page"
    assert record.error_type == "FetchError"


def test_parse_failure_still_saves_json(monkeypatch, tmp_path, caplog):
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [response("<html></html>"), response('{"unexpected": true}')]
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setattr(cli, "PscubeClient", lambda **kw: PscubeClient(session=session, request_interval=0))
    assert cli.main([URL, "--save-json"]) == 1
    files = list((tmp_path / "debug/pscube").glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text()) == {"unexpected": True}
    assert caplog.records[-1].stage == "parse_json"
    assert caplog.records[-1].error_type == "MachineParseError"


def test_http_status_preserved():
    session = MagicMock(spec=requests.Session)
    session.get.return_value = response("{}", 403)
    with pytest.raises(FetchError) as error:
        PscubeClient(session=session).fetch_json(URL, params={})
    assert error.value.status_code == 403

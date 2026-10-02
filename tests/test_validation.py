from dataclasses import replace
from datetime import date
import json
from pathlib import Path
from io import BytesIO
from unittest.mock import MagicMock

from PIL import Image

import pytest

from collectors.pscube import validation as v
from collectors.pscube.graph import GraphEstimate, GraphProfile, fetch_graph
from collectors.pscube.models import PscubeMachine
from collectors.pscube.unit_parser import parse_unit_detail
from common.exceptions import FetchError, UnitParseError
from jobs import validate_pscube_units as cli, evaluate_pscube_validation as evaluate_cli

DAY = date(2026, 9, 21)
URL = "https://example.invalid/h/test/cgi-bin/nc-v03-001.php?cd_ps=2"
MACHINE = PscubeMachine(DAY, "sample", 2, 0, 3, "code", ["0272", "0273", "0274"], None)


@pytest.fixture
def collector():
    payload = json.loads((Path(__file__).parent / "fixtures/pscube_unit.json").read_text(encoding="utf-8"))
    detail = parse_unit_detail(payload)
    mock = MagicMock()
    mock.collect_machines.return_value = [MACHINE]
    mock.collect_unit.side_effect = lambda url: replace(detail, days=[replace(d, unit_no=url[-4:]) for d in detail.days])
    return mock


@pytest.fixture
def graph(monkeypatch):
    fetch = MagicMock(return_value=Path("synthetic.png"))
    monkeypatch.setattr(v, "fetch_graph", fetch)
    estimate = GraphEstimate(DAY, "0272", "synthetic.png", 800, 730,
                             selected_profile=GraphProfile(), estimated_medal=3256, confidence="high",
                             warnings=["synthetic warning"])
    monkeypatch.setattr(v, "estimate_graph", lambda *args: estimate)
    return fetch, estimate


def run(tmp_path, collector, **kwargs):
    return v.validate_units(collector, URL, MACHINE, DAY, MACHINE.unit_numbers,
                            tmp_path / "result.csv", tmp_path, **kwargs)


def test_selection():
    assert v.select_machine([MACHINE], "sample") == MACHINE
    with pytest.raises(ValueError):
        v.select_machine([MACHINE, MACHINE], "sample")
    with pytest.raises(ValueError):
        v.select_machine([MACHINE], "absent")
    assert v.select_units(MACHINE, units="0274,0272") == ["0274", "0272"]
    assert v.select_units(MACHINE, limit=2) == ["0272", "0273"]
    assert v.select_units(MACHINE, all_units=True) == MACHINE.unit_numbers
    for kwargs in ({}, {"units":"272"}, {"units":"0272,0272"}, {"limit":0}):
        with pytest.raises(ValueError):
            v.select_units(MACHINE, **kwargs)


def test_selection_required():
    with pytest.raises(SystemExit) as error:
        cli.main(["--hall-url", URL, "--machine-name", "sample", "--date", "20260921"])
    assert error.value.code == 2


def test_csv_success_resume_force(tmp_path, collector, graph):
    assert run(tmp_path, collector)["success"] == 3
    assert collector.collect_unit.call_count == graph[0].call_count == 3
    path = tmp_path / "result.csv"
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    rows = v.read_rows(path)
    assert rows[0]["unit_no"] == "0272"
    assert rows[0]["bb"] == "38" and rows[0]["estimated_game"] == "7353"
    assert rows[0]["graph_profile_top"] == "5000"
    assert rows[0]["estimated_medal"] == "3256"
    assert json.loads(rows[0]["estimated_game_candidates"]) == [7352, 7353]
    assert json.loads(rows[0]["graph_warnings"]) == ["synthetic warning"]
    rows[0]["minrepo_medal"] = "3250"
    v.write_rows(path, rows)
    assert run(tmp_path, collector)["skipped"] == 3
    assert collector.collect_unit.call_count == 3
    assert run(tmp_path, collector, force=True)["processed"] == 3
    assert v.read_rows(path)[0]["minrepo_medal"] == "3250"


@pytest.mark.parametrize("error,status", [(FetchError("private", status_code=500), "unit_fetch_failed"),
                                         (UnitParseError("private"), "parse_failed")])
def test_failure_continues(tmp_path, collector, graph, error, status, caplog):
    collector.collect_unit.side_effect = error
    assert run(tmp_path, collector)["failure"] == 3
    assert all(r["status"] == status for r in v.read_rows(tmp_path / "result.csv"))
    assert "private" not in caplog.text


@pytest.mark.parametrize("code", [403, 429])
@pytest.mark.parametrize("stage", ["unit", "graph"])
def test_access_error_stops(tmp_path, collector, graph, code, stage):
    if stage == "unit":
        collector.collect_unit.side_effect = FetchError("private", status_code=code)
    else:
        graph[0].side_effect = FetchError("private", status_code=code)
    report = run(tmp_path, collector)
    assert report["stopped"] and report["not_processed"] == 2
    assert collector.collect_unit.call_count == 1
    assert len(v.read_rows(tmp_path / "result.csv")) == 1


def test_low_confidence_and_annotation(tmp_path, collector, graph, monkeypatch):
    graph[1].estimated_medal = None
    graph[1].confidence = "low"
    annotation = MagicMock()
    monkeypatch.setattr(v, "annotate_graph", annotation)
    run(tmp_path, collector)
    annotation.assert_not_called()
    assert v.read_rows(tmp_path / "result.csv")[0]["status"] == "graph_low_confidence"
    run(tmp_path, collector, annotate=True)
    assert annotation.call_count == 3


def test_missing_day_graph(tmp_path, collector, graph):
    detail = collector.collect_unit("url0272")
    collector.collect_unit.side_effect = None
    collector.collect_unit.return_value = replace(detail, days=[])
    run(tmp_path, collector)
    assert v.read_rows(tmp_path / "result.csv")[0]["status"] == "no_daily_data"
    collector.collect_unit.return_value = replace(detail, days=[replace(d, graph_src=None) for d in detail.days])
    run(tmp_path, collector)
    assert v.read_rows(tmp_path / "result.csv")[0]["status"] == "no_graph"
    graph[0].assert_not_called()


def test_context_mismatch(tmp_path, collector, graph):
    run(tmp_path, collector)
    with pytest.raises(ValueError):
        v.validate_units(collector, URL.replace("test", "other"), MACHINE, DAY, ["0272"],
                         tmp_path / "result.csv", tmp_path)
    assert collector.collect_unit.call_count == 3


def test_evaluation(tmp_path):
    rows = [{key:"" for key in v.FIELDS} for _ in range(3)]
    for row, estimate, ref1, ref2 in zip(rows, (3256,1393,0), (3250,1390,""), (3245,1386,"")):
        row.update(estimated_medal=str(estimate), minrepo_medal=str(ref1), anaslo_medal=str(ref2))
    report = v.evaluate_rows(rows)
    assert report["minrepo"]["MAE"] == report["minrepo"]["median_absolute_error"] == 4.5
    assert report["minrepo"]["mean_error"] == 4.5
    assert report["minrepo"]["max_absolute_error"] == 6
    assert report["anaslo"]["MAE"] == 9
    assert report["anaslo"]["within_10_rate"] == 50
    for threshold in (10,25,50,100,200):
        assert report["minrepo"][f"within_{threshold}_count"] == 2
        assert report["minrepo"][f"within_{threshold}_rate"] == 100
    assert rows[0]["error_vs_minrepo"] == "6"
    assert rows[2]["error_vs_minrepo"] == ""
    path = tmp_path / "compare.csv"
    v.write_rows(path, rows)
    assert evaluate_cli.main([str(path)]) == 0
    rows[0]["minrepo_medal"] = "private-invalid"
    v.write_rows(path, rows)
    before = path.read_bytes()
    assert evaluate_cli.main([str(path)]) == 1
    assert path.read_bytes() == before


def test_thresholds_signed_and_missing():
    rows = [{key:"" for key in v.FIELDS} for _ in range(7)]
    for row, error in zip(rows, (-10,25,50,100,200,201)):
        row.update(estimated_medal=str(error), minrepo_medal="0")
    rows[-1].update(minrepo_medal="1", error_vs_minrepo="stale")
    report = v.evaluate_rows(rows)["minrepo"]
    assert report["sample_count"] == 6
    for threshold, count in zip((10,25,50,100,200), (1,2,3,4,5)):
        assert report[f"within_{threshold}_count"] == count
        assert report[f"within_{threshold}_rate"] == pytest.approx(count/6*100)
    assert rows[0]["error_vs_minrepo"] == "-10"
    assert rows[-1]["error_vs_minrepo"] == ""
    assert v.evaluate_rows([])["minrepo"]["MAE"] is None


def test_cli(tmp_path, collector, graph, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "PscubeCollector", lambda client: collector)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setattr(cli, "load_dotenv", lambda *args: None)
    assert cli.main(["--hall-url", URL, "--machine-name", "sample", "--date", "20260921",
                     "--limit", "2"]) == 0
    assert collector.collect_unit.call_count == 2


def test_graph_reuses_detail(collector, tmp_path, monkeypatch):
    detail = collector.collect_unit("url0272")
    detail = replace(detail, graphs=[replace(g, src="synthetic.png") for g in detail.graphs])
    stream = BytesIO()
    Image.new("RGB", (100,100)).save(stream, format="PNG")
    collector.client.fetch_bytes.return_value = stream.getvalue()
    collect = MagicMock()
    monkeypatch.setattr("collectors.pscube.graph.PscubeCollector.collect_unit", collect)
    path = fetch_graph(collector.client, URL.replace("v03", "v06"), DAY, "0272", tmp_path, detail=detail)
    assert path.exists()
    collect.assert_not_called()
    assert collector.client.fetch_bytes.call_count == 1


def test_cli_hall(tmp_path, collector, graph, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "PscubeCollector", lambda client: collector)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setattr(cli, "load_dotenv", lambda *args: None)
    assert cli.main(["--hall", "yasuda5", "--machine-name", "sample",
                     "--date", "20260921", "--limit", "2"]) == 0
    collector.collect_machines.assert_called_once_with(
        "https://yasudaya.pscube.jp/h/a744203/cgi-bin/nc-v03-001.php?cd_ps=2")
    assert collector.collect_unit.call_count == 2


def test_cli_hall_exclusive():
    with pytest.raises(SystemExit) as error:
        cli.main(["--hall", "yasuda5", "--hall-url", URL, "--machine-name", "sample",
                  "--date", "20260921", "--limit", "2"])
    assert error.value.code == 2


def test_cli_unknown_hall(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(cli, "PscubeClient", client)
    assert cli.main(["--hall", "unknown", "--machine-name", "sample",
                     "--date", "20260921", "--limit", "2"]) == 1
    client.assert_not_called()

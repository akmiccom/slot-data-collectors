from dataclasses import asdict
import importlib
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from collectors.pscube.client import FetchResult, PscubeClient
from collectors.pscube.inspect import diagnose_html, save_html
from common.exceptions import FetchError
from common.logging_config import CollectionFormatter
from jobs import inspect_pscube

FIXTURES = Path(__file__).parent / "fixtures"


def test_approval_diagnostics():
    result = diagnose_html((FIXTURES / "pscube_inspection_approval.html").read_text(encoding="utf-8"))
    assert result.title == "利用規約の確認"
    assert result.form_count == 2
    assert result.has_checkbox and result.has_password_input
    assert result.submit_count == 3
    assert result.link_count == result.script_count == result.iframe_count == 1
    assert result.meta_refresh
    assert result.possible_approval_page
    assert set(result.approval_keywords) == {"承認", "同意", "確認", "利用規約", "agreement", "consent"}


def test_normal_diagnostics():
    result = diagnose_html((FIXTURES / "pscube_inspection_normal.html").read_text(encoding="utf-8"))
    assert result.title == "店舗データ"
    assert result.link_count == 1
    assert not result.possible_approval_page
    assert not result.meta_refresh
    assert not result.has_checkbox
    assert not result.has_password_input
    assert result.form_count == result.submit_count == 0
    assert diagnose_html("").title is None


def response(status=200, redirected=False):
    value = requests.Response()
    value.status_code = status
    value.url = "https://example.invalid/end?token=query-secret"
    value.encoding = "utf-8"
    value._content = "<title>店舗データ</title>".encode("utf-8")
    value.headers.update({"Content-Type": "text/html; charset=utf-8", "Set-Cookie": "sid=cookie-secret", "X-Api-Key": "api-secret", "Location": "/?password=password-secret"})
    value.cookies.set("sid", "cookie-secret")
    if redirected:
        hop = requests.Response()
        hop.status_code = 302
        hop.cookies.set("redirect_cookie", "redirect-secret")
        value.history = [hop]
    return value


@pytest.mark.parametrize("status", [200, 403, 429, 500])
def test_fetch_result_retains_http_diagnostics_without_secrets(status):
    session = MagicMock(spec=requests.Session)
    session.cookies = requests.cookies.RequestsCookieJar()
    session.cookies.set("session_cookie", "session-secret")
    value = response(status, redirected=True)
    session.get.return_value = value
    result = PscubeClient(session=session).fetch_result("https://user:pass@example.invalid/start?api_key=request-secret")
    assert isinstance(result, FetchResult)
    assert result.status_code == status
    assert result.redirected
    assert result.response_length == len(value.content)
    assert result.content_type == "text/html"
    assert result.cookie_names == ("redirect_cookie", "session_cookie", "sid")
    assert result.html == value.text
    assert result.requested_url == result.final_url == "https://example.invalid/[redacted]"
    assert session.get.call_args.kwargs["allow_redirects"] is True
    assert session.get.call_count == 1
    text = json.dumps(asdict(result))
    for secret in ("cookie-secret", "api-secret", "query-secret", "request-secret", "password-secret", "session-secret", "redirect-secret"):
        assert secret not in text
    assert "Set-Cookie" not in result.response_headers
    assert result.html not in repr(result)


def test_inspection_transport_error_is_sanitized():
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError("password-secret")
    with pytest.raises(FetchError) as error:
        PscubeClient(session=session).fetch_result("https://example.invalid/")
    assert "password-secret" not in str(error.value)


def test_save_html_filename_and_content(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    clock = MagicMock()
    clock.now.return_value = datetime(2026, 9, 22, tzinfo=timezone.utc)
    monkeypatch.setattr("collectors.pscube.inspect.datetime", clock)
    result = save_html("<title>店舗</title>", "https://example.invalid/?secret=hidden", tmp_path)
    assert result.parent == tmp_path
    assert result.name.endswith("_example_invalid.html")
    assert "hidden" not in result.name
    assert result.read_text(encoding="utf-8") == "<title>店舗</title>"
    second = save_html("second", "https://example.invalid/", tmp_path)
    assert second != result


@pytest.mark.parametrize("status", [200, 403])
def test_cli_report_save_and_logs(monkeypatch, capsys, caplog, tmp_path, status):
    session = MagicMock(spec=requests.Session)
    session.cookies = requests.cookies.RequestsCookieJar()
    session.get.return_value = response(status, redirected=True)
    monkeypatch.setattr(inspect_pscube, "ROOT", tmp_path)
    monkeypatch.setattr(inspect_pscube, "configure_logging", lambda: None)
    client_factory = MagicMock(return_value=PscubeClient(session=session))
    monkeypatch.setattr(inspect_pscube, "PscubeClient", client_factory)
    monkeypatch.setenv("REQUEST_TIMEOUT", "9")
    monkeypatch.setenv("REQUEST_INTERVAL", "2")
    with caplog.at_level(logging.INFO, logger="slot_collectors"):
        code = inspect_pscube.main(["https://example.invalid/?key=request-secret", "--save-html"])
    assert code == (0 if status == 200 else 1)
    client_factory.assert_called_once_with(timeout=9, request_interval=2)
    report = json.loads(capsys.readouterr().out)
    assert report["status_code"] == status
    assert report["redirected"]
    assert report["diagnostics"]["title"] == "店舗データ"
    assert not report["possible_approval_page"]
    assert Path(report["saved_html"]).parent == tmp_path / "debug" / "pscube"
    log = "\n".join(CollectionFormatter().format(record) for record in caplog.records)
    assert '"status_code": ' + str(status) in log
    assert '"response_size":' in log
    for secret in ("cookie-secret", "api-secret", "query-secret", "request-secret", "password-secret"):
        assert secret not in log
        assert secret not in json.dumps(report)


def test_cli_no_save_and_invalid_settings(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(inspect_pscube, "ROOT", tmp_path)
    monkeypatch.setattr(inspect_pscube, "configure_logging", lambda: None)
    session = MagicMock(spec=requests.Session)
    session.cookies = requests.cookies.RequestsCookieJar()
    session.get.return_value = response()
    monkeypatch.setattr(inspect_pscube, "PscubeClient", lambda **kwargs: PscubeClient(session=session, **kwargs))
    monkeypatch.setenv("REQUEST_TIMEOUT", "")
    monkeypatch.setenv("REQUEST_INTERVAL", "")
    assert inspect_pscube.main(["https://example.invalid/"]) == 0
    assert "saved_html" not in json.loads(capsys.readouterr().out)
    assert not (tmp_path / "debug").exists()
    monkeypatch.setenv("REQUEST_TIMEOUT", "not-a-number")
    assert inspect_pscube.main(["https://example.invalid/"]) == 1
    assert session.get.call_count == 1


@pytest.mark.parametrize("url", ["file:///private", "https://user:password@example.invalid", "https://[invalid"])
def test_cli_invalid_url_never_connects(url, monkeypatch):
    monkeypatch.setattr(inspect_pscube, "configure_logging", lambda: None)
    assert inspect_pscube.main([url]) == 1


def test_import_and_help_without_http(capsys):
    importlib.import_module("collectors.pscube.inspect")
    with pytest.raises(SystemExit) as exit_info:
        inspect_pscube.main(["--help"])
    assert exit_info.value.code == 0
    assert "--save-html" in capsys.readouterr().out

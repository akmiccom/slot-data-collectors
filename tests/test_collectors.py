import logging
from unittest.mock import MagicMock
from datetime import datetime, timezone
import pytest
import requests
from collectors.pscube.client import PscubeClient
from collectors.pscube.collector import PscubeCollector
from collectors.pscube.parser import PscubeParser
from collectors.reitoweb.client import ReitowebClient
from collectors.reitoweb.collector import ReitowebCollector
from collectors.reitoweb.parser import ReitowebParser
from common.exceptions import FetchError, NormalizationError, ParserNotImplementedError
from common.logging_config import CollectionFormatter, safe_url
from common.normalize import normalize_pscube


def session_with_html():
    session = MagicMock(spec=requests.Session)
    response = session.get.return_value.__enter__.return_value
    response.text = "<html>fixture</html>"
    return session, response


def test_http_only_and_session_ownership():
    session, _ = session_with_html()
    with PscubeClient(session=session, timeout=7) as client:
        assert client.fetch("https://example.invalid/") == "<html>fixture</html>"
    assert session.get.call_args.kwargs["timeout"] == 7
    assert session.get.call_args.kwargs["headers"]["User-Agent"]
    session.close.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_http_errors_are_not_retried(status):
    session, response = session_with_html()
    response.raise_for_status.side_effect = requests.HTTPError(f"{status}: secret")
    with pytest.raises(FetchError, match="HTTP request failed") as error:
        PscubeClient(session=session, max_retries=3).fetch("https://example.invalid/")
    assert session.get.call_count == 1
    assert "secret" not in str(error.value)


def test_retry_is_bounded(monkeypatch):
    session, _ = session_with_html()
    session.get.side_effect = requests.Timeout("secret")
    sleep = MagicMock()
    monkeypatch.setattr("collectors.pscube.client.time.sleep", sleep)
    with pytest.raises(FetchError):
        PscubeClient(session=session, max_retries=1, request_interval=0).fetch("https://example.invalid/")
    assert session.get.call_count == 2
    sleep.assert_called_once_with(1)


def test_request_spacing(monkeypatch):
    session, _ = session_with_html()
    monkeypatch.setattr("collectors.pscube.client.time.monotonic", lambda: 10.0)
    sleep = MagicMock()
    monkeypatch.setattr("collectors.pscube.client.time.sleep", sleep)
    client = PscubeClient(session=session, request_interval=2)
    client.fetch("https://example.invalid/")
    client.fetch("https://example.invalid/")
    sleep.assert_called_once_with(2)


@pytest.mark.parametrize("kwargs", [{"timeout": 0}, {"timeout": float("nan")}, {"request_interval": -1}, {"max_retries": 4}])
def test_invalid_client_configuration(kwargs):
    with pytest.raises(ValueError):
        PscubeClient(**kwargs)


def test_parsers_and_reito_fail_explicitly():
    for parser in (PscubeParser(), ReitowebParser()):
        with pytest.raises(ParserNotImplementedError):
            parser.parse("<html></html>")
    with pytest.raises(NotImplementedError):
        ReitowebClient().fetch("https://example.invalid/")
    with pytest.raises(NotImplementedError):
        ReitowebCollector().collect("https://example.invalid/")
    with pytest.raises(NormalizationError):
        normalize_pscube({}, source_url="https://example.invalid/", collected_at=datetime.now(timezone.utc))


def test_collector_failure_log_hides_secrets(caplog):
    client = MagicMock(spec=PscubeClient)
    client.fetch.return_value = "<html></html>"
    url = "https://user:password@example.invalid/private-token?api_key=secret#cookie"
    with caplog.at_level(logging.INFO, logger="slot_collectors"), pytest.raises(ParserNotImplementedError):
        PscubeCollector(client).collect(url)
    record = caplog.records[-1]
    output = CollectionFormatter().format(record)
    assert record.source == "pscube"
    assert record.status == "failure"
    assert record.count is None
    assert record.url == "https://example.invalid/[redacted]"
    for secret in ("password", "private-token", "api_key", "cookie"):
        assert secret not in output


def test_collector_wires_normalization(monkeypatch, caplog):
    client = MagicMock(spec=PscubeClient)
    client.fetch.return_value = "fixture"
    parser = MagicMock(spec=PscubeParser)
    parser.parse.return_value = [{"raw": "value"}]
    from common.models import SlotResult
    from datetime import date
    expected = SlotResult(unit_no=1, date=date(2026, 9, 21), source="pscube")
    normalize = MagicMock(return_value=expected)
    monkeypatch.setattr("collectors.pscube.collector.normalize_pscube", normalize)
    with caplog.at_level(logging.INFO, logger="slot_collectors"):
        assert PscubeCollector(client, parser).collect("https://example.invalid/") == [expected]
    parser.parse.assert_called_once_with("fixture")
    assert normalize.call_args.args == ({"raw": "value"},)
    assert normalize.call_args.kwargs["collected_at"].tzinfo is not None
    assert caplog.records[-1].count == 1
    assert caplog.records[-1].status == "success"


def test_bad_url_redacted():
    assert safe_url("https://[invalid") == "[invalid-url]"

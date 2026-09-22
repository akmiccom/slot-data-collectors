"""Fail immediately if an offline test accidentally tries real HTTP."""

import pytest
import requests

# User-owned manual probe executes HTTP at import time; never import it in pytest.
collect_ignore = ["test_pscube.py"]


def pytest_sessionstart(session):
    # Block collection-time HTTP too, before autouse fixtures can take effect.
    session._http_guard = pytest.MonkeyPatch()
    def fail(*args, **kwargs):
        raise AssertionError("Real HTTP is forbidden in unit tests")
    session._http_guard.setattr(requests.sessions.Session, "request", fail)


def pytest_sessionfinish(session, exitstatus):
    session._http_guard.undo()


@pytest.fixture(autouse=True)
def block_http(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Real HTTP is forbidden in unit tests")
    monkeypatch.setattr(requests.sessions.Session, "request", fail)

"""Fail immediately if an offline test accidentally tries real HTTP."""

import pytest
import requests


@pytest.fixture(autouse=True)
def block_http(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Real HTTP is forbidden in unit tests")
    monkeypatch.setattr(requests.sessions.Session, "request", fail)

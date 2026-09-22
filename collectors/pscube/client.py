"""HTTP only. One sequential client owns one reusable session."""

import math
from dataclasses import dataclass, field
import time
from types import TracebackType
from typing import cast
import requests
from common.exceptions import FetchError, JsonDecodeError
from common.logging_config import safe_url


@dataclass(frozen=True)
class FetchResult:
    """Inspection metadata; URLs are redacted and cookie values are excluded."""

    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    response_length: int
    cookie_names: tuple[str, ...]
    html: str = field(repr=False)
    redirected: bool = False
    response_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class JsonFetchResult:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    response_length: int
    data: dict[str, object] = field(repr=False)


def _inspection_result(url: str, response: requests.Response, session: requests.Session) -> FetchResult:
    # Do not copy Set-Cookie, Location or arbitrary header values into diagnostics.
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if not all(c.isalnum() or c in "/.+-" for c in content_type):
        content_type = "[redacted]"
    headers = {name: "[redacted]" for name in response.headers if name.lower() != "set-cookie"}
    if "Content-Type" in response.headers:
        headers["Content-Type"] = content_type
    names = {cookie.name for cookie in session.cookies}
    for hop in [*response.history, response]:
        names.update(cookie.name for cookie in hop.cookies)
    return FetchResult(
        requested_url=safe_url(url), final_url=safe_url(response.url),
        status_code=response.status_code, content_type=content_type,
        response_length=len(response.content), cookie_names=tuple(sorted(names)),
        html=response.text, redirected=bool(response.history), response_headers=headers,
    )


class PscubeClient:
    def __init__(
        self, *, timeout: float = 15.0, request_interval: float = 1.0,
        max_retries: int = 0, session: requests.Session | None = None,
        user_agent: str = "slot-data-collectors/0.1",
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        if not math.isfinite(request_interval) or request_interval < 0:
            raise ValueError("request_interval must be finite and nonnegative")
        if type(max_retries) is not int or not 0 <= max_retries <= 3:
            raise ValueError("max_retries must be between 0 and 3")
        self.timeout = timeout
        self.request_interval = request_interval
        self.max_retries = max_retries
        self.session = session if session is not None else requests.Session()
        self._owns_session = session is None
        self.user_agent = user_agent
        self._last_finished: float | None = None

    def fetch(self, url: str) -> str:
        return cast(str, self._request(url, inspect=False))

    def fetch_result(self, url: str) -> FetchResult:
        """Return diagnostics even for HTTP 4xx/5xx; transport failures still raise."""
        return cast(FetchResult, self._request(url, inspect=True))

    def fetch_json(self, url: str, *, params: dict[str, str | int]) -> JsonFetchResult:
        return cast(JsonFetchResult, self._request(url, inspect=False, params=params, json_result=True))

    def _request(self, url: str, *, inspect: bool,
                 params: dict[str, str | int] | None = None,
                 json_result: bool = False) -> str | FetchResult | JsonFetchResult:
        for attempt in range(self.max_retries + 1):
            if self._last_finished is not None:
                delay = self.request_interval - (time.monotonic() - self._last_finished)
                if delay > 0:
                    time.sleep(delay)
            try:
                with self.session.get(
                    url, timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                    allow_redirects=True,
                    params=params,
                ) as response:
                    if inspect:
                        return _inspection_result(url, response, self.session)
                    response.raise_for_status()
                    if json_result:
                        try:
                            data = response.json()
                        except ValueError:
                            raise JsonDecodeError("PScube response is not valid JSON") from None
                        if not isinstance(data, dict):
                            raise JsonDecodeError("PScube JSON must be an object")
                        media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                        return JsonFetchResult(
                            safe_url(url), safe_url(response.url), response.status_code,
                            "application/json" if media_type == "application/json" else "[other]",
                            len(response.content), data,
                        )
                    return response.text
            except (requests.Timeout, requests.ConnectionError):
                if attempt == self.max_retries:
                    raise FetchError("PScube connection failed") from None
            except requests.RequestException:
                # Do not retry HTTP errors, including 401, 403 and 429.
                # Request exceptions may embed credentials; never propagate their text.
                raise FetchError("PScube HTTP request failed") from None
            finally:
                self._last_finished = time.monotonic()
            time.sleep(2 ** attempt)
        raise FetchError("PScube request failed")

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> "PscubeClient":
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc_value: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        self.close()

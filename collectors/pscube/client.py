"""HTTP only. One sequential client owns one reusable session."""

import math
import time
from types import TracebackType
import requests
from common.exceptions import FetchError


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
        for attempt in range(self.max_retries + 1):
            if self._last_finished is not None:
                delay = self.request_interval - (time.monotonic() - self._last_finished)
                if delay > 0:
                    time.sleep(delay)
            try:
                with self.session.get(
                    url, timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                ) as response:
                    response.raise_for_status()
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

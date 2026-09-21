"""Structured collection events without response bodies or request credentials."""

import json
import logging
from urllib.parse import urlsplit


def safe_url(url: str) -> str:
    """Log only the origin: paths, query strings and userinfo can hold secrets."""
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return "[invalid-url]"
        return f"{parts.scheme}://{parts.hostname}/[redacted]"
    except ValueError:
        return "[invalid-url]"


class CollectionFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "level": record.levelname,
            "event": record.getMessage(),
            "source": getattr(record, "source", None),
            "url": getattr(record, "url", None),
            "status": getattr(record, "status", None),
            "count": getattr(record, "count", None),
        }, ensure_ascii=False)


def configure_logging() -> None:
    """Configure only this application's logger, leaving third-party logs alone."""
    logger = logging.getLogger("slot_collectors")
    handler = logging.StreamHandler()
    handler.setFormatter(CollectionFormatter())
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

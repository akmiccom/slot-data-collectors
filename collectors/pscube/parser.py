"""Pure HTML parsing interface; no network access."""

from common.exceptions import ParserNotImplementedError


class PscubeParser:
    def parse(self, html: str) -> list[dict[str, object]]:
        raise ParserNotImplementedError("PScube parser requires verified HTML fixtures")

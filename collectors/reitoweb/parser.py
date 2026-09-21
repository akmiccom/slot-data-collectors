"""REITO pure parser interface; no network access."""

from common.exceptions import ParserNotImplementedError


class ReitowebParser:
    def parse(self, html: str) -> list[dict[str, object]]:
        raise ParserNotImplementedError("REITO parser requires verified HTML fixtures")

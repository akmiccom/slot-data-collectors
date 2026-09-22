"""Exceptions exposed by collectors; messages must not contain credentials."""


class CollectorError(Exception):
    """Base error for acquisition, parsing and normalization."""


class FetchError(CollectorError):
    """HTTP acquisition failed."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class JsonDecodeError(FetchError):
    """Response was not a JSON object."""


class MachineParseError(CollectorError):
    """Machine response fields or pagination are invalid."""


class UnitParseError(CollectorError):
    """Unit detail has an unsupported or invalid structure."""


class UnitRequestUnsupported(CollectorError):
    """Normal page request parameters could not be identified."""


class ParserNotImplementedError(CollectorError, NotImplementedError):
    """Real source HTML is required before implementing the parser."""


class NormalizationError(CollectorError):
    """Source-to-standard mapping is unavailable or invalid."""

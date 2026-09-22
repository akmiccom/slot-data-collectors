"""Exceptions exposed by collectors; messages must not contain credentials."""


class CollectorError(Exception):
    """Base error for acquisition, parsing and normalization."""


class FetchError(CollectorError):
    """HTTP acquisition failed."""


class JsonDecodeError(FetchError):
    """Response was not a JSON object."""


class MachineParseError(CollectorError):
    """Machine response fields or pagination are invalid."""


class ParserNotImplementedError(CollectorError, NotImplementedError):
    """Real source HTML is required before implementing the parser."""


class NormalizationError(CollectorError):
    """Source-to-standard mapping is unavailable or invalid."""

"""Coordinate acquisition, parsing and normalization without persistence."""

import logging
from datetime import datetime, timezone
from collectors.pscube.client import PscubeClient
from collectors.pscube.parser import PscubeParser
from common.logging_config import safe_url
from common.models import SlotResult
from common.normalize import normalize_pscube

logger = logging.getLogger("slot_collectors.pscube")


class PscubeCollector:
    def __init__(self, client: PscubeClient, parser: PscubeParser | None = None) -> None:
        self.client = client
        self.parser = parser if parser is not None else PscubeParser()

    def collect(self, url: str) -> list[SlotResult]:
        context = {"source": "pscube", "url": safe_url(url)}
        try:
            html = self.client.fetch(url)
            collected_at = datetime.now(timezone.utc)
            rows = self.parser.parse(html)
            results = [normalize_pscube(
                row, source_url=url, collected_at=collected_at
            ) for row in rows]
        except Exception:
            logger.error("collection_failed", extra={**context, "status": "failure", "count": None})
            raise
        logger.info("collection_completed", extra={**context, "status": "success", "count": len(results)})
        return results

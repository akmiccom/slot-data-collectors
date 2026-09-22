"""Coordinate acquisition, parsing and normalization without persistence."""

import logging
from collections.abc import Iterator, Callable
from urllib.parse import urlsplit, urlunsplit, parse_qs
from datetime import datetime, timezone
from collectors.pscube.client import PscubeClient
from collectors.pscube.parser import PscubeParser
from collectors.pscube.parser import parse_machine_page
from collectors.pscube.models import PscubeMachine, PscubeMachinePage
from common.exceptions import MachineParseError
from common.logging_config import safe_url
from common.models import SlotResult
from common.normalize import normalize_pscube

logger = logging.getLogger("slot_collectors.pscube")


class PscubeCollector:
    def __init__(self, client: PscubeClient, parser: PscubeParser | None = None) -> None:
        self.client = client
        self.parser = parser if parser is not None else PscubeParser()

    def iter_machine_pages(self, url: str, *,
                           on_json: Callable[[int, dict[str, object]], None] | None = None
                           ) -> Iterator[PscubeMachinePage]:
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        if (parts.scheme not in ("http", "https") or not parts.hostname
                or parts.username or parts.password
                or not parts.path.endswith("/nc-v03-001.php")
                or query.get("cd_ps") != ["2"]):
            raise MachineParseError("Expected machine list page URL with cd_ps=2")
        endpoint = urlunsplit((parts.scheme, parts.netloc,
                               parts.path.rsplit("/", 1)[0] + "/nc-m03-001.php", "", ""))
        self.client.fetch(url)
        requested_page = 1
        first = None
        while True:
            result = self.client.fetch_json(endpoint, params={
                "cd_ps": 2, "bai": 0, "YMD_biz": "", "page": requested_page, "loaded": "",
            })
            parsed = parse_machine_page(result.data)
            if parsed.page != requested_page:
                raise MachineParseError("Response page differs from requested page")
            if first is None:
                first = parsed
            elif (parsed.page_max, parsed.count, parsed.business_date) != (first.page_max, first.count, first.business_date):
                raise MachineParseError("Page metadata changed during collection")
            if on_json is not None:
                on_json(requested_page, result.data)
            logger.info("machine_page_collected", extra={"source": "pscube", "url": safe_url(url),
                        "status": "success", "count": len(parsed.machines)})
            yield parsed
            if requested_page >= first.page_max:
                break
            requested_page += 1

    def collect_machines(self, url: str) -> list[PscubeMachine]:
        return [machine for page in self.iter_machine_pages(url) for machine in page.machines]

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

"""Sequential machine-list inspection; no browser cookies or bypasses."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit
import re
from uuid import uuid4
from dotenv import load_dotenv
from collectors.pscube.client import PscubeClient
from collectors.pscube.collector import PscubeCollector
from common.exceptions import CollectorError
from common.logging_config import configure_logging

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PScube機種一覧XHRを逐次取得")
    parser.add_argument("url", help="nc-v03-001.php?cd_ps=2 のページURL")
    parser.add_argument("--save-json", action="store_true", help="各ページのJSONをdebug/pscubeへ保存")
    args = parser.parse_args(argv)
    configure_logging()
    load_dotenv(ROOT / ".env")
    try:
        host = urlsplit(args.url).hostname or "unknown"
        safe_host = re.sub(r"[^a-zA-Z0-9_-]", "_", host)[:100]
        run = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:12]

        def save(page: int, data: dict[str, object]) -> None:
            directory = ROOT / "debug" / "pscube"
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / f"{run}_{safe_host}_page{page}.json").open("x", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)

        with PscubeClient(timeout=float(os.getenv("REQUEST_TIMEOUT") or "15"),
                          request_interval=float(os.getenv("REQUEST_INTERVAL") or "1")) as client:
            pages = list(PscubeCollector(client).iter_machine_pages(args.url, on_json=save if args.save_json else None))
        first = pages[0]
        machines = [machine for page in pages for machine in page.machines]
        report = {"host": host, "business_date": first.business_date.isoformat() if first.business_date else None,
                  "count": first.count, "pageMax": first.page_max, "collected_machine_count": len(machines),
                  "machines": [{"machine_name": m.machine_name, "unit_count": m.unit_count,
                                "unit_numbers_count": len(m.unit_numbers)} for m in machines]}
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0
    except (CollectorError, ValueError, OSError):
        logging.getLogger("slot_collectors.machines").error("machine_collection_failed",
            extra={"source": "pscube", "status": "failure"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

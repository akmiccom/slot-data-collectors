"""Inspect exactly one unit and four daily values; never fetch graph images."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from uuid import uuid4
from dotenv import load_dotenv
from collectors.pscube.client import PscubeClient
from collectors.pscube.collector import PscubeCollector
from collectors.pscube.unit_parser import parse_unit_detail
from common.exceptions import CollectorError
from common.logging_config import configure_logging

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PScube個別台1台のJSONと回転数推定を確認")
    parser.add_argument("url", nargs="?", help="nc-v06-001.php?cd_dai=0272 のURL")
    parser.add_argument("--save-json", action="store_true", help="解析前のJSONをdebug/pscubeへ保存")
    parser.add_argument("--from-json", type=Path, help="保存済みJSONを通信せず再解析")
    args = parser.parse_args(argv)
    if bool(args.url) == bool(args.from_json) or (args.from_json and args.save_json):
        parser.error("URLまたは--from-jsonのどちらか一方を指定（保存はURL指定時のみ）")
    configure_logging()
    load_dotenv(ROOT / ".env")
    stage = "configuration"
    logger = logging.getLogger("slot_collectors.unit")

    def set_stage(value: str) -> None:
        nonlocal stage
        stage = value

    def save(data: dict[str, object]) -> None:
        host = re.sub(r"[^a-zA-Z0-9_-]", "_", urlsplit(args.url).hostname or "unknown")[:100]
        directory = ROOT / "debug" / "pscube"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = directory / f"{stamp}_{uuid4().hex[:12]}_{host}_unit.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        logger.info("unit_json_saved", extra={"source": "pscube", "status": "success", "stage": "save_json"})

    try:
        if args.from_json:
            stage = "parse_json"
            detail = parse_unit_detail(json.loads(args.from_json.read_text(encoding="utf-8")))
        else:
            with PscubeClient(timeout=float(os.getenv("REQUEST_TIMEOUT") or "15"),
                              request_interval=float(os.getenv("REQUEST_INTERVAL") or "1")) as client:
                detail = PscubeCollector(client).collect_unit(args.url, on_json=save if args.save_json else None,
                                                            on_stage=set_stage)
        stage = "report"
        report = []
        for day in detail.days:
            row = asdict(day)
            row["business_date"] = day.business_date.isoformat()
            row["has_graph_src"] = bool(row.pop("graph_src"))
            report.append(row)
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0
    except (CollectorError, ValueError, OSError) as error:
        logger.error("unit_collection_failed", extra={"source": "pscube", "status": "failure", "stage": stage,
                     "error_type": type(error).__name__, "status_code": getattr(error, "status_code", None)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

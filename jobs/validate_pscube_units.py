"""Collect a selected machine's units sequentially for CSV accuracy validation."""

import argparse
from datetime import datetime
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from dotenv import load_dotenv
from collectors.pscube.client import PscubeClient
from collectors.pscube.collector import PscubeCollector
from collectors.pscube.validation import select_machine, select_units, validate_units
from common.exceptions import CollectorError
from common.logging_config import configure_logging

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PScube multi-unit validation CSV (sequential)")
    parser.add_argument("--hall-url", required=True)
    parser.add_argument("--machine-name", required=True, help="Exact m03 machine name")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--units", help="Comma-separated unit strings, preserving zeros")
    selection.add_argument("--limit", type=int)
    selection.add_argument("--all-units", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--annotate", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if args.units is not None and any(not u.isascii() or not u.isdigit() for u in args.units.split(",")):
        parser.error("--units must contain digit strings")
    configure_logging()
    load_dotenv(ROOT / ".env")
    stage = "configuration"
    try:
        day = datetime.strptime(args.date, "%Y%m%d").date()
        if day.strftime("%Y%m%d") != args.date:
            raise ValueError("Date must be YYYYMMDD")
        parts = urlsplit(args.hall_url)
        identity = sha256((str(parts.hostname) + parts.path + args.machine_name).encode()).hexdigest()[:12]
        directory = ROOT / "debug/pscube/validation" / identity
        output = args.output or directory / f"{day:%Y%m%d}_validation.csv"
        with PscubeClient(timeout=float(os.getenv("REQUEST_TIMEOUT") or "15"),
                          request_interval=float(os.getenv("REQUEST_INTERVAL") or "1")) as client:
            collector = PscubeCollector(client)
            stage = "machine_list"
            machine = select_machine(collector.collect_machines(args.hall_url), args.machine_name)
            units = select_units(machine, units=args.units, limit=args.limit, all_units=args.all_units)
            stage = "unit_validation"
            report = validate_units(collector, args.hall_url, machine, day, units, output, directory,
                                    force=args.force, annotate=args.annotate)
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 2 if report["stopped"] or report["failure"] else 0
    except (CollectorError, ValueError, OSError) as error:
        logging.getLogger("slot_collectors.validation").error("validation_failed", extra={
            "source": "pscube", "stage": stage, "error_type": type(error).__name__,
            "status_code": getattr(error, "status_code", None), "status": "failure"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

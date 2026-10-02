"""Recalculate manually supplied comparisons, preserving the validation CSV."""

import argparse
import json
import logging
from pathlib import Path
import sys

from collectors.pscube.validation import evaluate_rows, read_rows, write_rows
from common.logging_config import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate PScube CSV comparisons; rates are 0-100 percent")
    parser.add_argument("csv", type=Path)
    args = parser.parse_args(argv)
    configure_logging()
    try:
        if not args.csv.is_file():
            raise ValueError("CSV not found")
        rows = read_rows(args.csv)
        report = evaluate_rows(rows)
        write_rows(args.csv, rows)
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0
    except (ValueError, OSError) as error:
        logging.getLogger("slot_collectors.validation").error("evaluation_failed", extra={
            "source": "pscube", "stage": "evaluation", "error_type": type(error).__name__, "status": "failure"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

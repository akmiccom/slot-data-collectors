"""One graph image acquisition/analysis, or offline analysis of a local image."""

import argparse
from dataclasses import asdict
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sys
from dotenv import load_dotenv
from PIL import UnidentifiedImageError
from collectors.pscube.client import PscubeClient
from collectors.pscube.graph import GraphProfile, estimate_graph, fetch_graph, annotate_graph
from common.exceptions import CollectorError
from common.logging_config import configure_logging

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PScubeグラフ1枚の幾何解析（OCRなし・検証用）")
    parser.add_argument("--unit", required=True)
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--unit-url", help="対象台の通常ページURL。同じSessionでJSONと画像を取得")
    source.add_argument("--image", type=Path, help="ローカル画像を通信せず解析")
    parser.add_argument("--annotate", action="store_true")
    parser.add_argument("--top-medal", type=int)
    parser.add_argument("--bottom-medal", type=int)
    parser.add_argument("--step-medal", type=int)
    args = parser.parse_args(argv)
    configure_logging()
    load_dotenv(ROOT / ".env")
    stage = "configuration"
    try:
        day = datetime.strptime(args.date, "%Y%m%d").date()
        scale = (args.top_medal, args.bottom_medal, args.step_medal)
        if any(v is not None for v in scale) and any(v is None for v in scale):
            raise ValueError("Supply all three profile values")
        profile = GraphProfile(*scale) if all(v is not None for v in scale) else None
        directory = ROOT / "debug/pscube/graphs"
        path = args.image
        if args.unit_url:
            stage = "graph_fetch"
            with PscubeClient(timeout=float(os.getenv("REQUEST_TIMEOUT") or "15"),
                              request_interval=float(os.getenv("REQUEST_INTERVAL") or "1")) as client:
                path = fetch_graph(client, args.unit_url, day, args.unit, directory)
        stage = "graph_analysis"
        result = estimate_graph(path, day, args.unit, profile)
        report = asdict(result)
        report["business_date"] = day.isoformat()
        report["grid_line_count"] = len(result.horizontal_grid_y)
        if args.annotate:
            report["annotated_path"] = str(annotate_graph(result, directory / "annotated"))
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0 if result.estimated_medal is not None else 2
    except (CollectorError, ValueError, OSError, UnidentifiedImageError) as error:
        logging.getLogger("slot_collectors.graph").error("graph_inspection_failed", extra={
            "source":"pscube", "stage":stage, "error_type":type(error).__name__,
            "status_code":getattr(error,"status_code",None), "status":"failure"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

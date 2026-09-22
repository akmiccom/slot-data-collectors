"""Inspect one URL using ordinary requests redirects, with no page interaction."""

import argparse
from dataclasses import asdict
import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv
from collectors.pscube.client import PscubeClient
from collectors.pscube.inspect import diagnose_html, save_html
from common.exceptions import FetchError
from common.logging_config import configure_logging

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PScube取得検証（通常HTTPアクセスのみ）")
    parser.add_argument("url", help="取得するHTTP(S) URLを1つ指定")
    parser.add_argument("--save-html", action="store_true", help="HTMLをdebug/pscubeへUTF-8で保存")
    args = parser.parse_args(argv)
    configure_logging()
    logger = logging.getLogger("slot_collectors.inspect")
    load_dotenv(ROOT / ".env")
    try:
        parts = urlsplit(args.url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise ValueError("invalid URL")
        with PscubeClient(
            timeout=float(os.getenv("REQUEST_TIMEOUT") or "15"),
            request_interval=float(os.getenv("REQUEST_INTERVAL") or "1"),
        ) as client:
            result = client.fetch_result(args.url)
        logger.info("inspection_completed", extra={
            "source": "pscube", "requested_host": parts.hostname,
            "final_host": urlsplit(result.final_url).hostname,
            "status_code": result.status_code, "response_size": result.response_length,
        })
        diagnostics = diagnose_html(result.html)
        report = {
            "requested_url": result.requested_url, "final_url": result.final_url,
            "status_code": result.status_code, "content_type": result.content_type,
            "response_length": result.response_length, "redirected": result.redirected,
            "cookie_names": result.cookie_names, "response_headers": result.response_headers,
            "diagnostics": asdict(diagnostics),
            "possible_approval_page": diagnostics.possible_approval_page,
        }
        if args.save_html:
            report["saved_html"] = str(save_html(result.html, result.final_url, ROOT / "debug" / "pscube"))
        # The explicit diagnostic report goes to stdout; operational logs go to stderr.
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0 if result.status_code < 400 else 1
    except (FetchError, ValueError, OSError):
        logger.error("inspection_failed", extra={"source": "pscube", "status": "failure"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

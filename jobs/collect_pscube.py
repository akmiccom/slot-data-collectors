"""Offline readiness check until the PScube parser is implemented."""

import argparse
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from collectors.pscube.client import PscubeClient
from common.logging_config import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="PScube基盤の設定確認（通信は行いません）")
    parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    configure_logging()
    logger = logging.getLogger("slot_collectors.jobs")
    try:
        with PscubeClient(
            timeout=float(os.getenv("REQUEST_TIMEOUT") or "15"),
            request_interval=float(os.getenv("REQUEST_INTERVAL") or "1"),
        ):
            pass
    except ValueError:
        logger.error("invalid_request_settings", extra={"source": "pscube", "status": "failure"})
        return 2
    logger.error("parser_not_implemented", extra={"source": "pscube", "status": "failure", "count": 0})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

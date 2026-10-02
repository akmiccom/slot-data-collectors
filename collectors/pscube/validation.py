"""CSV contracts and sequential, inspection-only unit validation."""

import csv
from dataclasses import asdict
from datetime import date
import json
import logging
import os
from pathlib import Path
from statistics import mean, median
import tempfile
from urllib.parse import urlsplit, urlunsplit, urlencode

from collectors.pscube.collector import PscubeCollector
from collectors.pscube.graph import annotate_graph, estimate_graph, fetch_graph
from collectors.pscube.models import PscubeMachine
from common.exceptions import CollectorError, FetchError, UnitParseError, UnitRequestUnsupported

COMPARISON_FIELDS = ["minrepo_medal", "anaslo_medal", "error_vs_minrepo", "error_vs_anaslo",
                     "absolute_error_vs_minrepo", "absolute_error_vs_anaslo"]
FIELDS = ["hall_host", "hall_path", "business_date", "machine_name", "unit_no", "bb", "rb",
          "bb_probability", "rb_probability", "combined_probability", "estimated_game",
          "estimated_game_candidates", "game_estimation_spread", "max_payout", "estimated_medal",
          "graph_confidence", "graph_profile_top", "graph_profile_bottom", "graph_profile_step",
          "graph_warnings", "status", "error_type", *COMPARISON_FIELDS]
logger = logging.getLogger("slot_collectors.validation")


def select_machine(machines: list[PscubeMachine], name: str) -> PscubeMachine:
    matches = [m for m in machines if m.machine_name == name]
    if len(matches) != 1:
        raise ValueError("Machine name must match exactly one machine")
    return matches[0]


def select_units(machine: PscubeMachine, *, units: str | None = None,
                 limit: int | None = None, all_units: bool = False) -> list[str]:
    if sum((units is not None, limit is not None, all_units)) != 1:
        raise ValueError("Specify exactly one unit selection")
    available = list(dict.fromkeys(machine.unit_numbers))
    if units is not None:
        selected = units.split(",")
        if (not selected or any(not u.isascii() or not u.isdigit() for u in selected)
                or len(set(selected)) != len(selected) or not set(selected) <= set(available)):
            raise ValueError("Units must be unique digit strings belonging to the machine")
        return selected
    if limit is not None:
        if type(limit) is not int or limit <= 0:
            raise ValueError("Limit must be positive")
        return available[:limit]
    return available


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if (reader.fieldnames is None or len(reader.fieldnames) != len(FIELDS)
                or set(reader.fieldnames) != set(FIELDS)):
            raise ValueError("Unexpected validation CSV columns")
        rows = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError("Malformed validation CSV row")
    return rows


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    """Replace atomically so an interrupted write does not destroy comparison input."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="",
                                         dir=path.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def validate_units(collector: PscubeCollector, hall_url: str, machine: PscubeMachine,
                   day: date, units: list[str], output: Path, directory: Path, *,
                   force: bool = False, annotate: bool = False) -> dict[str, object]:
    parts = urlsplit(hall_url)
    context = {"hall_host": parts.hostname, "hall_path": parts.path.rsplit("/", 2)[0],
               "business_date": day.isoformat(), "machine_name": machine.machine_name}
    rows = read_rows(output)
    if any(any(row[k] != v for k, v in context.items()) for row in rows):
        raise ValueError("Existing CSV belongs to a different hall, date or machine")
    if len({r["unit_no"] for r in rows}) != len(rows):
        raise ValueError("Duplicate units in existing CSV")
    by_unit = {r["unit_no"]: r for r in rows}
    skipped, processed, stopped = 0, 0, False
    for unit in units:
        old = by_unit.get(unit)
        if old and old["status"] == "success" and not force:
            skipped += 1
            continue
        row: dict[str, object] = {key: "" for key in FIELDS}
        row.update(context, unit_no=unit)
        if old:
            # Derived errors become stale after a re-estimate; preserve only manual input.
            row.update({key: old[key] for key in ("minrepo_medal", "anaslo_medal")})
        url = urlunsplit((parts.scheme, parts.netloc,
                         parts.path.rsplit("/", 1)[0] + "/nc-v06-001.php",
                         urlencode({"cd_dai": unit}), ""))
        stage = "unit_fetch"
        try:
            detail = collector.collect_unit(url)
            daily = next((d for d in detail.days if d.business_date == day), None)
            if daily is None:
                row["status"] = "no_daily_data"
            else:
                values = asdict(daily)
                for key in ("bb", "rb", "bb_probability", "rb_probability", "combined_probability",
                            "estimated_game", "game_estimation_spread", "max_payout"):
                    row[key] = values[key]
                row["estimated_game_candidates"] = json.dumps(daily.estimated_game_candidates)
                if not daily.graph_src:
                    row["status"] = "no_graph"
                else:
                    stage = "graph_fetch"
                    path = fetch_graph(collector.client, url, day, unit, directory / "images", detail=detail)
                    stage = "graph_analysis"
                    estimate = estimate_graph(path, day, unit)
                    row.update(estimated_medal=estimate.estimated_medal, graph_confidence=estimate.confidence,
                               graph_warnings=json.dumps(estimate.warnings, ensure_ascii=False),
                               status="success" if estimate.estimated_medal is not None else "graph_low_confidence")
                    if estimate.selected_profile:
                        row.update(graph_profile_top=estimate.selected_profile.top_medal,
                                   graph_profile_bottom=estimate.selected_profile.bottom_medal,
                                   graph_profile_step=estimate.selected_profile.step_medal)
                    if annotate:
                        stage = "graph_annotate"
                        annotate_graph(estimate, directory / "annotated")
        except (CollectorError, ValueError, OSError) as error:
            row["error_type"] = type(error).__name__
            row["status"] = ("parse_failed" if isinstance(error, (UnitParseError, UnitRequestUnsupported))
                             else "unit_fetch_failed" if stage == "unit_fetch"
                             else "graph_fetch_failed" if stage == "graph_fetch" else "graph_processing_failed")
            status_code = getattr(error, "status_code", None)
            logger.error("unit_validation_failed", extra={"source": "pscube", "stage": stage,
                         "error_type": type(error).__name__, "status_code": status_code, "status": "failure"})
            stopped = isinstance(error, FetchError) and status_code in (403, 429)
        by_unit[unit] = row
        write_rows(output, list(by_unit.values()))
        processed += 1
        if stopped:
            break
    selected = [by_unit[u] for u in units if u in by_unit]
    success = sum(r["status"] == "success" for r in selected)
    return {"processed": processed, "skipped": skipped, "success": success,
            "failure": len(selected) - success, "not_processed": len(units) - len(selected),
            "stopped": stopped, "output": str(output)}


def evaluate_rows(rows: list[dict[str, str]]) -> dict[str, object]:
    report = {}
    for source in ("minrepo", "anaslo"):
        errors = []
        for row in rows:
            row[f"error_vs_{source}"] = ""
            row[f"absolute_error_vs_{source}"] = ""
            # Validate supplied numbers even if the estimate is missing.
            estimate = int(row["estimated_medal"]) if row["estimated_medal"].strip() else None
            reference = int(row[f"{source}_medal"]) if row[f"{source}_medal"].strip() else None
            if estimate is None or reference is None:
                continue
            error = estimate - reference
            row[f"error_vs_{source}"] = str(error)
            row[f"absolute_error_vs_{source}"] = str(abs(error))
            errors.append(error)
        absolute = [abs(e) for e in errors]
        metrics = {"sample_count": len(errors), "mean_error": mean(errors) if errors else None,
                   "MAE": mean(absolute) if errors else None,
                   "median_absolute_error": median(absolute) if errors else None,
                   "max_absolute_error": max(absolute) if errors else None}
        for threshold in (10, 25, 50, 100, 200):
            count = sum(e <= threshold for e in absolute)
            metrics[f"within_{threshold}_count"] = count
            metrics[f"within_{threshold}_rate"] = count / len(errors) * 100 if errors else None
        report[source] = metrics
    return report

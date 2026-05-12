"""Write each search run to results/jobs_YYYYMMDD_HHMMSS.csv."""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Iterable, Mapping

from .config import RESULTS_DIR

CSV_FIELDS: list[str] = [
    "title",
    "company",
    "type",
    "location",
    "salary",
    "posting_date",
    "link",
    "source",
    "is_nonprofit_or_h1b_cap_exempt",
    "why_match",
]


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def _row_from_job(job: Mapping[str, object]) -> dict[str, str]:
    nonprofit = job.get("is_nonprofit_or_h1b_cap_exempt")
    return {
        "title": _cell(job.get("title")),
        "company": _cell(job.get("company")),
        "type": _cell(job.get("work_mode")),
        "location": _cell(job.get("location")),
        "salary": _cell(job.get("salary")),
        "posting_date": _cell(job.get("posted")),
        "link": _cell(job.get("url")),
        "source": _cell(job.get("source")),
        "is_nonprofit_or_h1b_cap_exempt": "" if nonprofit is None else _cell(nonprofit),
        "why_match": _cell(job.get("why_match")),
    }


def write_csv(jobs: Iterable[Mapping[str, object]], results_dir: Path = RESULTS_DIR) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"jobs_{ts}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for job in jobs:
            writer.writerow(_row_from_job(job))
    return out_path


def list_results(results_dir: Path = RESULTS_DIR) -> list[dict[str, object]]:
    if not results_dir.exists():
        return []
    items: list[dict[str, object]] = []
    for path in results_dir.glob("jobs_*.csv"):
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = max(sum(1 for _ in handle) - 1, 0)
            stat = path.stat()
            items.append(
                {
                    "filename": path.name,
                    "created_at": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "rows": rows,
                    "size_bytes": stat.st_size,
                }
            )
        except OSError:
            continue
    items.sort(key=lambda x: x["filename"], reverse=True)
    return items

"""Entry point:
    python -m backtest.run --area th-chonburi-coast --end 2026-11-25 --count 52 --cache-dir <folder outside the repo> --out report.md
    add --offline to use the cache only (no network).

Reads NOAA ERDDAP through the ingest fetchers (see backtest/inputs.py for the request limits). Never writes to a database.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from fsi.config import FsiParams
from fsi.model import score_area
from ingest.config import ConfigError, load_area

from . import checks, inputs, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="backtest.run")
    ap.add_argument("--area", required=True)
    ap.add_argument("--end", required=True, help="last area-local date, YYYY-MM-DD")
    ap.add_argument("--count", type=int, default=52)
    ap.add_argument("--step-days", type=int, default=7)
    ap.add_argument("--extra-dates", default="", help="comma separated YYYY-MM-DD dates added to the sample (for day-to-day pairs)")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--max-requests", type=int, default=250)
    ap.add_argument("--pause-s", type=float, default=2.0)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        area = load_area(a.area)
        p = FsiParams.from_area(area)
        cache = inputs.check_cache_dir(Path(a.cache_dir))
        end = date.fromisoformat(a.end)
        if not 1 <= a.count <= 120 or not 1 <= a.step_days <= 31:
            raise ValueError("--count must be 1..120 and --step-days 1..31")
        extra = [date.fromisoformat(x) for x in a.extra_dates.split(",") if x.strip()]
    except (ConfigError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    dates = inputs.weekly_dates(end, a.count, a.step_days) + [d for d in extra if d not in set(inputs.weekly_dates(end, a.count, a.step_days))]
    http = None if a.offline else inputs.PoliteHttp(max_requests=a.max_requests, pause_s=a.pause_s)
    history, stats = inputs.load_history(area, dates, cache, http)
    if not history:
        print("no dates available", file=sys.stderr)
        return 1
    scored = {d: score_area(c, d, p, "trial") for d, c in history.items()}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parent).stdout.strip() or "unknown"
    text = report.render(
        area.area_id, p.model_version, p.config_sha256, sorted(history), stats, checks.coverage(history, scored),
        checks.monotonic_sweeps(p), checks.distribution(scored), checks.ranking_drivers(history, scored, p),
        checks.weight_sensitivity(history, p), checks.chlorophyll_dependence(history, p), checks.stability(scored),
        datetime.now(timezone.utc).strftime("%Y-%m-%d"), commit)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"report written: {a.out} ({len(history)} dates, requests {stats['requests']})")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

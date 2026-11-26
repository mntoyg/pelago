"""Entry point:  python -m ingest.run --area th-chonburi-coast --date today|YYYY-MM-DD

The database URL comes from the environment variable DATABASE_URL_INGEST (write role). It is never printed, logged or
written to a file. Output lines carry only variable, status, source id and counts.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date

from .config import ConfigError, load_area
from .timeutil import local_today


def parse_date(text: str, tz: str) -> date:
    if text == "today":
        return local_today(tz)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit("--date must be 'today' or YYYY-MM-DD") from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ingest.run")
    ap.add_argument("--area", required=True)
    ap.add_argument("--date", default="today", help="area-local calendar date, or 'today'")
    args = ap.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(name)s: %(message)s")
    try:
        area = load_area(args.area)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    run_date = parse_date(args.date, area.timezone)
    dsn = os.environ.get("DATABASE_URL_INGEST")
    if not dsn:
        print("DATABASE_URL_INGEST is not set", file=sys.stderr)
        return 2
    import psycopg
    from .db import Writer
    from .pipeline import run_ingest
    with psycopg.connect(dsn, autocommit=True) as conn:
        results = run_ingest(area, run_date, Writer(conn))
    print(f"area={area.area_id} run_date={run_date} config_sha256={area.sha256[:12]}")
    for r in results:
        print(f"  {r.variable:<9} {r.status:<8} source={r.source_id} role={r.role} cells_with_value={r.cells_with_value}"
              f" error={r.error_code}")
    return 0 if all(r.status != "failed" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

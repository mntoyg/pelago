"""Entry point:  python -m fsi.run --area th-chonburi-coast --date today|YYYY-MM-DD

Reads grid_daily and writes fsi_daily with the write role from DATABASE_URL_INGEST (shared with the ingest for now). The URL
is never printed or logged. Output carries counts only.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from ingest.config import ConfigError, load_area
from ingest.run import parse_date


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fsi.run")
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
    from .db import FsiStore
    from .pipeline import run_fsi
    with psycopg.connect(dsn, autocommit=True) as conn:
        r = run_fsi(area, run_date, FsiStore(conn))
    print(f"area={area.area_id} run_date={run_date} config_sha256={area.sha256[:12]} status={r.status} error={r.error_code}")
    print(f"  cells={r.cells_total} scored={r.scored} confidence={r.by_confidence}")
    return 0 if r.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

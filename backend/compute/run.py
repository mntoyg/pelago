"""Entry point:  python -m compute.run --area th-chonburi-coast --date today|YYYY-MM-DD [--boat-class small]

Runs mask -> fsi -> pick with the write role from DATABASE_URL_INGEST. The URL is never printed or logged; output carries counts only.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from ingest.config import ConfigError, load_area
from ingest.run import parse_date


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="compute.run")
    ap.add_argument("--area", required=True)
    ap.add_argument("--date", default="today", help="area-local calendar date, or 'today'")
    ap.add_argument("--boat-class", action="append", dest="boat_classes", help="repeatable; default: small")
    args = ap.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(name)s: %(message)s")
    try:
        area = load_area(args.area)
        classes = args.boat_classes or ["small"]
        unknown = [c for c in classes if c not in area.raw["boat_classes"]]
        if unknown:
            raise ConfigError("unknown boat class")
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    run_date = parse_date(args.date, area.timezone)
    dsn = os.environ.get("DATABASE_URL_INGEST")
    if not dsn:
        print("DATABASE_URL_INGEST is not set", file=sys.stderr)
        return 2
    import psycopg
    from .pipeline import run_compute
    with psycopg.connect(dsn, autocommit=True) as conn:
        try:
            r = run_compute(area, run_date, conn, classes)
        except ConfigError as exc:
            print(f"config error: {exc}", file=sys.stderr)
            return 2
    print(f"area={area.area_id} run_date={run_date} config_sha256={area.sha256[:12]} status={r.status}")
    print(f"  mask: {r.mask.status} {r.mask.error_code} eligible={r.mask.eligible} layers_missing={r.mask.layers_missing}")
    if r.fsi:
        print(f"  fsi:  {r.fsi.status} {r.fsi.error_code} scored={r.fsi.scored}")
    if r.pick:
        print(f"  pick: {r.pick.status} {r.pick.error_code} picks={r.pick.picks}")
    return 0 if r.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

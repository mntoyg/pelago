"""Shared ERDDAP griddap helpers (NOAA CoastWatch). URLs are built here from code constants only, never from config
or upstream text; nothing in this module puts a URL into an error."""
from __future__ import annotations

import csv
import io
import math
from datetime import date, datetime, timedelta
from urllib.parse import quote

from ..timeutil import UTC, local_date_of, local_day_end_utc, parse_utc
from .base import FetchError, HttpGet

BASE = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/"
DATASET_BASES = {
    "noaacwNPPVIIRSchlaDaily": "https://coastwatch.noaa.gov/erddap/griddap/",
    "noaacwN20VIIRSchlaDaily": "https://coastwatch.noaa.gov/erddap/griddap/",
}


def iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def url(dataset: str, variables_and_constraints: str) -> str:
    """dataset.csv?<query>; brackets are percent-encoded, parentheses and colons stay as ERDDAP expects."""
    return f"{DATASET_BASES.get(dataset, BASE)}{dataset}.csv?" + quote(variables_and_constraints, safe="()-:.,")


def parse_csv(body: bytes, required: tuple[str, ...]) -> list[dict[str, str]]:
    """ERDDAP CSV: header row, units row, data rows. Fails with bad_shape if a required column is absent."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FetchError("bad_shape") from exc
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2 or not set(required) <= set(rows[0]):
        raise FetchError("bad_shape")
    head = rows[0]
    out = []
    for r in rows[2:]:
        if len(r) != len(head):
            raise FetchError("bad_shape")      # truncated or malformed line: do not guess
        out.append(dict(zip(head, r)))
    return out


def num(text: str) -> float | None:
    """'NaN' / '' / non-finite -> None. A non-number is a shape error, not a missing value."""
    t = text.strip()
    if t == "" or t.lower() in ("nan", "null"):
        return None
    try:
        v = float(t)
    except ValueError as exc:
        raise FetchError("bad_value") from exc
    return v if math.isfinite(v) else None


def pick_times(http: HttpGet, dataset: str, run_date: date, tz: str, lookback_days: int, timeout: float,
               n_last: int = 40) -> list[datetime]:
    """Axis times (UTC, ascending) that are not after the end of the local run_date and not older than lookback_days.

    Reads the newest `n_last` axis values first; if the run date is older than that window, asks for the date range.
    """
    cutoff = local_day_end_utc(run_date, tz)                    # exclusive
    oldest_local = run_date - timedelta(days=lookback_days)

    def ok(t: datetime) -> bool:
        return t < cutoff and local_date_of(t, tz) >= oldest_local

    body = http(url(dataset, f"time[last-{n_last - 1}:1:last]"), timeout)
    times = [parse_utc(r["time"]) for r in parse_csv(body, ("time",))]
    if times and min(times) >= cutoff:       # the run date lies before the newest-N window: ask by value
        lo = local_day_end_utc(oldest_local - timedelta(days=1), tz)
        try:
            body = http(url(dataset, f"time[({iso_z(lo)}):1:({iso_z(cutoff - timedelta(seconds=1))})]"), timeout)
        except FetchError as exc:
            if exc.code in ("http_404", "http_400"):
                return []
            raise
        times = [parse_utc(r["time"]) for r in parse_csv(body, ("time",))]
    return sorted(t for t in times if ok(t))

"""Local-date and UTC handling. IANA zones only (zoneinfo); a fixed offset is never added by hand (risk R7)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


def parse_utc(text: str) -> datetime:
    """'2026-11-24T09:00:00Z' or '2026-11-25T21:00' (naive = UTC) -> aware UTC datetime."""
    s = text.strip()
    if s.endswith("Z"):
        s = s[:-1]
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        return dt.astimezone(UTC)
    return dt.replace(tzinfo=UTC)


def local_today(tz_name: str, now_utc: datetime | None = None) -> date:
    now = now_utc or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    return now.astimezone(ZoneInfo(tz_name)).date()


def local_day_end_utc(run_date: date, tz_name: str) -> datetime:
    """First instant AFTER the local calendar day run_date, in UTC (exclusive upper bound)."""
    return datetime.combine(run_date + timedelta(days=1), time(0, 0), tzinfo=ZoneInfo(tz_name)).astimezone(UTC)


def local_date_of(ts_utc: datetime, tz_name: str) -> date:
    return ts_utc.astimezone(ZoneInfo(tz_name)).date()


def sea_window_utc(run_date: date, tz_name: str, start_hhmm: str, end_hhmm: str) -> tuple[datetime, datetime]:
    """The sea window of the area's local date as an inclusive [start, end] pair of UTC instants."""
    z = ZoneInfo(tz_name)
    h0, m0 = (int(x) for x in start_hhmm.split(":"))
    h1, m1 = (int(x) for x in end_hhmm.split(":"))
    a = datetime.combine(run_date, time(h0, m0), tzinfo=z).astimezone(UTC)
    b = datetime.combine(run_date, time(h1, m1), tzinfo=z).astimezone(UTC)
    if not a < b:
        raise ValueError("sea window must end after it starts")
    return a, b

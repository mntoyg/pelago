"""Moon phase from the date: the same maths as moonPhase() in src/services/marine-data.js (so the server and the
browser agree), evaluated at one fixed instant per local date so that a re-run gives the same number."""
from __future__ import annotations

import math
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

SYNODIC = 29.530588853
MOON_LOCAL_TIME = time(9, 0)    # the middle of the default 04:00-14:00 sea window


def moon_phase(at_utc: datetime) -> dict[str, float]:
    """{'phase': 0..1 through the cycle, 'age_days', 'illumination': 0..1}."""
    if at_utc.tzinfo is None:
        raise ValueError("moon_phase needs an aware datetime")
    k = (at_utc.timestamp() * 1000 / 864e5 - 10962.76) / SYNODIC
    ph = ((k % 1) + 1) % 1
    return {"phase": ph, "age_days": ph * SYNODIC, "illumination": (1 - math.cos(2 * math.pi * ph)) / 2}


def moon_for_local_date(run_date: date, tz_name: str) -> dict[str, float]:
    return moon_phase(datetime.combine(run_date, MOON_LOCAL_TIME, tzinfo=ZoneInfo(tz_name)).astimezone(timezone.utc))

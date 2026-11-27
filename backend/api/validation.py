"""Strict query and path validation shared by the `/v1` handlers."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


AREA_ID = re.compile(r"^[a-z]{2}(-[a-z0-9]+)+$")
BOAT_CLASS = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_ALLOWED_SPOTS_QUERY = {"date", "boat_class", "limit"}


class ValidationProblem(ValueError):
    def __init__(self, code: str, param: str, message: str):
        super().__init__(message)
        self.code = code
        self.param = param
        self.message = message


def validate_area_id(value: str) -> str:
    if not isinstance(value, str) or len(value) > 40 or not AREA_ID.fullmatch(value):
        raise ValidationProblem("invalid_format", "area_id", "area_id has an invalid format")
    return value


def validate_spots_query(
    pairs: list[tuple[str, str]],
    timezone_name: str,
    *,
    today: date | None = None,
    boat_classes: tuple[str, ...] = ("small", "medium"),
) -> dict[str, object]:
    if len(pairs) > 8:
        raise ValidationProblem("invalid_format", "query", "too many query parameters")

    values: dict[str, str] = {}
    for key, value in pairs:
        if key not in _ALLOWED_SPOTS_QUERY:
            raise ValidationProblem("unknown_parameter", key[:32], "unknown query parameter")
        if key in values:
            raise ValidationProblem("invalid_format", key, "query parameter must appear once")
        if len(key) > 32 or len(value) > 64:
            raise ValidationProblem("invalid_format", key[:32], "query parameter is too long")
        values[key] = value

    local_today = today or datetime.now(ZoneInfo(timezone_name)).date()
    raw_date = values.get("date")
    if raw_date is None:
        run_date = local_today
    else:
        try:
            if len(raw_date) != 10 or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw_date):
                raise ValueError
            run_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValidationProblem("date_out_of_range", "date", "date must be a real YYYY-MM-DD calendar date") from exc
        if run_date > local_today or run_date < local_today - timedelta(days=60):
            raise ValidationProblem("date_out_of_range", "date", "date is outside the available range")

    boat_class = values.get("boat_class", boat_classes[0] if boat_classes else "")
    if not BOAT_CLASS.fullmatch(boat_class):
        raise ValidationProblem("invalid_format", "boat_class", "boat_class has an invalid format")
    if boat_class not in boat_classes:
        raise ValidationProblem("unsupported_boat_class", "boat_class", "boat_class is not supported for this area")

    raw_limit = values.get("limit", "5")
    if not re.fullmatch(r"[0-9]{1,2}", raw_limit):
        raise ValidationProblem("invalid_format", "limit", "limit must be an integer")
    limit = int(raw_limit)
    if not 1 <= limit <= 5:
        raise ValidationProblem("limit_out_of_range", "limit", "limit must be between 1 and 5")

    return {"date": run_date, "boat_class": boat_class, "limit": limit}

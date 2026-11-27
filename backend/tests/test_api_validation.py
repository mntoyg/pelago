from datetime import date

import pytest

from api.validation import ValidationProblem, validate_area_id, validate_spots_query


def test_area_id_accepts_only_contract_slugs():
    assert validate_area_id("th-chonburi-coast") == "th-chonburi-coast"
    for candidate in ("../secret", "TH-chonburi", "th-", "th-café", "th-海", "a" * 41, ""):
        with pytest.raises(ValidationProblem) as exc:
            validate_area_id(candidate)
        assert exc.value.code == "invalid_format"


def test_spots_query_rejects_invalid_dates_and_future_dates():
    with pytest.raises(ValidationProblem) as exc:
        validate_spots_query([("date", "2026-02-30")], "Asia/Bangkok", today=date(2026, 11, 27))
    assert exc.value.code == "date_out_of_range"

    with pytest.raises(ValidationProblem) as exc:
        validate_spots_query([("date", "2026-11-28")], "Asia/Bangkok", today=date(2026, 11, 27))
    assert exc.value.code == "date_out_of_range"


@pytest.mark.parametrize("query, expected", [
    ([("limit", "0")], "limit_out_of_range"),
    ([("limit", "6")], "limit_out_of_range"),
    ([("boat_class", "unknown")], "unsupported_boat_class"),
    ([("typo", "small")], "unknown_parameter"),
    ([
        ("date", "2026-11-27"),
        ("date", "2026-11-26"),
    ], "invalid_format"),
    ([ ("boat_class", "x" * 65) ], "invalid_format"),
])
def test_spots_query_rejects_hostile_or_ambiguous_values(query, expected):
    with pytest.raises(ValidationProblem) as exc:
        validate_spots_query(query, "Asia/Bangkok", today=date(2026, 11, 27))
    assert exc.value.code == expected


def test_spots_query_defaults_to_local_today_and_small_boat():
    result = validate_spots_query([], "Asia/Bangkok", today=date(2026, 11, 27))
    assert result == {"date": date(2026, 11, 27), "boat_class": "small", "limit": 5}

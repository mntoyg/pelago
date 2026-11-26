"""UTC versus area-local date (risk R7): a 03:00 local run is 20:00 UTC of the PREVIOUS day."""
from datetime import date, datetime, timezone

import pytest

from ingest.timeutil import UTC, local_date_of, local_day_end_utc, local_today, parse_utc, sea_window_utc


def test_local_today_differs_from_the_utc_date_after_17h_utc():
    now = datetime(2026, 11, 25, 20, 0, tzinfo=UTC)               # 03:00 on 26 Nov in Bangkok
    assert now.date() == date(2026, 11, 25)
    assert local_today("Asia/Bangkok", now) == date(2026, 11, 26)


def test_local_today_rejects_a_naive_datetime():
    with pytest.raises(ValueError):
        local_today("Asia/Bangkok", datetime(2026, 11, 25, 20, 0))


def test_observation_date_is_taken_in_local_time():
    assert local_date_of(parse_utc("2026-11-24T09:00:00Z"), "Asia/Bangkok") == date(2026, 11, 24)
    assert local_date_of(parse_utc("2026-11-24T18:30:00Z"), "Asia/Bangkok") == date(2026, 11, 25)   # 01:30 local next day


def test_day_end_is_exclusive_and_in_utc():
    assert local_day_end_utc(date(2026, 11, 26), "Asia/Bangkok") == datetime(2026, 11, 26, 17, 0, tzinfo=UTC)


def test_sea_window_for_bangkok():
    a, b = sea_window_utc(date(2026, 11, 26), "Asia/Bangkok", "04:00", "14:00")
    assert (a, b) == (datetime(2026, 11, 25, 21, 0, tzinfo=UTC), datetime(2026, 11, 26, 7, 0, tzinfo=UTC))


def test_sea_window_uses_the_zone_database_not_a_fixed_offset():
    summer = sea_window_utc(date(2026, 7, 1), "Europe/London", "04:00", "14:00")
    winter = sea_window_utc(date(2026, 1, 15), "Europe/London", "04:00", "14:00")
    assert summer[0] == datetime(2026, 7, 1, 3, 0, tzinfo=UTC)     # BST = UTC+1
    assert winter[0] == datetime(2026, 1, 15, 4, 0, tzinfo=UTC)    # GMT = UTC+0


def test_reversed_window_is_rejected():
    with pytest.raises(ValueError):
        sea_window_utc(date(2026, 11, 26), "Asia/Bangkok", "14:00", "04:00")


def test_parse_utc_variants():
    assert parse_utc("2026-11-25T21:00") == datetime(2026, 11, 25, 21, 0, tzinfo=UTC)
    assert parse_utc("2026-11-24T09:00:00Z") == datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
    assert parse_utc("2026-11-24T16:00:00+07:00") == datetime(2026, 11, 24, 9, 0, tzinfo=UTC)

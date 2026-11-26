"""Retry, fallback, carry-forward and what job_runs may hold, with fake sources (no network, no database)."""
import json
import math
from datetime import date, datetime, timedelta, timezone

import pytest

from ingest import pipeline
from ingest.fetchers.base import FetchError, Row
from tests.helpers import FakeWriter, ok_rows

UTC = timezone.utc
RUN = date(2026, 11, 26)


class FakeSource:
    def __init__(self, source_id, script):
        self.source_id, self.script, self.calls = source_id, list(script), 0

    def fetch(self, area, run_date):
        self.calls += 1
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(step, Exception):
            raise step
        return step(area) if callable(step) else step


def factory_for(sources):
    def f(source_id, area, **kw):
        s = sources[source_id]
        if isinstance(s, Exception):
            raise s
        return s
    return f


def run_var(area, variable, sources, writer=None, sleeps=None):
    w = writer or FakeWriter()
    res = pipeline.ingest_variable(area, RUN, variable, w, factory_for(sources),
                                   sleep=(sleeps.append if sleeps is not None else (lambda s: None)))
    return res, w


def test_primary_is_retried_three_times_then_the_fallback_is_used(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    primary = FakeSource("erddap_viirs_chl", [FetchError("timeout")])
    fallback = FakeSource("erddap_viirs_n20_chl", [ok_rows(area, "chl", 0.4, source="erddap_viirs_n20_chl")])
    sleeps = []
    res, w = run_var(area, "chl", {"erddap_viirs_chl": primary, "erddap_viirs_n20_chl": fallback}, sleeps=sleeps)
    assert primary.calls == 3 and fallback.calls == 1                      # S p.5: retry 3 times, then fall back
    assert [(r["source_id"], r["attempt"], r["status"], r["error_code"]) for r in w.runs] == [
        ("erddap_viirs_chl", 1, "failed", "timeout"), ("erddap_viirs_chl", 2, "failed", "timeout"),
        ("erddap_viirs_chl", 3, "failed", "timeout"), ("erddap_viirs_n20_chl", 1, "success", None)]
    assert w.runs[-1]["role"] == "fallback" and res.status == "success" and res.source_id == "erddap_viirs_n20_chl"
    assert len(sleeps) == 2                                                  # back-off between attempts, not after the last
    assert len(w.written["chl"]) == 4


def test_a_permanent_error_is_not_retried(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    primary = FakeSource("erddap_viirs_chl", [FetchError("no_recent_data")])
    fallback = FakeSource("erddap_viirs_n20_chl", [ok_rows(area, "chl")])
    run_var(area, "chl", {"erddap_viirs_chl": primary, "erddap_viirs_n20_chl": fallback})
    assert primary.calls == 1 and fallback.calls == 1


def test_a_transient_error_that_clears_succeeds_on_the_primary(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    primary = FakeSource("erddap_mur_sst", [FetchError("http_503"), ok_rows(area, "sst", 29.0, source="erddap_mur_sst")])
    res, w = run_var(area, "sst", {"erddap_mur_sst": primary})
    assert res.status == "success" and [r["attempt"] for r in w.runs] == [1, 2] and w.runs[0]["error_code"] == "http_503"


def test_all_sources_fail_and_earlier_data_is_kept_with_its_own_age(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    old_t = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)
    earlier = {"sst": [Row(c, 29.5, old_t, "erddap_mur_sst", None, {"grad_c_per_km": 0.05}) for c in area.cell_ids()[:3]]}
    res, w = run_var(area, "sst", {"erddap_mur_sst": FakeSource("erddap_mur_sst", [FetchError("timeout")])}, FakeWriter(earlier))
    assert res.status == "partial" and res.error_code == "timeout" and res.cells_with_value == 3
    kept = {r.cell_id: r for r in w.written["sst"]}
    assert all(kept[c].observed_at == old_t for c in area.cell_ids()[:3])    # the old observation time is NOT refreshed
    assert kept[area.cell_ids()[3]].value is None                             # a cell that never had data stays None
    last = w.runs[-1]
    assert last["status"] == "partial" and last["role"] == "fallback" and last["detail"]["carried_forward"] is True
    assert last["data_date"] == date(2026, 11, 22)


def test_carried_data_older_than_the_maximum_age_is_dropped(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    expired = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)                        # sst max age is 5 days
    earlier = {"sst": [Row(c, 29.5, expired, "erddap_mur_sst") for c in area.cell_ids()]}
    res, w = run_var(area, "sst", {"erddap_mur_sst": FakeSource("erddap_mur_sst", [FetchError("timeout")])}, FakeWriter(earlier))
    assert res.status == "failed" and "sst" not in w.written


def test_nothing_earlier_means_failed_not_invented(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    res, w = run_var(area, "chl", {"erddap_viirs_chl": FakeSource("a", [FetchError("timeout")]),
                                   "erddap_viirs_n20_chl": FakeSource("b", [FetchError("http_500")])})
    assert res.status == "failed" and res.error_code == "http_500" and w.written == {}


def test_wave_wind_is_never_carried_forward(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    t = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)
    earlier = {"wave_wind": [Row(c, 0.5, t, "open_meteo_marine", None, {"wind_kmh": 10.0}) for c in area.cell_ids()]}
    res, w = run_var(area, "wave_wind", {"open_meteo_marine": FakeSource("open_meteo_marine", [FetchError("timeout")])},
                     FakeWriter(earlier))
    assert res.status == "failed" and "wave_wind" not in w.written


def test_licence_route_b_does_not_call_open_meteo_and_does_not_substitute(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3], mutate=lambda raw: raw.update(licence_route="B"))
    from ingest.fetchers import registry
    w = FakeWriter()
    res = pipeline.ingest_variable(area, RUN, "wave_wind", w, registry.build, sleep=lambda s: None)
    assert res.status == "failed" and res.error_code == "route_not_allowed"
    assert [(r["source_id"], r["error_code"]) for r in w.runs] == [("open_meteo_marine", "route_not_allowed")]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), 41.0, -3.0])
def test_out_of_range_or_non_finite_values_never_reach_the_writer(make_area, bad):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    rows = ok_rows(area, "sst", 29.0)
    rows[1] = Row(rows[1].cell_id, bad, rows[1].observed_at, "s")
    res, w = run_var(area, "sst", {"erddap_mur_sst": FakeSource("erddap_mur_sst", [rows])})
    assert "sst" not in w.written and w.runs[0]["error_code"] == "bad_value"


def test_duplicate_missing_or_foreign_cells_and_naive_times_are_rejected(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    good = ok_rows(area, "sst", 29.0)
    for rows in (good[:3], good + good[:1], [Row(1, 29.0, good[0].observed_at, "s")] + good[1:],
                 [Row(good[0].cell_id, 29.0, datetime(2026, 11, 25, 9, 0), "s")] + good[1:]):
        with pytest.raises(FetchError):
            pipeline.validate_rows("sst", rows, area.cell_ids())


def test_job_runs_never_hold_urls_or_secrets(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    leak = "https://u:pw@host.example/q?token=SECRETTOKEN raw upstream text"
    crash = FakeSource("erddap_mur_sst", [RuntimeError(leak)])               # a bug that carries a URL in its message
    with_msg = FakeSource("erddap_viirs_chl", [FetchError(leak)])             # a fetcher that tries to pass text as the code
    w = FakeWriter()
    pipeline.ingest_variable(area, RUN, "sst", w, factory_for({"erddap_mur_sst": crash}), sleep=lambda s: None)
    pipeline.ingest_variable(area, RUN, "chl", w, factory_for({"erddap_viirs_chl": with_msg, "erddap_viirs_n20_chl": with_msg}),
                             sleep=lambda s: None)
    blob = json.dumps(w.runs, default=str)
    for needle in ("SECRETTOKEN", "pw@", "://", "raw upstream", "host.example"):
        assert needle not in blob
    assert {r["error_code"] for r in w.runs} <= {"internal_error", "error"}


def test_a_crashing_fetcher_does_not_stop_the_other_variables(make_area, monkeypatch):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    srcs = {"erddap_mur_sst": FakeSource("a", [RuntimeError("boom")]),
            "erddap_viirs_chl": FakeSource("b", [ok_rows(area, "chl", 0.5)]),
            "erddap_viirs_n20_chl": FakeSource("c", [ok_rows(area, "chl", 0.5)]),
            "erddap_etopo_depth": FakeSource("d", [ok_rows(area, "depth", 12.0)]),
            "open_meteo_marine": FakeSource("e", [ok_rows(area, "wave_wind", 0.4, extra={"wind_kmh": 10.0})])}
    w = FakeWriter()
    out = pipeline.run_ingest(area, RUN, w, factory_for(srcs), sleep=lambda s: None)
    assert [r.status for r in out] == ["failed", "success", "success", "success"]


def test_a_second_ingest_for_the_same_area_and_date_is_refused(make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    w = FakeWriter()
    w.locked = False
    with pytest.raises(RuntimeError):
        pipeline.run_ingest(area, RUN, w, factory_for({}), sleep=lambda s: None)

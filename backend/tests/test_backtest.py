"""Back-test harness tests. Everything here is SYNTHETIC: it proves the harness computes what it says, not that FSI is accurate."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from backtest import checks, inputs
from backtest.inputs import PoliteHttp, RequestCap
from backtest.run import main as run_main
from fsi.model import CellInputs, score_area
from tests.fsi_helpers import params

P = params()
UTC = timezone.utc


def synthetic_history(n_dates=4, n_cells=30, chl_every=2):
    h = {}
    for k in range(n_dates):
        d = date(2026, 6, 1) + timedelta(days=7 * k)
        t = datetime(d.year, d.month, d.day, 5, 0, tzinfo=UTC)
        h[d] = [CellInputs(i, 27.0 + (i % 9) * 0.4 + k * 0.1, t, 0.003 * ((i * 7) % n_cells + 1), 0.5 + (i % 5) * 0.4 if i % chl_every == 0 else None,
                           t if i % chl_every == 0 else None, "daily" if i % chl_every == 0 else None, 30.0)
                for i in range(1, n_cells + 1)]
    return h


# ---- statistics helpers -----------------------------------------------------------------------------------------------
def test_spearman_known_values():
    assert checks.spearman([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(0.8)
    assert checks.spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert checks.spearman([1, 2, 2, 3], [1, 2, 2, 3]) == pytest.approx(1.0)       # ties get average ranks
    assert checks.spearman([5, 5, 5, 5], [1, 2, 3, 4]) is None                     # no variation: undefined, not 1
    assert checks.spearman([1, 2], [1, 2]) is None


def test_top_set_includes_ties_and_overlap():
    vals = {i: float(i) for i in range(1, 11)}
    assert checks.top_set(vals, 0.2) == {9, 10}
    assert checks.top_set({1: 5.0, 2: 5.0, 3: 5.0}, 0.2) == {1, 2, 3}
    assert checks.overlap({1, 2, 3, 4}, {3, 4, 5}) == 0.5 and checks.overlap(set(), {1}) is None


# ---- hit rate on SYNTHETIC data (A9 definition) -----------------------------------------------------------------------
def trips(catches_cells, fisher="f1", season="dry", day=date(2026, 3, 1)):
    return [{"fisher": fisher, "season": season, "date": day, "cell_id": c, "catch_kg": kg} for kg, c in catches_cells]


def test_hit_rate_synthetic_matches_a_hand_count():
    fsi = {date(2026, 3, 1): {c: c * 10.0 for c in range(1, 11)}}                  # top 20% of 10 cells = cells 9 and 10
    t = trips([(10, 1), (20, 2), (30, 3), (40, 10), (50, 4)])                      # median 30; good = 40 (cell 10: hit), 50 (cell 4: miss)
    r = checks.hit_rate(t, fsi)
    assert (r["good_trips"], r["hits"], r["hit_rate"], r["lift"]) == (2, 1, 0.5, pytest.approx(2.5))


def test_hit_rate_good_catch_is_strictly_above_the_fishers_own_median():
    fsi = {date(2026, 3, 1): {c: c * 10.0 for c in range(1, 11)}}
    r = checks.hit_rate(trips([(10, 1), (30, 10), (30, 10), (30, 10), (50, 2)]), fsi)    # median 30: trips at 30 are not good
    assert r["good_trips"] == 1 and r["hits"] == 0


def test_hit_rate_leaves_out_unscored_cells_and_thin_seasons_and_says_so():
    fsi = {date(2026, 3, 1): {1: 10.0, 2: 90.0, 3: None}}
    t = trips([(10, 1), (20, 2), (90, 3), (80, 2), (5, 1)]) + trips([(1, 1), (9, 2)], fisher="f2")
    r = checks.hit_rate(t, fsi)
    assert r["left_out_too_few_trips"] == 2 and r["left_out_unscored"] == 1
    assert r["good_trips"] == 1                                                    # only the 80 kg trip is both good and scored


def test_hit_rate_is_none_without_good_trips():
    assert checks.hit_rate([], {})["hit_rate"] is None


# ---- sweeps, sensitivity, stability -----------------------------------------------------------------------------------
def test_monotonic_sweeps_pass_for_the_real_parameters_and_the_checker_can_fail():
    rows = checks.monotonic_sweeps(P)
    assert len(rows) >= 10 and all(r["ok"] for r in rows), [r for r in rows if not r["ok"]]
    assert checks.is_monotone([1, 2, 3, 3], "up") and not checks.is_monotone([1, 3, 2], "up")
    assert not checks.is_monotone([3, 1, 2], "down")


def test_sensitivity_to_an_unchanged_weight_is_zero_and_to_a_removed_input_is_not():
    h = synthetic_history()
    rows = checks.weight_sensitivity(h, P, factors=(1.0, 0.0))
    ident = [r for r in rows if r["factor"] == 1.0]
    assert ident and all(r["spearman"] == pytest.approx(1.0) and r["mean_abs_change"] == pytest.approx(0.0, abs=1e-9) for r in ident)
    chl_off = next(r for r in rows if r["weight"] == "chl" and r["factor"] == 0.0)
    assert chl_off["mean_abs_change"] > 0.5 and chl_off["spearman"] < 1.0
    assert not any(r["weight"] == "sst" and r["factor"] == 0.0 for r in rows)      # SST weight 0 is not a valid configuration


def test_moon_and_season_cannot_reorder_cells_on_one_date():
    h = {d: [CellInputs(c.cell_id, c.sst_c, c.sst_observed_at, c.sst_grad_c_per_km, 1.0, c.sst_observed_at, "daily", 30.0) for c in cells]
         for d, cells in synthetic_history().items()}                              # same freshness for every cell
    scored = {d: score_area(c, d, P, "trial") for d, c in h.items()}
    dr = checks.ranking_drivers(h, scored, P)
    assert dr["moon"] == pytest.approx(0.0, abs=1e-9) and dr["season"] == pytest.approx(0.0, abs=1e-9)
    assert dr["sst"] > 0.1 and dr["front"] > 0.1


def test_chlorophyll_dependence_is_neutral_when_there_is_none():
    h = synthetic_history(chl_every=10**9)
    h = {d: [CellInputs(c.cell_id, c.sst_c, c.sst_observed_at, c.sst_grad_c_per_km, None, None, None, c.depth_m) for c in cells] for d, cells in h.items()}
    assert checks.chlorophyll_dependence(h, P)["dates"] == 0
    assert checks.chlorophyll_dependence(synthetic_history(), P)["dates"] == 4


def test_stability_reports_the_gap_and_does_not_flatter_a_constant_map():
    h = synthetic_history()
    scored = {d: score_area(c, d, P, "trial") for d, c in h.items()}
    rows = checks.stability(scored)
    assert len(rows) == 3 and {r["gap_days"] for r in rows} == {7}
    const = {d: [CellInputs(c.cell_id, 29.0, c.sst_observed_at, 0.02, 1.0, c.sst_observed_at, "daily", 30.0) for c in cells] for d, cells in h.items()}
    flat = checks.stability({d: score_area(c, d, P, "trial") for d, c in const.items()})
    assert all(r["spearman"] is None for r in flat)                                # undefined, not a perfect 1.0


def test_coverage_counts_scored_and_confidence():
    h = synthetic_history()
    scored = {d: score_area(c, d, P, "trial") for d, c in h.items()}
    cov = checks.coverage(h, scored)
    assert cov["mean"]["sst"] == 1.0 and cov["mean"]["chl"] == pytest.approx(0.5) and cov["mean"]["scored"] == 1.0
    assert cov["mean"]["high"] == 0.0 and cov["dates_with_no_scored_cell"] == []


# ---- request limits and cache -----------------------------------------------------------------------------------------
def test_request_cap_is_enforced_before_the_request_is_made():
    calls = []
    http = PoliteHttp(lambda u, t: calls.append(u) or b"x", max_requests=3, pause_s=0, sleep=lambda s: None)
    for _ in range(3):
        http("https://example.invalid/a", 1)
    with pytest.raises(RequestCap):
        http("https://example.invalid/a", 1)
    assert len(calls) == 3 and http.count == 3


def test_pause_between_requests_is_kept():
    now, slept = [100.0], []
    def sleep(s): slept.append(s); now[0] += s
    http = PoliteHttp(lambda u, t: b"", max_requests=5, pause_s=2.0, clock=lambda: now[0], sleep=sleep)
    http("https://x", 1)
    now[0] += 0.5
    http("https://x", 1)                         # only 0.5 s passed: must wait 1.5 s
    now[0] += 5
    http("https://x", 1)                         # long enough: no wait
    assert slept == [pytest.approx(1.5)]


def test_bad_limits_are_refused():
    with pytest.raises(ValueError):
        PoliteHttp(max_requests=-1)
    with pytest.raises(ValueError):
        PoliteHttp(pause_s=-1)


def test_cache_must_be_outside_the_repository(tmp_path):
    assert inputs.check_cache_dir(tmp_path) == tmp_path.resolve()
    with pytest.raises(ValueError, match="outside the repository"):
        inputs.check_cache_dir(inputs.REPO_ROOT / "backend" / "data")
    with pytest.raises(ValueError, match="outside the repository"):
        inputs.check_cache_dir(inputs.REPO_ROOT)


def test_weekly_dates_are_spread_so_stopping_early_still_covers_the_year():
    ds = inputs.weekly_dates(date(2026, 11, 25), 52)
    assert len(ds) == 52 == len(set(ds)) and ds[0] == date(2026, 11, 25)
    assert all((date(2026, 11, 25) - d).days % 7 == 0 for d in ds)
    first13 = sorted(ds[:13])
    assert (first13[-1] - first13[0]).days >= 300                                  # the first pass already spans the year


def test_load_history_caches_stops_at_the_cap_and_leaves_out_transient_failures(tmp_path, monkeypatch, small_area):
    cells = [CellInputs(c, 29.0, datetime(2026, 6, 1, 5, tzinfo=UTC), 0.02, None, None, None, 20.0) for c in small_area.cell_ids()]
    calls = []
    def fake_date(area, d, http, depth):
        calls.append(d)
        http("https://example.invalid", 1)
        code = "timeout" if d == date(2026, 6, 8) else "no_recent_data" if d == date(2026, 6, 15) else None
        return {"cells": cells, "codes": {"sst": code, "chl": None}}
    monkeypatch.setattr(inputs, "fetch_date", fake_date)
    monkeypatch.setattr(inputs, "fetch_depth", lambda area, d, http: {c: 20.0 for c in small_area.cell_ids()})
    http = PoliteHttp(lambda u, t: b"", max_requests=3, pause_s=0, sleep=lambda s: None)
    dates = [date(2026, 6, 1), date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 22), date(2026, 6, 29)]
    out, st = inputs.load_history(small_area, dates, tmp_path, http, log=lambda m: None)
    assert set(out) == {date(2026, 6, 1), date(2026, 6, 15)}                       # the timeout date is left out, not scored as "no data"
    assert st["stopped_by_cap"] and st["failed"][date(2026, 6, 8)]["sst"] == "timeout" and st["failed"][date(2026, 6, 15)]["sst"] == "no_recent_data"
    again, st2 = inputs.load_history(small_area, dates, tmp_path, None, log=lambda m: None)   # offline: cache only
    assert set(again) == {date(2026, 6, 1), date(2026, 6, 15)} and st2["from_cache"] == 2 and st2["fetched"] == 0
    assert not (tmp_path / small_area.area_id / "2026-06-08.json").exists()      # transient failures are never cached


def test_end_to_end_offline_report_says_it_is_not_evidence_of_accuracy(tmp_path, capsys):
    area_dir = tmp_path / "th-chonburi-coast"
    area_dir.mkdir()
    from ingest.config import load_area
    cids = load_area("th-chonburi-coast").cell_ids()
    d = date(2026, 6, 1)
    t = datetime(2026, 6, 1, 5, 0, tzinfo=UTC)
    cells = [CellInputs(c, 28.0 + (i % 9) * 0.3, t, 0.002 * (i % 40 + 1), 0.8 if i % 2 else None, t if i % 2 else None, "daily" if i % 2 else None, 30.0)
             for i, c in enumerate(cids)]
    (area_dir / f"{d}.json").write_text(json.dumps({"version": inputs.CACHE_VERSION, "codes": {"sst": None, "chl": None},
                                                    "cells": [inputs._ser(c) for c in cells]}), encoding="utf-8")
    out = tmp_path / "r.md"
    assert run_main(["--area", "th-chonburi-coast", "--end", "2026-06-01", "--count", "1", "--cache-dir", str(tmp_path), "--offline", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "NOT EVIDENCE OF ACCURACY" in text and "Global Fishing Watch was not used" in text and "SYNTHETIC" in text
    assert "weekly sample is **not** day-to-day" in text
    assert run_main(["--area", "th-chonburi-coast", "--end", "2026-06-01", "--count", "1", "--cache-dir", "backend/data", "--offline"]) == 2


def test_stability_drivers_lists_the_baseline_and_each_switched_off_weight():
    h = synthetic_history()
    rows = checks.stability_drivers(h, P)
    assert [r["off"] for r in rows] == ["none", "front", "chl", "depth", "moon", "season"]
    assert all(r["pairs"] == 3 for r in rows)
    base = rows[0]["spearman"]
    assert any(r["spearman"] != base for r in rows[1:])                          # switching an input off does change the picture

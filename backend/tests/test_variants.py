"""Tests for the week-to-week stability variants (backtest/variants.py). All data is SYNTHETIC."""
import json
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from backtest import inputs, variants
from backtest.inputs import PoliteHttp
from fsi.model import CellInputs, score_area
from tests.fsi_helpers import params

P = params()
UTC = timezone.utc


def cell(i, grad, sst=29.0, t=datetime(2026, 6, 1, 5, tzinfo=UTC)):
    return CellInputs(i, sst, t, grad, 1.0, t, "daily", 30.0)


# ---- parameter variants ------------------------------------------------------------------------------------------------------
def test_front_weight_variant_changes_only_the_front_weight_and_leaves_the_original_alone():
    before = dict(P.weights)
    v = variants.weights_variant(P, front_factor=0.5)
    assert v.weights["front"] == pytest.approx(P.weights["front"] * 0.5)
    assert {k: x for k, x in v.weights.items() if k != "front"} == {k: x for k, x in P.weights.items() if k != "front"}
    assert P.weights == before                                                             # the config's own weights are never touched


def test_reference_variant_zeroes_every_weight_outside_the_list():
    v = variants.weights_variant(P, only=("sst",))
    assert v.weights["sst"] == P.weights["sst"] and all(v.weights[k] == 0 for k in v.weights if k != "sst")


# ---- pairs and windows ---------------------------------------------------------------------------------------------------------
def test_week_pairs_and_spread():
    ds = [date(2026, 1, 1) + timedelta(days=7 * i) for i in range(10)] + [date(2026, 6, 1)]
    pairs = variants.week_pairs(ds)
    assert len(pairs) == 9 and all((b - a).days == 7 for a, b in pairs)
    pick = variants.spread_pairs(pairs, 4)
    assert pick[0] == pairs[0] and pick[-1] == pairs[-1] and len(pick) == 4
    assert variants.spread_pairs(pairs, 20) == pairs and variants.spread_pairs(pairs, 1) == [pairs[0]]


def test_windows_end_on_the_date_and_must_not_overlap():
    d = date(2026, 6, 10)
    assert variants.window_days(d, 3) == [date(2026, 6, 8), date(2026, 6, 9), d]
    variants.check_no_overlap(d, d + timedelta(days=7), 3)
    variants.check_no_overlap(d, d + timedelta(days=7), 7)                                  # windows of 7 days touch but share no day
    with pytest.raises(ValueError, match="overlap"):
        variants.check_no_overlap(d, d + timedelta(days=7), 8)
    with pytest.raises(ValueError, match="overlap"):
        variants.check_no_overlap(d, d + timedelta(days=2), 3)
    with pytest.raises(ValueError):
        variants.window_days(d, 0)


# ---- smoothing ---------------------------------------------------------------------------------------------------------------------
def test_smoothing_is_the_mean_of_the_days_that_have_a_value_and_never_counts_a_gap_as_zero():
    cells = [cell(1, 0.06), cell(2, 0.03), cell(3, 0.10), cell(4, None, sst=None)]
    daily = [{1: 0.00, 2: None, 3: 0.20, 4: 0.5}, {1: 0.03, 2: float("nan"), 3: None, 4: 0.5}]
    out = variants.smooth_front(cells, daily)
    assert out[0].sst_grad_c_per_km == pytest.approx(0.015)                                    # mean of the two daily values 0.00 and 0.03
    assert out[1].sst_grad_c_per_km is None                                                    # no day has a value: stays None, not 0
    assert out[2].sst_grad_c_per_km == pytest.approx(0.20)                                     # 0.20 and a gap -> 0.20, not 0.10
    assert out[3].sst_grad_c_per_km is None                                                    # no SST on the date: no gradient (schema rule)
    assert [c.sst_c for c in out] == [c.sst_c for c in cells] and [c.chl_mg_m3 for c in out] == [c.chl_mg_m3 for c in cells]


def test_smoothing_with_the_own_day_included():
    c = [cell(1, 0.06)]
    out = variants.smooth_front(c, [{1: 0.00}, {1: 0.03}, {1: 0.06}])
    assert out[0].sst_grad_c_per_km == pytest.approx(0.03)


# ---- metrics -----------------------------------------------------------------------------------------------------------------------------
def make_scored(shift):
    d1, d2 = date(2026, 6, 1), date(2026, 6, 8)
    at = lambda d: datetime(d.year, d.month, d.day, 5, tzinfo=UTC)
    cells = lambda off, d: [cell(i, 0.002 * ((i * 3 + off) % 30 + 1), sst=27 + (i % 9) * 0.3, t=at(d)) for i in range(1, 31)]
    return {d1: score_area(cells(0, d1), d1, P, "trial"), d2: score_area(cells(shift, d2), d2, P, "trial")}, [(d1, d2)]


def test_identical_maps_agree_completely_and_unrelated_maps_do_not():
    sc, pairs = make_scored(0)
    r = variants.pair_metrics(sc, pairs)[0]
    assert r["spearman"] == pytest.approx(1.0) and r["top20_kept"] == 1.0 and r["mean_abs_change"] < 5.0          # not 0: the moon term differs between the two dates (the same shift for every cell)
    sc2, pairs2 = make_scored(7)
    r2 = variants.pair_metrics(sc2, pairs2)[0]
    assert r2["spearman"] < 0.99 and r2["mean_abs_change"] > 0


def test_summary_reports_pairs_mean_standard_error_and_undefined_counts():
    rows = [{"spearman": 0.2, "top20_kept": 0.3, "mean_abs_change": 5.0}, {"spearman": 0.4, "top20_kept": 0.5, "mean_abs_change": 7.0},
            {"spearman": None, "top20_kept": 0.4, "mean_abs_change": 6.0}]
    s = variants.summarise(rows)
    assert s["pairs"] == 3 and s["spearman"] == pytest.approx(0.3) and s["undefined_spearman"] == 1
    assert s["spearman_se"] == pytest.approx(0.1) and s["top20_kept"] == pytest.approx(0.4)
    assert variants.summarise([])["spearman"] is None


def test_gradient_spearman_uses_only_cells_present_in_both():
    a = {1: 0.1, 2: 0.2, 3: 0.3, 4: None, 5: 0.5}
    b = {1: 0.1, 2: 0.2, 3: 0.3, 4: 0.4, 5: 0.5, 6: 0.6}
    assert variants.gradient_spearman(a, b) == pytest.approx(1.0)
    assert variants.gradient_spearman({1: 1.0}, {1: 1.0}) is None


# ---- cache and live path -------------------------------------------------------------------------------------------------------------------
def test_daily_sst_is_cached_outside_the_repository_and_read_back(tmp_path, monkeypatch, small_area):
    calls = []
    obs = datetime(2026, 6, 1, 9, tzinfo=UTC)

    class R:
        def __init__(self, c): self.cell_id, self.extra = c, {"grad_c_per_km": 0.01 * c if c % 2 else None}
    http = PoliteHttp(lambda u, t: b"", max_requests=5, pause_s=0, sleep=lambda s: None)

    def fake_fetch_field(area, d, h=None, *a, **k):
        calls.append(d)
        h.count += 2
        return [R(c) for c in area.cell_ids()], obs, None, h
    monkeypatch.setattr(variants, "fetch_field", fake_fetch_field)
    g, o, h = variants.fetch_sst_day(small_area, date(2026, 6, 1), tmp_path, http, log=lambda m: None)
    assert o == obs and set(g) == set(small_area.cell_ids()) and calls == [date(2026, 6, 1)]
    g2, o2, _ = variants.fetch_sst_day(small_area, date(2026, 6, 1), tmp_path, None, log=lambda m: None)          # offline: from the cache
    assert g2 == g and o2 == obs and calls == [date(2026, 6, 1)]
    assert variants.fetch_sst_day(small_area, date(2026, 6, 2), tmp_path, None, log=lambda m: None)[0] is None  # not cached, no network
    with pytest.raises(ValueError, match="outside the repository"):
        variants.fetch_sst_day(small_area, date(2026, 6, 1), inputs.REPO_ROOT / "backend" / "cache", None)
    assert json.loads(next((tmp_path / small_area.area_id).glob("*.json")).read_text(encoding="utf-8"))["observed_at"].startswith("2026-06-01")


def test_a_pair_with_fewer_than_three_common_cells_is_skipped_not_reported():
    """F-26: two cells in common is too few for a rank correlation; the pair must give NO row (not a row with Spearman None
    and a mean change computed from two cells). Three common cells is the smallest pair that is reported."""
    d1, d2 = date(2026, 6, 1), date(2026, 6, 8)
    at = lambda d: datetime(d.year, d.month, d.day, 5, tzinfo=UTC)
    mk = lambda d, ids: score_area([cell(i, 0.002 * i, sst=27 + i * 0.3, t=at(d)) for i in ids], d, P, "trial")
    two = {d1: mk(d1, [1, 2, 3, 4]), d2: mk(d2, [3, 4, 8, 9])}          # common cells: 3 and 4
    assert variants.pair_metrics(two, [(d1, d2)]) == []
    three = {d1: mk(d1, [1, 2, 3, 4]), d2: mk(d2, [2, 3, 4, 9])}        # common cells: 2, 3, 4
    rows = variants.pair_metrics(three, [(d1, d2)])
    assert len(rows) == 1 and rows[0]["cells"] == 3
    assert variants.pair_metrics({d1: mk(d1, [1, 2]), d2: mk(d2, [1, 2])}, [(d1, d2)]) == []   # fewer cells than the minimum on both days

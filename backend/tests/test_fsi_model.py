"""FSI v1 model tests. Each guard has a test that must go RED when the guard is removed (docs/fsi-mutation-log.md).
Expected numbers are computed in the test from the formula in ARCHITECTURE.md A4, not copied from the code."""
import math
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from fsi import model
from fsi.explain import explain_cell
from fsi.model import CellInputs, fsi_display, score_area, score_cell
from fsi.moon import moon_for_local_date
from ingest.timeutil import local_day_end_utc
from tests.fsi_helpers import NOON_UTC, RUN, UTC, full_cell, obs_days_ago, params

P = params()


def area(n=25, **over):
    """n water cells with distinct gradients; cell 1 has the highest gradient."""
    return [full_cell(cid=i, sst_grad_c_per_km=0.001 * (n - i + 1), **over) for i in range(1, n + 1)]


def one(cell, cells=None, level="trial", p=P):
    cells = cells or [cell] + [c for c in area() if c.cell_id != cell.cell_id]
    out = score_area(cells, RUN, p, level)
    return next(s for s in out if s.cell_id == cell.cell_id)


def manual(p, sub, fresh):
    num = sum(p.weights[k] * fresh[k] * sub[k] for k in sub if sub[k] is not None and fresh[k])
    den = sum(p.weights[k] * fresh[k] for k in sub if sub[k] is not None and fresh[k])
    return 100 * num / den


# ---- the whole formula, from scratch -----------------------------------------------------------------------------------
def test_full_cell_matches_the_formula_computed_by_hand():
    s = one(full_cell(cid=1, sst_grad_c_per_km=0.5))   # highest gradient of 25 cells: mid-rank percentile (24 + 0.5) / 25
    moon = moon_for_local_date(RUN, P.timezone)["illumination"]
    sub = {"sst": 1.0, "front": 24.5 / 25, "chl": 1.0, "depth": 1.0, "moon": 1 - 0.6 * moon, "season": 0.5}
    assert s.fsi == pytest.approx(manual(P, sub, {k: 1.0 for k in sub}), abs=1e-3)
    assert s.confidence == "medium" and s.confidence_cap == "no_verified_catch_logs"
    assert s.confidence_reasons == ("no_verified_catch_logs",)


def test_scaling_all_weights_does_not_change_the_score():
    w = {k: v * 10 for k, v in P.weights.items()}
    assert one(full_cell(), p=replace(P, weights=w)).fsi == one(full_cell()).fsi


def test_missing_chlorophyll_is_excluded_not_scored_as_zero():
    cell = full_cell(cid=1, sst_grad_c_per_km=0.5, chl_mg_m3=None, chl_observed_at=None, chl_product=None)
    s = one(cell)
    moon = moon_for_local_date(RUN, P.timezone)["illumination"]
    sub = {"sst": 1.0, "front": 24.5 / 25, "chl": None, "depth": 1.0, "moon": 1 - 0.6 * moon, "season": 0.5}
    assert s.fsi == pytest.approx(manual(P, sub, {"sst": 1, "front": 1, "chl": 0, "depth": 1, "moon": 1, "season": 1}), abs=1e-3)
    assert s.scores["chl"] is None and s.fresh["chl"] is None
    assert s.confidence == "low" and "chl_missing" in s.confidence_reasons


def test_freshness_enters_numerator_and_denominator():
    """With ages 3 and 5 days, a_sst = exp(-2/3) and a_chl = exp(-4/3); the score must equal the weighted mean using them."""
    cell = full_cell(cid=1, sst_grad_c_per_km=0.5, sst_age=3, chl_age=5, chl_mg_m3=2.0)
    s = one(cell)
    moon = moon_for_local_date(RUN, P.timezone)["illumination"]
    a_sst, a_chl = math.exp(-2 / 3), math.exp(-4 / 3)
    sub = {"sst": 1.0, "front": 24.5 / 25, "chl": math.exp(-0.5 * (math.log10(2.0) / 0.5) ** 2), "depth": 1.0,
           "moon": 1 - 0.6 * moon, "season": 0.5}
    fresh = {"sst": a_sst, "front": a_sst, "chl": a_chl, "depth": 1, "moon": 1, "season": 1}
    assert s.fsi == pytest.approx(manual(P, sub, fresh), abs=1e-3)
    assert s.fresh["front"] == pytest.approx(a_sst)          # the front shares the SST's age


# ---- "no SST = no score" -----------------------------------------------------------------------------------------------
def test_no_sst_means_no_score_even_when_everything_else_is_present():
    cell = full_cell(sst_c=None, sst_observed_at=None)
    s = one(cell)
    assert s.fsi is None and s.confidence is None and s.confidence_cap is None
    assert s.confidence_reasons == ("sst_missing",)
    assert all(v is None for v in s.scores.values()) and all(v is None for v in s.fresh.values())


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 41.0, -2.5, True])
def test_unusable_sst_values_give_no_score_and_say_invalid(bad):
    s = one(full_cell(sst_c=bad))
    assert s.fsi is None and s.confidence_reasons == ("sst_invalid",)


def test_sst_age_limit_is_inclusive_and_one_day_later_is_expired():
    at_limit = one(full_cell(sst_age=P.sst_max_days))
    assert at_limit.fsi is not None and at_limit.states["sst"].status == "stale"
    expired = one(full_cell(sst_age=P.sst_max_days + 1))
    assert expired.fsi is None and expired.confidence_reasons == ("sst_missing",)
    assert expired.states["sst"].status == "expired"


def test_stale_sst_lowers_freshness_and_confidence():
    s = one(full_cell(sst_age=3))
    assert s.fresh["sst"] == pytest.approx(math.exp(-(3 - 1) / 3))
    assert s.confidence == "low" and "sst_stale" in s.confidence_reasons


def test_observation_after_the_end_of_the_local_run_date_is_not_used():
    end = local_day_end_utc(RUN, P.timezone)                     # exclusive upper bound, in UTC
    ok = one(full_cell(sst_observed_at=end - timedelta(seconds=1)))
    assert ok.fsi is not None
    future = one(full_cell(sst_observed_at=end))
    assert future.fsi is None and future.confidence_reasons == ("sst_invalid",)
    future_chl = one(full_cell(chl_observed_at=end + timedelta(hours=1)))
    assert "chl_invalid" in future_chl.confidence_reasons and future_chl.scores["chl"] is None


def test_naive_timestamp_is_invalid():
    s = one(full_cell(sst_observed_at=datetime(2026, 11, 26, 5, 0)))
    assert s.fsi is None and s.confidence_reasons == ("sst_invalid",)


def test_value_without_time_or_time_without_value_is_invalid():
    assert one(full_cell(sst_observed_at=None)).confidence_reasons == ("sst_invalid",)
    assert one(full_cell(sst_c=None)).confidence_reasons == ("sst_invalid",)


# ---- chlorophyll -------------------------------------------------------------------------------------------------------
def test_bloom_is_cut_to_zero_above_the_threshold_only():
    assert model.s_chl(P.bloom_mg_m3 + 0.0001, P) == 0.0
    assert model.s_chl(P.bloom_mg_m3, P) > 0.0
    assert model.s_chl(1.0, P) == 1.0


@pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, math.inf, 1000.5])
def test_chlorophyll_that_cannot_be_real_is_invalid_and_not_scored(bad):
    s = one(full_cell(chl_mg_m3=bad))
    assert "chl_invalid" in s.confidence_reasons
    assert s.scores["chl"] is None and s.fresh["chl"] is None and s.fsi is not None


def test_chlorophyll_age_limits():
    assert one(full_cell(chl_age=P.chl_max_days)).states["chl"].status == "stale"      # 10 days: used, lower weight
    expired = one(full_cell(chl_age=P.chl_max_days + 1))
    assert expired.scores["chl"] is None and "chl_missing" in expired.confidence_reasons


# ---- depth -------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("d,exp", [(0, 0.0), (5, 0.5), (10, 1.0), (80, 1.0), (140, 0.5), (200, 0.0), (500, 0.0)])
def test_depth_curve(d, exp):
    assert model.s_depth(d, P) == pytest.approx(exp)


def test_depth_missing_scores_the_cell_but_marks_it_low():
    s = one(full_cell(depth_m=None))
    assert s.fsi is not None and s.scores["depth"] is None
    assert s.confidence == "low" and "depth_missing" in s.confidence_reasons


@pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf, 20000.0])
def test_depth_invalid(bad):
    s = one(full_cell(depth_m=bad))
    assert "depth_invalid" in s.confidence_reasons and s.scores["depth"] is None


# ---- front (percentile) ------------------------------------------------------------------------------------------------
def test_front_needs_enough_cells_in_the_area():
    few = area(P.front_min_cells - 1)
    assert model.front_percentiles(few, RUN, P) == {}
    s = score_area(few, RUN, P, "trial")[0]
    assert s.scores["front"] is None and "front_missing" in s.confidence_reasons and s.confidence == "low"
    enough = area(P.front_min_cells)
    assert len(model.front_percentiles(enough, RUN, P)) == P.front_min_cells


def test_front_percentile_only_ranks_cells_with_a_depth_value():
    cells = area(25)
    land = full_cell(cid=99, depth_m=None, sst_grad_c_per_km=99.0)          # a huge gradient on a partly-land cell
    pct = model.front_percentiles(cells + [land], RUN, P)
    assert 99 not in pct and pct[1] == pytest.approx(24.5 / 25)              # the land cell did not push cell 1 down
    s = next(x for x in score_area(cells + [land], RUN, P, "trial") if x.cell_id == 99)
    assert s.scores["front"] is None and s.front_note == "front_unranked" and "front_missing" in s.confidence_reasons


def test_front_ties_share_the_mid_rank():
    cells = [full_cell(cid=i, sst_grad_c_per_km=0.05) for i in range(1, 21)]
    assert set(model.front_percentiles(cells, RUN, P).values()) == {0.5}


# ---- confidence --------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("level,conf,cap,reasons", [
    ("trial", "medium", "no_verified_catch_logs", ("no_verified_catch_logs",)),
    ("beta", "high", None, ()), ("confirmed", "high", None, ()),
    (None, "medium", "no_verified_catch_logs", ("no_verified_catch_logs",)),        # fail closed
    ("BETA", "medium", "no_verified_catch_logs", ("no_verified_catch_logs",)),
    ("verified", "medium", "no_verified_catch_logs", ("no_verified_catch_logs",)),
])
def test_confidence_is_capped_until_the_area_is_verified(level, conf, cap, reasons):
    s = one(full_cell(), level=level)
    assert (s.confidence, s.confidence_cap, s.confidence_reasons) == (conf, cap, reasons)


def test_low_confidence_in_a_trial_area_still_carries_the_cap():
    s = one(full_cell(chl_mg_m3=None, chl_observed_at=None, chl_product=None))
    assert s.confidence == "low" and s.confidence_cap == "no_verified_catch_logs"
    assert "no_verified_catch_logs" not in s.confidence_reasons               # the cap did not lower anything here


def test_medium_needs_fresh_sst_and_fresh_chlorophyll():
    assert one(full_cell(sst_age=2)).confidence == "medium"
    assert one(full_cell(sst_age=3)).confidence == "low"
    assert one(full_cell(chl_age=3)).confidence == "medium"
    s = one(full_cell(chl_age=4))
    assert s.confidence == "low" and "chl_stale" in s.confidence_reasons


def test_eight_day_composite_is_fresh_for_eight_days():
    assert one(full_cell(chl_age=8, chl_product="8day")).confidence == "medium"
    s = one(full_cell(chl_age=9, chl_product="8day"))
    assert s.confidence == "low" and "chl_stale" in s.confidence_reasons


def test_high_is_never_reached_with_a_missing_input_even_when_verified():
    s = one(full_cell(depth_m=None), level="beta")
    assert s.confidence == "low" and s.confidence_cap is None


# ---- numeric safety ----------------------------------------------------------------------------------------------------
def test_zero_total_weight_gives_no_score_instead_of_dividing_by_zero():
    p = replace(P, weights={k: 0.0 for k in P.weights})
    s = one(full_cell(), p=p)
    assert s.fsi is None and s.scores["sst"] is None        # consistent with the schema: fsi NULL iff s_sst NULL


def test_fsi_stays_within_0_and_100():
    for cell in area(25):
        s = one(cell, cells=area(25))
        assert 0 <= s.fsi <= 100


def test_display_rounding_is_half_up_like_the_browser():
    assert fsi_display(74.5) == 75 and fsi_display(0.5) == 1 and fsi_display(2.5) == 3 and fsi_display(None) is None


def test_scoring_is_deterministic():
    assert score_area(area(), RUN, P, "trial") == score_area(area(), RUN, P, "trial")


# ---- sub-score shapes --------------------------------------------------------------------------------------------------
def test_responses_are_monotonic_where_the_model_says_they_should_be():
    up = [model.s_sst(t / 10, P) for t in range(200, 291)]
    down = [model.s_sst(t / 10, P) for t in range(290, 380)]
    assert all(a <= b for a, b in zip(up, up[1:])) and all(a >= b for a, b in zip(down, down[1:]))
    assert model.s_sst(P.sst_c, P) == 1.0
    chl_up = [model.s_chl(10 ** (x / 100), P) for x in range(-200, 1)]
    assert all(a <= b for a, b in zip(chl_up, chl_up[1:]))
    moon = [model.s_moon(i / 100, P) for i in range(101)]
    assert all(a >= b for a, b in zip(moon, moon[1:])) and moon[0] == 1.0 and moon[-1] == pytest.approx(0.4)


def test_moon_matches_the_browser_formula():
    # reference values printed by node on 2026-11-26 from moonPhase() in src/services/marine-data.js at 02:00Z (09:00 Asia/Bangkok)
    m = moon_for_local_date(RUN, "Asia/Bangkok")
    assert m["phase"] == pytest.approx(0.5474944715058996, abs=1e-9) and m["illumination"] == pytest.approx(0.9779016140844988, abs=1e-9)
    assert m["age_days"] == pytest.approx(16.167834137331244, abs=1e-6)
    m2 = moon_for_local_date(RUN.replace(year=2025, month=6, day=15), "Asia/Bangkok")
    assert m2["illumination"] == pytest.approx(0.8333200545185662, abs=1e-9)


# ---- explanation -------------------------------------------------------------------------------------------------------
def test_explanation_shows_inputs_and_marks_placeholders():
    cell = full_cell(cid=1)
    s = one(cell)
    e = explain_cell(cell, s, RUN, P)
    assert e["subscores"]["moon"]["placeholder"] and e["subscores"]["season"]["placeholder"]
    assert not e["subscores"]["sst"]["placeholder"]
    assert sum(v["contribution_points"] for v in e["subscores"].values()) == pytest.approx(s.fsi, abs=0.05)
    assert e["data_weight_share"] == 1.0 and "demo_weights_untuned" in e["notes"]
    assert "front_percentile_over_depth_not_null_cells" in e["notes"] and "no_verified_catch_logs" in e["notes"]
    assert e["observations"]["sst"]["age_days"] == 0 and e["observations"]["depth"]["age_days"] is None


def test_explanation_of_an_unscored_cell_has_no_number():
    cell = full_cell(sst_c=None, sst_observed_at=None)
    e = explain_cell(cell, one(cell), RUN, P)
    assert e["fsi"] is None and e["data_weight_share"] is None
    assert all(v["contribution_points"] is None for v in e["subscores"].values())


def test_explanation_reports_a_reduced_data_share_when_chlorophyll_is_missing():
    cell = full_cell(chl_mg_m3=None, chl_observed_at=None, chl_product=None)
    e = explain_cell(cell, one(cell), RUN, P)
    assert e["data_weight_share"] == pytest.approx((0.20 + 0.20 + 0.15) / 0.80, abs=1e-3)

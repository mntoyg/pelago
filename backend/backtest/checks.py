"""Back-test checks for FSI v1 (ARCHITECTURE.md A9). Pure functions over lists of scored cells; no network, no database.

WHAT THIS IS NOT: nothing here measures whether FSI predicts fish. That needs verified catch logs or fishing-activity data
(Global Fishing Watch, token not provided). The checks below say whether the number behaves sensibly (coverage, direction of
response, spread, weight sensitivity, stability). `hit_rate` is implemented from the A9 definition and is exercised only on
SYNTHETIC data in the tests.
"""
from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np

from fsi import model
from fsi.config import SUBSCORES, FsiParams
from fsi.model import CellInputs, CellScore, score_area

NOT_ACCURACY = ("NOT EVIDENCE OF ACCURACY: these checks describe how the formula behaves on satellite inputs. They cannot show "
                "that high FSI cells have more fish. That needs verified catch logs (A9) or fishing-activity data.")


# ---------------------------------------------------------------------------------------------------------------------
# small statistics helpers (numpy only)
# ---------------------------------------------------------------------------------------------------------------------
def spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Rank correlation with average ranks for ties. None when it is undefined (fewer than 3 pairs or no variation)."""
    if len(a) != len(b) or len(a) < 3:
        return None
    ra, rb = _ranks(a), _ranks(b)
    if np.std(ra) == 0 or np.std(rb) == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _ranks(x: Sequence[float]) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x))
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def top_set(values: Mapping[int, float], fraction: float = 0.2) -> set[int]:
    """Cells whose value is at or above the (1 - fraction) quantile; ties at the threshold are included."""
    if not values:
        return set()
    thr = float(np.quantile(list(values.values()), 1 - fraction))
    return {k for k, v in values.items() if v >= thr}


def overlap(a: set, b: set) -> float | None:
    return None if not a else len(a & b) / len(a)


def _mean(xs: Iterable[float | None]) -> float | None:
    v = [x for x in xs if x is not None]
    return statistics.fmean(v) if v else None


# ---------------------------------------------------------------------------------------------------------------------
# 1. coverage
# ---------------------------------------------------------------------------------------------------------------------
def coverage(history: Mapping[date, list[CellInputs]], scored: Mapping[date, list[CellScore]]) -> dict:
    """Share of cells per input and per outcome, per date and overall. Land-proxy cells (no depth) are listed on their own."""
    per_date = {}
    for d, cells in history.items():
        n = len(cells) or 1
        sc = scored[d]
        per_date[d] = {
            "cells": len(cells), "sst": sum(c.sst_c is not None for c in cells) / n,
            "chl": sum(c.chl_mg_m3 is not None for c in cells) / n, "depth": sum(c.depth_m is not None for c in cells) / n,
            "scored": sum(s.scored for s in sc) / n,
            "medium": sum(s.confidence == "medium" for s in sc) / n, "low": sum(s.confidence == "low" for s in sc) / n,
            "high": sum(s.confidence == "high" for s in sc) / n,
        }
    keys = ("sst", "chl", "depth", "scored", "medium", "low", "high")
    return {"per_date": per_date, "mean": {k: _mean(v[k] for v in per_date.values()) for k in keys},
            "dates_with_no_scored_cell": [d for d, v in per_date.items() if v["scored"] == 0],
            "reasons": Counter(r for ss in scored.values() for s in ss for r in s.confidence_reasons)}


# ---------------------------------------------------------------------------------------------------------------------
# 2. monotonic response (the formula must move the way A4 says it should)
# ---------------------------------------------------------------------------------------------------------------------
def is_monotone(ys: Sequence[float], direction: str, tol: float = 1e-12) -> bool:
    pairs = list(zip(ys, ys[1:]))
    return all(b >= a - tol for a, b in pairs) if direction == "up" else all(b <= a + tol for a, b in pairs)


def monotonic_sweeps(p: FsiParams) -> list[dict]:
    """Each row: a sub-score swept over its input with everything else fixed, and whether it moved in the expected direction."""
    rows = []

    def add(name, xs, fn, direction):
        ys = [fn(x) for x in xs]
        rows.append({"check": name, "direction": direction, "min": min(ys), "max": max(ys), "ok": is_monotone(ys, direction)})

    lin = lambda a, b, n: [a + (b - a) * i / n for i in range(n + 1)]
    add("S_sst rises up to the target temperature", lin(18, p.sst_c, 200), lambda t: model.s_sst(t, p), "up")
    add("S_sst falls above the target temperature", lin(p.sst_c, 36, 200), lambda t: model.s_sst(t, p), "down")
    add("S_chl rises up to the target (log scale)", [10 ** x for x in lin(-2, p.log10_chl, 200)], lambda c: model.s_chl(c, p), "up")
    add("S_chl falls from the target to the bloom threshold",
        [10 ** x for x in lin(p.log10_chl, math.log10(p.bloom_mg_m3), 200)], lambda c: model.s_chl(c, p), "down")
    add("S_chl is zero above the bloom threshold", lin(p.bloom_mg_m3 * 1.0001, 100, 50), lambda c: model.s_chl(c, p), "down")
    add("S_depth rises from the shoreline to the working depth", lin(0, p.depth_ramp_up_m, 50), lambda d: model.s_depth(d, p), "up")
    add("S_depth falls from the working depth to the cut-off", lin(p.depth_full_to_m, p.depth_zero_at_m, 100),
        lambda d: model.s_depth(d, p), "down")
    add("S_moon falls as the moon gets brighter", lin(0, 1, 100), lambda i: model.s_moon(i, p), "down")
    add("freshness a falls as data gets older", list(range(0, 11)), lambda a: model.freshness(a, p), "down")
    # whole-pipeline sweep: a cell's FSI with other inputs fixed, SST below the target
    run = date(2026, 6, 1)
    from datetime import datetime, timedelta, timezone
    obs = datetime(2026, 6, 1, 5, 0, tzinfo=timezone.utc)

    def fsi_of(sst):
        c = CellInputs(1, sst, obs, 0.02, 1.0, obs, "daily", 30.0)
        return score_area([c], run, p, "trial")[0].fsi
    add("FSI (whole cell) rises with SST below the target", lin(20, p.sst_c, 100), fsi_of, "up")
    return rows


# ---------------------------------------------------------------------------------------------------------------------
# 3. distribution and what drives the ranking
# ---------------------------------------------------------------------------------------------------------------------
def distribution(scored: Mapping[date, list[CellScore]]) -> dict:
    vals = [s.fsi for ss in scored.values() for s in ss if s.fsi is not None]
    if not vals:
        return {"n": 0}
    q = np.quantile(vals, [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1])
    per_date_spread = [float(np.ptp([s.fsi for s in ss if s.fsi is not None])) for ss in scored.values()
                       if sum(s.fsi is not None for s in ss) > 1]
    hist = np.histogram(vals, bins=10, range=(0, 100))[0].tolist()
    return {"n": len(vals), "quantiles": dict(zip(("min", "p10", "p25", "median", "p75", "p90", "max"), (float(x) for x in q))),
            "mean_within_date_range": _mean(per_date_spread), "hist_10_bins_0_100": hist,
            "share_at_floor_or_ceiling": sum(v <= 0.0 or v >= 100.0 for v in vals) / len(vals)}


def ranking_drivers(history: Mapping[date, list[CellInputs]], scored: Mapping[date, list[CellScore]], p: FsiParams) -> dict:
    """For each input, the average across dates of the SPREAD (standard deviation across cells) of its contribution to the
    score in FSI points. An input with a spread of 0 cannot change which cell is better than another on that date."""
    spread: dict[str, list[float]] = defaultdict(list)
    for d, ss in scored.items():
        rows = [s for s in ss if s.fsi is not None]
        if len(rows) < 3:
            continue
        den = [sum(p.weights[k] * s.fresh[k] for k in SUBSCORES if s.scores[k] is not None and s.fresh[k]) for s in rows]
        for k in SUBSCORES:
            contrib = [100 * p.weights[k] * s.fresh[k] * s.scores[k] / dn if s.scores[k] is not None and s.fresh[k] else 0.0
                       for s, dn in zip(rows, den)]
            spread[k].append(float(np.std(contrib)))
    return {k: _mean(v) for k, v in spread.items()}


# ---------------------------------------------------------------------------------------------------------------------
# 4. sensitivity to each weight
# ---------------------------------------------------------------------------------------------------------------------
def weight_sensitivity(history: Mapping[date, list[CellInputs]], p: FsiParams, level: str = "trial",
                       factors: Sequence[float] = (0.0, 0.5, 1.5)) -> list[dict]:
    """One weight at a time is multiplied by each factor (0 = the input is switched off). Compared with the baseline per date:
    Spearman rank correlation of the cells, overlap of the top 20%, and the mean absolute change in FSI points."""
    base = {d: score_area(cells, d, p, level) for d, cells in history.items()}
    out = []
    for k in SUBSCORES:
        for f in factors:
            w = dict(p.weights)
            w[k] = w[k] * f
            if k == "sst" and w[k] <= 0:
                continue                                   # SST is the gate: a zero weight is not a valid configuration
            alt_p = replace(p, weights=w)
            rho, ov, dabs = [], [], []
            for d, cells in history.items():
                alt = score_area(cells, d, alt_p, level)
                pairs = [(b.cell_id, b.fsi, a.fsi) for b, a in zip(base[d], alt) if b.fsi is not None and a.fsi is not None]
                if len(pairs) < 3:
                    continue
                rho.append(spearman([x[1] for x in pairs], [x[2] for x in pairs]))
                ov.append(overlap(top_set({c: b for c, b, _ in pairs}), top_set({c: a for c, _, a in pairs})))
                dabs.append(float(np.mean([abs(b - a) for _, b, a in pairs])))
            out.append({"weight": k, "factor": f, "spearman": _mean(rho), "top20_overlap": _mean(ov), "mean_abs_change": _mean(dabs),
                        "dates": len(dabs)})
    return out


def chlorophyll_dependence(history: Mapping[date, list[CellInputs]], p: FsiParams, level: str = "trial") -> dict:
    """What the demo looks like today: the same dates scored with chlorophyll removed from every cell."""
    stripped = {d: [replace(c, chl_mg_m3=None, chl_observed_at=None, chl_product=None) for c in cells] for d, cells in history.items()}
    rho, ov, shift = [], [], []
    for d, cells in history.items():
        a, b = score_area(cells, d, p, level), score_area(stripped[d], d, p, level)
        pairs = [(x.cell_id, x.fsi, y.fsi) for x, y in zip(a, b) if x.fsi is not None and y.fsi is not None]
        have = [c for c in cells if c.chl_mg_m3 is not None]
        if len(pairs) < 3 or not have:
            continue
        rho.append(spearman([x[1] for x in pairs], [x[2] for x in pairs]))
        ov.append(overlap(top_set({c: x for c, x, _ in pairs}), top_set({c: y for c, _, y in pairs})))
        shift.append(float(np.mean([y - x for _, x, y in pairs])))
    return {"dates": len(rho), "spearman": _mean(rho), "top20_overlap": _mean(ov), "mean_fsi_shift": _mean(shift)}


# ---------------------------------------------------------------------------------------------------------------------
# 5. stability between dates
# ---------------------------------------------------------------------------------------------------------------------
def stability(scored: Mapping[date, list[CellScore]]) -> list[dict]:
    """Pairs of neighbouring dates in the sample (the gap in days is reported: with a weekly sample this is NOT day-to-day).
    High stability means smooth maps, not correct maps: a constant would score perfectly."""
    ds = sorted(scored)
    rows = []
    for a, b in zip(ds, ds[1:]):
        va = {s.cell_id: s.fsi for s in scored[a] if s.fsi is not None}
        vb = {s.cell_id: s.fsi for s in scored[b] if s.fsi is not None}
        common = sorted(set(va) & set(vb))
        if len(common) < 3:
            continue
        rows.append({"from": a, "to": b, "gap_days": (b - a).days, "cells": len(common),
                     "spearman": spearman([va[c] for c in common], [vb[c] for c in common]),
                     "top20_overlap": overlap(top_set({c: va[c] for c in common}), top_set({c: vb[c] for c in common})),
                     "mean_abs_change": float(np.mean([abs(va[c] - vb[c]) for c in common]))})
    return rows


# ---------------------------------------------------------------------------------------------------------------------
# 6. hit rate (A9 definition) -- needs catch logs; only SYNTHETIC data exists
# ---------------------------------------------------------------------------------------------------------------------
def hit_rate(trips: Sequence[Mapping], fsi_by_date: Mapping[date, Mapping[int, float | None]], top_fraction: float = 0.2,
             min_trips_per_fisher_season: int = 3) -> dict:
    """A9: hit rate = share of trips with a GOOD catch (above that fisher's own median in the same season) that happened in
    cells in the top 20% of FSI that day. A trip is {fisher, season, date, cell_id, catch_kg}. Trips whose cell had no score on
    that date, and fishers with fewer than `min_trips_per_fisher_season` trips in a season, are counted and left out.
    `lift` divides by `top_fraction`, the share a map with no skill would reach; a hit rate near that share means no skill."""
    groups: dict[tuple, list[Mapping]] = defaultdict(list)
    for t in trips:
        groups[(t["fisher"], t["season"])].append(t)
    good, hits, unscored, short = 0, 0, 0, 0
    for (_f, _s), ts in groups.items():
        if len(ts) < min_trips_per_fisher_season:
            short += len(ts)
            continue
        med = statistics.median(t["catch_kg"] for t in ts)
        for t in ts:
            if t["catch_kg"] <= med:
                continue                                      # not a good catch: strictly above the median only
            day = {c: v for c, v in fsi_by_date.get(t["date"], {}).items() if v is not None}
            if t["cell_id"] not in day:
                unscored += 1
                continue
            good += 1
            hits += t["cell_id"] in top_set(day, top_fraction)
    return {"good_trips": good, "hits": hits, "hit_rate": (hits / good) if good else None,
            "lift": (hits / good / top_fraction) if good else None, "left_out_unscored": unscored,
            "left_out_too_few_trips": short, "top_fraction": top_fraction}

"""Render the back-test result as Markdown. Aggregates only: no raw upstream values and no per-cell rows are written."""
from __future__ import annotations

from datetime import date

from . import checks


def _p(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def render(area_id: str, model_version: str, config_sha: str, dates: list[date], stats: dict, cov: dict, mono: list[dict],
           dist: dict, drivers: dict, sens: list[dict], chl_dep: dict, stab: list[dict], measured_on: str, commit: str) -> str:
    L = [f"# FSI v1 back-test: coverage and sanity checks ({area_id})", "",
         f"> **{checks.NOT_ACCURACY}**", "",
         f"MEASURED {measured_on} at commit `{commit}`, model `{model_version}`, config_sha256 `{config_sha[:16]}`. Every weight and "
         "target is an untuned demo value. Only NOAA ERDDAP sources were used (SST `jplMURSST41`, chlorophyll VIIRS with the NOAA-20 "
         "fallback, depth ETOPO). Global Fishing Watch was not used (no token). Open-Meteo is not part of FSI.", "",
         "## 1. What was run", "",
         f"- Dates scored: **{len(dates)}** ({min(dates)} to {max(dates)}); from cache {stats['from_cache']}, fetched now {stats['fetched']}, "
         f"requests this run {stats['requests']}, stopped by the request cap: {stats['stopped_by_cap']}.",
         f"- Dates where a source returned nothing usable: {len(stats['failed'])} " +
         (", ".join(f"{d} {v}" for d, v in sorted(stats['failed'].items())) if stats["failed"] else "(none)"), ""]
    m = cov["mean"]
    L += ["## 2. Coverage", "", "Share of the area's cells, averaged over dates.", "",
          "| Input or outcome | Mean share of cells |", "| --- | --- |"]
    for k, label in (("sst", "SST present"), ("chl", "Chlorophyll present"), ("depth", "Depth present (ETOPO water proxy)"),
                     ("scored", "Cell has an FSI"), ("medium", "confidence medium"), ("low", "confidence low"), ("high", "confidence high")):
        L.append(f"| {label} | {_pct(m[k])} |")
    L += ["", f"Dates with no scored cell at all: {len(cov['dates_with_no_scored_cell'])}.", "",
          "Reason codes seen (counted over every cell and date): " + ", ".join(f"`{k}` {v}" for k, v in sorted(cov["reasons"].items())), ""]
    L += ["## 3. Direction of response (does the formula move the right way?)", "", "| Check | Expected | Result |", "| --- | --- | --- |"]
    for r in mono:
        L.append(f"| {r['check']} | {r['direction']} | {'pass' if r['ok'] else '**FAIL**'} |")
    L += ["", "## 4. Spread of the score", ""]
    if dist.get("n"):
        q = dist["quantiles"]
        L += [f"- Cells scored (all dates): {dist['n']}. FSI min {q['min']:.1f}, p10 {q['p10']:.1f}, median {q['median']:.1f}, "
              f"p90 {q['p90']:.1f}, max {q['max']:.1f}.",
              f"- Mean spread inside one date (max minus min): {_p(dist['mean_within_date_range'], 1)} points.",
              f"- Histogram, 10 bins of 10 points from 0: {dist['hist_10_bins_0_100']}.",
              f"- Share at exactly 0 or 100: {_pct(dist['share_at_floor_or_ceiling'])}.", ""]
    L += ["What can change which cell is better than another on one date (mean standard deviation of each input's contribution "
          "across cells, in FSI points; 0 means that input cannot reorder the cells that day):", "",
          "| Input | Mean spread (points) |", "| --- | --- |"]
    for k, v in drivers.items():
        L.append(f"| {k}{' (placeholder)' if k in ('moon', 'season') else ''} | {_p(v, 2)} |")
    L += ["", "## 5. Sensitivity to each weight", "",
          "One weight at a time is multiplied by the factor (0 = that input is switched off). Compared with the baseline on the same "
          "dates: Spearman rank correlation of the cells, share of the baseline top 20% that stays in the top 20%, and the mean "
          "absolute change in FSI points. Moon and season are placeholders; their rows show how much of today's output rests on them.", "",
          "| Weight | Factor | Spearman | Top-20% kept | Mean abs change |", "| --- | --- | --- | --- | --- |"]
    for r in sens:
        L.append(f"| {r['weight']} | x{r['factor']} | {_p(r['spearman'])} | {_pct(r['top20_overlap'])} | {_p(r['mean_abs_change'], 2)} |")
    L += ["", "## 6. The demo's situation: chlorophyll removed", "",
          f"Same dates scored again with every chlorophyll value removed (dates compared: {chl_dep['dates']}): Spearman "
          f"{_p(chl_dep['spearman'])}, top 20% kept {_pct(chl_dep['top20_overlap'])}, mean FSI shift {_p(chl_dep['mean_fsi_shift'], 2)} points.", ""]
    L += ["## 7. Stability between sampled dates", "",
          "Neighbouring dates in the sample. The gap column matters: a weekly sample is **not** day-to-day. High stability means smooth "
          "maps, not correct maps (a constant map would score perfectly).", ""]
    if stab:
        gaps = sorted({r["gap_days"] for r in stab})
        L += [f"- Pairs: {len(stab)}; gaps in days: {gaps}.",
              f"- Mean Spearman {_p(checks._mean(r['spearman'] for r in stab))}, mean top-20% kept "
              f"{_pct(checks._mean(r['top20_overlap'] for r in stab))}, mean absolute change {_p(checks._mean(r['mean_abs_change'] for r in stab), 2)} points.", ""]
        by_gap: dict[int, list[dict]] = {}
        for r in stab:
            by_gap.setdefault(r["gap_days"], []).append(r)
        L += ["| Gap (days) | Pairs | Mean Spearman | Mean top-20% kept |", "| --- | --- | --- | --- |"]
        for g in sorted(by_gap):
            rs = by_gap[g]
            L.append(f"| {g} | {len(rs)} | {_p(checks._mean(r['spearman'] for r in rs))} | {_pct(checks._mean(r['top20_overlap'] for r in rs))} |")
        L.append("")
    L += ["## 8. What this does not show", "",
          "- Whether FSI predicts where fish are. Hit rate (A9) cannot be measured without catch logs or fishing-activity data; "
          "`backtest.checks.hit_rate` is implemented from the A9 definition and was exercised only on SYNTHETIC data.",
          "- Anything about small boats (Global Fishing Watch, if it is ever used, sees mostly large vessels).",
          "- The land mask, EEZ and legal layers: not built, so some scored cells are land or partly land.",
          "- Waves and wind (sea state is a separate filter, not part of FSI).", ""]
    return "\n".join(L)

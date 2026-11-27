"""AI-1: FSI front check (F-16) and week-to-week stability variants (open question 13), one report.

    python -m backtest.fsi_checks --area th-chonburi-coast --history-cache <old back-test cache> --daily-cache <new folder>
        --end 2026-11-25 --count 52 --field-date 2026-11-26 --max-requests 80 --out backend/docs/fsi-front-and-stability.md

Both cache folders must be outside the repository. History is read from the cache only (no request); live requests are the one real
field for F-16 (2) and the daily SST of the windows for variant (c) (2 per day), through the ingest fetcher, at most --max-requests,
2 s apart. Never writes to a database and never changes the default weights.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

from fsi.config import FsiParams
from ingest.config import ConfigError, load_area

from . import front_check, inputs, variants
from .inputs import PoliteHttp, RequestCap

VARIANTS = (("a", "today's weights", None, None), ("b1", "front weight x0.5 (0.10)", 0.5, None), ("b2", "front weight x0.25 (0.05)", 0.25, None))
REFERENCES = (("ref-front-off", "reference: front weight 0", 0.0, None), ("ref-sst-only", "reference: SST only", None, ("sst",)),
              ("ref-front-only", "reference: SST (gate) + front only", None, ("sst", "front")))


def _fmt(s: dict) -> str:
    f = lambda v, nd=3: "n/a" if v is None else f"{v:.{nd}f}"
    se = lambda v: "" if v is None else f" ± {v:.3f}"
    return (f"{s['pairs']} | {f(s['spearman'])}{se(s['spearman_se'])} | {100 * s['top20_kept']:.0f}%{'' if s['top20_kept_se'] is None else f' ± {100 * s['top20_kept_se']:.0f}'} | "
            f"{f(s['mean_abs_change'], 2)}") if s["pairs"] else "0 | n/a | n/a | n/a"


def table(rows: list[tuple[str, dict]]) -> list[str]:
    L = ["| Variant | Pairs | Mean Spearman ± se | Top 20% kept ± se (random: 20%) | Mean abs change (FSI points) |", "| --- | --- | --- | --- | --- |"]
    L += [f"| {name} | {_fmt(s)} |" for name, s in rows]
    return L


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="backtest.fsi_checks")
    ap.add_argument("--area", required=True)
    ap.add_argument("--history-cache", required=True)
    ap.add_argument("--daily-cache", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--count", type=int, default=52)
    ap.add_argument("--field-date", required=True)
    ap.add_argument("--pairs", type=int, default=6)
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("--max-requests", type=int, default=80)
    ap.add_argument("--pause-s", type=float, default=2.0)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        area = load_area(a.area)
        p = FsiParams.from_area(area)
        hist_dir, daily_dir = inputs.check_cache_dir(Path(a.history_cache)), inputs.check_cache_dir(Path(a.daily_cache))
        end, field_date = date.fromisoformat(a.end), date.fromisoformat(a.field_date)
        if not 1 <= a.window <= 7 or not 1 <= a.pairs <= 12 or not 0 <= a.max_requests <= 250:
            raise ValueError("--window 1..7, --pairs 1..12, --max-requests 0..250")
    except (ConfigError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    log = lambda m: print(m, flush=True)
    http: PoliteHttp | None = None

    # ---- history from the old cache: no request ----
    history, stats = inputs.load_history(area, inputs.weekly_dates(end, a.count), hist_dir, None, log=log)
    dates = sorted(history)
    pairs_all, pairs7 = list(zip(dates, dates[1:])), variants.week_pairs(dates)
    log(f"history: {len(dates)} dates from the cache; neighbour pairs {len(pairs_all)}, 7-day pairs {len(pairs7)}")

    # ---- F-16: one real field ----
    cache = daily_dir / area.area_id
    cache.mkdir(parents=True, exist_ok=True)
    npz = cache / f"field-{field_date}.npz"
    if npz.exists():
        z = np.load(npz)
        lats, lons, field = z["lats"], z["lons"], z["field"]
        observed, rows_equal = datetime.fromisoformat(str(z["observed"])), None
        n_req = 0
    elif a.offline:
        print("no cached field and --offline", file=sys.stderr)
        return 1
    else:
        rows, observed, (lats, lons, field), http = front_check.fetch_field(area, field_date, None, a.pause_s, a.max_requests)
        np.savez_compressed(npz, lats=lats, lons=lons, field=field, observed=np.array(observed.isoformat()))
        n_req = http.count
        rows_equal = None
    st = front_check.analyse_field(lats, lons, field, set(area.cell_ids()), area.bbox, area.ingest["min_valid_fraction"]["sst"])
    front_md = front_check.render(st, field_date, observed, n_req, rows_equal)

    # ---- Q13 (a)(b) on every cached date ----
    sc = {}
    for key, label, ff, only in VARIANTS + REFERENCES:
        pv = variants.weights_variant(p, ff, only)
        sc[key] = (label, variants.score_variant(history, pv), variants.score_variant(variants.strip_chlorophyll(history), pv))
    def rows_for(pairs, which):
        return [(sc[k][0], variants.summarise(variants.pair_metrics(sc[k][which], pairs))) for k, *_ in VARIANTS + REFERENCES]
    full = {"all": rows_for(pairs_all, 1), "w7": rows_for(pairs7, 1), "all_nochl": rows_for(pairs_all, 2), "w7_nochl": rows_for(pairs7, 2)}

    # ---- Q13 (c): front smoothed over `window` days, on a subset of 7-day pairs, windows never overlapping ----
    sub = variants.spread_pairs(pairs7, a.pairs)
    daily_info, smoothed, skipped = {}, {}, []
    try:
        for d1, d2 in sub:
            variants.check_no_overlap(d1, d2, a.window)
            for d in (d1, d2):
                days = variants.window_days(d, a.window)
                g_own = {c.cell_id: c.sst_grad_c_per_km for c in history[d]}
                glist = []
                for day in days[:-1]:
                    if day in daily_info:
                        glist.append(daily_info[day][0]); continue
                    g, obs, http = variants.fetch_sst_day(area, day, daily_dir, None if a.offline else http, log)
                    if g is None:
                        skipped.append(day); continue
                    daily_info[day] = (g, obs)
                    glist.append(g)
                smoothed[d] = variants.smooth_front(history[d], glist + [g_own])
    except RequestCap:
        log("request cap reached; variant (c) uses the pairs completed so far")
    done = [(d1, d2) for d1, d2 in sub if d1 in smoothed and d2 in smoothed]
    hist_sub = {d: history[d] for pair in done for d in pair}
    sm_hist = {d: smoothed[d] for d in hist_sub}
    subset_rows = {}
    for tag, hh in (("chl as ingested", hist_sub), ("chlorophyll removed", variants.strip_chlorophyll(hist_sub))):
        r = [(sc[k][0], variants.summarise(variants.pair_metrics(variants.score_variant(hh, variants.weights_variant(p, ff, only)), done)))
             for k, _l, ff, only in VARIANTS]
        smh = sm_hist if tag == "chl as ingested" else variants.strip_chlorophyll(sm_hist)
        r.append((f"(c) front = mean of the last {a.window} days, today's weights",
                  variants.summarise(variants.pair_metrics(variants.score_variant(smh, p), done))))
        subset_rows[tag] = r
    def distinct(x):
        obs = [daily_info[d][1] for d in variants.window_days(x, a.window)[:-1] if d in daily_info]
        return len(set(obs)) == len(obs)
    distinct_ok = all(distinct(x) for x in smoothed)
    own = {d: {c.cell_id: c.sst_grad_c_per_km for c in history[d]} for d in dates}
    lag1 = []
    for d in smoothed:
        series = [daily_info[x][0] for x in variants.window_days(d, a.window)[:-1] if x in daily_info] + [own[d]]
        lag1 += [variants.gradient_spearman(u, v) for u, v in zip(series, series[1:])]
    lag7 = [variants.gradient_spearman(own[x], own[y]) for x, y in pairs7]
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).resolve().parent).stdout.strip() or "unknown"

    L = [f"MEASURED {datetime.now(timezone.utc):%Y-%m-%d} at commit `{commit}`, model `{p.model_version}`, config_sha256 `{p.config_sha256[:16]}`. History: {len(dates)} weekly dates from the earlier back-test cache "
         f"({dates[0]} to {dates[-1]}); {len(pairs_all)} neighbour pairs (gaps 7 and 14 days), {len(pairs7)} pairs exactly 7 days apart.", "",
         "## A. F-16: the SST temperature-front input on one real field", "", front_md, "",
         "## B. Open question 13: week-to-week agreement under three treatments of the front", "",
         "Metrics as in REVIEW-004: Spearman rank correlation of the cells' FSI between two dates, and the share of the first date's top 20% cells that is still in the second date's top 20%. "
         "A map with no skill keeps 20%. `± se` is the standard error across pairs (dates are not independent, so it is optimistic). Default weights in the config are unchanged; variants are copies inside the harness.", "",
         "### B1. All cached dates, chlorophyll as ingested", "", "All neighbouring pairs (control: variant (a) must reproduce REVIEW-004: Spearman 0.190, top 20% kept 25%):", ""] + table(full["all"]) + \
        ["", "Pairs exactly 7 days apart:", ""] + table(full["w7"]) + \
        ["", "### B2. Same, chlorophyll removed from every cell (the chlorophyll-empty case, open question 12)", "", "All neighbouring pairs:", ""] + table(full["all_nochl"]) + \
        ["", "Pairs exactly 7 days apart:", ""] + table(full["w7_nochl"]) + \
        ["", f"### B3. Front smoothed over {a.window} days (variant c), on {len(done)} pairs 7 days apart", "",
         f"Daily SST was fetched for the {a.window - 1} days before each date (window = the date and the {a.window - 1} days before it; the two windows of a pair never share a day: checked by `check_no_overlap`). "
         f"Pairs used: {', '.join(f'{x}→{y}' for x, y in done)}. Days that could not be fetched: {len(skipped)}. Live requests this run: {0 if http is None else http.count}. "
         f"Observation times inside every window distinct: {distinct_ok}.", ""]
    for tag, r in subset_rows.items():
        L += [f"Chlorophyll: {tag}.", ""] + table(r) + [""]
    L += ["### B4. How long the front itself persists", "",
          "Spearman between the cell gradient maps themselves (not the FSI), over the cells that have a gradient on both days: "
          f"one day apart (inside the windows above) mean {variants.mean_defined(lag1):.3f} over {len(lag1)} pairs; "
          f"seven days apart (all 7-day pairs) mean {variants.mean_defined(lag7):.3f} over {len(lag7)} pairs.", ""]
    open_text = "\n".join(L)
    if a.out:
        Path(a.out).write_text(open_text + "\n", encoding="utf-8")
        print(f"written {a.out}")
    else:
        print(open_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

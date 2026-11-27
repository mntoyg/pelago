# FSI front check (F-16) and week-to-week stability (open question 13)

> **Numbers only. This is NOT evidence of accuracy.** Nothing here shows that a high FSI cell has more fish, or that one weighting
> is better than another. A calm map is not a correct map: a constant map would score perfectly on every stability metric below.
> The default weights in `th-chonburi-coast.json` are unchanged; the variants are copies inside the harness. The owner decides.

Task AI-1 (Pelago AIE 01), branch `feature/fsi-checks`. Live requests to NOAA ERDDAP: 72 in total (2 for a first look at the field, then 70 in the
run below: 2 for the field and 68 for the daily SST of the smoothing windows), 2 s apart, the ingest fetcher's generic User-Agent, cache outside
the repository, no file downloads, nothing raw committed. Chlorophyll and the 41 weekly dates came from the earlier back-test cache (no new request).

## What each result shows and does not show

| Result | It shows | It does NOT show |
| --- | --- | --- |
| A. One real field, gradient statistics | the gradient code matches an independent calculation (largest relative difference 7e-7 at 25 pixels), puts no gradient on the array edge, does not pile up near missing (land) pixels, and is not dominated by pixel-scale noise (the 3-pixel baseline gives 0.86 of the 1-pixel mean, pixel-map Spearman 0.93) | that the gradient is an oceanographic front. MUR is an analysis product (interpolated and blended), so a 1 km gradient is not an observation. One date (a November field whose SST ranges only 29.6 to 30.7 degC), one area |
| A. Size of the signal | on this date the strongest pixel gradient is 0.12 degC per km and the median 0.022 (0.22 degC per 10 km). `S_front` is a **percentile within the area**, so these small differences still spread cells from 0 to 1 and the front keeps its full weight 0.20 | whether such a gradient matters to fish or fishers; whether other seasons look the same (only this one field was examined pixel by pixel) |
| B1/B2. Weights | lowering the front weight raises week-to-week Spearman steadily (0.19 at weight 0.20, 0.31 at 0.10, 0.42 at 0.05, 0.47 at 0) while the top 20% kept stays between 25% and 32% against 20% for a random map | which weight is better. A lower front weight lets SST, chlorophyll and depth decide, and "SST only" is also unstable (0.12), so stability alone says nothing about quality |
| B3. Front smoothed over 3 days | on 6 pairs, a 3-day mean changes agreement from 0.238 to 0.252 (standard error about 0.1): no visible effect | that smoothing could never help: only 6 pairs, one window length |
| B4. Persistence of the front itself | the cell gradient maps agree 0.56 (Spearman) one day apart and 0.03 seven days apart, so a mean over a few days cannot make the front last a week | why: it may be real transient structure, or analysis noise; these data cannot tell |
| B2. Chlorophyll removed | the chlorophyll-empty situation (open question 12) gives the same ordering of variants and slightly lower agreement (0.13 against 0.19 for today's weights); `confidence` medium needs fresh chlorophyll, so it cannot be reached there (rule tested in `tests/test_fsi_model.py`) | any change to the `fsi` code or the confidence rule: `backend/fsi/` is untouched in this task |

**Does the front look wrong?** As a calculation: no (it matches an independent method, and shows no edge or coastline artefact on this field). As an
input to the ranking: it is weak in absolute size on this date, relative by construction (percentile), and its map shares almost nothing with the
map of a week earlier (0.03), so it carries a fifth of the score while changing almost completely every week. That is a design property to decide
on (open question 13), not a defect of the code.

## Findings (none fixed here)

- **F-23 [Medium, design] A percentile front gives a weak gradient the same weight as a strong one.** Reproduced on the real field above: the area's
  strongest pixel gradient is 0.12 degC per km, and `S_front` still spans 0 to 1. Actor: any day with no real front. What would settle the physical
  question: the same check on more dates, or a comparison with another SST product. Not fixed (the owner decides the weights and the scoring rule).
- **F-24 [Low] A cell gradient can rest on few pixels.** `backend/ingest/fetchers/erddap_mur_sst.py` applies `min_valid_fraction` to the SST but not to the
  gradient (`block_mean(..., cells)`): on the real field 7 of 136 cells have a gradient from under half of their pixels (smallest share 0.28). Those
  cells are coastal; coastal cells are 7% of the top 20% against 10% of all cells, so it does not drive the ranking. Not fixed.
- **F-25 [Low] `fetch_field` relies on two private attributes of the fetcher** (`_http`, `_sleep`) to keep the fetcher's own (allowlisted) HTTP function
  while counting requests. The live run used `main` before `fix/backend-hygiene` (F-20) was merged; **UNVERIFIED** against that branch. What would settle
  it: rebase after that merge and re-run one live field.
- **Info:** the standard errors are optimistic (neighbouring dates are not independent); `smooth_front` uses the date itself plus the previous days, never
  later days; the 41 weekly dates are the earlier back-test's 41 of 52 (11 never fetched).

## Reproduce

```
cd backend
python -m backtest.fsi_checks --area th-chonburi-coast --history-cache <earlier back-test cache> --daily-cache <new folder> --end 2026-11-25 --count 52 --field-date 2026-11-26 --max-requests 80 --out report-body.md
python -m backtest.fsi_checks ...same arguments... --offline      # same tables from the caches, no request (folders must be OUTSIDE the repository)
python -m pytest -q                                              # 221 passed, 15 skipped (database tests) on this branch
```

The tables below are the output of that command (an `--offline` re-run of the live run: every table in A and B1 to B3 is identical to the live run's; only the commit, the request counts and the added section B4 differ).

---

MEASURED 2026-11-27 at commit `b2a07c5`, model `fsi-v1.0.0`, config_sha256 `46e87256a902eb47`. History: 41 weekly dates from the earlier back-test cache (2025-12-10 to 2026-11-25); 40 neighbour pairs (gaps 7 and 14 days), 30 pairs exactly 7 days apart.

## A. F-16: the SST temperature-front input on one real field

- Field: MUR `jplMURSST41`, observation `2026-11-24 09:00:00+00:00`, requested for local date 2026-11-26; 0 requests in total (time axis + one data request).
- Pixels: 105 x 55 = 5775 (0.01 degree); with an SST value: 67.4%.
- SST over the field: min 29.62, median 30.31, max 30.73 degC.
- Gradient (1 pixel, degC per km), n=3549: mean 0.0279, median 0.0224, p90 0.0547, p99 0.1007, max 0.1246 (median 0.22 degC and p99 1.01 degC per 10 km).
- Pixels with an SST value that have a gradient: 91.1%; array-edge pixels with a gradient: 0 (expected 0).
- Independent haversine recomputation at 25 random pixels: largest relative difference 7.22e-07.
- The module's s=1 baseline equals the ingest function: True.

Baseline test (is the 1-pixel gradient mostly pixel-scale noise?): over 2919 pixels the mean gradient is 0.0275 with a 1-pixel baseline and 0.0237 with a 3-pixel baseline (ratio 0.86); Spearman between the two pixel maps 0.93.

| Distance to the nearest pixel without SST (pixels) | Pixels with a gradient | Mean gradient | Median gradient |
| --- | --- | --- | --- |
| 1 | 45 | 0.028 | 0.0249 |
| 2 | 148 | 0.0283 | 0.0255 |
| 3-5 | 431 | 0.0294 | 0.026 |
| 6-10 | 661 | 0.0308 | 0.0248 |
| 11+ | 2264 | 0.0268 | 0.0204 |

Cells (200 in the area): 136 have an SST and a gradient; 13 of them contain at least one pixel without SST (coastal); 41 lie on the outer ring of the area. Cell gradient (mean of its valid pixels): median 0.0240, p90 0.0496, max 0.1013.
- Share of a cell's pixels that have a gradient: min 0.28, p10 0.92, median 1.00; cells whose gradient rests on under half of their pixels: 7.
- Top 20% of cells by gradient (28 cells): coastal 7% against 10% of all cells; outer-ring cells 10 of the top against 30% of all cells.
- Spearman between a cell's gradient and the share of its pixels that have a gradient: -0.05.

## B. Open question 13: week-to-week agreement under three treatments of the front

Metrics as in REVIEW-004: Spearman rank correlation of the cells' FSI between two dates, and the share of the first date's top 20% cells that is still in the second date's top 20%. A map with no skill keeps 20%. `± se` is the standard error across pairs (dates are not independent, so it is optimistic). Default weights in the config are unchanged; variants are copies inside the harness.

### B1. All cached dates, chlorophyll as ingested

All neighbouring pairs (control: variant (a) must reproduce REVIEW-004: Spearman 0.190, top 20% kept 25%):

| Variant | Pairs | Mean Spearman ± se | Top 20% kept ± se (random: 20%) | Mean abs change (FSI points) |
| --- | --- | --- | --- | --- |
| today's weights | 40 | 0.190 ± 0.040 | 25% ± 3 | 8.96 |
| front weight x0.5 (0.10) | 40 | 0.305 ± 0.038 | 26% ± 3 | 6.79 |
| front weight x0.25 (0.05) | 40 | 0.420 ± 0.035 | 28% ± 2 | 5.99 |
| reference: front weight 0 | 40 | 0.468 ± 0.032 | 32% ± 3 | 5.96 |
| reference: SST only | 40 | 0.118 ± 0.060 | 30% ± 4 | 8.18 |
| reference: SST (gate) + front only | 40 | 0.106 ± 0.038 | 28% ± 2 | 16.29 |

Pairs exactly 7 days apart:

| Variant | Pairs | Mean Spearman ± se | Top 20% kept ± se (random: 20%) | Mean abs change (FSI points) |
| --- | --- | --- | --- | --- |
| today's weights | 30 | 0.234 ± 0.043 | 27% ± 3 | 8.85 |
| front weight x0.5 (0.10) | 30 | 0.353 ± 0.038 | 28% ± 3 | 6.61 |
| front weight x0.25 (0.05) | 30 | 0.461 ± 0.033 | 28% ± 3 | 5.73 |
| reference: front weight 0 | 30 | 0.466 ± 0.034 | 31% ± 3 | 5.65 |
| reference: SST only | 30 | 0.092 ± 0.070 | 31% ± 4 | 8.60 |
| reference: SST (gate) + front only | 30 | 0.124 ± 0.045 | 27% ± 3 | 16.14 |

### B2. Same, chlorophyll removed from every cell (the chlorophyll-empty case, open question 12)

All neighbouring pairs:

| Variant | Pairs | Mean Spearman ± se | Top 20% kept ± se (random: 20%) | Mean abs change (FSI points) |
| --- | --- | --- | --- | --- |
| today's weights | 40 | 0.130 ± 0.037 | 24% ± 2 | 9.62 |
| front weight x0.5 (0.10) | 40 | 0.229 ± 0.034 | 24% ± 2 | 7.07 |
| front weight x0.25 (0.05) | 40 | 0.371 ± 0.031 | 25% ± 2 | 6.16 |
| reference: front weight 0 | 40 | 0.505 ± 0.032 | 36% ± 4 | 6.19 |
| reference: SST only | 40 | 0.118 ± 0.060 | 30% ± 4 | 8.18 |
| reference: SST (gate) + front only | 40 | 0.106 ± 0.038 | 28% ± 2 | 16.29 |

Pairs exactly 7 days apart:

| Variant | Pairs | Mean Spearman ± se | Top 20% kept ± se (random: 20%) | Mean abs change (FSI points) |
| --- | --- | --- | --- | --- |
| today's weights | 30 | 0.166 ± 0.043 | 26% ± 3 | 9.28 |
| front weight x0.5 (0.10) | 30 | 0.265 ± 0.041 | 26% ± 3 | 6.62 |
| front weight x0.25 (0.05) | 30 | 0.403 ± 0.038 | 26% ± 3 | 5.56 |
| reference: front weight 0 | 30 | 0.487 ± 0.038 | 36% ± 4 | 5.42 |
| reference: SST only | 30 | 0.092 ± 0.070 | 31% ± 4 | 8.60 |
| reference: SST (gate) + front only | 30 | 0.124 ± 0.045 | 27% ± 3 | 16.14 |

### B3. Front smoothed over 3 days (variant c), on 6 pairs 7 days apart

Daily SST was fetched for the 2 days before each date (window = the date and the 2 days before it; the two windows of a pair never share a day: checked by `check_no_overlap`). Pairs used: 2026-04-15→2026-04-22, 2026-05-27→2026-06-03, 2026-07-08→2026-07-15, 2026-08-12→2026-08-19, 2026-10-07→2026-10-14, 2026-11-18→2026-11-25. Days that could not be fetched: 0. Live requests this run: 0. Observation times inside every window distinct: True.

Chlorophyll: chl as ingested.

| Variant | Pairs | Mean Spearman ± se | Top 20% kept ± se (random: 20%) | Mean abs change (FSI points) |
| --- | --- | --- | --- | --- |
| today's weights | 6 | 0.238 ± 0.107 | 29% ± 9 | 8.28 |
| front weight x0.5 (0.10) | 6 | 0.356 ± 0.103 | 29% ± 9 | 5.74 |
| front weight x0.25 (0.05) | 6 | 0.477 ± 0.095 | 32% ± 6 | 4.61 |
| (c) front = mean of the last 3 days, today's weights | 6 | 0.252 ± 0.079 | 27% ± 8 | 8.12 |

Chlorophyll: chlorophyll removed.

| Variant | Pairs | Mean Spearman ± se | Top 20% kept ± se (random: 20%) | Mean abs change (FSI points) |
| --- | --- | --- | --- | --- |
| today's weights | 6 | 0.196 ± 0.097 | 26% ± 8 | 8.85 |
| front weight x0.5 (0.10) | 6 | 0.296 ± 0.090 | 27% ± 7 | 6.12 |
| front weight x0.25 (0.05) | 6 | 0.423 ± 0.097 | 29% ± 6 | 4.94 |
| (c) front = mean of the last 3 days, today's weights | 6 | 0.224 ± 0.074 | 30% ± 7 | 8.60 |

### B4. How long the front itself persists

Spearman between the cell gradient maps themselves (not the FSI), over the cells that have a gradient on both days: one day apart (inside the windows above) mean 0.556 over 24 pairs; seven days apart (all 7-day pairs) mean 0.032 over 30 pairs.



---

## Guard tests proven able to fail (mutation checks, MEASURED 2026-11-27)

Method as in `fsi-mutation-log.md`: saved copy of the file, SHA-256 (first 16 hex) before, edit, run `tests/test_front_check.py` and `tests/test_variants.py`, restore from the copy, hash after. `backtest.variants.__file__` printed as the file in this worktree. Control: 20 passed in 0.61s.

| Mutation | File | Hash before | Hash after | Failing tests | First failing test |
| --- | --- | --- | --- | --- | --- |
| V01 smoothing windows may overlap | `backtest/variants.py` | 550f1304e6d53728 | 550f1304e6d53728 | 1 | `test_windows_end_on_the_date_and_must_not_overlap` |
| V02 a day without a gradient counted as 0 | `backtest/variants.py` | 550f1304e6d53728 | 550f1304e6d53728 | 1 | `test_smoothing_is_the_mean_of_the_days_that_have_a_value_and_never_cou` |
| V03 variant changes the config weights in place | `backtest/variants.py` | 550f1304e6d53728 | 550f1304e6d53728 | 1 | `test_front_weight_variant_changes_only_the_front_weight_and_leaves_the` |
| V04 spread pairs lose the last pair | `backtest/variants.py` | 550f1304e6d53728 | 550f1304e6d53728 | 1 | `test_week_pairs_and_spread` |
| V05 gradient ignores cos(latitude) | `backtest/front_check.py` | 0b5b65bf7a335cce | 0b5b65bf7a335cce | 5 | `test_gradient_of_a_field_linear_in_latitude_is_the_slope_in_degrees_pe` |
| V06 independent check uses one distance for both directions | `backtest/front_check.py` | 0b5b65bf7a335cce | 0b5b65bf7a335cce | 3 | `test_independent_check_agrees_with_the_ingest_gradient_and_catches_a_w` |
| V07 array edge counted as missing | `backtest/front_check.py` | 0b5b65bf7a335cce | 0b5b65bf7a335cce | 1 | `test_distance_to_missing_is_chebyshev_and_the_array_edge_is_not_missin` |
| V08 field fetch has no request cap | `backtest/front_check.py` | 0b5b65bf7a335cce | 0b5b65bf7a335cce | 1 | `test_fetch_field_counts_requests_shares_the_counter_and_obeys_the_cap` |
| V09 field fetch ignores the shared counter | `backtest/front_check.py` | 0b5b65bf7a335cce | 0b5b65bf7a335cce | 1 | `test_fetch_field_counts_requests_shares_the_counter_and_obeys_the_cap` |
| V10 gradient Spearman counts missing cells | `backtest/variants.py` | 550f1304e6d53728 | 550f1304e6d53728 | 1 | `test_gradient_spearman_uses_only_cells_present_in_both` |
| V11 standard error without the square root of n | `backtest/variants.py` | 550f1304e6d53728 | 550f1304e6d53728 | 1 | `test_summary_reports_pairs_mean_standard_error_and_undefined_counts` |

Not mutated: the report text, the CLI argument checks, the 41-date history loader (reused unchanged from the earlier back-test).

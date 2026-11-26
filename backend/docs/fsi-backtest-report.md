# FSI v1 back-test: coverage and sanity checks (th-chonburi-coast)

> **NOT EVIDENCE OF ACCURACY: these checks describe how the formula behaves on satellite inputs. They cannot show that high FSI cells have more fish. That needs verified catch logs (A9) or fishing-activity data.**

MEASURED 2026-11-26 at commit `f70f884`, model `fsi-v1.0.0`, config_sha256 `46e87256a902eb47`. Every weight and target is an untuned demo value. Only NOAA ERDDAP sources were used (SST `jplMURSST41`, chlorophyll VIIRS with the NOAA-20 fallback, depth ETOPO). Global Fishing Watch was not used (no token). Open-Meteo is not part of FSI.


**How the data was obtained.** One live run on 2026-11-26 asked NOAA ERDDAP for up to 52 weekly dates ending 2026-11-25, in a spread
order, with the cap of 250 requests (all 250 were used; 40 dates fetched plus 1 from an earlier one-date probe). The cap stopped it before
2026-04-08, so 11 of the 52 dates were never fetched. One fetched date (2026-08-26) failed with `http_503`, was treated as a network
error and left out (it was not retried). This report was regenerated from the local cache (outside the repository) with `--offline`, so
"requests this run" below says 0. Re-running the live part needs a new request budget from the owner.

**Reading the numbers (MEASURED on the 41 dates; every statement is about the formula, none about fish).**

- The temperature front is the input that most reorders the cells (spread 7.3 points, section 4) and switching its weight off changes the
  ranking most (Spearman 0.36, section 5). It is also where most of the week-to-week change comes from (section 7: stability rises from
  0.19 to 0.47 without it). The front is a percentile of the MUR SST gradient; the ingest seat checked the gradient only against a synthetic
  field (REVIEW-003), so its physical meaning on real data is **not verified**. Treat the ranking as only as good as that input.
- Neighbouring weekly maps barely agree (mean Spearman 0.19, top-20% kept 25% against 20% for a random map). Whether spots should move that
  much from week to week is a product question; no daily sample was possible within the request budget.
- FSI is compressed: median 73.5, p10 61, p90 84, no cell below 32 or above 94. It is a score, not a probability.
- Moon and season (placeholders) change scores by 1.4 to 2.0 points inside one date only because cells differ in data freshness; with equal
  freshness they cannot reorder cells (tested). Switching season off changes scores by 3.3 points on average.
- Chlorophyll: with every chlorophyll value removed (the situation of the demo today) the ranking is 0.95 correlated with the full one and 89%
  of the top 20% stays. On these dates `confidence medium` needed a fresh chlorophyll value and was reached by 26% of cells; `high` by none
  (the area is `trial`).

## 1. What was run

- Dates scored: **41** (2025-12-10 to 2026-11-25); from cache 41, fetched now 0, requests this run 0, stopped by the request cap: False.
- Dates where a source returned nothing usable: 3 2026-07-01 {'sst': None, 'chl': 'no_recent_data'}, 2026-07-22 {'sst': None, 'chl': 'no_recent_data'}, 2026-08-05 {'sst': None, 'chl': 'no_recent_data'}

## 2. Coverage

Share of the area's cells, averaged over dates.

| Input or outcome | Mean share of cells |
| --- | --- |
| SST present | 68% |
| Chlorophyll present | 50% |
| Depth present (ETOPO water proxy) | 63% |
| Cell has an FSI | 68% |
| confidence medium | 26% |
| confidence low | 42% |
| confidence high | 0% |

Dates with no scored cell at all: 0.

Reason codes seen (counted over every cell and date): `chl_missing` 1643, `chl_stale` 1696, `depth_missing` 410, `front_missing` 410, `no_verified_catch_logs` 2128, `sst_missing` 2624

## 3. Direction of response (does the formula move the right way?)

| Check | Expected | Result |
| --- | --- | --- |
| S_sst rises up to the target temperature | up | pass |
| S_sst falls above the target temperature | down | pass |
| S_chl rises up to the target (log scale) | up | pass |
| S_chl falls from the target to the bloom threshold | down | pass |
| S_chl is zero above the bloom threshold | down | pass |
| S_depth rises from the shoreline to the working depth | up | pass |
| S_depth falls from the working depth to the cut-off | down | pass |
| S_moon falls as the moon gets brighter | down | pass |
| freshness a falls as data gets older | down | pass |
| FSI (whole cell) rises with SST below the target | up | pass |

## 4. Spread of the score

- Cells scored (all dates): 5576. FSI min 32.8, p10 61.2, median 73.5, p90 84.4, max 93.8.
- Mean spread inside one date (max minus min): 39.3 points.
- Histogram, 10 bins of 10 points from 0: [0, 0, 0, 5, 82, 365, 1581, 2145, 1349, 49].
- Share at exactly 0 or 100: 0%.

What can change which cell is better than another on one date (mean standard deviation of each input's contribution across cells, in FSI points; 0 means that input cannot reorder the cells that day):

| Input | Mean spread (points) |
| --- | --- |
| sst | 4.78 |
| front | 7.27 |
| chl | 4.65 |
| depth | 5.37 |
| moon (placeholder) | 1.99 |
| season (placeholder) | 1.40 |

## 5. Sensitivity to each weight

One weight at a time is multiplied by the factor (0 = that input is switched off). Compared with the baseline on the same dates: Spearman rank correlation of the cells, share of the baseline top 20% that stays in the top 20%, and the mean absolute change in FSI points. Moon and season are placeholders; their rows show how much of today's output rests on them.

| Weight | Factor | Spearman | Top-20% kept | Mean abs change |
| --- | --- | --- | --- | --- |
| sst | x0.5 | 0.995 | 96% | 2.15 |
| sst | x1.5 | 0.997 | 96% | 1.64 |
| front | x0.0 | 0.355 | 32% | 7.52 |
| front | x0.5 | 0.962 | 91% | 3.25 |
| front | x1.5 | 0.989 | 95% | 2.56 |
| chl | x0.0 | 0.956 | 89% | 2.40 |
| chl | x0.5 | 0.992 | 95% | 1.06 |
| chl | x1.5 | 0.994 | 96% | 0.86 |
| depth | x0.0 | 0.943 | 90% | 5.06 |
| depth | x0.5 | 0.988 | 97% | 2.28 |
| depth | x1.5 | 0.993 | 98% | 1.90 |
| moon | x0.0 | 0.996 | 98% | 2.70 |
| moon | x0.5 | 0.999 | 99% | 1.25 |
| moon | x1.5 | 0.999 | 99% | 1.10 |
| season | x0.0 | 0.991 | 93% | 3.33 |
| season | x0.5 | 0.998 | 98% | 1.54 |
| season | x1.5 | 0.999 | 99% | 1.35 |

## 6. The demo's situation: chlorophyll removed

Same dates scored again with every chlorophyll value removed (dates compared: 38): Spearman 0.953, top 20% kept 89%, mean FSI shift -1.83 points.

## 7. Stability between sampled dates

Neighbouring dates in the sample. The gap column matters: a weekly sample is **not** day-to-day. High stability means smooth maps, not correct maps (a constant map would score perfectly).

- Pairs: 40; gaps in days: [7, 14].
- Mean Spearman 0.190, mean top-20% kept 25%, mean absolute change 8.96 points.

| Gap (days) | Pairs | Mean Spearman | Mean top-20% kept |
| --- | --- | --- | --- |
| 7 | 30 | 0.234 | 27% |
| 14 | 10 | 0.056 | 20% |

Where the change comes from: the same neighbouring-date stability with one non-SST weight switched off at a time.

| Weight off | Pairs | Mean Spearman | Mean top-20% kept |
| --- | --- | --- | --- |
| none | 40 | 0.190 | 25% |
| front | 40 | 0.468 | 32% |
| chl | 40 | 0.130 | 24% |
| depth | 40 | 0.094 | 22% |
| moon | 40 | 0.195 | 25% |
| season | 40 | 0.194 | 23% |

## 8. What this does not show

- Whether FSI predicts where fish are. Hit rate (A9) cannot be measured without catch logs or fishing-activity data; `backtest.checks.hit_rate` is implemented from the A9 definition and was exercised only on SYNTHETIC data.
- Anything about small boats (Global Fishing Watch, if it is ever used, sees mostly large vessels).
- The land mask, EEZ and legal layers: not built, so some scored cells are land or partly land.
- Waves and wind (sea state is a separate filter, not part of FSI).

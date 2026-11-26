# Ingest dry run: what the public sources really return for `th-chonburi-coast`

**MEASURED on 2026-11-26** (about 14:30 to 15:00 Thai time) from this machine, before any fetcher code was written.
Bbox lon 100.7 to 101.2, lat 12.2 to 13.2. It has 200 cells of 0.05 degree (20 rows x 10 columns). Raw responses were
saved only in a scratch folder outside the repository and are not committed (they are upstream data; the numbers below
are what was measured from them). Requests were small (3 ERDDAP subsets of 0.2 to 1.1 MB, 2 Open-Meteo calls of 50
points), sent one at a time with 2 to 4 s pauses and the generic User-Agent `pelago-ingest-dryrun/0.1 (research prototype)`.

Terms used below. **Water cell**: a cell whose block mean of ETOPO `z` is below 0 (126 of 200). **Coastal water cell**: a
water cell that touches a land cell (8 neighbours) or contains a pixel with `z >= 0` (35 of 126). This is a proxy made
only for this measurement; the real land mask is a separate task. "Share" = cells with at least one valid value divided
by the cells of that class.

## 1. Datasets (server `https://coastwatch.pfeg.noaa.gov/erddap/griddap/`)

| Source | Dataset id | Variable | Axis order | Units | Spacing | Missing | Newest time on 2026-11-26 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SST | `jplMURSST41` | `analysed_sst` | `time, latitude, longitude` (latitude ascending) | degree_C | 0.01 degree | `NaN` in the CSV (33% of the bbox points, the land) | **2026-11-24T09:00:00Z** (2 days old; time axis is not evenly spaced) |
| Chlorophyll | `nesdisVHNchlaDaily` | `chlor_a` | `time, altitude, latitude, longitude`; **latitude is descending**, so a range must be written `(13.2):(12.2)` | mg m^-3 | 0.0375 degree (4 km) | `NaN` (clouds) | **2026-11-15T12:00:00Z** (11 days old); the bbox is all `NaN` on 11-13 and 11-15 and 11-14 is absent from the axis |
| Depth | `ETOPO_2022_v1_15s` | `z` (positive up, so depth = -z) | `latitude, longitude` (no time axis) | m | 15 arc-second = 0.004167 degree | no `NaN` in the bbox (0 of 28 800) | static grid |
| Waves | Open-Meteo Marine `/v1/marine` | `wave_height` hourly | JSON array per point | m | model grid about 0.083 degree (see section 3) | JSON `null` | forecast, hours up to +2 days |
| Wind | Open-Meteo Forecast `/v1/forecast` | `wind_speed_10m` hourly (`wind_speed_unit=kmh`) | JSON array per point | km/h | model grid about 0.1 degree or finer (section 3) | JSON `null` | forecast, hours up to +2 days |

Differences from the documents (nothing was guessed):

1. `nesdisVHNchlaDaily` exists, **has the altitude axis** (one value, 0.0), and is 4 km, not the 300 m of `ARCHITECTURE.md` A7.
   Its title says "Near Real-Time" and "2017 to 2026-11-02", but its time axis runs to 2026-11-15, so it lags by 11 days.
   The prototype's retry without the altitude axis is not needed for this dataset (it stays as a fallback in the fetcher).
2. The `ARCHITECTURE.md` A7 line "Sentinel-3 OLCI ... 300 m" is not what the prototype's dataset is (VIIRS S-NPP, 4 km).
3. ERDDAP time syntax: `time[(last-4):(last)]` returned only one row; the index form `time[last-4:1:last]` returned five.
   Value-based time requests must use timestamps that exist on the axis, so the fetcher reads the axis first.
4. Open-Meteo marine snaps a query point to the nearest **sea** model cell that has data, not to the nearest cell. A land
   point returns the values of a sea cell up to 28.6 km away, or all `null` (3 of the 50 probe points, all inland).
5. Open-Meteo does not return the forecast issue time, only the hourly series. `wx_issued_at` will therefore be the
   **retrieval time** (UTC) and the doc and the column comment must say so (UNVERIFIED that no issue time is available in
   another parameter).

Alternatives found by one ERDDAP search, newest time read once, nothing else compared: `nesdisVHNnoaa20chlaDaily` (NOAA-20
VIIRS, same layout, 4 km, newest **2026-11-16T12:00:00Z**), `nesdisVHNSQchlaDaily` (science quality, ends 2026-11-06, no use for
near-real-time), and gap-filled products (`nesdisVHNnoaaSNPPnoaa20NRTchlaGapfilledDaily`; interpolated, so not an observation, not
used). Licence text of the three ERDDAP datasets says free to use and redistribute, "not intended for legal use" (the same
words as the EEZ caveat in `ARCHITECTURE.md` A5).

## 2. Coverage of the 0.05 degree cells

Run: SST 2026-11-24 (newest), chlorophyll the last 10 axis times, depth static, wave/wind for the local date 2026-11-26
(window 04:00 to 14:00 Bangkok = 21:00Z of 11-25 to 07:00Z of 11-26, 11 hourly values).

| Variable | All 200 cells | Water cells (126) | Coastal water cells (35) | Note |
| --- | --- | --- | --- | --- |
| SST, at least 1 of 25 pixels | 147 (74%) | **126 (100%)** | **35 (100%)** | 21 cells whose mean `z` is above 0 also have a few SST pixels (partly sea) |
| SST, at least 20 of 25 pixels | 128 (64%) | 126 (100%) | 35 (100%) | so a rule "at least half of the pixels" loses no water cell |
| Depth (block mean of `z` below 0) | 126 (63%) | 126 (100%) | 35 (100%) | depth 0.2 to 40.9 m; land cells have no depth by definition |
| Chlorophyll, newest axis day 2026-11-15 | 0 | **0** | **0** | all `NaN` (clouds) |
| Chlorophyll, 2026-11-08 / 11-11 (best days) | 109 / 103 | 100 / 97 (79% / 77%) | 24 / 17 (69% / 49%) | other days 0 to 17% |
| Chlorophyll, any of the 10 days | 119 (60%) | 109 (87%) | 26 (74%) | newest valid value per cell is 11-12 for 22 cells, 11-11 for 85, 11-09 for 2, 11-08 for 10 |
| Wave height (50-point lattice, nearest point) | n/a | **126 (100%)** | **35 (100%)** | 47 of 50 lattice points have a complete window; 3 inland points are all `null` |
| Wind speed 10 m (50-point lattice, nearest point) | n/a | **126 (100%)** | **35 (100%)** | 50 of 50 points complete |

Consequences (these are findings for the owner, see the report):

* **Chlorophyll is the weak input.** On 2026-11-26 the newest chlorophyll in the bbox is 14 to 18 days old (11-08 to
  11-12), older than the `max` of 10 days in the starting limits of `backend/README.md` 3.2, so every cell is `expired`
  today unless the NOAA-20 dataset is used (newest 11-16, still 10 days old and empty over the bbox on a cloudy day is
  possible; not measured). The FSI then runs without `chl` (freshness weight 0), as designed.
* Risk **R5** (no near-shore wave/wind values) is **not confirmed for this bbox**: all 126 water cells and all 35 coastal water
  cells get a value from the nearest lattice point. The caveat is resolution, section 3.
* Observed wave maximum over the window was 0.26 to 0.54 m and wind maximum 14.8 to 32.2 km/h that day (one lattice point
  at or above the 30 km/h red threshold of the small boat class; `ingest` stores the numbers, it does not classify).

## 3. How Open-Meteo points map to cells (decision, for the ingest builder's design; change it in config)

Open-Meteo gives point forecasts. The model cells behind them are coarser than 0.05 degree: marine snapped lattice
points to model points a median 4.7 km (max 28.6 km, inland) away; for the 126 water cells the model point actually used
was a median 5.4 km and at most 10.6 km (waves) and 15.9 km (wind) from the cell centre.

* **Query lattice: 0.1 degree, centres at x.x5** (lat 12.25 to 13.15, lon 100.75 to 101.15), so **10 x 5 = 50 points per
  variable, 100 location-calls per run**, sent as one request per endpoint with 50 coordinates (well under the free
  tier of 10 000 calls per day). Each lattice point is the centre of a 2 x 2 block of cells.
* **Per point**: the maximum over the sea window of the area's local date (`timezone=GMT` is requested and the window is
  converted with `zoneinfo`, never a fixed offset, because the API's own `timezone` handling is a second place for a
  date bug, risk R7).
* **Per cell: nearest-neighbour**, not interpolation (nothing is invented between points; a maximum stays a maximum). The
  cell takes the value of the nearest lattice point whose whole window is non-null, if it is within `max_snap_km`
  (config, 15 km). If no such point exists the cell gets `NULL`, never 0.
* Honesty note: neighbouring cells therefore share one value, and the value describes a model cell of roughly 8 to 15 km.
  The API should not present the wave/wind of a cell as measured at that cell.

## 4. Decisions taken while writing the fetchers (all in config or documented in code)

* SST per cell: mean of the valid 0.01 degree pixels inside the cell, only if at least `min_valid_fraction` (0.5, untuned)
  of the 25 pixels are valid. The front input `sst_grad_c_per_km` is computed at ingest from the full-resolution
  field (central differences, km via the cosine of the latitude), block-averaged; the pipeline fetches a 2-pixel margin so edge
  cells have neighbours.
* Chlorophyll per cell: the newest day inside the look-back window (`max_age_days.chl.max`, 10 days before the run
  date) on which the cell has at least one valid pixel (a 0.05 degree cell always contains at least one 0.0375 degree pixel
  centre); `chl_observed_at` is that day's timestamp, `chl_product = 'daily'`.
* Depth per cell: minus the block mean of `z` when that mean is below 0, else `NULL` (land is not depth 0).
* `wx_issued_at` is the retrieval time (section 1, point 5).
* `run_date` is the area-local date; every observation timestamp is stored in UTC and the cut-off for "newest
  observation not after the run date" is the end of the local day expressed in UTC.

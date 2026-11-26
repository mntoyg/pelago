# Mask, pick and compute: mutation log

Seat: mask-and-pick (branch `feature/mask-and-pick`). Run on 2026-11-26 (Thai time) against the committed code (the commit that
adds the mask and the pick step; the code the log was run on is the code on the branch, apart from this file).

Method (`AGENTS.md` section 7 rule 5, standing rule 1): every mutation is applied to a COPY of `backend/` made for that mutation
(never to the repository), the owner file's sha256 is recorded before and after, the listed tests are run in the copy, and the
copy is thrown away. The unmutated copy was run first (all green) and the module files imported there were printed and are inside
the copy (`...\scratchpad\mut\baseline\masks\geo.py`, `...\legal.py`). After the whole run the repository files were
hashed again: unchanged (`originals unchanged: True`). Real PostGIS: `postgis/postgis:16-3.7` on 127.0.0.1 with a random password,
`PELAGO_REQUIRE_DB=1`. Evidence label: **MEASURED** on this branch.

Baseline in the unmutated copy: **129 passed** (the 3 unit files + the geometry and integration files). Whole suite on the branch: **349 passed** (216 before this work). M40 was run separately after the redirect guard was added.

| ID | File (sha256 before -> after, first 12) | What was removed | Result | First test that went red |
| --- | --- | --- | --- | --- |
| M01 | `masks/geo.py` (5525fcc41128 -> 5b7a4220f31d) | land guard: every centre is water | 3 failed, 25 passed in 28.96s | `test_land_cell_is_not_water_and_sea_cell_is` |
| M02 | `masks/geo.py` (5525fcc41128 -> f9aad0cbd34e) | EEZ 5 km buffer | 5 failed, 23 passed in 28.72s | `test_distance_to_a_border_4_8_km_is_refused_and_5_2_km_is_accepted` |
| M03 | `masks/geo.py` (5525fcc41128 -> de96df5d2231) | outside-the-waters check | 5 failed, 23 passed in 40.08s | `test_distance_to_a_border_4_8_km_is_refused_and_5_2_km_is_accepted` |
| M04 | `masks/geo.py` (5525fcc41128 -> 6bc5aae7376f) | coast-is-not-a-border rule (coast + hole exclusion) | 2 failed, 9 passed in 7.29s | `test_the_coast_is_not_a_border_even_inside_five_kilometres` |
| M05 | `masks/geo.py` (5525fcc41128 -> ec4923ef395d) | small-hole (island) exclusion | 1 failed, 10 passed in 7.52s | `test_a_small_hole_is_an_island_whose_edge_is_coast_and_whose_inside_is_not_water` |
| M06 | `masks/geo.py` (5525fcc41128 -> 1ed4fe3cbaa5) | coast tolerance | 1 failed, 10 passed in 7.25s | `test_the_coast_is_not_a_border_even_inside_five_kilometres` |
| M07 | `masks/geo.py` (5525fcc41128 -> 8084b25fd105) | gap between the two coastlines counts as inside | 1 failed, 10 passed in 7.63s | `test_the_coast_is_not_a_border_even_inside_five_kilometres` |
| M09 | `legal.py` (72bb1a3f3500 -> cda653024bc3) | unknown EEZ is not eligible (decide) | 3 failed, 115 passed in 22.82s | `test_eez_layer_not_loaded_means_unknown_and_no_spot` |
| M10 | `legal.py` (72bb1a3f3500 -> a58e04bf1e7f) | red sea is not eligible (decide) | 9 failed, 109 passed in 21.49s | `test_no_recommended_spot_is_ever_in_a_forbidden_or_unknown_cell` |
| M11 | `legal.py` (72bb1a3f3500 -> 604df13e3fab) | missing forecast is not eligible (decide) | 11 failed, 107 passed in 21.89s | `test_no_recommended_spot_is_ever_in_a_forbidden_or_unknown_cell` |
| M12 | `legal.py` (72bb1a3f3500 -> 2a8e1f94d61e) | unknown legal layers need the trial policy | 2 failed, 116 passed in 22.68s | `test_the_withhold_policy_recommends_nothing_while_legal_layers_are_incomplete` |
| M13 | `legal.py` (72bb1a3f3500 -> fa4b295614ee) | any forbidden flag blocks | 4 failed, 114 passed in 23.51s | `test_any_forbidden_flag_blocks_even_under_the_trial_policy[disputed_ok-disputed_area]` |
| M14 | `legal.py` (72bb1a3f3500 -> e36d6693900d) | land is not eligible (decide) | 9 failed, 109 passed in 25.43s | `test_no_recommended_spot_is_ever_in_a_forbidden_or_unknown_cell` |
| M15 | `legal.py` (72bb1a3f3500 -> 2987aa3aa3c9) | tri-state strictness | 6 failed, 95 passed in 0.55s | `test_flags_are_strictly_tri_state[1]` |
| M16 | `seastate.py` (515f1df63db5 -> 85922f55763f) | NaN/negative wave is missing, not calm | 3 failed, 115 passed in 39.23s | `test_missing_nan_negative_or_non_numeric_is_never_calm[nan-10]` |
| M17 | `seastate.py` (515f1df63db5 -> 4e57126d68da) | stale forecast | 1 failed, 100 passed in 0.83s | `test_stale_and_untimed_forecasts` |
| M18 | `seastate.py` (515f1df63db5 -> e3d9abebaf04) | missing forecast | 9 failed, 109 passed in 45.88s | `test_missing_nan_negative_or_non_numeric_is_never_calm[None-10]` |
| M19 | `pick/select.py` (553e8ebb1835 -> ee81edf047cf) | spacing guard | 5 failed, 113 passed in 43.50s | `test_spacing_exactly_at_just_below_and_just_above_the_limit` |
| M20 | `pick/select.py` (553e8ebb1835 -> ac442b0dd8d9) | great-circle spacing replaced by cell-index spacing | 5 failed, 113 passed in 35.63s | `test_spacing_exactly_at_just_below_and_just_above_the_limit` |
| M21 | `pick/select.py` (553e8ebb1835 -> dac0f17066f6) | at least becomes more than | 1 failed, 100 passed in 0.75s | `test_spacing_exactly_at_just_below_and_just_above_the_limit` |
| M22 | `pick/select.py` (553e8ebb1835 -> 895913117874) | at most 5 spots | 7 failed, 111 passed in 37.82s | `test_at_most_five_even_with_hundreds_of_spread_out_candidates` |
| M23 | `pick/select.py` (553e8ebb1835 -> 7b0f4d5ef1f5) | area-box guard | 5 failed, 113 passed in 36.70s | `test_invalid_or_out_of_bbox_candidates_are_dropped_and_counted_never_picked[bad10]` |
| M24 | `pick/select.py` (553e8ebb1835 -> 46e147b145dc) | NaN / infinity guard | 101 passed in 0.62s | `-` |
| M24b | `pick/select.py` (553e8ebb1835 -> 1d956e73d143) | NaN / infinity guard AND the FSI range check together | 4 failed, 97 passed in 0.66s | `test_invalid_or_out_of_bbox_candidates_are_dropped_and_counted_never_picked[bad2]` |
| M25 | `pick/db.py` (4e7872a31518 -> ff095c54e14a) | pick SQL: eligible only | 11 failed, 6 passed in 37.37s | `test_no_recommended_spot_is_ever_in_a_forbidden_or_unknown_cell` |
| M26 | `pick/db.py` (4e7872a31518 -> cdfac6c84e1f) | pick SQL: scored only | 7 failed, 10 passed in 37.85s | `test_no_recommended_spot_is_ever_in_a_forbidden_or_unknown_cell` |
| M27 | `pick/select.py` (553e8ebb1835 -> 89980ea16b55) | duplicate cell ids | 1 failed, 100 passed in 0.57s | `test_the_same_cell_id_twice_with_different_coordinates_is_picked_once` |
| M28 | `masks/db.py` (6c2b3df3dee0 -> a4a134e9ad85) | orchestrated mask run clears old picks | 1 failed, 16 passed in 35.37s | `test_a_mask_change_that_would_orphan_a_pick_fails_and_leaves_everything_as_it_was` |
| M29 | `masks/pipeline.py` (d3a68799e3b1 -> f700367e1614) | withhold policy | 1 failed, 16 passed in 38.35s | `test_the_withhold_policy_recommends_nothing_while_legal_layers_are_incomplete` |
| M30 | `masks/pipeline.py` (d3a68799e3b1 -> ba413acdca58) | recommendation_conflict handling | 1 failed, 16 passed in 36.46s | `test_a_mask_change_that_would_orphan_a_pick_fails_and_leaves_everything_as_it_was` |
| M31 | `masks/layers.py` (4b3125d42aa8 -> 942bbfaaec8f) | NaN / Infinity literals in layer files | 2 failed, 99 passed in 0.58s | `test_bad_layer_files_are_refused_with_a_short_code[nan literal-text1-not_json]` |
| M32 | `masks/layers.py` (4b3125d42aa8 -> 75b4608428af) | layer must overlap the area | 1 failed, 100 passed in 0.70s | `test_bad_layer_files_are_refused_with_a_short_code[far away-text8-no_overlap]` |
| M33 | `masks/layers.py` (4b3125d42aa8 -> 6ef50b0b716a) | symlinked layer file | 1 failed, 100 passed in 0.57s | `test_a_symlinked_layer_file_is_refused` |
| M34 | `masks/pipeline.py` (d3a68799e3b1 -> e6da525d6d9b) | EEZ needs land (coast vs border) | 1 failed, 16 passed in 40.19s | `test_land_layer_not_loaded_means_no_cell_is_known_to_be_water` |
| M35 | `masks/build_land.py` (f61272e019a1 -> fb17fe30b2fd) | shapefile length check | 1 failed, 100 passed in 0.72s | `test_corrupt_shapefiles_are_refused[<lambda>-header declares a different length than the file has]` |
| M36 | `masks/fetch_eez.py` (70189b9dcf41 -> d1f9a96018b5) | closed-ring check on fetched polygons | 1 failed, 100 passed in 0.64s | `test_bad_layer_files_are_refused_with_a_short_code[unclosed ring-text5-bad_geometry]` |
| M37 | `pick/pipeline.py` (f89ea7591236 -> d6256e8e582c) | fewer than 3 spots is reported partial | 6 failed, 11 passed in 38.86s | `test_a_huge_spacing_leaves_one_honest_spot_and_a_partial_run` |
| M38 | `compute/pipeline.py` (f90bce7bf93a -> d45e8725fc78) | orchestrator passes clear_picks | 1 failed, 16 passed in 35.18s | `test_a_mask_change_that_would_orphan_a_pick_fails_and_leaves_everything_as_it_was` |
| M39 | `compute/pipeline.py` (f90bce7bf93a -> 1dd2321b7805) | skipped rows after a failed step | 1 failed, 16 passed in 33.34s | `test_a_failed_mask_skips_the_later_steps_and_says_so` |
| M40 | `masks/fetch_eez.py` (b0359027a7c0 -> 86a7aee689aa) | no redirect is followed by the EEZ fetch | 1 failed, 101 passed in 0.64s | `test_the_fetch_never_follows_a_redirect_to_another_host` |

## Read this before trusting the table

* **M24 survived** (`101 passed`): removing only the `math.isfinite` check in `pick/select.py` changes nothing, because a NaN or
  infinity also fails the bbox comparison (lat/lon) or the `0 <= fsi <= 100` comparison. It is a redundant guard, not an untested
  one. **M24b** removes the `isfinite` check AND the FSI range check together: 4 tests go red (the NaN and infinite FSI cases).
* **M03 and the integration test.** Removing the outside-the-waters branch makes five geometry tests red, but the key integration
  test `test_no_recommended_spot_is_ever_in_a_forbidden_or_unknown_cell` stays green: the world's column 0 is only 2 km west of the
  border, so the 5 km buffer (M02) refuses it too. The two guards overlap on that cell; the geometry test with a cell about 5.4 km outside
  the border is the one that proves M03 on its own.
* **An earlier equivalent mutant was removed instead of tested:** the SQL branches `WHEN nat.geom IS NULL ... THEN NULL` and
  `CASE WHEN land.geom IS NULL` could never change a result (a NULL comparison is NULL anyway, and `evaluate()` does not run the SQL
  for a layer that is not loaded). They were deleted from `masks/geo.py`; no test was kept for dead code.
* Overlapping guards by design: `legal.decide` and the `cell_mask_daily` CHECK encode the same eligibility rule. With `decide`
  mutated (M09 to M14) the database CHECK refuses the row, the mask run fails with `write_failed`, and the tests go red because
  the run did not succeed; they do not prove that `decide` alone suffices, they prove that removing it is noticed.
* `M13` uses the unit tests for the proof (4 red); the database tests there stay green because no cell has a False flag in this
  slice (disputed, protected, closure and boat-zone are always NULL), which is the honest state of the data.
* Not mutated: `masks/db.py` SQL text other than `clear_picks`, `compute/run.py` argument handling (3 smoke tests only), the real
  Natural Earth / Marine Regions files (the real-layer run is in the report, not in the test suite).

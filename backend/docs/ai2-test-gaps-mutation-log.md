# AI-2: test gaps F-26 and F-27, mutation log

MEASURED 2026-11-27 on branch `feature/fsi-test-gaps` (base `1815713`). Tests only; no behaviour changed. `backtest.variants.__file__` and
`masks.geo.__file__` printed as files in this worktree. Method: saved copy, SHA-256 (first 16 hex) before, edit, run the listed tests (DB tests with
`PELAGO_REQUIRE_DB=1` on a throwaway `postgis/postgis:16-3.7` bound to 127.0.0.1 with a random password), restore from the copy, hash after.

Controls: `tests/test_variants.py` 11 passed in 0.88s; `tests/test_mask_geo_empty_border.py` 4 passed in 7.65s; `tests/test_mask_geo_db.py` 11 passed in 11.20s.

| Mutation | File | Tests run | Hash before | Hash after | Failing | First failing test |
| --- | --- | --- | --- | --- | --- | --- |
| W01 F-26: remove the 'fewer than 3 common cells' skip | `backtest/variants.py` | test_variants.py | 6c25ad4527ef8e0e | 6c25ad4527ef8e0e | 1 | `test_a_pair_with_fewer_than_three_common_cells_is_skipped_not_reported` |
| W02 F-26: skip threshold 3 -> 2 | `backtest/variants.py` | test_variants.py | 6c25ad4527ef8e0e | 6c25ad4527ef8e0e | 1 | `test_a_pair_with_fewer_than_three_common_cells_is_skipped_not_reported` |
| W03 F-27: empty border -> FALSE (flip) | `masks/geo.py` | test_mask_geo_empty_border.py | 5525fcc411284e74 | 5525fcc411284e74 | 2 | `test_waters_without_any_border_count_as_inside_the_eez` |
| W04 F-27: empty-border branch removed | `masks/geo.py` | test_mask_geo_empty_border.py | 5525fcc411284e74 | 5525fcc411284e74 | 0 | `none (green)` |
| W05 F-27 control: flip leaves the old mask DB tests green (the gap) | `masks/geo.py` | test_mask_geo_db.py | 5525fcc411284e74 | 5525fcc411284e74 | 0 | `none (green)` |

Reading: W01-W03 turn the new tests red. W05 reproduces the PM's observation (the old mask DB tests stay green under the flip).
**W04 stays green and is not a test gap:** removing the `WHEN ST_IsEmpty(border.geom) THEN TRUE` branch gives the same answer, because
`ST_DWithin(point, empty geography, d)` is false, so `ELSE NOT ST_DWithin(...)` is TRUE as well. The branch is redundant on PostGIS 3.7; the new
test guards the behaviour (empty border = inside), which is what matters if the branch or the ELSE changes. Not changed here (tests only).

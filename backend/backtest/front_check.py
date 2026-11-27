"""F-16: check the SST temperature-front input (the SST gradient) on ONE real MUR SST field.

The gradient is computed by the ingest (`ingest.aggregate.sst_gradient_c_per_km`) and was checked before only on a synthetic linear
field. Here the same function runs on a real field, and its numbers are compared with an independent calculation (haversine
distances), with a longer baseline (is the 1-pixel gradient mostly pixel-scale noise?), and by distance to the nearest missing pixel
(land, cloud): does the front pile up at the coast?

Numbers only. Nothing here says that a front is a place with fish.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np

from ingest import aggregate as agg
from ingest.fetchers import erddap, registry
from ingest.fetchers.erddap_mur_sst import build_rows

from .checks import spearman, top_set
from .inputs import PoliteHttp

DIST_BINS = ((1, 1), (2, 2), (3, 5), (6, 10), (11, 99))     # pixels to the nearest pixel without an SST value (Chebyshev)


def parse_field(body: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ERDDAP CSV of analysed_sst -> (lats ascending, lons ascending, field[lat, lon], NaN = no value). Same layout rules as the ingest."""
    recs = erddap.parse_csv(body, ("latitude", "longitude", "analysed_sst"))
    if not recs:
        raise ValueError("empty field")
    lat = np.array([float(r["latitude"]) for r in recs])
    lon = np.array([float(r["longitude"]) for r in recs])
    val = np.array([np.nan if (v := erddap.num(r["analysed_sst"])) is None else v for r in recs])
    lats, lons = np.unique(np.round(lat, 4)), np.unique(np.round(lon, 4))
    if lats.size * lons.size != val.size:
        raise ValueError("not a full rectangle")
    field = np.full((lats.size, lons.size), np.nan)
    field[np.searchsorted(lats, np.round(lat, 4)), np.searchsorted(lons, np.round(lon, 4))] = val
    return lats, lons, field


def gradient_baseline(lats, lons, field, s: int) -> np.ndarray:
    """Central-difference gradient magnitude (deg C per km) over +-s pixels. s = 1 is the ingest's own formula."""
    f = np.asarray(field, float)
    la, lo = np.asarray(lats, float), np.asarray(lons, float)
    out = np.full(f.shape, np.nan)
    if f.shape[0] < 2 * s + 1 or f.shape[1] < 2 * s + 1:
        return out
    dlat_km = abs(float(la[-1] - la[0])) / (la.size - 1) * agg.KM_PER_DEG
    dlon_deg = abs(float(lo[-1] - lo[0])) / (lo.size - 1)
    gy = (f[2 * s:, s:-s] - f[:-2 * s, s:-s]) / (2 * s * dlat_km)
    dlon_km = (dlon_deg * agg.KM_PER_DEG * np.cos(np.radians(la[s:-s])))[:, None]
    gx = (f[s:-s, 2 * s:] - f[s:-s, :-2 * s]) / (2 * s * dlon_km)
    mag = np.hypot(gx, gy)
    mag[~np.isfinite(mag)] = np.nan
    out[s:-s, s:-s] = mag
    return out


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def independent_check(lats, lons, field, grad, n: int = 25, seed: int = 0) -> dict:
    """Recompute the gradient at n pixels with haversine distances (a different way to get the kilometres) and compare."""
    ii, jj = np.where(np.isfinite(grad))
    if ii.size == 0:
        return {"checked": 0, "max_rel_diff": None}
    pick = np.random.default_rng(seed).choice(ii.size, size=min(n, ii.size), replace=False)
    worst = 0.0
    for k in pick:
        i, j = int(ii[k]), int(jj[k])
        dy = field[i + 1, j] - field[i - 1, j]
        dx = field[i, j + 1] - field[i, j - 1]
        ky = haversine_km(lats[i - 1], lons[j], lats[i + 1], lons[j])
        kx = haversine_km(lats[i], lons[j - 1], lats[i], lons[j + 1])
        ref = math.hypot(dx / kx, dy / ky)
        worst = max(worst, abs(ref - grad[i, j]) / max(ref, 1e-12))
    return {"checked": int(len(pick)), "max_rel_diff": float(worst)}


def distance_to_missing(valid: np.ndarray, cap: int = 12) -> np.ndarray:
    """Chebyshev distance in pixels from each valid pixel to the nearest pixel without a value (0 for a missing pixel). The array edge
    is not counted as missing. Values above `cap` are reported as cap + 1."""
    dist = np.where(valid, cap + 1, 0).astype(int)
    missing = ~valid
    grown = missing.copy()
    for d in range(1, cap + 1):
        p = np.pad(grown, 1, constant_values=False)
        grown = grown | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:] | p[:-2, :-2] | p[:-2, 2:] | p[2:, :-2] | p[2:, 2:]
        dist = np.where(valid & grown & (dist > d), d, dist)
    return dist


def _q(x: np.ndarray) -> dict:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"n": 0}
    p = np.quantile(x, [0, 0.5, 0.9, 0.99, 1])
    return {"n": int(x.size), "mean": float(x.mean()), "min": float(p[0]), "median": float(p[1]), "p90": float(p[2]),
            "p99": float(p[3]), "max": float(p[4])}


def analyse_field(lats, lons, field, cells: set[int], bbox: tuple, min_valid_fraction: float = 0.5) -> dict:
    """Everything the report prints, as plain numbers. `cells` are the area's cell ids, `bbox` = (lon0, lat0, lon1, lat1)."""
    valid = np.isfinite(field)
    g1 = agg.sst_gradient_c_per_km(lats, lons, field)
    g3 = gradient_baseline(lats, lons, field, 3)
    dist = distance_to_missing(valid)
    out: dict = {"shape": [int(len(lats)), int(len(lons))], "pixels": int(valid.size), "valid_sst_share": float(valid.mean()),
                 "sst": _q(field), "gradient_1px": _q(g1),
                 "gradient_valid_share_of_valid_sst": float(np.isfinite(g1).sum() / max(valid.sum(), 1))}
    out["gradient_per_10km_median_p99"] = [out["gradient_1px"].get("median", math.nan) * 10, out["gradient_1px"].get("p99", math.nan) * 10]
    # independent calculation and the ingest function against the one in this module with s = 1
    out["independent"] = independent_check(lats, lons, field, g1)
    out["same_as_s1_baseline"] = bool(np.allclose(np.nan_to_num(g1, nan=-1), np.nan_to_num(gradient_baseline(lats, lons, field, 1), nan=-1)))
    # outer ring of the array has no gradient by construction
    ring = np.zeros_like(valid)
    ring[0, :] = ring[-1, :] = ring[:, 0] = ring[:, -1] = True
    out["array_edge_pixels_with_gradient"] = int((np.isfinite(g1) & ring).sum())
    # baseline length: is the 1-pixel gradient mostly small-scale noise?
    both = np.isfinite(g1) & np.isfinite(g3)
    out["baseline"] = {"pixels": int(both.sum()), "mean_1px": float(g1[both].mean()) if both.any() else None,
                       "mean_3px": float(g3[both].mean()) if both.any() else None,
                       "ratio_3px_over_1px": float(g3[both].mean() / g1[both].mean()) if both.any() and g1[both].mean() > 0 else None,
                       "spearman_pixels": spearman(g1[both].tolist(), g3[both].tolist()) if both.sum() >= 3 else None}
    # behaviour by distance to the nearest missing pixel
    bins = []
    for lo, hi in DIST_BINS:
        m = np.isfinite(g1) & (dist >= lo) & (dist <= hi)
        bins.append({"from_px": lo, "to_px": hi if hi < 99 else None, "pixels": int(m.sum()),
                     "mean_gradient": float(g1[m].mean()) if m.any() else None, "median_gradient": float(np.median(g1[m])) if m.any() else None})
    out["by_distance_to_missing"] = bins
    # cell level, exactly as the ingest aggregates it
    la_g, lo_g = np.meshgrid(lats, lons, indexing="ij")
    flat = list(zip(la_g.ravel().tolist(), lo_g.ravel().tolist()))
    sst_c = agg.block_mean(((a, b, v) for (a, b), v in zip(flat, field.ravel().tolist())), cells, min_valid_fraction)
    sst_any = agg.block_mean(((a, b, v) for (a, b), v in zip(flat, field.ravel().tolist())), cells, 0.0)
    gr_c = agg.block_mean(((a, b, v) for (a, b), v in zip(flat, g1.ravel().tolist())), cells)
    rows = []
    lon0, lat0, lon1, lat1 = bbox
    for cid in sorted(cells):
        if cid not in sst_c or cid not in gr_c:
            continue
        clat, clon = (float(x) for x in agg.cell_centre(cid))
        n_valid_sst, n_tot = sst_any[cid][1], sst_any[cid][2]
        rows.append({"cell": cid, "grad": gr_c[cid][0], "grad_share": gr_c[cid][1] / gr_c[cid][2], "coastal": n_valid_sst < n_tot,
                     "edge": clon < lon0 + 0.05 or clon > lon1 - 0.05 or clat < lat0 + 0.05 or clat > lat1 - 0.05})
    out["cells"] = {"in_area": len(cells), "with_sst_and_gradient": len(rows)}
    if rows:
        shares = np.array([r["grad_share"] for r in rows])
        out["cells"].update({"coastal": int(sum(r["coastal"] for r in rows)), "edge_ring": int(sum(r["edge"] for r in rows)),
                             "gradient_from_under_half_of_pixels": int((shares < 0.5).sum()),
                             "gradient_share_quantiles": [float(x) for x in np.quantile(shares, [0, 0.1, 0.5, 1])],
                             "cell_gradient": _q(np.array([r["grad"] for r in rows]))})
        grads = {r["cell"]: r["grad"] for r in rows}
        top = top_set(grads, 0.2)
        co = [r for r in rows if r["coastal"]]
        out["top20"] = {"cells": len(top), "coastal_in_top": sum(r["cell"] in top and r["coastal"] for r in rows),
                        "coastal_share_of_cells": len(co) / len(rows),
                        "coastal_share_of_top": sum(r["cell"] in top and r["coastal"] for r in rows) / max(len(top), 1),
                        "edge_in_top": sum(r["cell"] in top and r["edge"] for r in rows),
                        "edge_share_of_cells": sum(r["edge"] for r in rows) / len(rows)}
        out["cell_gradient_vs_valid_pixel_share_spearman"] = spearman([r["grad"] for r in rows], [r["grad_share"] for r in rows])
    return out


def fetch_field(area, run_date: date, http: PoliteHttp | None = None, pause_s: float = 2.0, max_requests: int = 4):
    """Real MUR field for the area through the ingest fetcher (same URL, same checks): 2 requests (time axis + data).
    Returns (rows, observed_at, (lats, lons, field), http). The fetcher's own HTTP function is kept (it carries the host allowlist once
    that exists) and wrapped for counting and pacing; pass the returned `http` to the next call to share the count and the pause."""
    fetcher = registry.build("erddap_mur_sst", area)
    if http is None:
        http = PoliteHttp(inner=fetcher._http, max_requests=max_requests, pause_s=pause_s)
    bodies: list[bytes] = []

    def recording(url: str, timeout: float) -> bytes:
        b = http(url, timeout)
        bodies.append(b)
        return b
    fetcher._http, fetcher._sleep = recording, (lambda s: None)
    rows = fetcher.fetch(area, run_date)
    observed = next((r.observed_at for r in rows if r.observed_at is not None), None)
    return rows, observed, parse_field(bodies[-1]), http


def render(stats: dict, run_date: date, observed, requests: int, rows_gradient_equal: bool | None) -> str:
    g, s, c = stats["gradient_1px"], stats["sst"], stats["cells"]
    L = [f"- Field: MUR `jplMURSST41`, observation `{observed}`, requested for local date {run_date}; {requests} requests in total (time axis + one data request).",
         f"- Pixels: {stats['shape'][0]} x {stats['shape'][1]} = {stats['pixels']} (0.01 degree); with an SST value: {100 * stats['valid_sst_share']:.1f}%.",
         f"- SST over the field: min {s['min']:.2f}, median {s['median']:.2f}, max {s['max']:.2f} degC.",
         f"- Gradient (1 pixel, degC per km), n={g['n']}: mean {g['mean']:.4f}, median {g['median']:.4f}, p90 {g['p90']:.4f}, p99 {g['p99']:.4f}, max {g['max']:.4f} "
         f"(median {stats['gradient_per_10km_median_p99'][0]:.2f} degC and p99 {stats['gradient_per_10km_median_p99'][1]:.2f} degC per 10 km).",
         f"- Pixels with an SST value that have a gradient: {100 * stats['gradient_valid_share_of_valid_sst']:.1f}%; array-edge pixels with a gradient: {stats['array_edge_pixels_with_gradient']} (expected 0).",
         f"- Independent haversine recomputation at {stats['independent']['checked']} random pixels: largest relative difference {stats['independent']['max_rel_diff']:.2e}.",
         f"- The module's s=1 baseline equals the ingest function: {stats['same_as_s1_baseline']}."]
    if rows_gradient_equal is not None:
        L.append(f"- Cell gradients from the live fetcher equal the cell gradients rebuilt here: {rows_gradient_equal}.")
    b = stats["baseline"]
    L += ["", f"Baseline test (is the 1-pixel gradient mostly pixel-scale noise?): over {b['pixels']} pixels the mean gradient is {b['mean_1px']:.4f} with a 1-pixel baseline and "
          f"{b['mean_3px']:.4f} with a 3-pixel baseline (ratio {b['ratio_3px_over_1px']:.2f}); Spearman between the two pixel maps {b['spearman_pixels']:.2f}.", "",
          "| Distance to the nearest pixel without SST (pixels) | Pixels with a gradient | Mean gradient | Median gradient |", "| --- | --- | --- | --- |"]
    for r in stats["by_distance_to_missing"]:
        rng = f"{r['from_px']}" + ("" if r["to_px"] == r["from_px"] else f"-{r['to_px']}" if r["to_px"] else "+")
        L.append(f"| {rng} | {r['pixels']} | {r['mean_gradient'] if r['mean_gradient'] is None else round(r['mean_gradient'], 4)} | "
                 f"{r['median_gradient'] if r['median_gradient'] is None else round(r['median_gradient'], 4)} |")
    t = stats["top20"]
    cg = c["cell_gradient"]
    L += ["", f"Cells ({c['in_area']} in the area): {c['with_sst_and_gradient']} have an SST and a gradient; {c['coastal']} of them contain at least one pixel without SST (coastal); "
          f"{c['edge_ring']} lie on the outer ring of the area. Cell gradient (mean of its valid pixels): median {cg['median']:.4f}, p90 {cg['p90']:.4f}, max {cg['max']:.4f}.",
          f"- Share of a cell's pixels that have a gradient: min {c['gradient_share_quantiles'][0]:.2f}, p10 {c['gradient_share_quantiles'][1]:.2f}, median {c['gradient_share_quantiles'][2]:.2f}; "
          f"cells whose gradient rests on under half of their pixels: {c['gradient_from_under_half_of_pixels']}.",
          f"- Top 20% of cells by gradient ({t['cells']} cells): coastal {100 * t['coastal_share_of_top']:.0f}% against {100 * t['coastal_share_of_cells']:.0f}% of all cells; "
          f"outer-ring cells {t['edge_in_top']} of the top against {100 * t['edge_share_of_cells']:.0f}% of all cells.",
          f"- Spearman between a cell's gradient and the share of its pixels that have a gradient: {stats['cell_gradient_vs_valid_pixel_share_spearman']:.2f}."]
    return "\n".join(L)

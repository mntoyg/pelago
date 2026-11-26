"""Pure aggregation onto the 0.05 degree grid. No network, no database. Missing is None, never 0.

Every function drops non-finite numbers (NaN, +-Infinity) as missing before it computes anything.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Iterable, Sequence

import numpy as np

from .grid import CoordinateError, cell_centre, cell_id

KM_PER_DEG = 111.195   # mean Earth radius 6371.0088 km; used for gradients and snap distances


def finite(x) -> float | None:
    """float(x) if it is a finite real number, else None. bool, str, None, NaN, Infinity -> None."""
    if x is None or isinstance(x, (bool, str, bytes)):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def block_mean(pixels: Iterable[tuple[float, float, float | None]], cells: set[int],
               min_valid_fraction: float = 0.0) -> dict[int, tuple[float, int, int]]:
    """Mean of the valid pixels per cell: {cell_id: (mean, n_valid, n_total)} for cells with a result.

    A pixel belongs to the cell that cell_id() gives for its position. Pixels outside `cells` are ignored. A cell is
    left out (no result) when it has no valid pixel, or when n_valid / n_total < min_valid_fraction. n_total counts
    every pixel that lies in the cell, valid or not, so land/cloud gaps lower the fraction.
    """
    total: dict[int, int] = defaultdict(int)
    count: dict[int, int] = defaultdict(int)
    acc: dict[int, float] = defaultdict(float)
    for lat, lon, val in pixels:
        try:
            cid = cell_id(lat, lon)
        except CoordinateError:
            continue
        if cid not in cells:
            continue
        total[cid] += 1
        v = finite(val)
        if v is not None:
            count[cid] += 1
            acc[cid] += v
    out = {}
    for cid, n in count.items():
        if n and n / total[cid] >= min_valid_fraction:
            out[cid] = (acc[cid] / n, n, total[cid])
    return out


def sst_gradient_c_per_km(lats: Sequence[float], lons: Sequence[float], field: np.ndarray) -> np.ndarray:
    """Magnitude of the horizontal SST gradient, deg C per km, on the field's own grid.

    field[i, j] is the temperature at (lats[i], lons[j]); NaN = missing. Central differences; a pixel whose four
    neighbours are not all valid (or which is itself missing, or on the array edge) is NaN. Longitude spacing is
    converted to km with the cosine of the pixel's latitude.
    """
    f = np.asarray(field, dtype=float)
    la = np.asarray(lats, dtype=float)
    lo = np.asarray(lons, dtype=float)
    out = np.full(f.shape, np.nan)
    if f.ndim != 2 or f.shape[0] < 3 or f.shape[1] < 3 or f.shape != (la.size, lo.size):
        return out
    dlat_km = abs(float(la[-1] - la[0])) / (la.size - 1) * KM_PER_DEG
    dlon_deg = abs(float(lo[-1] - lo[0])) / (lo.size - 1)
    # derivative along latitude index and longitude index; the sign of the axis does not matter for a magnitude
    gy = (f[2:, 1:-1] - f[:-2, 1:-1]) / (2 * dlat_km)
    dlon_km = (dlon_deg * KM_PER_DEG * np.cos(np.radians(la[1:-1])))[:, None]
    gx = (f[1:-1, 2:] - f[1:-1, :-2]) / (2 * dlon_km)
    mag = np.hypot(gx, gy)
    mag[~np.isfinite(mag)] = np.nan
    out[1:-1, 1:-1] = mag
    return out


def window_max(times_utc: Sequence[datetime], values: Sequence, start: datetime, end: datetime) -> float | None:
    """Maximum of the hourly values in [start, end] (inclusive, UTC), or None unless EVERY hour of the window is
    present and finite. A partial window would understate the worst hour at sea, so it counts as missing."""
    need = set()
    t = start
    from datetime import timedelta
    while t <= end:
        need.add(t)
        t += timedelta(hours=1)
    got: dict[datetime, float] = {}
    for t, v in zip(times_utc, values):
        fv = finite(v)
        if start <= t <= end and fv is not None:
            got[t] = fv
    if not need or set(got) != need:
        return None
    return max(got.values())


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular distance in km (good to a fraction of a percent at these distances)."""
    mid = math.radians((lat1 + lat2) / 2)
    return math.hypot((lat1 - lat2) * KM_PER_DEG, (lon1 - lon2) * KM_PER_DEG * math.cos(mid))


def nearest_assign(cells: Iterable[int], points: Sequence[tuple[float, float, float | None]],
                   max_km: float) -> dict[int, tuple[float | None, float]]:
    """Nearest-neighbour from point values to cells. Only points with a finite value are candidates.

    Returns {cell_id: (value, distance_km)} for every cell; value is None when no valid point lies within max_km.
    Ties go to the point that comes first in `points`.
    """
    valid = [(la, lo, finite(v)) for la, lo, v in points]
    valid = [(la, lo, v) for la, lo, v in valid if v is not None and finite(la) is not None and finite(lo) is not None]
    out: dict[int, tuple[float | None, float]] = {}
    for cid in cells:
        clat, clon = (float(x) for x in cell_centre(cid))
        best = None
        for la, lo, v in valid:
            d = km_between(clat, clon, la, lo)
            if best is None or d < best[0]:
                best = (d, v)
        out[cid] = (best[1], best[0]) if best is not None and best[0] <= max_km else (None, best[0] if best else math.inf)
    return out

"""Choose the spots: pure, no database. Best FSI first, each next spot at least min_spacing_km (great-circle) from every chosen one.

Spacing is measured between cell centres on a sphere (haversine, R = 6 371 008.7714 m, the radius PostGIS uses for sphere
distances), never in cell-index steps. Exactly min_spacing_km is allowed ("at least"). A candidate with a NaN, infinite or
out-of-range coordinate, a coordinate outside the area bbox, or a non-finite FSI is dropped and counted, never picked.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_R_KM = 6371.0087714150598
MAX_PICKS = 5
MIN_PICKS = 3


@dataclass(frozen=True)
class Candidate:
    cell_id: int
    lat: float
    lon: float
    fsi: float


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(min(1.0, math.sqrt(a)))


def _valid(c: Candidate, bbox) -> bool:
    vals = (c.lat, c.lon, c.fsi)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vals):
        return False
    if isinstance(c.cell_id, bool) or not isinstance(c.cell_id, int):
        return False
    if not (-90 <= c.lat <= 90 and -180 <= c.lon <= 180 and 0 <= c.fsi <= 100):
        return False
    lon0, lat0, lon1, lat1 = bbox
    return lon0 <= c.lon <= lon1 and lat0 <= c.lat <= lat1


def pick(candidates: list[Candidate], bbox, min_spacing_km: float, limit: int = MAX_PICKS) -> tuple[list[Candidate], int]:
    """(picked in rank order, number of candidates dropped as invalid). Deterministic: ties on FSI go to the lower cell id."""
    if isinstance(min_spacing_km, bool) or not isinstance(min_spacing_km, (int, float)) or not math.isfinite(min_spacing_km) \
            or min_spacing_km <= 0:
        raise ValueError("min_spacing_km must be a finite number greater than 0")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PICKS:
        raise ValueError("limit must be an integer from 1 to 5")
    good = [c for c in candidates if _valid(c, bbox)]
    dropped = len(candidates) - len(good)
    seen, uniq = set(), []
    for c in sorted(good, key=lambda c: (-c.fsi, c.cell_id)):
        if c.cell_id not in seen:
            seen.add(c.cell_id)
            uniq.append(c)
    chosen: list[Candidate] = []
    for c in uniq:
        if len(chosen) == limit:
            break
        if all(haversine_km(c.lat, c.lon, o.lat, o.lon) >= min_spacing_km for o in chosen):
            chosen.append(c)
    return chosen, dropped

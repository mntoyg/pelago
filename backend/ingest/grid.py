"""pelago-cell-v1: the 0.05 degree cell-id scheme. Python twin of pelago.cell_id() in db/schema.sql.

Integer arithmetic only. Floats are never used for the index: (12.3 + 90) / 0.05 is 2045.9999999999998 in binary
floating point, which puts a point on a cell edge into the wrong row. Inputs go through repr() -> Decimal and are rounded
half away from zero to 0.0001 degree, exactly like PostgreSQL round(numeric).
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterator

CELL_E4 = 500            # cell size in units of 0.0001 degree (0.05 degree)
LAT_OFFSET_E4 = 900000   # lat_e4 + 900000 >= 0
LON_OFFSET_E4 = 1800000
LON_CELLS = 7200
MAX_CELL_ID = 25919999


class CoordinateError(ValueError):
    """Out-of-range or non-finite coordinate (PostgreSQL error 22003 in the SQL twin)."""


def to_e4(value: float | int | str | Decimal) -> int:
    """Degrees -> integer count of 0.0001 degree, half away from zero. Rejects NaN, Infinity and bools."""
    if isinstance(value, bool):
        raise CoordinateError("coordinate must be a number")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CoordinateError("coordinate is not finite")
        d = Decimal(repr(value))
    else:
        try:
            d = Decimal(str(value)) if not isinstance(value, Decimal) else value
        except Exception as exc:  # decimal.InvalidOperation
            raise CoordinateError("coordinate is not a number") from exc
        if not d.is_finite():
            raise CoordinateError("coordinate is not finite")
    return int((d * 10000).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def cell_id(lat: float | str | Decimal, lon: float | str | Decimal) -> int:
    la, lo = to_e4(lat), to_e4(lon)
    if la < -900000 or la >= 900000 or lo < -1800000 or lo >= 1800000:
        raise CoordinateError(f"coordinate out of range: lat={lat}, lon={lon}")
    return ((la + LAT_OFFSET_E4) // CELL_E4) * LON_CELLS + (lo + LON_OFFSET_E4) // CELL_E4


def cell_centre(cid: int) -> tuple[Decimal, Decimal]:
    """(lat, lon) of the cell centre as exact Decimals with 4 decimals."""
    if not 0 <= cid <= MAX_CELL_ID:
        raise CoordinateError("cell id out of range")
    lat_idx, lon_idx = divmod(cid, LON_CELLS)
    return (Decimal(lat_idx * CELL_E4 - LAT_OFFSET_E4 + 250) / 10000,
            Decimal(lon_idx * CELL_E4 - LON_OFFSET_E4 + 250) / 10000)


def cells_in_bbox(min_lon, min_lat, max_lon, max_lat) -> list[int]:
    """Cell ids whose CENTRE lies inside [min, max) of the bbox, row by row from the south-west.

    The bbox corners must lie on 0.05 degree edges (checked), so no cell is cut by the box.
    """
    lo0, la0, lo1, la1 = (to_e4(x) for x in (min_lon, min_lat, max_lon, max_lat))
    for v in (lo0, la0, lo1, la1):
        if v % CELL_E4:
            raise CoordinateError("bbox edge is not on the 0.05 degree grid")
    if not (lo0 < lo1 and la0 < la1):
        raise CoordinateError("empty bbox")
    out = []
    for la in range(la0, la1, CELL_E4):
        for lo in range(lo0, lo1, CELL_E4):
            out.append(cell_id(Decimal(la + 250) / 10000, Decimal(lo + 250) / 10000))
    return out


def iter_cell_index(cids: list[int]) -> Iterator[tuple[int, int, int]]:
    for c in cids:
        yield (c,) + divmod(c, LON_CELLS)

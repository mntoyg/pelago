"""Build the land layer for one area: read a Natural Earth land shapefile (untrusted download) and write a small GeoJSON
clipped to the area bbox plus a margin.

Standalone on purpose (standard library only, no import of this package) so it can run as
    python -I backend/masks/build_land.py --shp <folder>/ne_10m_land.shp --bbox 100.7 12.2 101.2 13.2 --out land.geojson
with -I, which keeps the folder of the download and the current directory off the import path.

The clip is Sutherland-Hodgman per ring against the rectangle. On a concave ring it can leave zero-width edges along the
window; the database repairs them (ST_MakeValid) and they lie at least `margin` degrees away from every cell, so they cannot
change a mask result. Output coordinates are rounded to 5 decimals (about 1 m).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

MAX_SHP_BYTES = 200 * 1024 * 1024      # ne_10m_land.shp is 7 MB; anything far bigger is not the file we expect
MAX_POINTS = 5_000_000
MAX_PARTS = 200_000
SHAPE_POLYGON = 5


class ShapefileError(ValueError):
    pass


def read_polygons(data: bytes):
    """Yield (rings) for each polygon record; rings is a list of [(x, y), ...]. Raises ShapefileError on any inconsistency."""
    n = len(data)
    if n < 100 or n > MAX_SHP_BYTES:
        raise ShapefileError("file size out of range")
    if struct.unpack(">i", data[0:4])[0] != 9994:
        raise ShapefileError("not a shapefile")
    if struct.unpack("<i", data[28:32])[0] != 1000:
        raise ShapefileError("unsupported shapefile version")
    declared = struct.unpack(">i", data[24:28])[0] * 2
    if declared != n:
        raise ShapefileError("declared length does not match the file")
    if struct.unpack("<i", data[32:36])[0] != SHAPE_POLYGON:
        raise ShapefileError("not a polygon shapefile")
    pos, total_points = 100, 0
    while pos < n:
        if pos + 8 > n:
            raise ShapefileError("truncated record header")
        clen = struct.unpack(">i", data[pos + 4:pos + 8])[0] * 2
        start, end = pos + 8, pos + 8 + clen
        if clen < 44 or end > n:
            raise ShapefileError("bad record length")
        stype = struct.unpack("<i", data[start:start + 4])[0]
        pos = end
        if stype == 0:                      # null shape
            continue
        if stype != SHAPE_POLYGON:
            raise ShapefileError("unexpected shape type in record")
        nparts, npoints = struct.unpack("<ii", data[start + 36:start + 44])
        if not (0 < nparts <= MAX_PARTS and 0 < npoints <= MAX_POINTS) or npoints < nparts:
            raise ShapefileError("bad part or point count")
        total_points += npoints
        if total_points > MAX_POINTS * 4:
            raise ShapefileError("too many points")
        if 44 + 4 * nparts + 16 * npoints != clen:
            raise ShapefileError("record length does not match its counts")
        parts = list(struct.unpack(f"<{nparts}i", data[start + 44:start + 44 + 4 * nparts]))
        if parts[0] != 0 or any(b <= a for a, b in zip(parts, parts[1:])) or parts[-1] >= npoints:
            raise ShapefileError("bad part offsets")
        flat = struct.unpack(f"<{2 * npoints}d", data[start + 44 + 4 * nparts:end])
        if not all(math.isfinite(v) for v in flat):
            raise ShapefileError("non-finite coordinate")
        pts = list(zip(flat[0::2], flat[1::2]))
        if any(not (-180.0 <= x <= 180.0 and -90.0 <= y <= 90.0) for x, y in pts):
            raise ShapefileError("coordinate out of range")
        bounds = parts + [npoints]
        yield [pts[a:b] for a, b in zip(bounds, bounds[1:])]


def signed_area(ring) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])) / 2.0


def clip_ring(ring, win):
    """Sutherland-Hodgman against the rectangle win = (x0, y0, x1, y1). Returns [] if nothing is left."""
    x0, y0, x1, y1 = win
    if ring and ring[0] == ring[-1]:
        ring = ring[:-1]
    edges = [
        (lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
        (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
        (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
        (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1)),
    ]
    out = ring
    for inside, cut in edges:
        if not out:
            return []
        src, out = out, []
        prev = src[-1]
        for cur in src:
            if inside(cur):
                if not inside(prev):
                    out.append(cut(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cut(prev, cur))
            prev = cur
    return out if len(out) >= 3 else []


def _inside_ring(pt, ring) -> bool:
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def clipped_multipolygon(records, win, digits: int = 5):
    """GeoJSON MultiPolygon coordinates of everything inside the window. Shapefile rings: clockwise = outer, else hole."""
    polys = []
    for rings in records:
        outers, holes = [], []
        for r in rings:
            xs, ys = [p[0] for p in r], [p[1] for p in r]
            if max(xs) < win[0] or min(xs) > win[2] or max(ys) < win[1] or min(ys) > win[3]:
                continue
            is_outer = signed_area(r) < 0          # decided on the unclipped ring
            c = clip_ring(r, win)
            if not c:
                continue
            c = [(round(x, digits), round(y, digits)) for x, y in c]
            (outers if is_outer else holes).append(c)
        for o in outers:
            polys.append([o + [o[0]]])
        for h in holes:
            for poly in polys:
                if _inside_ring(h[0], poly[0][:-1]):
                    poly.append(h + [h[0]])
                    break
    return [[[list(p) for p in ring] for ring in poly] for poly in polys]


def build(shp: Path, bbox, margin: float, out: Path) -> dict:
    data = shp.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    win = (bbox[0] - margin, bbox[1] - margin, bbox[2] + margin, bbox[3] + margin)
    coords = clipped_multipolygon(read_polygons(data), win)
    if not coords:
        raise ShapefileError("no land inside the window; refusing to write an empty layer")
    doc = {"type": "FeatureCollection",
           "features": [{"type": "Feature", "properties": {"layer": "land"},
                         "geometry": {"type": "MultiPolygon", "coordinates": coords}}],
           "pelago": {"source": "Natural Earth 10m land (public domain)", "source_shp_sha256": sha,
                      "window": list(win), "margin_deg": margin}}
    out.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    return {"polygons": len(coords), "vertices": sum(len(r) for p in coords for r in p), "source_sha256": sha}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shp", required=True, type=Path)
    ap.add_argument("--bbox", required=True, nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    ap.add_argument("--margin", type=float, default=0.5, help="degrees added on every side (must exceed the buffer)")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    if not (math.isfinite(a.margin) and 0.1 <= a.margin <= 5):
        print("margin must be between 0.1 and 5 degrees", file=sys.stderr)
        return 2
    try:
        info = build(a.shp, a.bbox, a.margin, a.out)
    except (OSError, ShapefileError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())

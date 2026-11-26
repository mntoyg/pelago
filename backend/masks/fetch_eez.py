"""Build-time download of the Marine Regions EEZ and Internal Waters polygons for one area (untrusted external data).

Standalone (standard library only) so it can run with -I:
    python -I backend/masks/fetch_eez.py --bbox 100.7 12.2 101.2 13.2 --out-dir backend/config/layers/th-chonburi-coast

Source: Marine Regions public WFS, layers `eez` (v12, 2023) and `eez_internal_waters` (v4, 2023), licence CC BY 4.0
(Flanders Marine Institute, VLIZ). The provider asks users not to re-publish its downloads, so the output files are listed in
backend/.gitignore and are NOT committed: every deployment runs this script once. No form, account or key is involved.

Only the host geo.vliz.be over https is contacted. The response is size-capped, parsed as JSON and checked before a file is
written; the file is written atomically. Nothing is printed except counts and sha256 values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "geo.vliz.be"
PATH = "/geoserver/MarineRegions/wfs"
LAYERS = {"eez": "eez.geojson", "eez_internal_waters": "internal_waters.geojson"}
MAX_BYTES = 30 * 1024 * 1024
TIMEOUT_S = 90
KEEP = ("mrgid", "geoname", "territory1", "sovereign1", "iso_ter1", "pol_type")


def request_url(layer: str, bbox) -> str:
    """WFS 2.0.0 puts latitude first for EPSG:4326, so the bbox is sent as lat0,lon0,lat1,lon1 with the URN crs."""
    lon0, lat0, lon1, lat1 = bbox
    q = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": f"MarineRegions:{layer}",
         "outputFormat": "application/json",
         "bbox": f"{lat0},{lon0},{lat1},{lon1},urn:ogc:def:crs:EPSG::4326"}
    return f"https://{HOST}{PATH}?{urllib.parse.urlencode(q, safe=':,')}"


def check_collection(doc) -> int:
    """Raise ValueError unless doc is a non-empty FeatureCollection of finite Polygon/MultiPolygon coordinates in range."""
    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection" or not isinstance(doc.get("features"), list):
        raise ValueError("not a FeatureCollection")
    if not doc["features"]:
        raise ValueError("no feature overlaps the area (empty layer)")
    n = 0
    for f in doc["features"]:
        g = f.get("geometry") if isinstance(f, dict) else None
        if not isinstance(g, dict) or g.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError("feature is not a polygon")
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            for ring in poly:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError("ring is not closed")
                for pt in ring:
                    x, y = pt[0], pt[1]
                    if isinstance(x, bool) or isinstance(y, bool) or not (math.isfinite(x) and math.isfinite(y)) \
                            or not (-180 <= x <= 180 and -90 <= y <= 90):
                        raise ValueError("coordinate not finite or out of range")
                n += len(ring)
    return n


def fetch(layer: str, bbox) -> bytes:
    url = request_url(layer, bbox)
    if urllib.parse.urlsplit(url).hostname != HOST:      # defensive: the URL is built here, never taken from input
        raise ValueError("unexpected host")
    req = urllib.request.Request(url, headers={"User-Agent": "pelago-layer-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("response larger than the cap")
    return data


def write_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".part-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    ap.add_argument("--out-dir", required=True, type=Path)
    a = ap.parse_args(argv)
    margin = 0.25                       # the provider returns whole features that touch the box; a little slack is harmless
    bbox = (a.bbox[0] - margin, a.bbox[1] - margin, a.bbox[2] + margin, a.bbox[3] + margin)
    if not a.out_dir.is_dir():
        print("out-dir must exist", file=sys.stderr)
        return 2
    for layer, name in LAYERS.items():
        try:
            doc = json.loads(fetch(layer, bbox).decode("utf-8"))
            vertices = check_collection(doc)
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            print(f"{layer}: failed ({type(exc).__name__}): {exc}", file=sys.stderr)
            return 1
        slim = {"type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {k: f.get("properties", {}).get(k) for k in KEEP},
                              "geometry": f["geometry"]} for f in doc["features"]],
                "pelago": {"source": f"Marine Regions WFS MarineRegions:{layer}", "licence": "CC BY 4.0",
                           "attribution": "Flanders Marine Institute (VLIZ), Maritime Boundaries Geodatabase"}}
        out = json.dumps(slim, separators=(",", ":")).encode("utf-8")
        write_atomic(a.out_dir / name, out)
        print(f"{layer}: features={len(slim['features'])} vertices={vertices} bytes={len(out)} "
              f"sha256={hashlib.sha256(out).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

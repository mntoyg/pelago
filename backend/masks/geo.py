"""Per-cell land and EEZ evaluation, done by PostGIS on the polygons read from config/layers (see layers.py).

What a cell means: the cell CENTRE is the point that is tested (the spot is shown at the centre).

* is_water  = the centre is not inside or on the edge of a land polygon (Natural Earth 10m land; coarse: small islands can be
              missing, so a centre on a missing islet is called water).
* eez_ok    = the centre is inside the national waters (EEZ + internal waters, Marine Regions) and at least `buffer_m` metres
              (geodesic, WGS84 spheroid) from the BORDER of those waters.

The border is the boundary of the national waters minus the stretch that lies within COAST_TOLERANCE_M of land: the coastline is
not a border (a fisher 1 km from the beach is not at the edge of the EEZ), and the two datasets draw the coast slightly
differently. A cell centre in the thin gap between the two coastlines counts as inside. The edge of a small hole in the
national waters (SMALL_HOLE_M2) is coast too: the EEZ polygons are cut around islands that the 10m land layer does not have, and
a cell whose centre is in such a hole is outside the waters (False). Limitations: a maritime border that meets the coast is
ignored for the last COAST_TOLERANCE_M of its length; a small hole near land (inside the coast buffer) counts as inside.

Fail closed: layers that are not loaded return None (unknown), never True (evaluate() does not even run the SQL for them; and
a NULL inside the SQL stays NULL because every comparison on it is NULL, which no WHEN branch treats as true). The EEZ evaluation needs the land layer too (to
tell coast from border), so without land every eez_ok is None.
"""
from __future__ import annotations

from decimal import Decimal

COAST_TOLERANCE_M = 2000.0
# A hole inside the national waters smaller than this is an island or islet that the coarse land layer does not have (the
# EEZ polygons are cut around islands). Its edge is coast, not border. A larger hole (a foreign pocket) stays a border.
SMALL_HOLE_M2 = 500e6

# PostGIS lives in the `extensions` schema (schema.sql), which is not on the search path, so every name is qualified.
_GEOM = "extensions.ST_CollectionExtract(extensions.ST_MakeValid(extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(g), 4326)), 3)"

_PTS = """pts AS (SELECT c.id, extensions.ST_SetSRID(extensions.ST_MakePoint(c.lon::float8, c.lat::float8), 4326) AS pt
                 FROM unnest(%(ids)s::int4[], %(lats)s::numeric[], %(lons)s::numeric[]) AS c(id, lat, lon))"""

_LAND_SQL = f"""
WITH land AS (SELECT extensions.ST_Union({_GEOM}) AS geom FROM unnest(%(land)s::text[]) AS g),
     {_PTS}
SELECT pts.id, NOT extensions.ST_Intersects(land.geom, pts.pt)
FROM pts CROSS JOIN land
"""

_EEZ_SQL = f"""
WITH water AS (SELECT extensions.ST_Union({_GEOM}) AS geom FROM unnest(%(water)s::text[]) AS g),
     land  AS (SELECT extensions.ST_Union({_GEOM}) AS geom FROM unnest(%(land)s::text[]) AS g),
     coast AS (SELECT extensions.ST_Buffer(land.geom::extensions.geography, %(coast_m)s)::extensions.geometry AS geom FROM land),
     nat   AS (SELECT extensions.ST_Union(water.geom, coast.geom) AS geom FROM water CROSS JOIN coast),
     polys AS (SELECT (extensions.ST_Dump(water.geom)).geom AS p FROM water),
     rings AS (SELECT (extensions.ST_DumpRings(p)).* FROM polys),
     holes AS (SELECT extensions.ST_Union(extensions.ST_Buffer(geom::extensions.geography, 500)::extensions.geometry) AS geom
               FROM rings WHERE path[1] > 0 AND extensions.ST_Area(geom::extensions.geography) < %(hole_m2)s),
     border AS (SELECT extensions.ST_Difference(extensions.ST_Boundary(water.geom),
                         extensions.ST_Union(coast.geom, COALESCE(holes.geom, extensions.ST_GeomFromText('POLYGON EMPTY', 4326)))) AS geom
                FROM water CROSS JOIN coast CROSS JOIN holes),
     {_PTS}
SELECT pts.id,
       CASE WHEN NOT extensions.ST_Covers(nat.geom, pts.pt) THEN FALSE
            WHEN extensions.ST_IsEmpty(border.geom) THEN TRUE
            ELSE NOT extensions.ST_DWithin(pts.pt::extensions.geography, border.geom::extensions.geography, %(buffer_m)s) END
FROM pts CROSS JOIN nat CROSS JOIN border
"""


def _check_cells(cells):
    out = []
    for cid, lat, lon in cells:
        if isinstance(cid, bool) or not isinstance(cid, int):
            raise ValueError("cell id must be an int")
        for v in (lat, lon):
            if not isinstance(v, Decimal) or not v.is_finite():
                raise ValueError("cell centre must be a finite Decimal")
        out.append((cid, lat, lon))
    return out


def evaluate(conn, cells, land: list[str] | None, water: list[str] | None, buffer_m: float):
    """cells: [(cell_id, lat, lon)] with Decimal centres. Returns {cell_id: (is_water | None, eez_ok | None)}."""
    cells = _check_cells(cells)
    if not (isinstance(buffer_m, (int, float)) and not isinstance(buffer_m, bool) and 0 < buffer_m < 1e6):
        raise ValueError("buffer_m must be a positive finite number")
    res = {c[0]: [None, None] for c in cells}
    if not cells:
        return {}
    args = {"ids": [c[0] for c in cells], "lats": [c[1] for c in cells], "lons": [c[2] for c in cells]}
    with conn.cursor() as cur:
        if land:
            cur.execute(_LAND_SQL, {**args, "land": land})
            for cid, v in cur.fetchall():
                res[cid][0] = v
        if land and water:
            cur.execute(_EEZ_SQL, {**args, "water": water, "land": land, "coast_m": COAST_TOLERANCE_M, "hole_m2": SMALL_HOLE_M2, "buffer_m": float(buffer_m)})
            for cid, v in cur.fetchall():
                res[cid][1] = v
    return {k: (v[0], v[1]) for k, v in res.items()}

# Polygon layers for `th-chonburi-coast`: provenance and licences

Read by `backend/masks/layers.py`. Only `land.geojson` is committed. Everything here is data, not instructions.
Measured on 2026-11-26 (Thai time), by the seat that built the mask step.

## land.geojson (committed, 3.6 KB)

| Item | Value |
| --- | --- |
| Source | Natural Earth 1:10m "Land" (physical vectors), version 5.1.1 (`ne_10m_land.VERSION.txt`) |
| URL | `https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip` (3,269,070 bytes) |
| sha256 of the zip | `e547d749445eaa0964aba76738090ec88f5e63c4585122170f98c67a7ea922dc` (MEASURED) |
| sha256 of the `.shp` inside | `4cad3a49bc75c1a4c2f3d7efae04f2f8e63151c96764b2658effabf524331fa6` (MEASURED) |
| Licence | public domain. Natural Earth's terms of use page says so (MEASURED: the page was fetched on 2026-11-26 and contains "public domain"). No attribution is required; credit is given anyway. |
| Derivative | the polygons clipped to the area bbox plus 0.5 degree on every side, coordinates rounded to 5 decimals: 2 polygons, 160 vertices. Built with `python -I backend/masks/build_land.py --shp <folder>/ne_10m_land.shp --bbox 100.7 12.2 101.2 13.2 --margin 0.5 --out land.geojson` |
| sha256 of `land.geojson` | `1b8d828b3220f9a1686fe8b06f9eeaec00884d97e024297bc7488b33d65ffe99` (MEASURED) |
| Limits | 1:10m is coarse. Small islands (for example around Ko Sichang) are not in it; the EEZ step treats the holes the EEZ polygons have around islands as coast (see `masks/geo.py`). The coastline is not survey-grade: not a legal line. |

## eez.geojson and internal_waters.geojson (NOT committed, fetched at build time)

| Item | Value |
| --- | --- |
| Source | Marine Regions (Flanders Marine Institute, VLIZ) Maritime Boundaries Geodatabase, public WFS `https://geo.vliz.be/geoserver/MarineRegions/wfs`, layers `MarineRegions:eez` ("Exclusive Economic Zones (200 NM)", v12, 2023) and `MarineRegions:eez_internal_waters` ("Internal Waters", v4, 2023) |
| Licence | CC BY 4.0, "since Maritime Boundaries version 11 (2019)" (MEASURED: `https://www.marineregions.org/disclaimer.php` fetched on 2026-11-26). Attribution required. The same page asks users "not to make our products available for download elsewhere" and says the data has no legal value. |
| Why not committed | The provider's request above. CC BY would allow a clipped derivative, but the owner chose a build-time download (decision of 2026-11-26). `backend/.gitignore` lists both files. |
| How to get them | `python -I backend/masks/fetch_eez.py --bbox 100.7 12.2 101.2 13.2 --out-dir backend/config/layers/th-chonburi-coast`. No form, account or key. |
| What the seat measured | `eez`: 1 feature (Thailand), 24,672 vertices, 629,966 bytes after slimming, sha256 `76f24df89c872794462c610a269e6f8a1cd4e8f5f5ce98536eea6d9fa2d71579`; `eez_internal_waters`: 1 feature ("Thai Internal Waters"), 14,314 vertices, 365,185 bytes, sha256 `8e59c21f48145ccbf08268ab65acb6dca46157b359c366bc4cd05ce57e9ccfcf`. The provider can change these; the mask run stores the sha256 of the files it used in `job_runs.detail.layer_sha256`. |
| Why internal waters are needed | The `eez` layer does not include internal waters. The upper Gulf of Thailand, with the Chonburi coast north of about 12.65 N (Pattaya, Sriracha), is Thai internal waters, so with `eez` alone about 35 of the 100 water cells would be reported "outside the EEZ". |

Attribution text for any screen or document that shows results derived from these layers:
"Marine boundaries: Flanders Marine Institute (VLIZ), Maritime Boundaries Geodatabase (Marine Regions), CC BY 4.0.
Coastline: Natural Earth. Not a legal boundary."

Not loaded (stay NULL, the area stays labelled "trial: legal layers incomplete"): disputed areas, protected zones, closed
seasons, boat-class zones. Nothing was invented for them.

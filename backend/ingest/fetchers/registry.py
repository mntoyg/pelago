"""source_id (from the area config) -> fetcher class. Enforces the licence route and never substitutes another source."""
from __future__ import annotations

from .base import FetchError
from .erddap_etopo_depth import ErddapEtopoDepth
from .erddap_mur_sst import ErddapMurSst
from .erddap_viirs_chl import ErddapViirsChl
from .erddap_viirs_n20_chl import ErddapViirsN20Chl
from .open_meteo_marine import OpenMeteoMarine

REGISTRY = {c.source_id: c for c in (ErddapMurSst, ErddapViirsChl, ErddapViirsN20Chl, ErddapEtopoDepth, OpenMeteoMarine)}


def build(source_id: str, area, **kwargs):
    cls = REGISTRY.get(source_id)
    if cls is None:
        raise FetchError("unknown_source")
    if area.licence_route not in cls.routes:
        raise FetchError("route_not_allowed")       # e.g. Open-Meteo on route B; the config must list an allowed source
    return cls(**kwargs)

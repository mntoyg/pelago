"""Chlorophyll fallback: VIIRS NOAA-20 near-real-time daily, dataset noaacwN20VIIRSchlaDaily (same layout and variable
as the S-NPP dataset; newest time 2026-11-16 when S-NPP's was 2026-11-15, MEASURED 2026-11-26). D11 keeps it in the
area config as the fallback of chl."""
from .erddap_viirs_chl import ErddapViirsChl


class ErddapViirsN20Chl(ErddapViirsChl):
    source_id = "erddap_viirs_n20_chl"
    dataset = "noaacwN20VIIRSchlaDaily"

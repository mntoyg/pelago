// External services and tunables.
// Every endpoint below is a public, key-less API: no secrets belong in this file.

const GIBS_BASE = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/';
export const ESRI_IMAGERY_TILE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
export const ERDDAP_BASE = 'https://coastwatch.pfeg.noaa.gov/erddap/griddap/';
export const OPEN_METEO_MARINE_URL = 'https://marine-api.open-meteo.com/v1/marine';
export const OPEN_METEO_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast';

// Point used for the 7-day wave/wind forecast (off Sattahip, demo location).
export const FORECAST_POINT = { lat: 12.31, lon: 100.92 };

// How often imagery dates and per-spot live data are refreshed (30 minutes).
export const REFRESH_INTERVAL_MS = 18e5;

// Globe raster layers drawn by map/tiles.js, in this object's key order (draw order is set in tiles.js).
// template: {z}/{y}/{x} are tile coordinates, {date} is yesterday's date (YYYY-MM-DD) where a layer is daily.
// maxZoom: highest tile level the layer offers; alpha: layer opacity.
// UNVERIFIED layer ids / tile-matrix sets: confirm against GIBS WMTSCapabilities.xml before relying on them
export const TILE_LAYERS = {
  img: { template: GIBS_BASE + 'BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg', maxZoom: 8, alpha: 1 },
  chl: { template: GIBS_BASE + 'VIIRS_SNPP_L2_Chlorophyll_A/default/{date}/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png', maxZoom: 7, alpha: 0.75 },
  sst: { template: GIBS_BASE + 'GHRSST_L4_MUR_Sea_Surface_Temperature/default/{date}/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png', maxZoom: 7, alpha: 0.75 },
  // layer id UNVERIFIED; daily swath gaps are black, hence 'lighten' blending
  liv: { template: GIBS_BASE + 'VIIRS_SNPP_CorrectedReflectance_TrueColor/default/{date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg', maxZoom: 9, alpha: 0.9 },
};

// FSI v1 inputs per the project guide.
// STARTING weights/targets, untuned: tune from verified catch logs
export const FSI_WEIGHTS = { sst: 1.5, chl: 1.5, depth: 1, moon: 0.5, season: 0.5 };
export const FSI_TARGETS = {
  sst: 29,    // ideal sea surface temperature, °C
  sw: 2.5,    // temperature tolerance (std-dev), °C
  lc: 0,      // ideal log10(chlorophyll-a) -> 1 mg/m³
  lw: 0.5,    // chlorophyll tolerance (std-dev in log10 units)
  bloom: 10,  // chlorophyll above this (mg/m³) is treated as a bloom and scores 0
};

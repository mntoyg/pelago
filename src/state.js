// Shared mutable app state. Objects are exported (never reassigned) so every module sees the same instance.
import { COUNTRIES, ALL_SPOTS, bestSpot } from './data/spots.js';

export const reducedMotion = matchMedia('(prefers-reduced-motion:reduce)').matches;

// What the user has drilled into: country key, then province index, then spot index (null = not chosen).
export const selection = { country: null, province: null, spot: null };

// Camera. lo/la = centre longitude/latitude in degrees, R = globe radius in px (zoom).
export const view = { lo: 100, la: 14, R: 400 };   // what is drawn this frame
export const target = { ...view };                 // where the camera is easing to

// Raster layers currently switched on (see TILE_LAYERS in config.js).
export const layers = { img: true, chl: false, sst: false, liv: true };

// Per-frame / interaction state.
export const runtime = {
  anim: null,   // active fly-to animation { t0, d, a, b, h? } or null
  focus: null,  // ALL_SPOTS-style entry shown in the popup, or null
  hits: [],     // marker hit targets from the last frame: [{ x, y, marker }]
  drag: null,   // active pointer drag { x, y, m } or null
};

// Markers shown at the current drill level: best spot per country, best per province, or every spot in the province.
export function markersInScope() {
  const { country, province } = selection;
  if (!country) return Object.keys(COUNTRIES).map(k => bestSpot(ALL_SPOTS.filter(o => o.countryKey === k)));
  if (province == null) {
    return COUNTRIES[country].provinces.map((p, pi) => bestSpot(ALL_SPOTS.filter(o => o.countryKey === country && o.provinceIndex === pi)));
  }
  return ALL_SPOTS.filter(o => o.countryKey === country && o.provinceIndex === province);
}

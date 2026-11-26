// Drill-down navigation: Asia -> country -> province -> spot. Each step re-aims the camera and re-renders the UI.
import { selection, target, runtime, view, reducedMotion } from './state.js';
import { goalForSelection } from './map/camera.js';
import { renderSelection } from './ui/sidebar.js';

// Select a country (key), province (index) and spot (index). Call go() with no arguments to return to the whole map.
// Deeper levels are ignored unless the levels above them are given.
export function go(country, province, spot) {
  Object.assign(selection, {
    country: country || null,
    province: country && province != null ? province : null,
    spot: country && province != null && spot != null ? spot : null,
  });
  Object.assign(target, goalForSelection());
  runtime.anim = reducedMotion ? null : { t0: performance.now(), d: selection.spot != null ? 1600 : 2300, a: { ...view }, b: target };
  runtime.focus = null;
  renderSelection();
}

// <select> handlers (inline onchange).
export const pickCountry = value => go(value || null);
export const pickProvince = value => go(selection.country, value === '' ? null : +value);

// Click on a marker: go one level deeper.
export function drill(marker) {
  if (!selection.country) go(marker.countryKey);
  else if (selection.province == null) go(marker.countryKey, marker.provinceIndex);
  else go(marker.countryKey, marker.provinceIndex, marker.spotIndex);
}
